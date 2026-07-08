"""Integration test fixtures that require real PG/ES/Kafka connections.

These tests are skipped unless explicitly enabled via --run-integration.
"""

import os

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests (require PG/ES/Kafka)",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: Integration tests requiring external services")

    # Register the integration marker
    if not config.option.run_integration:
        skip_integration = pytest.mark.skip(reason="use --run-integration to include")
        config.stash["skip_integration"] = skip_integration


def pytest_runtest_setup(item):
    if "integration" in item.keywords:
        integration_marker = item.get_closest_marker("integration")
        if integration_marker is not None and not item.config.option.run_integration:
            pytest.skip("use --run-integration to include")


# ── Connection info ───────────────────────────────────────────────

PG_HOST = os.getenv("TEST_POSTGRES_HOST", "localhost")
PG_PORT = int(os.getenv("TEST_POSTGRES_PORT", "5432"))
PG_USER = os.getenv("TEST_POSTGRES_USER", "admin")
PG_PASSWORD = os.getenv("TEST_POSTGRES_PASSWORD", "admin123")
PG_DB = os.getenv("TEST_POSTGRES_DB", "defenseintel_test")

ES_HOST = os.getenv("TEST_ELASTICSEARCH_HOST", "localhost")
ES_PORT = int(os.getenv("TEST_ELASTICSEARCH_PORT", "9200"))

KAFKA_BOOTSTRAP = os.getenv("TEST_KAFKA_BOOTSTRAP", "localhost:9092")


@pytest.fixture(scope="session")
def pg_dsn():
    return f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"


@pytest.fixture(scope="session")
def es_url():
    return f"http://{ES_HOST}:{ES_PORT}"


@pytest.fixture(scope="session")
def kafka_servers():
    return KAFKA_BOOTSTRAP
