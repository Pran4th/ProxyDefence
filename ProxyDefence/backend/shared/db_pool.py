import asyncpg
from backend.shared.config import settings

_pg_pool = None

async def get_pg_pool():
    global _pg_pool
    if _pg_pool is None:
        _pg_pool = await asyncpg.create_pool(
            host=settings.POSTGRES_HOST,
            database=settings.POSTGRES_DB,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
        )
    return _pg_pool