import asyncio
import time
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from prometheus_fastapi_instrumentator import Instrumentator

from backend.shared.config import SERVICE_VERSION
from backend.shared.logging_config import setup_structlog, get_logger
from backend.shared.observability import (
    HealthBuilder,
    StartupTimer,
    collect_system_metrics,
    db_query_latency,
    pool_usage,
    pool_idle,
)
from backend.shared.request_middleware import RequestTrackingMiddleware

from config import JWT_SECRET_KEY, JWT_ALGORITHM
from db import create_pool, get_pool, close_pool, get_connection, return_connection, get_es_client, get_pool_stats
from services.database import fetch_articles, get_article_by_id, get_analytics_summary
from services.event_intelligence import update_event_intelligence, validate_rebuild_prerequisites
from services.elastic_indexer import search_articles

setup_structlog("database-service")
logger = get_logger(__name__)

bearer_scheme = HTTPBearer(auto_error=True)

health = HealthBuilder("database-service")


def get_admin_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict[str, Any]:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, email, username, role FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            if row is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
            user = {"id": row[0], "email": row[1], "username": row[2], "role": row[3]}
            if user["role"] != "admin":
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
            return user
    finally:
        return_connection(conn)


def check_postgres():
    t0 = time.time()
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        latency = (time.time() - t0) * 1000
        db_query_latency.labels(service="database-service", operation="health").observe(latency / 1000)
        stats = get_pool_stats()
        if stats.get("initialized"):
            pool_usage.labels(service="database-service").set(stats.get("total", 0) - stats.get("available", 0))
            pool_idle.labels(service="database-service").set(stats.get("available", 0))
        return {"status": "connected", "latency_ms": round(latency, 1), "pool": stats}
    except Exception as e:
        return {"status": "disconnected", "error": str(e)}
    finally:
        if conn is not None:
            return_connection(conn)


def check_elasticsearch():
    t0 = time.time()
    try:
        es = get_es_client(max_retries=1, delay=0)
        if es is None:
            return {"status": "disconnected", "error": "Elasticsearch unavailable"}
        es.info()
        latency = (time.time() - t0) * 1000
        return {"status": "connected", "latency_ms": round(latency, 1)}
    except Exception as e:
        return {"status": "disconnected", "error": str(e)}


health.add_check("postgres", check_postgres)
health.add_check("elasticsearch", check_elasticsearch)


@asynccontextmanager
async def lifespan(app: FastAPI):
    timer = StartupTimer("database-service")
    timer.phase("database")
    logger.info("database_service_starting")
    create_pool()
    timer.phase("ready")
    logger.info("database_service_ready", startup=timer.finish())
    sys_metrics = asyncio.create_task(collect_system_metrics("database-service"))
    yield
    sys_metrics.cancel()
    close_pool()
    logger.info("database_service_stopped")


app = FastAPI(title="Database Service", version=SERVICE_VERSION, lifespan=lifespan)
app.add_middleware(RequestTrackingMiddleware)
Instrumentator().instrument(app).expose(app)


@app.get("/")
async def read_root():
    return {"message": "Database Service is online"}


@app.get("/health")
async def health_endpoint():
    return await health.build()


@app.get("/liveness")
async def liveness():
    return {"status": "alive"}


@app.get("/readiness")
async def readiness():
    return await health.build()


@app.get("/version")
async def version():
    return {"service": "database-service", "version": SERVICE_VERSION}


@app.get("/status")
async def status():
    h = await health.build()
    h["settings"] = {"jwt_algorithm": JWT_ALGORITHM}
    return h


@app.get("/api/articles")
async def get_articles(limit: int = 20, offset: int = 0, sentiment: Optional[str] = None):
    try:
        return fetch_articles(limit=limit, offset=offset, sentiment=sentiment)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc


@app.post("/rebuild-events")
async def rebuild_events(current_user: dict[str, Any] = Depends(get_admin_user)):
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                validate_rebuild_prerequisites(cur)
                cur.execute("DELETE FROM event_entities")
                cur.execute("DELETE FROM event_articles")
                cur.execute("DELETE FROM events")
                cur.execute("SELECT id FROM processed_articles ORDER BY id")
                article_ids = [row[0] for row in cur.fetchall()]

            rebuilt = 0
            for article_id in article_ids:
                update_event_intelligence(article_id, conn=conn)
                rebuilt += 1

        return {"status": "success", "articles_processed": rebuilt}
    finally:
        return_connection(conn)


@app.get("/api/analytics/summary")
async def analytics_summary():
    return get_analytics_summary()


@app.get("/api/search")
async def search(q: str = Query(..., min_length=2)):
    return search_articles(q)


@app.get("/api/articles/{article_id}")
async def get_article(article_id: int):
    article = get_article_by_id(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return article
