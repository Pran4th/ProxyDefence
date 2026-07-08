from __future__ import annotations

import re
import time
import uuid
from typing import Any

import pandas as pd

from backend.shared.logging_config import get_logger
from normalization.base import BaseNormalizer, NormalizationConfig, NormalizationResult, NormalizationRule
from normalization.registry import normalization_registry

logger = get_logger(__name__)

_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)
_PREFIX_PATTERN = re.compile(r"^([A-Za-z]+[-_]?)(\d+)$")
_WHITESPACE = re.compile(r"\s+")


class EntityIDNormalizer(BaseNormalizer):
    def __init__(self, rule: NormalizationRule) -> None:
        super().__init__(rule)
        self.id_format: str = rule.config.get("id_format", "uuid")
        self.prefix: str = rule.config.get("prefix", "")
        self.padding: int = rule.config.get("padding", 0)
        self.case: str = rule.config.get("case", "lower")

    async def normalize(
        self,
        df: pd.DataFrame,
        config: NormalizationConfig | None = None,
    ) -> tuple[pd.DataFrame, NormalizationResult]:
        config = config or NormalizationConfig()
        start = time.perf_counter()
        result = NormalizationResult(rule_name=self.rule.name)
        working = df.copy()

        for col in working.select_dtypes(include=["object", "string"]).columns:
            for idx, val in enumerate(working[col]):
                if pd.isna(val):
                    continue
                standardized = self._standardize(str(val))
                if standardized != str(val).strip():
                    working.at[idx, col] = standardized
                    result.records_affected += 1
                    if config.report_changes:
                        result.changes.append({"row": idx, "column": col, "old": val, "new": standardized})

        result.duration_ms = (time.perf_counter() - start) * 1000
        return working, result

    async def validate_rule(self) -> list[str]:
        errors: list[str] = []
        valid_formats = {"uuid", "slug", "numeric", "alphanumeric"}
        if self.id_format not in valid_formats:
            errors.append(f"invalid id_format: {self.id_format!r}, expected one of {valid_formats}")
        valid_cases = {"upper", "lower"}
        if self.case not in valid_cases:
            errors.append(f"invalid case: {self.case!r}, expected upper or lower")
        if self.padding < 0:
            errors.append("padding must be non-negative")
        return errors

    async def estimate_impact(self, df: pd.DataFrame) -> dict[str, Any]:
        count = 0
        for col in df.select_dtypes(include=["object", "string"]).columns:
            count += df[col].dropna().apply(lambda x: self._standardize(str(x)) != str(x).strip()).sum()
        return {
            "total_rows": len(df),
            "estimated_affected": int(count),
            "rule_name": self.rule.name,
            "rule_type": self.rule.rule_type,
        }

    def _standardize(self, value: str) -> str:
        result = value.strip()
        result = _WHITESPACE.sub("", result)

        if self.id_format == "uuid":
            if _UUID_PATTERN.match(result):
                return result.lower() if self.case == "lower" else result.upper()
            try:
                parsed = uuid.UUID(result)
                formatted = str(parsed)
                return formatted.lower() if self.case == "lower" else formatted.upper()
            except (ValueError, AttributeError):
                return value.strip()

        if self.id_format == "slug":
            result = result.lower().replace(" ", "-")
            result = re.sub(r"[^a-z0-9_-]", "", result)
            if self.prefix and not result.startswith(self.prefix):
                result = f"{self.prefix}{result}"
            return result

        if self.id_format == "numeric":
            result = re.sub(r"[^0-9]", "", result)
            if self.padding > 0:
                result = result.zfill(self.padding)
            if self.prefix:
                result = f"{self.prefix}{result}"
            return result

        if self.id_format == "alphanumeric":
            result = re.sub(r"[^a-zA-Z0-9]", "", result)
            if self.case == "upper":
                result = result.upper()
            else:
                result = result.lower()
            if self.prefix and not result.startswith(self.prefix):
                result = f"{self.prefix}{result}"
            return result

        return value.strip()


normalization_registry.register("entity_id", EntityIDNormalizer)
