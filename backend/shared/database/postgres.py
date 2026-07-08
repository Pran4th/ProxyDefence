"""Low-level PostgreSQL helpers — DSN builder, health check.

These are the only place in the entire codebase where PostgreSQL
connection strings are constructed and connectivity is verified.
"""

from backend.shared.settings import settings


def build_dsn(
    *,
    host: str | None = None,
    port: int | None = None,
    db: str | None = None,
    user: str | None = None,
    password: str | None = None,
) -> str:
    """Construct a PostgreSQL DSN from explicit args or shared settings defaults."""
    host = host if host is not None else settings.POSTGRES_HOST
    port = port if port is not None else settings.POSTGRES_PORT
    db = db if db is not None else settings.POSTGRES_DB
    user = user if user is not None else settings.POSTGRES_USER
    password = password if password is not None else settings.POSTGRES_PASSWORD
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


async def check_health(pool) -> bool:
    """Execute a trivial query to verify the database connection.

    Works with both asyncpg pools and psycopg2 connections.
    """
    if hasattr(pool, "acquire"):
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
    else:
        with pool.cursor() as cur:
            cur.execute("SELECT 1")
    return True
