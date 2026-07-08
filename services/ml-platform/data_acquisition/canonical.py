from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class CanonicalSchema:
    entity_type: str = ""
    entity_id: str = ""
    entity_name: str = ""
    timestamp: str = ""
    timestamp_precision: str = ""
    latitude: float | None = None
    longitude: float | None = None
    location_name: str | None = None
    location_code: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    relationships: list[dict] = field(default_factory=list)
    source: str = ""
    source_record_id: str | None = None
    confidence: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _none_if_empty(v: Any) -> Any:
    if v is None or (isinstance(v, str) and v.strip() == ""):
        return None
    if isinstance(v, str):
        try:
            return float(v)
        except (ValueError, TypeError):
            return v
    return v


class CanonicalRecord:
    def __init__(self, **kwargs: Any) -> None:
        self.entity_type: str = kwargs.get("entity_type", "")
        self.entity_id: str = kwargs.get("entity_id", "")
        self.entity_name: str = kwargs.get("entity_name", "")
        self.timestamp: str = kwargs.get("timestamp", "")
        self.timestamp_precision: str = kwargs.get("timestamp_precision", "")
        self.latitude: float | None = _none_if_empty(kwargs.get("latitude"))
        self.longitude: float | None = _none_if_empty(kwargs.get("longitude"))
        self.location_name: str | None = kwargs.get("location_name") or None
        self.location_code: str | None = kwargs.get("location_code") or None
        self.attributes: dict[str, Any] = kwargs.get("attributes", {})
        self.relationships: list[dict] = kwargs.get("relationships", [])
        self.source: str = kwargs.get("source", "")
        self.source_record_id: str | None = kwargs.get("source_record_id") or None
        self.confidence: float | None = _none_if_empty(kwargs.get("confidence"))
        self.metadata: dict[str, Any] = kwargs.get("metadata", {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "timestamp": self.timestamp,
            "timestamp_precision": self.timestamp_precision,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "location_name": self.location_name,
            "location_code": self.location_code,
            "attributes": self.attributes,
            "relationships": self.relationships,
            "source": self.source,
            "source_record_id": self.source_record_id,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CanonicalRecord:
        return cls(**data)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.entity_type:
            errors.append("entity_type is required")
        if not self.entity_id:
            errors.append("entity_id is required")
        if self.latitude is not None and (self.latitude < -90 or self.latitude > 90):
            errors.append(f"latitude out of range: {self.latitude}")
        if self.longitude is not None and (self.longitude < -180 or self.longitude > 180):
            errors.append(f"longitude out of range: {self.longitude}")
        if self.confidence is not None and (self.confidence < 0 or self.confidence > 1):
            errors.append(f"confidence out of range [0,1]: {self.confidence}")
        valid_precisions = {"year", "month", "day", "hour", "minute", "second"}
        if self.timestamp_precision and self.timestamp_precision not in valid_precisions:
            errors.append(f"invalid timestamp_precision: {self.timestamp_precision}")
        return errors

    def to_dataframe_row(self) -> dict[str, Any]:
        flat = {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "timestamp": self.timestamp,
            "timestamp_precision": self.timestamp_precision,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "location_name": self.location_name,
            "location_code": self.location_code,
            "source": self.source,
            "source_record_id": self.source_record_id,
            "confidence": self.confidence,
        }
        for key, val in self.attributes.items():
            safe_key = str(key).replace(" ", "_").replace(".", "_")
            flat[f"attr_{safe_key}"] = val
        flat["relationships"] = str(self.relationships)
        flat["metadata"] = str(self.metadata)
        return flat


def canonical_schema_definition() -> dict[str, dict[str, str]]:
    return {
        "entity_type": {"type": "string", "description": "Type of the entity (e.g. vessel, port, event, trade_flow)"},
        "entity_id": {"type": "string", "description": "Unique identifier for the entity"},
        "entity_name": {"type": "string", "description": "Human-readable name for the entity"},
        "timestamp": {"type": "string (ISO 8601)", "description": "Timestamp associated with the record"},
        "timestamp_precision": {"type": "string", "description": "Precision of timestamp: year/month/day/hour/minute/second"},
        "latitude": {"type": "float or null", "description": "Latitude in decimal degrees"},
        "longitude": {"type": "float or null", "description": "Longitude in decimal degrees"},
        "location_name": {"type": "string or null", "description": "Name of the location"},
        "location_code": {"type": "string or null", "description": "Location code (ISO country code, UNLOCODE, etc.)"},
        "attributes": {"type": "dict", "description": "Key-value pairs for dataset-specific data"},
        "relationships": {"type": "list[dict]", "description": "Related entities with type and target_id"},
        "source": {"type": "string", "description": "Original data source name"},
        "source_record_id": {"type": "string or null", "description": "Identifier in the original source"},
        "confidence": {"type": "float or null", "description": "Confidence score between 0 and 1"},
        "metadata": {"type": "dict", "description": "Provenance, version info, and other metadata"},
    }
