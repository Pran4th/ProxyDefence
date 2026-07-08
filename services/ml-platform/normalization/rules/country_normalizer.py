from __future__ import annotations

import time
from difflib import get_close_matches
from typing import Any

import pandas as pd

from backend.shared.logging_config import get_logger
from normalization.base import BaseNormalizer, NormalizationConfig, NormalizationResult, NormalizationRule
from normalization.registry import normalization_registry

logger = get_logger(__name__)

_COUNTRY_MAP: dict[str, dict[str, str]] = {
    "united states": {"name": "United States", "alpha2": "US", "alpha3": "USA", "numeric": "840"},
    "usa": {"name": "United States", "alpha2": "US", "alpha3": "USA", "numeric": "840"},
    "us": {"name": "United States", "alpha2": "US", "alpha3": "USA", "numeric": "840"},
    "united states of america": {"name": "United States", "alpha2": "US", "alpha3": "USA", "numeric": "840"},
    "u.s.": {"name": "United States", "alpha2": "US", "alpha3": "USA", "numeric": "840"},
    "u.s.a": {"name": "United States", "alpha2": "US", "alpha3": "USA", "numeric": "840"},
    "united kingdom": {"name": "United Kingdom", "alpha2": "GB", "alpha3": "GBR", "numeric": "826"},
    "uk": {"name": "United Kingdom", "alpha2": "GB", "alpha3": "GBR", "numeric": "826"},
    "u.k.": {"name": "United Kingdom", "alpha2": "GB", "alpha3": "GBR", "numeric": "826"},
    "great britain": {"name": "United Kingdom", "alpha2": "GB", "alpha3": "GBR", "numeric": "826"},
    "england": {"name": "United Kingdom", "alpha2": "GB", "alpha3": "GBR", "numeric": "826"},
    "china": {"name": "China", "alpha2": "CN", "alpha3": "CHN", "numeric": "156"},
    "people's republic of china": {"name": "China", "alpha2": "CN", "alpha3": "CHN", "numeric": "156"},
    "russia": {"name": "Russia", "alpha2": "RU", "alpha3": "RUS", "numeric": "643"},
    "russian federation": {"name": "Russia", "alpha2": "RU", "alpha3": "RUS", "numeric": "643"},
    "uae": {"name": "United Arab Emirates", "alpha2": "AE", "alpha3": "ARE", "numeric": "784"},
    "united arab emirates": {"name": "United Arab Emirates", "alpha2": "AE", "alpha3": "ARE", "numeric": "784"},
    "saudi arabia": {"name": "Saudi Arabia", "alpha2": "SA", "alpha3": "SAU", "numeric": "682"},
    "iran": {"name": "Iran", "alpha2": "IR", "alpha3": "IRN", "numeric": "364"},
    "iraq": {"name": "Iraq", "alpha2": "IQ", "alpha3": "IRQ", "numeric": "368"},
    "kuwait": {"name": "Kuwait", "alpha2": "KW", "alpha3": "KWT", "numeric": "414"},
    "qatar": {"name": "Qatar", "alpha2": "QA", "alpha3": "QAT", "numeric": "634"},
    "venezuela": {"name": "Venezuela", "alpha2": "VE", "alpha3": "VEN", "numeric": "862"},
    "nigeria": {"name": "Nigeria", "alpha2": "NG", "alpha3": "NGA", "numeric": "566"},
    "angola": {"name": "Angola", "alpha2": "AO", "alpha3": "AGO", "numeric": "024"},
    "norway": {"name": "Norway", "alpha2": "NO", "alpha3": "NOR", "numeric": "578"},
    "canada": {"name": "Canada", "alpha2": "CA", "alpha3": "CAN", "numeric": "124"},
    "mexico": {"name": "Mexico", "alpha2": "MX", "alpha3": "MEX", "numeric": "484"},
    "brazil": {"name": "Brazil", "alpha2": "BR", "alpha3": "BRA", "numeric": "076"},
    "australia": {"name": "Australia", "alpha2": "AU", "alpha3": "AUS", "numeric": "036"},
    "india": {"name": "India", "alpha2": "IN", "alpha3": "IND", "numeric": "356"},
    "japan": {"name": "Japan", "alpha2": "JP", "alpha3": "JPN", "numeric": "392"},
    "south korea": {"name": "South Korea", "alpha2": "KR", "alpha3": "KOR", "numeric": "410"},
    "korea": {"name": "South Korea", "alpha2": "KR", "alpha3": "KOR", "numeric": "410"},
    "republic of korea": {"name": "South Korea", "alpha2": "KR", "alpha3": "KOR", "numeric": "410"},
    "germany": {"name": "Germany", "alpha2": "DE", "alpha3": "DEU", "numeric": "276"},
    "france": {"name": "France", "alpha2": "FR", "alpha3": "FRA", "numeric": "250"},
    "italy": {"name": "Italy", "alpha2": "IT", "alpha3": "ITA", "numeric": "380"},
    "spain": {"name": "Spain", "alpha2": "ES", "alpha3": "ESP", "numeric": "724"},
    "netherlands": {"name": "Netherlands", "alpha2": "NL", "alpha3": "NLD", "numeric": "528"},
    "türkiye": {"name": "Turkey", "alpha2": "TR", "alpha3": "TUR", "numeric": "792"},
    "turkey": {"name": "Turkey", "alpha2": "TR", "alpha3": "TUR", "numeric": "792"},
    "indonesia": {"name": "Indonesia", "alpha2": "ID", "alpha3": "IDN", "numeric": "360"},
    "malaysia": {"name": "Malaysia", "alpha2": "MY", "alpha3": "MYS", "numeric": "458"},
    "singapore": {"name": "Singapore", "alpha2": "SG", "alpha3": "SGP", "numeric": "702"},
    "thailand": {"name": "Thailand", "alpha2": "TH", "alpha3": "THA", "numeric": "764"},
    "vietnam": {"name": "Vietnam", "alpha2": "VN", "alpha3": "VNM", "numeric": "704"},
    "egypt": {"name": "Egypt", "alpha2": "EG", "alpha3": "EGY", "numeric": "818"},
    "algeria": {"name": "Algeria", "alpha2": "DZ", "alpha3": "DZA", "numeric": "012"},
    "libya": {"name": "Libya", "alpha2": "LY", "alpha3": "LBY", "numeric": "434"},
    "kazakhstan": {"name": "Kazakhstan", "alpha2": "KZ", "alpha3": "KAZ", "numeric": "398"},
    "oman": {"name": "Oman", "alpha2": "OM", "alpha3": "OMN", "numeric": "512"},
    "yemen": {"name": "Yemen", "alpha2": "YE", "alpha3": "YEM", "numeric": "887"},
    "syria": {"name": "Syria", "alpha2": "SY", "alpha3": "SYR", "numeric": "760"},
    "sudan": {"name": "Sudan", "alpha2": "SD", "alpha3": "SDN", "numeric": "729"},
    "south sudan": {"name": "South Sudan", "alpha2": "SS", "alpha3": "SSD", "numeric": "728"},
    "colombia": {"name": "Colombia", "alpha2": "CO", "alpha3": "COL", "numeric": "170"},
    "ecuador": {"name": "Ecuador", "alpha2": "EC", "alpha3": "ECU", "numeric": "218"},
    "argentina": {"name": "Argentina", "alpha2": "AR", "alpha3": "ARG", "numeric": "032"},
}

_KNOWN_NAMES = sorted(set(rec["name"].lower() for rec in _COUNTRY_MAP.values()))
_KNOWN_CODES_ALPHA2 = set(rec["alpha2"] for rec in _COUNTRY_MAP.values())
_KNOWN_CODES_ALPHA3 = set(rec["alpha3"] for rec in _COUNTRY_MAP.values())
_KNOWN_CODES_NUM = set(rec["numeric"] for rec in _COUNTRY_MAP.values())


class CountryNormalizer(BaseNormalizer):
    def __init__(self, rule: NormalizationRule) -> None:
        super().__init__(rule)
        self.target_format: str = rule.config.get("target_format", "name")
        self.fuzzy_match: bool = rule.config.get("fuzzy_match", False)

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
                if standardized is not None:
                    working.at[idx, col] = standardized
                    result.records_affected += 1
                    if config.report_changes:
                        result.changes.append({"row": idx, "column": col, "old": val, "new": standardized})

        result.duration_ms = (time.perf_counter() - start) * 1000
        return working, result

    async def validate_rule(self) -> list[str]:
        errors: list[str] = []
        valid_formats = {"name", "alpha2", "alpha3", "numeric"}
        if self.target_format not in valid_formats:
            errors.append(f"invalid target_format: {self.target_format!r}, expected one of {valid_formats}")
        return errors

    async def estimate_impact(self, df: pd.DataFrame) -> dict[str, Any]:
        count = 0
        for col in df.select_dtypes(include=["object", "string"]).columns:
            count += df[col].dropna().apply(
                lambda x: self._standardize(str(x)) is not None
            ).sum()
        return {
            "total_rows": len(df),
            "estimated_affected": int(count),
            "rule_name": self.rule.name,
            "rule_type": self.rule.rule_type,
        }

    def _standardize(self, value: str) -> str | None:
        key = value.strip().lower()
        direct = _COUNTRY_MAP.get(key)
        if direct is not None:
            return direct[self.target_format]

        if key.upper() in _KNOWN_CODES_ALPHA2:
            for rec in _COUNTRY_MAP.values():
                if rec["alpha2"] == key.upper():
                    return rec[self.target_format]

        if key.upper() in _KNOWN_CODES_ALPHA3:
            for rec in _COUNTRY_MAP.values():
                if rec["alpha3"] == key.upper():
                    return rec[self.target_format]

        if key in _KNOWN_CODES_NUM:
            for rec in _COUNTRY_MAP.values():
                if rec["numeric"] == key:
                    return rec[self.target_format]

        if self.fuzzy_match:
            matches = get_close_matches(key, _KNOWN_NAMES, n=1, cutoff=0.8)
            if matches:
                for rec in _COUNTRY_MAP.values():
                    if rec["name"].lower() == matches[0]:
                        return rec[self.target_format]

        return None


normalization_registry.register("country", CountryNormalizer)
