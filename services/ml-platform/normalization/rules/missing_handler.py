from __future__ import annotations

import time
from typing import Any

import pandas as pd

from backend.shared.logging_config import get_logger
from normalization.base import BaseNormalizer, NormalizationConfig, NormalizationResult, NormalizationRule
from normalization.registry import normalization_registry

logger = get_logger(__name__)

_NULL_STRINGS: set[Any] = {"", "n/a", "na", "null", "none", "nan", "-", "--", "?", "undefined", "nil", "none", "nat"}


class MissingValueHandler(BaseNormalizer):
    def __init__(self, rule: NormalizationRule) -> None:
        super().__init__(rule)
        self.strategy: str = rule.config.get("strategy", "drop")
        self.fill_value: Any = rule.config.get("fill_value")
        self.max_missing_rate: float = rule.config.get("max_missing_rate", 1.0)
        self.columns: list[str] | None = rule.config.get("columns")

    async def normalize(
        self,
        df: pd.DataFrame,
        config: NormalizationConfig | None = None,
    ) -> tuple[pd.DataFrame, NormalizationResult]:
        config = config or NormalizationConfig()
        start = time.perf_counter()
        result = NormalizationResult(rule_name=self.rule.name)
        working = df.copy()

        working = self._unify_nulls(working)
        target_cols = self.columns or list(working.columns)
        target_cols = [c for c in target_cols if c in working.columns]

        # Filter columns exceeding max_missing_rate
        valid_cols = []
        for col in target_cols:
            missing_rate = working[col].isna().mean()
            if missing_rate > self.max_missing_rate:
                if self.strategy == "drop":
                    working = working.drop(columns=[col])
                    result.records_affected += 1
                    if config.report_changes:
                        result.changes.append({"action": "drop_column", "column": col, "missing_rate": missing_rate})
                else:
                    result.errors.append(f"column '{col}' has {missing_rate:.1%} missing (max: {self.max_missing_rate:.0%})")
                    if config.strict_mode:
                        return working, result
            else:
                valid_cols.append(col)

        before_missing = working[valid_cols].isna().sum().sum()

        if self.strategy == "drop":
            working = working.dropna(subset=valid_cols)
            result.records_affected += int(before_missing)

        elif self.strategy == "fill_constant":
            fill_val = self.fill_value if self.fill_value is not None else 0
            for col in valid_cols:
                if working[col].isna().any():
                    working[col] = working[col].fillna(fill_val)
                    result.records_affected += 1

        elif self.strategy == "fill_mean":
            for col in valid_cols:
                if working[col].dtype.kind in ("i", "f") and working[col].isna().any():
                    working[col] = working[col].fillna(working[col].mean())
                    result.records_affected += 1

        elif self.strategy == "fill_median":
            for col in valid_cols:
                if working[col].dtype.kind in ("i", "f") and working[col].isna().any():
                    working[col] = working[col].fillna(working[col].median())
                    result.records_affected += 1

        elif self.strategy == "fill_mode":
            for col in valid_cols:
                if working[col].isna().any():
                    mode_val = working[col].mode()
                    if not mode_val.empty:
                        working[col] = working[col].fillna(mode_val[0])
                        result.records_affected += 1

        elif self.strategy == "fill_forward":
            working[valid_cols] = working[valid_cols].ffill()
            result.records_affected += 1

        elif self.strategy == "fill_backward":
            working[valid_cols] = working[valid_cols].bfill()
            result.records_affected += 1

        elif self.strategy == "interpolate":
            for col in valid_cols:
                if working[col].dtype.kind in ("i", "f") and working[col].isna().any():
                    working[col] = working[col].interpolate()
                    result.records_affected += 1

        after_missing = working[valid_cols].isna().sum().sum()
        filled = int(before_missing - after_missing)

        if config.report_changes:
            result.changes.append({"strategy": self.strategy, "before_missing": int(before_missing), "after_missing": int(after_missing), "filled": filled})

        result.duration_ms = (time.perf_counter() - start) * 1000
        return working, result

    async def validate_rule(self) -> list[str]:
        errors: list[str] = []
        valid_strategies = {
            "drop", "fill_mean", "fill_median", "fill_mode",
            "fill_constant", "fill_forward", "fill_backward", "interpolate",
        }
        if self.strategy not in valid_strategies:
            errors.append(f"invalid strategy: {self.strategy!r}, expected one of {valid_strategies}")
        if self.strategy == "fill_constant" and self.fill_value is None:
            errors.append("fill_constant strategy requires fill_value")
        if not 0.0 <= self.max_missing_rate <= 1.0:
            errors.append("max_missing_rate must be between 0 and 1")
        return errors

    async def estimate_impact(self, df: pd.DataFrame) -> dict[str, Any]:
        target_cols = self.columns or list(df.columns)
        target_cols = [c for c in target_cols if c in df.columns]
        missing = df[target_cols].isna().sum().sum()
        return {
            "total_rows": len(df),
            "estimated_affected": int(missing),
            "rule_name": self.rule.name,
            "rule_type": self.rule.rule_type,
        }

    def _unify_nulls(self, df: pd.DataFrame) -> pd.DataFrame:
        for col in df.select_dtypes(include=["object", "string"]).columns:
            df[col] = df[col].apply(
                lambda x: None if isinstance(x, str) and x.strip().lower() in _NULL_STRINGS else x
            )
        return df


normalization_registry.register("missing", MissingValueHandler)
