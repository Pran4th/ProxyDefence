"""Schema bootstrap and migration helpers.

Consolidates the schema bootstrapping logic from
:mod:`backend.shared.schema_bootstrap` and the various service-level
``ensure_*`` functions into one place.
"""

from pathlib import Path

import asyncpg


async def bootstrap_schema(
    pool: asyncpg.Pool,
    *,
    schema_name: str,
    sentinel_table: str,
    sql_path: str | Path,
    logger,
) -> None:
    """Bootstrap a database schema from a canonical SQL file.

    Checks for a sentinel table in the target schema.  If the table
    exists the schema is assumed initialized and the SQL file is skipped.
    If not, the SQL file is executed exactly once.

    Args:
        pool: An open asyncpg Pool.
        schema_name: PostgreSQL schema name (e.g. ``"energy"``, ``"ml"``).
        sentinel_table: Table name whose presence indicates the schema is
            initialized.
        sql_path: Path to the canonical SQL file.
        logger: A structlog logger.

    Raises:
        FileNotFoundError: If *sql_path* does not exist.
    """
    logger.info("Starting %s bootstrap…", schema_name)
    sql_path = Path(sql_path).resolve(strict=True)

    async with pool.acquire() as conn:
        exists = await conn.fetchval(
            """SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = $1 AND table_name = $2
            )""",
            schema_name,
            sentinel_table,
        )

        if exists:
            logger.info("Schema %r already initialized.", schema_name)
            return

        logger.info("Schema %r not found. Applying canonical schema…", schema_name)
        sql = sql_path.read_text()
        await conn.execute(sql)
        logger.info("Schema %r created successfully.", schema_name)

    logger.info("%s bootstrap complete.", schema_name)


async def apply_sql_file(pool: asyncpg.Pool, sql_path: str | Path, logger) -> None:
    """Execute a SQL file against the database pool.

    No sentinel check — the file is always applied.  Useful forCREATE EXTENSION``
    and other idempotent operations.
    """
    sql_path = Path(sql_path).resolve()
    async with pool.acquire() as conn:
        sql = sql_path.read_text()
        await conn.execute(sql)
    logger.info("SQL file applied", path=str(sql_path))


async def ensure_extension(
    pool: asyncpg.Pool,
    extension_name: str = "vector",
    logger=None,
) -> None:
    """Run ``CREATE EXTENSION IF NOT EXISTS`` for the given extension."""
    async with pool.acquire() as conn:
        await conn.execute(f"CREATE EXTENSION IF NOT EXISTS {extension_name}")
    if logger:
        logger.info("Extension verified", extension=extension_name)
