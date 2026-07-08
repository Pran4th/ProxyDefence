from __future__ import annotations

import re
import time
from typing import Any

import pandas as pd

from backend.shared.logging_config import get_logger
from normalization.base import BaseNormalizer, NormalizationConfig, NormalizationResult, NormalizationRule
from normalization.registry import normalization_registry

logger = get_logger(__name__)

_ORG_ABBREVIATIONS: dict[str, str] = {
    "opec": "Organization of the Petroleum Exporting Countries",
    "iea": "International Energy Agency",
    "eia": "U.S. Energy Information Administration",
    "ira": "International Renewable Energy Agency",
    "iea": "International Energy Agency",
    "wto": "World Trade Organization",
    "imf": "International Monetary Fund",
    "world bank": "World Bank Group",
    "wb": "World Bank Group",
    "un": "United Nations",
    "nato": "North Atlantic Treaty Organization",
    "g7": "Group of Seven",
    "g20": "Group of Twenty",
    "gcc": "Gulf Cooperation Council",
    "oecd": "Organisation for Economic Co-operation and Development",
    "apec": "Asia-Pacific Economic Cooperation",
    "european union": "European Union",
    "eu": "European Union",
    "cia": "Central Intelligence Agency",
    "fbi": "Federal Bureau of Investigation",
    "nsa": "National Security Agency",
    "dod": "U.S. Department of Defense",
    "doe": "U.S. Department of Energy",
    "dos": "U.S. Department of State",
    "epa": "U.S. Environmental Protection Agency",
    "fema": "Federal Emergency Management Agency",
    "faa": "Federal Aviation Administration",
    "sec": "U.S. Securities and Exchange Commission",
    "fcc": "Federal Communications Commission",
    "ftc": "Federal Trade Commission",
    "ices": "International Council for the Exploration of the Sea",
    "imo": "International Maritime Organization",
    "who": "World Health Organization",
    "icj": "International Court of Justice",
    "icc": "International Criminal Court",
    "iaea": "International Atomic Energy Agency",
    "bse": "Bureau of Safety and Environmental Enforcement",
    "boem": "Bureau of Ocean Energy Management",
    "blm": "Bureau of Land Management",
    "usgs": "U.S. Geological Survey",
    "noaa": "National Oceanic and Atmospheric Administration",
    "ferc": "Federal Energy Regulatory Commission",
    "nrc": "Nuclear Regulatory Commission",
    "jod": "Joint Organisations Data Initiative",
    "jodi": "Joint Organisations Data Initiative",
}

_COMPANY_SUFFIXES: list[str] = [
    "inc", "inc.", "corp", "corp.", "corporation",
    "ltd", "ltd.", "limited", "llc", "llc.",
    "gmbh", "ag", "sa", "s.a.", "s.a",
    "plc", "plc.", "pvt", "pvt.", "private",
    "pty", "pty.", "co", "co.", "company",
    "group", "group.", "holdings", "holding",
    "bhd", "bhd.", "spa", "s.p.a.", "spa.",
    "nv", "n.v.", "bv", "b.v.",
]

_ORG_SUFFIX_PATTERN = re.compile(
    r"[\s,]*(" + "|".join(re.escape(s) for s in sorted(_COMPANY_SUFFIXES, key=len, reverse=True)) + r")[\s,]*$",
    re.IGNORECASE,
)
_MULTI_WS = re.compile(r"\s+")
_NON_ALPHA = re.compile(r"[^\w\s&-]")


class OrgNormalizer(BaseNormalizer):
    def __init__(self, rule: NormalizationRule) -> None:
        super().__init__(rule)
        self.abbreviation_map: dict[str, str] = rule.config.get("abbreviation_map", {})
        self.strip_suffixes: list[str] = rule.config.get("strip_suffixes", [])
        self.standardize_case: str = rule.config.get("standardize_case", "title")

    async def normalize(
        self,
        df: pd.DataFrame,
        config: NormalizationConfig | None = None,
    ) -> tuple[pd.DataFrame, NormalizationResult]:
        config = config or NormalizationConfig()
        start = time.perf_counter()
        result = NormalizationResult(rule_name=self.rule.name)
        working = df.copy()

        combined_map: dict[str, str] = {}
        combined_map.update(_ORG_ABBREVIATIONS)
        combined_map.update(self.abbreviation_map)

        for col in working.select_dtypes(include=["object", "string"]).columns:
            for idx, val in enumerate(working[col]):
                if pd.isna(val):
                    continue
                standardized = self._standardize(str(val), combined_map)
                if standardized != str(val).strip():
                    working.at[idx, col] = standardized
                    result.records_affected += 1
                    if config.report_changes:
                        result.changes.append({"row": idx, "column": col, "old": val, "new": standardized})

        result.duration_ms = (time.perf_counter() - start) * 1000
        return working, result

    async def validate_rule(self) -> list[str]:
        errors: list[str] = []
        valid_cases = {"lower", "upper", "title"}
        if self.standardize_case not in valid_cases:
            errors.append(f"invalid standardize_case: {self.standardize_case!r}, expected one of {valid_cases}")
        return errors

    async def estimate_impact(self, df: pd.DataFrame) -> dict[str, Any]:
        count = 0
        combined_map: dict[str, str] = {}
        combined_map.update(_ORG_ABBREVIATIONS)
        combined_map.update(self.abbreviation_map)
        for col in df.select_dtypes(include=["object", "string"]).columns:
            for val in df[col].dropna():
                if self._standardize(str(val), combined_map) != str(val).strip():
                    count += 1
        return {
            "total_rows": len(df),
            "estimated_affected": count,
            "rule_name": self.rule.name,
            "rule_type": self.rule.rule_type,
        }

    def _standardize(self, value: str, combined_map: dict[str, str]) -> str:
        result = value.strip()

        lower = result.lower()
        if lower in combined_map:
            result = combined_map[lower]
            return self._apply_case(result)

        result = _ORG_SUFFIX_PATTERN.sub("", result).strip()
        result = _MULTI_WS.sub(" ", result)
        result = _NON_ALPHA.sub(" ", result)
        result = _MULTI_WS.sub(" ", result).strip()

        result = self._apply_case(result)

        return result

    def _apply_case(self, value: str) -> str:
        if self.standardize_case == "lower":
            return value.lower()
        elif self.standardize_case == "upper":
            return value.upper()
        elif self.standardize_case == "title":
            return value.title()
        return value


normalization_registry.register("organization", OrgNormalizer)
