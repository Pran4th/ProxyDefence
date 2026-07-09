from contextlib import asynccontextmanager

import structlog
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from backend.api.agents.router import router as agents_router
from backend.api.analytics.router import router as analytics_router
from backend.api.articles.router import router as articles_router
from backend.api.auth.router import router as auth_router
from backend.api.copilot.router import router as copilot_router
from backend.api.graph.router import router as graph_router
from backend.api.health.router import router as health_router
from backend.api.investigations.router import router as investigations_router
from backend.api.public.router import router as public_router
from backend.api.search.router import router as search_router
from backend.api.search.router import semantic_router
from backend.api.energy.router import router as energy_router
from backend.api.energy.router import intel_router
from backend.api.rag.router import router as rag_router
from backend.api_service.rate_limit import limiter
from backend.api_service.repositories.intelligence import IntelligenceRepository
from backend.api_service.security import get_current_user
from backend.shared.config import SERVICE_VERSION
from backend.shared.db_pool import close_pg_pool, get_pg_pool
from backend.shared.elastic_client import close_es_client, get_es_client
from backend.shared.logging_config import setup_structlog, get_logger
from backend.shared.request_middleware import RequestTrackingMiddleware
from backend.shared.settings import settings
from prometheus_fastapi_instrumentator import Instrumentator

setup_structlog("modular-api")
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting modular-api service")
    app.state.pg_pool = await get_pg_pool()
    app.state.es_client = await get_es_client()
    try:
        yield
    finally:
        await close_es_client()
        await close_pg_pool()


app = FastAPI(title="ProxyDefence API Service", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(RequestTrackingMiddleware)
Instrumentator().instrument(app).expose(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(public_router)

protected_routers = (
    agents_router,
    articles_router,
    analytics_router,
    search_router,
    semantic_router,
    graph_router,
    investigations_router,
    copilot_router,
    energy_router,
    intel_router,
    rag_router,
)

for router in protected_routers:
    app.include_router(router, dependencies=[Depends(get_current_user)])

app.include_router(health_router)


@app.middleware("http")
async def audit_mutating_requests(request: Request, call_next):
    response = await call_next(request)
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and hasattr(request.app.state, "pg_pool"):
        try:
            repository = IntelligenceRepository(request.app.state.pg_pool)
            current_user = getattr(request.state, "current_user", None)
            user_id = current_user.get("id") if isinstance(current_user, dict) else None
            await repository.audit(
                user_id,
                f"{request.method} {request.url.path}",
                request.url.path,
                {"status_code": response.status_code},
            )
        except Exception:
            pass
    return response


@app.get("/")
async def root():
    return {"status": "ProxyDefence API running"}
