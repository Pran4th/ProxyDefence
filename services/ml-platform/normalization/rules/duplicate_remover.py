from __future__ import annotations

import time
from typing import Any

import pandas as pd

from backend.shared.logging_config import get_logger
from normalization.base import BaseNormalizer, NormalizationConfig, NormalizationResult, NormalizationRule
from normalization.registry import normalization_registry

logger = get_logger(__name__)


class DuplicateRemover(BaseNormalizer):
    def __init__(self, rule: NormalizationRule) -> None:
        super().__init__(rule)
        self.subset: list[str] | None = rule.config.get("subset")
        self.keep: str | bool = rule.config.get("keep", "first")
        self.ignore_case: bool = rule.config.get("ignore_case", False)
        self.fuzzy_threshold: int = rule.config.get("fuzzy_threshold", 0)

    async def normalize(
        self,
        df: pd.DataFrame,
        config: NormalizationConfig | None = None,
    ) -> tuple[pd.DataFrame, NormalizationResult]:
        config = config or NormalizationConfig()
        start = time.perf_counter()
        result = NormalizationResult(rule_name=self.rule.name)
        working = df.copy()

        before_count = len(working)
        subset_cols = self.subset or list(working.columns)
        subset_cols = [c for c in subset_cols if c in working.columns]

        if self.ignore_case:
            for col in subset_cols:
                if working[col].dtype == "object":
                    working[col] = working[col].astype(str).str.lower()

        working = working.drop_duplicates(subset=subset_cols, keep=self.keep)
        removed = before_count - len(working)
        result.records_affected = removed

        if config.report_changes:
            result.changes.append({"before": before_count, "after": len(working), "removed": removed})

        if self.fuzzy_threshold > 0 and not config.dry_run:
            fuzzy_removed = self._remove_fuzzy_duplicates(working, subset_cols)
            removed += fuzzy_removed
            result.records_affected = removed

        result.duration_ms = (time.perf_counter() - start) * 1000
        return working, result

    async def validate_rule(self) -> list[str]:
        errors: list[str] = []
        valid_keep = {"first", "last", False}
        if self.keep not in valid_keep:
            errors.append(f"invalid keep: {self.keep!r}, expected first/last/False")
        if not 0 <= self.fuzzy_threshold <= 100:
            errors.append("fuzzy_threshold must be between 0 and 100")
        return errors

    async def estimate_impact(self, df: pd.DataFrame) -> dict[str, Any]:
        subset_cols = self.subset or list(df.columns)
        subset_cols = [c for c in subset_cols if c in df.columns]
        count = len(df) - len(df.drop_duplicates(subset=subset_cols))
        return {
            "total_rows": len(df),
            "estimated_affected": count,
            "rule_name": self.rule.name,
            "rule_type": self.rule.rule_type,
        }

    def _remove_fuzzy_duplicates(self, df: pd.DataFrame, subset: list[str]) -> int:
        removed = 0
        keep_indices = set()
        for i in range(len(df)):
            if i in keep_indices:
                continue
            keep_indices.add(i)
            row_i = df.iloc[i]
            for j in range(i + 1, len(df)):
                if j in keep_indices:
                    continue
                row_j = df.iloc[j]
                similarity = self._compute_similarity(row_i, row_j, subset)
                if similarity >= self.fuzzy_threshold:
                    keep_indices.add(j)
                    logger.info("fuzzy_duplicate_removed", row_i=i, row_j=j, similarity=similarity)
                    removed += 1
        return removed

    def _compute_similarity(self, row_a: pd.Series, row_b: pd.Series, subset: list[str]) -> float:
        matches = 0
        total = 0
        for col in subset:
            va = str(row_a.get(col, "")).strip().lower()
            vb = str(row_b.get(col, "")).strip().lower()
            total += 1
            if va == vb:
                matches += 1
            elif va and vb and (va in vb or vb in va):
                matches += 0.5
        return (matches / total * 100) if total > 0 else 0.0


normalization_registry.register("duplicate", DuplicateRemover)
