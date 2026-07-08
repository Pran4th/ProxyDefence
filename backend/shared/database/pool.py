"""Pool management — the only place where asyncpg pools are created.

Every async service creates a single ``Pool`` instance in its local
``db.py`` and exports ``get_pool`` / ``close_pool`` from it.
"""

import json

import asyncpg

from backend.shared.database.postgres import build_dsn


async def _init_conn(conn: asyncpg.Connection) -> None:
    """Register JSON/JSONB codecs so asyncpg returns dict/list instead of str."""
    await conn.set_type_codec(
        "json",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


class Pool:
    """Manages a singleton asyncpg connection pool for one service.

    Usage in a service's ``db.py``::

        from backend.shared.database import Pool

        pool = Pool(min_size=2, max_size=10, search_path="energy,public",
                    pool_name="energy-service")

        get_pool = pool.get
        close_pool = pool.close
    """

    def __init__(
        self,
        *,
        min_size: int = 2,
        max_size: int = 10,
        command_timeout: int = 30,
        search_path: str | None = None,
        pool_name: str = "default",
    ):
        self._min_size = min_size
        self._max_size = max_size
        self._command_timeout = command_timeout
        self._search_path = search_path
        self._pool_name = pool_name
        self._pool: asyncpg.Pool | None = None

    async def get(self) -> asyncpg.Pool:
        """Return the singleton pool, creating it lazily if needed."""
        if self._pool is None:
            server_settings: dict[str, str] = {}
            if self._search_path:
                server_settings["search_path"] = self._search_path
            self._pool = await asyncpg.create_pool(
                dsn=build_dsn(),
                min_size=self._min_size,
                max_size=self._max_size,
                command_timeout=self._command_timeout,
                server_settings=server_settings or None,
                init=_init_conn,
            )
        return self._pool

    async def close(self) -> None:
        """Close the pool and reset the singleton."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    @property
    def initialized(self) -> bool:
        return self._pool is not None
