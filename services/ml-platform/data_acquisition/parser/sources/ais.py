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

AIS_FIELDS = [
    "MMSI", "Timestamp", "Latitude", "Longitude", "Speed", "Course",
    "Heading", "Destination", "ShipName", "ShipType", "Length", "Width",
    "Draft", "CargoType", "Status",
]

PORT_CONGESTION_FIELDS = [
    "port_name", "port_code", "country", "region", "date",
    "waiting_days", "vessel_count", "capacity_mt", "congestion_level",
]

WORLD_PORT_INDEX_FIELDS = [
    "port_name", "country_code", "latitude", "longitude", "UNLOCODE",
    "harbor_type", "max_draft", "max_length", "tug_assist",
    "fuel_available", "cargo_types",
]


class AISParser(BaseParser):
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

        geo = kwargs.get("geojson", False)
        canonical_records: list[dict] = []
        features: list[dict] = []

        if suffix == ".json":
            with open(input_path, "r", encoding=encoding) as f:
                data = json.load(f)
            positions = data if isinstance(data, list) else data.get("positions", data.get("data", [data]))
            for item in positions:
                if max_records is not None and records_parsed >= max_records:
                    break
                try:
                    rec = {
                        "MMSI": str(item.get("MMSI", item.get("mmsi", ""))),
                        "Timestamp": item.get("Timestamp", item.get("timestamp", item.get("time", ""))),
                        "Latitude": item.get("Latitude", item.get("lat", item.get("latitude"))),
                        "Longitude": item.get("Longitude", item.get("lon", item.get("lng", item.get("longitude")))),
                        "Speed": item.get("Speed", item.get("speed", item.get("sog"))),
                        "Course": item.get("Course", item.get("course", item.get("cog"))),
                        "Heading": item.get("Heading", item.get("heading")),
                        "Destination": item.get("Destination", item.get("destination", "")),
                        "ShipName": item.get("ShipName", item.get("ship_name", item.get("name", ""))),
                        "ShipType": item.get("ShipType", item.get("ship_type", item.get("type", ""))),
                        "Length": item.get("Length", item.get("length", item.get("dim_length"))),
                        "Width": item.get("Width", item.get("width", item.get("dim_width"))),
                        "Draft": item.get("Draft", item.get("draft")),
                        "CargoType": item.get("CargoType", item.get("cargo_type", "")),
                        "Status": item.get("Status", item.get("status", "")),
                    }
                    canonical = await self.to_canonical([rec])
                    canonical_records.extend(canonical)
                    if geo:
                        features.append(self._to_geojson_feature(rec))
                    records_parsed += 1
                except Exception as e:
                    records_failed += 1
                    errors.append({"mmsi": item.get("MMSI"), "error": str(e)})
        else:
            with open(input_path, "r", encoding=encoding) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if max_records is not None and records_parsed >= max_records:
                        break
                    try:
                        rec = {
                            "MMSI": row.get("MMSI", row.get("mmsi", "")),
                            "Timestamp": row.get("Timestamp", row.get("timestamp", row.get("time", ""))),
                            "Latitude": row.get("Latitude", row.get("lat", row.get("latitude"))),
                            "Longitude": row.get("Longitude", row.get("lon", row.get("lng", row.get("longitude")))),
                            "Speed": row.get("Speed", row.get("speed", row.get("sog"))),
                            "Course": row.get("Course", row.get("course", row.get("cog"))),
                            "Heading": row.get("Heading", row.get("heading")),
                            "Destination": row.get("Destination", row.get("destination", "")),
                            "ShipName": row.get("ShipName", row.get("ship_name", row.get("name", ""))),
                            "ShipType": row.get("ShipType", row.get("ship_type", row.get("type", ""))),
                            "Length": row.get("Length", row.get("length", row.get("dim_length"))),
                            "Width": row.get("Width", row.get("width", row.get("dim_width"))),
                            "Draft": row.get("Draft", row.get("draft")),
                            "CargoType": row.get("CargoType", row.get("cargo_type", "")),
                            "Status": row.get("Status", row.get("status", "")),
                        }
                        canonical = await self.to_canonical([rec])
                        canonical_records.extend(canonical)
                        if geo:
                            features.append(self._to_geojson_feature(rec))
                        records_parsed += 1
                    except Exception as e:
                        records_failed += 1
                        errors.append({"row": records_parsed, "error": str(e)})

        if geo:
            geojson = {
                "type": "FeatureCollection",
                "features": features,
            }
            output_path = output_path.with_suffix(".geojson")
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(geojson, f, indent=2)
        else:
            with open(output_path, "w", encoding="utf-8", newline="") as out_f:
                if canonical_records:
                    writer = csv.DictWriter(out_f, fieldnames=list(canonical_records[0].keys()))
                    writer.writeheader()
                    writer.writerows(canonical_records)

        return ParserResult(
            source="ais",
            version="1.0",
            records_parsed=records_parsed,
            records_failed=records_failed,
            output_path=output_path,
            schema_discovered=schema,
            columns=AIS_FIELDS,
            row_count=records_parsed,
            duration_seconds=time.monotonic() - start,
            errors=errors,
        )

    def _to_geojson_feature(self, rec: dict) -> dict:
        lat = self._safe_float(rec.get("Latitude"))
        lon = self._safe_float(rec.get("Longitude"))
        return {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat] if lat is not None and lon is not None else [0, 0],
            },
            "properties": {
                "mmsi": rec.get("MMSI"),
                "timestamp": rec.get("Timestamp"),
                "speed": self._safe_float(rec.get("Speed")),
                "course": self._safe_float(rec.get("Course")),
                "heading": self._safe_float(rec.get("Heading")),
                "ship_name": rec.get("ShipName"),
                "ship_type": rec.get("ShipType"),
                "destination": rec.get("Destination"),
                "cargo_type": rec.get("CargoType"),
                "status": rec.get("Status"),
            },
        }

    async def discover_schema(self, input_path: Path) -> dict:
        return {
            "MMSI": "string",
            "Timestamp": "string",
            "Latitude": "number",
            "Longitude": "number",
            "Speed": "number",
            "Course": "number",
            "Heading": "number",
            "Destination": "string",
            "ShipName": "string",
            "ShipType": "string",
            "Length": "number",
            "Width": "number",
            "Draft": "number",
            "CargoType": "string",
            "Status": "string",
        }

    async def validate(self, input_path: Path) -> list[str]:
        issues: list[str] = []
        try:
            with open(input_path, "r", encoding="utf-8", errors="replace") as f:
                if input_path.suffix.lower() == ".json":
                    data = json.load(f)
                    items = data if isinstance(data, list) else data.get("positions", data.get("data", []))
                    if not items:
                        issues.append("No position data found")
                else:
                    reader = csv.DictReader(f)
                    for row_idx, row in enumerate(reader):
                        if row_idx > 1000:
                            break
                        lat = self._safe_float(row.get("Latitude", row.get("lat", "")))
                        lon = self._safe_float(row.get("Longitude", row.get("lon", "")))
                        if lat is not None and (lat < -90 or lat > 90):
                            issues.append(f"Row {row_idx}: latitude out of range ({lat})")
                        if lon is not None and (lon < -180 or lon > 180):
                            issues.append(f"Row {row_idx}: longitude out of range ({lon})")
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
            "field_count": len(AIS_FIELDS),
        }

    async def to_canonical(self, records: list[dict]) -> list[dict]:
        canonical: list[dict] = []
        for rec in records:
            lat = self._safe_float(rec.get("Latitude"))
            lon = self._safe_float(rec.get("Longitude"))
            canonical.append({
                "entity_type": "vessel",
                "entity_id": rec.get("MMSI", ""),
                "entity_name": rec.get("ShipName", f"Vessel {rec.get('MMSI', '')}"),
                "timestamp": rec.get("Timestamp", ""),
                "timestamp_precision": "second",
                "latitude": lat,
                "longitude": lon,
                "location_name": None,
                "location_code": None,
                "attributes": {
                    "mmsi": rec.get("MMSI"),
                    "speed": self._safe_float(rec.get("Speed")),
                    "course": self._safe_float(rec.get("Course")),
                    "heading": self._safe_float(rec.get("Heading")),
                    "destination": rec.get("Destination"),
                    "ship_type": rec.get("ShipType"),
                    "length": self._safe_float(rec.get("Length")),
                    "width": self._safe_float(rec.get("Width")),
                    "draft": self._safe_float(rec.get("Draft")),
                    "cargo_type": rec.get("CargoType"),
                    "status": rec.get("Status"),
                },
                "relationships": [
                    {"type": "destination_port", "target_id": rec.get("Destination")},
                ],
                "source": "ais",
                "source_record_id": rec.get("MMSI"),
                "confidence": None,
                "metadata": {"parser": "AISParser", "version": "1.0"},
            })
        return canonical

    def _safe_float(self, value: Any) -> float | None:
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None


class PortCongestionParser(BaseParser):
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
                        "port_name": row.get("port_name", row.get("Port", row.get("port", ""))),
                        "port_code": row.get("port_code", row.get("port_code", row.get("code", ""))),
                        "country": row.get("country", row.get("Country", "")),
                        "region": row.get("region", row.get("Region", "")),
                        "date": row.get("date", row.get("Date", row.get("timestamp", ""))),
                        "waiting_days": row.get("waiting_days", row.get("waiting_days", row.get("wait_time", ""))),
                        "vessel_count": row.get("vessel_count", row.get("vessel_count", row.get("vessels", ""))),
                        "capacity_mt": row.get("capacity_mt", row.get("capacity_mt", row.get("capacity", ""))),
                        "congestion_level": row.get("congestion_level", row.get("congestion", row.get("level", ""))),
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
            source="port_congestion",
            version="1.0",
            records_parsed=records_parsed,
            records_failed=records_failed,
            output_path=output_path,
            schema_discovered=schema,
            columns=PORT_CONGESTION_FIELDS,
            row_count=records_parsed,
            duration_seconds=time.monotonic() - start,
            errors=errors,
        )

    async def discover_schema(self, input_path: Path) -> dict:
        return {
            "port_name": "string",
            "port_code": "string",
            "country": "string",
            "region": "string",
            "date": "string",
            "waiting_days": "number",
            "vessel_count": "integer",
            "capacity_mt": "number",
            "congestion_level": "string",
        }

    async def validate(self, input_path: Path) -> list[str]:
        issues: list[str] = []
        try:
            with open(input_path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for row_idx, row in enumerate(reader):
                    if row_idx > 1000:
                        break
                    if not row.get("port_name", "").strip():
                        issues.append(f"Row {row_idx}: missing port_name")
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
            "field_count": len(PORT_CONGESTION_FIELDS),
        }

    async def to_canonical(self, records: list[dict]) -> list[dict]:
        canonical: list[dict] = []
        for rec in records:
            congestion_map = {
                "low": 0.2, "moderate": 0.4, "medium": 0.5, "high": 0.7, "severe": 0.9, "critical": 1.0,
            }
            cl = rec.get("congestion_level", "").lower().strip()
            confidence = congestion_map.get(cl, None)
            canonical.append({
                "entity_type": "port_congestion",
                "entity_id": f"{rec['port_code']}_{rec['date']}",
                "entity_name": f"{rec['port_name']} Congestion",
                "timestamp": rec.get("date", ""),
                "timestamp_precision": "day",
                "latitude": None,
                "longitude": None,
                "location_name": rec.get("port_name"),
                "location_code": rec.get("port_code"),
                "attributes": {
                    "port_name": rec.get("port_name"),
                    "port_code": rec.get("port_code"),
                    "country": rec.get("country"),
                    "region": rec.get("region"),
                    "waiting_days": self._safe_float(rec.get("waiting_days")),
                    "vessel_count": self._safe_int(rec.get("vessel_count")),
                    "capacity_mt": self._safe_float(rec.get("capacity_mt")),
                    "congestion_level": rec.get("congestion_level"),
                },
                "relationships": [
                    {"type": "located_in", "target_id": rec.get("country")},
                ],
                "source": "port_congestion",
                "source_record_id": f"{rec['port_code']}_{rec['date']}",
                "confidence": confidence,
                "metadata": {"parser": "PortCongestionParser", "version": "1.0"},
            })
        return canonical

    def _safe_float(self, value: str | None) -> float | None:
        if value is None or value.strip() == "":
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _safe_int(self, value: str | None) -> int | None:
        if value is None or value.strip() == "":
            return None
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None


class WorldPortIndexParser(BaseParser):
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
        suffix = input_path.suffix.lower()

        if suffix == ".csv":
            with open(input_path, "r", encoding=encoding) as f:
                reader = csv.DictReader(f)
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
        elif suffix == ".txt":
            with open(input_path, "r", encoding=encoding) as f:
                for line_idx, line in enumerate(f):
                    if max_records is not None and records_parsed >= max_records:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        fields = re.split(r"\s{2,}", line)
                        rec = {
                            "port_name": fields[0].strip() if len(fields) > 0 else "",
                            "country_code": fields[1].strip() if len(fields) > 1 else "",
                            "latitude": fields[2].strip() if len(fields) > 2 else "",
                            "longitude": fields[3].strip() if len(fields) > 3 else "",
                            "UNLOCODE": fields[4].strip() if len(fields) > 4 else "",
                            "harbor_type": fields[5].strip() if len(fields) > 5 else "",
                            "max_draft": fields[6].strip() if len(fields) > 6 else "",
                            "max_length": fields[7].strip() if len(fields) > 7 else "",
                            "tug_assist": fields[8].strip() if len(fields) > 8 else "",
                            "fuel_available": fields[9].strip() if len(fields) > 9 else "",
                            "cargo_types": fields[10].strip() if len(fields) > 10 else "",
                        }
                        canonical = await self.to_canonical([rec])
                        canonical_records.extend(canonical)
                        records_parsed += 1
                    except Exception as e:
                        records_failed += 1
                        errors.append({"line": line_idx, "error": str(e)})

        with open(output_path, "w", encoding="utf-8", newline="") as out_f:
            if canonical_records:
                writer = csv.DictWriter(out_f, fieldnames=list(canonical_records[0].keys()))
                writer.writeheader()
                writer.writerows(canonical_records)

        return ParserResult(
            source="world_port_index",
            version="1.0",
            records_parsed=records_parsed,
            records_failed=records_failed,
            output_path=output_path,
            schema_discovered=schema,
            columns=WORLD_PORT_INDEX_FIELDS,
            row_count=records_parsed,
            duration_seconds=time.monotonic() - start,
            errors=errors,
        )

    async def discover_schema(self, input_path: Path) -> dict:
        return {
            "port_name": "string",
            "country_code": "string",
            "latitude": "number",
            "longitude": "number",
            "UNLOCODE": "string",
            "harbor_type": "string",
            "max_draft": "number",
            "max_length": "number",
            "tug_assist": "string",
            "fuel_available": "string",
            "cargo_types": "string",
        }

    async def validate(self, input_path: Path) -> list[str]:
        issues: list[str] = []
        try:
            with open(input_path, "r", encoding="utf-8", errors="replace") as f:
                for line_idx, line in enumerate(f):
                    if line_idx > 1000:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    fields = re.split(r"\s{2,}", line)
                    if len(fields) < 5:
                        issues.append(f"Line {line_idx}: fewer than 5 fields expected")
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
            "field_count": len(WORLD_PORT_INDEX_FIELDS),
        }

    async def to_canonical(self, records: list[dict]) -> list[dict]:
        canonical: list[dict] = []
        for rec in records:
            lat = self._safe_float(rec.get("latitude"))
            lon = self._safe_float(rec.get("longitude"))
            canonical.append({
                "entity_type": "port",
                "entity_id": rec.get("UNLOCODE", rec.get("port_name", "")),
                "entity_name": rec.get("port_name", ""),
                "timestamp": None,
                "timestamp_precision": None,
                "latitude": lat,
                "longitude": lon,
                "location_name": rec.get("port_name"),
                "location_code": rec.get("UNLOCODE"),
                "attributes": {
                    "port_name": rec.get("port_name"),
                    "country_code": rec.get("country_code"),
                    "harbor_type": rec.get("harbor_type"),
                    "max_draft": self._safe_float(rec.get("max_draft")),
                    "max_length": self._safe_float(rec.get("max_length")),
                    "tug_assist": rec.get("tug_assist"),
                    "fuel_available": rec.get("fuel_available"),
                    "cargo_types": rec.get("cargo_types"),
                    "unlocode": rec.get("UNLOCODE"),
                },
                "relationships": [
                    {"type": "located_in_country", "target_id": rec.get("country_code")},
                ],
                "source": "world_port_index",
                "source_record_id": rec.get("UNLOCODE"),
                "confidence": None,
                "metadata": {"parser": "WorldPortIndexParser", "version": "1.0"},
            })
        return canonical

    def _safe_float(self, value: str | None) -> float | None:
        if value is None or value.strip() == "":
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
