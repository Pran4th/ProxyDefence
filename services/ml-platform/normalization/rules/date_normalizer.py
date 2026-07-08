from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import pandas as pd

from backend.shared.logging_config import get_logger
from normalization.base import BaseNormalizer, NormalizationConfig, NormalizationResult, NormalizationRule
from normalization.registry import normalization_registry

logger = get_logger(__name__)


DATE_FORMAT_PATTERNS: list[str] = [
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%Y/%m/%d",
    "%d-%m-%Y",
    "%m-%d-%Y",
    "%Y.%m.%d",
    "%d.%m.%Y",
    "%m.%d.%Y",
    "%Y%m%d",
    "%B %d, %Y",
    "%d %B %Y",
    "%b %d, %Y",
    "%d %b %Y",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S%z",
    "%Y",
]


class DateNormalizer(BaseNormalizer):
    def __init__(self, rule: NormalizationRule) -> None:
        super().__init__(rule)
        self.source_format: str | list[str] | None = rule.config.get("source_format")
        self.target_format: str = rule.config.get("target_format", "%Y-%m-%d")
        self.error_strategy: str = rule.config.get("error_strategy", "coerce")

    async def normalize(
        self,
        df: pd.DataFrame,
        config: NormalizationConfig | None = None,
    ) -> tuple[pd.DataFrame, NormalizationResult]:
        config = config or NormalizationConfig()
        start = time.perf_counter()
        result = NormalizationResult(rule_name=self.rule.name)
        working = df.copy()

        formats = (
            [self.source_format] if isinstance(self.source_format, str) else self.source_format or DATE_FORMAT_PATTERNS
        )

        for col in working.select_dtypes(include=["object", "string"]).columns:
            for idx, val in enumerate(working[col]):
                if pd.isna(val):
                    continue
                parsed = self._parse_date(str(val), formats)
                if parsed is not None:
                    try:
                        working.at[idx, col] = parsed.strftime(self.target_format)
                        result.records_affected += 1
                        if config.report_changes:
                            result.changes.append({"row": idx, "column": col, "old": val, "new": str(parsed)})
                    except (ValueError, TypeError) as e:
                        error_msg = f"row {idx}, col {col}: {e}"
                        result.errors.append(error_msg)
                        if self.error_strategy == "skip":
                            continue
                        elif self.error_strategy == "fill":
                            working.at[idx, col] = pd.NaT

        if not config.dry_run:
            for col in working.select_dtypes(include=["object", "string"]).columns:
                if working[col].apply(lambda x: self._parse_date(str(x), formats) is not None if pd.notna(x) else False).any():
                    working[col] = pd.to_datetime(working[col], errors="coerce", format=self.target_format)

        result.duration_ms = (time.perf_counter() - start) * 1000
        return working, result

    async def validate_rule(self) -> list[str]:
        errors: list[str] = []
        strategy = self.rule.config.get("error_strategy", "coerce")
        if strategy not in ("skip", "coerce", "fill"):
            errors.append(f"invalid error_strategy: {strategy!r}, expected skip/coerce/fill")
        target = self.rule.config.get("target_format")
        if target:
            try:
                datetime.now().strftime(str(target))
            except Exception as e:
                errors.append(f"invalid target_format: {e}")
        return errors

    async def estimate_impact(self, df: pd.DataFrame) -> dict[str, Any]:
        count = 0
        for col in df.select_dtypes(include=["object", "string"]).columns:
            for val in df[col].dropna():
                try:
                    if self._parse_date(str(val), DATE_FORMAT_PATTERNS):
                        count += 1
                except Exception:
                    continue
        return {
            "total_rows": len(df),
            "estimated_affected": count,
            "rule_name": self.rule.name,
            "rule_type": self.rule.rule_type,
        }

    def _parse_date(self, value: str, formats: list[str]) -> datetime | None:
        value = value.strip()
        if not value:
            return None
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        if value.isdigit() and len(value) == 4:
            return datetime(int(value), 1, 1)
        return None


normalization_registry.register("date", DateNormalizer)
