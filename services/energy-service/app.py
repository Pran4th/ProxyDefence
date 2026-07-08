import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
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

from db import get_pool, close_pool, bootstrap
from routers import catalog, relationships, events, history, bulk, intelligence, digital_twin, procurement

setup_structlog("energy-service")
logger = get_logger(__name__)

health = HealthBuilder("energy-service")


async def check_postgres():
    t0 = time.time()
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.fetchval("SELECT 1")
    latency = (time.time() - t0) * 1000
    db_query_latency.labels(service="energy-service", operation="health").observe(latency / 1000)
    if hasattr(pool, "_holders"):
        total = pool._maxsize
        in_use = len(pool._holders)
        pool_usage.labels(service="energy-service").set(in_use)
        idle = total - in_use
        pool_idle.labels(service="energy-service").set(idle if idle > 0 else 0)
    return {"status": "connected", "latency_ms": round(latency, 1)}


async def check_intelligence_signals():
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            active = await conn.fetchval(
                "SELECT COUNT(*) FROM energy.disruption_signals WHERE expires_at > NOW()"
            )
            high_sev = await conn.fetchval(
                """SELECT COUNT(*) FROM energy.disruption_signals
                   WHERE expires_at > NOW() AND severity IN ('high','critical')"""
            )
        return {"status": "ok", "active_signals": active or 0, "critical_signals": high_sev or 0}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


async def check_ingestors():
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            prices = await conn.fetchval("SELECT COUNT(*) FROM energy.commodity_prices")
            sanctions = await conn.fetchval("SELECT COUNT(*) FROM energy.sanctions")
            ports = await conn.fetchval("SELECT COUNT(*) FROM energy.port_congestion")
            tankers = await conn.fetchval("SELECT COUNT(*) FROM energy.tanker_availability")
        return {
            "status": "ok",
            "commodity_prices": prices or 0,
            "sanctions": sanctions or 0,
            "port_congestion": ports or 0,
            "tanker_availability": tankers or 0,
        }
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


health.add_check("postgres", check_postgres)
health.add_check("intelligence_signals", check_intelligence_signals)
health.add_check("ingestors", check_ingestors)


@asynccontextmanager
async def lifespan(app: FastAPI):
    timer = StartupTimer("energy-service")
    timer.phase("database")
    logger.info("Starting energy-service")
    pool = await get_pool()
    timer.phase("bootstrap")
    await bootstrap(pool)
    timer.phase("ready")
    logger.info("energy-service ready", startup=timer.finish())
    sys_metrics = asyncio.create_task(collect_system_metrics("energy-service"))
    yield
    sys_metrics.cancel()
    await close_pool()
    logger.info("energy-service stopped")


app = FastAPI(title="Energy Service", version=SERVICE_VERSION, lifespan=lifespan)
app.add_middleware(RequestTrackingMiddleware)
Instrumentator().instrument(app).expose(app)

app.include_router(relationships.router)
app.include_router(catalog.router)
app.include_router(events.router)
app.include_router(history.router)
app.include_router(bulk.router)
app.include_router(intelligence.router)
app.include_router(digital_twin.router)
app.include_router(procurement.router)


@app.get("/")
async def root():
    return {"service": "energy-service", "version": SERVICE_VERSION}


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
    return {"service": "energy-service", "version": SERVICE_VERSION}


@app.get("/status")
async def status():
    return await health.build()
