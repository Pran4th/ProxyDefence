"""Unit tests for backend.shared.database.pool."""

from unittest.mock import patch

import pytest


class TestPool:
    @pytest.mark.asyncio
    async def test_get_creates_pool_lazily(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_USER", "test_user")
        monkeypatch.setenv("POSTGRES_PASSWORD", "test_pass")
        monkeypatch.setenv("ELASTICSEARCH_PASSWORD", "test_es_pass")
        monkeypatch.setenv("JWT_SECRET_KEY", "test_jwt")

        import importlib
        from backend.shared import settings
        importlib.reload(settings)

        from backend.shared.database.pool import Pool
        pool = Pool(min_size=1, max_size=5, pool_name="test-pool")
        assert pool.initialized is False

    @pytest.mark.asyncio
    async def test_close_resets_pool(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_USER", "test_user")
        monkeypatch.setenv("POSTGRES_PASSWORD", "test_pass")
        monkeypatch.setenv("ELASTICSEARCH_PASSWORD", "test_es_pass")
        monkeypatch.setenv("JWT_SECRET_KEY", "test_jwt")

        import importlib
        from backend.shared import settings
        importlib.reload(settings)

        from backend.shared.database.pool import Pool
        pool = Pool(min_size=1, max_size=5, pool_name="test-pool")

        await pool.close()
        assert pool.initialized is False

    @pytest.mark.asyncio
    async def test_close_on_uninitialized_pool(self):
        from backend.shared.database.pool import Pool
        pool = Pool(min_size=1, max_size=5, pool_name="test-pool")
        await pool.close()
        assert pool.initialized is False

    def test_default_params(self):
        from backend.shared.database.pool import Pool
        pool = Pool()
        assert pool._pool is None
        pool2 = Pool(min_size=1, max_size=3, search_path="public", pool_name="custom")
        assert pool2._search_path == "public"
        assert pool2._pool_name == "custom"
