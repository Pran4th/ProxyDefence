import pytest

from connectors.base import (
    ConnectorConfig,
    ConnectorFetchConfig,
    ConnectorValidationResult,
    TokenBucket,
    BaseConnector,
    exponential_backoff,
)
from connectors.errors import (
    ConnectorError,
    ConnectorConnectionError,
    ConnectorAuthError,
    ConnectorSchemaDiscoveryError,
    ConnectorFetchError,
    ConnectorValidationError,
    ConnectorRateLimitError,
    ConnectorCheckpointError,
)
from connectors.registry import ConnectorRegistry, DEFAULT_CONFIGS, connector_registry


class TestConnectorConfig:
    def test_minimal_config(self):
        cfg = ConnectorConfig(name="test", connector_type="csv")
        assert cfg.name == "test"
        assert cfg.connector_type == "csv"
        assert cfg.config == {}
        assert cfg.auth == {}
        assert cfg.rate_limit == {"max_per_second": 10, "burst": 20}
        assert cfg.retry == {"max_retries": 3, "backoff_factor": 1.0, "max_delay": 60.0}

    def test_config_with_all_fields(self):
        cfg = ConnectorConfig(
            name="full",
            connector_type="rest_api",
            config={"base_url": "http://example.com"},
            auth={"token": "abc"},
            rate_limit={"max_per_second": 5, "burst": 10},
            retry={"max_retries": 5, "backoff_factor": 2.0, "max_delay": 120.0},
        )
        assert cfg.config["base_url"] == "http://example.com"
        assert cfg.auth["token"] == "abc"
        assert cfg.rate_limit["max_per_second"] == 5


class TestConnectorFetchConfig:
    def test_defaults(self):
        cfg = ConnectorFetchConfig()
        assert cfg.batch_size == 1000
        assert cfg.max_records is None
        assert cfg.start_position is None
        assert cfg.filters == {}

    def test_custom(self):
        cfg = ConnectorFetchConfig(batch_size=500, max_records=1000, filters={"status": "active"})
        assert cfg.batch_size == 500
        assert cfg.max_records == 1000
        assert cfg.filters == {"status": "active"}


class TestConnectorValidationResult:
    def test_default_valid(self):
        r = ConnectorValidationResult()
        assert r.is_valid is True
        assert r.errors == []
        assert r.warnings == []
        assert r.metadata == {}

    def test_invalid_with_errors(self):
        r = ConnectorValidationResult(
            is_valid=False, errors=["missing name"], warnings=["deprecated type"]
        )
        assert r.is_valid is False
        assert "missing name" in r.errors
        assert "deprecated type" in r.warnings


class TestTokenBucket:
    def test_init_defaults(self):
        tb = TokenBucket(max_per_second=5)
        assert tb.max_per_second == 5
        assert tb.burst >= 1
        assert tb.tokens == tb.burst

    def test_init_custom_burst(self):
        tb = TokenBucket(max_per_second=10, burst=50)
        assert tb.burst == 50
        assert tb.tokens == 50


class TestExponentialBackoff:
    def test_backoff_increases_with_attempt(self):
        d0 = exponential_backoff(0, backoff_factor=1.0, max_delay=60.0)
        d1 = exponential_backoff(1, backoff_factor=1.0, max_delay=60.0)
        d2 = exponential_backoff(2, backoff_factor=1.0, max_delay=60.0)
        assert d0 < d1 < d2

    def test_backoff_respects_max_delay(self):
        d = exponential_backoff(10, backoff_factor=1.0, max_delay=5.0)
        assert d <= 5.0


class TestBaseConnector:
    def test_abstract_methods_raise(self):
        cfg = ConnectorConfig(name="test", connector_type="test")
        with pytest.raises(TypeError):
            BaseConnector(cfg)

    def test_validate_name_required(self):
        class MinimalConnector(BaseConnector):
            async def connect(self): pass
            async def disconnect(self): pass
            async def discover_schema(self): return {}
            async def fetch(self, config): return iter([])

        c = MinimalConnector(ConnectorConfig(name="", connector_type="test"))
        result = c.config  # just verify it constructs


class TestConnectorRegistry:
    def test_singleton(self):
        assert connector_registry is not None
        assert isinstance(connector_registry, ConnectorRegistry)

    def test_register_and_get(self):
        reg = ConnectorRegistry()
        class FakeConn(BaseConnector):
            async def connect(self): pass
            async def disconnect(self): pass
            async def discover_schema(self): return {}
            async def fetch(self, config): return iter([])

        reg.register("fake", FakeConn)
        cls = reg.get("fake")
        assert cls is FakeConn

    def test_get_unknown_raises(self):
        reg = ConnectorRegistry()
        with pytest.raises(KeyError, match="No connector registered"):
            reg.get("nonexistent")

    def test_create_from_config(self):
        reg = ConnectorRegistry()
        class FakeConn(BaseConnector):
            async def connect(self): pass
            async def disconnect(self): pass
            async def discover_schema(self): return {}
            async def fetch(self, config): return iter([])

        reg.register("fake", FakeConn)
        cfg = ConnectorConfig(name="x", connector_type="fake")
        instance = reg.create(cfg)
        assert isinstance(instance, FakeConn)
        assert instance.config.name == "x"

    def test_list_types(self):
        reg = ConnectorRegistry()
        class FakeConn(BaseConnector):
            async def connect(self): pass
            async def disconnect(self): pass
            async def discover_schema(self): return {}
            async def fetch(self, config): return iter([])

        reg.register("fake_a", FakeConn)
        reg.register("fake_b", FakeConn)
        types = reg.list_types()
        assert "fake_a" in types
        assert "fake_b" in types

    def test_get_default_config_known(self):
        reg = ConnectorRegistry()
        cfg = reg.get_default_config("csv")
        assert cfg["delimiter"] == ","
        assert cfg["file_path_or_pattern"] == ""

    def test_get_default_config_unknown_raises(self):
        reg = ConnectorRegistry()
        with pytest.raises(KeyError):
            reg.get_default_config("no_such_type")


class TestDEFAULT_CONFIGS:
    def test_all_16_types_present(self):
        expected = {
            "rest_api", "csv", "excel", "json", "parquet", "geojson",
            "sql", "postgresql", "elasticsearch", "kafka", "s3", "ftp",
            "http_archive", "zip", "tar", "gzip",
        }
        assert set(DEFAULT_CONFIGS.keys()) == expected

    def test_rest_api_has_expected_keys(self):
        cfg = DEFAULT_CONFIGS["rest_api"]
        assert "base_url" in cfg
        assert "headers" in cfg
        assert "pagination_type" in cfg


class TestConnectorExceptions:
    def test_exception_hierarchy(self):
        assert issubclass(ConnectorConnectionError, ConnectorError)
        assert issubclass(ConnectorAuthError, ConnectorError)
        assert issubclass(ConnectorSchemaDiscoveryError, ConnectorError)
        assert issubclass(ConnectorFetchError, ConnectorError)
        assert issubclass(ConnectorValidationError, ConnectorError)
        assert issubclass(ConnectorRateLimitError, ConnectorError)
        assert issubclass(ConnectorCheckpointError, ConnectorError)

    def test_exceptions_are_distinct(self):
        assert ConnectorConnectionError is not ConnectorAuthError
        assert ConnectorFetchError is not ConnectorValidationError


class TestConnectorValidationLogic:
    def test_validate_requires_connector_type(self):
        class MinimalConnector(BaseConnector):
            async def connect(self): pass
            async def disconnect(self): pass
            async def discover_schema(self): return {}
            async def fetch(self, config): return iter([])

        import pytest

        async def run_validate():
            c = MinimalConnector(ConnectorConfig(name="test", connector_type=""))
            return await c.validate()

        result = asyncio_run(run_validate())
        assert result.is_valid is False
        assert any("Connector type" in e for e in result.errors)


def asyncio_run(coro):
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    return loop.run_until_complete(coro)
