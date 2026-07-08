"""Modular-api PostgreSQL pool (singleton, asyncpg).

Thin wrapper that uses the shared :class:`Pool` class so the modular-api
follows the same pattern as every other async service.
"""

from backend.shared.database import Pool

_pool = Pool(min_size=1, max_size=10, pool_name="modular-api")

get_pg_pool = _pool.get
close_pg_pool = _pool.close
