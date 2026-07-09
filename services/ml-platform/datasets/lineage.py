from __future__ import annotations

import json
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


class DatasetLineage:
    async def record(
        self, dataset_name: str, version: int, parent_name: str | None,
        parent_version: int | None, transform_type: str, transform_params: dict | None = None,
    ) -> dict[str, Any]:
        pool = await _get_pool()
        row = await pool.fetchrow(
            """INSERT INTO ml.dataset_lineage
               (dataset_name, dataset_version, parent_name, parent_version, transform_type, transform_params)
               VALUES ($1,$2,$3,$4,$5,$6)
               RETURNING *""",
            dataset_name, version, parent_name, parent_version, transform_type,
            json.dumps(transform_params or {}),
        )
        return dict(row)

    async def get_parents(self, dataset_name: str, version: int) -> list[dict[str, Any]]:
        pool = await _get_pool()
        rows = await pool.fetch(
            "SELECT * FROM ml.dataset_lineage WHERE dataset_name = $1 AND dataset_version = $2 ORDER BY created_at",
            dataset_name, version,
        )
        return [dict(r) for r in rows]

    async def get_children(self, dataset_name: str, version: int) -> list[dict[str, Any]]:
        pool = await _get_pool()
        rows = await pool.fetch(
            "SELECT * FROM ml.dataset_lineage WHERE parent_name = $1 AND parent_version = $2 ORDER BY created_at",
            dataset_name, version,
        )
        return [dict(r) for r in rows]

    async def get_lineage_graph(self, dataset_name: str, version: int, depth: int = 5) -> dict[str, Any]:
        nodes: dict[str, dict] = {}
        edges: list[dict] = []

        async def _walk_up(name: str, ver: int, remaining: int):
            key = f"{name}:{ver}"
            if key in nodes or remaining <= 0:
                return
            nodes[key] = {"dataset_name": name, "dataset_version": ver}
            parents = await self.get_parents(name, ver)
            for p in parents:
                pname, pver = p.get("parent_name"), p.get("parent_version")
                if pname:
                    edges.append({
                        "from": f"{pname}:{pver}", "to": key,
                        "transform_type": p.get("transform_type"),
                    })
                    await _walk_up(pname, pver, remaining - 1)

        await _walk_up(dataset_name, version, depth)
        return {
            "dataset_name": dataset_name,
            "dataset_version": version,
            "nodes": list(nodes.values()),
            "edges": edges,
        }


class DatasetProvenance:
    async def record(
        self, dataset_name: str, version: int, source_type: str, source_name: str,
        source_version: str | None = None, source_url: str | None = None,
        access_method: str | None = None, access_params: dict | None = None,
        checksum: str | None = None,
    ) -> dict[str, Any]:
        pool = await _get_pool()
        row = await pool.fetchrow(
            """INSERT INTO ml.dataset_provenance
               (dataset_name, dataset_version, source_type, source_name, source_version,
                source_url, access_method, access_params, retrieval_timestamp, checksum)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,now(),$9)
               RETURNING *""",
            dataset_name, version, source_type, source_name, source_version,
            source_url, access_method, json.dumps(access_params or {}), checksum,
        )
        return dict(row)

    async def get_source_tree(self, dataset_name: str, version: int) -> dict[str, Any]:
        pool = await _get_pool()
        rows = await pool.fetch(
            "SELECT * FROM ml.dataset_provenance WHERE dataset_name = $1 AND dataset_version = $2 ORDER BY retrieval_timestamp",
            dataset_name, version,
        )
        sources = [dict(r) for r in rows]
        return {
            "dataset_name": dataset_name,
            "dataset_version": version,
            "sources": sources,
            "source_count": len(sources),
        }
