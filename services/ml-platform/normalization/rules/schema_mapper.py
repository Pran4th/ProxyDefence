from __future__ import annotations

import time
from typing import Any

import pandas as pd

from backend.shared.logging_config import get_logger
from normalization.base import BaseNormalizer, NormalizationConfig, NormalizationResult, NormalizationRule
from normalization.registry import normalization_registry

logger = get_logger(__name__)


class SchemaMapper(BaseNormalizer):
    def __init__(self, rule: NormalizationRule) -> None:
        super().__init__(rule)
        self.column_mapping: dict[str, str] = rule.config.get("column_mapping", {})
        self.drop_unmapped: bool = rule.config.get("drop_unmapped", False)
        self.strict: bool = rule.config.get("strict", False)

    async def normalize(
        self,
        df: pd.DataFrame,
        config: NormalizationConfig | None = None,
    ) -> tuple[pd.DataFrame, NormalizationResult]:
        config = config or NormalizationConfig()
        start = time.perf_counter()
        result = NormalizationResult(rule_name=self.rule.name)
        working = df.copy()

        if not self.column_mapping:
            result.errors.append("column_mapping is empty")
            return working, result

        reverse_map: dict[str, str] = {}
        for src, tgt in self.column_mapping.items():
            matched_src = self._find_column(working, src)
            if matched_src:
                reverse_map[matched_src] = tgt
            elif self.strict:
                result.errors.append(f"source column '{src}' not found in dataframe")
                return working, result
            else:
                logger.warning("schema_mapper_column_not_found", source=src)

        working = working.rename(columns=reverse_map)
        result.records_affected = len(working)

        if config.report_changes:
            result.changes.append({"renamed": reverse_map})

        if self.drop_unmapped:
            target_cols = set(self.column_mapping.values())
            cols_to_drop = [c for c in working.columns if c not in target_cols]
            if cols_to_drop:
                working = working.drop(columns=cols_to_drop)
                if config.report_changes:
                    result.changes.append({"dropped_unmapped": cols_to_drop})

        result.duration_ms = (time.perf_counter() - start) * 1000
        return working, result

    async def validate_rule(self) -> list[str]:
        errors: list[str] = []
        if not self.column_mapping:
            errors.append("column_mapping is required")
        return errors

    async def estimate_impact(self, df: pd.DataFrame) -> dict[str, Any]:
        found = 0
        for src in self.column_mapping:
            if self._find_column(df, src):
                found += 1
        return {
            "total_rows": len(df),
            "estimated_affected": len(df) if found > 0 else 0,
            "columns_mapped": found,
            "rule_name": self.rule.name,
            "rule_type": self.rule.rule_type,
        }

    def _find_column(self, df: pd.DataFrame, name: str) -> str | None:
        if name in df.columns:
            return name
        lower_map = {c.lower(): c for c in df.columns}
        return lower_map.get(name.lower())


normalization_registry.register("schema_map", SchemaMapper)
