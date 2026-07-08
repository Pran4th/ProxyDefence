import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.shared.logging_config import get_logger
from data_acquisition.config import DataAcquisitionConfig, get_config

logger = get_logger(__name__)


@dataclass
class DataLakeConfig:
    base_dir: str = "./datasets"
    max_retries: int = 3
    retry_delay: float = 5.0
    chunk_size: int = 8192
    verify_checksums: bool = True
    preserve_archives: bool = False
    log_level: str = "INFO"


class DataLake:
    def __init__(self, config: DataLakeConfig | None = None) -> None:
        self._cfg = config or DataLakeConfig()
        self._base = Path(self._cfg.base_dir)

    @property
    def raw_dir(self) -> Path:
        return self._base / "raw"

    @property
    def processed_dir(self) -> Path:
        return self._base / "processed"

    @property
    def normalized_dir(self) -> Path:
        return self._base / "normalized"

    @property
    def features_dir(self) -> Path:
        return self._base / "features"

    @property
    def training_dir(self) -> Path:
        return self._base / "training"

    @property
    def registry_dir(self) -> Path:
        return self._base / "registry"

    async def ensure_directories(self) -> None:
        for d in [self.raw_dir, self.processed_dir, self.normalized_dir,
                  self.features_dir, self.training_dir, self.registry_dir]:
            d.mkdir(parents=True, exist_ok=True)
            logger.debug("ensured lake directory", dir=str(d))

    async def get_raw_path(self, source: str, version: str | None = None) -> Path:
        p = self.raw_dir / source
        if version:
            p = p / version
        return p

    async def get_processed_path(self, dataset_name: str, version: str | None = None) -> Path:
        p = self.processed_dir / dataset_name
        if version:
            p = p / version
        return p

    async def get_normalized_path(self, dataset_name: str, version: str | None = None) -> Path:
        p = self.normalized_dir / dataset_name
        if version:
            p = p / version
        return p

    async def get_features_path(self, dataset_name: str, version: str | None = None) -> Path:
        p = self.features_dir / dataset_name
        if version:
            p = p / version
        return p

    async def get_training_path(self, dataset_name: str, version: str | None = None) -> Path:
        p = self.training_dir / dataset_name
        if version:
            p = p / version
        return p

    async def get_registry_path(self, dataset_name: str) -> Path:
        return self.registry_dir / dataset_name

    async def list_versions(self, source: str) -> list[dict]:
        source_path = self.raw_dir / source
        if not source_path.exists():
            return []
        versions: list[dict] = []
        for entry in sorted(source_path.iterdir()):
            if entry.is_dir():
                created = datetime.fromtimestamp(entry.stat().st_ctime).isoformat()
                size = sum(f.stat().st_size for f in entry.rglob("*") if f.is_file())
                file_count = sum(1 for f in entry.rglob("*") if f.is_file())
                versions.append({
                    "version": entry.name,
                    "source": source,
                    "created": created,
                    "size_bytes": size,
                    "file_count": file_count,
                    "path": str(entry),
                })
        return versions

    async def list_sources(self) -> list[str]:
        if not self.raw_dir.exists():
            return []
        return sorted(
            e.name for e in self.raw_dir.iterdir() if e.is_dir()
        )

    async def get_source_info(self, source: str) -> dict:
        source_path = self.raw_dir / source
        if not source_path.exists():
            return {"source": source, "exists": False}
        versions = await self.list_versions(source)
        total_size = sum(v["size_bytes"] for v in versions)
        total_files = sum(v["file_count"] for v in versions)
        return {
            "source": source,
            "exists": True,
            "version_count": len(versions),
            "total_size_bytes": total_size,
            "total_files": total_files,
            "versions": versions,
        }

    async def get_lake_stats(self) -> dict:
        if not self._base.exists():
            return {"total_size_bytes": 0, "file_count": 0, "source_count": 0, "directories": {}}
        dirs_info: dict[str, dict[str, int]] = {}
        total_size = 0
        total_files = 0
        for subdir in ["raw", "processed", "normalized", "features", "training", "registry"]:
            p = self._base / subdir
            if p.exists():
                size = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
                count = sum(1 for f in p.rglob("*") if f.is_file())
                dirs_info[subdir] = {"size_bytes": size, "file_count": count}
                total_size += size
                total_files += count
            else:
                dirs_info[subdir] = {"size_bytes": 0, "file_count": 0}
        return {
            "total_size_bytes": total_size,
            "file_count": total_files,
            "source_count": len(await self.list_sources()),
            "directories": dirs_info,
        }

    async def create_version_dir(self, source: str, version: str) -> Path:
        version_path = self.raw_dir / source / version
        version_path.mkdir(parents=True, exist_ok=True)
        logger.info("created version directory", source=source, version=version, path=str(version_path))
        return version_path

    async def get_disk_usage(self) -> dict:
        usage: dict[str, int] = {}
        for source_dir in (self.raw_dir.iterdir() if self.raw_dir.exists() else []):
            if source_dir.is_dir():
                size = sum(f.stat().st_size for f in source_dir.rglob("*") if f.is_file())
                usage[source_dir.name] = size
        return usage
