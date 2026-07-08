from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from backend.shared.logging_config import get_logger
from config import DATASET_DIR, REPORT_DIR, DEFAULT_RANDOM_SEED, DEFAULT_TEST_SIZE, DEFAULT_VAL_SIZE
from db import get_pool

from dataset_factory.config import DatasetFactoryConfig
from dataset_factory.normalized import NormalizedCanonical
from dataset_factory.cleaning import CleaningPipeline
from dataset_factory.validators import DatasetValidator
from dataset_factory.quality import QualityReportGenerator
from dataset_factory.eda import EDAReportGenerator
from dataset_factory.features import FeatureEngineeringPipeline, FeatureConfig
from dataset_factory.feature_validation import FeatureValidator
from dataset_factory.exporters import DatasetExporter
from datasets.loader import EnergyServiceLoader, MockDataLoader
from datasets.splitter import DatasetSplitter
from datasets.versioning import DvcManager
from datasets.metadata import DatasetMetadataManager
from datasets.cards import DatasetCards
from datasets.catalog import DatasetCatalog
from datasets.lineage import DatasetLineage
from datasets.profiling import DatasetProfiler

logger = get_logger(__name__)


@dataclass
class BuildResult:
    dataset_name: str
    version: int
    total_records: int
    feature_count: int
    target_column: str
    splits: dict[str, int]
    duration_seconds: float

    normalized: bool = False
    cleaned: bool = False
    validated: bool = False
    quality_report: bool = False
    eda_report: bool = False
    feature_engineered: bool = False
    feature_validated: bool = False
    exported: bool = False
    registered: bool = False
    dataset_card: bool = False

    steps_completed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    export_path: str = ""
    db_uuid: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "version": self.version,
            "total_records": self.total_records,
            "feature_count": self.feature_count,
            "target_column": self.target_column,
            "splits": self.splits,
            "duration_seconds": round(self.duration_seconds, 2),
            "normalized": self.normalized,
            "cleaned": self.cleaned,
            "validated": self.validated,
            "quality_report": self.quality_report,
            "eda_report": self.eda_report,
            "feature_engineered": self.feature_engineered,
            "feature_validated": self.feature_validated,
            "exported": self.exported,
            "registered": self.registered,
            "dataset_card": self.dataset_card,
            "steps_completed": self.steps_completed,
            "errors": self.errors,
            "warnings": self.warnings,
            "export_path": self.export_path,
            "db_uuid": self.db_uuid,
        }


class DatasetFactory:
    def __init__(self, config: DatasetFactoryConfig | None = None):
        self._config = config or DatasetFactoryConfig()
        self._normalizer = NormalizedCanonical()
        self._cleaner = CleaningPipeline(config=self._config.to_dict())
        self._validator = DatasetValidator()
        self._quality = QualityReportGenerator()
        self._eda = EDAReportGenerator()
        self._features = FeatureEngineeringPipeline()
        self._feature_validator = FeatureValidator()
        self._exporter = DatasetExporter(output_dir=self._config.export_dir)
        self._splitter = DatasetSplitter(
            test_size=self._config.default_test_size,
            val_size=self._config.default_val_size,
            random_seed=self._config.random_seed,
        )
        self._dvc = DvcManager()
        self._catalog = DatasetCatalog()

    async def build(self, name: str,
                     target_column: str = "criticality_score",
                     feature_names: list[str] | None = None,
                     feature_configs: list[dict[str, Any]] | None = None,
                     force_synthetic: bool = False,
                     test_size: float | None = None,
                     val_size: float | None = None,
                     random_seed: int | None = None,
                     description: str | None = None,
                     dataset_type: str = "energy_infrastructure",
                     skip_normalize: bool = False,
                     skip_clean: bool = False,
                     skip_validate: bool = False,
                     skip_quality: bool = False,
                     skip_eda: bool = False,
                     skip_features: bool = False,
                     skip_feature_validation: bool = False,
                     skip_export: bool = False,
                     skip_db_registration: bool = False,
                     skip_dataset_card: bool = False,
                     db_pool: Any = None) -> BuildResult:
        t0 = time.monotonic()
        result = BuildResult(
            dataset_name=name,
            version=0,
            total_records=0,
            feature_count=0,
            target_column=target_column,
            splits={},
            duration_seconds=0.0,
        )

        try:
            pool = db_pool
            if pool is None and not skip_db_registration:
                try:
                    pool = await get_pool()
                except Exception:
                    pool = None
                    logger.warning("database unavailable, running without DB registration")

            version = 1
            if pool:
                existing_version = await pool.fetchval(
                    "SELECT MAX(version) FROM ml.datasets WHERE name = $1", name
                )
                version = (existing_version or 0) + 1
            result.version = version

            df, version = await self._execute_pipeline(
                pool, name, version, target_column, feature_names,
                feature_configs, force_synthetic, test_size, val_size,
                random_seed, description, dataset_type,
                skip_normalize, skip_clean, skip_validate, skip_quality,
                skip_eda, skip_features, skip_feature_validation,
                skip_export, skip_db_registration, skip_dataset_card,
                result,
            )

            result.total_records = len(df)
            result.feature_count = len(df.columns) - (1 if target_column in df.columns else 0)

        except Exception as e:
            result.errors.append(str(e))
            logger.error("dataset build failed for %s: %s", name, e, exc_info=True)
            raise

        result.duration_seconds = time.monotonic() - t0
        logger.info("dataset build complete for %s v%d in %.2fs: %s",
                     name, version, result.duration_seconds, result.steps_completed)
        return result

    async def _execute_pipeline(self, pool, name, version, target_column,
                                  feature_names, feature_configs, force_synthetic,
                                  test_size, val_size, random_seed,
                                  description, dataset_type,
                                  skip_normalize, skip_clean, skip_validate,
                                  skip_quality, skip_eda, skip_features,
                                  skip_feature_validation, skip_export,
                                  skip_db_registration, skip_dataset_card,
                                  result: BuildResult) -> tuple[pd.DataFrame, int]:
        logger.info("=" * 50)
        logger.info("DATASET FACTORY: %s v%d", name, version)
        logger.info("=" * 50)

        loader = EnergyServiceLoader()
        df = loader.load()

        if df.empty or (force_synthetic and len(df) < 100):
            df = MockDataLoader().load()
            logger.info("using synthetic data (%d records)", len(df))

        if df.empty:
            df = MockDataLoader().load()
            logger.info("using synthetic data (%d records)", len(df))

        if target_column not in df.columns:
            df = self._derive_target(df, target_column)

        df, version = await self._step_data_acquisition(
            pool, df, name, version, target_column, description, dataset_type, result
        )

        if not skip_normalize:
            df = await self._step_normalize(df, name, version, result)

        if not skip_clean:
            df = await self._step_clean(df, name, version, result)

        if feature_names:
            available = [c for c in feature_names if c in df.columns]
            missing = [c for c in feature_names if c not in df.columns]
            if missing:
                logger.warning("requested features not found: %s", missing)
            cols = available + ([target_column] if target_column in df.columns else [])
            df = df[cols] if cols else df

        if test_size is not None or val_size is not None:
            self._splitter = DatasetSplitter(
                test_size=test_size or DEFAULT_TEST_SIZE,
                val_size=val_size or DEFAULT_VAL_SIZE,
                random_seed=random_seed or DEFAULT_RANDOM_SEED,
            )

        splits = {}
        X_train, X_val, X_test, y_train, y_val, y_test = self._splitter.split(df, target_column)
        splits = {"train": len(X_train), "validation": len(X_val), "test": len(X_test)}

        train_df = X_train.copy()
        train_df[target_column] = y_train.values
        val_df = X_val.copy()
        val_df[target_column] = y_val.values
        test_df = X_test.copy()
        test_df[target_column] = y_test.values

        if not skip_validate:
            await self._step_validate(df, name, version, target_column, result)

        if not skip_quality:
            await self._step_quality(df, name, version, target_column, result)

        if not skip_eda:
            await self._step_eda(df, name, version, target_column, result)

        if not skip_features and feature_configs:
            df = await self._step_features(df, name, version, target_column, feature_configs, result)
            splits = self._resplit_and_save(df, target_column, name, version, splits, result)

        if not skip_feature_validation:
            await self._step_feature_validation(df, name, version, target_column, feature_configs, result)

        version_dir = Path(DATASET_DIR) / name / f"v{version}"
        version_dir.mkdir(parents=True, exist_ok=True)

        train_df = df.iloc[:splits.get("train", 0)]
        val_df = df.iloc[splits.get("train", 0):splits.get("train", 0) + splits.get("validation", 0)]
        test_df = df.iloc[splits.get("train", 0) + splits.get("validation", 0):]

        def _save_split(split_df: pd.DataFrame, split_name: str):
            if not split_df.empty:
                split_df.to_parquet(version_dir / f"{split_name}.parquet", index=False)

        _save_split(train_df, "train")
        _save_split(val_df, "validation")
        _save_split(test_df, "test")

        if not skip_export:
            await self._step_export(df, name, version, target_column,
                                      {"train": train_df, "validation": val_df, "test": test_df},
                                      result)

        try:
            self._dvc.track(str(version_dir))
        except Exception as e:
            logger.warning("DVC tracking failed: %s", e)
            result.warnings.append(f"DVC tracking failed: {e}")

        if not skip_db_registration and pool:
            try:
                db_row = await pool.fetchrow(
                    "INSERT INTO ml.datasets (name, version, path, total_records, train_records, val_records, test_records, "
                    "target_column, random_seed) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) "
                    "RETURNING uuid, name, version, path",
                    name, version, str(version_dir), len(df),
                    splits.get("train", 0), splits.get("validation", 0), splits.get("test", 0),
                    target_column, self._splitter._random_seed,
                )
                result.db_uuid = str(db_row["uuid"])
                result.registered = True
                result.steps_completed.append("db_registration")
            except Exception as e:
                logger.warning("DB registration failed: %s", e)
                result.warnings.append(f"DB registration failed: {e}")

        if not skip_dataset_card:
            await DatasetCards.generate_default(name, dataset_type, description)
            result.dataset_card = True
            result.steps_completed.append("dataset_card")

        result.splits = splits
        return df, version

    async def _step_data_acquisition(self, pool, df, name, version, target_column,
                                       description, dataset_type, result) -> tuple[pd.DataFrame, int]:
        result.steps_completed.append("data_acquisition")
        return df, version

    async def _step_normalize(self, df: pd.DataFrame, name: str, version: int,
                               result: BuildResult) -> pd.DataFrame:
        logger.info("step: normalize canonical records")
        norm_df, logs = self._normalizer.normalize_dataframe(df)
        n_warnings = sum(len(l.warnings) for l in logs)
        n_errors = sum(len(l.errors) for l in logs)
        result.normalized = True
        result.steps_completed.append("normalize")
        if n_warnings:
            result.warnings.append(f"normalization: {n_warnings} warnings")
        if n_errors:
            result.warnings.append(f"normalization: {n_errors} records with validation errors")
        return norm_df

    async def _step_clean(self, df: pd.DataFrame, name: str, version: int,
                           result: BuildResult) -> pd.DataFrame:
        logger.info("step: clean dataset")
        df, cleaning_report = self._cleaner.clean(df, name, version)
        result.cleaned = True
        result.steps_completed.append("clean")
        for w in cleaning_report.warnings:
            result.warnings.append(f"cleaning: {w}")
        return df

    async def _step_validate(self, df: pd.DataFrame, name: str, version: int,
                              target_column: str, result: BuildResult):
        logger.info("step: validate dataset")
        vreport = await self._validator.validate(
            df, name, version,
            target_column=target_column,
        )
        result.validated = vreport.passed_validation
        result.steps_completed.append("validate")
        if not vreport.passed_validation:
            failed = [r for r in vreport.results if not r.passed and r.severity == "error"]
            for f in failed:
                result.errors.append(f"validation: {f.check_name} - {f.message}")
        if vreport.warnings:
            result.warnings.append(f"validation: {vreport.warnings} warnings")

    async def _step_quality(self, df: pd.DataFrame, name: str, version: int,
                             target_column: str, result: BuildResult):
        logger.info("step: generate quality report")
        qreport = self._quality.generate(df, name, version, target_column)
        result.quality_report = True
        result.steps_completed.append("quality_report")
        if qreport.overall_score < 0.5:
            result.warnings.append(f"quality: overall score {qreport.overall_score:.4f} is low")

    async def _step_eda(self, df: pd.DataFrame, name: str, version: int,
                         target_column: str, result: BuildResult):
        logger.info("step: generate EDA report")
        ereport = self._eda.generate(df, name, version, target_column)
        result.eda_report = True
        result.steps_completed.append("eda_report")

    async def _step_features(self, df: pd.DataFrame, name: str, version: int,
                              target_column: str,
                              feature_configs: list[dict[str, Any]],
                              result: BuildResult) -> pd.DataFrame:
        logger.info("step: feature engineering (%d configs)", len(feature_configs))
        configs = []
        for fc in feature_configs:
            cfg = FeatureConfig(
                name=fc.get("name", "feature"),
                source_columns=fc.get("source_columns", fc.get("sources", [])),
                transform_type=fc.get("transform", fc.get("transform_type", "identity")),
                transform_params=fc.get("params", fc.get("transform_params", {})),
                description=fc.get("description", ""),
                freshness=fc.get("freshness", "realtime"),
                tags=fc.get("tags", []),
            )
            configs.append(cfg)
        df = self._features.apply_configs(df, configs, target_column)
        result.feature_engineered = True
        result.steps_completed.append("feature_engineering")
        return df

    async def _step_feature_validation(self, df: pd.DataFrame, name: str, version: int,
                                         target_column: str,
                                         feature_configs: list[dict[str, Any]] | None,
                                         result: BuildResult):
        logger.info("step: validate features")
        fresults = self._feature_validator.validate(df, target_column, feature_configs)
        n_failed = sum(1 for r in fresults.values() if not r.passed)
        result.feature_validated = True
        result.steps_completed.append("feature_validation")
        if n_failed:
            result.warnings.append(f"feature validation: {n_failed} features failed")
            for fname, fr in fresults.items():
                if not fr.passed:
                    for w in fr.warnings:
                        result.warnings.append(f"  {fname}: {w}")

    async def _step_export(self, df: pd.DataFrame, name: str, version: int,
                            target_column: str, splits: dict[str, pd.DataFrame],
                            result: BuildResult):
        logger.info("step: export dataset")
        manifest = self._exporter.export_all(
            df=df,
            dataset_name=name,
            version=version,
            splits=splits,
            metadata={"target_column": target_column, "description": f"{name} v{version}"},
            schema={"columns": list(df.columns), "count": len(df.columns)},
        )
        result.exported = True
        result.export_path = str(Path(self._config.export_dir) / name / f"v{version}")
        result.steps_completed.append("export")

    def _resplit_and_save(self, df: pd.DataFrame, target_column: str,
                            name: str, version: int,
                            current_splits: dict[str, int],
                            result: BuildResult) -> dict[str, int]:
        X_train, X_val, X_test, y_train, y_val, y_test = self._splitter.split(df, target_column)
        splits = {"train": len(X_train), "validation": len(X_val), "test": len(X_test)}
        return splits

    def _derive_target(self, df: pd.DataFrame, target_column: str) -> pd.DataFrame:
        import numpy as np
        if "criticality" in df.columns:
            cmap = {"low": 0, "medium": 1, "high": 2, "critical": 3}
            df[target_column] = df["criticality"].map(cmap).fillna(1).astype(int)
        else:
            num_cols = df.select_dtypes(include=[np.number]).columns
            if len(num_cols) > 0:
                df[target_column] = pd.qcut(
                    df[num_cols].sum(axis=1) / max(len(num_cols), 1),
                    4, labels=[0, 1, 2, 3]
                ).astype(int)
            else:
                df[target_column] = 1
        return df
