import os

import asyncpg
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from fastembed import TextEmbedding

app = FastAPI(title="Embedding Service")

DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "defenseintel")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
if not DB_USER or not DB_PASSWORD:
    raise RuntimeError("Missing required database credentials")

pool = None
model = None

ARTICLE_EMBEDDINGS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS article_embeddings (
    id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES processed_articles(id) ON DELETE CASCADE,
    embedding vector(384) NOT NULL
)
"""


async def ensure_article_embeddings_table(conn):
    await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    await conn.execute(ARTICLE_EMBEDDINGS_TABLE_SQL)


async def get_readiness_state():
    database_connected = False
    article_embeddings_exists = False
    embedding_model_ready = model is not None

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                database_connected = True
                article_embeddings_exists = bool(
                    await conn.fetchval(
                        "SELECT to_regclass('public.article_embeddings') IS NOT NULL"
                    )
                )
        except Exception:
            database_connected = False
            article_embeddings_exists = False

    ready = database_connected and article_embeddings_exists and embedding_model_ready

    return {
        "status": "healthy" if ready else "degraded",
        "ready": ready,
        "database_connected": database_connected,
        "article_embeddings_exists": article_embeddings_exists,
        "embedding_model_ready": embedding_model_ready,
    }


@app.on_event("startup")
async def startup():
    global pool, model

    model = TextEmbedding(
        model_name="BAAI/bge-small-en-v1.5"
    )

    pool = await asyncpg.create_pool(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )

    async with pool.acquire() as conn:
        await ensure_article_embeddings_table(conn)

@app.get("/search")
async def semantic_search(q: str):

    if model is None:
        raise RuntimeError("Embedding model is not ready")

    query_embedding = list(
        model.embed([q])
    )[0].tolist()

    query_vector = (
        "[" +
        ",".join(str(x) for x in query_embedding)
        + "]"
    )

    async with pool.acquire() as conn:

        rows = await conn.fetch(
            """
            SELECT
                p.id,
                p.title,
                p.summary,
                p.topic,
                p.risk_level,
                1 - (
                    ae.embedding <=> $1::vector
                ) AS similarity
            FROM article_embeddings ae
            JOIN processed_articles p
                ON p.id = ae.article_id
            ORDER BY
                ae.embedding <=> $1::vector
            LIMIT 5
            """,
            query_vector
        )

    return {
        "query": q,
        "results": [
            dict(r)
            for r in rows
        ]
    }

@app.get("/generate")
async def generate_embeddings():

    if model is None:
        raise RuntimeError("Embedding model is not ready")

    async with pool.acquire() as conn:

        rows = await conn.fetch(
            """
            SELECT id, title, summary
            FROM processed_articles
            WHERE id NOT IN (
                SELECT article_id
                FROM article_embeddings
            )
            """
        )

        created = 0

        for row in rows:

            text = f"{row['title']} {row['summary'] or ''}"

            embedding = list(
             model.embed([text])
              )[0].tolist()

            embedding_str = "[" + ",".join(
               str(x) for x in embedding
               ) + "]"

            await conn.execute(
    """
    INSERT INTO article_embeddings
    (article_id, embedding)
    VALUES ($1, $2::vector)
    """,
    row["id"],
    embedding_str,
)

            created += 1

    return {
        "embeddings_created": created
    }


@app.get("/health")
async def health():
    readiness_state = await get_readiness_state()
    return JSONResponse(
        status_code=(
            status.HTTP_200_OK
            if readiness_state["ready"]
            else status.HTTP_503_SERVICE_UNAVAILABLE
        ),
        content=readiness_state,
    )