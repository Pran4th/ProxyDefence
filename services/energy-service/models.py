from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ─── ENUM-basierte String Literals (keine Abhängigkeit von DB-ENUMs) ───

class LifecycleState(str):
    DRAFT = "draft"
    VERIFIED = "verified"
    OPERATIONAL = "operational"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"

class OperationalStatus(str):
    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"
    DAMAGED = "damaged"
    UNDER_CONSTRUCTION = "under_construction"
    MOTHBALLED = "mothballed"
    DECOMMISSIONED = "decommissioned"

class CriticalityLevel(str):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ─── Basis-Modelle ───

class ExternalReference(BaseModel):
    system: str
    id: str
    url: str | None = None
    label: str | None = None


class Provenance(BaseModel):
    source_type: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    source_version: str | None = None
    ingested_at: datetime | None = None


class AuditFields(BaseModel):
    created_by: str = "system"
    updated_by: str = "system"
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SoftDelete(BaseModel):
    is_deleted: bool = False
    deleted_at: datetime | None = None
    deleted_by: str | None = None


class BaseEntity(BaseModel):
    uuid: UUID | None = None
    name: str
    slug: str | None = None
    description: str | None = None
    notes: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    geojson: dict[str, Any] = {}
    location_id: UUID | None = None
    organization_id: int | None = None
    status: str = LifecycleState.DRAFT
    operational_status: str = OperationalStatus.ACTIVE
    criticality: str = CriticalityLevel.MEDIUM
    importance: int = 50
    confidence: float = 0.8
    is_deleted: bool = False
    version: int = 1
    last_verified: datetime | None = None
    tags: list[str] = []
    external_references: list[ExternalReference] = []
    risk_metadata: dict[str, Any] = {}
    graph_metadata: dict[str, Any] = {}
    metadata: dict[str, Any] = {}
    provenance: Provenance = Provenance()
    audit: AuditFields = AuditFields()


class BaseEntityResponse(BaseEntity):
    id: int
    uuid: UUID


class PaginatedResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int


class BulkImportResult(BaseModel):
    created: int = 0
    updated: int = 0
    errors: list[str] = []


class BulkImportRequest(BaseModel):
    entities: list[dict[str, Any]]
    format: str = "json"


# ─── Entity-spezifische Modelle ───

class Location(BaseEntity):
    location_type: str = "country"
    parent_location_id: UUID | None = None
    iso_code: str | None = None
    iso_code_3: str | None = None
    region: str | None = None

class Organization(BaseEntity):
    organization_type: str = "national_oil_company"
    country_id: UUID | None = None

class Commodity(BaseEntity):
    commodity_type: str = "crude"
    unit: str | None = None
    benchmark_price: float | None = None
    api_gravity: float | None = None
    sulfur_content: float | None = None
    category: str | None = None

class Port(BaseEntity):
    port_type: str = "crude"
    throughput_mtpa: float | None = None
    storage_capacity_barrels: float | None = None
    max_draft_m: float | None = None
    annual_capacity_mtpa: float | None = None

class OilField(BaseEntity):
    reserve_estimate_barrels: float | None = None
    production_bpd: float | None = None
    api_gravity: float | None = None
    sulfur_content: float | None = None

class GasField(BaseEntity):
    reserve_estimate_cf: float | None = None
    production_mcfd: float | None = None

class Pipeline(BaseEntity):
    length_km: float | None = None
    capacity_bpd: float | None = None
    diameter_inches: float | None = None
    max_pressure_psi: float | None = None
    commodity_type: str = "crude"
    flow_direction: str = "bidirectional"

class Refinery(BaseEntity):
    capacity_bpd: float | None = None
    nelson_complexity_index: float | None = None
    crude_types_accepted: list[str] = []
    output_products: list[str] = []

class PowerPlant(BaseEntity):
    capacity_mw: float | None = None
    fuel_type: str | None = None
    plant_type: str | None = None

class StorageFacility(BaseEntity):
    capacity_barrels: float | None = None
    facility_type: str = "above_ground"

class StrategicPetroleumReserve(BaseEntity):
    capacity_barrels: float | None = None
    current_inventory_barrels: float | None = None
    max_drawdown_rate_bpd: float | None = None
    replenishment_rate_bpd: float | None = None

class ImportCorridor(BaseEntity):
    origin_location_id: UUID | None = None
    destination_location_id: UUID | None = None
    distance_km: float | None = None
    transit_time_days: float | None = None

class ShippingRoute(BaseEntity):
    origin_port_id: int | None = None
    destination_port_id: int | None = None
    distance_nm: float | None = None
    transit_time_days: float | None = None
    insurance_multiplier: float = 1.0
    risk_score: float = 0.0

class Supplier(BaseEntity):
    organization_id: int | None = None
    location_id: UUID | None = None
    supplier_type: str = "national_oil_company"
    market_share_pct: float | None = None

class EntityRelationship(BaseModel):
    source_entity_type: str
    source_entity_id: int
    target_entity_type: str
    target_entity_id: int
    relationship_type: str
    confidence: float = 0.8
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    metadata: dict[str, Any] = {}
    created_by: str = "system"
    updated_by: str = "system"

class InfrastructureEvent(BaseModel):
    entity_type: str
    entity_id: int
    event_type: str
    severity: str = "medium"
    description: str | None = None
    occurred_at: datetime | None = None
    resolved_at: datetime | None = None
    metadata: dict[str, Any] = {}

class CapacityRecord(BaseModel):
    entity_type: str
    entity_id: int
    metric_type: str
    value: float
    unit: str | None = None
    recorded_at: datetime | None = None
    metadata: dict[str, Any] = {}


# ─── Entity Registry ───

ENTITY_TABLES = {
    "locations": Location,
    "organizations": Organization,
    "commodities": Commodity,
    "ports": Port,
    "oil_fields": OilField,
    "gas_fields": GasField,
    "pipelines": Pipeline,
    "refineries": Refinery,
    "power_plants": PowerPlant,
    "storage_facilities": StorageFacility,
    "strategic_petroleum_reserves": StrategicPetroleumReserve,
    "import_corridors": ImportCorridor,
    "shipping_routes": ShippingRoute,
    "suppliers": Supplier,
}

ENTITY_TABLE_NAMES = list(ENTITY_TABLES.keys())

ASSET_TYPE_BY_TABLE = {
    "locations": "location",
    "organizations": "organization",
    "ports": "port",
    "oil_fields": "oil_field",
    "gas_fields": "gas_field",
    "pipelines": "pipeline",
    "refineries": "refinery",
    "power_plants": "power_plant",
    "storage_facilities": "storage_facility",
    "strategic_petroleum_reserves": "strategic_petroleum_reserve",
    "import_corridors": "import_corridor",
    "shipping_routes": "shipping_route",
    "suppliers": "supplier",
}

VALID_ASSET_TYPES = set(ASSET_TYPE_BY_TABLE.values())

CATALOG_WRITABLE_COLUMNS = {
    "uuid", "name", "slug", "description", "notes", "latitude", "longitude", "geojson",
    "location_id", "organization_id", "status", "operational_status", "criticality",
    "importance", "confidence", "is_deleted", "deleted_at", "deleted_by", "version",
    "last_verified", "source_type", "source_name", "source_url", "source_version",
    "ingested_at", "tags", "external_references", "risk_metadata", "graph_metadata",
    "metadata", "created_by", "updated_by", "location_type", "parent_location_id",
    "iso_code", "iso_code_3", "region", "organization_type", "country_id",
    "commodity_type", "unit", "benchmark_price", "api_gravity", "sulfur_content",
    "category", "port_type", "throughput_mtpa", "storage_capacity_barrels",
    "max_draft_m", "annual_capacity_mtpa", "reserve_estimate_barrels", "production_bpd",
    "reserve_estimate_cf", "production_mcfd", "length_km", "capacity_bpd",
    "diameter_inches", "max_pressure_psi", "flow_direction", "capacity_bpd",
    "nelson_complexity_index", "crude_types_accepted", "output_products", "capacity_mw",
    "fuel_type", "plant_type", "capacity_barrels", "facility_type",
    "current_inventory_barrels", "max_drawdown_rate_bpd", "replenishment_rate_bpd",
    "origin_location_id", "destination_location_id", "distance_km", "transit_time_days",
    "origin_port_id", "destination_port_id", "distance_nm", "insurance_multiplier",
    "risk_score", "supplier_type", "market_share_pct",
}

CATALOG_JSON_COLUMNS = {
    "geojson", "external_references", "risk_metadata", "graph_metadata", "metadata",
}

RELATIONSHIP_WRITABLE_COLUMNS = {
    "source_entity_type", "source_entity_id", "target_entity_type", "target_entity_id",
    "relationship_type", "confidence", "valid_from", "valid_to", "metadata",
    "created_by", "updated_by",
}

EVENT_WRITABLE_COLUMNS = {
    "entity_type", "entity_id", "event_type", "severity", "description",
    "occurred_at", "resolved_at", "metadata", "created_by", "updated_by",
}

ENERGY_JSON_COLUMNS = {"metadata"}

HISTORY_WRITABLE_COLUMNS = {
    "entity_type", "entity_id", "metric_type", "value", "unit", "recorded_at",
    "metadata", "created_by",
}
