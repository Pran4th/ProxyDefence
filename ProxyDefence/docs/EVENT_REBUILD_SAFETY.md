# Event Rebuild Safety

## Scope

This document covers the `/rebuild-events` endpoint in `database-service` and the ARCH-09 remediation applied to make the rebuild flow safer.

## Safety Guarantees

The rebuild flow now:

- requires an authenticated admin user,
- validates the required event tables before any destructive action,
- runs the full delete-and-rebuild sequence inside a single PostgreSQL transaction,
- rolls back automatically if any step fails.

## What the Endpoint Does

`POST /rebuild-events` still performs the same logical work:

1. clears the event clustering tables,
2. walks every row in `processed_articles`,
3. rebuilds event intelligence with the existing matching logic,
4. returns the number of articles processed.

The functional behavior is preserved, but partial rebuilds no longer persist if a later article fails.

## Validation Checks

Before deleting anything, the service now verifies that these tables exist:

- `processed_articles`
- `events`
- `event_articles`
- `event_entities`

If any are missing, the endpoint fails fast with `409 Conflict` and the transaction never starts mutating data.

## Authorization

The endpoint now accepts only JWT-authenticated users whose `users.role` value is `admin`.

## Operational Notes

- Because the rebuild now runs in one transaction, it will hold locks longer than the previous implementation.
- The endpoint should be used intentionally, not as a routine background operation.
- If an exception is raised at any point, PostgreSQL rolls back the entire rebuild automatically.