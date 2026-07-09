"""Shared query-execution helpers for the repositories that each hand-roll
`async with pool.acquire() as conn: rows = await conn.fetch(...);
return [record_to_dict(r) for r in rows]`.

Deliberately thin: only wraps connection-acquire + fetch + record_to_dict
mapping. Does NOT attempt to generate WHERE clauses or JOINs — those vary too
much per table (see investigations.list_cases, which aggregates across
joined tables and stays hand-written) to safely generify without hiding real
query differences behind a leaky abstraction.
"""
from typing import Any

from backend.api.common.schema import record_to_dict


async def fetch_all(pool, sql: str, *params: Any) -> list[dict[str, Any]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)
    return [record_to_dict(row) for row in rows]


async def fetch_one(pool, sql: str, *params: Any) -> dict[str, Any] | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, *params)
    return record_to_dict(row) if row else None
