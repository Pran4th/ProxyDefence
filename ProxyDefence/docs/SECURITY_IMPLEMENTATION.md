# Phase 1 Security Implementation

## Scope

This phase removes hardcoded secrets, externalizes runtime configuration, enforces JWT authentication on non-public API routes, and restores audit attribution to the authenticated user.

## Files Changed

- [backend/shared/config.py](../backend/shared/config.py)
- [backend/api_service/security.py](../backend/api_service/security.py)
- [backend/api_service/main.py](../backend/api_service/main.py)
- [backend/api_service/routes/alerts.py](../backend/api_service/routes/alerts.py)
- [backend/api_service/routes/cases.py](../backend/api_service/routes/cases.py)
- [backend/api_service/routes/reports.py](../backend/api_service/routes/reports.py)
- [backend/api_service/routes/watchlists.py](../backend/api_service/routes/watchlists.py)
- [backend/api_service/repositories/intelligence.py](../backend/api_service/repositories/intelligence.py)
- [services/ingest-service/app.py](../services/ingest-service/app.py)
- [services/database-service/app.py](../services/database-service/app.py)
- [services/embedding-service/app.py](../services/embedding-service/app.py)
- [services/conflict-api/app/main.py](../services/conflict-api/app/main.py)
- [services/conflict-api/app/database.py](../services/conflict-api/app/database.py)
- [docker-compose.yml](../docker-compose.yml)
- [.gitignore](../.gitignore)
- [.env.example](../.env.example)

## What Changed

- Removed embedded JWT, database, and API key defaults from service code.
- Added required-environment validation for security-sensitive settings.
- Routed all non-public API routers behind JWT authentication.
- Kept `/auth/register`, `/auth/login`, `/`, and `/health` public.
- Captured authenticated user IDs in audit logging.
- Added owner/admin authorization checks for watchlists, cases, and reports.
- Restricted alert generation to admin users.
- Removed committed token seed artifacts from the repository.

## Risks

- Existing local environments will fail to start until `.env` or equivalent runtime variables are provided.
- Any client relying on anonymous access to protected endpoints will now receive `401` or `403` responses.
- Users can no longer access another user's watchlists/cases/reports unless they are admin.

## Testing Checklist

- Start the stack with a populated `.env` and confirm the API boots.
- Verify `/auth/register` and `/auth/login` still work without a bearer token.
- Verify protected routes return `401` without a token.
- Verify protected routes return `200` with a valid token.
- Verify watchlist/case/report access is limited to the owner or admin.
- Verify alert generation is rejected for non-admin users.
- Verify audit rows contain the authenticated user ID for mutating requests.

## Rollback

- Revert the touched files in this phase.
- Restore the previous `docker-compose.yml` and service defaults if you need a temporary local-only fallback.
- Reintroduce the removed token seed files only if you are reconstructing a pre-hardening snapshot; do not restore them into an active shared branch.

## Operational Note

Rotate any previously committed or exposed secrets before deploying this branch.