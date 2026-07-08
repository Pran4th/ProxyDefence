# Dev MCP Server — Design Spec

**Status:** Approved for planning
**Sub-project:** 1 of 3 (setup/launch, news volume, frontend)

## Problem

Local dev today requires running `scripts/dev/start-local.ps1`, which does solid
pre-flight checks and health-gated startup, but launches the 7 API services and
the frontend each in their own **visible PowerShell window** (only the 3 Kafka
consumers get their output redirected to log files). This means:

- Navigating 8+ windows to find which one has an error
- `logs.ps1`'s per-service log files (`ingest.log`, `ml.log`, etc.) are mostly
  empty because those services' real stdout goes to their own window, not a file
- No reliable way for an external tool (including Claude Code) to manage these
  processes — PIDs captured in `logs/local-pids.json` can't always be acted on
  reliably from outside the window that spawned them (observed directly: a
  `taskkill` on a PID `netstat` showed as LISTENING reported success while the
  service kept serving stale config — `Get-Process`/`tasklist` couldn't see the
  PID at all)

## Goal

A project-specific MCP server that Claude Code can use directly to start/stop/
restart services and to see what's wrong, without the user needing to check
terminal windows.

## Architecture

New package: `tools/dev-mcp/` (own `.venv`; deps: `mcp`, `psutil`, `httpx`).
Registered in a new root `.mcp.json` so Claude Code launches it automatically
over stdio whenever this repo is opened.

The server directly spawns and owns every local process:

- 7 API services (modular-api, ingest-service, ml-service, database-service,
  embedding-service, energy-service, ml-platform)
- 3 Kafka consumers (ml-consumer, db-consumer, embedding-consumer)
- 1 frontend (Vite dev server)

Each is launched via `subprocess.Popen` with `stdout`/`stderr` redirected to
`logs/<service>.log` — no visible windows. Processes are spawned **detached**
(survive the MCP server process exiting) so closing/reopening Claude Code does
not interrupt a running dev environment. Docker-managed infra (PostgreSQL,
Kafka, Elasticsearch) is untouched — still `docker compose up -d` / `down`,
shelled out from the server's `start_all`/`stop_all`.

Startup order and gating logic is ported from `start-local.ps1`: pre-flight
checks (Python/Node/Docker versions, `.env` present, venvs present) → infra up
→ wait for PG/Kafka/ES ports → start services sequentially, each gated on its
port opening then its health endpoint responding → start consumers → start
frontend (detecting its actual bound port from the log, since Vite may shift
ports).

## Components

**`process_manager.py`** — spawns/tracks/kills processes. Owns the PID file
(`logs/mcp-pids.json`): written on spawn, read on server startup to re-attach
to already-running services instead of double-spawning. One function per
lifecycle action (`spawn`, `is_alive`, `stop`, `restart`), each operating on a
single service definition (name, working dir, command, port, health path).

**`service_defs.py`** — static list of the 10 services + their venv paths,
commands, ports, health-check paths, and log file names. Single source of
truth, replacing the duplicated service lists across `start-local.ps1`,
`status.ps1`, and `logs.ps1`.

**`health.py`** — probes a service's port and health endpoint (mirrors
`status.ps1`'s `Write-Status`/`Check-Port`), returns a status enum
(`running` / `degraded` / `down` / `not_started`).

**`log_scanner.py`** — the failure-classification regexes already written in
`start-local.ps1`'s `Inspect-Log` (missing dependency, DB connection refused,
Kafka unavailable, port in use, permission denied, file not found, Python
runtime error, missing env var, timeout), ported as reusable functions so both
`get_logs` and `diagnose` can use them.

**`server.py`** — the MCP server entrypoint, wires the above into tools:

| Tool | Purpose |
|---|---|
| `list_services()` | name/pid/status/port/uptime for all 10 processes + infra containers |
| `get_status()` | aggregated health probe across everything (mirrors `status.ps1`) |
| `get_logs(service, lines=50, errors_only=false)` | tail a service's log, optionally pre-filtered to error-looking lines |
| `diagnose()` | runs `get_status()` + scans every log via `log_scanner`, returns one consolidated "what's wrong right now" report |
| `start_all(skip_infra=false, skip_frontend=false)` | full startup sequence |
| `stop_all(skip_infra=false)` | stop all tracked processes + optionally `docker compose down` |
| `start_service(name)` / `stop_service(name)` / `restart_service(name)` | single-service control |

## Data flow

```
Claude Code (MCP client)
  <-> tools/dev-mcp/server.py (stdio)
        -> process_manager.py -> subprocess.Popen (10 detached processes)
                               -> logs/<service>.log (stdout+stderr)
                               -> logs/mcp-pids.json (PID tracking)
        -> health.py -> HTTP probes to each service's port/health endpoint
        -> log_scanner.py -> reads logs/*.log, classifies failures
        -> docker compose (infra only, unchanged)
```

## Error handling

- `start_service`/`start_all` surface the same fail-fast diagnostics
  `start-local.ps1` already has: if a process exits immediately or its port/
  health check times out, the tool returns the failure stage, reason, and the
  last N log lines — not a silent hang.
- `diagnose()` never throws on a down service — a `down`/`not_started` status
  is a normal result, not an error.
- If `logs/mcp-pids.json` references a PID that's no longer running (crashed,
  or killed outside the MCP), `list_services`/`get_status` report it as
  `crashed` rather than erroring, and `restart_service` clears the stale entry
  before respawning.

## What happens to the existing scripts

`start-local.ps1`, `stop-local.ps1`, `status.ps1`, `logs.ps1`, and the
per-service `start-*.ps1` scripts are kept as-is for manual fallback (e.g.
running a single service by hand without Claude Code). `CLAUDE.md`'s
documented dev workflow is updated to list the MCP tools as the primary path.

## Testing

- Unit tests for `log_scanner.py`'s classification against fixture log
  snippets (one per failure category already handled).
- Manual verification pass (this is a dev-tooling change, not a service with
  its own test suite): `start_all` from a clean state, confirm all 10
  processes + infra report healthy via `get_status`, confirm log files are
  populated for every service (not just consumers), kill one service process
  externally and confirm `list_services`/`diagnose` detect the crash, then
  `restart_service` recovers it, then `stop_all` leaves no stray processes
  (verified via `Get-Process`/`netstat` showing nothing on the 8 ports).
