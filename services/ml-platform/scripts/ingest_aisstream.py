"""Streams real-time AIS (Automatic Identification System) vessel position
reports from aisstream.io for a fixed window, scoped to the maritime
chokepoints this platform already models risk for (digital_twin scenarios,
energy-service shipping_routes). Confirmed live: subscribing to a single
global bounding box produces a steady stream of PositionReport messages
within seconds of connecting.

Only PositionReport messages are requested (FilterMessageTypes), so vessel
static fields (name/type/dimensions) come from AIS MetaData only when the
network has cached them — ShipStaticData messages (a separate AIS message
type) are not subscribed to here, so those fields are frequently null. This
is a real, honest gap: a live position snapshot, not a full vessel registry.

Run from services/ml-platform/ with POSTGRES_* and AISSTREAM_API_KEY env set:
    .venv/Scripts/python.exe scripts/ingest_aisstream.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pandas as pd
import websockets

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_PATH = REPO_ROOT / "datasets" / "processed" / "ais-chokepoints" / "ais-chokepoints.csv"

API_KEY = os.environ.get("AISSTREAM_API_KEY")
WS_URI = "wss://stream.aisstream.io/v0/stream"

# [[lat_min, lon_min], [lat_max, lon_max]] per chokepoint, matching the scenarios
# already modeled in energy-service's digital_twin (Hormuz, Red Sea/Bab-el-Mandeb).
CHOKEPOINTS: dict[str, list[list[float]]] = {
    "strait_of_hormuz": [[24.5, 54.5], [27.0, 57.5]],
    "bab_el_mandeb": [[11.5, 42.5], [13.5, 44.0]],
    "suez_canal": [[29.7, 32.2], [31.5, 32.6]],
    "strait_of_malacca": [[1.0, 100.0], [6.0, 104.5]],
    "turkish_straits": [[40.0, 26.0], [41.5, 29.5]],
    "strait_of_gibraltar": [[35.7, -6.0], [36.2, -5.0]],
    "panama_canal": [[8.8, -80.1], [9.4, -79.4]],
}

COLLECT_SECONDS = 90
MAX_MESSAGES = 2000


def classify_chokepoint(lat: float, lon: float) -> str | None:
    for name, ((lat_min, lon_min), (lat_max, lon_max)) in CHOKEPOINTS.items():
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            return name
    return None


async def collect() -> list[dict]:
    bboxes = [[[lat_min, lon_min], [lat_max, lon_max]] for (lat_min, lon_min), (lat_max, lon_max) in CHOKEPOINTS.values()]
    messages: list[dict] = []

    async with websockets.connect(WS_URI) as ws:
        await ws.send(json.dumps({
            "APIKey": API_KEY,
            "BoundingBoxes": bboxes,
            "FilterMessageTypes": ["PositionReport"],
        }))

        loop = asyncio.get_event_loop()
        deadline = loop.time() + COLLECT_SECONDS
        while loop.time() < deadline and len(messages) < MAX_MESSAGES:
            remaining = deadline - loop.time()
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=max(remaining, 0.1))
            except asyncio.TimeoutError:
                break
            try:
                messages.append(json.loads(raw))
            except json.JSONDecodeError:
                continue

    return messages


def to_canonical(messages: list[dict]) -> pd.DataFrame:
    records = []
    for msg in messages:
        meta = msg.get("MetaData", {})
        report = msg.get("Message", {}).get("PositionReport", {})
        lat = meta.get("latitude")
        lon = meta.get("longitude")
        if lat is None or lon is None:
            continue

        chokepoint = classify_chokepoint(lat, lon)
        mmsi = meta.get("MMSI")
        timestamp = meta.get("time_utc", "")

        records.append({
            "entity_type": "vessel",
            "entity_id": str(mmsi),
            "entity_name": (meta.get("ShipName") or f"Vessel {mmsi}").strip(),
            "timestamp": timestamp,
            "timestamp_precision": "second",
            "latitude": lat,
            "longitude": lon,
            "location_name": chokepoint,
            "location_code": chokepoint,
            "attributes": json.dumps({
                "mmsi": mmsi,
                "speed_over_ground_knots": report.get("Sog"),
                "course_over_ground": report.get("Cog"),
                "true_heading": report.get("TrueHeading"),
                "navigational_status": report.get("NavigationalStatus"),
                "rate_of_turn": report.get("RateOfTurn"),
                "chokepoint": chokepoint,
            }, default=str),
            "relationships": json.dumps([]),
            "source": "aisstream",
            "source_record_id": f"{mmsi}_{timestamp}",
            "confidence": None,
            "metadata": json.dumps({"parser": "ingest_aisstream", "version": "1.0"}),
        })
    return pd.DataFrame(records)


def main() -> None:
    if not API_KEY:
        raise RuntimeError("AISSTREAM_API_KEY not set")

    print(f"streaming AIS position reports near {len(CHOKEPOINTS)} chokepoints for {COLLECT_SECONDS}s...")
    messages = asyncio.run(collect())
    print(f"received {len(messages)} raw AIS messages")

    canonical = to_canonical(messages)
    if canonical.empty:
        print("no vessel positions fell within the monitored chokepoint boxes this run; nothing written")
        return

    canonical = canonical.drop_duplicates(subset=["entity_id", "timestamp"])
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if OUT_PATH.exists():
        existing = pd.read_csv(OUT_PATH)
        combined = pd.concat([existing, canonical], ignore_index=True)
        combined = combined.drop_duplicates(subset=["entity_id", "timestamp"], keep="last")
    else:
        combined = canonical

    combined.to_csv(OUT_PATH, index=False)
    by_chokepoint = canonical["location_name"].value_counts().to_dict()
    print(f"wrote {len(canonical)} new vessel positions ({len(combined)} total accumulated) -> {OUT_PATH}")
    print(f"by chokepoint this run: {by_chokepoint}")


if __name__ == "__main__":
    main()
