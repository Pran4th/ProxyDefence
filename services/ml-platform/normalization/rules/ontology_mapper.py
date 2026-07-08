from __future__ import annotations

import json
import os
import time
from typing import Any

import pandas as pd

from backend.shared.logging_config import get_logger
from normalization.base import BaseNormalizer, NormalizationConfig, NormalizationResult, NormalizationRule
from normalization.registry import normalization_registry

logger = get_logger(__name__)


class OntologyMapper(BaseNormalizer):
    def __init__(self, rule: NormalizationRule) -> None:
        super().__init__(rule)
        raw_mapping = rule.config.get("ontology_mapping", {})
        if isinstance(raw_mapping, str):
            if os.path.isfile(raw_mapping):
                with open(raw_mapping) as f:
                    self.ontology_mapping: dict[str, Any] = json.load(f)
            else:
                self.ontology_mapping = {}
                logger.error("ontology_file_not_found", path=raw_mapping)
        else:
            self.ontology_mapping = raw_mapping
        self.hierarchy: dict[str, Any] = rule.config.get("hierarchy", {})
        self.default_value: Any = rule.config.get("default_value")
        self.allow_partial: bool = rule.config.get("allow_partial", False)

    async def normalize(
        self,
        df: pd.DataFrame,
        config: NormalizationConfig | None = None,
    ) -> tuple[pd.DataFrame, NormalizationResult]:
        config = config or NormalizationConfig()
        start = time.perf_counter()
        result = NormalizationResult(rule_name=self.rule.name)
        working = df.copy()

        for col in working.select_dtypes(include=["object", "string", "category"]).columns:
            for idx, val in enumerate(working[col]):
                if pd.isna(val):
                    continue
                mapped = self._map_value(str(val).strip(), self.ontology_mapping)
                if mapped is not None:
                    if mapped != val:
                        working.at[idx, col] = mapped
                        result.records_affected += 1
                        if config.report_changes:
                            result.changes.append({"row": idx, "column": col, "old": val, "new": mapped})
                elif self.default_value is not None:
                    working.at[idx, col] = self.default_value
                    result.records_affected += 1
                elif config.strict_mode:
                    result.errors.append(f"row {idx}, col '{col}': unmapped value '{val}'")

        result.duration_ms = (time.perf_counter() - start) * 1000
        return working, result

    async def validate_rule(self) -> list[str]:
        errors: list[str] = []
        if not self.ontology_mapping:
            errors.append("ontology_mapping is required (dict or file path)")
        return errors

    async def estimate_impact(self, df: pd.DataFrame) -> dict[str, Any]:
        count = 0
        for col in df.select_dtypes(include=["object", "string", "category"]).columns:
            count += df[col].dropna().apply(
                lambda x: self._map_value(str(x).strip(), self.ontology_mapping) is not None
            ).sum()
        return {
            "total_rows": len(df),
            "estimated_affected": int(count),
            "rule_name": self.rule.name,
            "rule_type": self.rule.rule_type,
        }

    def _map_value(self, value: str, mapping: dict[str, Any]) -> Any | None:
        lower = value.lower()

        if lower in mapping:
            return mapping[lower]

        for src, tgt in mapping.items():
            if isinstance(src, str) and (lower.startswith(src) or src.startswith(lower)):
                if self.allow_partial:
                    return tgt

        if self.hierarchy:
            for parent, children in self.hierarchy.items():
                if isinstance(children, list):
                    if lower in [c.lower() for c in children]:
                        return parent
                elif isinstance(children, dict):
                    result = self._map_value(value, children)
                    if result is not None:
                        return parent

        return None


normalization_registry.register("ontology_map", OntologyMapper)
