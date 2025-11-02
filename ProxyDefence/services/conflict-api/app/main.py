from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import asyncpg
from elasticsearch import AsyncElasticsearch
import json
from datetime import datetime, timedelta
import os

app = FastAPI(title="ProxyDefence Conflict API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database configuration
POSTGRES_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "postgres"),
    "database": os.getenv("POSTGRES_DB", "defenseintel"),
    "user": os.getenv("POSTGRES_USER", "admin"),
    "password": os.getenv("POSTGRES_PASSWORD", "admin123"),
}

ELASTICSEARCH_HOST = os.getenv("ELASTICSEARCH_HOST", "elasticsearch")

@app.on_event("startup")
async def startup():
    """Initialize database connections"""
    app.state.pg_pool = await asyncpg.create_pool(**POSTGRES_CONFIG)
    app.state.es_client = AsyncElasticsearch([f"http://{ELASTICSEARCH_HOST}:9200"])

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "conflict-api", "timestamp": datetime.utcnow().isoformat()}

@app.get("/articles")
async def get_articles(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sentiment: Optional[str] = Query(None)
):
    """Get processed articles with filtering"""
    try:
        async with app.state.pg_pool.acquire() as conn:
            if sentiment:
                articles = await conn.fetch(
                    "SELECT * FROM processed_articles WHERE sentiment = $1 ORDER BY published_at DESC LIMIT $2 OFFSET $3",
                    sentiment, limit, offset
                )
            else:
                articles = await conn.fetch(
                    "SELECT * FROM processed_articles ORDER BY published_at DESC LIMIT $1 OFFSET $2",
                    limit, offset
                )
        
        return [dict(article) for article in articles]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/articles/{article_id}")
async def get_article(article_id: int):
    """Get a specific article by ID"""
    try:
        async with app.state.pg_pool.acquire() as conn:
            article = await conn.fetchrow(
                "SELECT * FROM processed_articles WHERE id = $1",
                article_id
            )
        
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        
        return dict(article)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/analytics/summary")
async def get_analytics_summary():
    """Get dashboard summary statistics"""
    try:
        async with app.state.pg_pool.acquire() as conn:
            # Total articles
            total_articles = await conn.fetchval("SELECT COUNT(*) FROM processed_articles")
            
            # Articles in last 24 hours
            last_24h = await conn.fetchval(
                "SELECT COUNT(*) FROM processed_articles WHERE published_at >= NOW() - INTERVAL '24 hours'"
            )
            
            # Average confidence
            avg_confidence = await conn.fetchval("SELECT AVG(confidence) FROM processed_articles")
            
            # Sentiment distribution
            sentiment_dist = await conn.fetch(
                "SELECT sentiment, COUNT(*) as count FROM processed_articles GROUP BY sentiment"
            )
        
        return {
            "total_articles": total_articles,
            "articles_last_24h": last_24h,
            "avg_confidence": float(avg_confidence) if avg_confidence else 0.0,
            "sentiment_distribution": {row['sentiment']: row['count'] for row in sentiment_dist}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analytics error: {str(e)}")

@app.get("/search")
async def search_articles(q: str = Query(..., min_length=2)):
    """Search articles using Elasticsearch"""
    try:
        response = await app.state.es_client.search(
            index="processed_articles",
            body={
                "query": {
                    "multi_match": {
                        "query": q,
                        "fields": ["title", "content", "source"]
                    }
                }
            }
        )
        
        return {
            "query": q,
            "total_results": response['hits']['total']['value'],
            "results": [hit["_source"] for hit in response['hits']['hits']]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")