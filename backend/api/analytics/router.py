from fastapi import APIRouter, Request

from backend.api.analytics.repository import AnalyticsRepository
from backend.api.analytics.service import AnalyticsService
from backend.api.common.errors import error_response

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/dashboard")
async def get_dashboard_stats(request: Request):
    repo = AnalyticsRepository(request.app.state.pg_pool)
    service = AnalyticsService(repo)
    return await service.get_dashboard_stats()


@router.get("/dashboard-v2")
async def get_dashboard_stats_v2(request: Request):
    repo = AnalyticsRepository(request.app.state.pg_pool)
    service = AnalyticsService(repo)
    return await service.get_dashboard_stats()


@router.get("/threat-trends")
async def get_threat_trends(request: Request):
    repo = AnalyticsRepository(request.app.state.pg_pool)
    service = AnalyticsService(repo)
    return await service.get_threat_trends()


@router.get("/summary")
async def get_analytics_summary(request: Request):
    repo = AnalyticsRepository(request.app.state.pg_pool)
    service = AnalyticsService(repo)
    return await service.get_summary()


@router.get("/graph")
async def get_attack_graph(request: Request):
    try:
        repo = AnalyticsRepository(request.app.state.pg_pool)
        service = AnalyticsService(repo)
        return await service.get_attack_graph()
    except Exception:
        raise error_response(code="ANALYTICS_ERROR", message="Failed to fetch attack graph", status_code=500)


@router.get("/timeseries")
async def get_timeseries(request: Request):
    try:
        repo = AnalyticsRepository(request.app.state.pg_pool)
        service = AnalyticsService(repo)
        return await service.get_timeseries()
    except Exception:
        raise error_response(code="ANALYTICS_ERROR", message="Failed to fetch timeseries data", status_code=500)


@router.get("/entities")
async def get_top_entities(request: Request):
    try:
        repo = AnalyticsRepository(request.app.state.pg_pool)
        service = AnalyticsService(repo)
        return await service.get_top_entities()
    except Exception:
        raise error_response(code="ANALYTICS_ERROR", message="Failed to fetch entity analytics", status_code=500)


@router.get("/topics")
async def get_topic_breakdown(request: Request):
    try:
        repo = AnalyticsRepository(request.app.state.pg_pool)
        service = AnalyticsService(repo)
        return await service.get_topic_breakdown()
    except Exception:
        raise error_response(code="ANALYTICS_ERROR", message="Failed to fetch topic analytics", status_code=500)
