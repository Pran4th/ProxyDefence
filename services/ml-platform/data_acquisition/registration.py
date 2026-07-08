import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from backend.shared.logging_config import get_logger
from data_acquisition.manifest import ManifestGenerator
from datasets.catalog import DatasetCatalog
from datasets.profiling import DatasetProfiler
from datasets.statistics import DatasetStatistics

logger = get_logger(__name__)


@dataclass
class DatasetRegistrationResult:
    dataset_name: str
    version: str
    status: str
    catalog_entry: dict
    statistics: dict
    preview_rows: int
    manifest_path: Path
    registration_id: str
    error: str | None = None


class DatasetRegistrationPipeline:
    def __init__(self) -> None:
        self._catalog = DatasetCatalog()
        self._manifest_gen = ManifestGenerator()

    async def register_dataset(
        self,
        dataset_name: str,
        source: str,
        version: str,
        processed_path: Path,
        schema: dict | None = None,
        pool=None,
    ) -> DatasetRegistrationResult:
        try:
            df = self._load_dataframe(processed_path)
            version_int = int(version) if version.isdigit() else 1

            stats = await DatasetStatistics.compute(df, dataset_name, version_int)
            await DatasetProfiler.profile(df, dataset_name, version_int)

            feature_summary = await self.compute_feature_summary(processed_path)
            missing_values = await self.compute_missing_values(processed_path)
            distributions = await self.compute_distributions(processed_path)
            preview = await self.generate_preview(processed_path)
            checksum = await self.compute_checksum(processed_path)
            inferred_schema = schema or await self.generate_schema(processed_path)

            catalog_entry = await self._catalog.register(
                name=dataset_name,
                dataset_type=source,
                description=f"Auto-registered dataset from {source} v{version}",
                source=source,
            )

            file_paths = (
                [processed_path]
                if processed_path.is_file()
                else list(processed_path.rglob("*"))
                if processed_path.is_dir()
                else []
            )

            manifest = await self._manifest_gen.generate_manifest(
                dataset_name=dataset_name,
                version=version,
                source=source,
                file_paths=file_paths,
                schema=inferred_schema,
                row_count=stats.get("row_count"),
                column_count=stats.get("column_count"),
            )
            manifest_dir = (
                processed_path.parent if processed_path.is_file() else processed_path
            )
            manifest_path = await self._manifest_gen.save_manifest(manifest, manifest_dir)

            combined_stats = {
                **stats,
                "feature_summary": feature_summary,
                "missing_values": missing_values,
                "distributions": distributions,
            }

            return DatasetRegistrationResult(
                dataset_name=dataset_name,
                version=version,
                status="registered",
                catalog_entry=catalog_entry,
                statistics=combined_stats,
                preview_rows=len(preview),
                manifest_path=manifest_path,
                registration_id=catalog_entry.get("uuid", ""),
            )

        except Exception as e:
            logger.error("dataset registration failed", dataset=dataset_name, error=str(e))
            return DatasetRegistrationResult(
                dataset_name=dataset_name,
                version=version,
                status="failed",
                catalog_entry={},
                statistics={},
                preview_rows=0,
                manifest_path=Path(),
                registration_id="",
                error=str(e),
            )

    async def compute_statistics(
        self, file_path: Path, schema: dict | None = None
    ) -> dict:
        df = self._load_dataframe(file_path)
        return {
            "row_count": len(df),
            "column_count": len(df.columns),
            "memory_bytes": int(df.memory_usage(deep=True).sum()),
            "missing_cells": int(df.isnull().sum().sum()),
            "total_cells": df.size,
            "duplicate_count": int(df.duplicated().sum()),
            "numerical_columns": int(len(df.select_dtypes(include=[np.number]).columns)),
            "categorical_columns": int(
                len(df.select_dtypes(include=["object", "category"]).columns)
            ),
            "boolean_columns": int(len(df.select_dtypes(include=["bool"]).columns)),
            "datetime_columns": int(
                len(df.select_dtypes(include=["datetime64"]).columns)
            ),
        }

    async def compute_feature_summary(self, file_path: Path) -> dict:
        df = self._load_dataframe(file_path)
        summary = {}
        for col in df.columns:
            col_data = df[col]
            summary[col] = {
                "dtype": str(col_data.dtype),
                "cardinality": int(col_data.nunique()),
                "cardinality_ratio": round(
                    float(col_data.nunique() / max(len(col_data), 1)), 6
                ),
                "missing_count": int(col_data.isnull().sum()),
                "missing_rate": round(float(col_data.isnull().mean()), 6),
            }
        return summary

    async def compute_missing_values(self, file_path: Path) -> dict:
        df = self._load_dataframe(file_path)
        result = {}
        for col in df.columns:
            missing = int(df[col].isnull().sum())
            result[col] = {
                "missing_count": missing,
                "missing_rate": round(missing / len(df), 6) if len(df) > 0 else 0.0,
            }
        return result

    async def compute_distributions(self, file_path: Path) -> dict:
        df = self._load_dataframe(file_path)
        distributions = {}
        for col in df.columns:
            col_data = df[col].dropna()
            if len(col_data) == 0:
                distributions[col] = {"type": "empty"}
                continue

            if pd.api.types.is_numeric_dtype(df[col]):
                distributions[col] = {
                    "type": "numerical",
                    "min": float(col_data.min()),
                    "max": float(col_data.max()),
                    "mean": float(col_data.mean()),
                    "std": float(col_data.std()),
                    "p25": float(col_data.quantile(0.25)),
                    "p50": float(col_data.median()),
                    "p75": float(col_data.quantile(0.75)),
                }

            elif (
                pd.api.types.is_categorical_dtype(df[col])
                or df[col].dtype == "object"
            ):
                vc = col_data.value_counts()
                distributions[col] = {
                    "type": "categorical",
                    "unique_values": vc.count(),
                    "top_values": {
                        str(k): int(v) for k, v in vc.head(10).items()
                    },
                }

            elif pd.api.types.is_datetime64_any_dtype(df[col]):
                delta = col_data.max() - col_data.min()
                range_days = delta.days if hasattr(delta, "days") else 0
                distributions[col] = {
                    "type": "temporal",
                    "min": str(col_data.min()),
                    "max": str(col_data.max()),
                    "range_days": range_days,
                }

            else:
                distributions[col] = {"type": "other", "dtype": str(df[col].dtype)}

        return distributions

    async def generate_preview(
        self, file_path: Path, n_rows: int = 100
    ) -> list[dict]:
        df = self._load_dataframe(file_path)
        preview_df = df.head(n_rows)
        preview_df = preview_df.where(pd.notnull(preview_df), None)
        return json.loads(preview_df.to_json(orient="records", date_format="iso"))

    async def generate_schema(self, file_path: Path) -> dict:
        df = self._load_dataframe(file_path)
        schema = {}
        for col in df.columns:
            dtype = df[col].dtype
            if pd.api.types.is_integer_dtype(dtype):
                schema[col] = "integer"
            elif pd.api.types.is_float_dtype(dtype):
                schema[col] = "float"
            elif pd.api.types.is_bool_dtype(dtype):
                schema[col] = "boolean"
            elif pd.api.types.is_datetime64_any_dtype(dtype):
                schema[col] = "datetime"
            elif pd.api.types.is_categorical_dtype(dtype):
                schema[col] = "categorical"
            else:
                schema[col] = "string"
        return schema

    async def compute_checksum(self, file_path: Path) -> str:
        h = hashlib.sha256()
        if file_path.is_file():
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
        else:
            for fp in sorted(file_path.rglob("*")):
                if fp.is_file():
                    with open(fp, "rb") as f:
                        for chunk in iter(lambda: f.read(8192), b""):
                            h.update(chunk)
        return h.hexdigest()

    async def verify_integrity(
        self, file_path: Path, expected_checksum: str
    ) -> bool:
        actual = await self.compute_checksum(file_path)
        return actual == expected_checksum

    async def build_feature_columns(self, file_path: Path) -> dict:
        df = self._load_dataframe(file_path)
        features: list[str] = []
        targets: list[str] = []
        categorical: list[str] = []
        numerical: list[str] = []
        temporal: list[str] = []
        geographical: list[str] = []
        entity: list[str] = []

        for col in df.columns:
            col_lower = col.lower()
            if col_lower in ("target", "label", "criticality_score", "criticality"):
                targets.append(col)
            elif any(
                g in col_lower
                for g in ("lat", "lon", "long", "latitude", "longitude", "geo", "coord")
            ):
                geographical.append(col)
            elif pd.api.types.is_datetime64_any_dtype(df[col]):
                temporal.append(col)
            elif any(e in col_lower for e in ("id", "uuid", "code", "key", "mmsi")):
                entity.append(col)
            elif pd.api.types.is_numeric_dtype(df[col]):
                numerical.append(col)
                features.append(col)
            elif (
                pd.api.types.is_categorical_dtype(df[col])
                or df[col].dtype == "object"
            ):
                if df[col].nunique() < 0.5 * len(df):
                    categorical.append(col)
                    features.append(col)
                else:
                    entity.append(col)
            else:
                features.append(col)

        return {
            "features": features,
            "targets": targets,
            "categorical": categorical,
            "numerical": numerical,
            "temporal": temporal,
            "geographical": geographical,
            "entity": entity,
        }

    @staticmethod
    def _load_dataframe(file_path: Path) -> pd.DataFrame:
        if file_path.is_dir():
            parquet_files = list(file_path.glob("*.parquet"))
            if parquet_files:
                return pd.concat(
                    [pd.read_parquet(f) for f in parquet_files], ignore_index=True
                )
            csv_files = list(file_path.glob("*.csv"))
            if csv_files:
                return pd.concat(
                    [pd.read_csv(f) for f in csv_files], ignore_index=True
                )
            raise ValueError(f"No data files found in directory: {file_path}")

        ext = file_path.suffix.lower()
        if ext == ".parquet":
            return pd.read_parquet(file_path)
        elif ext == ".csv":
            return pd.read_csv(file_path)
        elif ext == ".json":
            return pd.read_json(file_path)
        elif ext in (".xls", ".xlsx"):
            return pd.read_excel(file_path)
        elif ext == ".feather":
            return pd.read_feather(file_path)
        else:
            raise ValueError(f"Unsupported file format: {ext}")
