from __future__ import annotations

import re
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)

ISO_COUNTRY_MAP: dict[str, str] = {
    "us": "US", "usa": "US", "united states": "US", "united states of america": "US",
    "uk": "GB", "gb": "GB", "united kingdom": "GB", "great britain": "GB",
    "uae": "AE", "ae": "AE", "united arab emirates": "AE",
    "sa": "SA", "saudi arabia": "SA", "ksa": "SA",
    "ir": "IR", "iran": "IR", "islamic republic of iran": "IR",
    "iq": "IQ", "iraq": "IQ", "republic of iraq": "IQ",
    "kw": "KW", "kuwait": "KW", "state of kuwait": "KW",
    "qa": "QA", "qatar": "QA", "state of qatar": "QA",
    "om": "OM", "oman": "OM", "sultanate of oman": "OM",
    "bh": "BH", "bahrain": "BH", "kingdom of bahrain": "BH",
    "ru": "RU", "russia": "RU", "russian federation": "RU",
    "cn": "CN", "china": "CN", "people's republic of china": "CN",
    "in": "IN", "india": "IN", "republic of india": "IN",
    "jp": "JP", "japan": "JP",
    "kr": "KR", "south korea": "KR", "republic of korea": "KR",
    "sg": "SG", "singapore": "SG", "republic of singapore": "SG",
    "my": "MY", "malaysia": "MY",
    "id": "ID", "indonesia": "ID",
    "ng": "NG", "nigeria": "NG",
    "ao": "AO", "angola": "AO",
    "dz": "DZ", "algeria": "DZ",
    "ly": "LY", "libya": "LY",
    "ve": "VE", "venezuela": "VE",
    "mx": "MX", "mexico": "MX",
    "ca": "CA", "canada": "CA",
    "no": "NO", "norway": "NO",
    "nl": "NL", "netherlands": "NL",
    "de": "DE", "germany": "DE",
    "fr": "FR", "france": "FR",
    "it": "IT", "italy": "IT",
    "es": "ES", "spain": "ES",
    "au": "AU", "australia": "AU",
    "br": "BR", "brazil": "BR",
    "ar": "AR", "argentina": "AR",
    "eg": "EG", "egypt": "EG",
    "za": "ZA", "south africa": "ZA",
    "tr": "TR", "turkey": "TR",
    "th": "TH", "thailand": "TH",
    "vn": "VN", "vietnam": "VN",
}

COUNTRY_CONTINENT: dict[str, str] = {
    "US": "north_america", "CA": "north_america", "MX": "north_america",
    "GB": "europe", "DE": "europe", "FR": "europe", "IT": "europe",
    "ES": "europe", "NL": "europe", "NO": "europe", "RU": "europe",
    "SA": "middle_east", "AE": "middle_east", "QA": "middle_east",
    "KW": "middle_east", "OM": "middle_east", "BH": "middle_east",
    "IR": "middle_east", "IQ": "middle_east",
    "CN": "asia", "IN": "asia", "JP": "asia", "KR": "asia",
    "SG": "asia", "MY": "asia", "TH": "asia", "VN": "asia",
    "NG": "africa", "AO": "africa", "DZ": "africa", "LY": "africa",
    "EG": "africa", "ZA": "africa",
    "BR": "south_america", "AR": "south_america", "VE": "south_america",
    "AU": "oceania",
    "TR": "europe",
}

SOURCE_RELIABILITY: dict[str, float] = {
    "gnews": 0.85, "gdelt": 0.80, "eia": 0.95, "opec": 0.90,
    "world_bank": 0.95, "imf": 0.95, "fao": 0.90, "comtrade": 0.90,
    "kaggle": 0.60, "reuters": 0.85, "bloomberg": 0.85,
    "energy_service": 0.90, "manual": 0.50, "unknown": 0.50,
}


@dataclass
class NormalizationLog:
    record_id: str
    original_record_id: str
    transformations: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    original_hash: str = ""
    normalized_hash: str = ""

    def add_transform(self, field: str, original: Any, normalized: Any, rule: str = ""):
        self.transformations.append({
            "field": field,
            "original": str(original),
            "normalized": str(normalized),
            "rule": rule,
        })

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def add_error(self, msg: str):
        self.errors.append(msg)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "original_record_id": self.original_record_id,
            "transformations_count": len(self.transformations),
            "transformations": self.transformations,
            "warnings": self.warnings,
            "errors": self.errors,
            "original_hash": self.original_hash,
            "normalized_hash": self.normalized_hash,
        }


@dataclass
class NormalizedRecord:
    normalized_id: str = ""
    original_id: str = ""
    entity_type: str = ""
    entity_name: str = ""
    source: str = ""
    source_reliability: float = 0.5

    iso_country: str = ""
    country_name: str = ""
    continent: str = ""
    region: str = ""
    iso_alpha3: str = ""
    iso_numeric: str = ""

    organization: str = ""
    organization_type: str = ""
    organization_normalized: str = ""

    persons: list[str] = field(default_factory=list)
    persons_normalized: list[str] = field(default_factory=list)

    timestamp: str = ""
    timestamp_normalized: str = ""
    timestamp_timezone: str = "UTC"
    timestamp_precision: str = ""
    year: int = 0
    month: int = 0
    day: int = 0
    hour: int = 0
    dow: int = 0
    weekend: bool = False

    latitude: float | None = None
    longitude: float | None = None
    coordinate_valid: bool = False
    location_name: str = ""
    location_code: str = ""

    confidence: float = 1.0
    confidence_recalculated: float = 1.0

    duplicate_of: str = ""
    is_duplicate: bool = False
    entity_resolution_key: str = ""

    attributes: dict[str, Any] = field(default_factory=dict)
    relationships: list[dict] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    schema_valid: bool = True
    relationship_valid: bool = True
    validation_errors: list[str] = field(default_factory=list)

    trace: NormalizationLog | None = None

    def to_dict(self) -> dict[str, Any]:
        d = {k: v for k, v in self.__dict__.items() if not k.startswith("_")}
        if self.trace:
            d["trace"] = self.trace.to_dict()
        return d

    def to_flat_dict(self) -> dict[str, Any]:
        return {
            "normalized_id": self.normalized_id,
            "original_id": self.original_id,
            "entity_type": self.entity_type,
            "entity_name": self.entity_name,
            "source": self.source,
            "source_reliability": self.source_reliability,
            "iso_country": self.iso_country,
            "country_name": self.country_name,
            "continent": self.continent,
            "region": self.region,
            "organization": self.organization,
            "organization_type": self.organization_type,
            "timestamp_normalized": self.timestamp_normalized,
            "timestamp_precision": self.timestamp_precision,
            "year": self.year,
            "month": self.month,
            "day": self.day,
            "hour": self.hour,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "coordinate_valid": self.coordinate_valid,
            "confidence": self.confidence,
            "confidence_recalculated": self.confidence_recalculated,
            "is_duplicate": self.is_duplicate,
            "schema_valid": self.schema_valid,
            "relationship_valid": self.relationship_valid,
        }


class NormalizedCanonical:
    def __init__(self, country_map: dict[str, str] | None = None,
                 source_reliability: dict[str, float] | None = None):
        self._country_map = country_map or ISO_COUNTRY_MAP
        self._source_reliability = source_reliability or SOURCE_RELIABILITY
        self._logs: list[NormalizationLog] = []

    def normalize(self, records: list[dict[str, Any]]) -> tuple[list[NormalizedRecord], list[NormalizationLog]]:
        normalized = []
        self._logs = []

        for record in records:
            nrec, log = self._normalize_single(record)
            normalized.append(nrec)
            self._logs.append(log)

        normalized = self._resolve_duplicates(normalized)
        normalized = self._recalibrate_confidence(normalized)

        logger.info("normalized %d records, %d warnings, %d errors",
                     len(normalized),
                     sum(len(l.warnings) for l in self._logs),
                     sum(len(l.errors) for l in self._logs))
        return normalized, self._logs

    def normalize_dataframe(self, df: pd.DataFrame, id_col: str = "uuid",
                             country_col: str | None = None,
                             timestamp_col: str | None = None,
                             lat_col: str | None = None,
                             lng_col: str | None = None) -> tuple[pd.DataFrame, list[NormalizationLog]]:
        records = df.to_dict("records")
        normalized, logs = self.normalize(records)
        norm_df = pd.DataFrame([r.to_flat_dict() for r in normalized])

        extra_cols = {}
        for col in df.columns:
            if col not in norm_df.columns and col != id_col:
                extra_cols[col] = df[col].values
        for col, vals in extra_cols.items():
            norm_df[col] = list(vals)

        return norm_df, logs

    def _normalize_single(self, record: dict[str, Any]) -> tuple[NormalizedRecord, NormalizationLog]:
        nrec = NormalizedRecord()
        nrec.normalized_id = str(uuid4())
        nrec.original_id = str(record.get("uuid", record.get("id", "")))
        nrec.entity_type = record.get("entity_type", record.get("type", ""))
        nrec.entity_name = record.get("entity_name", record.get("name", ""))
        nrec.source = record.get("source", record.get("source_type", "unknown"))

        log = NormalizationLog(
            record_id=nrec.normalized_id,
            original_record_id=nrec.original_id,
        )

        self._normalize_country(record, nrec, log)
        self._normalize_organization(record, nrec, log)
        self._normalize_persons(record, nrec, log)
        self._normalize_timestamps(record, nrec, log)
        self._normalize_coordinates(record, nrec, log)
        self._normalize_confidence(record, nrec, log)
        self._validate_schema(record, nrec, log)
        self._validate_relationships(record, nrec, log)

        nrec.trace = log
        return nrec, log

    def _normalize_country(self, record: dict, nrec: NormalizedRecord, log: NormalizationLog):
        raw = str(record.get("iso_country", record.get("country", record.get("location_code", "")))).strip().lower()
        if raw and raw != "nan" and raw != "none":
            iso = self._country_map.get(raw, raw.upper() if len(raw) == 2 else "")
            if iso:
                nrec.iso_country = iso
                nrec.country_name = {v: k for k, v in ISO_COUNTRY_MAP.items()}.get(iso, iso)
                nrec.continent = COUNTRY_CONTINENT.get(iso, "unknown")
                nrec.region = nrec.continent
                if raw.upper() != iso:
                    log.add_transform("iso_country", raw, iso, "country_normalization")
            else:
                nrec.iso_country = raw.upper()
                log.add_warning(f"could not map country: {raw}")
        region = record.get("region", "")
        if region and not nrec.region:
            nrec.region = str(region)
            nrec.continent = str(region)

    def _normalize_organization(self, record: dict, nrec: NormalizedRecord, log: NormalizationLog):
        org = record.get("organization", record.get("organization_name", record.get("org", "")))
        org_type = record.get("organization_type", record.get("org_type", ""))
        if org and org != "nan":
            nrec.organization = str(org)
            nrec.organization_normalized = str(org).strip().lower().replace("  ", " ")
            if nrec.organization != nrec.organization_normalized:
                log.add_transform("organization", org, nrec.organization_normalized, "org_normalization")
        if org_type and org_type != "nan":
            nrec.organization_type = str(org_type)

    def _normalize_persons(self, record: dict, nrec: NormalizedRecord, log: NormalizationLog):
        persons = record.get("persons", record.get("personnel", record.get("actors", [])))
        if isinstance(persons, str):
            try:
                persons = json.loads(persons)
            except (json.JSONDecodeError, TypeError):
                persons = [persons]
        if isinstance(persons, list):
            for p in persons:
                name = str(p).strip() if not isinstance(p, str) else p.strip()
                if name and name.lower() != "nan":
                    nrec.persons.append(name)
                    nrec.persons_normalized.append(name.strip().lower())

    def _normalize_timestamps(self, record: dict, nrec: NormalizedRecord, log: NormalizationLog):
        raw_ts = record.get("timestamp", record.get("published_at", record.get("created_at", "")))
        if raw_ts and raw_ts != "nan" and raw_ts != "none":
            nrec.timestamp = str(raw_ts)
            try:
                parsed = pd.Timestamp(raw_ts)
                nrec.timestamp_normalized = parsed.isoformat()
                nrec.timestamp_timezone = str(parsed.tz) if parsed.tz else "UTC"
                nrec.year = parsed.year
                nrec.month = parsed.month
                nrec.day = parsed.day
                nrec.hour = parsed.hour
                nrec.dow = parsed.dayofweek
                nrec.weekend = parsed.dayofweek >= 5
                nrec.timestamp_precision = self._precision_from_timestamp(parsed)
            except (ValueError, TypeError):
                log.add_warning(f"could not parse timestamp: {raw_ts}")
        tz = record.get("timezone", record.get("tz", ""))
        if tz:
            nrec.timestamp_timezone = str(tz)

    def _normalize_coordinates(self, record: dict, nrec: NormalizedRecord, log: NormalizationLog):
        lat = record.get("latitude", record.get("lat"))
        lng = record.get("longitude", record.get("lon", record.get("lng")))
        if lat is not None and lng is not None:
            try:
                lat_f = float(lat)
                lng_f = float(lng)
                nrec.latitude = lat_f
                nrec.longitude = lng_f
                nrec.coordinate_valid = -90 <= lat_f <= 90 and -180 <= lng_f <= 180
                if not nrec.coordinate_valid:
                    log.add_warning(f"invalid coordinates: ({lat_f}, {lng_f})")
            except (ValueError, TypeError):
                log.add_warning(f"non-numeric coordinates: lat={lat}, lng={lng}")
        loc = record.get("location_name", record.get("location", ""))
        if loc and loc != "nan":
            nrec.location_name = str(loc)
        loc_code = record.get("location_code", record.get("code", ""))
        if loc_code and loc_code != "nan":
            nrec.location_code = str(loc_code)

    def _normalize_confidence(self, record: dict, nrec: NormalizedRecord, log: NormalizationLog):
        conf = record.get("confidence", record.get("confidence_score", 1.0))
        try:
            nrec.confidence = min(1.0, max(0.0, float(conf)))
        except (ValueError, TypeError):
            nrec.confidence = 0.5
            log.add_warning(f"invalid confidence: {conf}")

        source_reliability = self._source_reliability.get(nrec.source.lower(), 0.5)
        nrec.source_reliability = source_reliability
        nrec.confidence_recalculated = round(nrec.confidence * source_reliability, 4)

    def _validate_schema(self, record: dict, nrec: NormalizedRecord, log: NormalizationLog):
        errors = []
        if not nrec.entity_type:
            errors.append("missing entity_type")
        if not nrec.original_id:
            errors.append("missing entity_id")
        if nrec.latitude is not None and not nrec.coordinate_valid:
            errors.append("invalid latitude range")
        if nrec.longitude is not None and not nrec.coordinate_valid:
            errors.append("invalid longitude range")
        nrec.schema_valid = len(errors) == 0
        nrec.validation_errors = errors
        for e in errors:
            log.add_error(e)

    def _validate_relationships(self, record: dict, nrec: NormalizedRecord, log: NormalizationLog):
        rels = record.get("relationships", [])
        if isinstance(rels, str):
            try:
                rels = json.loads(rels)
            except (json.JSONDecodeError, TypeError):
                rels = []
        if isinstance(rels, list):
            valid = []
            for r in rels:
                if isinstance(r, dict) and r.get("target_id"):
                    valid.append(r)
                elif isinstance(r, dict) and r.get("entity_id"):
                    valid.append(r)
            if len(valid) != len(rels):
                log.add_warning(f"filtered {len(rels) - len(valid)} invalid relationships")
            nrec.relationships = valid
            nrec.relationship_valid = len(valid) == len(rels) or len(rels) == 0

    def _resolve_duplicates(self, records: list[NormalizedRecord]) -> list[NormalizedRecord]:
        seen: dict[str, int] = {}
        for i, r in enumerate(records):
            key = f"{r.entity_type}:{r.entity_name}:{r.iso_country}:{r.organization}"
            r.entity_resolution_key = key
            if key in seen:
                r.is_duplicate = True
                r.duplicate_of = records[seen[key]].normalized_id
            else:
                seen[key] = i
        return records

    def _recalibrate_confidence(self, records: list[NormalizedRecord]) -> list[NormalizedRecord]:
        for r in records:
            penalty = 0.0
            if r.is_duplicate:
                penalty += 0.1
            if not r.schema_valid:
                penalty += 0.1
            if not r.coordinate_valid and r.latitude is not None:
                penalty += 0.05
            r.confidence_recalculated = round(max(0.0, r.confidence_recalculated - penalty), 4)
        return records

    def get_logs_dataframe(self) -> pd.DataFrame:
        rows = []
        for log in self._logs:
            rows.append({
                "record_id": log.record_id,
                "original_record_id": log.original_record_id,
                "transformations": len(log.transformations),
                "warnings": len(log.warnings),
                "errors": len(log.errors),
                "transformation_details": json.dumps(log.transformations[:5]),
                "warning_details": "; ".join(log.warnings[:5]),
                "error_details": "; ".join(log.errors[:5]),
            })
        return pd.DataFrame(rows)

    @staticmethod
    def _precision_from_timestamp(ts: pd.Timestamp) -> str:
        if ts.hour or ts.minute or ts.second:
            return "second" if ts.second else "minute" if ts.minute else "hour"
        return "day" if ts.day else "month" if ts.month else "year"

    @staticmethod
    def calculate_confidence(source: str, record_confidence: float = 1.0) -> float:
        src = SOURCE_RELIABILITY.get(source.lower(), 0.5)
        return round(record_confidence * src, 4)
