import time
from datetime import datetime

from fastapi import APIRouter, Request

from backend.shared.config import SERVICE_VERSION
from backend.shared.kafka_monitor import get_consumer_lag, get_consumer_lag_summary
from backend.shared.observability import HealthBuilder, db_query_latency

router = APIRouter(tags=["Health"])

health = HealthBuilder("modular-api")


async def check_postgres(request: Request):
    t0 = time.time()
    async with request.app.state.pg_pool.acquire() as conn:
        await conn.fetchval("SELECT 1")
    latency = (time.time() - t0) * 1000
    db_query_latency.labels(service="modular-api", operation="health").observe(latency / 1000)
    return {"status": "connected", "latency_ms": round(latency, 1)}


async def check_elasticsearch(request: Request):
    t0 = time.time()
    client = request.app.state.es_client
    await client.ping()
    latency = (time.time() - t0) * 1000
    return {"status": "connected", "latency_ms": round(latency, 1)}


@router.get("/health")
async def health_endpoint(request: Request):
    check_pg = lambda: check_postgres(request)
    check_es = lambda: check_elasticsearch(request)
    health._checks = {}
    health.add_check("postgres", check_pg)
    health.add_check("elasticsearch", check_es)
    return await health.build()


@router.get("/liveness")
async def liveness():
    return {"status": "alive"}


@router.get("/readiness")
async def readiness(request: Request):
    try:
        async with request.app.state.pg_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        await request.app.state.es_client.ping()
        return {"status": "healthy", "service": "modular-api"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@router.get("/version")
async def version():
    return {"service": "modular-api", "version": SERVICE_VERSION}


@router.get("/status")
async def status(request: Request):
    check_pg = lambda: check_postgres(request)
    check_es = lambda: check_elasticsearch(request)
    health._checks = {}
    health.add_check("postgres", check_pg)
    health.add_check("elasticsearch", check_es)
    result = await health.build()
    try:
        result["kafka"] = await get_consumer_lag()
    except Exception:
        result["kafka"] = {"error": "unavailable"}
    result["timestamp"] = datetime.utcnow().isoformat()
    return result


@router.get("/health/kafka")
async def health_kafka():
    status = await get_consumer_lag()
    return {"status": "ok", "consumer_groups": status}


@router.get("/health/kafka/details")
async def health_kafka_details():
    details = await get_consumer_lag_summary()
    return {"status": "ok", "details": details}
