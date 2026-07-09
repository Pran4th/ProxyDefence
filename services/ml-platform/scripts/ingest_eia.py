"""Fetches real U.S. crude oil stock levels from the EIA v2 API (keyed, weekly
petroleum/stoc/wstk series) — a genuinely new supply signal not covered by the
already-registered FRED brent/wti price series. Includes SPR-specific stock
levels (WCSSTUS1), directly relevant to the existing SPR drawdown models.

Note: EIAParser (data_acquisition/parser/sources/eia.py) expects the older EIA
v1 JSON shape (nested per-series `data` arrays). The real v2 API returns flat
records instead — confirmed live against api.eia.gov — so this script converts
directly to canonical schema rather than routing through that parser.

Run from services/ml-platform/ with POSTGRES_* and EIA_API_KEY env set:
    .venv/Scripts/python.exe scripts/ingest_eia.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_PATH = REPO_ROOT / "datasets" / "processed" / "eia-crude-stocks" / "eia-crude-stocks.csv"

EIA_API_KEY = os.environ.get("EIA_API_KEY")
BASE_URL = "https://api.eia.gov/v2/petroleum/stoc/wstk/data/"

# duoarea codes: national total + the 5 PADD regions (crude oil regional distribution
# is a real geopolitical signal — e.g. PADD3 = Gulf Coast, refinery-heavy).
DUOAREAS = ["NUS", "R10", "R20", "R30", "R40", "R50"]


def fetch_series(start: str = "2021-01-01") -> list[dict]:
    all_rows: list[dict] = []
    offset = 0
    length = 5000
    while True:
        params = {
            "api_key": EIA_API_KEY,
            "frequency": "weekly",
            "data[0]": "value",
            "facets[product][]": "EPC0",
            "facets[duoarea][]": DUOAREAS,
            "start": start,
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "offset": offset,
            "length": length,
        }
        resp = requests.get(BASE_URL, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()["response"]["data"]
        if not data:
            break
        all_rows.extend(data)
        if len(data) < length:
            break
        offset += length
    return all_rows


def to_canonical(rows: list[dict]) -> pd.DataFrame:
    records = []
    for r in rows:
        period = r.get("period", "")
        series_id = r.get("series", "")
        records.append({
            "entity_type": "petroleum_stock",
            "entity_id": f"{series_id}_{period}",
            "entity_name": r.get("series-description", series_id),
            "timestamp": period,
            "timestamp_precision": "week",
            "latitude": None,
            "longitude": None,
            "location_name": r.get("area-name"),
            "location_code": r.get("duoarea"),
            "attributes": json.dumps({
                "series_id": series_id,
                "series_description": r.get("series-description"),
                "product": r.get("product-name"),
                "process": r.get("process-name"),
                "value_thousand_barrels": float(r["value"]) if r.get("value") not in (None, "") else None,
                "units": r.get("units"),
                "duoarea": r.get("duoarea"),
            }, default=str),
            "relationships": json.dumps([]),
            "source": "eia",
            "source_record_id": f"{series_id}_{period}",
            "confidence": None,
            "metadata": json.dumps({"parser": "ingest_eia", "version": "1.0", "route": "petroleum/stoc/wstk"}),
        })
    return pd.DataFrame(records)


def main() -> None:
    if not EIA_API_KEY:
        raise RuntimeError("EIA_API_KEY not set")

    print("fetching EIA weekly crude oil stocks (national + PADD regions, 2021-present)...")
    rows = fetch_series()
    print(f"fetched {len(rows)} raw records")

    canonical = to_canonical(rows)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    canonical.to_csv(OUT_PATH, index=False)
    print(f"wrote {len(canonical)} canonical entity records -> {OUT_PATH}")


if __name__ == "__main__":
    main()
