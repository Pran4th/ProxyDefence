"""Fetches the current Brent spot price + 2-month forward predictions from
crudepriceapi.com's /latest endpoint. Only /latest is reachable on the free
tier (recent_prices/past_week/etc all 404 without a paid plan, confirmed live)
and the tier is capped at 100 requests/month, so this makes exactly one call
per run rather than polling.

Run from services/ml-platform/ with POSTGRES_* and CRUDE_PRICE_API_KEY env set:
    .venv/Scripts/python.exe scripts/ingest_crude_price_api.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_PATH = REPO_ROOT / "datasets" / "processed" / "crude-price-api" / "crude-price-api.csv"

API_KEY = os.environ.get("CRUDE_PRICE_API_KEY")
URL = "https://www.crudepriceapi.com/api/prices/latest"


def fetch() -> dict:
    resp = requests.get(URL, headers={"Authorization": f"Bearer {API_KEY}"}, timeout=15)
    resp.raise_for_status()
    return resp.json()["data"]


def to_canonical(data: dict) -> pd.DataFrame:
    records = []
    fetched_at = data.get("created_at", datetime.now(timezone.utc).isoformat())

    records.append({
        "entity_type": "commodity_price",
        "entity_id": f"BRENT_SPOT_{fetched_at}",
        "entity_name": "Brent Crude Spot Price",
        "timestamp": fetched_at,
        "timestamp_precision": "second",
        "latitude": None,
        "longitude": None,
        "location_name": None,
        "location_code": None,
        "attributes": json.dumps({
            "commodity": "brent_crude",
            "price": float(data["price"]),
            "currency": data.get("currency", "USD"),
            "code": data.get("code"),
            "type": "spot_price",
        }, default=str),
        "relationships": json.dumps([]),
        "source": "crude_price_api",
        "source_record_id": f"BRENT_SPOT_{fetched_at}",
        "confidence": None,
        "metadata": json.dumps({"parser": "ingest_crude_price_api", "version": "1.0"}),
    })

    for pred in data.get("next_two_months_predictions", []):
        period = pred.get("period", "")
        records.append({
            "entity_type": "commodity_price_forecast",
            "entity_id": f"{pred.get('seriesId', 'BRENT')}_{period}",
            "entity_name": pred.get("seriesDescription", "Brent crude oil forecast"),
            "timestamp": period,
            "timestamp_precision": "month",
            "latitude": None,
            "longitude": None,
            "location_name": None,
            "location_code": None,
            "attributes": json.dumps({
                "commodity": "brent_crude",
                "series_id": pred.get("seriesId"),
                "predicted_value": float(pred["value"]) if pred.get("value") not in (None, "") else None,
                "unit": pred.get("unit"),
                "type": "forecast",
                "predicted_at": fetched_at,
            }, default=str),
            "relationships": json.dumps([{"type": "forecast_of", "target_id": f"BRENT_SPOT_{fetched_at}"}]),
            "source": "crude_price_api",
            "source_record_id": f"{pred.get('seriesId', 'BRENT')}_{period}",
            "confidence": None,
            "metadata": json.dumps({"parser": "ingest_crude_price_api", "version": "1.0"}),
        })

    return pd.DataFrame(records)


def main() -> None:
    if not API_KEY:
        raise RuntimeError("CRUDE_PRICE_API_KEY not set")

    print("fetching current Brent spot price + forward predictions from crudepriceapi.com...")
    data = fetch()
    print(f"spot price: ${data['price']} {data.get('currency', 'USD')} as of {data.get('created_at')}")

    canonical = to_canonical(data)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if OUT_PATH.exists():
        existing = pd.read_csv(OUT_PATH)
        combined = pd.concat([existing, canonical], ignore_index=True)
        combined = combined.drop_duplicates(subset=["entity_id"], keep="last")
    else:
        combined = canonical

    combined.to_csv(OUT_PATH, index=False)
    print(f"wrote {len(canonical)} new records ({len(combined)} total accumulated) -> {OUT_PATH}")


if __name__ == "__main__":
    main()
