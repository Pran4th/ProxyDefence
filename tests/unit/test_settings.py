"""Unit tests for backend.shared.settings."""

import os

import pytest


class TestSettingsDefaults:
    """Verify that Settings class provides correct defaults."""

    def test_loads_env_defaults_when_not_set(self, monkeypatch):
        monkeypatch.delenv("POSTGRES_HOST", raising=False)
        monkeypatch.delenv("POSTGRES_PORT", raising=False)
        monkeypatch.delenv("POSTGRES_DB", raising=False)
        monkeypatch.delenv("KAFKA_BOOTSTRAP_SERVERS", raising=False)
        monkeypatch.setenv("POSTGRES_USER", "test_user")
        monkeypatch.setenv("POSTGRES_PASSWORD", "test_pass")
        monkeypatch.setenv("ELASTICSEARCH_PASSWORD", "test_es_pass")
        monkeypatch.setenv("JWT_SECRET_KEY", "test_jwt_key")

        import importlib
        from backend.shared import settings as settings_module
        importlib.reload(settings_module)
        s = settings_module.settings

        assert s.POSTGRES_HOST == "postgres"
        assert s.POSTGRES_PORT == 5432
        assert s.POSTGRES_DB == "defenseintel"
        assert s.POSTGRES_USER == "test_user"
        assert s.POSTGRES_PASSWORD == "test_pass"
        assert s.KAFKA_BOOTSTRAP_SERVERS == "kafka:9092"

    def test_cors_origins_default(self, monkeypatch):
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        monkeypatch.setenv("POSTGRES_USER", "test_user")
        monkeypatch.setenv("POSTGRES_PASSWORD", "test_pass")
        monkeypatch.setenv("ELASTICSEARCH_PASSWORD", "test_es_pass")
        monkeypatch.setenv("JWT_SECRET_KEY", "test_jwt_key")

        import importlib
        from backend.shared import settings as settings_module
        importlib.reload(settings_module)
        s = settings_module.settings

        assert "http://localhost:3000" in s.CORS_ORIGINS
        assert "http://127.0.0.1:3000" in s.CORS_ORIGINS

    def test_log_level_default(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_USER", "test_user")
        monkeypatch.setenv("POSTGRES_PASSWORD", "test_pass")
        monkeypatch.setenv("ELASTICSEARCH_PASSWORD", "test_es_pass")
        monkeypatch.setenv("JWT_SECRET_KEY", "test_jwt_key")

        import importlib
        from backend.shared import settings as settings_module
        importlib.reload(settings_module)
        s = settings_module.settings

        assert s.LOG_LEVEL == "INFO"

    def test_service_name_default(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_USER", "test_user")
        monkeypatch.setenv("POSTGRES_PASSWORD", "test_pass")
        monkeypatch.setenv("ELASTICSEARCH_PASSWORD", "test_es_pass")
        monkeypatch.setenv("JWT_SECRET_KEY", "test_jwt_key")

        import importlib
        from backend.shared import settings as settings_module
        importlib.reload(settings_module)
        s = settings_module.settings

        assert s.SERVICE_NAME == "unknown"

    def test_jwt_algorithm_default(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_USER", "test_user")
        monkeypatch.setenv("POSTGRES_PASSWORD", "test_pass")
        monkeypatch.setenv("ELASTICSEARCH_PASSWORD", "test_es_pass")
        monkeypatch.setenv("JWT_SECRET_KEY", "test_jwt_key")

        import importlib
        from backend.shared import settings as settings_module
        importlib.reload(settings_module)
        s = settings_module.settings

        assert s.JWT_ALGORITHM == "HS256"

    def test_access_token_expire_minutes_default(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_USER", "test_user")
        monkeypatch.setenv("POSTGRES_PASSWORD", "test_pass")
        monkeypatch.setenv("ELASTICSEARCH_PASSWORD", "test_es_pass")
        monkeypatch.setenv("JWT_SECRET_KEY", "test_jwt_key")

        import importlib
        from backend.shared import settings as settings_module
        importlib.reload(settings_module)
        s = settings_module.settings

        assert s.ACCESS_TOKEN_EXPIRE_MINUTES == 60

    def test_overrides_env_vars(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_USER", "test_user")
        monkeypatch.setenv("POSTGRES_PASSWORD", "test_pass")
        monkeypatch.setenv("ELASTICSEARCH_PASSWORD", "test_es_pass")
        monkeypatch.setenv("JWT_SECRET_KEY", "test_jwt_key")
        monkeypatch.setenv("POSTGRES_HOST", "test-pg-host")
        monkeypatch.setenv("POSTGRES_PORT", "15432")
        monkeypatch.setenv("POSTGRES_DB", "test_db")
        monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "test-kafka:19092")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("SERVICE_NAME", "test-service")

        import importlib
        from backend.shared import settings as settings_module
        importlib.reload(settings_module)
        s = settings_module.settings

        assert s.POSTGRES_HOST == "test-pg-host"
        assert s.POSTGRES_PORT == 15432
        assert s.POSTGRES_DB == "test_db"
        assert s.KAFKA_BOOTSTRAP_SERVERS == "test-kafka:19092"
        assert s.LOG_LEVEL == "DEBUG"
        assert s.SERVICE_NAME == "test-service"

    def test_raises_on_missing_required(self, monkeypatch):
        monkeypatch.delenv("POSTGRES_USER", raising=False)
        monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
        monkeypatch.delenv("ELASTICSEARCH_PASSWORD", raising=False)
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

        import importlib
        with pytest.raises(RuntimeError, match="POSTGRES_USER"):
            from backend.shared import settings as settings_module
            importlib.reload(settings_module)
            _ = settings_module.settings
