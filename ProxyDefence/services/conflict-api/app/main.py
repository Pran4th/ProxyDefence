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
    # Wait for DB to be ready
    import asyncio
    max_retries = 10
    for i in range(max_retries):
        try:
            app.state.pg_pool = await asyncpg.create_pool(**POSTGRES_CONFIG)
            print("Connected to PostgreSQL")
            break
        except Exception as e:
            print(f"Waiting for PostgreSQL... {e}")
            await asyncio.sleep(2)
    
    app.state.es_client = AsyncElasticsearch([f"http://{ELASTICSEARCH_HOST}:9200"])



