from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import pytz

from backend.shared.logging_config import get_logger
from normalization.base import BaseNormalizer, NormalizationConfig, NormalizationResult, NormalizationRule
from normalization.registry import normalization_registry

logger = get_logger(__name__)

_TIMESTAMP_UNITS = {"s", "ms", "us", "ns"}


class TimestampNormalizer(BaseNormalizer):
    def __init__(self, rule: NormalizationRule) -> None:
        super().__init__(rule)
        self.source_timezone: str | None = rule.config.get("source_timezone")
        self.target_timezone: str = rule.config.get("target_timezone", "UTC")
        self.unit: str = rule.config.get("unit", "ms")
        self.format: str | None = rule.config.get("format")

    async def normalize(
        self,
        df: pd.DataFrame,
        config: NormalizationConfig | None = None,
    ) -> tuple[pd.DataFrame, NormalizationResult]:
        config = config or NormalizationConfig()
        start = time.perf_counter()
        result = NormalizationResult(rule_name=self.rule.name)
        working = df.copy()

        target_tz = pytz.timezone(self.target_timezone)

        for col in working.columns:
            if working[col].dtype.kind == "M":
                working[col] = self._convert_datetime_col(working[col], target_tz, result, config)
            elif working[col].dtype.kind in ("i", "f"):
                working[col] = self._convert_numeric_timestamp(working[col], target_tz, result, config)
            elif working[col].dtype == "object":
                working[col] = self._convert_object_timestamp(working[col], target_tz, result, config)

        result.duration_ms = (time.perf_counter() - start) * 1000
        return working, result

    async def validate_rule(self) -> list[str]:
        errors: list[str] = []
        if self.rule.config.get("unit", "ms") not in _TIMESTAMP_UNITS:
            errors.append(f"invalid unit: {self.rule.config.get('unit')!r}, expected s/ms/us/ns")
        if self.source_timezone:
            try:
                pytz.timezone(self.source_timezone)
            except Exception:
                errors.append(f"invalid source_timezone: {self.source_timezone!r}")
        try:
            pytz.timezone(self.target_timezone)
        except Exception:
            errors.append(f"invalid target_timezone: {self.target_timezone!r}")
        return errors

    async def estimate_impact(self, df: pd.DataFrame) -> dict[str, Any]:
        count = 0
        for col in df.columns:
            kind = df[col].dtype.kind
            if kind == "M":
                count += df[col].notna().sum()
            elif kind in ("i", "f"):
                count += df[col].notna().sum()
            elif kind == "O":
                count += df[col].dropna().apply(
                    lambda x: isinstance(x, (int, float, str)) and len(str(x).strip()) > 0
                ).sum()
        return {
            "total_rows": len(df),
            "estimated_affected": int(count),
            "rule_name": self.rule.name,
            "rule_type": self.rule.rule_type,
        }

    def _convert_datetime_col(
        self,
        series: pd.Series,
        target_tz: Any,
        result: NormalizationResult,
        config: NormalizationConfig,
    ) -> pd.Series:
        converted = pd.to_datetime(series, errors="coerce")
        before = converted.notna().sum()
        converted = converted.dt.tz_convert(target_tz) if converted.dt.tz is not None else converted.dt.tz_localize(target_tz)
        result.records_affected += int(before)
        return converted

    def _convert_numeric_timestamp(
        self,
        series: pd.Series,
        target_tz: Any,
        result: NormalizationResult,
        config: NormalizationConfig,
    ) -> pd.Series:
        converted = pd.to_datetime(series, unit=self.unit, errors="coerce")
        before = converted.notna().sum()
        converted = converted.dt.tz_localize(timezone.utc).dt.tz_convert(target_tz)
        result.records_affected += int(before)
        return converted

    def _convert_object_timestamp(
        self,
        series: pd.Series,
        target_tz: Any,
        result: NormalizationResult,
        config: NormalizationConfig,
    ) -> pd.Series:
        converted = pd.to_datetime(series, format=self.format, errors="coerce", utc=True)
        before = converted.notna().sum()
        converted = converted.dt.tz_convert(target_tz)
        result.records_affected += int(before)
        return converted


normalization_registry.register("timestamp", TimestampNormalizer)
