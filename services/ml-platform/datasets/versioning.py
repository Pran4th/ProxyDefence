from __future__ import annotations

from pathlib import Path

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class DvcManager:
    def __init__(self, remote: str | None = None):
        self._remote = remote

    def track(self, path: str) -> dict:
        logger.info("DVC tracking placeholder", path=path)
        return {"tracked": True, "path": path}
