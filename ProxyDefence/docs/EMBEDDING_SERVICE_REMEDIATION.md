# Embedding Service Remediation

## Scope

This remediation addresses ARCH-08 by moving `article_embeddings` creation into service startup and making `/health` report readiness instead of a generic healthy flag.

## Startup Guarantees

At startup, the embedding service now:

- loads the `BAAI/bge-small-en-v1.5` embedding model,
- ensures the PostgreSQL `vector` extension exists,
- creates `article_embeddings` if it is missing.

The table shape remains aligned with the documented runtime schema:

- `id SERIAL PRIMARY KEY`
- `article_id INTEGER REFERENCES processed_articles(id) ON DELETE CASCADE`
- `embedding vector(384)`

## Readiness Validation

`GET /health` now reports:

- `database_connected`
- `article_embeddings_exists`
- `embedding_model_ready`
- `ready`

When any readiness check fails, the endpoint returns `503 Service Unavailable` with the same payload so orchestration can detect the failure quickly.

## Preserved Behavior

The public API surface is unchanged:

- `GET /search`
- `GET /generate`
- `GET /health`

Search and generation logic still use the same embedding model and query flow. The only behavioral change is that table setup happens before the service is considered ready.

## Validation Notes

Recommended checks after deployment:

1. Start the service with a fresh database volume and confirm `/health` returns `ready: true`.
2. Restart the service and confirm `article_embeddings` is still present.
3. Call `/search?q=example` and `/generate` to confirm the existing endpoints still function.