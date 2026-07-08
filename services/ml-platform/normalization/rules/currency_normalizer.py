from __future__ import annotations

import re
import time
from typing import Any

import pandas as pd

from backend.shared.logging_config import get_logger
from normalization.base import BaseNormalizer, NormalizationConfig, NormalizationResult, NormalizationRule
from normalization.registry import normalization_registry

logger = get_logger(__name__)

_CURRENCY_SYMBOLS: dict[str, str] = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "₹": "INR",
    "¥": "JPY",
    "R$": "BRL",
    "R": "ZAR",
    "₽": "RUB",
    "₩": "KRW",
    "₪": "ILS",
    "₫": "VND",
    "₱": "PHP",
    "฿": "THB",
    "₴": "UAH",
    "₦": "NGN",
    "₡": "CRC",
    "₲": "PYG",
    "₵": "GHS",
    "₸": "KZT",
    "₺": "TRY",
}

_CURRENCY_SUFFIXES: dict[str, str] = {
    "USD": "USD",
    "EUR": "EUR",
    "GBP": "GBP",
    "INR": "INR",
    "JPY": "JPY",
    "BRL": "BRL",
    "ZAR": "ZAR",
    "RUB": "RUB",
    "KRW": "KRW",
    "CNY": "CNY",
    "CHF": "CHF",
    "CAD": "CAD",
    "AUD": "AUD",
    "NZD": "NZD",
    "SEK": "SEK",
    "NOK": "NOK",
    "DKK": "DKK",
    "MXN": "MXN",
    "SGD": "SGD",
    "HKD": "HKD",
    "TWD": "TWD",
}

_PAREN_NEGATIVE = re.compile(r"^\(([\d.,]+)\)$")
_CURRENCY_PREFIX = re.compile(r"^([R]{0,2}[\$€£₹¥₽₩₪₫₱฿₴₦₡₲₵₸₺])\s*([\d.,]+)$")
_CURRENCY_SUFFIX_RE = re.compile(r"^([\d.,]+)\s*([A-Z]{3})$")
_NUMERIC_CLEAN = re.compile(r"[^\d.,\-()]")


class CurrencyNormalizer(BaseNormalizer):
    def __init__(self, rule: NormalizationRule) -> None:
        super().__init__(rule)
        self.source_currency: str | None = rule.config.get("source_currency")
        self.target_currency: str = rule.config.get("target_currency", "USD")
        self.rate: float | None = rule.config.get("rate")
        self.decimal_separator: str = rule.config.get("decimal_separator", ".")
        self.thousand_separator: str = rule.config.get("thousand_separator", ",")

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
                numeric, currency = self._parse_currency(str(val))
                if numeric is None:
                    continue
                rate = self.rate or self._lookup_rate(currency or self.source_currency, self.target_currency)
                if rate is not None:
                    converted = numeric * rate
                    working.at[idx, col] = converted
                    result.records_affected += 1
                    if config.report_changes:
                        result.changes.append({"row": idx, "column": col, "old": val, "new": converted})
                else:
                    working.at[idx, col] = numeric
                    result.records_affected += 1

        for col in working.select_dtypes(include=["object", "string"]).columns:
            try:
                working[col] = pd.to_numeric(working[col], errors="ignore")
            except (ValueError, TypeError):
                pass

        result.duration_ms = (time.perf_counter() - start) * 1000
        return working, result

    async def validate_rule(self) -> list[str]:
        errors: list[str] = []
        if self.rule.config.get("decimal_separator", ".") not in (".", ","):
            errors.append("decimal_separator must be '.' or ','")
        if self.rule.config.get("thousand_separator", ",") not in (".", ",", "", " "):
            errors.append("thousand_separator must be one of: ., ,, '', ' '")
        if self.rule.config.get("decimal_separator") == self.rule.config.get("thousand_separator"):
            errors.append("decimal_separator and thousand_separator must differ")
        return errors

    async def estimate_impact(self, df: pd.DataFrame) -> dict[str, Any]:
        count = 0
        for col in df.select_dtypes(include=["object", "string"]).columns:
            for val in df[col].dropna():
                if self._parse_currency(str(val))[0] is not None:
                    count += 1
        return {
            "total_rows": len(df),
            "estimated_affected": count,
            "rule_name": self.rule.name,
            "rule_type": self.rule.rule_type,
        }

    def _parse_currency(self, value: str) -> tuple[float | None, str | None]:
        value = value.strip()
        if not value or value in ("N/A", "-", "--", "n/a"):
            return None, None

        m = _PAREN_NEGATIVE.match(value)
        if m:
            value = "-" + m.group(1)

        m = _CURRENCY_PREFIX.match(value)
        if m:
            symbol, num_part = m.groups()
            currency = _CURRENCY_SYMBOLS.get(symbol, symbol)
            return self._to_float(num_part), currency

        m = _CURRENCY_SUFFIX_RE.match(value)
        if m:
            num_part, suffix = m.groups()
            currency = _CURRENCY_SUFFIXES.get(suffix, suffix)
            return self._to_float(num_part), currency

        cleaned = _NUMERIC_CLEAN.sub("", value)
        if cleaned:
            return self._to_float(cleaned), None
        return None, None

    def _to_float(self, value: str) -> float | None:
        try:
            dec = self.decimal_separator
            thou = self.thousand_separator
            cleaned = value.replace(thou, "").replace(dec, ".")
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    def _lookup_rate(self, source: str | None, target: str) -> float | None:
        if source is None or source == target:
            return None
        return None


normalization_registry.register("currency", CurrencyNormalizer)
