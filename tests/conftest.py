from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.api_service.main import app
from backend.shared.settings import settings

# ── Test configuration ────────────────────────────────────────────


def pytest_configure(config):
    config.addinivalue_line("markers", "unit: Unit tests (no external dependencies)")
    config.addinivalue_line("markers", "integration: Integration tests (require PG/ES/Kafka)")
    config.addinivalue_line("markers", "slow: Tests that take more than 5 seconds")
    config.addinivalue_line("markers", "smoke: Quick smoke tests for CI")


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


# ── Mock pools / clients ──────────────────────────────────────────


@pytest_asyncio.fixture
async def mock_pg_pool():
    pool = MagicMock()
    pool.acquire = AsyncMock()
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=None)
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock(return_value="EXECUTE")
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock()
    pool.acquire.return_value = cm
    return pool


@pytest_asyncio.fixture
async def mock_es_client():
    client = AsyncMock()
    client.ping = AsyncMock(return_value=True)
    client.search = AsyncMock(return_value={
        "hits": {"total": {"value": 0}, "hits": []},
    })
    client.index = AsyncMock(return_value={"result": "created", "_id": "test-id"})
    client.close = AsyncMock()
    return client


# ── API test client (mocked deps) ─────────────────────────────────


@pytest_asyncio.fixture
async def async_client(mock_pg_pool, mock_es_client) -> AsyncGenerator[AsyncClient, None]:
    app.state.pg_pool = mock_pg_pool
    app.state.es_client = mock_es_client
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ── Auth helpers ──────────────────────────────────────────────────


@pytest.fixture
def auth_token():
    from datetime import datetime, timedelta, timezone
    from jose import jwt
    payload = {
        "sub": "1",
        "role": "admin",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


@pytest.fixture
def auth_headers(auth_token: str) -> dict:
    return {"Authorization": f"Bearer {auth_token}"}
