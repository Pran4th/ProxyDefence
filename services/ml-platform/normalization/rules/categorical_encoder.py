from __future__ import annotations

import time
from typing import Any

import pandas as pd

from backend.shared.logging_config import get_logger
from normalization.base import BaseNormalizer, NormalizationConfig, NormalizationResult, NormalizationRule
from normalization.registry import normalization_registry

logger = get_logger(__name__)


class CategoricalEncoder(BaseNormalizer):
    def __init__(self, rule: NormalizationRule) -> None:
        super().__init__(rule)
        self.encoding: str = rule.config.get("encoding", "label")
        self.category_order: list[str] | None = rule.config.get("category_order")
        self.handle_unknown: str = rule.config.get("handle_unknown", "error")

    async def normalize(
        self,
        df: pd.DataFrame,
        config: NormalizationConfig | None = None,
    ) -> tuple[pd.DataFrame, NormalizationResult]:
        config = config or NormalizationConfig()
        start = time.perf_counter()
        result = NormalizationResult(rule_name=self.rule.name)
        working = df.copy()

        for col in working.select_dtypes(include=["object", "category", "string"]).columns:
            if col in working.select_dtypes(include=["number"]).columns:
                continue

            cleaned = working[col].astype(str).str.strip().str.lower()

            if self.encoding == "label":
                categories = self.category_order or sorted(cleaned.unique())
                cat_to_int = {cat: i for i, cat in enumerate(categories)}
                encoded = []
                for val in cleaned:
                    if val in cat_to_int:
                        encoded.append(cat_to_int[val])
                    elif self.handle_unknown == "ignore":
                        encoded.append(-1)
                    elif self.handle_unknown == "value":
                        encoded.append(len(categories))
                    else:
                        raise ValueError(f"unknown category '{val}' in column '{col}'")
                working[col] = encoded
                result.records_affected += len(working)

            elif self.encoding == "onehot":
                categories = self.category_order or sorted(cleaned.unique())
                for cat in categories:
                    working[f"{col}_{cat}"] = (cleaned == cat).astype(int)
                working = working.drop(columns=[col])
                result.records_affected += len(working)

            elif self.encoding == "frequency":
                freq = cleaned.value_counts()
                working[col] = cleaned.map(freq).astype(float)
                result.records_affected += len(working)

            elif self.encoding == "ordinal":
                if not self.category_order:
                    result.errors.append(f"ordinal encoding requires category_order for column '{col}'")
                    continue
                cat_to_ord = {cat.lower().strip(): i for i, cat in enumerate(self.category_order)}
                encoded = []
                for val in cleaned:
                    if val in cat_to_ord:
                        encoded.append(cat_to_ord[val])
                    elif self.handle_unknown == "ignore":
                        encoded.append(-1)
                    elif self.handle_unknown == "value":
                        encoded.append(len(self.category_order))
                    else:
                        raise ValueError(f"unknown category '{val}' in column '{col}'")
                working[col] = encoded
                result.records_affected += len(working)

        result.duration_ms = (time.perf_counter() - start) * 1000
        return working, result

    async def validate_rule(self) -> list[str]:
        errors: list[str] = []
        valid_encodings = {"label", "onehot", "frequency", "ordinal"}
        if self.encoding not in valid_encodings:
            errors.append(f"invalid encoding: {self.encoding!r}, expected one of {valid_encodings}")
        valid_unknown = {"error", "ignore", "value"}
        if self.handle_unknown not in valid_unknown:
            errors.append(f"invalid handle_unknown: {self.handle_unknown!r}, expected one of {valid_unknown}")
        if self.encoding == "ordinal" and not self.category_order:
            errors.append("ordinal encoding requires category_order")
        return errors

    async def estimate_impact(self, df: pd.DataFrame) -> dict[str, Any]:
        count = 0
        for col in df.select_dtypes(include=["object", "category", "string"]).columns:
            count += df[col].notna().sum()
        return {
            "total_rows": len(df),
            "estimated_affected": int(count),
            "rule_name": self.rule.name,
            "rule_type": self.rule.rule_type,
        }


normalization_registry.register("categorical", CategoricalEncoder)
