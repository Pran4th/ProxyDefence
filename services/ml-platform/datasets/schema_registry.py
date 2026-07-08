from __future__ import annotations

from typing import Any

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class SchemaRegistry:
    def __init__(self):
        self._schemas: dict[str, dict] = {}

    async def register(self, name: str, schema: dict[str, Any], version: int = 1) -> dict:
        key = f"{name}_v{version}"
        self._schemas[key] = schema
        logger.info("schema registered", name=name, version=version)
        return {"name": name, "version": version, "columns": list(schema.keys())}

    async def get(self, name: str, version: int = 1) -> dict | None:
        return self._schemas.get(f"{name}_v{version}")
