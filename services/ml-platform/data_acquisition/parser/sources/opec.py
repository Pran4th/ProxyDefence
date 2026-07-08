from __future__ import annotations

import csv
import re
import time
from pathlib import Path
from typing import Any

from backend.shared.logging_config import get_logger
from data_acquisition.parser.base import BaseParser, ParseConfig, ParserResult

logger = get_logger(__name__)

OPEC_FIELDS = ["country", "month", "production_kbbl", "change_kbbl", "capacity_kbbl", "export_kbbl"]

COUNTRY_NORMALIZATION = {
    "islamic republic of iran": "Iran",
    "iran (islamic republic of)": "Iran",
    "iran, islamic republic of": "Iran",
    "iran, islamic rep.": "Iran",
    "saudi arabia (ksa)": "Saudi Arabia",
    "saudi arabia": "Saudi Arabia",
    "kingdom of saudi arabia": "Saudi Arabia",
    "united arab emirates": "UAE",
    "u.a.e.": "UAE",
    "venezuela (bolivarian republic of)": "Venezuela",
    "venezuela, bolivarian republic of": "Venezuela",
    "venezuela, bolivarian rep.": "Venezuela",
    "russian federation": "Russia",
    "russian federation (rf)": "Russia",
    "congo (br)": "Congo",
    "congo (brazzaville)": "Congo",
    "democratic republic of the congo": "DR Congo",
    "dr congo": "DR Congo",
    "d.r. congo": "DR Congo",
    "equatorial guinea": "Equatorial Guinea",
    "republic of congo": "Congo",
    "south sudan": "South Sudan",
    "rep. of congo": "Congo",
    "côte d'ivoire": "Cote d'Ivoire",
    "cote d'ivoire": "Cote d'Ivoire",
}


def normalize_country(name: str) -> str:
    key = name.strip().lower()
    key = re.sub(r"\s+", " ", key)
    return COUNTRY_NORMALIZATION.get(key, name.strip())


class OPECParser(BaseParser):
    @property
    def canonical_schema(self) -> dict:
        return {
            "entity_type": "string",
            "entity_id": "string",
            "entity_name": "string",
            "timestamp": "string",
            "timestamp_precision": "string",
            "latitude": "float",
            "longitude": "float",
            "location_name": "string",
            "location_code": "string",
            "attributes": "dict",
            "relationships": "list",
            "source": "string",
            "source_record_id": "string",
            "confidence": "float",
            "metadata": "dict",
        }

    async def parse(self, config: ParseConfig) -> ParserResult:
        return await self.parse_file(
            config.input_path, config.output_path,
            encoding=config.encoding, max_records=config.max_records,
            batch_size=config.batch_size,
        )

    async def parse_file(
        self, input_path: Path, output_path: Path, **kwargs: Any
    ) -> ParserResult:
        start = time.monotonic()
        errors: list[dict] = []
        records_parsed = 0
        records_failed = 0
        max_records = kwargs.get("max_records")
        encoding = kwargs.get("encoding", "utf-8")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        schema = await self.discover_schema(input_path)

        canonical_records: list[dict] = []
        with open(input_path, "r", encoding=encoding) as f:
            reader = csv.DictReader(f)
            for row_idx, row in enumerate(reader):
                if max_records is not None and records_parsed >= max_records:
                    break
                try:
                    rec = {
                        "country": row.get("country", row.get("Country", "")),
                        "month": row.get("month", row.get("Month", row.get("date", row.get("Date", "")))),
                        "production_kbbl": row.get("production_kbbl", row.get("production", row.get("Production", ""))),
                        "change_kbbl": row.get("change_kbbl", row.get("change", row.get("Change", ""))),
                        "capacity_kbbl": row.get("capacity_kbbl", row.get("capacity", row.get("Capacity", ""))),
                        "export_kbbl": row.get("export_kbbl", row.get("export", row.get("Export", ""))),
                    }
                    rec["country"] = normalize_country(rec["country"])
                    canonical = await self.to_canonical([rec])
                    canonical_records.extend(canonical)
                    records_parsed += 1
                except Exception as e:
                    records_failed += 1
                    errors.append({"row": row_idx, "error": str(e)})

        with open(output_path, "w", encoding="utf-8", newline="") as out_f:
            if canonical_records:
                writer = csv.DictWriter(out_f, fieldnames=list(canonical_records[0].keys()))
                writer.writeheader()
                writer.writerows(canonical_records)

        return ParserResult(
            source="opec",
            version="1.0",
            records_parsed=records_parsed,
            records_failed=records_failed,
            output_path=output_path,
            schema_discovered=schema,
            columns=OPEC_FIELDS,
            row_count=records_parsed,
            duration_seconds=time.monotonic() - start,
            errors=errors,
        )

    async def discover_schema(self, input_path: Path) -> dict:
        return {
            "country": "string",
            "month": "string",
            "production_kbbl": "number",
            "change_kbbl": "number",
            "capacity_kbbl": "number",
            "export_kbbl": "number",
        }

    async def validate(self, input_path: Path) -> list[str]:
        issues: list[str] = []
        try:
            with open(input_path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for row_idx, row in enumerate(reader):
                    if row_idx > 1000:
                        break
                    if not row.get("country", "").strip():
                        issues.append(f"Row {row_idx}: missing country")
                    if not row.get("month", "").strip():
                        issues.append(f"Row {row_idx}: missing month")
        except Exception as e:
            issues.append(f"File read error: {e}")
        return issues

    async def get_metadata(self, input_path: Path) -> dict:
        line_count = 0
        with open(input_path, "r", encoding="utf-8", errors="replace") as f:
            for _ in f:
                line_count += 1
        return {
            "file_name": input_path.name,
            "file_size_bytes": input_path.stat().st_size,
            "line_count": line_count,
            "field_count": len(OPEC_FIELDS),
        }

    async def to_canonical(self, records: list[dict]) -> list[dict]:
        canonical: list[dict] = []
        for rec in records:
            month = rec.get("month", "")
            if re.match(r"^\d{4}-\d{2}$", month):
                precision = "month"
            elif re.match(r"^\d{4}$", month):
                precision = "year"
            else:
                precision = "month"

            canonical.append({
                "entity_type": "oil_production",
                "entity_id": f"opec_{rec['country']}_{month}",
                "entity_name": f"{rec['country']} OPEC Production",
                "timestamp": month,
                "timestamp_precision": precision,
                "latitude": None,
                "longitude": None,
                "location_name": rec.get("country"),
                "location_code": rec.get("country"),
                "attributes": {
                    "country": rec.get("country"),
                    "production_kbbl": self._safe_float(rec.get("production_kbbl")),
                    "change_kbbl": self._safe_float(rec.get("change_kbbl")),
                    "capacity_kbbl": self._safe_float(rec.get("capacity_kbbl")),
                    "export_kbbl": self._safe_float(rec.get("export_kbbl")),
                    "unit": "thousand barrels per day",
                },
                "relationships": [
                    {"type": "member_of", "target_id": "OPEC"},
                ],
                "source": "opec",
                "source_record_id": f"{rec['country']}_{month}",
                "confidence": None,
                "metadata": {"parser": "OPECParser", "version": "1.0"},
            })
        return canonical

    def _safe_float(self, value: str | None) -> float | None:
        if value is None or value.strip() == "":
            return None
        try:
            cleaned = value.strip().replace(",", "").replace(" ", "")
            return float(cleaned)
        except (ValueError, TypeError):
            return None
