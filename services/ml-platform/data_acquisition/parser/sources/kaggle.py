from __future__ import annotations

import csv
import json
import os
import time
from pathlib import Path
from typing import Any

from backend.shared.logging_config import get_logger
from data_acquisition.parser.base import BaseParser, ParseConfig, ParserResult

logger = get_logger(__name__)


KAGGLE_CANONICAL_MAP = {
    "id": "entity_id",
    "name": "entity_name",
    "title": "entity_name",
    "label": "entity_name",
    "date": "timestamp",
    "timestamp": "timestamp",
    "time": "timestamp",
    "lat": "latitude",
    "latitude": "latitude",
    "lon": "longitude",
    "lng": "longitude",
    "longitude": "longitude",
    "country": "location_name",
    "country_code": "location_code",
    "region": "location_name",
    "city": "location_name",
    "source": "source",
    "description": "entity_name",
}


class KaggleParser(BaseParser):
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

        canonical_records: list[dict] = []
        fieldnames: list[str] = []

        if suffix == ".json":
            with open(input_path, "r", encoding=encoding) as f:
                data = json.load(f)
            records = data if isinstance(data, list) else data.get("data", data.get("records", [data]))
            if records:
                fieldnames = list(records[0].keys()) if isinstance(records[0], dict) else []
            for item in records:
                if max_records is not None and records_parsed >= max_records:
                    break
                if not isinstance(item, dict):
                    continue
                try:
                    canonical = await self.to_canonical([item])
                    canonical_records.extend(canonical)
                    records_parsed += 1
                except Exception as e:
                    records_failed += 1
                    errors.append({"record": records_parsed, "error": str(e)})
        else:
            with open(input_path, "r", encoding=encoding) as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames or []
                for row_idx, row in enumerate(reader):
                    if max_records is not None and records_parsed >= max_records:
                        break
                    try:
                        canonical = await self.to_canonical([row])
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
            source="kaggle",
            version="1.0",
            records_parsed=records_parsed,
            records_failed=records_failed,
            output_path=output_path,
            schema_discovered=schema,
            columns=fieldnames,
            row_count=records_parsed,
            duration_seconds=time.monotonic() - start,
            errors=errors,
        )

    async def discover_schema(self, input_path: Path) -> dict:
        schema: dict[str, str] = {}
        suffix = input_path.suffix.lower()
        if suffix == ".json":
            with open(input_path, "r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)
            records = data if isinstance(data, list) else data.get("data", data.get("records", [data]))
            if records and isinstance(records[0], dict):
                for key, val in records[0].items():
                    schema[key] = self._infer_type_from_value(val)
        else:
            with open(input_path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames:
                    for field in reader.fieldnames:
                        schema[field] = "string"
                    for row in reader:
                        for field, val in row.items():
                            if val.strip():
                                inferred = self._infer_type_from_value(val.strip())
                                existing = schema.get(field)
                                if existing != inferred and existing == "string":
                                    pass
                                elif existing != inferred:
                                    schema[field] = "string"
                        break
        return schema

    def _infer_type_from_value(self, value: Any) -> str:
        if value is None:
            return "string"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "integer"
        if isinstance(value, float):
            return "number"
        if isinstance(value, dict):
            return "object"
        if isinstance(value, list):
            return "array"
        s = str(value)
        if s.lower() in ("true", "false"):
            return "boolean"
        try:
            int(s)
            return "integer"
        except ValueError:
            pass
        try:
            float(s)
            return "number"
        except ValueError:
            pass
        return "string"

    async def validate(self, input_path: Path) -> list[str]:
        issues: list[str] = []
        try:
            suffix = input_path.suffix.lower()
            if suffix == ".json":
                with open(input_path, "r", encoding="utf-8") as f:
                    json.load(f)
            else:
                with open(input_path, "r", encoding="utf-8", errors="replace") as f:
                    reader = csv.reader(f)
                    headers = next(reader, None)
                    if not headers:
                        issues.append("Empty or no header row in CSV")
                    else:
                        for row_idx, row in enumerate(reader):
                            if row_idx > 1000:
                                break
                            if len(row) != len(headers):
                                issues.append(f"Row {row_idx + 1}: column count mismatch ({len(row)} vs {len(headers)})")
        except json.JSONDecodeError as e:
            issues.append(f"Invalid JSON: {e}")
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
            "format": input_path.suffix.lower(),
        }

    async def to_canonical(self, records: list[dict]) -> list[dict]:
        canonical: list[dict] = []
        for rec in records:
            mapped: dict[str, Any] = self._apply_mapping(rec, KAGGLE_CANONICAL_MAP)

            known_keys = set(KAGGLE_CANONICAL_MAP.keys())
            attributes: dict[str, Any] = {}
            for key, val in rec.items():
                if key.lower() not in known_keys:
                    attributes[key] = val

            entity_id = mapped.get("entity_id") or str(hash(str(rec.get(list(rec.keys())[0], ""))))
            entity_name = mapped.get("entity_name") or entity_id
            timestamp = mapped.get("timestamp") or ""
            lat = self._safe_float(mapped.get("latitude"))
            lon = self._safe_float(mapped.get("longitude"))

            canonical.append({
                "entity_type": "kaggle_record",
                "entity_id": str(entity_id),
                "entity_name": str(entity_name),
                "timestamp": str(timestamp),
                "timestamp_precision": self._detect_timestamp_precision(timestamp),
                "latitude": lat,
                "longitude": lon,
                "location_name": mapped.get("location_name"),
                "location_code": mapped.get("location_code"),
                "attributes": attributes,
                "relationships": [],
                "source": "kaggle",
                "source_record_id": str(entity_id),
                "confidence": None,
                "metadata": {
                    "parser": "KaggleParser",
                    "version": "1.0",
                    "original_fields": list(rec.keys()),
                },
            })
        return canonical

    def _apply_mapping(self, record: dict, mapping: dict[str, str]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for src_key, dst_key in mapping.items():
            exact = record.get(src_key)
            if exact is not None:
                result[dst_key] = exact
                continue
            lower_map: dict[str, str] = {}
            for k in record:
                lower_map[k.lower()] = k
            match = lower_map.get(src_key)
            if match:
                result[dst_key] = record[match]
        return result

    def _detect_timestamp_precision(self, timestamp: str) -> str | None:
        if not timestamp:
            return None
        import re
        if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", timestamp):
            return "second"
        if re.match(r"^\d{4}-\d{2}-\d{2}$", timestamp):
            return "day"
        if re.match(r"^\d{4}-\d{2}$", timestamp):
            return "month"
        if re.match(r"^\d{4}$", timestamp):
            return "year"
        return None

    def _safe_float(self, value: Any) -> float | None:
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
