import re
from typing import Any, Callable

import numpy as np
import pandas as pd

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class QualityDimension:
    COMPLETENESS = "completeness"
    CONSISTENCY = "consistency"
    UNIQUENESS = "uniqueness"
    TIMELINESS = "timeliness"
    VALIDITY = "validity"
    INTEGRITY = "integrity"


_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
_URL_PATTERN = re.compile(
    r"^https?:\/\/(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&\/=]*)$"
)
_ISO_DATE_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?)?$"
)


class QualityScorer:
    def __init__(self):
        self._builtin_validators: dict[str, Callable] = {
            "numeric_range": self._validate_numeric_range,
            "string_length": self._validate_string_length,
            "email": self._validate_email,
            "url": self._validate_url,
            "iso_date": self._validate_iso_date,
        }

    async def score_completeness(self, df: pd.DataFrame) -> tuple[float, dict]:
        total_cells = df.size
        if total_cells == 0:
            return 1.0, {"per_column": {}, "total_missing": 0, "total_cells": 0}

        missing_counts = df.isnull().sum()
        total_missing = int(missing_counts.sum())
        per_column = {}
        for col in df.columns:
            col_missing = int(missing_counts[col])
            per_column[col] = {
                "missing": col_missing,
                "total": len(df),
                "rate": round(col_missing / len(df), 6),
                "completeness": round(1.0 - col_missing / len(df), 6),
            }

        overall = round(1.0 - total_missing / total_cells, 6)
        logger.info("completeness score: %s (%d missing / %d cells)", overall, total_missing, total_cells)
        return overall, {
            "per_column": per_column,
            "total_missing": total_missing,
            "total_cells": total_cells,
        }

    async def score_consistency(self, df: pd.DataFrame, schema: dict | None = None) -> tuple[float, dict]:
        if df.empty:
            return 1.0, {"inconsistencies": {}, "column_types": {}}

        issues = []
        column_types = {}
        inconsistencies = {}

        for col in df.columns:
            col_data = df[col].dropna()
            if len(col_data) == 0:
                column_types[col] = {"inferred": str(df[col].dtype), "consistent": True}
                continue

            inferred_dtype = str(df[col].dtype)
            column_types[col] = {"inferred": inferred_dtype}

            if np.issubdtype(df[col].dtype, np.number):
                non_numeric = col_data.apply(lambda x: not isinstance(x, (int, float, np.number))).sum()
                if non_numeric > 0:
                    rate = non_numeric / len(col_data)
                    inconsistencies[col] = {"type": "mixed_numeric", "rate": round(rate, 6)}
                    issues.append(f"{col}:{rate:.2%}_non_numeric")

            elif df[col].dtype == "object":
                inferred_types = col_data.apply(type).value_counts(normalize=True)
                if len(inferred_types) > 1:
                    dominant = inferred_types.index[0]
                    mixed_rate = 1.0 - inferred_types.iloc[0]
                    if mixed_rate > 0.01:
                        inconsistencies[col] = {
                            "type": "mixed_types",
                            "dominant": str(dominant),
                            "mixed_rate": round(mixed_rate, 6),
                            "type_distribution": {
                                str(k): round(float(v), 4) for k, v in inferred_types.items()
                            },
                        }
                        issues.append(f"{col}:{mixed_rate:.2%}_mixed_types")

                str_lengths = col_data.astype(str).str.len()
                length_std = str_lengths.std()
                if length_std > 50 and len(col_data) > 1:
                    inconsistencies[col] = {
                        "type": "inconsistent_length",
                        "std": round(float(length_std), 4),
                    }
                    issues.append(f"{col}:length_std={length_std:.1f}")

            column_types[col]["consistent"] = col not in inconsistencies

        if schema and "columns" in schema:
            expected_types = schema.get("dtypes", {})
            for col, expected in expected_types.items():
                if col in df.columns:
                    actual = str(df[col].dtype)
                    if actual != expected:
                        inconsistencies[col] = {
                            "type": "schema_mismatch",
                            "expected": expected,
                            "actual": actual,
                        }
                        issues.append(f"{col}:expected_{expected}_got_{actual}")

        n_columns = len(df.columns)
        n_inconsistent = len(inconsistencies)
        score = round(1.0 - n_inconsistent / n_columns, 6) if n_columns > 0 else 1.0

        logger.info("consistency score: %s (%d/%d columns inconsistent)", score, n_inconsistent, n_columns)
        return score, {
            "inconsistencies": inconsistencies,
            "column_types": column_types,
            "issues": issues,
        }

    async def score_uniqueness(self, df: pd.DataFrame, key_columns: list[str] | None = None) -> tuple[float, dict]:
        if df.empty:
            return 1.0, {"duplicate_rows": 0, "duplicate_rate": 0.0}

        total_rows = len(df)
        duplicate_rows = int(df.duplicated().sum())
        duplicate_rate = round(duplicate_rows / total_rows, 6) if total_rows > 0 else 0.0

        key_violations = {}
        if key_columns:
            valid_keys = [c for c in key_columns if c in df.columns]
            if valid_keys:
                key_dup_count = int(df.duplicated(subset=valid_keys, keep=False).sum())
                key_dup_rate = round(key_dup_count / total_rows, 6) if total_rows > 0 else 0.0
                key_violations = {
                    "key_columns": valid_keys,
                    "duplicate_rows": key_dup_count,
                    "duplicate_rate": key_dup_rate,
                }

        n_duplicates = duplicate_rows + key_violations.get("duplicate_rows", 0)
        score = round(1.0 - (n_duplicates / (total_rows * 2)) if total_rows > 0 else 1.0, 6)
        score = max(0.0, min(1.0, score))

        logger.info("uniqueness score: %s (%d duplicate rows)", score, duplicate_rows)
        return score, {
            "duplicate_rows": duplicate_rows,
            "duplicate_rate": duplicate_rate,
            "total_rows": total_rows,
            "key_violations": key_violations if key_violations else None,
        }

    async def score_timeliness(self, df: pd.DataFrame, date_column: str | None = None) -> tuple[float, dict]:
        if not date_column or date_column not in df.columns:
            return 1.0, {"note": "no date column provided", "date_column": date_column}

        col_data = df[date_column].dropna()
        if len(col_data) == 0:
            return 0.0, {"note": "date column is empty", "date_column": date_column}

        try:
            dates = pd.to_datetime(col_data)
        except Exception:
            return 0.5, {"note": "could not parse dates", "date_column": date_column}

        now = pd.Timestamp.now()
        date_min = dates.min()
        date_max = dates.max()
        date_range_days = (date_max - date_min).days

        sorted_dates = dates.sort_values()
        gaps = sorted_dates.diff().dropna()
        if len(gaps) > 0:
            max_gap_days = float(gaps.max().total_seconds() / 86400) if hasattr(gaps.max(), "total_seconds") else 0.0
            mean_gap_days = float(gaps.mean().total_seconds() / 86400) if hasattr(gaps.mean(), "total_seconds") else 0.0
            large_gaps = int((gaps > pd.Timedelta(days=7)).sum())
        else:
            max_gap_days = 0.0
            mean_gap_days = 0.0
            large_gaps = 0

        staleness_days = (now - date_max).days if hasattr(now - date_max, "days") else 0
        staleness_score = max(0.0, 1.0 - staleness_days / 365.0)

        coverage_score = min(1.0, date_range_days / max(1, (now - date_min).days)) if (now - date_min).days > 0 else 1.0
        gap_penalty = max(0.0, 1.0 - large_gaps * 0.1)

        score = round(staleness_score * 0.5 + coverage_score * 0.3 + gap_penalty * 0.2, 6)

        logger.info("timeliness score: %s (range=%d days, staleness=%d days)", score, date_range_days, staleness_days)
        return score, {
            "date_column": date_column,
            "date_range": {
                "min": str(date_min),
                "max": str(date_max),
                "range_days": date_range_days,
            },
            "staleness_days": staleness_days,
            "mean_gap_days": round(mean_gap_days, 4),
            "max_gap_days": round(max_gap_days, 4),
            "large_gaps_gt_7d": large_gaps,
            "total_records_with_date": len(dates),
        }

    async def score_validity(self, df: pd.DataFrame, rules: dict[str, Callable] | None = None) -> tuple[float, dict]:
        if df.empty:
            return 1.0, {"per_column_validity": {}, "builtin_rules_applied": [], "custom_rules": {}}

        per_column_validity = {}
        total_valid = 0
        total_checked = 0
        builtin_rules_applied = []
        custom_results = {}

        for col in df.columns:
            col_data = df[col].dropna()
            if len(col_data) == 0:
                per_column_validity[col] = {"valid_count": 0, "invalid_count": 0, "valid_rate": 1.0, "issues": []}
                continue

            col_lower = col.lower()
            valid_mask = pd.Series(True, index=col_data.index)
            issues = []

            if np.issubdtype(df[col].dtype, np.number):
                valid_mask &= self._validate_numeric_range(col_data)
                builtin_rules_applied.append("numeric_range")
            elif df[col].dtype == "object":
                valid_mask &= self._validate_string_length(col_data)
                builtin_rules_applied.append("string_length")

                if "email" in col_lower:
                    valid_mask &= col_data.astype(str).apply(self._validate_email)
                    builtin_rules_applied.append("email")
                if "url" in col_lower or "link" in col_lower or "website" in col_lower:
                    valid_mask &= col_data.astype(str).apply(self._validate_url)
                    builtin_rules_applied.append("url")
                if "date" in col_lower or "time" in col_lower or "timestamp" in col_lower:
                    valid_mask &= col_data.astype(str).apply(self._validate_iso_date)
                    builtin_rules_applied.append("iso_date")

            if rules and col in rules:
                validator = rules[col]
                custom_valid = col_data.apply(validator)
                custom_invalid = int((~custom_valid).sum())
                custom_results[col] = {"invalid": custom_invalid, "total": len(col_data)}
                valid_mask &= custom_valid

            n_valid = int(valid_mask.sum())
            n_invalid = int((~valid_mask).sum())
            valid_rate = round(n_valid / len(col_data), 6) if len(col_data) > 0 else 1.0

            per_column_validity[col] = {
                "valid_count": n_valid,
                "invalid_count": n_invalid,
                "valid_rate": valid_rate,
                "issues": issues,
            }
            total_valid += n_valid
            total_checked += len(col_data)

        overall = round(total_valid / total_checked, 6) if total_checked > 0 else 1.0
        builtin_rules_applied = list(set(builtin_rules_applied))

        logger.info("validity score: %s (%d/%d valid)", overall, total_valid, total_checked)
        return overall, {
            "per_column_validity": per_column_validity,
            "builtin_rules_applied": builtin_rules_applied,
            "custom_rules": custom_results if custom_results else None,
            "total_valid": total_valid,
            "total_checked": total_checked,
        }

    async def score_integrity(self, df: pd.DataFrame, reference_dfs: dict[str, pd.DataFrame] | None = None) -> tuple[float, dict]:
        if not reference_dfs:
            return 1.0, {"note": "no reference dataframes provided", "referential_violations": {}}

        violations = {}
        total_refs = 0
        total_violations = 0

        for ref_name, ref_df in reference_dfs.items():
            if ref_name not in df.columns:
                continue
            if ref_df.empty:
                violations[ref_name] = {"note": "empty reference", "violation_count": len(df[ref_name].dropna())}
                total_violations += len(df[ref_name].dropna())
                total_refs += 1
                continue

            fk_values = df[ref_name].dropna()
            pk_column = ref_df.columns[0]
            pk_set = set(ref_df[pk_column].dropna().unique())

            if len(pk_set) == 0:
                violations[ref_name] = {
                    "note": "empty reference key set",
                    "violation_count": len(fk_values),
                    "referenced_table": ref_name,
                    "referenced_column": pk_column,
                }
                total_violations += len(fk_values)
                total_refs += 1
                continue

            orphan_values = fk_values[~fk_values.isin(pk_set)]
            n_violations = len(orphan_values)
            violation_rate = round(n_violations / len(fk_values), 6) if len(fk_values) > 0 else 0.0

            if n_violations > 0:
                violations[ref_name] = {
                    "referenced_table": ref_name,
                    "referenced_column": pk_column,
                    "violation_count": n_violations,
                    "violation_rate": violation_rate,
                    "sample_violations": [str(v) for v in orphan_values.head(10).tolist()],
                }
                total_violations += n_violations

            total_refs += 1

        total_checked = total_refs if total_refs > 0 else 1
        score = round(1.0 - (total_violations / (total_checked * 100)), 6) if total_checked > 0 else 1.0
        score = max(0.0, min(1.0, score))

        logger.info("integrity score: %s (%d violations across %d refs)", score, total_violations, total_refs)
        return score, {
            "referential_violations": violations if violations else None,
            "total_references_checked": total_refs,
            "total_violations": total_violations,
        }

    async def overall_score(self, dimension_scores: dict[str, float], weights: dict[str, float] | None = None) -> float:
        default_weights = {
            QualityDimension.COMPLETENESS: 0.25,
            QualityDimension.CONSISTENCY: 0.15,
            QualityDimension.UNIQUENESS: 0.15,
            QualityDimension.TIMELINESS: 0.15,
            QualityDimension.VALIDITY: 0.2,
            QualityDimension.INTEGRITY: 0.1,
        }
        w = weights or default_weights

        total_weight = sum(w.get(dim, 0) for dim in dimension_scores)
        if total_weight == 0:
            return 0.0

        weighted_sum = sum(dimension_scores.get(dim, 0) * w.get(dim, 0) for dim in dimension_scores)
        return round(weighted_sum / total_weight, 6)

    async def score_all(self, df: pd.DataFrame, **kwargs) -> dict[str, Any]:
        completeness_score, completeness_detail = await self.score_completeness(df)
        consistency_score, consistency_detail = await self.score_consistency(df, kwargs.get("schema"))
        uniqueness_score, uniqueness_detail = await self.score_uniqueness(df, kwargs.get("key_columns"))
        timeliness_score, timeliness_detail = await self.score_timeliness(df, kwargs.get("date_column"))
        validity_score, validity_detail = await self.score_validity(df, kwargs.get("rules"))
        integrity_score, integrity_detail = await self.score_integrity(df, kwargs.get("reference_dfs"))

        dimension_scores = {
            QualityDimension.COMPLETENESS: completeness_score,
            QualityDimension.CONSISTENCY: consistency_score,
            QualityDimension.UNIQUENESS: uniqueness_score,
            QualityDimension.TIMELINESS: timeliness_score,
            QualityDimension.VALIDITY: validity_score,
            QualityDimension.INTEGRITY: integrity_score,
        }

        overall = await self.overall_score(dimension_scores, kwargs.get("weights"))

        return {
            "dimension_scores": dimension_scores,
            "dimension_details": {
                QualityDimension.COMPLETENESS: completeness_detail,
                QualityDimension.CONSISTENCY: consistency_detail,
                QualityDimension.UNIQUENESS: uniqueness_detail,
                QualityDimension.TIMELINESS: timeliness_detail,
                QualityDimension.VALIDITY: validity_detail,
                QualityDimension.INTEGRITY: integrity_detail,
            },
            "overall_score": overall,
        }

    # ── Built-in validators ──────────────────────────────────────

    def _validate_numeric_range(self, series: pd.Series) -> pd.Series:
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            return pd.Series(True, index=series.index)
        lower = q1 - 3.0 * iqr
        upper = q3 + 3.0 * iqr
        return (series >= lower) & (series <= upper)

    @staticmethod
    def _validate_string_length(series: pd.Series) -> pd.Series:
        lengths = series.astype(str).str.len()
        return lengths <= 10000

    @staticmethod
    def _validate_email(value: Any) -> bool:
        if not isinstance(value, str):
            return False
        return bool(_EMAIL_PATTERN.match(value))

    @staticmethod
    def _validate_url(value: Any) -> bool:
        if not isinstance(value, str):
            return False
        return bool(_URL_PATTERN.match(value))

    @staticmethod
    def _validate_iso_date(value: Any) -> bool:
        if not isinstance(value, str):
            return False
        return bool(_ISO_DATE_PATTERN.match(value))
