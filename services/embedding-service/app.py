import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from backend.shared.config import SERVICE_VERSION
from backend.shared.logging_config import setup_structlog, get_logger
from backend.shared.observability import (
    HealthBuilder,
    StartupTimer,
    collect_system_metrics,
    db_query_latency,
    pool_usage,
    embedding_latency,
)
from backend.shared.request_middleware import RequestTrackingMiddleware

from db import get_pool, close_pool, ensure_vector_extension
from services.embeddings import load_model, get_model, embed_text, make_vector_str

setup_structlog("embedding-service")
logger = get_logger(__name__)

health = HealthBuilder("embedding-service")


async def check_postgres():
    t0 = time.time()
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.fetchval("SELECT 1")
    latency = (time.time() - t0) * 1000
    db_query_latency.labels(service="embedding-service", operation="health").observe(latency / 1000)
    # Approximate pool usage from internal queue
    if hasattr(pool, "_holders"):
        total = pool._maxsize
        in_use = len(pool._holders)
        pool_usage.labels(service="embedding-service").set(in_use)
        pool_idle_val = total - in_use
        if pool_idle_val < 0:
            pool_idle_val = 0
        try:
            from backend.shared.observability import pool_idle
            pool_idle.labels(service="embedding-service").set(pool_idle_val)
        except Exception:
            pass
    return {"status": "connected", "latency_ms": round(latency, 1)}


def check_model():
    model = get_model()
    if model is not None:
        return {"status": "loaded", "model": "bge-small-en-v1.5"}
    return {"status": "unavailable"}


health.add_check("postgres", check_postgres)
health.add_check("embedding_model", check_model)


@asynccontextmanager
async def lifespan(app: FastAPI):
    timer = StartupTimer("embedding-service")
    timer.phase("model")
    logger.info("embedding_service_starting")
    load_model()
    timer.phase("database")
    await get_pool()
    await ensure_vector_extension()
    timer.phase("ready")
    logger.info("embedding_service_ready", startup=timer.finish())
    sys_metrics = asyncio.create_task(collect_system_metrics("embedding-service"))
    yield
    sys_metrics.cancel()
    await close_pool()
    logger.info("embedding_service_stopped")


app = FastAPI(title="Embedding Service", version=SERVICE_VERSION, lifespan=lifespan)
app.add_middleware(RequestTrackingMiddleware)
Instrumentator().instrument(app).expose(app)


@app.get("/")
async def root():
    return {"service": "embedding-service", "version": SERVICE_VERSION}


async def _readiness_state():
    database_connected = False
    article_embeddings_exists = False

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
            database_connected = True
            article_embeddings_exists = bool(
                await conn.fetchval("SELECT to_regclass('public.article_embeddings') IS NOT NULL")
            )
    except Exception as e:
        logger.error("health_check_failed", error=str(e))

    embedding_model_ready = get_model() is not None
    ready = database_connected and article_embeddings_exists and embedding_model_ready

    return {
        "status": "healthy" if ready else "degraded",
        "ready": ready,
        "database_connected": database_connected,
        "article_embeddings_exists": article_embeddings_exists,
        "embedding_model_ready": embedding_model_ready,
    }


@app.get("/health")
async def health_endpoint():
    return await health.build()


@app.get("/liveness")
async def liveness():
    return {"status": "alive"}


@app.get("/readiness")
async def readiness():
    state = await _readiness_state()
    return JSONResponse(
        status_code=status.HTTP_200_OK if state["ready"] else status.HTTP_503_SERVICE_UNAVAILABLE,
        content=state,
    )


@app.get("/version")
async def version():
    return {"service": "embedding-service", "version": SERVICE_VERSION}


@app.get("/status")
async def status():
    h = await health.build()
    h["readiness"] = await _readiness_state()
    return h


@app.get("/search")
async def semantic_search(q: str):
    model = get_model()
    if model is None:
        raise HTTPException(status_code=503, detail="Embedding model not ready")

    t0 = time.time()
    query_embedding = embed_text(q)
    query_vector = make_vector_str(query_embedding)
    embedding_latency.labels(service="embedding-service").observe(time.time() - t0)

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT p.id, p.title, p.summary, p.topic, p.risk_level,
                   1 - (ae.embedding <=> $1::vector) AS similarity
            FROM article_embeddings ae
            JOIN processed_articles p ON p.id = ae.article_id
            ORDER BY ae.embedding <=> $1::vector
            LIMIT 5
            """,
            query_vector,
        )

    return {"query": q, "results": [dict(row) for row in rows]}


@app.get("/generate")
async def generate_embeddings():
    model = get_model()
    if model is None:
        raise HTTPException(status_code=503, detail="Embedding model not ready")

    created = 0
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, title, summary
            FROM processed_articles p
            WHERE NOT EXISTS (
                SELECT 1 FROM article_embeddings ae WHERE ae.article_id = p.id
            )
            """
        )
        logger.info("generating_embeddings", count=len(rows))

        for row in rows:
            text = f"{row['title']} {row['summary'] or ''}"
            t0 = time.time()
            embedding = embed_text(text)
            embedding_latency.labels(service="embedding-service").observe(time.time() - t0)
            embedding_str = make_vector_str(embedding)
            await conn.execute(
                "INSERT INTO article_embeddings (article_id, embedding) VALUES ($1, $2::vector) ON CONFLICT (article_id) DO NOTHING",
                row["id"],
                embedding_str,
            )
            created += 1

    return {"status": "success", "embeddings_created": created}
