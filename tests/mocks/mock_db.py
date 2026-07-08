"""Mock asyncpg Pool and Connection for unit tests."""

from unittest.mock import AsyncMock, MagicMock


class MockConnection:
    """In-memory mock for asyncpg.Connection with configurable fetch behavior."""

    def __init__(self):
        self.executed = []
        self._fetchval_return = None
        self._fetchrow_return = None
        self._fetch_return = None

    async def fetchval(self, query: str, *args) -> any:
        self.executed.append(("fetchval", query, args))
        return self._fetchval_return

    async def fetchrow(self, query: str, *args) -> dict | None:
        self.executed.append(("fetchrow", query, args))
        return self._fetchrow_return

    async def fetch(self, query: str, *args) -> list[dict]:
        self.executed.append(("fetch", query, args))
        return self._fetch_return or []

    async def execute(self, query: str, *args) -> str:
        self.executed.append(("execute", query, args))
        return "EXECUTE"


class MockPool:
    """Mock for asyncpg.Pool that returns MockConnections."""

    def __init__(self):
        self.connections: list[MockConnection] = []
        self.closed = False

    def acquire(self) -> "MockPoolAcquirer":
        conn = MockConnection()
        self.connections.append(conn)
        return MockPoolAcquirer(conn)

    async def close(self):
        self.closed = True


class MockPoolAcquirer:
    """Context manager returned by MockPool.acquire()."""

    def __init__(self, conn: MockConnection):
        self._conn = conn

    async def __aenter__(self) -> MockConnection:
        return self._conn

    async def __aexit__(self, *args):
        pass


def make_mock_pool_with_data(rows: list[dict] | None = None) -> MockPool:
    """Create a MockPool whose connections return the given rows on fetch()."""
    pool = MockPool()
    if rows:
        for conn in pool.connections:
            conn._fetch_return = rows
    return pool
