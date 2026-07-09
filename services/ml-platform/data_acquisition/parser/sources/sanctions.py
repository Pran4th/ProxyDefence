from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Any

from backend.shared.logging_config import get_logger
from data_acquisition.parser.base import BaseParser, ParseConfig, ParserResult

logger = get_logger(__name__)


OFAC_FIELDS = ["ent_num", "sdn_name", "sdn_type", "program", "list", "score", "remarks"]
UN_SANCTIONS_FIELDS = ["individual_name", "entity_name", "identifier", "type", "sanctions_program", "listed_date"]

# Official Treasury sdn.csv layout: no header row, fixed 12-column position.
# https://www.treasury.gov/ofac/downloads/sdn.csv
OFAC_SDN_RAW_COLUMNS = [
    "ent_num", "sdn_name", "sdn_type", "program", "title", "call_sign",
    "vess_type", "tonnage", "grt", "vess_flag", "vess_owner", "remarks",
]


class OFACParser(BaseParser):
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

        if suffix == ".json":
            with open(input_path, "r", encoding=encoding) as f:
                data = json.load(f)
            entries = data if isinstance(data, list) else data.get("sdn_entries", data.get("matches", data.get("data", [])))
            for entry in entries:
                if max_records is not None and records_parsed >= max_records:
                    break
                try:
                    rec = {
                        "ent_num": str(entry.get("ent_num", entry.get("uid", entry.get("id", "")))),
                        "sdn_name": entry.get("sdn_name", entry.get("name", entry.get("Name", ""))),
                        "sdn_type": entry.get("sdn_type", entry.get("type", entry.get("Type", ""))),
                        "program": entry.get("program", entry.get("Program", entry.get("programs", ""))),
                        "list": entry.get("list", entry.get("List", "")),
                        "score": str(entry.get("score", entry.get("Score", ""))),
                        "remarks": entry.get("remarks", entry.get("Remarks", "")),
                    }
                    canonical = await self.to_canonical([rec])
                    canonical_records.extend(canonical)
                    records_parsed += 1
                except Exception as e:
                    records_failed += 1
                    errors.append({"uid": entry.get("ent_num", ""), "error": str(e)})
        else:
            with open(input_path, "r", encoding=encoding) as f:
                sniff = f.readline()
                f.seek(0)
                first_field = sniff.split(",", 1)[0].strip().strip('"')
                is_headerless_sdn = first_field.isdigit()

                if is_headerless_sdn:
                    reader = csv.reader(f)
                    for row_idx, fields in enumerate(reader):
                        if max_records is not None and records_parsed >= max_records:
                            break
                        if not fields or not fields[0].strip():
                            continue
                        try:
                            padded = fields + [""] * (len(OFAC_SDN_RAW_COLUMNS) - len(fields))
                            raw = dict(zip(OFAC_SDN_RAW_COLUMNS, padded))
                            na = lambda v: "" if v.strip() in ("-0-", "") else v.strip()
                            rec = {
                                "ent_num": na(raw["ent_num"]),
                                "sdn_name": na(raw["sdn_name"]),
                                "sdn_type": na(raw["sdn_type"]),
                                "program": na(raw["program"]),
                                "list": "SDN",
                                "score": "",
                                "remarks": na(raw["remarks"]),
                            }
                            canonical = await self.to_canonical([rec])
                            canonical_records.extend(canonical)
                            records_parsed += 1
                        except Exception as e:
                            records_failed += 1
                            errors.append({"row": row_idx, "error": str(e)})
                else:
                    reader = csv.DictReader(f)
                    for row_idx, row in enumerate(reader):
                        if max_records is not None and records_parsed >= max_records:
                            break
                        try:
                            rec = {
                                "ent_num": row.get("ent_num", row.get("uid", row.get("ENT_NUM", ""))),
                                "sdn_name": row.get("sdn_name", row.get("name", row.get("SDN_NAME", ""))),
                                "sdn_type": row.get("sdn_type", row.get("type", row.get("SDN_TYPE", ""))),
                                "program": row.get("program", row.get("Program", row.get("programs", ""))),
                                "list": row.get("list", row.get("List", "")),
                                "score": row.get("score", row.get("Score", "")),
                                "remarks": row.get("remarks", row.get("Remarks", "")),
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
            source="ofac",
            version="1.0",
            records_parsed=records_parsed,
            records_failed=records_failed,
            output_path=output_path,
            schema_discovered=schema,
            columns=OFAC_FIELDS,
            row_count=records_parsed,
            duration_seconds=time.monotonic() - start,
            errors=errors,
        )

    async def discover_schema(self, input_path: Path) -> dict:
        return {
            "ent_num": "string",
            "sdn_name": "string",
            "sdn_type": "string",
            "program": "string",
            "list": "string",
            "score": "string",
            "remarks": "string",
        }

    async def validate(self, input_path: Path) -> list[str]:
        issues: list[str] = []
        try:
            with open(input_path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for row_idx, row in enumerate(reader):
                    if row_idx > 1000:
                        break
                    if not row.get("sdn_name", "").strip() and not row.get("SDN_NAME", "").strip():
                        issues.append(f"Row {row_idx}: missing sdn_name")
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
            "field_count": len(OFAC_FIELDS),
        }

    async def to_canonical(self, records: list[dict]) -> list[dict]:
        canonical: list[dict] = []
        for rec in records:
            programs = [p.strip() for p in rec.get("program", "").split(";") if p.strip()] if rec.get("program") else []
            canonical.append({
                "entity_type": "sanctioned_entity",
                "entity_id": rec.get("ent_num", ""),
                "entity_name": rec.get("sdn_name", ""),
                "timestamp": None,
                "timestamp_precision": None,
                "latitude": None,
                "longitude": None,
                "location_name": None,
                "location_code": None,
                "attributes": {
                    "ent_num": rec.get("ent_num"),
                    "sdn_name": rec.get("sdn_name"),
                    "sdn_type": rec.get("sdn_type"),
                    "program": programs,
                    "list_name": rec.get("list"),
                    "score": rec.get("score"),
                    "remarks": rec.get("remarks"),
                },
                "relationships": [
                    {"type": "subject_to_program", "target_id": p} for p in programs
                ],
                "source": "ofac",
                "source_record_id": rec.get("ent_num"),
                "confidence": None,
                "metadata": {"parser": "OFACParser", "version": "1.0"},
            })
        return canonical


class UNSanctionsParser(BaseParser):
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
                        "individual_name": row.get("individual_name", row.get("Individual", row.get("name", row.get("Name", "")))),
                        "entity_name": row.get("entity_name", row.get("Entity", row.get("organization", ""))),
                        "identifier": row.get("identifier", row.get("Identifier", row.get("id", row.get("ID", "")))),
                        "type": row.get("type", row.get("Type", "")),
                        "sanctions_program": row.get("sanctions_program", row.get("Program", row.get("program", ""))),
                        "listed_date": row.get("listed_date", row.get("date", row.get("Date", row.get("listed", "")))),
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
            source="un_sanctions",
            version="1.0",
            records_parsed=records_parsed,
            records_failed=records_failed,
            output_path=output_path,
            schema_discovered=schema,
            columns=UN_SANCTIONS_FIELDS,
            row_count=records_parsed,
            duration_seconds=time.monotonic() - start,
            errors=errors,
        )

    async def discover_schema(self, input_path: Path) -> dict:
        return {
            "individual_name": "string",
            "entity_name": "string",
            "identifier": "string",
            "type": "string",
            "sanctions_program": "string",
            "listed_date": "string",
        }

    async def validate(self, input_path: Path) -> list[str]:
        issues: list[str] = []
        try:
            with open(input_path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for row_idx, row in enumerate(reader):
                    if row_idx > 1000:
                        break
                    has_individual = bool(row.get("individual_name", "").strip() or row.get("Individual", "").strip())
                    has_entity = bool(row.get("entity_name", "").strip() or row.get("Entity", "").strip())
                    if not has_individual and not has_entity:
                        issues.append(f"Row {row_idx}: missing both individual and entity name")
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
            "field_count": len(UN_SANCTIONS_FIELDS),
        }

    async def to_canonical(self, records: list[dict]) -> list[dict]:
        canonical: list[dict] = []
        for rec in records:
            name = rec.get("individual_name") or rec.get("entity_name") or ""
            entity_id = rec.get("identifier", name)
            entity_type = "sanctioned_individual" if rec.get("individual_name") else "sanctioned_entity"
            programs = [p.strip() for p in rec.get("sanctions_program", "").split(";") if p.strip()] if rec.get("sanctions_program") else []
            canonical.append({
                "entity_type": entity_type,
                "entity_id": entity_id,
                "entity_name": name,
                "timestamp": rec.get("listed_date", ""),
                "timestamp_precision": "day" if rec.get("listed_date") else None,
                "latitude": None,
                "longitude": None,
                "location_name": None,
                "location_code": None,
                "attributes": {
                    "individual_name": rec.get("individual_name"),
                    "entity_name": rec.get("entity_name"),
                    "identifier": rec.get("identifier"),
                    "type": rec.get("type"),
                    "sanctions_program": programs,
                    "listed_date": rec.get("listed_date"),
                },
                "relationships": [
                    {"type": "subject_to_program", "target_id": p} for p in programs
                ],
                "source": "un_sanctions",
                "source_record_id": entity_id,
                "confidence": None,
                "metadata": {"parser": "UNSanctionsParser", "version": "1.0"},
            })
        return canonical
