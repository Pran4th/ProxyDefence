from __future__ import annotations

import asyncpg
from backend.shared.logging_config import get_logger

logger = get_logger(__name__)

VALID_DATASET_TYPES = {
    "commodity_prices", "digital_twin", "energy_infrastructure",
    "entity_relationships", "events", "graph_embeddings", "hybrid",
    "knowledge_graph", "news_articles", "procurement", "risk_signals", "spr",
}

DSN = "postgresql://admin:change-me@localhost:5432/defenseintel"


class DatasetCatalog:
    def __init__(self, dsn: str = DSN) -> None:
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=2)
        return self._pool

    async def register(
        self, name: str, dataset_type: str, description: str | None = None,
        category: str | None = None, tags: list[str] | None = None,
        owner: str = "system", source: str | None = None,
        documentation: str | None = None, license: str | None = None,
        pool=None,
    ) -> dict:
        if dataset_type not in VALID_DATASET_TYPES:
            raise ValueError(
                f"Invalid dataset_type: {dataset_type}. "
                f"Valid: {sorted(VALID_DATASET_TYPES)}"
            )
        p = pool or await self._get_pool()
        row = await p.fetchrow(
            "INSERT INTO ml.dataset_catalog "
            "(name, dataset_type, description, category, tags, owner, source, documentation, license) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) "
            "ON CONFLICT (name) DO UPDATE SET "
            "dataset_type = $2, description = $3, category = $4, "
            "tags = $5, owner = $6, source = $7, documentation = $8, license = $9 "
            "RETURNING uuid, name, dataset_type, created_at",
            name, dataset_type, description, category, tags or [], owner,
            source, documentation, license,
        )
        logger.info("dataset registered in catalog", name=name, type=dataset_type)
        return dict(row) if row else {"uuid": "", "name": name, "dataset_type": dataset_type}

    async def get(self, name: str, pool=None) -> dict | None:
        p = pool or await self._get_pool()
        row = await p.fetchrow(
            "SELECT * FROM ml.dataset_catalog WHERE name = $1", name
        )
        return dict(row) if row else None

    async def search(
        self, query: str | None = None, dataset_type: str | None = None,
        pool=None,
    ) -> tuple[list[dict], int]:
        p = pool or await self._get_pool()
        conditions = ["TRUE"]
        params: list = []
        if query:
            conditions.append("(name ILIKE $1 OR description ILIKE $1)")
            params.append(f"%{query}%")
        if dataset_type:
            conditions.append(f"dataset_type = ${len(params) + 1}")
            params.append(dataset_type)
        where = " AND ".join(conditions)
        rows = await p.fetch(
            f"SELECT * FROM ml.dataset_catalog WHERE {where} ORDER BY created_at DESC",
            *params,
        )
        return [dict(r) for r in rows], len(rows)

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
