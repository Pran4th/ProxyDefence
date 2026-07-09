"""Downloads and parses the EU Consolidated Financial Sanctions List into the
canonical entity schema (same shape as the OFAC parser), deduplicating the
source's one-row-per-alias format down to one row per sanctioned entity.

Source: European Commission FSF public CSV export. Uses a documented,
stable public access token (the same one used by open-source AML tools
like moov-io/watchman) — no EU Login account needed for this endpoint.

Run from services/ml-platform/ with POSTGRES_* env set:
    .venv/Scripts/python.exe scripts/ingest_eu_sanctions.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_PATH = REPO_ROOT / "datasets" / "raw" / "sanctions" / "eu_fsf_sanctions.csv"
OUT_PATH = REPO_ROOT / "datasets" / "processed" / "eu-sanctions" / "eu-sanctions.csv"

EU_FSF_URL = (
    "https://webgate.ec.europa.eu/fsd/fsf/public/files/csvFullSanctionsList/content"
    "?token=dG9rZW4tMjAxNw"
)

SUBJECT_TYPE_LABELS = {"P": "person", "E": "entity"}


def download() -> Path:
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(EU_FSF_URL, timeout=60)
    resp.raise_for_status()
    RAW_PATH.write_bytes(resp.content)
    print(f"downloaded {len(resp.content):,} bytes -> {RAW_PATH}")
    return RAW_PATH


def parse_and_dedupe(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";", encoding="utf-8-sig", low_memory=False)
    print(f"raw rows: {len(df)} | distinct entities: {df['Entity_logical_id'].nunique()}")

    records = []
    for entity_id, group in df.groupby("Entity_logical_id"):
        first = group.iloc[0]
        names = [n for n in group["Naal_wholename"].dropna().unique().tolist() if n]
        primary_name = names[0] if names else f"entity-{entity_id}"
        aliases = names[1:]
        programs = sorted(group["Programme"].dropna().unique().tolist())
        birth_country = group["Birt_country"].dropna().iloc[0] if "Birt_country" in group and group["Birt_country"].notna().any() else None
        addr_country = group["Addr_country"].dropna().iloc[0] if "Addr_country" in group and group["Addr_country"].notna().any() else None

        records.append({
            "entity_type": "sanctioned_entity",
            "entity_id": str(entity_id),
            "entity_name": primary_name,
            "timestamp": str(first.get("Leba_publication_date", "")),
            "timestamp_precision": "day",
            "latitude": None,
            "longitude": None,
            "location_name": addr_country or birth_country,
            "location_code": addr_country or birth_country,
            "attributes": json.dumps({
                "subject_type": SUBJECT_TYPE_LABELS.get(first.get("Subject_type"), first.get("Subject_type")),
                "program": programs,
                "list_name": "EU_FSF",
                "aliases": aliases,
                "birth_country": birth_country,
                "address_country": addr_country,
                "legal_basis_title": str(first.get("Leba_numtitle", "")),
                "legal_basis_url": str(first.get("Leba_url", "")),
            }, default=str),
            "relationships": json.dumps([{"type": "subject_to_program", "target_id": p} for p in programs]),
            "source": "eu_fsf",
            "source_record_id": str(entity_id),
            "confidence": None,
            "metadata": json.dumps({"parser": "ingest_eu_sanctions", "version": "1.0"}),
        })

    return pd.DataFrame(records)


def main() -> None:
    path = download()
    canonical = parse_and_dedupe(path)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    canonical.to_csv(OUT_PATH, index=False)
    print(f"wrote {len(canonical)} canonical entity records -> {OUT_PATH}")

    # quick relevance check for the hackathon's core scenarios
    iran = canonical[canonical["attributes"].str.contains('"IRN"')]
    russia_related = canonical[canonical["attributes"].str.contains('"UKR"')]
    print(f"Iran-program entities: {len(iran)}")
    print(f"Ukraine/Russia-program entities: {len(russia_related)}")


if __name__ == "__main__":
    main()
