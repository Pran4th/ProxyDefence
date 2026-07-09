import asyncio
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from backend.shared.config import SERVICE_VERSION
from backend.shared.logging_config import setup_structlog, get_logger
from backend.shared.observability import HealthBuilder, StartupTimer, collect_system_metrics
from backend.shared.request_middleware import RequestTrackingMiddleware

from producer import check_kafka_connection, flush_producer
from services.news_fetcher import fetch_real_news
from services.newsdata_fetcher import fetch_newsdata_news

setup_structlog("ingest-service")
logger = get_logger(__name__)

scheduler = BackgroundScheduler()

health = HealthBuilder("ingest-service")
health.add_check("kafka", check_kafka_connection)


@asynccontextmanager
async def lifespan(app: FastAPI):
    timer = StartupTimer("ingest-service")
    timer.phase("kafka")
    logger.info("ingest_service_starting")
    try:
        fetch_real_news()
    except Exception as e:
        logger.error("initial_fetch_failed", error=str(e))
    try:
        fetch_newsdata_news()
    except Exception as e:
        logger.error("initial_newsdata_fetch_failed", error=str(e))
    scheduler.add_job(fetch_real_news, "interval", hours=1, id="fetch_news_job")
    scheduler.add_job(fetch_newsdata_news, "interval", hours=1, id="fetch_newsdata_job")
    scheduler.start()

    timer.phase("ready")
    logger.info("ingest_service_started", schedule_hours=1, startup=timer.finish())
    sys_metrics = asyncio.create_task(collect_system_metrics("ingest-service"))
    yield
    sys_metrics.cancel()
    scheduler.shutdown()
    flush_producer()
    logger.info("ingest_service_stopped")


app = FastAPI(title="Ingest Service", version=SERVICE_VERSION, lifespan=lifespan)
app.add_middleware(RequestTrackingMiddleware)
Instrumentator().instrument(app).expose(app)


@app.get("/")
async def read_root():
    return {
        "message": "Ingest Service is Online",
        "scheduler_status": "Running" if scheduler.running else "Stopped",
        "jobs": [str(job) for job in scheduler.get_jobs()],
    }


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
    return {"service": "ingest-service", "version": SERVICE_VERSION}


@app.get("/status")
async def status():
    h = await health.build()
    h["scheduler"] = {
        "running": scheduler.running,
        "jobs": len(scheduler.get_jobs()),
    }
    return h


@app.get("/fetch-real-news")
async def trigger_fetch_news():
    return fetch_real_news()


@app.get("/fetch-newsdata-news")
async def trigger_fetch_newsdata_news():
    return fetch_newsdata_news()
