from __future__ import annotations

from typing import Any

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class DatasetCards:
    @staticmethod
    async def generate_default(name: str, dataset_type: str, description: str | None = None) -> dict[str, Any]:
        card = {
            "dataset_name": name,
            "title": name.replace("_", " ").title(),
            "summary": description or f"Dataset {name} for the ProxyDefence platform.",
            "dataset_type": dataset_type,
            "version": 1,
        }
        logger.info("dataset card generated", name=name, type=dataset_type)
        return card
