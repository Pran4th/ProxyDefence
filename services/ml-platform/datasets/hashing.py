from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import asyncpg
import pandas as pd

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


class DatasetHasher:
    @staticmethod
    def hash_dataframe(df: pd.DataFrame) -> str:
        h = hashlib.sha256()
        h.update(pd.util.hash_pandas_object(df, index=True).values.tobytes())
        return h.hexdigest()

    @staticmethod
    def hash_json(data: Any) -> str:
        payload = json.dumps(data, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def hash_file(file_path: str) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()


class DatasetManifest:
    @staticmethod
    async def record(
        dataset_name: str, version: int, file_paths: list[Path],
        row_count: int | None = None, column_count: int | None = None,
    ) -> list[dict[str, Any]]:
        pool = await _get_pool()
        entries = []
        for fp in file_paths:
            if not fp.is_file():
                continue
            sha256 = DatasetHasher.hash_file(str(fp))
            file_size = fp.stat().st_size
            fmt = fp.suffix.lstrip(".") or "unknown"
            row = await pool.fetchrow(
                """INSERT INTO ml.dataset_manifests
                   (dataset_name, dataset_version, file_path, file_size, sha256,
                    row_count, column_count, format)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                   ON CONFLICT (dataset_name, dataset_version, file_path) DO UPDATE SET
                       file_size = EXCLUDED.file_size,
                       sha256 = EXCLUDED.sha256,
                       row_count = EXCLUDED.row_count,
                       column_count = EXCLUDED.column_count,
                       format = EXCLUDED.format
                   RETURNING *""",
                dataset_name, version, str(fp), file_size, sha256, row_count, column_count, fmt,
            )
            entries.append(dict(row))
        return entries

    @staticmethod
    async def get_manifest(dataset_name: str, version: int) -> list[dict[str, Any]]:
        pool = await _get_pool()
        rows = await pool.fetch(
            "SELECT * FROM ml.dataset_manifests WHERE dataset_name = $1 AND dataset_version = $2 ORDER BY file_path",
            dataset_name, version,
        )
        return [dict(r) for r in rows]

    @staticmethod
    async def verify(dataset_name: str, version: int) -> dict[str, Any]:
        entries = await DatasetManifest.get_manifest(dataset_name, version)
        if not entries:
            return {"dataset_name": dataset_name, "dataset_version": version, "verified": False, "reason": "no manifest entries found"}

        mismatches = []
        for entry in entries:
            fp = Path(entry["file_path"])
            if not fp.exists():
                mismatches.append({"file_path": entry["file_path"], "reason": "file missing"})
                continue
            actual = DatasetHasher.hash_file(str(fp))
            if actual != entry.get("sha256"):
                mismatches.append({"file_path": entry["file_path"], "reason": "checksum mismatch"})

        return {
            "dataset_name": dataset_name,
            "dataset_version": version,
            "verified": len(mismatches) == 0,
            "files_checked": len(entries),
            "mismatches": mismatches,
        }
