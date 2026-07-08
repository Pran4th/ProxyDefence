"""ProxyDefence shared database layer.

Every asyncpg service uses this package for pool management, DSN
construction, transactions, and schema migrations.
"""

from backend.shared.database.postgres import build_dsn, check_health
from backend.shared.database.pool import Pool
from backend.shared.database.transactions import transaction
from backend.shared.database.migrations import (
    bootstrap_schema,
    apply_sql_file,
    ensure_extension,
)

__all__ = [
    "build_dsn",
    "check_health",
    "Pool",
    "transaction",
    "bootstrap_schema",
    "apply_sql_file",
    "ensure_extension",
]
