# Security and Validation Status

## Completed checks

| Check | Result | Evidence |
| --- | --- | --- |
| Frontend production dependencies | Pass | `npm audit --omit=dev` reports zero vulnerabilities after dependency remediation |
| Frontend production build | Pass | `npm run build` |
| Command Center browser path | Pass | `npm run test:e2e` |
| Secrets committed to Git | Pass | `.env` is ignored; only `.env.example` is tracked |
| JWT secret production guard | Pass | Staging/production reject placeholder or short JWT secrets at startup |
| Password storage | Pass | Shared bcrypt password-hashing context is used |
| Authenticated pilot replay | Pass | `scripts/demo/verify-pilot-readiness.ps1` |
| API browser security headers | Pass | Shared request middleware sets `nosniff`, frame, referrer, and permissions headers |
| Full live validation runner | Pass with documented warnings | 59 checks: 49 pass, 0 fail, 10 warnings in the complete local-stack run |

## Current validation warnings

The warnings are deliberately retained rather than converted into green claims:

- The modular API health response does not expose external LLM-provider
  connectivity. Copilot itself returned a response during the live run.
- The optional supervisor-agent request can exceed the 90-second validation
  budget because it chains specialists and an external LLM. A direct
  authenticated request did return content in 43 seconds; it is not part of
  the pilot command-response path and should not be used where bounded latency
  is required.
- Kafka consumer-group listing requires broker-admin access. Topic, consumer
  processing, PostgreSQL, Elasticsearch, and embedding checks passed.
- Two optional in-process feature/GDELT validators are run from the modular API
  environment, which intentionally does not include the ML platform's NumPy
  dependency. Their service-level checks passed.
- No generic model is deployed through the ML platform's generic prediction
  endpoint, so generic-prediction checks are skipped. The specialised risk
  serving path used by the energy service is separately exercised.
- One later full-suite run recorded a single search timeout while the endpoint
  was otherwise responsive. Ten immediate authenticated search requests and a
  subsequent frontend-category run completed successfully (6/6). Treat this
  as a transient reliability observation to monitor, not proof of a resolved
  load-test issue.

## Deployment hardening required before internet exposure

The current `docker-compose.yml` is a local-development infrastructure file,
not a production-security posture. Its Kafka (9092), Elasticsearch (9200),
and PostgreSQL (host 5434) mappings are restricted to `127.0.0.1` for
developer access. Kafka is configured with PLAINTEXT transport and
Elasticsearch is configured for local development.

Before a public deployment:

1. Do not publish Kafka, PostgreSQL, or Elasticsearch ports to the internet.
2. Use a private network/security group and TLS/authentication for every
   infrastructure service.
3. Set a high-entropy unique `JWT_SECRET_KEY`, rotate it through a secret
   manager, and set a short access-token lifetime appropriate for operators.
   Staging and production now refuse a placeholder or a secret shorter than
   32 characters at startup.
4. Set `CORS_ORIGINS` to the exact production frontend origin; never use a
   wildcard with credentials.
5. Terminate TLS at the ingress/proxy, enforce HTTPS/HSTS, and add rate limits
   for auth and externally reachable APIs.
6. Use a managed secret store for database, Elasticsearch, news, and model API
   credentials; never place production secrets in `.env` committed to source.
7. Run Python dependency scanning (`pip-audit`) in CI for each service and
   block deploys on high/critical findings after triage.
8. Add backup, restore, audit-log retention, and least-privilege database roles
   before using customer data.

## Known product-security boundary

ProxyDefence is decision support only. The approval API records a human decision
state; it does not execute a trade, cargo nomination, or SPR release. Do not
connect it to transactional systems without a separate threat model, approval
control design, and customer security review.

## Validation commands

```powershell
cd services/frontend
npm audit --omit=dev
npm run build
npm run test:e2e

cd ../..
scripts/demo/verify-pilot-readiness.ps1
```

For a full live-stack check, start all services and run:

```powershell
$env:PYTHONPATH = (Get-Location).Path
services/modular-api/.venv/Scripts/python.exe -m validation.runner
```

The full validation runner requires PostgreSQL, Kafka, Elasticsearch, every
service, and any configured external keys. A failed or skipped external
connector must be represented as cached/fallback/disabled—not as live.
