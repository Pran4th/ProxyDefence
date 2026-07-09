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


class DatasetCards:
    @staticmethod
    async def generate_default(name: str, dataset_type: str, description: str | None = None) -> dict[str, Any]:
        title = name.replace("_", " ").replace("-", " ").title()
        summary = f"Dataset {name} for the ProxyDefence platform."
        return await DatasetCards.create_or_update(
            dataset_name=name,
            title=title,
            summary=summary,
            description=description or summary,
            intended_uses=f"Training and evaluating ML models for {dataset_type} use cases.",
            limitations="Auto-generated card; review for domain-specific caveats before external use.",
        )

    @staticmethod
    async def create_or_update(
        dataset_name: str, title: str | None = None, summary: str | None = None,
        description: str | None = None, intended_uses: str | None = None,
        limitations: str | None = None, ethical_considerations: str | None = None,
        maintenance: str | None = None, authors: list[str] | None = None,
        references: list[str] | None = None,
    ) -> dict[str, Any]:
        pool = await _get_pool()
        row = await pool.fetchrow(
            """INSERT INTO ml.dataset_cards
               (dataset_name, title, summary, description, intended_uses, limitations,
                ethical_considerations, maintenance, authors, references_json, version)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,1)
               ON CONFLICT (dataset_name) DO UPDATE SET
                   title = EXCLUDED.title,
                   summary = EXCLUDED.summary,
                   description = EXCLUDED.description,
                   intended_uses = EXCLUDED.intended_uses,
                   limitations = EXCLUDED.limitations,
                   ethical_considerations = EXCLUDED.ethical_considerations,
                   maintenance = EXCLUDED.maintenance,
                   authors = EXCLUDED.authors,
                   references_json = EXCLUDED.references_json,
                   version = ml.dataset_cards.version + 1,
                   updated_at = now()
               RETURNING *""",
            dataset_name, title, summary, description, intended_uses, limitations,
            ethical_considerations, maintenance,
            json.dumps(authors or []), json.dumps(references or []),
        )
        logger.info("dataset card generated", dataset=dataset_name)
        return dict(row)

    @staticmethod
    async def get(dataset_name: str) -> dict[str, Any] | None:
        pool = await _get_pool()
        row = await pool.fetchrow("SELECT * FROM ml.dataset_cards WHERE dataset_name = $1", dataset_name)
        return dict(row) if row else None
