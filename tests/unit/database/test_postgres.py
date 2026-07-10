"""Unit tests for backend.shared.database.postgres."""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestBuildDSN:
    def test_default_from_settings(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_USER", "test_user")
        monkeypatch.setenv("POSTGRES_PASSWORD", "test_pass")
        monkeypatch.setenv("ELASTICSEARCH_PASSWORD", "test_es")
        monkeypatch.setenv("JWT_SECRET_KEY", "test_jwt")

        import importlib
        from backend.shared import settings
        importlib.reload(settings)
        from backend.shared.database import postgres
        importlib.reload(postgres)

        dsn = postgres.build_dsn()
        assert dsn.startswith("postgresql://")
        assert "test_user" in dsn
        assert "test_pass" in dsn

    def test_custom_args_override_settings(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_USER", "default_user")
        monkeypatch.setenv("POSTGRES_PASSWORD", "default_pass")
        monkeypatch.setenv("ELASTICSEARCH_PASSWORD", "test_es_pass")
        monkeypatch.setenv("JWT_SECRET_KEY", "test_jwt")

        import importlib
        from backend.shared import settings
        importlib.reload(settings)

        from backend.shared.database.postgres import build_dsn
        dsn = build_dsn(host="custom-host", port=15432, db="custom_db", user="custom_user", password="custom_pass")
        assert "custom-host" in dsn
        assert "15432" in dsn
        assert "custom_db" in dsn
        assert "custom_user" in dsn
        assert "custom_pass" in dsn

    def test_partial_overrides(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_USER", "base_user")
        monkeypatch.setenv("POSTGRES_PASSWORD", "base_pass")
        monkeypatch.setenv("POSTGRES_HOST", "base-host")
        monkeypatch.setenv("POSTGRES_PORT", "5432")
        monkeypatch.setenv("POSTGRES_DB", "base_db")
        monkeypatch.setenv("ELASTICSEARCH_PASSWORD", "test_es_pass")
        monkeypatch.setenv("JWT_SECRET_KEY", "test_jwt")

        import importlib
        from backend.shared import settings
        importlib.reload(settings)
        from backend.shared.database import postgres
        importlib.reload(postgres)

        dsn = postgres.build_dsn(host="override-host")
        assert "override-host" in dsn
        assert "base_user" in dsn
        assert "base_pass" in dsn
        assert "base_db" in dsn


class TestCheckHealth:
    @pytest.mark.asyncio
    async def test_asyncpg_pool(self):
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock()
        mock_pool.acquire.return_value = cm

        from backend.shared.database.postgres import check_health
        result = await check_health(mock_pool)
        assert result is True
        mock_conn.fetchval.assert_called_once_with("SELECT 1")

    def test_psycopg2_connection(self):
        # check_health() branches on hasattr(pool, "acquire") to tell an asyncpg
        # pool from a psycopg2 connection -- MagicMock auto-vivifies any
        # attribute access, so `acquire` must be explicitly removed to make
        # this mock look like a real psycopg2 connection (which has none).
        mock_conn = MagicMock(spec=["cursor"])
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        import asyncio
        from backend.shared.database.postgres import check_health
        result = asyncio.run(check_health(mock_conn))
        assert result is True
        mock_cursor.execute.assert_called_once_with("SELECT 1")
