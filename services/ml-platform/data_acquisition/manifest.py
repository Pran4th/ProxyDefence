import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class DatasetManifest:
    dataset_name: str
    version: str
    source: str
    download_date: str
    file_count: int
    total_size_bytes: int
    checksum: str
    schema_hash: str
    row_count: int | None = None
    column_count: int | None = None
    last_updated: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    license: str = ""
    citation: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ManifestGenerator:
    def __init__(self) -> None:
        self._lake_path: Path | None = None

    def _set_lake_path(self, p: Path) -> None:
        self._lake_path = p

    async def _default(self, dataset_name: str, version: str) -> Path:
        base = Path("./datasets/processed") / dataset_name / version
        return base

    async def get_manifest_path(self, dataset_name: str, version: str) -> Path:
        base = self._lake_path or await self._default(dataset_name, version)
        return base / "dataset.yaml"

    async def generate_manifest(
        self,
        dataset_name: str,
        version: str,
        source: str,
        file_paths: list[Path],
        schema: dict | None = None,
        **kwargs: Any,
    ) -> DatasetManifest:
        checksum = await self.compute_checksum(file_paths)
        schema_hash = await self.compute_schema_hash(schema or {})
        total_size = sum(p.stat().st_size for p in file_paths if p.exists())
        file_count = len(file_paths)

        return DatasetManifest(
            dataset_name=dataset_name,
            version=version,
            source=source,
            download_date=datetime.utcnow().isoformat(),
            file_count=file_count,
            total_size_bytes=total_size,
            checksum=checksum,
            schema_hash=schema_hash,
            last_updated=datetime.utcnow().isoformat(),
            **{k: v for k, v in kwargs.items() if hasattr(DatasetManifest, k)},
        )

    async def save_manifest(self, manifest: DatasetManifest, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = output_dir / "dataset.yaml"
        data = asdict(manifest)
        with open(manifest_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        logger.info("manifest saved", path=str(manifest_path), dataset=manifest.dataset_name)
        return manifest_path

    async def load_manifest(self, manifest_path: Path) -> DatasetManifest:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return DatasetManifest(**data)

    async def verify_manifest(self, manifest: DatasetManifest, file_paths: list[Path]) -> bool:
        current_checksum = await self.compute_checksum(file_paths)
        match = current_checksum == manifest.checksum
        if not match:
            logger.warning(
                "manifest checksum mismatch",
                expected=manifest.checksum,
                actual=current_checksum,
            )
        return match

    async def compute_checksum(self, file_paths: list[Path]) -> str:
        h = hashlib.sha256()
        for fp in sorted(file_paths):
            if not fp.exists():
                continue
            with open(fp, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
        return h.hexdigest()

    async def compute_schema_hash(self, schema: dict) -> str:
        return hashlib.sha256(
            json.dumps(schema, sort_keys=True, default=str).encode()
        ).hexdigest()
