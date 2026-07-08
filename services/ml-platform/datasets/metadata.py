from __future__ import annotations

from typing import Any

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class DatasetMetadataManager:
    @staticmethod
    async def get_current_version(dataset_name: str) -> int | None:
        return 1
