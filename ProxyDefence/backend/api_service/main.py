from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api_service.routes import articles, analytics, graph, search
from backend.api_service.routes import health
from backend.shared.db_pool import close_pg_pool, get_pg_pool
from backend.shared.elastic_client import close_es_client, get_es_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pg_pool = await get_pg_pool()
    app.state.es_client = await get_es_client()
    try:
        yield
    finally:
        await close_es_client()
        await close_pg_pool()


app = FastAPI(title="ProxyDefence API Service", lifespan=lifespan)

# Register routers
app.include_router(articles.router)
app.include_router(analytics.router)
app.include_router(search.router)
app.include_router(graph.router)
app.include_router(health.router)

# CORS (so frontend can call backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"status": "ProxyDefence API running"}
