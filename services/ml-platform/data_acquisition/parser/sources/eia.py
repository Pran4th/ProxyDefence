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

EIA_CATEGORIES = {
    "petroleum": "PET",
    "natural_gas": "NG",
    "coal": "COAL",
    "electricity": "ELEC",
}

FRED_FIELDS = ["date", "value", "series_id", "name"]


class EIAParser(BaseParser):
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
            batch_size=config.batch_size, schema=config.schema,
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

        if suffix == ".json":
            records_parsed, records_failed, errors = await self._parse_json(
                input_path, output_path, encoding, max_records, errors,
            )
        elif suffix == ".csv":
            records_parsed, records_failed, errors = await self._parse_csv(
                input_path, output_path, encoding, max_records, errors,
            )
        else:
            raise ValueError(f"Unsupported EIA file format: {suffix}")

        return ParserResult(
            source="eia",
            version="1.0",
            records_parsed=records_parsed,
            records_failed=records_failed,
            output_path=output_path,
            schema_discovered=schema,
            columns=list(schema.keys()),
            row_count=records_parsed,
            duration_seconds=time.monotonic() - start,
            errors=errors,
        )

    async def _parse_json(
        self, input_path: Path, output_path: Path, encoding: str,
        max_records: int | None, errors: list[dict],
    ) -> tuple[int, int, list[dict]]:
        records_parsed = 0
        records_failed = 0
        with open(input_path, "r", encoding=encoding) as f:
            data = json.load(f)

        series_data = self._extract_series(data)
        canonical_records: list[dict] = []

        for series in series_data:
            if max_records is not None and records_parsed >= max_records:
                break
            series_id = series.get("series_id", "")
            for point in series.get("data", []):
                if max_records is not None and records_parsed >= max_records:
                    break
                try:
                    rec = {
                        "series_id": series_id,
                        "period": point[0] if len(point) > 0 else "",
                        "value": point[1] if len(point) > 1 else None,
                        "unit": series.get("units", ""),
                        "area": series.get("area", ""),
                        "product": series.get("product", ""),
                        "process": series.get("process", ""),
                        "series_name": series.get("name", ""),
                    }
                    canonical = await self.to_canonical([rec])
                    canonical_records.extend(canonical)
                    records_parsed += 1
                except Exception as e:
                    records_failed += 1
                    errors.append({"series_id": series_id, "error": str(e)})

        with open(output_path, "w", encoding="utf-8", newline="") as out_f:
            if canonical_records:
                writer = csv.DictWriter(out_f, fieldnames=list(canonical_records[0].keys()))
                writer.writeheader()
                writer.writerows(canonical_records)

        return records_parsed, records_failed, errors

    async def _parse_csv(
        self, input_path: Path, output_path: Path, encoding: str,
        max_records: int | None, errors: list[dict],
    ) -> tuple[int, int, list[dict]]:
        records_parsed = 0
        records_failed = 0
        canonical_records: list[dict] = []

        with open(input_path, "r", encoding=encoding) as f:
            reader = csv.DictReader(f)
            for row in reader:
                if max_records is not None and records_parsed >= max_records:
                    break
                try:
                    rec = {
                        "series_id": row.get("series_id", ""),
                        "period": row.get("period", row.get("date", "")),
                        "value": row.get("value"),
                        "unit": row.get("units", row.get("unit", "")),
                        "area": row.get("area", row.get("area-name", "")),
                        "product": row.get("product", row.get("product-name", "")),
                        "process": row.get("process", ""),
                        "series_name": row.get("name", row.get("series_description", "")),
                    }
                    canonical = await self.to_canonical([rec])
                    canonical_records.extend(canonical)
                    records_parsed += 1
                except Exception as e:
                    records_failed += 1
                    errors.append({"row": records_parsed, "error": str(e)})

        with open(output_path, "w", encoding="utf-8", newline="") as out_f:
            if canonical_records:
                writer = csv.DictWriter(out_f, fieldnames=list(canonical_records[0].keys()))
                writer.writeheader()
                writer.writerows(canonical_records)

        return records_parsed, records_failed, errors

    def _extract_series(self, data: dict) -> list[dict]:
        series_data = data.get("series", [])
        if series_data:
            return series_data
        response_data = data.get("response", {})
        if response_data:
            return response_data.get("data", response_data.get("series", []))
        sfa = data.get("series", {})
        if isinstance(sfa, dict):
            for v in sfa.values():
                if isinstance(v, list):
                    return v
        return []

    async def discover_schema(self, input_path: Path) -> dict:
        suffix = input_path.suffix.lower()
        if suffix == ".json":
            return {
                "series_id": "string",
                "period": "string",
                "value": "number",
                "unit": "string",
                "area": "string",
                "product": "string",
                "process": "string",
                "series_name": "string",
            }
        return {
            "period": "string",
            "value": "number",
            "area": "string",
            "product": "string",
            "unit": "string",
        }

    async def validate(self, input_path: Path) -> list[str]:
        issues: list[str] = []
        suffix = input_path.suffix.lower()
        if suffix == ".json":
            try:
                with open(input_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                series = self._extract_series(data)
                if not series:
                    issues.append("No series data found in JSON")
                for s in series:
                    if "series_id" not in s:
                        issues.append(f"Series missing series_id: {str(s)[:100]}")
                        break
            except json.JSONDecodeError as e:
                issues.append(f"Invalid JSON: {e}")
        return issues

    async def get_metadata(self, input_path: Path) -> dict:
        suffix = input_path.suffix.lower()
        return {
            "file_name": input_path.name,
            "file_size_bytes": input_path.stat().st_size,
            "format": suffix,
            "category": self._detect_category(input_path),
        }

    def _detect_category(self, input_path: Path) -> str:
        name = input_path.name.lower()
        for cat, prefix in EIA_CATEGORIES.items():
            if prefix.lower() in name:
                return cat
        return "unknown"

    async def to_canonical(self, records: list[dict]) -> list[dict]:
        canonical: list[dict] = []
        for rec in records:
            timestamp = rec.get("period", "")
            if re.match(r"^\d{4}$", timestamp):
                precision = "year"
            elif re.match(r"^\d{4}\d{2}$", timestamp):
                precision = "month"
                timestamp = f"{timestamp[:4]}-{timestamp[4:6]}"
            elif re.match(r"^\d{4}-\d{2}-\d{2}$", timestamp):
                precision = "day"
            else:
                precision = "unknown"

            value = self._safe_float(rec.get("value"))
            canonical.append({
                "entity_type": "timeseries",
                "entity_id": rec.get("series_id", ""),
                "entity_name": rec.get("series_name", rec.get("series_id", "")),
                "timestamp": timestamp,
                "timestamp_precision": precision,
                "latitude": None,
                "longitude": None,
                "location_name": rec.get("area"),
                "location_code": rec.get("area"),
                "attributes": {
                    "series_id": rec.get("series_id"),
                    "value": value,
                    "unit": rec.get("unit"),
                    "product": rec.get("product"),
                    "process": rec.get("process"),
                },
                "relationships": [],
                "source": "eia",
                "source_record_id": rec.get("series_id"),
                "confidence": None,
                "metadata": {"parser": "EIAParser", "version": "1.0"},
            })
        return canonical

    def _safe_float(self, value: Any) -> float | None:
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None


class FREDParser(BaseParser):
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

        series_id = self._extract_series_id(input_path)
        canonical_records: list[dict] = []

        if suffix == ".json":
            with open(input_path, "r", encoding=encoding) as f:
                data = json.load(f)
            observations = data.get("observations", data.get("data", []))
            for obs in observations:
                if max_records is not None and records_parsed >= max_records:
                    break
                try:
                    rec = {
                        "series_id": series_id or obs.get("series_id", ""),
                        "date": obs.get("date", ""),
                        "value": obs.get("value"),
                        "name": obs.get("name", ""),
                    }
                    canonical = await self.to_canonical([rec])
                    canonical_records.extend(canonical)
                    records_parsed += 1
                except Exception as e:
                    records_failed += 1
                    errors.append({"date": obs.get("date"), "error": str(e)})
        elif suffix == ".csv":
            with open(input_path, "r", encoding=encoding) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if max_records is not None and records_parsed >= max_records:
                        break
                    try:
                        rec = {
                            "series_id": series_id or row.get("series_id", ""),
                            "date": row.get("date", ""),
                            "value": row.get("value"),
                            "name": row.get("name", row.get("series_name", "")),
                        }
                        canonical = await self.to_canonical([rec])
                        canonical_records.extend(canonical)
                        records_parsed += 1
                    except Exception as e:
                        records_failed += 1
                        errors.append({"row": records_parsed, "error": str(e)})

        with open(output_path, "w", encoding="utf-8", newline="") as out_f:
            if canonical_records:
                writer = csv.DictWriter(out_f, fieldnames=list(canonical_records[0].keys()))
                writer.writeheader()
                writer.writerows(canonical_records)

        return ParserResult(
            source="fred",
            version="1.0",
            records_parsed=records_parsed,
            records_failed=records_failed,
            output_path=output_path,
            schema_discovered=schema,
            columns=FRED_FIELDS,
            row_count=records_parsed,
            duration_seconds=time.monotonic() - start,
            errors=errors,
        )

    def _extract_series_id(self, input_path: Path) -> str:
        name = input_path.stem
        return name.upper()

    async def discover_schema(self, input_path: Path) -> dict:
        return {
            "date": "string",
            "value": "number",
            "series_id": "string",
            "name": "string",
        }

    async def validate(self, input_path: Path) -> list[str]:
        issues: list[str] = []
        suffix = input_path.suffix.lower()
        if suffix == ".json":
            try:
                with open(input_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                obs = data.get("observations", data.get("data", []))
                if not obs:
                    issues.append("No observations found")
            except json.JSONDecodeError as e:
                issues.append(f"Invalid JSON: {e}")
        return issues

    async def get_metadata(self, input_path: Path) -> dict:
        series_id = self._extract_series_id(input_path)
        return {
            "file_name": input_path.name,
            "file_size_bytes": input_path.stat().st_size,
            "series_id": series_id,
            "format": input_path.suffix.lower(),
        }

    async def to_canonical(self, records: list[dict]) -> list[dict]:
        canonical: list[dict] = []
        for rec in records:
            value = self._safe_float(rec.get("value"))
            canonical.append({
                "entity_type": "timeseries",
                "entity_id": rec.get("series_id", ""),
                "entity_name": rec.get("name", rec.get("series_id", "")),
                "timestamp": rec.get("date", ""),
                "timestamp_precision": "day",
                "latitude": None,
                "longitude": None,
                "location_name": None,
                "location_code": None,
                "attributes": {
                    "series_id": rec.get("series_id"),
                    "value": value,
                    "unit": "index",
                },
                "relationships": [],
                "source": "fred",
                "source_record_id": rec.get("series_id"),
                "confidence": None,
                "metadata": {"parser": "FREDParser", "version": "1.0"},
            })
        return canonical

    def _safe_float(self, value: Any) -> float | None:
        if value is None or (isinstance(value, str) and value.strip() in ("", ".")):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
