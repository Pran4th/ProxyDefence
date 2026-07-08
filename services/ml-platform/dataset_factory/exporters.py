from __future__ import annotations

import csv
import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ExportManifest:
    dataset_name: str
    version: int
    files: list[dict[str, Any]] = field(default_factory=list)
    total_size_bytes: int = 0
    version_hash: str = ""
    created_at: str = ""

    def add_file(self, path: str, file_format: str, size_bytes: int, sha256: str):
        self.files.append({
            "path": path,
            "format": file_format,
            "size_bytes": size_bytes,
            "sha256": sha256,
        })
        self.total_size_bytes += size_bytes

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "version": self.version,
            "files": self.files,
            "total_size_bytes": self.total_size_bytes,
            "total_files": len(self.files),
            "version_hash": self.version_hash,
            "created_at": self.created_at,
        }


class DatasetExporter:
    def __init__(self, output_dir: str = "./data/exports"):
        self._output_dir = Path(output_dir)

    def export_all(self, df: pd.DataFrame, dataset_name: str, version: int,
                    splits: dict[str, pd.DataFrame] | None = None,
                    metadata: dict[str, Any] | None = None,
                    schema: dict[str, Any] | None = None,
                    quality_report: dict[str, Any] | None = None,
                    eda_report: dict[str, Any] | None = None,
                    feature_catalog: dict[str, Any] | None = None,
                    dataset_card: dict[str, Any] | None = None,
                    validation_report: dict[str, Any] | None = None) -> ExportManifest:
        base = self._output_dir / dataset_name / f"v{version}"
        base.mkdir(parents=True, exist_ok=True)

        manifest = ExportManifest(
            dataset_name=dataset_name,
            version=version,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        self._export_parquet(df, base, "full", manifest)
        self._export_csv(df, base, "full", manifest)

        if splits:
            for split_name, split_df in splits.items():
                if not split_df.empty:
                    self._export_parquet(split_df, base, split_name, manifest)
                    self._export_csv(split_df, base, split_name, manifest)

        if metadata:
            self._write_json(base, "metadata", metadata, manifest)
        if schema:
            self._write_json(base, "schema", schema, manifest)
        if quality_report:
            self._write_json(base, "quality_report", quality_report, manifest)
        if eda_report:
            self._write_json(base, "eda_report", eda_report, manifest)
        if feature_catalog:
            self._write_json(base, "feature_catalog", feature_catalog, manifest)
        if dataset_card:
            self._write_json(base, "dataset_card", dataset_card, manifest)
        if validation_report:
            self._write_json(base, "validation_report", validation_report, manifest)

        manifest.version_hash = self._compute_version_hash(base)
        self._write_manifest(base, manifest)
        self._generate_dataset_card_markdown(base, dataset_name, version, metadata, quality_report)
        self._generate_kaggle_metadata(base, dataset_name, metadata)

        logger.info("exported dataset %s v%d to %s (%d files, %s bytes)",
                     dataset_name, version, base,
                     len(manifest.files), manifest.total_size_bytes)
        return manifest

    def _export_parquet(self, df: pd.DataFrame, base_dir: Path,
                         suffix: str, manifest: ExportManifest):
        path = base_dir / f"{manifest.dataset_name}_v{manifest.version}_{suffix}.parquet"
        df.to_parquet(path, index=False)
        sha256 = self._hash_file(path)
        manifest.add_file(str(path), "parquet", path.stat().st_size, sha256)

    def _export_csv(self, df: pd.DataFrame, base_dir: Path,
                     suffix: str, manifest: ExportManifest):
        path = base_dir / f"{manifest.dataset_name}_v{manifest.version}_{suffix}.csv"
        df.to_csv(path, index=False)
        sha256 = self._hash_file(path)
        manifest.add_file(str(path), "csv", path.stat().st_size, sha256)

    def _write_json(self, base_dir: Path, name: str, data: dict[str, Any],
                     manifest: ExportManifest):
        path = base_dir / f"{manifest.dataset_name}_v{manifest.version}_{name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        sha256 = self._hash_file(path)
        manifest.add_file(str(path), "json", path.stat().st_size, sha256)

    def _write_manifest(self, base_dir: Path, manifest: ExportManifest):
        path = base_dir / f"{manifest.dataset_name}_v{manifest.version}_manifest.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(manifest.to_dict(), f, indent=2, default=str)

    def _hash_file(self, path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def _compute_version_hash(self, base_dir: Path) -> str:
        h = hashlib.sha256()
        for fpath in sorted(base_dir.iterdir()):
            if fpath.is_file() and fpath.suffix != ".md":
                h.update(fpath.name.encode())
                h.update(str(fpath.stat().st_size).encode())
                h.update(str(fpath.stat().st_mtime).encode())
        return h.hexdigest()[:16]

    def _generate_dataset_card_markdown(self, base_dir: Path, dataset_name: str,
                                          version: int, metadata: dict | None,
                                          quality_report: dict | None):
        md = [
            f"# Dataset Card: {dataset_name} v{version}",
            "",
            f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
            "",
            "## Description",
            metadata.get("description", f"Auto-generated dataset {dataset_name} v{version}") if metadata else "",
            "",
            "## Files",
        ]
        export_dir = self._output_dir / dataset_name / f"v{version}"
        for fpath in sorted(export_dir.iterdir()):
            if fpath.is_file():
                md.append(f"- {fpath.name} ({fpath.stat().st_size:,} bytes)")
        if quality_report:
            md += [
                "",
                "## Quality Scores",
                f"- **Overall:** {quality_report.get('overall_score', 'N/A')}",
            ]
            dims = quality_report.get("dimension_scores", {})
            for dim, score in dims.items():
                md.append(f"- **{dim}:** {score}")
        md.append("")
        md.append("---")
        md.append("_Auto-generated by ProxyDefence Dataset Factory_")
        path = base_dir / f"{dataset_name}_v{version}_DATASET_CARD.md"
        with open(path, "w") as f:
            f.write("\n".join(md))

    def _generate_kaggle_metadata(self, base_dir: Path, dataset_name: str,
                                    metadata: dict | None):
        kaggle_meta = {
            "title": dataset_name.replace("_", " ").title(),
            "id": f"proxydefence/{dataset_name}",
            "subtitle": (metadata or {}).get("description", "")[:80] if metadata else "",
            "description": (metadata or {}).get("description", ""),
            "licenses": [{"name": "MIT"}],
            "keywords": ["energy", "cyber-defense", "proxy-wars"],
        }
        path = base_dir / "dataset-metadata.json"
        with open(path, "w") as f:
            json.dump(kaggle_meta, f, indent=2)
