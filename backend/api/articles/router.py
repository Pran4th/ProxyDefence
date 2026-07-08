from fastapi import APIRouter, HTTPException, Query, Request
from typing import Optional

from backend.api.articles.repository import ArticleRepository
from backend.api.articles.service import ArticleService

router = APIRouter(prefix="/articles", tags=["Articles"])


@router.get("/")
async def get_articles(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sentiment: Optional[str] = Query(None),
    topic: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
):
    repo = ArticleRepository(request.app.state.pg_pool)
    service = ArticleService(repo)
    return await service.list_articles(limit, offset, sentiment, topic, risk_level)


@router.get("/{id}")
async def get_article(id: int, request: Request):
    repo = ArticleRepository(request.app.state.pg_pool)
    service = ArticleService(repo)
    article = await service.get_article(id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.get("/{id}/entities")
async def get_article_entities(id: int, request: Request):
    repo = ArticleRepository(request.app.state.pg_pool)
    service = ArticleService(repo)
    article = await service.get_article(id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return await service.get_article_entities(id)
