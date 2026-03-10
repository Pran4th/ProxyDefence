from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api_service.routes import articles, analytics, search, graph
from backend.api_service.routes import health
app = FastAPI(title="ProxyDefence API Service")

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