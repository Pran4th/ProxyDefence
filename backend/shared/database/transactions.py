"""Reusable transaction context manager for asyncpg.

Eliminates the repeated ``async with pool.acquire() as conn:`` /
``await conn.execute("BEGIN")`` / ``COMMIT`` / ``ROLLBACK`` pattern.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg


@asynccontextmanager
async def transaction(pool: asyncpg.Pool) -> AsyncIterator[asyncpg.Connection]:
    """Provide a transactional scope around a sequence of operations.

    Usage::

        async with transaction(pool) as conn:
            await conn.execute("INSERT INTO …")
            await conn.execute("UPDATE …")
            # auto-committed on success, rolled back on exception
    """
    async with pool.acquire() as conn:
        try:
            await conn.execute("BEGIN")
            yield conn
            await conn.execute("COMMIT")
        except BaseException:
            await conn.execute("ROLLBACK")
            raise
