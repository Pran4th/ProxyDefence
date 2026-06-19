from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware


from backend.api_service.routes import (
    alerts,
    articles,
    analytics,
    auth,
    cases,
    copilot,
   entities,
   events,
    graph,
   reports,
    search,
    semantic_search,
 # timeline,
   watchlists,
)
from backend.api_service.routes import health
from backend.api_service.repositories.intelligence import IntelligenceRepository
from backend.api_service.security import get_current_user
from backend.shared.db_pool import close_pg_pool, get_pg_pool
from backend.shared.schema_bootstrap import ensure_application_schema
from backend.shared.elastic_client import close_es_client, get_es_client

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
app.include_router(auth.router)

protected_routers = (
    articles.router,
    analytics.router,
    search.router,
    graph.router,
    semantic_search.router,
    events.router,
    entities.router,
    reports.router,
    watchlists.router,
    alerts.router,
    cases.router,
    copilot.router,
)

for router in protected_routers:
    app.include_router(router, dependencies=[Depends(get_current_user)])

app.include_router(health.router)



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
            # Audit logging must never break production request handling.
            pass
    return response


@app.get("/")
async def root():
    return {"status": "ProxyDefence API running"}
