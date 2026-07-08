"""Unit tests for backend.shared.database.migrations."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestBootstrapSchema:
    @pytest.mark.asyncio
    async def test_skips_when_sentinel_table_exists(self):
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=True)
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock()
        mock_pool.acquire.return_value = cm

        mock_logger = MagicMock()

        from backend.shared.database.migrations import bootstrap_schema
        await bootstrap_schema(
            mock_pool,
            schema_name="test_schema",
            sentinel_table="test_table",
            sql_path=__file__,
            logger=mock_logger,
        )

        mock_conn.fetchval.assert_called_once()
        assert mock_conn.execute.call_count == 0

    @pytest.mark.asyncio
    async def test_applies_schema_when_sentinel_missing(self, tmp_path):
        sql_file = tmp_path / "test_schema.sql"
        sql_file.write_text("CREATE SCHEMA test_schema;")

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=False)
        mock_conn.execute = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock()
        mock_pool.acquire.return_value = cm

        mock_logger = MagicMock()

        from backend.shared.database.migrations import bootstrap_schema
        await bootstrap_schema(
            mock_pool,
            schema_name="test_schema",
            sentinel_table="test_table",
            sql_path=str(sql_file),
            logger=mock_logger,
        )

        mock_conn.execute.assert_called_once_with("CREATE SCHEMA test_schema;")


class TestEnsureExtension:
    @pytest.mark.asyncio
    async def test_creates_extension(self):
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock()
        mock_pool.acquire.return_value = cm

        from backend.shared.database.migrations import ensure_extension
        await ensure_extension(mock_pool, "vector")

        mock_conn.execute.assert_called_once_with("CREATE EXTENSION IF NOT EXISTS vector")
