from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

import numpy as np
import pandas as pd

from backend.shared.logging_config import get_logger
from dataset_factory.normalized import ISO_COUNTRY_MAP

logger = get_logger(__name__)


class ValidationSeverity:
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationResult:
    check_name: str
    passed: bool
    severity: str = ValidationSeverity.ERROR
    score: float = 1.0
    details: dict[str, Any] = field(default_factory=dict)
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_name": self.check_name,
            "passed": self.passed,
            "severity": self.severity,
            "score": self.score,
            "details": self.details,
            "message": self.message,
        }


@dataclass
class ValidationReport:
    dataset_name: str
    version: int
    total_checks: int = 0
    passed: int = 0
    failed: int = 0
    warnings: int = 0
    results: list[ValidationResult] = field(default_factory=list)
    overall_score: float = 1.0
    passed_validation: bool = True
    timestamp: str = ""

    def add_result(self, result: ValidationResult):
        self.results.append(result)
        self.total_checks += 1
        if result.passed:
            self.passed += 1
        else:
            if result.severity == ValidationSeverity.WARNING:
                self.warnings += 1
            else:
                self.failed += 1

    def finalize(self):
        if self.total_checks > 0:
            self.overall_score = round(self.passed / self.total_checks, 4)
        self.passed_validation = self.failed == 0
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        self.finalize()
        return {
            "dataset_name": self.dataset_name,
            "version": self.version,
            "total_checks": self.total_checks,
            "passed": self.passed,
            "failed": self.failed,
            "warnings": self.warnings,
            "overall_score": self.overall_score,
            "passed_validation": self.passed_validation,
            "timestamp": self.timestamp,
            "results": [r.to_dict() for r in self.results],
        }


class DatasetValidator:
    def __init__(self):
        self._checks: list[tuple[str, Callable]] = []
        self._register_defaults()

    def _register_defaults(self):
        self._checks = [
            ("schema_validation", self._check_schema),
            ("primary_key_uniqueness", self._check_primary_keys),
            ("temporal_consistency", self._check_temporal),
            ("country_codes", self._check_country_codes),
            ("coordinates", self._check_coordinates),
            ("categorical_domains", self._check_categorical_domains),
            ("entity_references", self._check_entity_references),
            ("relationship_consistency", self._check_relationships),
            ("duplicate_rows", self._check_duplicate_rows),
            ("null_percentage", self._check_null_percentage),
            ("feature_completeness", self._check_feature_completeness),
            ("target_completeness", self._check_target_completeness),
            ("dataset_grain", self._check_dataset_grain),
        ]

    def add_check(self, name: str, check_fn: Callable):
        self._checks.append((name, check_fn))

    async def validate(self, df: pd.DataFrame, dataset_name: str, version: int,
                        target_column: str | None = None,
                        schema: dict[str, Any] | None = None,
                        primary_keys: list[str] | None = None,
                        categorical_domains: dict[str, list[str]] | None = None) -> ValidationReport:
        report = ValidationReport(dataset_name=dataset_name, version=version)

        for name, check_fn in self._checks:
            try:
                result = check_fn(df, target_column=target_column, schema=schema,
                                  primary_keys=primary_keys,
                                  categorical_domains=categorical_domains)
                report.add_result(result)
            except Exception as e:
                report.add_result(ValidationResult(
                    check_name=name,
                    passed=False,
                    severity=ValidationSeverity.ERROR,
                    score=0.0,
                    details={"error": str(e)},
                    message=f"check threw exception: {e}",
                ))

        report.finalize()
        logger.info("validation %s for %s v%d: %d/%d passed (score=%.4f)",
                     "PASSED" if report.passed_validation else "FAILED",
                     dataset_name, version, report.passed, report.total_checks, report.overall_score)
        return report

    def _check_schema(self, df: pd.DataFrame, **kwargs) -> ValidationResult:
        schema = kwargs.get("schema")
        if not schema or "columns" not in schema:
            return ValidationResult("schema_validation", True, ValidationSeverity.INFO,
                                    1.0, {}, "no schema provided, skipping")
        expected = set(schema["columns"])
        actual = set(df.columns)
        missing = expected - actual
        extra = actual - expected
        passed = len(missing) == 0
        score = 1.0 - len(missing) / len(expected) if expected else 1.0
        details = {"missing_columns": list(missing), "extra_columns": list(extra)}
        return ValidationResult("schema_validation", passed, ValidationSeverity.ERROR,
                                max(0.0, score), details,
                                f"{len(missing)} missing, {len(extra)} extra columns")

    def _check_primary_keys(self, df: pd.DataFrame, **kwargs) -> ValidationResult:
        keys = kwargs.get("primary_keys")
        if not keys:
            return ValidationResult("primary_key_uniqueness", True, ValidationSeverity.INFO,
                                    1.0, {}, "no primary keys specified, skipping")
        valid_keys = [k for k in keys if k in df.columns]
        if not valid_keys:
            return ValidationResult("primary_key_uniqueness", False, ValidationSeverity.ERROR,
                                    0.0, {"specified_keys": keys, "available_keys": list(df.columns)},
                                    "no primary key columns found in dataframe")
        dups = df.duplicated(subset=valid_keys, keep=False).sum()
        rate = dups / len(df) if len(df) > 0 else 0
        passed = dups == 0
        return ValidationResult("primary_key_uniqueness", passed, ValidationSeverity.ERROR,
                                round(1.0 - rate, 6),
                                {"duplicates": int(dups), "rate": round(rate, 6), "keys": valid_keys},
                                f"{dups} duplicate primary key rows")

    def _check_temporal(self, df: pd.DataFrame, **kwargs) -> ValidationResult:
        time_cols = [c for c in df.columns if df[c].dtype in ("datetime64[ns]", "datetime64[ns, UTC]")]
        if not time_cols:
            return ValidationResult("temporal_consistency", True, ValidationSeverity.INFO,
                                    1.0, {}, "no datetime columns found")
        issues = []
        for col in time_cols:
            col_data = df[col].dropna()
            if len(col_data) < 2:
                continue
            sorted_data = col_data.sort_values()
            diffs = sorted_data.diff().dropna()
            if len(diffs) > 0 and (diffs < pd.Timedelta(0)).any():
                count = int((diffs < pd.Timedelta(0)).sum())
                issues.append(f"{col}:{count}_non_monotonic")
            min_dt, max_dt = col_data.min(), col_data.max()
            try:
                if max_dt > pd.Timestamp.now() + pd.Timedelta(days=1):
                    issues.append(f"{col}:future_dates_{max_dt.date()}")
            except Exception:
                pass
        passed = len(issues) == 0
        return ValidationResult("temporal_consistency", passed, ValidationSeverity.WARNING,
                                round(1.0 - len(issues) / max(len(time_cols), 1), 6),
                                {"issues": issues, "datetime_columns": time_cols},
                                f"{len(issues)} temporal issues")

    def _check_country_codes(self, df: pd.DataFrame, **kwargs) -> ValidationResult:
        country_cols = [c for c in df.columns if any(k in c.lower() for k in
                       ("country", "iso", "nation", "location_code"))]
        invalid = {}
        for col in country_cols:
            values = df[col].dropna().unique()
            bad = [str(v) for v in values if str(v).upper() not in ISO_COUNTRY_MAP.values()
                   and str(v).lower() not in ISO_COUNTRY_MAP
                   and str(v).strip().upper() not in ISO_COUNTRY_MAP.values()
                   and len(str(v).strip()) == 2]
            if bad:
                invalid[col] = bad[:20]
        passed = len(invalid) == 0
        return ValidationResult("country_codes", passed, ValidationSeverity.WARNING,
                                1.0 - len(invalid) / max(len(country_cols), 1),
                                {"invalid_countries": invalid, "columns_checked": country_cols},
                                f"{len(invalid)} columns with invalid country codes")

    def _check_coordinates(self, df: pd.DataFrame, **kwargs) -> ValidationResult:
        lat_cols = [c for c in df.columns if "lat" in c.lower() and "latitude" in c.lower()]
        lng_cols = [c for c in df.columns if any(k in c.lower() for k in ("lon", "lng"))]
        if not lat_cols and not lng_cols:
            return ValidationResult("coordinates", True, ValidationSeverity.INFO,
                                    1.0, {}, "no coordinate columns found")

        invalid = 0
        total = 0
        for col in lat_cols + lng_cols:
            if col in df.columns and pd.api.types.is_numeric_dtype(df[col].dtype):
                valid = df[col].dropna()
                total += len(valid)
                threshold = 90 if col in lat_cols else 180
                invalid += int((valid.abs() > threshold).sum())
        passed = invalid == 0
        rate = invalid / total if total > 0 else 0
        return ValidationResult("coordinates", passed, ValidationSeverity.ERROR,
                                round(1.0 - rate, 6),
                                {"invalid_count": invalid, "total_checked": total},
                                f"{invalid} coordinate values out of bounds")

    def _check_categorical_domains(self, df: pd.DataFrame, **kwargs) -> ValidationResult:
        domains = kwargs.get("categorical_domains", {})
        if not domains:
            return ValidationResult("categorical_domains", True, ValidationSeverity.INFO,
                                    1.0, {}, "no domain definitions provided")
        violations = {}
        for col, valid_values in domains.items():
            if col in df.columns:
                col_data = df[col].dropna()
                invalid_vals = col_data[~col_data.isin(valid_values)].unique()
                if len(invalid_vals) > 0:
                    violations[col] = [str(v) for v in invalid_vals[:10]]
        passed = len(violations) == 0
        return ValidationResult("categorical_domains", passed, ValidationSeverity.ERROR,
                                1.0 - len(violations) / max(len(domains), 1),
                                {"violations": violations, "domains_checked": list(domains.keys())},
                                f"{len(violations)} columns with out-of-domain values")

    def _check_entity_references(self, df: pd.DataFrame, **kwargs) -> ValidationResult:
        ref_cols = [c for c in df.columns if c.endswith("_id") or c.endswith("_uuid")]
        valid_refs = [c for c in ref_cols if c in df.columns and c != "id"]
        if not valid_refs:
            return ValidationResult("entity_references", True, ValidationSeverity.INFO,
                                    1.0, {}, "no reference columns found")
        null_counts = {c: int(df[c].isnull().sum()) for c in valid_refs}
        high_null = {c: n for c, n in null_counts.items() if n > 0.5 * len(df)}
        passed = len(high_null) == 0
        return ValidationResult("entity_references", passed, ValidationSeverity.WARNING,
                                1.0 - len(high_null) / max(len(valid_refs), 1),
                                {"null_references": high_null, "reference_columns": valid_refs},
                                f"{len(high_null)} reference columns with >50% nulls")

    def _check_relationships(self, df: pd.DataFrame, **kwargs) -> ValidationResult:
        rel_cols = [c for c in df.columns if "relation" in c.lower() or "relationship" in c.lower()]
        if not rel_cols:
            return ValidationResult("relationship_consistency", True, ValidationSeverity.INFO,
                                    1.0, {}, "no relationship columns found")
        issues = []
        for col in rel_cols:
            raw = df[col].dropna()
            if len(raw) == 0:
                continue
            try:
                parsed = raw.apply(lambda x: json.loads(x) if isinstance(x, str) else x)
                invalid = parsed.apply(lambda x: not isinstance(x, (list, dict))).sum()
                if invalid > 0:
                    issues.append(f"{col}:{invalid}_invalid_formats")
            except Exception:
                issues.append(f"{col}:parse_error")
        passed = len(issues) == 0
        return ValidationResult("relationship_consistency", passed, ValidationSeverity.WARNING,
                                1.0 - len(issues) / max(len(rel_cols), 1),
                                {"issues": issues, "relationship_columns": rel_cols},
                                f"{len(issues)} relationship consistency issues")

    def _check_duplicate_rows(self, df: pd.DataFrame, **kwargs) -> ValidationResult:
        dups = df.duplicated().sum()
        rate = dups / len(df) if len(df) > 0 else 0
        passed = rate < 0.01
        return ValidationResult("duplicate_rows", passed, ValidationSeverity.ERROR,
                                round(1.0 - rate, 6),
                                {"duplicate_count": int(dups), "duplicate_rate": round(rate, 6)},
                                f"{dups} duplicate rows ({rate:.2%})")

    def _check_null_percentage(self, df: pd.DataFrame, **kwargs) -> ValidationResult:
        threshold = kwargs.get("null_threshold", 0.5)
        total_cells = df.size
        if total_cells == 0:
            return ValidationResult("null_percentage", False, ValidationSeverity.ERROR,
                                    0.0, {}, "empty dataframe")
        null_count = int(df.isnull().sum().sum())
        rate = null_count / total_cells
        passed = rate < threshold
        cols_above = {c: round(float(df[c].isnull().mean()), 6)
                      for c in df.columns if df[c].isnull().mean() > threshold}
        return ValidationResult("null_percentage", passed, ValidationSeverity.ERROR,
                                round(1.0 - rate, 6),
                                {"null_count": null_count, "null_rate": round(rate, 6),
                                 "columns_above_threshold": cols_above},
                                f"null rate: {rate:.2%}")

    def _check_feature_completeness(self, df: pd.DataFrame, **kwargs) -> ValidationResult:
        target = kwargs.get("target_column")
        feature_cols = [c for c in df.columns if c != target]
        if not feature_cols:
            return ValidationResult("feature_completeness", True, ValidationSeverity.INFO,
                                    1.0, {}, "no feature columns")
        incomplete_cols = {c: round(float(df[c].isnull().mean()), 6)
                           for c in feature_cols if df[c].isnull().mean() > 0.1}
        passed = len(incomplete_cols) == 0
        return ValidationResult("feature_completeness", passed, ValidationSeverity.WARNING,
                                1.0 - len(incomplete_cols) / max(len(feature_cols), 1),
                                {"feature_count": len(feature_cols),
                                 "incomplete_features": incomplete_cols},
                                f"{len(incomplete_cols)} features with >10% nulls")

    def _check_target_completeness(self, df: pd.DataFrame, **kwargs) -> ValidationResult:
        target = kwargs.get("target_column")
        if not target or target not in df.columns:
            return ValidationResult("target_completeness", False, ValidationSeverity.ERROR,
                                    0.0, {"target_column": target},
                                    f"target column '{target}' not found")
        null_targets = int(df[target].isnull().sum())
        rate = null_targets / len(df) if len(df) > 0 else 1.0
        passed = rate < 0.01
        return ValidationResult("target_completeness", passed, ValidationSeverity.ERROR,
                                round(1.0 - rate, 6),
                                {"null_targets": null_targets, "null_rate": round(rate, 6),
                                 "target_column": target},
                                f"{null_targets} null targets ({rate:.2%})")

    def _check_dataset_grain(self, df: pd.DataFrame, **kwargs) -> ValidationResult:
        if len(df) == 0:
            return ValidationResult("dataset_grain", False, ValidationSeverity.ERROR,
                                    0.0, {}, "empty dataset")
        if len(df) < 100:
            return ValidationResult("dataset_grain", False, ValidationSeverity.WARNING,
                                    round(len(df) / 100, 4),
                                    {"row_count": len(df)},
                                    f"only {len(df)} rows, expected >= 100")
        return ValidationResult("dataset_grain", True, ValidationSeverity.INFO,
                                1.0, {"row_count": len(df)}, f"{len(df)} rows")
