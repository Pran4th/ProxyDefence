from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware


from backend.api_service.routes import (
#    alerts,
    articles,
    analytics,
    auth,
    copilot,
   entities,
   events,
    graph,
#    reports,
    search,
    semantic_search,
 #   timeline,
 #   watchlists,
)
from backend.api_service.routes import health
from backend.api_service.repositories.intelligence import IntelligenceRepository
from backend.shared.db_pool import close_pg_pool, get_pg_pool
from backend.shared.schema_bootstrap import ensure_application_schema
from backend.shared.elastic_client import close_es_client, get_es_client
from backend.shared.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pg_pool = await get_pg_pool()
    await ensure_application_schema(app.state.pg_pool)
    app.state.es_client = await get_es_client()
    try:
        yield
    finally:
        await close_es_client()
        await close_pg_pool()


app = FastAPI(title="ProxyDefence API Service", lifespan=lifespan)
origins = [
    "http://localhost:8081",
    "http://localhost:5173",
    "http://localhost:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Register routers
app.include_router(auth.router)
app.include_router(articles.router)
app.include_router(analytics.router)
app.include_router(search.router)
app.include_router(graph.router)
app.include_router(
    semantic_search.router
)
app.include_router(events.router)
#app.include_router(events.router)
app.include_router(entities.router)
#app.include_router(reports.router)
##app.include_router(watchlists.router)
#app.include_router(alerts.router)
#app.include_router(timeline.router)
app.include_router(copilot.router)
app.include_router(health.router)



@app.middleware("http")
async def audit_mutating_requests(request: Request, call_next):
    response = await call_next(request)
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and hasattr(request.app.state, "pg_pool"):
        try:
            repository = IntelligenceRepository(request.app.state.pg_pool)
            await repository.audit(
                None,
                f"{request.method} {request.url.path}",
                request.url.path,
                {"status_code": response.status_code},
            )
        except Exception:
            # Audit logging must never break production request handling.
            pass
    return response


@app.get("/")
async def root():
    return {"status": "ProxyDefence API running"}
