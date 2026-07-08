"""Integration tests for database migrations.

Requires --run-integration flag and running PostgreSQL.
"""

import pytest


@pytest.mark.integration
class TestMigrations:
    async def test_bootstrap_schema_skips_existing(self, pg_dsn):
        import asyncpg

        pool = await asyncpg.create_pool(dsn=pg_dsn)
        try:
            from backend.shared.database.migrations import bootstrap_schema

            import logging
            result = await bootstrap_schema(
                pool,
                schema_name="public",
                sentinel_table="processed_articles",
                sql_path=__file__,
                logger=logging.getLogger(__name__),
            )
            assert result is None
        finally:
            await pool.close()

    async def test_ensure_extension(self, pg_dsn):
        import asyncpg

        pool = await asyncpg.create_pool(dsn=pg_dsn)
        try:
            from backend.shared.database.migrations import ensure_extension
            await ensure_extension(pool, "pgcrypto")
        finally:
            await pool.close()
