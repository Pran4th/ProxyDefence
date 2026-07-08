"""Unified Elasticsearch client factories.

Provides async and (optionally) sync client builders so that every
service constructs the ES URL in exactly one place.
"""

from elasticsearch import AsyncElasticsearch, Elasticsearch

from backend.shared.settings import settings


def es_url(*, host: str | None = None, port: int | None = None) -> str:
    host = host if host is not None else settings.ELASTICSEARCH_HOST
    port = port if port is not None else settings.ELASTICSEARCH_PORT
    return f"http://{host}:{port}"


def create_async_client(
    *,
    host: str | None = None,
    port: int | None = None,
    **kwargs,
) -> AsyncElasticsearch:
    url = es_url(host=host, port=port)
    return AsyncElasticsearch(
        [url],
        basic_auth=(settings.ELASTICSEARCH_USER, settings.ELASTICSEARCH_PASSWORD),
        **kwargs,
    )


def create_sync_client(
    *,
    host: str | None = None,
    port: int | None = None,
    request_timeout: int = 10,
    **kwargs,
) -> Elasticsearch:
    url = es_url(host=host, port=port)
    return Elasticsearch(
        url,
        request_timeout=request_timeout,
        basic_auth=(settings.ELASTICSEARCH_USER, settings.ELASTICSEARCH_PASSWORD),
        **kwargs,
    )


async def check_es_health(client: AsyncElasticsearch) -> bool:
    """Ping Elasticsearch via async client."""
    return await client.ping()
