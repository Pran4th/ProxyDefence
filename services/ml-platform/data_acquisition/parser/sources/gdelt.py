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

GDELT_EVENT_FIELDS = [
    "GlobalEventID",       # 0
    "Day",                 # 1
    "MonthYear",           # 2
    "Year",                # 3
    "FractionDate",        # 4
    "Actor1Code",          # 5
    "Actor1Name",          # 6
    "Actor1CountryCode",   # 7
    "Actor1KnownGroupCode", # 8
    "Actor1EthnicCode",    # 9
    "Actor1Religion1Code", # 10
    "Actor1Religion2Code", # 11
    "Actor1Type1Code",     # 12
    "Actor1Type2Code",     # 13
    "Actor1Type3Code",     # 14
    "Actor2Code",          # 15
    "Actor2Name",          # 16
    "Actor2CountryCode",   # 17
    "Actor2KnownGroupCode", # 18
    "Actor2EthnicCode",    # 19
    "Actor2Religion1Code", # 20
    "Actor2Religion2Code", # 21
    "Actor2Type1Code",     # 22
    "Actor2Type2Code",     # 23
    "Actor2Type3Code",     # 24
    "IsRootEvent",         # 25
    "EventCode",           # 26
    "EventBaseCode",       # 27
    "EventRootCode",       # 28
    "QuadClass",           # 29
    "GoldsteinScale",      # 30
    "NumMentions",         # 31
    "NumSources",          # 32
    "NumArticles",         # 33
    "AvgTone",             # 34
    "Actor1Geo_Type",      # 35
    "Actor1Geo_FullName",  # 36
    "Actor1Geo_CountryCode", # 37
    "Actor1Geo_ADM1Code",  # 38
    "Actor1Geo_ADM2Code",  # 39
    "Actor1Geo_Lat",       # 40
    "Actor1Geo_Long",      # 41
    "Actor1Geo_FeatureID", # 42
    "Actor2Geo_Type",      # 43
    "Actor2Geo_FullName",  # 44
    "Actor2Geo_CountryCode", # 45
    "Actor2Geo_ADM1Code",  # 46
    "Actor2Geo_ADM2Code",  # 47
    "Actor2Geo_Lat",       # 48
    "Actor2Geo_Long",      # 49
    "Actor2Geo_FeatureID", # 50
    "ActionGeo_Type",      # 51
    "ActionGeo_FullName",  # 52
    "ActionGeo_CountryCode", # 53
    "ActionGeo_ADM1Code",  # 54
    "ActionGeo_ADM2Code",  # 55
    "ActionGeo_Lat",       # 56
    "ActionGeo_Long",      # 57
    "ActionGeo_FeatureID", # 58
    "DATEADDED",           # 59
    "SOURCEURL",           # 60
]

GDELT_MENTION_FIELDS = [
    "GlobalEventID", "EventTimeDate", "MentionTimeDate", "MentionType",
    "MentionSourceName", "MentionIdentifier", "SentenceID", "Actor1CharOffset",
    "Actor2CharOffset", "ActionCharOffset", "Confidence", "MentionDocLen",
    "MentionDocTone",
]

GKG_FIELDS = [
    "GKGRECORDID",           # 0
    "DATE",                  # 1
    "SourceCollectionIdentifier",  # 2
    "SourceCommonName",      # 3
    "DocumentIdentifier",    # 4
    "V1Counts",              # 5
    "V1CountsExt",           # 6
    "V2Themes",              # 7
    "V2ThemesCounts",        # 8
    "V2Locations",           # 9
    "V2LocationsExt",        # 10
    "V2Persons",             # 11
    "V2PersonsCounts",       # 12
    "V2Organizations",       # 13
    "V2OrganizationsCounts", # 14
    "V2Tone",                # 15
    "V2Dates",               # 16
    "V2GCAM",                # 17
]

GCAM_FIELDS = [
    "GlobalEventID", "EventCode", "Geo_Type", "Geo_FullName", "Geo_CountryCode",
    "Geo_ADM1Code", "Geo_ADM2Code", "Geo_Lat", "Geo_Long", "Geo_FeatureID",
]


def _parse_date(value: str) -> str:
    if len(value) == 8 and value.isdigit():
        return f"{value[:4]}-{value[4:6]}-{value[6:8]}"
    return value


def _open_csv_lines(path: Path, encoding: str = "utf-8"):
    """Open a GDELT CSV file, filtering out NUL bytes and normalizing line endings."""
    f = path.open("rb")
    try:
        for line in f:
            yield line.decode(encoding, errors="replace").replace("\x00", "").rstrip("\r\n")
    finally:
        f.close()


def _split_pipe(value: str | None) -> list[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(";") if v.strip()]


def _extract_pipe_dicts(value: str | None, keys: list[str]) -> list[dict]:
    if not value:
        return []
    items: list[dict] = []
    for part in value.split(";"):
        part = part.strip()
        if not part:
            continue
        elems = part.split(",")
        item: dict[str, str] = {}
        for i, k in enumerate(keys):
            if i < len(elems):
                item[k] = elems[i].strip()
        if item:
            items.append(item)
    return items


class GDELTEventParser(BaseParser):
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
            config.input_path,
            config.output_path,
            encoding=config.encoding,
            max_records=config.max_records,
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
        batch_size = kwargs.get("batch_size", 10000)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        schema = await self.discover_schema(input_path)

        with open(output_path, "w", encoding="utf-8", newline="") as out_f:
            writer = None
            f_iter = _open_csv_lines(input_path, encoding)
            reader = csv.reader(f_iter, delimiter="\t")
            for row_idx, row in enumerate(reader):
                if max_records is not None and records_parsed >= max_records:
                    break
                if not row or all(cell.strip() == "" for cell in row):
                    continue
                try:
                    record = self._row_to_dict(row)
                    canonical = await self.to_canonical([record])
                    if writer is None:
                        fieldnames = list(canonical[0].keys()) if canonical else []
                        writer = csv.DictWriter(out_f, fieldnames=fieldnames)
                        writer.writeheader()
                    for rec in canonical:
                        writer.writerow(rec)
                    records_parsed += 1
                except Exception as e:
                    records_failed += 1
                    errors.append({"row": row_idx, "error": str(e)})

        return ParserResult(
            source="gdelt_event",
            version="1.0",
            records_parsed=records_parsed,
            records_failed=records_failed,
            output_path=output_path,
            schema_discovered=schema,
            columns=GDELT_EVENT_FIELDS,
            row_count=records_parsed,
            duration_seconds=time.monotonic() - start,
            errors=errors,
        )

    async def discover_schema(self, input_path: Path) -> dict:
        schema: dict[str, str] = {}
        sample_count = 0
        f_iter = _open_csv_lines(input_path)
        reader = csv.reader(f_iter, delimiter="\t")
        for row in reader:
            if sample_count >= 100:
                break
            if not row:
                continue
            for i, field in enumerate(GDELT_EVENT_FIELDS):
                if i < len(row):
                    val = row[i].strip()
                    if val:
                        inferred = self._infer_type(val)
                        existing = schema.get(field)
                        if existing is None:
                            schema[field] = inferred
                        elif existing != inferred and existing == "string":
                            pass
                        elif existing != inferred:
                            schema[field] = "string"
            sample_count += 1
        for field in GDELT_EVENT_FIELDS:
            schema.setdefault(field, "string")
        return schema

    async def validate(self, input_path: Path) -> list[str]:
        issues: list[str] = []
        try:
            f_iter = _open_csv_lines(input_path)
            reader = csv.reader(f_iter, delimiter="\t")
            for row_idx, row in enumerate(reader):
                if row_idx == 0:
                    continue
                if len(row) < 10:
                    issues.append(f"Row {row_idx}: fewer than 10 columns ({len(row)})")
                if row_idx > 1000:
                    break
        except Exception as e:
            issues.append(f"File read error: {e}")
        return issues

    async def get_metadata(self, input_path: Path) -> dict:
        line_count = 0
        file_size = input_path.stat().st_size
        for _ in _open_csv_lines(input_path):
            line_count += 1
        return {
            "file_name": input_path.name,
            "file_size_bytes": file_size,
            "line_count": line_count,
            "field_count": len(GDELT_EVENT_FIELDS),
            "delimiter": "tab",
        }

    async def to_canonical(self, records: list[dict]) -> list[dict]:
        canonical: list[dict] = []
        for rec in records:
            confidence = self._compute_confidence(
                rec.get("NumSources", "0"),
                rec.get("NumMentions", "0"),
                rec.get("NumArticles", "0"),
            )
            lat = self._safe_float(rec.get("Actor1Geo_Lat"))
            lon = self._safe_float(rec.get("Actor1Geo_Long"))
            canonical.append({
                "entity_type": "event",
                "entity_id": rec.get("GlobalEventID", ""),
                "entity_name": f"{rec.get('Actor1Name', '')} - {rec.get('Actor2Name', '')}",
                "timestamp": _parse_date(rec.get("Day", "")),
                "timestamp_precision": "day",
                "latitude": lat,
                "longitude": lon,
                "location_name": rec.get("Actor1Geo_FullName"),
                "location_code": rec.get("Actor1Geo_CountryCode"),
                "attributes": {
                    "actor1_code": rec.get("Actor1Code"),
                    "actor1_name": rec.get("Actor1Name"),
                    "actor1_country": rec.get("Actor1CountryCode"),
                    "actor2_code": rec.get("Actor2Code"),
                    "actor2_name": rec.get("Actor2Name"),
                    "actor2_country": rec.get("Actor2CountryCode"),
                    "event_code": rec.get("EventCode"),
                    "goldstein_scale": self._safe_float(rec.get("GoldsteinScale")),
                    "num_mentions": self._safe_int(rec.get("NumMentions")),
                    "num_sources": self._safe_int(rec.get("NumSources")),
                    "num_articles": self._safe_int(rec.get("NumArticles")),
                    "avg_tone": self._safe_float(rec.get("AvgTone")),
                    "geo_type": rec.get("Actor1Geo_Type"),
                    "action_geo_type": self._safe_int(rec.get("ActionGeo_Type")),
                    "action_geo_fullname": rec.get("ActionGeo_FullName"),
                    "action_geo_country": rec.get("ActionGeo_CountryCode"),
                    "action_geo_lat": self._safe_float(rec.get("ActionGeo_Lat")),
                    "action_geo_lon": self._safe_float(rec.get("ActionGeo_Long")),
                    "is_root_event": self._safe_int(rec.get("IsRootEvent")),
                    "quad_class": self._safe_int(rec.get("QuadClass")),
                    "date_added": rec.get("DATEADDED"),
                    "source_url": rec.get("SOURCEURL"),
                },
                "relationships": [],
                "source": "gdelt",
                "source_record_id": rec.get("GlobalEventID"),
                "confidence": confidence,
                "metadata": {"parser": "GDELTEventParser", "version": "1.0"},
            })
        return canonical

    def _row_to_dict(self, row: list[str]) -> dict[str, str]:
        d: dict[str, str] = {}
        for i, field in enumerate(GDELT_EVENT_FIELDS):
            d[field] = row[i].strip() if i < len(row) else ""
        return d

    def _compute_confidence(self, sources: str, mentions: str, articles: str) -> float:
        s = self._safe_int(sources) or 0
        m = self._safe_int(mentions) or 0
        a = self._safe_int(articles) or 0
        score = min(1.0, (s * 0.1 + m * 0.05 + a * 0.02))
        return round(score, 4)

    def _infer_type(self, value: str) -> str:
        if re.match(r"^-?\d+\.?\d*$", value):
            return "number" if "." in value else "integer"
        if re.match(r"^\d{4}\d{2}\d{2}$", value):
            return "date"
        return "string"

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
            return int(value)
        except (ValueError, TypeError):
            return None


class GDELTMentionParser(BaseParser):
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

        with open(output_path, "w", encoding="utf-8", newline="") as out_f:
            writer = None
            f_iter = _open_csv_lines(input_path, encoding)
            reader = csv.reader(f_iter, delimiter="\t")
            for row_idx, row in enumerate(reader):
                if max_records is not None and records_parsed >= max_records:
                    break
                if not row:
                    continue
                try:
                    record = self._row_to_dict(row)
                    canonical = await self.to_canonical([record])
                    if writer is None:
                        fieldnames = list(canonical[0].keys()) if canonical else []
                        writer = csv.DictWriter(out_f, fieldnames=fieldnames)
                        writer.writeheader()
                    for rec in canonical:
                        writer.writerow(rec)
                    records_parsed += 1
                except Exception as e:
                    records_failed += 1
                    errors.append({"row": row_idx, "error": str(e)})

        return ParserResult(
            source="gdelt_mention",
            version="1.0",
            records_parsed=records_parsed,
            records_failed=records_failed,
            output_path=output_path,
            schema_discovered=schema,
            columns=GDELT_MENTION_FIELDS,
            row_count=records_parsed,
            duration_seconds=time.monotonic() - start,
            errors=errors,
        )

    async def discover_schema(self, input_path: Path) -> dict:
        schema: dict[str, str] = {}
        f_iter = _open_csv_lines(input_path)
        reader = csv.reader(f_iter, delimiter="\t")
        for row_idx, row in enumerate(reader):
            if row_idx >= 100:
                break
            for i, field in enumerate(GDELT_MENTION_FIELDS):
                if i < len(row) and row[i].strip():
                    schema[field] = self._infer_type(row[i].strip())
        for field in GDELT_MENTION_FIELDS:
            schema.setdefault(field, "string")
        return schema

    async def validate(self, input_path: Path) -> list[str]:
        issues: list[str] = []
        try:
            f_iter = _open_csv_lines(input_path)
            reader = csv.reader(f_iter, delimiter="\t")
            for row_idx, row in enumerate(reader):
                if len(row) < 5:
                    issues.append(f"Row {row_idx}: fewer than 5 columns")
                if row_idx > 1000:
                    break
        except Exception as e:
            issues.append(f"File read error: {e}")
        return issues

    async def get_metadata(self, input_path: Path) -> dict:
        line_count = 0
        for _ in _open_csv_lines(input_path):
            for _ in f:
                line_count += 1
        return {
            "file_name": input_path.name,
            "file_size_bytes": input_path.stat().st_size,
            "line_count": line_count,
            "field_count": len(GDELT_MENTION_FIELDS),
        }

    async def to_canonical(self, records: list[dict]) -> list[dict]:
        canonical: list[dict] = []
        for rec in records:
            confidence = self._safe_float(rec.get("Confidence"))
            canonical.append({
                "entity_type": "mention",
                "entity_id": rec.get("GlobalEventID", ""),
                "entity_name": f"mention_{rec.get('GlobalEventID', '')}",
                "timestamp": _parse_date(rec.get("EventTimeDate", "")),
                "timestamp_precision": "day",
                "latitude": None,
                "longitude": None,
                "location_name": None,
                "location_code": None,
                "attributes": {
                    "event_time_date": rec.get("EventTimeDate"),
                    "mention_time_date": rec.get("MentionTimeDate"),
                    "mention_type": rec.get("MentionType"),
                    "mention_source_name": rec.get("MentionSourceName"),
                    "mention_identifier": rec.get("MentionIdentifier"),
                    "sentence_id": self._safe_int(rec.get("SentenceID")),
                    "actor1_char_offset": self._safe_int(rec.get("Actor1CharOffset")),
                    "actor2_char_offset": self._safe_int(rec.get("Actor2CharOffset")),
                    "action_char_offset": self._safe_int(rec.get("ActionCharOffset")),
                    "mention_doc_len": self._safe_int(rec.get("MentionDocLen")),
                    "mention_doc_tone": self._safe_float(rec.get("MentionDocTone")),
                },
                "relationships": [{"type": "mentions_event", "target_id": rec.get("GlobalEventID")}],
                "source": "gdelt",
                "source_record_id": rec.get("GlobalEventID"),
                "confidence": confidence / 100.0 if confidence is not None else None,
                "metadata": {"parser": "GDELTMentionParser", "version": "1.0"},
            })
        return canonical

    def _row_to_dict(self, row: list[str]) -> dict[str, str]:
        d: dict[str, str] = {}
        for i, field in enumerate(GDELT_MENTION_FIELDS):
            d[field] = row[i].strip() if i < len(row) else ""
        return d

    def _infer_type(self, value: str) -> str:
        if re.match(r"^-?\d+\.?\d*$", value):
            return "number" if "." in value else "integer"
        if re.match(r"^\d{4}\d{2}\d{2}$", value):
            return "date"
        return "string"

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
            return int(value)
        except (ValueError, TypeError):
            return None


class GKGParser(BaseParser):
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

        with open(output_path, "w", encoding="utf-8", newline="") as out_f:
            writer = None
            f_iter = _open_csv_lines(input_path, encoding)
            reader = csv.reader(f_iter, delimiter="\t")
            for row_idx, row in enumerate(reader):
                if max_records is not None and records_parsed >= max_records:
                    break
                if not row:
                    continue
                try:
                    record = self._row_to_dict(row)
                    canonical = await self.to_canonical([record])
                    if writer is None:
                        fieldnames = list(canonical[0].keys()) if canonical else []
                        writer = csv.DictWriter(out_f, fieldnames=fieldnames)
                        writer.writeheader()
                    for rec in canonical:
                        writer.writerow(rec)
                    records_parsed += 1
                except Exception as e:
                    records_failed += 1
                    errors.append({"row": row_idx, "error": str(e)})

        return ParserResult(
            source="gdelt_gkg",
            version="1.0",
            records_parsed=records_parsed,
            records_failed=records_failed,
            output_path=output_path,
            schema_discovered=schema,
            columns=GKG_FIELDS,
            row_count=records_parsed,
            duration_seconds=time.monotonic() - start,
            errors=errors,
        )

    async def discover_schema(self, input_path: Path) -> dict:
        schema: dict[str, str] = {}
        f_iter = _open_csv_lines(input_path)
        reader = csv.reader(f_iter, delimiter="\t")
        for row_idx, row in enumerate(reader):
            if row_idx >= 100:
                break
            for i, field in enumerate(GKG_FIELDS):
                if i < len(row) and row[i].strip():
                    schema[field] = "string"
        for field in GKG_FIELDS:
            schema.setdefault(field, "string")
        return schema

    async def validate(self, input_path: Path) -> list[str]:
        issues: list[str] = []
        try:
            f_iter = _open_csv_lines(input_path)
            reader = csv.reader(f_iter, delimiter="\t")
            for row_idx, row in enumerate(reader):
                if len(row) < 5:
                    issues.append(f"Row {row_idx}: fewer than 5 columns")
                if row_idx > 1000:
                    break
        except Exception as e:
            issues.append(f"File read error: {e}")
        return issues

    async def get_metadata(self, input_path: Path) -> dict:
        line_count = 0
        for _ in _open_csv_lines(input_path):
            for _ in f:
                line_count += 1
        return {
            "file_name": input_path.name,
            "file_size_bytes": input_path.stat().st_size,
            "line_count": line_count,
            "field_count": len(GKG_FIELDS),
        }

    async def to_canonical(self, records: list[dict]) -> list[dict]:
        canonical: list[dict] = []
        for rec in records:
            themes = _split_pipe(rec.get("V2Themes"))
            locations_raw = _extract_pipe_dicts(
                rec.get("V2Locations"),
                ["location_name", "lat", "lon", "country_code", "location_type"],
            )
            persons = _split_pipe(rec.get("V2Persons"))
            organizations = _split_pipe(rec.get("V2Organizations"))

            tone_data = rec.get("V2Tone", "")
            tone_parts = tone_data.split(",") if tone_data else []
            tone = float(tone_parts[0]) if len(tone_parts) > 0 and tone_parts[0] else None

            canonical.append({
                "entity_type": "gkg_record",
                "entity_id": rec.get("GKGRECORDID", ""),
                "entity_name": rec.get("SourceCommonName", ""),
                "timestamp": _parse_date(rec.get("DATE", "")),
                "timestamp_precision": "day",
                "latitude": None,
                "longitude": None,
                "location_name": None,
                "location_code": None,
                "attributes": {
                    "source_collection": rec.get("SourceCollectionIdentifier"),
                    "source_common_name": rec.get("SourceCommonName"),
                    "document_identifier": rec.get("DocumentIdentifier"),
                    "themes": themes,
                    "persons": persons,
                    "organizations": organizations,
                    "locations": locations_raw,
                    "tone": tone,
                    "tone_raw": tone_data,
                },
                "relationships": [
                    {"type": "has_theme", "target_id": t} for t in themes
                ] + [
                    {"type": "has_person", "target_id": p} for p in persons
                ] + [
                    {"type": "has_organization", "target_id": o} for o in organizations
                ],
                "source": "gdelt",
                "source_record_id": rec.get("GKGRECORDID"),
                "confidence": None,
                "metadata": {"parser": "GKGParser", "version": "1.0"},
            })
        return canonical

    def _row_to_dict(self, row: list[str]) -> dict[str, str]:
        d: dict[str, str] = {}
        for i, field in enumerate(GKG_FIELDS):
            d[field] = row[i].strip() if i < len(row) else ""
        return d


class GCAMParser(BaseParser):
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

        with open(output_path, "w", encoding="utf-8", newline="") as out_f:
            writer = None
            f_iter = _open_csv_lines(input_path, encoding)
            reader = csv.reader(f_iter, delimiter="\t")
            for row_idx, row in enumerate(reader):
                if max_records is not None and records_parsed >= max_records:
                    break
                if not row:
                    continue
                try:
                    record = self._row_to_dict(row)
                    canonical = await self.to_canonical([record])
                    if writer is None:
                        fieldnames = list(canonical[0].keys()) if canonical else []
                        writer = csv.DictWriter(out_f, fieldnames=fieldnames)
                        writer.writeheader()
                    for rec in canonical:
                        writer.writerow(rec)
                    records_parsed += 1
                except Exception as e:
                    records_failed += 1
                    errors.append({"row": row_idx, "error": str(e)})

        return ParserResult(
            source="gdelt_gcam",
            version="1.0",
            records_parsed=records_parsed,
            records_failed=records_failed,
            output_path=output_path,
            schema_discovered=schema,
            columns=GCAM_FIELDS,
            row_count=records_parsed,
            duration_seconds=time.monotonic() - start,
            errors=errors,
        )

    async def discover_schema(self, input_path: Path) -> dict:
        schema: dict[str, str] = {}
        f_iter = _open_csv_lines(input_path)
        reader = csv.reader(f_iter, delimiter="\t")
        for row_idx, row in enumerate(reader):
            if row_idx >= 100:
                break
            for i, field in enumerate(GCAM_FIELDS):
                if i < len(row) and row[i].strip():
                    schema[field] = "string"
        for field in GCAM_FIELDS:
            schema.setdefault(field, "string")
        return schema

    async def validate(self, input_path: Path) -> list[str]:
        issues: list[str] = []
        try:
            f_iter = _open_csv_lines(input_path)
            reader = csv.reader(f_iter, delimiter="\t")
            for row_idx, row in enumerate(reader):
                if len(row) < 5:
                    issues.append(f"Row {row_idx}: fewer than 5 columns")
                if row_idx > 1000:
                    break
        except Exception as e:
            issues.append(f"File read error: {e}")
        return issues

    async def get_metadata(self, input_path: Path) -> dict:
        line_count = 0
        for _ in _open_csv_lines(input_path):
            for _ in f:
                line_count += 1
        return {
            "file_name": input_path.name,
            "file_size_bytes": input_path.stat().st_size,
            "line_count": line_count,
            "field_count": len(GCAM_FIELDS),
        }

    async def to_canonical(self, records: list[dict]) -> list[dict]:
        canonical: list[dict] = []
        for rec in records:
            lat = self._safe_float(rec.get("Geo_Lat"))
            lon = self._safe_float(rec.get("Geo_Long"))
            canonical.append({
                "entity_type": "geographic_event",
                "entity_id": rec.get("GlobalEventID", ""),
                "entity_name": rec.get("Geo_FullName", ""),
                "timestamp": None,
                "timestamp_precision": None,
                "latitude": lat,
                "longitude": lon,
                "location_name": rec.get("Geo_FullName"),
                "location_code": rec.get("Geo_CountryCode"),
                "attributes": {
                    "event_code": rec.get("EventCode"),
                    "geo_type": rec.get("Geo_Type"),
                    "geo_adm1_code": rec.get("Geo_ADM1Code"),
                    "geo_adm2_code": rec.get("Geo_ADM2Code"),
                    "geo_feature_id": rec.get("Geo_FeatureID"),
                },
                "relationships": [
                    {"type": "located_in", "target_id": rec.get("Geo_CountryCode")},
                ],
                "source": "gdelt",
                "source_record_id": rec.get("GlobalEventID"),
                "confidence": None,
                "metadata": {"parser": "GCAMParser", "version": "1.0"},
            })
        return canonical

    def _row_to_dict(self, row: list[str]) -> dict[str, str]:
        d: dict[str, str] = {}
        for i, field in enumerate(GCAM_FIELDS):
            d[field] = row[i].strip() if i < len(row) else ""
        return d

    def _safe_float(self, value: str | None) -> float | None:
        if value is None or value.strip() == "":
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
