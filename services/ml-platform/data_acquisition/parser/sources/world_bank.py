from __future__ import annotations

import csv
import json
import re
import time
from pathlib import Path
from typing import Any

from backend.shared.logging_config import get_logger
from data_acquisition.parser.base import BaseParser, ParseConfig, ParserResult

logger = get_logger(__name__)


WORLD_BANK_FIELDS = ["indicator", "country", "date", "value", "unit", "source_note"]


class WorldBankParser(BaseParser):
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
        suffix = input_path.suffix.lower()

        canonical_records: list[dict] = []

        if suffix == ".json":
            with open(input_path, "r", encoding=encoding) as f:
                data = json.load(f)

            if isinstance(data, list) and len(data) >= 2:
                meta = data[0]
                records = data[1]
            elif isinstance(data, dict):
                records = data.get("data", data.get("records", []))
            else:
                records = data

            for item in records:
                if max_records is not None and records_parsed >= max_records:
                    break
                try:
                    indicator = item.get("indicator", {})
                    country = item.get("country", {})
                    if isinstance(indicator, dict):
                        indicator_id = indicator.get("id", indicator.get("value", ""))
                        indicator_name = indicator.get("value", indicator_id)
                    else:
                        indicator_id = str(indicator)
                        indicator_name = indicator_id
                    if isinstance(country, dict):
                        country_id = country.get("id", country.get("value", ""))
                        country_name = country.get("value", country_id)
                    else:
                        country_id = str(country)
                        country_name = country_id

                    rec = {
                        "indicator": indicator_name,
                        "indicator_id": indicator_id,
                        "country": country_name,
                        "country_id": country_id,
                        "date": str(item.get("date", "")),
                        "value": item.get("value"),
                        "unit": item.get("unit", item.get("units", "")),
                        "source_note": item.get("sourceNote", item.get("source_note", "")),
                    }
                    canonical = await self.to_canonical([rec])
                    canonical_records.extend(canonical)
                    records_parsed += 1
                except Exception as e:
                    records_failed += 1
                    errors.append({"indicator": item.get("indicator"), "error": str(e)})
        else:
            with open(input_path, "r", encoding=encoding) as f:
                reader = csv.DictReader(f)
                for row_idx, row in enumerate(reader):
                    if max_records is not None and records_parsed >= max_records:
                        break
                    try:
                        rec = {
                            "indicator": row.get("indicator", row.get("Indicator", row.get("Indicator Name", ""))),
                            "indicator_id": row.get("indicator_id", row.get("IndicatorCode", row.get("Indicator Code", ""))),
                            "country": row.get("country", row.get("Country", row.get("Country Name", ""))),
                            "country_id": row.get("country_id", row.get("CountryCode", row.get("Country Code", ""))),
                            "date": row.get("date", row.get("Date", row.get("year", row.get("Year", "")))),
                            "value": row.get("value", row.get("Value", "")),
                            "unit": row.get("unit", row.get("Unit", "")),
                            "source_note": row.get("source_note", row.get("SourceNote", "")),
                        }
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
            source="world_bank",
            version="1.0",
            records_parsed=records_parsed,
            records_failed=records_failed,
            output_path=output_path,
            schema_discovered=schema,
            columns=WORLD_BANK_FIELDS,
            row_count=records_parsed,
            duration_seconds=time.monotonic() - start,
            errors=errors,
        )

    async def discover_schema(self, input_path: Path) -> dict:
        return {
            "indicator": "string",
            "country": "string",
            "country_id": "string",
            "date": "string",
            "value": "number",
            "unit": "string",
            "source_note": "string",
        }

    async def validate(self, input_path: Path) -> list[str]:
        issues: list[str] = []
        try:
            with open(input_path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for row_idx, row in enumerate(reader):
                    if row_idx > 1000:
                        break
                    if not row.get("country", "").strip() and not row.get("Country", "").strip():
                        issues.append(f"Row {row_idx}: missing country")
        except Exception as e:
            issues.append(f"Validation error: {e}")
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
            "field_count": len(WORLD_BANK_FIELDS),
        }

    async def to_canonical(self, records: list[dict]) -> list[dict]:
        canonical: list[dict] = []
        for rec in records:
            date = rec.get("date", "")
            if re.match(r"^\d{4}$", date):
                precision = "year"
            elif re.match(r"^\d{4}-\d{2}$", date):
                precision = "month"
            elif re.match(r"^\d{4}-\d{2}-\d{2}$", date):
                precision = "day"
            else:
                precision = "year" if date.isdigit() and len(date) == 4 else "unknown"

            country = rec.get("country", "")
            country_id = rec.get("country_id", "")
            indicator = rec.get("indicator", "")
            indicator_id = rec.get("indicator_id", "")

            canonical.append({
                "entity_type": "economic_indicator",
                "entity_id": f"{indicator_id}_{country_id}_{date}",
                "entity_name": f"{indicator} - {country}",
                "timestamp": date,
                "timestamp_precision": precision,
                "latitude": None,
                "longitude": None,
                "location_name": country,
                "location_code": country_id,
                "attributes": {
                    "indicator": indicator,
                    "indicator_id": indicator_id,
                    "value": self._safe_float(rec.get("value")),
                    "unit": rec.get("unit"),
                    "source_note": rec.get("source_note"),
                },
                "relationships": [
                    {"type": "measures", "target_id": indicator_id},
                ],
                "source": "world_bank",
                "source_record_id": f"{indicator_id}_{country_id}_{date}",
                "confidence": None,
                "metadata": {"parser": "WorldBankParser", "version": "1.0"},
            })
        return canonical

    def _safe_float(self, value: Any) -> float | None:
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
