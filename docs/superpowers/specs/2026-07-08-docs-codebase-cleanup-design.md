# Docs & Codebase Cleanup — Design Spec

**Status:** Approved for planning
**Sub-project:** 4 of 4 (setup/launch, news volume, frontend, this one)
**Branch:** `perf-imp`

## Problem

`docs/` has grown to 65 markdown files, most of them dated point-in-time
snapshots (validation reports, "planning document — no implementation
started" proposals, freeze/readiness sign-offs, session bug-logs) rather than
living reference material. Several directly contradict each other or the
current code because they were written days apart during a rapid-change
period — e.g. `PROJECT_IMPLEMENTATION_AUDIT.md` calls `ml-platform` an "empty
shell" and `modular-api` "legacy/unused", both false against the current
code. `CLAUDE.md` itself has known inaccuracies (surfaced by the earlier
codebase research pass): a fictional "Gemini Integration" section, a
description of ml-service sentiment as "keyword-based" when it's actually
DistilBERT/BERT transformer models, an undocumented modular-api gateway, and
an energy-service description covering only ~1/3 of its actual routers.
There's also stray root-level cruft and dead code unrelated to docs.

## Goal

Leave `docs/` holding only living reference material, fix `CLAUDE.md`'s
known inaccuracies, and remove the confirmed-dead files/folders found during
the sweep — without losing any information that's still useful (merge before
delete, don't delete blind).

## Scope & approach

Per your answers: **consolidate** (merge unique content into canonical docs,
then delete the source) rather than archive-everything or delete-everything;
include CLAUDE.md fixes in this pass; clean up all confirmed dead-code/cruft
found; do a broader repo sweep (done — see below) rather than limiting scope
to docs alone.

## Docs cleanup plan

**Keep as-is (~24 files):** `01_LOCAL_SETUP.md`–`06_ENVIRONMENT_VARIABLES.md`
(6 files, after the env-var fix below), `AGENT_DESIGN.md`, `AGENT_ROUTER.md`,
`AI_ORCHESTRATION_ARCHITECTURE.md`, `CONFIDENCE_ENGINE.md`, `CONSTITUTION.md`
(flag as containing aspirational/unbuilt sections — see below), `CONTRIBUTING.md`,
`DATA_ACQUISITION_ARCHITECTURE.md`, `DATA_CONNECTOR_ARCHITECTURE.md`,
`DATA_QUALITY.md`, `DATABASE_GUIDE.md`, `DATASET_LIFECYCLE.md`,
`ENERGY_RUNBOOK.md`, `EVENT_REBUILD_SAFETY.md`, `EXECUTION_ENGINE.md`,
`EXECUTION_SEQUENCE_DIAGRAMS.md`, `HISTORICAL_ACQUISITION_ARCHITECTURE.md`,
`INGESTION_PIPELINE.md`, `KAFKA_GUIDE.md`, `LLM_DESIGN.md` (after the Groq/OpenAI
fix below), `PLANNER_DESIGN.md`, `PROMPT_ARCHITECTURE.md`,
`PROXYDEFENCE_DEVELOPER_HANDBOOK.md`, `REFLECTION_ENGINE.md`,
`RESEARCH_INFRASTRUCTURE.md`, `SPR_DECISION_SYSTEM.md`, `TOOLS.md`,
`ARCHITECTURE.md`.

**Merge then delete source (~11 files):**
| Source | Target | Note before deleting |
|---|---|---|
| `AI_ARCHITECTURE.md` | `AI_ORCHESTRATION_ARCHITECTURE.md` | Note both the direct `/copilot/query` path and the orchestrated `/api/v1/agents/query` path exist; don't let one look like it supersedes the other |
| `PROMPTS.md` | `PROMPT_ARCHITECTURE.md` | PROMPTS.md describes the pre-refactor single-file setup; just delete once confirmed no unique content |
| `SERVICE_ARCHITECTURE.md` | `SERVICE_GUIDE.md` | ~70% overlap; keep SERVICE_GUIDE's more detailed endpoint reference |
| `PIPELINE_VALIDATION.md` | `PIPELINE_GUIDE.md` | Despite the name, has living reference content (failure modes, FK constraints) — port that before deleting |
| `LOCAL_DEVELOPMENT.md` | `01_LOCAL_SETUP.md` / `03_DEVELOPMENT_WORKFLOW.md` | Port any Makefile/pytest/log-tail detail not already in the numbered docs |
| `STARTUP_RUNBOOK.md` | `01_LOCAL_SETUP.md` / `06_ENVIRONMENT_VARIABLES.md` | **Must port the LLM/OPENAI env vars first** — 06 is currently missing them entirely |
| `REQUEST_FLOW.md`, `SEQUENCE_DIAGRAMS.md` | cross-link with `EXECUTION_SEQUENCE_DIAGRAMS.md` | These document the older direct-agent path, which is still real (not dead) — cross-link rather than delete, so a reader isn't confused about which path is current |
| `local-dev-summary.md` | (none — pure session log) | Delete outright, zero reference value |

**Archive/delete (~35 files)** — the dated audit/validation/planning-doc
cluster from the June 19 – July 6 hardening sprint: `ARCHITECTURE_REPORT.md`,
`ARCHITECTURE_REVIEW.md`, `AI_ARCHITECTURE_REVIEW.md`,
`DIGITAL_TWIN_VALIDATION.md`, `EMBEDDING_SERVICE_REMEDIATION.md`,
`END_TO_END_VALIDATION_REPORT.md`, `ENERGY_FRONTEND_INTEGRATION.md`,
`ENERGY_INTEGRATION.md`, `FINAL_INFRASTRUCTURE_VALIDATION.md`,
`GDELT_PIPELINE_VALIDATION.md`, `HISTORICAL_ACQUISITION_PLAN.md`,
`ML_PLATFORM_ARCHITECTURE_REVIEW.md`, `ML_PLATFORM_ARCHITECTURE_v2.md`,
`ML_PLATFORM_FREEZE_REPORT.md`, `ML_PLATFORM_GAP_ANALYSIS.md`,
`ML_PLATFORM_READINESS.md`, `ML_RESEARCH_ROADMAP.md`, `ML_SYSTEM_ANALYSIS.md`,
`PHASE2_ARCHITECTURAL_REVIEW.md`, `PHASE2_ENERGY_INTELLIGENCE_ROADMAP.md`,
`REMEDIATION_PLAN.md`, `RISK_ENGINE_VALIDATION.md`,
`SECURITY_IMPLEMENTATION.md`, `SPR_VALIDATION.md`, `STABILIZATION_TRACKER.md`,
`VALIDATION_REPORT.md`. Move to `docs/archive/` (kept for history per your
earlier "archive, don't delete" instinct on anything with unique content) —
**except** `PROJECT_IMPLEMENTATION_AUDIT.md`, which gets **deleted outright**
since its central claims (ml-platform "empty shell", modular-api
"legacy/unused") are factually wrong and actively misleading if kept around
in any form.

## CLAUDE.md fixes (folded into this pass)

From the earlier research pass, fix:
- Remove the fictional "AI Collaboration (Gemini Integration)" section —
  there is zero Gemini reference in the codebase; the real LLM backend is
  Groq-hosted Llama 3.3/3.1 via an OpenAI-compatible SDK (`backend/shared/llm`)
  — though note per this sweep, the *code's own default* is actually OpenAI
  `gpt-4o`, with Groq/Llama set via `.env`. Document both: the default and
  what this repo's `.env`/`.env.example` actually configure.
- Fix ml-service's sentiment/NER description: real DistilBERT SST-2 sentiment
  and BERT-large-CoNLL03 NER (with fallbacks), not "keyword-based" — keyword
  logic is actually topic/threat/relationship scoring.
- Add a modular-api section (JWT auth, agents/copilot/RAG subsystem, live
  reverse-proxy to Energy Service) — currently a single port-table line.
- Expand the energy-service section to mention the risk-intelligence,
  digital-twin, and procurement/SPR subsystems (currently undocumented,
  roughly 2/3 of that service's actual code).
- Expand ml-platform's schema/capability claims (~39 tables, not 4; no live
  `/train` endpoint; MLflow guarded by try/except and absent from production
  `requirements.txt`).
- Note that ingest-service also runs on an hourly APScheduler, not just the
  manual `/fetch-real-news` trigger.

## Other cleanup (confirmed via sweep)

**Delete:**
- `current_requirements.txt` (empty, zero references)
- `dataset_inventory.py` (superseded by `research/phase0_inventory.py` /
  `phase1_source_study.py`)
- `start_local_log.txt` (stray log; also add a `*_log.txt` pattern to
  `.gitignore` so this doesn't recur)
- `backend/api_service/security.py`, `rate_limit.py`, `repositories/`,
  `services/` (dead duplicate auth/rate-limit code — confirmed zero imports;
  `backend/api/app.py` has its own independent implementation).
  **Keep** `backend/api_service/main.py`/`__init__.py` — that's the live
  Docker entrypoint.
- `research/reports/leakage_audit_20260707_223156.md` (0 bytes, failed run)
- `services/ml-platform/research/notebooks/output/` (empty scratch dir)
- `services/ml-platform/data/reports/` (empty dir — confirm nothing expects
  it to exist at runtime before removing)

**Move/archive:**
- `research/phase0_inventory.py`, `research/phase1_source_study.py` →
  `research/archive/` (job done, outputs already live in `research/inventory/`,
  kept for provenance)
- `research/configs/*.yaml` (3 files) → `research/archive/` per your answer —
  documented as archived examples, not wired into the live
  `services/ml-platform/research/configs/` path the code actually reads

**Fix (not a deletion):**
- Makefile's `pipeline-test`/`seed-demo`/`reset-db` targets point at
  nonexistent `scripts/dev/test/*.ps1` — repoint to the real
  `scripts/*.ps1` locations.

**Needs a decision before deleting:**
- `research/reports/leakage_audit_20260707_223414.md` — an earlier
  `all_features`-mode run superseded by `225601`'s rerun, but it flags extra
  duplicate/correlation pairs not present in the later run. Implementation
  step should diff the two once more and only delete `223414` if `225601` is
  confirmed to be a strict refinement (fixed issues), not a run against a
  different dataset cut.

## Testing / verification

This is a docs/file-reorganization change with no runtime surface for most
of it, except the `backend/api_service` dead-code deletion and the Makefile
fix. Verification plan:
- After deleting `backend/api_service/{security,rate_limit,repositories,services}`:
  re-run `grep -rn "api_service.security\|api_service.rate_limit\|api_service\.repositories"`
  across the repo to confirm zero references remain, then start
  `modular-api` locally and confirm it still boots and `/health` responds
  (proves nothing was silently relying on the deleted modules).
- After the Makefile fix: run `make pipeline-test`/`make seed-demo`/`make reset-db`
  (or whichever are safe to run locally) and confirm they now resolve to a
  real script instead of erroring on a missing path.
- After each doc merge: spot-check that the merge target actually contains
  the ported unique content before deleting the source (e.g. confirm
  `06_ENVIRONMENT_VARIABLES.md` lists the LLM/OPENAI vars before
  `STARTUP_RUNBOOK.md` is deleted).
- Final pass: `git status`/`git diff --stat` review before committing, to
  make sure nothing unintended (e.g. the uncommitted real-secrets
  `.env.example` working-tree change) gets swept into the same commit.
