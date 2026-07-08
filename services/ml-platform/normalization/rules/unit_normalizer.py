from __future__ import annotations

import re
import time
from typing import Any

import pandas as pd

from backend.shared.logging_config import get_logger
from normalization.base import BaseNormalizer, NormalizationConfig, NormalizationResult, NormalizationRule
from normalization.registry import normalization_registry

logger = get_logger(__name__)

_UNIT_CONVERSIONS: dict[str, dict[str, float]] = {
    "volume": {
        "barrel": 1.0,
        "barrels": 1.0,
        "bbl": 1.0,
        "mmbbl": 1e6,
        "mbbl": 1e3,
        "cubic_meter": 6.28981,
        "cubic_meters": 6.28981,
        "m3": 6.28981,
        "liter": 158.987,
        "liters": 158.987,
        "l": 158.987,
        "gallon": 42.0,
        "gallons": 42.0,
        "gal": 42.0,
        "bcm": 1e9 / 6.28981,
        "mcf": 1.0 / 5.61458,
        "mmcf": 1e6 / 5.61458,
    },
    "mass": {
        "ton": 1.0,
        "tons": 1.0,
        "t": 1.0,
        "metric_ton": 1.0,
        "metric_tons": 1.0,
        "kilogram": 1000.0,
        "kilograms": 1000.0,
        "kg": 1000.0,
        "pound": 2204.62,
        "pounds": 2204.62,
        "lb": 2204.62,
        "mt": 1.0,
    },
    "energy": {
        "btu": 1.0,
        "mmbtu": 1e6,
        "mwh": 0.000293297,
        "megawatt_hour": 0.000293297,
        "kwh": 0.293297,
        "kilowatt_hour": 0.293297,
        "joule": 1055055.0,
        "j": 1055055.0,
        "gj": 1055.055,
        "boe": 1.0 / 5.8,
        "toe": 1.0 / 39.68e6,
    },
    "length": {
        "meter": 1.0,
        "meters": 1.0,
        "m": 1.0,
        "kilometer": 0.001,
        "kilometers": 0.001,
        "km": 0.001,
        "mile": 0.000621371,
        "miles": 0.000621371,
        "foot": 3.28084,
        "feet": 3.28084,
        "ft": 3.28084,
    },
    "temperature": {
        "celsius": lambda c: (c * 9 / 5) + 32,
        "fahrenheit": lambda f: f,
        "kelvin": lambda k: (k - 273.15) * 9 / 5 + 32,
    },
    "pressure": {
        "bar": 1.0,
        "psi": 14.5038,
        "pascal": 100000.0,
        "pa": 100000.0,
        "kpa": 100.0,
        "mpa": 0.1,
        "atm": 0.986923,
    },
}

_UNIT_PATTERN = re.compile(r"^([\d.,]+)\s*([a-zA-Z_/]+)$")


class UnitNormalizer(BaseNormalizer):
    def __init__(self, rule: NormalizationRule) -> None:
        super().__init__(rule)
        self.source_unit: str = rule.config.get("source_unit", "")
        self.target_unit: str = rule.config.get("target_unit", "")
        self.unit_type: str = rule.config.get("unit_type", "volume")
        self.conversion_map: dict[str, float] | None = rule.config.get("conversion_map")

    async def normalize(
        self,
        df: pd.DataFrame,
        config: NormalizationConfig | None = None,
    ) -> tuple[pd.DataFrame, NormalizationResult]:
        config = config or NormalizationConfig()
        start = time.perf_counter()
        result = NormalizationResult(rule_name=self.rule.name)
        working = df.copy()

        conversions = self.unit_type_map()
        for col in working.select_dtypes(include=["object", "string"]).columns:
            for idx, val in enumerate(working[col]):
                if pd.isna(val):
                    continue
                val_str = str(val).strip()
                m = _UNIT_PATTERN.match(val_str)
                if not m:
                    continue
                num_str, unit = m.groups()
                num_str = num_str.replace(",", "")
                try:
                    value = float(num_str)
                except ValueError:
                    continue
                unit_lower = unit.lower().rstrip("s")
                target_factor = conversions.get(self.target_unit)
                source_factor = conversions.get(unit_lower) or conversions.get(unit)
                if target_factor is not None and source_factor is not None:
                    if callable(target_factor):
                        converted = target_factor(value)
                    else:
                        converted = value / source_factor * target_factor
                    working.at[idx, col] = converted
                    result.records_affected += 1
                    if config.report_changes:
                        result.changes.append({"row": idx, "column": col, "old": val, "new": converted})

        for col in working.select_dtypes(include=["object", "string"]).columns:
            try:
                working[col] = pd.to_numeric(working[col], errors="ignore")
            except (ValueError, TypeError):
                pass

        result.duration_ms = (time.perf_counter() - start) * 1000
        return working, result

    async def validate_rule(self) -> list[str]:
        errors: list[str] = []
        valid_types = {"volume", "mass", "energy", "length", "temperature", "pressure"}
        if self.unit_type not in valid_types:
            errors.append(f"invalid unit_type: {self.unit_type!r}, expected one of {valid_types}")
        conv = self.unit_type_map()
        if self.source_unit and self.source_unit not in conv:
            errors.append(f"source_unit {self.source_unit!r} not found in {self.unit_type} conversions")
        if self.target_unit and self.target_unit not in conv:
            errors.append(f"target_unit {self.target_unit!r} not found in {self.unit_type} conversions")
        return errors

    async def estimate_impact(self, df: pd.DataFrame) -> dict[str, Any]:
        count = 0
        for col in df.select_dtypes(include=["object", "string"]).columns:
            count += df[col].dropna().apply(lambda x: bool(_UNIT_PATTERN.match(str(x).strip()))).sum()
        return {
            "total_rows": len(df),
            "estimated_affected": int(count),
            "rule_name": self.rule.name,
            "rule_type": self.rule.rule_type,
        }

    def unit_type_map(self) -> dict[str, Any]:
        if self.conversion_map:
            return self.conversion_map
        return _UNIT_CONVERSIONS.get(self.unit_type, _UNIT_CONVERSIONS["volume"])


normalization_registry.register("unit", UnitNormalizer)
