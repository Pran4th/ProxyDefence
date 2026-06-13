import os
import asyncpg
from fastapi import FastAPI
from fastembed import TextEmbedding

app = FastAPI(title="Embedding Service")

model = TextEmbedding(
    model_name="BAAI/bge-small-en-v1.5"
)

DB_HOST = os.getenv("DB_HOST", "postgres-db")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "defenseintel")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin123")

pool = None


@app.on_event("startup")
async def startup():
    global pool

    pool = await asyncpg.create_pool(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )

@app.get("/search")
async def semantic_search(q: str):

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
    return {
        "status": "healthy"
    }