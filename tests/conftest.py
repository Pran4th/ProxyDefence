from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.api.app import app
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


@pytest.fixture(autouse=True)
def _restore_shared_modules_after_reload():
    """Undo cross-test pollution from tests that importlib.reload() shared
    singleton modules (backend.shared.settings/config and anything derived
    from them) under monkeypatched fake env vars.

    Module objects live in sys.modules for the whole process, so a reload
    under fake credentials leaks into every test that runs afterward in the
    same pytest session unless it's reloaded back once real env vars are
    restored. Autouse fixtures set up before explicitly-requested ones (like
    monkeypatch) at the same scope, so this fixture's teardown -- below the
    yield -- runs after monkeypatch has already reverted the environment,
    which is exactly when re-reloading picks up the real values again.
    """
    yield
    import importlib
    import sys

    for name in (
        "backend.shared.settings",
        "backend.shared.config",
        "backend.shared.database.postgres",
        "backend.api_service.security",
        "backend.shared.observability.health",
    ):
        module = sys.modules.get(name)
        if module is not None:
            importlib.reload(module)


# ── Mock pools / clients ──────────────────────────────────────────


@pytest_asyncio.fixture
async def mock_pg_pool():
    # asyncpg's real Pool.acquire() is a plain (sync) method that returns an
    # async-context-manager object -- it is not itself a coroutine to await.
    # `async with pool.acquire() as conn` therefore needs pool.acquire to be
    # a MagicMock (not AsyncMock), or the `async with` statement operates on
    # an unawaited coroutine instead of the context manager.
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=None)
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock(return_value="EXECUTE")
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock()
    pool.acquire = MagicMock(return_value=cm)
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


# ── API test client (real DB) ──────────────────────────────────────
#
# A generic mocked pool can't simulate a real INSERT ... RETURNING /
# uniqueness-constraint round trip, so flows like /auth/register that
# genuinely depend on that (not just "does the endpoint respond") need a
# real connection against the live dev database instead.


@pytest_asyncio.fixture
async def live_client(mock_es_client) -> AsyncGenerator[AsyncClient, None]:
    import asyncpg
    from backend.shared.database.postgres import build_dsn

    pool = await asyncpg.create_pool(dsn=build_dsn(), min_size=1, max_size=2)
    app.state.pg_pool = pool
    app.state.es_client = mock_es_client
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    finally:
        await pool.close()


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
