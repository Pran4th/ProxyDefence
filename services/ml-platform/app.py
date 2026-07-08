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

from db import get_pool, close_pool, ensure_schema
from routers import (
    features, datasets, models, inference, monitoring, deployment,
    features_serve, governance,
    dataset_catalog, dataset_validation, dataset_profiling, dataset_lineage,
    feature_transforms, feature_groups, feature_importance,
    research_experiments, research_configs,
    research_execution, research_leaderboard, research_reports,
    connectors, ingestion, normalization, data_quality,
    feature_pipelines, explorer_dashboard, data_acquisition,
    gdelt_pipeline, dataset_factory,
)

setup_structlog("ml-platform")
logger = get_logger(__name__)

health = HealthBuilder("ml-platform")


async def check_postgres():
    t0 = time.time()
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.fetchval("SELECT 1")
    latency = (time.time() - t0) * 1000
    db_query_latency.labels(service="ml-platform", operation="health").observe(latency / 1000)
    if hasattr(pool, "_holders"):
        total = pool._maxsize
        in_use = len(pool._holders)
        pool_usage.labels(service="ml-platform").set(in_use)
        idle = total - in_use
        pool_idle.labels(service="ml-platform").set(idle if idle > 0 else 0)
    return {"status": "connected", "latency_ms": round(latency, 1)}


health.add_check("postgres", check_postgres)


@asynccontextmanager
async def lifespan(app: FastAPI):
    timer = StartupTimer("ml-platform")
    timer.phase("database")
    logger.info("Starting ml-platform")
    pool = await get_pool()
    timer.phase("schema")
    await ensure_schema(pool)
    timer.phase("ready")
    logger.info("ml-platform ready", startup=timer.finish())
    sys_metrics = asyncio.create_task(collect_system_metrics("ml-platform"))
    yield
    sys_metrics.cancel()
    await close_pool()
    logger.info("ml-platform stopped")


app = FastAPI(title="ML Platform", version=SERVICE_VERSION, lifespan=lifespan)
app.add_middleware(RequestTrackingMiddleware)
Instrumentator().instrument(app).expose(app)

app.include_router(features.router)
app.include_router(datasets.router)
app.include_router(models.router)
app.include_router(inference.router)
app.include_router(monitoring.router)
app.include_router(deployment.router)
app.include_router(features_serve.router)
app.include_router(governance.router)
app.include_router(dataset_catalog.router)
app.include_router(dataset_validation.router)
app.include_router(dataset_profiling.router)
app.include_router(dataset_lineage.router)
app.include_router(feature_transforms.router)
app.include_router(feature_groups.router)
app.include_router(feature_importance.router)
app.include_router(research_experiments.router)
app.include_router(research_configs.router)
app.include_router(research_execution.router)
app.include_router(research_leaderboard.router)
app.include_router(research_reports.router)
app.include_router(connectors.router)
app.include_router(ingestion.router)
app.include_router(normalization.router)
app.include_router(data_quality.router)
app.include_router(feature_pipelines.router)
app.include_router(explorer_dashboard.router)
app.include_router(data_acquisition.router)
app.include_router(gdelt_pipeline.router)
app.include_router(dataset_factory.router)


@app.get("/")
async def root():
    return {"service": "ml-platform", "version": SERVICE_VERSION}


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
    return {"service": "ml-platform", "version": SERVICE_VERSION}


@app.get("/status")
async def status():
    return await health.build()
