"""Unit tests for backend.shared.config."""


class TestServiceVersion:
    def test_default_version(self, monkeypatch):
        monkeypatch.delenv("SERVICE_VERSION", raising=False)
        from backend.shared.config import SERVICE_VERSION
        assert SERVICE_VERSION == "1.0.0"

    def test_overridden_version(self, monkeypatch):
        monkeypatch.setenv("SERVICE_VERSION", "2.1.0")
        import importlib
        from backend.shared import config
        importlib.reload(config)
        assert config.SERVICE_VERSION == "2.1.0"


class TestGitCommit:
    def test_default(self, monkeypatch):
        monkeypatch.delenv("GIT_COMMIT", raising=False)
        from backend.shared.config import GIT_COMMIT
        assert GIT_COMMIT == "unknown"

    def test_overridden(self, monkeypatch):
        monkeypatch.setenv("GIT_COMMIT", "abc123def456")
        import importlib
        from backend.shared import config
        importlib.reload(config)
        assert config.GIT_COMMIT == "abc123def456"


class TestRequiredEnv:
    def test_returns_value_when_set(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "test_value")
        from backend.shared.config import _required_env
        assert _required_env("TEST_VAR") == "test_value"

    def test_raises_when_missing(self, monkeypatch):
        monkeypatch.delenv("MISSING_VAR", raising=False)
        from backend.shared.config import _required_env
        with pytest.raises(RuntimeError, match="MISSING_VAR"):
            _required_env("MISSING_VAR")

    def test_raises_when_empty(self, monkeypatch):
        monkeypatch.setenv("EMPTY_VAR", "")
        from backend.shared.config import _required_env
        with pytest.raises(RuntimeError, match="EMPTY_VAR"):
            _required_env("EMPTY_VAR")
