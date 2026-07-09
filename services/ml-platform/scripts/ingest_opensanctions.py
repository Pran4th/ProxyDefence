"""Downloads OpenSanctions' free, keyless bulk export (targets.simple.csv,
aggregates OFAC/EU/UN/UK/and 100+ other sanctions & PEP lists into one
schema) and filters to entities relevant to this app's scenarios — full
1.3M-row global PEP/sanctions coverage isn't useful for a hackathon dataset,
so this keeps only rows whose topic/country/dataset signals overlap Iran,
Russia, the energy sector, or maritime/shipping.

The download path is date-stamped and rotates every ~6h, so the current URL
is resolved dynamically from the stable index.json each run (never hardcode
the artifact path).

Run from services/ml-platform/ with POSTGRES_* env set:
    .venv/Scripts/python.exe scripts/ingest_opensanctions.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_PATH = REPO_ROOT / "datasets" / "raw" / "sanctions" / "opensanctions_targets.csv"
OUT_PATH = REPO_ROOT / "datasets" / "processed" / "opensanctions" / "opensanctions-filtered.csv"

INDEX_URL = "https://data.opensanctions.org/datasets/latest/default/index.json"

RELEVANT_COUNTRIES = {"ir", "ru", "sy", "kp", "by", "ae", "sa", "iq", "in"}  # Iran, Russia, Syria, N.Korea, Belarus, UAE, Saudi, Iraq, India
RELEVANT_SCHEMA = {"Person", "Company", "Organization", "Vessel", "LegalEntity"}


def resolve_current_url() -> str:
    index = requests.get(INDEX_URL, timeout=30).json()
    for resource in index["resources"]:
        if resource["name"] == "targets.simple.csv":
            print(f"resolved current export: {resource['url']} ({resource['size'] / 1e6:.0f} MB, "
                  f"dataset updated_at={index.get('updated_at')})")
            return resource["url"]
    raise RuntimeError("targets.simple.csv not found in current index.json")


def download(url: str) -> Path:
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=300) as resp:
        resp.raise_for_status()
        with open(RAW_PATH, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    print(f"downloaded {RAW_PATH.stat().st_size / 1e6:.0f} MB -> {RAW_PATH}")
    return RAW_PATH


def filter_and_convert(path: Path) -> pd.DataFrame:
    chunks = []
    total_rows = 0
    for chunk in pd.read_csv(path, chunksize=200_000, low_memory=False):
        total_rows += len(chunk)
        countries = chunk.get("countries", pd.Series(dtype=str)).fillna("").str.lower()
        schema = chunk.get("schema", pd.Series(dtype=str)).fillna("")
        sanctions_present = chunk.get("sanctions", pd.Series(dtype=str)).fillna("").str.len() > 0

        country_match = countries.apply(lambda c: any(rc in c.split(";") for rc in RELEVANT_COUNTRIES))
        schema_match = schema.isin(RELEVANT_SCHEMA)

        filtered = chunk[country_match & schema_match & sanctions_present]
        if len(filtered):
            chunks.append(filtered)

    print(f"scanned {total_rows} total rows")
    if not chunks:
        return pd.DataFrame()
    result = pd.concat(chunks, ignore_index=True)
    print(f"kept {len(result)} rows matching relevant countries/schema/sanctions-present")
    return result


def to_canonical(df: pd.DataFrame) -> pd.DataFrame:
    records = []
    for _, row in df.iterrows():
        records.append({
            "entity_type": "sanctioned_entity",
            "entity_id": str(row.get("id", "")),
            "entity_name": row.get("name", ""),
            "timestamp": str(row.get("first_seen", "")),
            "timestamp_precision": "day",
            "latitude": None,
            "longitude": None,
            "location_name": row.get("countries", ""),
            "location_code": row.get("countries", ""),
            "attributes": json.dumps({
                "schema": row.get("schema"),
                "sanctions": row.get("sanctions"),
                "program_ids": str(row.get("program_ids", "")).split(";") if pd.notna(row.get("program_ids")) else [],
                "dataset": str(row.get("dataset", "")).split(";") if pd.notna(row.get("dataset")) else [],
                "countries": str(row.get("countries", "")).split(";") if pd.notna(row.get("countries")) else [],
                "list_name": "OpenSanctions",
                "aliases": str(row.get("aliases", "")).split(";") if pd.notna(row.get("aliases")) else [],
                "birth_date": row.get("birth_date"),
                "last_change": row.get("last_change"),
            }, default=str),
            "relationships": json.dumps([]),
            "source": "opensanctions",
            "source_record_id": str(row.get("id", "")),
            "confidence": None,
            "metadata": json.dumps({"parser": "ingest_opensanctions", "version": "1.0"}),
        })
    return pd.DataFrame(records)


def main() -> None:
    url = resolve_current_url()
    path = download(url)
    filtered = filter_and_convert(path)
    canonical = to_canonical(filtered)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    canonical.to_csv(OUT_PATH, index=False)
    print(f"wrote {len(canonical)} canonical entity records -> {OUT_PATH}")

    # drop the large raw download once processed — keep the raw/ folder lean
    path.unlink(missing_ok=True)
    print("removed raw download (filtered output retained)")


if __name__ == "__main__":
    main()
