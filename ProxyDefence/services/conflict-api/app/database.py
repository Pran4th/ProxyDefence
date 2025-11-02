import asyncpg
from elasticsearch import AsyncElasticsearch
import os

# Database connection settings
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'postgres')
POSTGRES_DB = os.getenv('POSTGRES_DB', 'defenseintel')
POSTGRES_USER = os.getenv('POSTGRES_USER', 'admin')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'admin123')

# Elasticsearch connection
ELASTICSEARCH_HOST = os.getenv('ELASTICSEARCH_HOST', 'elasticsearch')

async def get_postgres_connection():
    """Create a connection to PostgreSQL."""
    return await asyncpg.connect(
        host=POSTGRES_HOST,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )

def get_elasticsearch_client():
    """Create a connection to Elasticsearch."""
    return AsyncElasticsearch([f"http://{ELASTICSEARCH_HOST}:9200"])