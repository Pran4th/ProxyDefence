"""Modular-api Elasticsearch client (singleton, async).

Thin wrapper that reuses the client factory from :mod:`backend.shared.elastic`
so there is exactly one place where ES URLs are constructed.
"""

from elasticsearch import AsyncElasticsearch

from backend.shared.elastic import create_async_client

_es_client = None


async def get_es_client() -> AsyncElasticsearch:
    global _es_client
    if _es_client is None:
        _es_client = create_async_client()
    return _es_client


async def close_es_client() -> None:
    global _es_client
    if _es_client is not None:
        await _es_client.close()
        _es_client = None
