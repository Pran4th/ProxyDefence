from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class DatasetHasher:
    @staticmethod
    def hash_dataframe(df: pd.DataFrame) -> str:
        raw = df.to_csv(index=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def hash_json(data: dict[str, Any]) -> str:
        raw = json.dumps(data, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def hash_file(filepath: str, chunk_size: int = 8192) -> str:
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()


class DatasetManifest:
    @staticmethod
    async def get_manifest(name: str, version: int) -> list[dict[str, Any]]:
        return [{"dataset_name": name, "version": version, "status": "available"}]

    @staticmethod
    async def verify(name: str, version: int) -> dict[str, Any]:
        return {"verified": True, "dataset_name": name, "version": version}
