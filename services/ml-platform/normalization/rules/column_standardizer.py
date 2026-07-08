from __future__ import annotations

import re
import time
from typing import Any

import pandas as pd

from backend.shared.logging_config import get_logger
from normalization.base import BaseNormalizer, NormalizationConfig, NormalizationResult, NormalizationRule
from normalization.registry import normalization_registry

logger = get_logger(__name__)

_SPECIAL_CHARS = re.compile(r"[^a-zA-Z0-9\s_-]")
_MULTI_UNDERSCORE = re.compile(r"_+")
_MULTI_DASH = re.compile(r"-+")
_LEADING_TRAILING = re.compile(r"^[_\s-]+|[_\s-]+$")
_CAMEL_SPLIT = re.compile(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


class ColumnStandardizer(BaseNormalizer):
    def __init__(self, rule: NormalizationRule) -> None:
        super().__init__(rule)
        self.naming: str = rule.config.get("naming", "snake_case")
        self.lowercase: bool = rule.config.get("lowercase", True)
        self.strip_special: bool = rule.config.get("strip_special", True)
        self.prefix: str = rule.config.get("prefix", "")
        self.suffix: str = rule.config.get("suffix", "")
        self.max_length: int = rule.config.get("max_length", 0)

    async def normalize(
        self,
        df: pd.DataFrame,
        config: NormalizationConfig | None = None,
    ) -> tuple[pd.DataFrame, NormalizationResult]:
        config = config or NormalizationConfig()
        start = time.perf_counter()
        result = NormalizationResult(rule_name=self.rule.name)
        working = df.copy()

        rename_map: dict[str, str] = {}
        seen: dict[str, int] = {}

        for col in working.columns:
            standardized = self._standardize_name(str(col))
            if standardized != col:
                rename_map[col] = standardized

        if rename_map:
            working = working.rename(columns=rename_map)
            result.records_affected = len(rename_map)

            working = self._resolve_duplicates(working, seen)

            if config.report_changes:
                result.changes.append({"renamed": rename_map})

        result.duration_ms = (time.perf_counter() - start) * 1000
        return working, result

    async def validate_rule(self) -> list[str]:
        errors: list[str] = []
        valid_naming = {"snake_case", "camelCase", "PascalCase", "kebab-case"}
        if self.naming not in valid_naming:
            errors.append(f"invalid naming: {self.naming!r}, expected one of {valid_naming}")
        return errors

    async def estimate_impact(self, df: pd.DataFrame) -> dict[str, Any]:
        changes = 0
        for col in df.columns:
            if self._standardize_name(str(col)) != col:
                changes += 1
        return {
            "total_rows": len(df),
            "estimated_affected": changes,
            "total_columns": len(df.columns),
            "rule_name": self.rule.name,
            "rule_type": self.rule.rule_type,
        }

    def _standardize_name(self, name: str) -> str:
        result = name.strip()

        if self.strip_special:
            result = _SPECIAL_CHARS.sub(" ", result)

        result = re.sub(r"\s+", "_", result.strip())

        if self.naming == "snake_case":
            words = _CAMEL_SPLIT.sub(" ", result).split()
            result = "_".join(words)
            if self.lowercase:
                result = result.lower()

        elif self.naming == "camelCase":
            words = _CAMEL_SPLIT.sub(" ", result).split()
            if words:
                result = words[0].lower() + "".join(w.capitalize() for w in words[1:])
            else:
                result = result.lower()

        elif self.naming == "PascalCase":
            words = _CAMEL_SPLIT.sub(" ", result).split()
            result = "".join(w.capitalize() for w in words)

        elif self.naming == "kebab-case":
            words = _CAMEL_SPLIT.sub(" ", result).split()
            result = "-".join(words)
            if self.lowercase:
                result = result.lower()

        result = _MULTI_UNDERSCORE.sub("_", result)
        result = _MULTI_DASH.sub("-", result)
        result = _LEADING_TRAILING.sub("", result)

        if self.prefix and not result.startswith(self.prefix):
            result = f"{self.prefix}{result}"
        if self.suffix and not result.endswith(self.suffix):
            result = f"{result}{self.suffix}"

        if self.max_length > 0 and len(result) > self.max_length:
            result = result[:self.max_length].rstrip("_-")

        return result if result else "unnamed"

    def _resolve_duplicates(self, df: pd.DataFrame, seen: dict[str, int]) -> pd.DataFrame:
        cols = list(df.columns)
        new_cols = []
        for col in cols:
            count = seen.get(col, 0)
            seen[col] = count + 1
            if count > 0:
                new_col = f"{col}_{count}"
                new_cols.append(new_col)
            else:
                new_cols.append(col)
        df.columns = new_cols
        return df


normalization_registry.register("column_std", ColumnStandardizer)
