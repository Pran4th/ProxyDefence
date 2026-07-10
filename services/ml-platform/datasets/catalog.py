from __future__ import annotations

import json

import asyncpg
from backend.shared.logging_config import get_logger
from backend.shared.settings import settings

logger = get_logger(__name__)

VALID_DATASET_TYPES = {
    "commodity_prices", "digital_twin", "energy_infrastructure",
    "entity_relationships", "events", "gkg", "graph_embeddings", "hybrid",
    "knowledge_graph", "mentions", "news_articles", "procurement",
    "risk_signals", "spr",
}


def _default_dsn() -> str:
    host = settings.POSTGRES_HOST if settings.POSTGRES_HOST != "postgres" else "localhost"
    return (
        f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
        f"@{host}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    )


class DatasetCatalog:
    def __init__(self, dsn: str | None = None) -> None:
        self._dsn = dsn or _default_dsn()
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
        metadata: dict | None = None, pool: asyncpg.Pool | None = None,
    ) -> dict:
        if dataset_type not in VALID_DATASET_TYPES:
            raise ValueError(f"Invalid dataset_type: {dataset_type}. Valid: {sorted(VALID_DATASET_TYPES)}")
        p = pool or await self._get_pool()
        row = await p.fetchrow(
            """INSERT INTO ml.dataset_catalog
               (name, dataset_type, description, category, tags, owner, source,
                documentation, license, metadata)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
               ON CONFLICT (name) DO UPDATE SET
                   dataset_type = EXCLUDED.dataset_type,
                   description = EXCLUDED.description,
                   category = EXCLUDED.category,
                   tags = EXCLUDED.tags,
                   source = EXCLUDED.source,
                   documentation = EXCLUDED.documentation,
                   license = EXCLUDED.license,
                   metadata = EXCLUDED.metadata,
                   updated_at = now()
               RETURNING id, uuid, name, dataset_type, created_at, updated_at""",
            name, dataset_type, description, category, tags or [], owner, source,
            documentation, license, json.dumps(metadata or {}),
        )
        logger.info("dataset registered in catalog", name=name, type=dataset_type)
        return dict(row)

    async def get(self, name: str, pool: asyncpg.Pool | None = None) -> dict | None:
        p = pool or await self._get_pool()
        row = await p.fetchrow("SELECT * FROM ml.dataset_catalog WHERE name = $1", name)
        return dict(row) if row else None

    async def list_all(self, dataset_type: str | None = None, pool: asyncpg.Pool | None = None) -> list[dict]:
        p = pool or await self._get_pool()
        if dataset_type:
            rows = await p.fetch(
                "SELECT * FROM ml.dataset_catalog WHERE dataset_type = $1 AND is_active = true ORDER BY name",
                dataset_type,
            )
        else:
            rows = await p.fetch("SELECT * FROM ml.dataset_catalog WHERE is_active = true ORDER BY name")
        return [dict(r) for r in rows]

    async def search(
        self, query: str | None = None, dataset_type: str | None = None,
        category: str | None = None, tag: str | None = None, owner: str | None = None,
        limit: int = 100, offset: int = 0, pool: asyncpg.Pool | None = None,
    ) -> tuple[list[dict], int]:
        p = pool or await self._get_pool()
        conditions = ["is_active = true"]
        params: list = []
        if query:
            params.append(f"%{query}%")
            conditions.append(f"(name ILIKE ${len(params)} OR description ILIKE ${len(params)})")
        if dataset_type:
            params.append(dataset_type)
            conditions.append(f"dataset_type = ${len(params)}")
        if category:
            params.append(category)
            conditions.append(f"category = ${len(params)}")
        if tag:
            params.append(tag)
            conditions.append(f"${len(params)} = ANY(tags)")
        if owner:
            params.append(owner)
            conditions.append(f"owner = ${len(params)}")
        where = " AND ".join(conditions)

        total = await p.fetchval(f"SELECT COUNT(*) FROM ml.dataset_catalog WHERE {where}", *params)
        params.append(limit)
        params.append(offset)
        rows = await p.fetch(
            f"SELECT * FROM ml.dataset_catalog WHERE {where} ORDER BY name LIMIT ${len(params) - 1} OFFSET ${len(params)}",
            *params,
        )
        return [dict(r) for r in rows], total or 0

    async def list_types(self, pool: asyncpg.Pool | None = None) -> list[str]:
        p = pool or await self._get_pool()
        rows = await p.fetch(
            "SELECT DISTINCT dataset_type FROM ml.dataset_catalog WHERE is_active = true ORDER BY dataset_type"
        )
        return [r["dataset_type"] for r in rows]

    async def list_categories(self, pool: asyncpg.Pool | None = None) -> list[str]:
        p = pool or await self._get_pool()
        rows = await p.fetch(
            "SELECT DISTINCT category FROM ml.dataset_catalog WHERE is_active = true AND category IS NOT NULL ORDER BY category"
        )
        return [r["category"] for r in rows]

    async def update_tags(self, name: str, tags: list[str], pool: asyncpg.Pool | None = None) -> dict | None:
        p = pool or await self._get_pool()
        row = await p.fetchrow(
            "UPDATE ml.dataset_catalog SET tags = $1, updated_at = now() WHERE name = $2 "
            "RETURNING id, uuid, name, tags, updated_at",
            tags, name,
        )
        return dict(row) if row else None

    async def deactivate(self, name: str, pool: asyncpg.Pool | None = None) -> dict | None:
        p = pool or await self._get_pool()
        row = await p.fetchrow(
            "UPDATE ml.dataset_catalog SET is_active = false, updated_at = now() WHERE name = $1 "
            "RETURNING id, name",
            name,
        )
        return dict(row) if row else None

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
