"""Database-service database / ES connection helpers (sync).

Uses psycopg2 (sync) and Elasticsearch (sync) unlike the rest of the
codebase which uses asyncpg.  Env vars are imported from ``config.py``
which re-exports from ``backend.shared.settings`` — the single source of
truth.
"""

import time

import psycopg2
from elasticsearch import Elasticsearch
from psycopg2 import pool

from backend.shared.elastic import es_url
from backend.shared.logging_config import get_logger

from config import (
    POSTGRES_HOST, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD,
    ELASTICSEARCH_HOST, ELASTICSEARCH_USER, ELASTICSEARCH_PASSWORD,
)

logger = get_logger(__name__)

_pg_pool = None


def create_pool(min_size: int = 5, max_size: int = 20) -> None:
    global _pg_pool
    try:
        _pg_pool = pool.SimpleConnectionPool(
            min_size,
            max_size,
            host=POSTGRES_HOST,
            database=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            connect_timeout=5,
        )
        logger.info("database_service_pool_created", min=min_size, max=max_size)
    except Exception as exc:
        logger.exception("database_service_pool_failed: %s", exc)
        raise


def get_pool():
    if _pg_pool is None:
        raise RuntimeError("Database pool not initialized")
    return _pg_pool


def close_pool() -> None:
    global _pg_pool
    if _pg_pool is not None:
        _pg_pool.closeall()
        _pg_pool = None
        logger.info("database_service_pool_closed")


def get_connection():
    global _pg_pool
    pool_obj = get_pool()
    conn = pool_obj.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
    except Exception:
        pool_obj.putconn(conn)
        pool_obj.closeall()
        _pg_pool = None
        create_pool()
        conn = get_pool().getconn()
    return conn


def return_connection(conn) -> None:
    if _pg_pool is not None:
        _pg_pool.putconn(conn)


def get_es_client(max_retries: int = 10, delay: int = 3):
    url = es_url(host=ELASTICSEARCH_HOST)
    for attempt in range(max_retries):
        try:
            client = Elasticsearch(
                url,
                request_timeout=10,
                basic_auth=(ELASTICSEARCH_USER, ELASTICSEARCH_PASSWORD),
            )
            if client.ping():
                return client
        except Exception as exc:
            logger.warning("es_connection_attempt_failed", attempt=attempt + 1, max=max_retries, error=str(exc))
        if attempt < max_retries - 1:
            time.sleep(delay)
    return None


def close_es(client) -> None:
    if client is not None:
        client.transport.close()


def get_pool_stats() -> dict:
    if _pg_pool is None:
        return {"initialized": False}
    return {
        "initialized": True,
        "available": _pg_pool._pool.__len__() if hasattr(_pg_pool, "_pool") else 0,
        "total": _pg_pool._maxconn if hasattr(_pg_pool, "_maxconn") else 0,
    }
