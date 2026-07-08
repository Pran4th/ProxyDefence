"""Unit tests for backend.shared.observability.health."""

import pytest


class TestHealthBuilder:
    def test_init_sets_service_name_and_version(self, monkeypatch):
        monkeypatch.setenv("SERVICE_VERSION", "2.0.0-test")
        monkeypatch.setenv("POSTGRES_USER", "x")
        monkeypatch.setenv("POSTGRES_PASSWORD", "x")
        monkeypatch.setenv("ELASTICSEARCH_PASSWORD", "x")
        monkeypatch.setenv("JWT_SECRET_KEY", "x")

        import importlib
        from backend.shared import config
        importlib.reload(config)

        from backend.shared.observability.health import HealthBuilder
        health = HealthBuilder("test-service")
        assert health._service_name == "test-service"
        assert health._version == "2.0.0-test"

    @pytest.mark.asyncio
    async def test_build_with_no_checks_returns_healthy(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_USER", "x")
        monkeypatch.setenv("POSTGRES_PASSWORD", "x")
        monkeypatch.setenv("ELASTICSEARCH_PASSWORD", "x")
        monkeypatch.setenv("JWT_SECRET_KEY", "x")

        import importlib
        from backend.shared import config
        importlib.reload(config)

        from backend.shared.observability.health import HealthBuilder
        health = HealthBuilder("test-service")
        result = await health.build()
        assert result["status"] == "healthy"
        assert result["service"] == "test-service"
        assert "uptime_seconds" in result
        assert "started_at" in result
        assert result["dependencies"] == {}

    @pytest.mark.asyncio
    async def test_sync_check(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_USER", "x")
        monkeypatch.setenv("POSTGRES_PASSWORD", "x")
        monkeypatch.setenv("ELASTICSEARCH_PASSWORD", "x")
        monkeypatch.setenv("JWT_SECRET_KEY", "x")

        import importlib
        from backend.shared import config
        importlib.reload(config)

        from backend.shared.observability.health import HealthBuilder
        health = HealthBuilder("test-service")

        def check_db():
            return {"status": "connected", "latency_ms": 1.5}

        health.add_check("postgres", check_db)
        result = await health.build()
        assert result["status"] == "healthy"
        assert result["dependencies"]["postgres"]["status"] == "connected"
        assert result["dependencies"]["postgres"]["latency_ms"] == 1.5

    @pytest.mark.asyncio
    async def test_async_check(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_USER", "x")
        monkeypatch.setenv("POSTGRES_PASSWORD", "x")
        monkeypatch.setenv("ELASTICSEARCH_PASSWORD", "x")
        monkeypatch.setenv("JWT_SECRET_KEY", "x")

        import importlib
        from backend.shared import config
        importlib.reload(config)

        from backend.shared.observability.health import HealthBuilder
        health = HealthBuilder("test-service")

        async def check_es():
            return {"status": "connected", "latency_ms": 3.2}

        health.add_check("elasticsearch", check_es)
        result = await health.build()
        assert result["status"] == "healthy"
        assert result["dependencies"]["elasticsearch"]["status"] == "connected"

    @pytest.mark.asyncio
    async def test_degraded_status(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_USER", "x")
        monkeypatch.setenv("POSTGRES_PASSWORD", "x")
        monkeypatch.setenv("ELASTICSEARCH_PASSWORD", "x")
        monkeypatch.setenv("JWT_SECRET_KEY", "x")

        import importlib
        from backend.shared import config
        importlib.reload(config)

        from backend.shared.observability.health import HealthBuilder
        health = HealthBuilder("test-service")
        health.add_check("cache", lambda: {"status": "degraded", "latency_ms": 500})
        result = await health.build()
        assert result["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_unhealthy_when_check_raises(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_USER", "x")
        monkeypatch.setenv("POSTGRES_PASSWORD", "x")
        monkeypatch.setenv("ELASTICSEARCH_PASSWORD", "x")
        monkeypatch.setenv("JWT_SECRET_KEY", "x")

        import importlib
        from backend.shared import config
        importlib.reload(config)

        from backend.shared.observability.health import HealthBuilder
        health = HealthBuilder("test-service")

        def broken_check():
            raise RuntimeError("DB is down")

        health.add_check("postgres", broken_check)
        result = await health.build()
        assert result["status"] == "unhealthy"
        assert result["dependencies"]["postgres"]["status"] == "error"

    @pytest.mark.asyncio
    async def test_multiple_checks_aggregated(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_USER", "x")
        monkeypatch.setenv("POSTGRES_PASSWORD", "x")
        monkeypatch.setenv("ELASTICSEARCH_PASSWORD", "x")
        monkeypatch.setenv("JWT_SECRET_KEY", "x")

        import importlib
        from backend.shared import config
        importlib.reload(config)

        from backend.shared.observability.health import HealthBuilder
        health = HealthBuilder("test-service")
        health.add_check("db", lambda: {"status": "connected"})
        health.add_check("es", lambda: {"status": "connected"})
        health.add_check("cache", lambda: {"status": "degraded"})
        result = await health.build()
        assert result["status"] == "degraded"
        assert "db" in result["dependencies"]
        assert "es" in result["dependencies"]
        assert "cache" in result["dependencies"]
