from elasticsearch import AsyncElasticsearch
from backend.shared.config import settings

_es_client = None

async def get_es_client():
    global _es_client
    if _es_client is None:
        _es_client = AsyncElasticsearch(
            [f"http://{settings.ELASTICSEARCH_HOST}:9200"]
        )
    return _es_client