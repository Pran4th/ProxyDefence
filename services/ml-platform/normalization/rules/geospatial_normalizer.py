from __future__ import annotations

import re
import time
from typing import Any

import pandas as pd

from backend.shared.logging_config import get_logger
from normalization.base import BaseNormalizer, NormalizationConfig, NormalizationResult, NormalizationRule
from normalization.registry import normalization_registry

logger = get_logger(__name__)

_DMS_PATTERN = re.compile(
    r"^([\d.]+)[°d\s]\s*(\d+)?['′\s]\s*(\d+(?:\.\d+)?)?[\"″\s]?\s*([NSEW])?\s*$",
    re.IGNORECASE,
)
_DECIMAL_PATTERN = re.compile(r"^[-+]?\d+(?:\.\d+)?\s*[°\s]?\s*([NSEW])?\s*$", re.IGNORECASE)


class GeospatialNormalizer(BaseNormalizer):
    def __init__(self, rule: NormalizationRule) -> None:
        super().__init__(rule)
        self.lat_col: str | None = rule.config.get("lat_col")
        self.lng_col: str | None = rule.config.get("lng_col")
        self.target_srid: int = rule.config.get("target_srid", 4326)
        self.validate_range: bool = rule.config.get("validate_range", True)
        self.reverse_parsing: bool = rule.config.get("reverse_parsing", False)

    async def normalize(
        self,
        df: pd.DataFrame,
        config: NormalizationConfig | None = None,
    ) -> tuple[pd.DataFrame, NormalizationResult]:
        config = config or NormalizationConfig()
        start = time.perf_counter()
        result = NormalizationResult(rule_name=self.rule.name)
        working = df.copy()

        lat_col = self.lat_col or self._detect_coord_column(working, "lat")
        lng_col = self.lng_col or self._detect_coord_column(working, "lng")

        if not lat_col or not lng_col:
            result.errors.append("could not detect lat/lng columns")
            return working, result

        for idx in working.index:
            lat_val = working.at[idx, lat_col]
            lng_val = working.at[idx, lng_col]

            if pd.isna(lat_val) or pd.isna(lng_val):
                continue

            lat_str = str(lat_val).strip()
            lng_str = str(lng_val).strip()

            lat_dec = self._to_decimal(lat_str, "lat")
            lng_dec = self._to_decimal(lng_str, "lng")

            if lat_dec is None or lng_dec is None:
                continue

            if self.reverse_parsing and self._detect_swap(lat_dec, lng_dec):
                lat_dec, lng_dec = lng_dec, lat_dec
                result.changes.append({"row": idx, "note": "lat/lng swapped"})

            if self.validate_range:
                if lat_dec < -90 or lat_dec > 90:
                    result.errors.append(f"row {idx}: latitude {lat_dec} out of range [-90, 90]")
                    if config.strict_mode:
                        continue
                if lng_dec < -180 or lng_dec > 180:
                    result.errors.append(f"row {idx}: longitude {lng_dec} out of range [-180, 180]")
                    if config.strict_mode:
                        continue

            working.at[idx, lat_col] = lat_dec
            working.at[idx, lng_col] = lng_dec
            result.records_affected += 1
            if config.report_changes:
                result.changes.append({"row": idx, "lat_old": lat_val, "lat_new": lat_dec, "lng_old": lng_val, "lng_new": lng_dec})

        result.duration_ms = (time.perf_counter() - start) * 1000
        return working, result

    async def validate_rule(self) -> list[str]:
        errors: list[str] = []
        return errors

    async def estimate_impact(self, df: pd.DataFrame) -> dict[str, Any]:
        lat_col = self.lat_col or self._detect_coord_column(df, "lat")
        lng_col = self.lng_col or self._detect_coord_column(df, "lng")
        if lat_col and lng_col:
            both_notna = df[lat_col].notna() & df[lng_col].notna()
            return {
                "total_rows": len(df),
                "estimated_affected": int(both_notna.sum()),
                "rule_name": self.rule.name,
                "rule_type": self.rule.rule_type,
            }
        return {
            "total_rows": len(df),
            "estimated_affected": 0,
            "rule_name": self.rule.name,
            "rule_type": self.rule.rule_type,
        }

    def _detect_coord_column(self, df: pd.DataFrame, kind: str) -> str | None:
        patterns = {
            "lat": ["latitude", "lat", "y"],
            "lng": ["longitude", "lng", "lon", "x"],
        }
        for col in df.columns:
            lower = col.lower().strip()
            for pattern in patterns.get(kind, []):
                if lower == pattern or lower.startswith(pattern):
                    return col
        return None

    def _to_decimal(self, value: str, coord_type: str) -> float | None:
        m = _DMS_PATTERN.match(value)
        if m:
            degrees = float(m.group(1))
            minutes = float(m.group(2) or 0)
            seconds = float(m.group(3) or 0)
            direction = (m.group(4) or "").strip().upper()
            decimal = degrees + minutes / 60.0 + seconds / 3600.0
            if direction in ("S", "W"):
                decimal = -decimal
            return decimal

        m = _DECIMAL_PATTERN.match(value)
        if m:
            decimal = float(re.sub(r"[^\d.\-+]", "", value))
            direction = (m.group(1) or "").strip().upper()
            if direction in ("S", "W") and decimal > 0:
                decimal = -decimal
            return decimal

        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _detect_swap(self, lat: float, lng: float) -> bool:
        if abs(lat) > 90 and abs(lng) <= 90:
            return True
        return False


normalization_registry.register("geospatial", GeospatialNormalizer)
