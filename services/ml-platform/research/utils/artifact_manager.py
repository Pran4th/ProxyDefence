import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.shared.logging_config import get_logger
from config import ARTIFACT_DIR
from db import get_pool

logger = get_logger(__name__)


class ArtifactManager:
    def __init__(self, base_dir: str | None = None):
        self._base_dir = Path(base_dir or ARTIFACT_DIR)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    async def save(self, data: Any, name: str, artifact_type: str = "generic",
                    experiment_uuid: str | None = None,
                    run_uuid: str | None = None,
                    metadata: dict | None = None) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        artifact_dir = self._base_dir / artifact_type / f"{name}_{timestamp}"
        artifact_dir.mkdir(parents=True, exist_ok=True)

        if isinstance(data, str) and os.path.isfile(data):
            shutil.copy2(data, artifact_dir / Path(data).name)
            file_path = str(artifact_dir / Path(data).name)
        else:
            file_path = str(artifact_dir / f"{name}.json")
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2, default=str)

        file_size = os.path.getsize(file_path)
        checksum = self._compute_checksum(file_path)
        mime = self._guess_mime(file_path)

        pool = await get_pool()
        await pool.execute(
            "INSERT INTO ml.research_artifacts (artifact_type, name, file_path, file_size, "
            "mime_type, artifact_metadata, experiment_uuid, run_uuid, checksum) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
            artifact_type, name, file_path, file_size, mime,
            json.dumps(metadata or {}), experiment_uuid, run_uuid, checksum,
        )
        logger.info("artifact saved: %s (%s, %d bytes)", name, artifact_type, file_size)
        return file_path

    async def get(self, uuid: str) -> dict[str, Any] | None:
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT * FROM ml.research_artifacts WHERE uuid = $1", uuid,
        )
        return dict(row) if row else None

    async def list_by_experiment(self, experiment_uuid: str,
                                   artifact_type: str | None = None,
                                   limit: int = 100) -> list[dict[str, Any]]:
        pool = await get_pool()
        if artifact_type:
            rows = await pool.fetch(
                "SELECT * FROM ml.research_artifacts WHERE experiment_uuid = $1 AND artifact_type = $2 "
                "ORDER BY created_at DESC LIMIT $3",
                experiment_uuid, artifact_type, limit,
            )
        else:
            rows = await pool.fetch(
                "SELECT * FROM ml.research_artifacts WHERE experiment_uuid = $1 "
                "ORDER BY created_at DESC LIMIT $2",
                experiment_uuid, limit,
            )
        return [dict(r) for r in rows]

    async def list_by_type(self, artifact_type: str, limit: int = 100) -> list[dict[str, Any]]:
        pool = await get_pool()
        rows = await pool.fetch(
            "SELECT * FROM ml.research_artifacts WHERE artifact_type = $1 "
            "ORDER BY created_at DESC LIMIT $2",
            artifact_type, limit,
        )
        return [dict(r) for r in rows]

    def _compute_checksum(self, path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def _guess_mime(self, path: str) -> str:
        ext = Path(path).suffix.lower()
        mime_map = {
            ".json": "application/json",
            ".yaml": "application/x-yaml",
            ".yml": "application/x-yaml",
            ".csv": "text/csv",
            ".parquet": "application/parquet",
            ".pkl": "application/octet-stream",
            ".joblib": "application/octet-stream",
            ".png": "image/png",
            ".svg": "image/svg+xml",
            ".html": "text/html",
            ".md": "text/markdown",
            ".txt": "text/plain",
            ".pdf": "application/pdf",
        }
        return mime_map.get(ext, "application/octet-stream")
