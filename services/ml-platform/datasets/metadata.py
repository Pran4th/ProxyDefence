from __future__ import annotations

from typing import Any

import asyncpg

from backend.shared.logging_config import get_logger
from backend.shared.settings import settings

logger = get_logger(__name__)

_pool: asyncpg.Pool | None = None


def _default_dsn() -> str:
    host = settings.POSTGRES_HOST if settings.POSTGRES_HOST != "postgres" else "localhost"
    return (
        f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
        f"@{host}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    )


async def _get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(_default_dsn(), min_size=1, max_size=2)
    return _pool


class DatasetMetadataManager:
    @staticmethod
    async def get_current_version(dataset_name: str) -> int | None:
        pool = await _get_pool()
        version = await pool.fetchval(
            "SELECT MAX(version) FROM ml.datasets WHERE name = $1", dataset_name,
        )
        if version is not None:
            return int(version)

        version = await pool.fetchval(
            "SELECT MAX(dataset_version) FROM ml.dataset_statistics WHERE dataset_name = $1", dataset_name,
        )
        return int(version) if version is not None else None

    @staticmethod
    async def get_metadata(dataset_name: str, version: int | None = None) -> dict[str, Any] | None:
        pool = await _get_pool()
        if version is None:
            version = await DatasetMetadataManager.get_current_version(dataset_name)
            if version is None:
                return None
        row = await pool.fetchrow(
            "SELECT * FROM ml.datasets WHERE name = $1 AND version = $2", dataset_name, version,
        )
        return dict(row) if row else None
