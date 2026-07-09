"""Adds a usd_price column to the global-fuel-prices dataset using World Bank's
official exchange rate indicator (PA.NUS.FCRF, annual average, LCU per USD) —
keyless, and a source already integrated this session for other indicators.

This is a real, honest tradeoff, not silently swept under the rug:
  - Rate resolution is ANNUAL AVERAGE, not daily/monthly — a coarser
    approximation than a true daily FX rate would give, particularly during
    high-volatility months (e.g. a currency crisis mid-year).
  - AFN (Afghanistan) and SOS (Somalia) have ZERO World Bank FX coverage —
    no unified official rate is tracked for either. Their usd_price is left
    null rather than fabricated from an unrelated proxy.
  - XOF (West African CFA Franc, a currency union) is resolved via Côte
    d'Ivoire's rate as a proxy — legitimate since XOF is a hard peg shared
    identically across all zone members.

Run from services/ml-platform/ with POSTGRES_* env set:
    .venv/Scripts/python.exe scripts/normalize_fuel_prices_usd.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO_ROOT = Path(__file__).resolve().parents[3]
FILES = [
    REPO_ROOT / "datasets" / "processed" / "commodity-prices" / "2025" / "commodity-prices.csv",
    REPO_ROOT / "datasets" / "processed" / "commodity-prices" / "2026" / "commodity-prices.csv",
]

# currency -> World Bank country ISO3 to query the FX rate for
# (XOF is a shared peg — Côte d'Ivoire is a representative zone member)
CURRENCY_TO_ISO3 = {
    "SSP": "SSD", "XOF": "CIV", "LBP": "LBN", "NGN": "NGA", "IQD": "IRQ",
    "GMD": "GMB", "LRD": "LBR", "SOS": "SOM", "AFN": "AFG", "LAK": "LAO", "AMD": "ARM",
}
NO_COVERAGE = {"SOM", "AFG"}  # confirmed zero World Bank data for these


def fetch_annual_rates(iso3_codes: list[str], start_year: int = 2020, end_year: int = 2026) -> dict[str, dict[int, float]]:
    codes = ";".join(c for c in iso3_codes if c not in NO_COVERAGE)
    url = f"https://api.worldbank.org/v2/country/{codes}/indicator/PA.NUS.FCRF"
    resp = requests.get(url, params={"format": "json", "per_page": 200, "date": f"{start_year}:{end_year}"}, timeout=60)
    data = resp.json()
    rows = data[1] if len(data) > 1 and data[1] else []

    rates: dict[str, dict[int, float]] = {}
    for r in rows:
        if r["value"] is None:
            continue
        iso3 = r["countryiso3code"]
        rates.setdefault(iso3, {})[int(r["date"])] = float(r["value"])
    return rates


def resolve_rate(rates: dict[int, float], year: int) -> float | None:
    if not rates:
        return None
    if year in rates:
        return rates[year]
    # fallback to the closest available year (annual-average approximation)
    closest = min(rates.keys(), key=lambda y: abs(y - year))
    return rates[closest]


def main() -> None:
    iso3_needed = sorted(set(CURRENCY_TO_ISO3.values()))
    print(f"fetching World Bank official exchange rates for: {iso3_needed}")
    rates_by_iso3 = fetch_annual_rates(iso3_needed)
    for iso3 in iso3_needed:
        years = sorted(rates_by_iso3.get(iso3, {}).keys())
        print(f"  {iso3}: {'no coverage' if not years else f'years {years[0]}-{years[-1]}'}")

    for path in FILES:
        df = pd.read_csv(path)
        attrs = df["attributes"].apply(ast.literal_eval)

        usd_prices = []
        for i, a in enumerate(attrs):
            currency = a.get("currency")
            price = a.get("price")
            year = int(str(df.iloc[i]["timestamp"])[:4]) if pd.notna(df.iloc[i]["timestamp"]) else None
            iso3 = CURRENCY_TO_ISO3.get(currency)

            if price is None or iso3 is None or iso3 in NO_COVERAGE or year is None:
                usd_prices.append(None)
                continue
            rate = resolve_rate(rates_by_iso3.get(iso3, {}), year)
            usd_prices.append(round(price / rate, 4) if rate else None)

        new_attrs = []
        for i, usd in enumerate(usd_prices):
            a = dict(attrs.iloc[i])
            a["price_usd"] = usd
            a["fx_rate_source"] = "world_bank_PA.NUS.FCRF_annual_avg" if usd is not None else None
            new_attrs.append(a)
        df["attributes"] = [str(a) for a in new_attrs]

        df.to_csv(path, index=False)
        covered = sum(1 for u in usd_prices if u is not None)
        print(f"{path.name}: {covered}/{len(df)} rows normalized to USD (rest: AFN/SOS with no WB coverage, or missing price)")


if __name__ == "__main__":
    main()
