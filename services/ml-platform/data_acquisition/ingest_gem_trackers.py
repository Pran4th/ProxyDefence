"""One-off/rerunnable ingestion of Global Energy Monitor (GEM) infrastructure trackers.

These are xlsx files with no matching source in data_acquisition/source_registry.py
(GEM isn't a REST API source — it's a manual bulk-download tracker), so they bypass
the BaseParser plugin framework and go straight from raw xlsx -> canonical CSV in the
processed/ lake, ready for `ml register`.

Run from services/ml-platform/ with:
    PYTHONPATH="<repo>;<repo>/services/ml-platform" .venv/Scripts/python.exe data_acquisition/ingest_gem_trackers.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import openpyxl

REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = REPO_ROOT / "datasets" / "raw"
PROCESSED_DIR = REPO_ROOT / "datasets" / "processed"

TRACKERS = [
    {
        "key": "oil-ngl-pipelines",
        "file": "GEM-GOIT-Oil-NGL-Pipelines-2026-06.xlsx",
        "sheet": "Data",
        "entity_type": "oil_pipeline",
        "id_col": "ProjectID",
        "name_col": "PipelineName",
        "status_col": "Status",
        "country_col": "CountriesOrAreas",
        "lat_col": None,
        "lon_col": None,
    },
    {
        "key": "gas-pipelines",
        "file": "GEM-GGIT-Gas-Pipelines-2025-11.xlsx",
        "sheet": "Pipelines",
        "entity_type": "gas_pipeline",
        "id_col": "ProjectID",
        "name_col": "PipelineName",
        "status_col": "Status",
        "country_col": "CountriesOrAreas",
        "lat_col": None,
        "lon_col": None,
    },
    {
        "key": "lng-terminals",
        "file": "GEM-GGIT-LNG-Teminals-2025-09.xlsx",
        "sheet": "LNG Terminals",
        "entity_type": "lng_terminal",
        "id_col": "TerminalID",
        "name_col": "TerminalName",
        "status_col": "Status",
        "country_col": "Country",
        "lat_col": "Latitude",
        "lon_col": "Longitude",
    },
    {
        "key": "oil-gas-fields",
        "file": "Global-Oil-and-Gas-Extraction-Tracker-March-2026.xlsx",
        "sheet": "Field-level main data",
        "entity_type": "oil_gas_field",
        "id_col": "Unit ID",
        "name_col": "Unit Name",
        "status_col": "Status",
        "country_col": "Country/Area",
        "lat_col": "Latitude",
        "lon_col": "Longitude",
    },
    {
        "key": "oil-gas-plants",
        "file": "Global-Oil-and-Gas-Plant-Tracker-GOGPT-January-2026.xlsx",
        "sheet": "Gas & Oil Units",
        "entity_type": "refinery_or_plant_unit",
        "id_col": "GEM Unit ID",
        "name_col": "Plant name",
        "status_col": "Status",
        "country_col": "Country/Area",
        "lat_col": "Latitude",
        "lon_col": "Longitude",
    },
]


def _safe_float(value) -> float | None:
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _find_col(header: list[str], candidates: list[str]) -> str | None:
    lower = {str(h).strip().lower(): h for h in header if h}
    for c in candidates:
        if c and c.lower() in lower:
            return lower[c.lower()]
    return None


def ingest_tracker(spec: dict) -> dict:
    path = RAW_DIR / spec["file"]
    if not path.exists():
        return {"key": spec["key"], "status": "missing_file", "rows": 0}

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[spec["sheet"]]
    rows_iter = ws.iter_rows(values_only=True)
    header = [str(h).strip() if h is not None else "" for h in next(rows_iter)]

    id_col = _find_col(header, [spec["id_col"]])
    name_col = _find_col(header, [spec["name_col"]])
    status_col = _find_col(header, [spec["status_col"]])
    country_col = _find_col(header, [spec["country_col"]])
    lat_col = _find_col(header, [spec["lat_col"]]) if spec["lat_col"] else None
    lon_col = _find_col(header, [spec["lon_col"]]) if spec["lon_col"] else None

    out_dir = PROCESSED_DIR / "gem-infrastructure" / spec["key"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{spec['key']}.csv"

    fieldnames = [
        "entity_type", "entity_id", "entity_name", "status", "country",
        "latitude", "longitude", "attributes", "source", "source_record_id",
    ]

    row_count = 0
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows_iter:
            if row is None or all(v is None for v in row):
                continue
            rec = dict(zip(header, row))
            entity_id = str(rec.get(id_col, "")) if id_col else ""
            entity_name = str(rec.get(name_col, "")) if name_col else ""
            if not entity_id and not entity_name:
                continue
            attributes = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in rec.items() if v is not None}
            writer.writerow({
                "entity_type": spec["entity_type"],
                "entity_id": entity_id or entity_name,
                "entity_name": entity_name,
                "status": rec.get(status_col, "") if status_col else "",
                "country": rec.get(country_col, "") if country_col else "",
                "latitude": _safe_float(rec.get(lat_col)) if lat_col else None,
                "longitude": _safe_float(rec.get(lon_col)) if lon_col else None,
                "attributes": json.dumps(attributes, default=str),
                "source": f"gem_{spec['key']}",
                "source_record_id": entity_id or entity_name,
            })
            row_count += 1

    wb.close()
    return {"key": spec["key"], "status": "ok", "rows": row_count, "output": str(out_path)}


def main() -> None:
    results = []
    for spec in TRACKERS:
        result = ingest_tracker(spec)
        results.append(result)
        print(f"{result['key']}: {result['status']} rows={result['rows']}" + (f" -> {result.get('output')}" if result.get("output") else ""))
    total = sum(r["rows"] for r in results)
    print(f"\ntotal records ingested: {total}")


if __name__ == "__main__":
    main()
