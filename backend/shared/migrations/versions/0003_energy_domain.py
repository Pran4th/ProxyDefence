"""create energy domain schema with all infrastructure tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ENUMS = [
    "lifecycle_state", "operational_status", "criticality_level",
    "organization_type", "relationship_type", "event_type",
    "severity_level", "location_type", "asset_type",
]

TABLES_IN_ORDER = [
    "locations", "organizations", "commodities",
    "ports", "oil_fields", "gas_fields", "pipelines",
    "refineries", "power_plants", "storage_facilities",
    "strategic_petroleum_reserves", "import_corridors",
    "shipping_routes", "suppliers",
    "entity_relationships", "infrastructure_events", "capacity_history",
]


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS energy")

    # ENUM types
    op.execute("""
        CREATE TYPE energy.lifecycle_state AS ENUM (
            'draft', 'verified', 'operational', 'deprecated', 'archived'
        )
    """)
    op.execute("""
        CREATE TYPE energy.operational_status AS ENUM (
            'active', 'maintenance', 'offline', 'damaged',
            'under_construction', 'mothballed', 'decommissioned'
        )
    """)
    op.execute("""
        CREATE TYPE energy.criticality_level AS ENUM (
            'low', 'medium', 'high', 'critical'
        )
    """)
    op.execute("""
        CREATE TYPE energy.organization_type AS ENUM (
            'national_oil_company', 'international_oil_company', 'independent',
            'trader', 'utility', 'government', 'regulatory_body', 'consortium'
        )
    """)
    op.execute("""
        CREATE TYPE energy.relationship_type AS ENUM (
            'supplies', 'connects_to', 'located_in', 'owned_by',
            'operated_by', 'feeds_into', 'receives_from',
            'monitored_by', 'regulated_by', 'adjacent_to', 'crosses'
        )
    """)
    op.execute("""
        CREATE TYPE energy.event_type AS ENUM (
            'shutdown', 'maintenance', 'cyber_attack', 'expansion',
            'inspection', 'explosion', 'natural_disaster',
            'sanctions', 'conflict', 'piracy', 'labor_strike', 'oil_spill'
        )
    """)
    op.execute("""
        CREATE TYPE energy.severity_level AS ENUM (
            'low', 'medium', 'high', 'critical'
        )
    """)
    op.execute("""
        CREATE TYPE energy.location_type AS ENUM (
            'country', 'eez', 'sea', 'region', 'economic_zone',
            'strategic_area', 'strait', 'canal', 'territory'
        )
    """)
    op.execute("""
        CREATE TYPE energy.asset_type AS ENUM (
            'port', 'oil_field', 'gas_field', 'pipeline', 'refinery',
            'power_plant', 'storage_facility', 'strategic_petroleum_reserve',
            'import_corridor', 'shipping_route', 'supplier',
            'location', 'organization'
        )
    """)

    # Locations
    op.execute("""
        CREATE TABLE energy.locations (
            id BIGSERIAL PRIMARY KEY,
            uuid UUID UNIQUE DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            location_type energy.location_type NOT NULL DEFAULT 'country',
            parent_location_id UUID REFERENCES energy.locations(uuid),
            latitude DOUBLE PRECISION, longitude DOUBLE PRECISION,
            geojson JSONB DEFAULT '{}',
            iso_code VARCHAR(2), iso_code_3 VARCHAR(3),
            region TEXT, metadata JSONB DEFAULT '{}',
            is_deleted BOOLEAN DEFAULT FALSE,
            deleted_at TIMESTAMPTZ, version INTEGER DEFAULT 1,
            created_by TEXT DEFAULT 'system', updated_by TEXT DEFAULT 'system',
            created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Organizations
    op.execute("""
        CREATE TABLE energy.organizations (
            id BIGSERIAL PRIMARY KEY,
            uuid UUID UNIQUE DEFAULT gen_random_uuid(),
            name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
            description TEXT, notes TEXT,
            organization_type energy.organization_type NOT NULL DEFAULT 'national_oil_company',
            country_id UUID REFERENCES energy.locations(uuid),
            latitude DOUBLE PRECISION, longitude DOUBLE PRECISION,
            tags TEXT[] DEFAULT '{}', external_references JSONB DEFAULT '[]',
            metadata JSONB DEFAULT '{}',
            is_deleted BOOLEAN DEFAULT FALSE, deleted_at TIMESTAMPTZ, deleted_by TEXT,
            version INTEGER DEFAULT 1,
            created_by TEXT DEFAULT 'system', updated_by TEXT DEFAULT 'system',
            created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Commodities
    op.execute("""
        CREATE TABLE energy.commodities (
            id BIGSERIAL PRIMARY KEY, uuid UUID UNIQUE DEFAULT gen_random_uuid(),
            name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
            description TEXT, commodity_type VARCHAR(50) NOT NULL,
            unit VARCHAR(20), benchmark_price DOUBLE PRECISION,
            api_gravity DOUBLE PRECISION, sulfur_content DOUBLE PRECISION,
            category TEXT, tags TEXT[] DEFAULT '{}', metadata JSONB DEFAULT '{}',
            is_deleted BOOLEAN DEFAULT FALSE, version INTEGER DEFAULT 1,
            created_by TEXT DEFAULT 'system', updated_by TEXT DEFAULT 'system',
            created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Ports
    op.execute("""
        CREATE TABLE energy.ports (
            id BIGSERIAL PRIMARY KEY, uuid UUID UNIQUE DEFAULT gen_random_uuid(),
            name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
            description TEXT, notes TEXT,
            latitude DOUBLE PRECISION, longitude DOUBLE PRECISION,
            geojson JSONB DEFAULT '{}',
            location_id UUID REFERENCES energy.locations(uuid),
            organization_id BIGINT REFERENCES energy.organizations(id),
            port_type VARCHAR(50) DEFAULT 'crude',
            throughput_mtpa DOUBLE PRECISION, storage_capacity_barrels DOUBLE PRECISION,
            max_draft_m DOUBLE PRECISION, annual_capacity_mtpa DOUBLE PRECISION,
            status energy.lifecycle_state DEFAULT 'draft',
            operational_status energy.operational_status DEFAULT 'active',
            criticality energy.criticality_level DEFAULT 'medium',
            importance INTEGER DEFAULT 50, confidence DOUBLE PRECISION DEFAULT 0.8,
            is_deleted BOOLEAN DEFAULT FALSE, deleted_at TIMESTAMPTZ, deleted_by TEXT,
            version INTEGER DEFAULT 1, last_verified TIMESTAMPTZ DEFAULT NOW(),
            source_type TEXT, source_name TEXT, source_url TEXT, source_version TEXT,
            ingested_at TIMESTAMPTZ DEFAULT NOW(),
            tags TEXT[] DEFAULT '{}', external_references JSONB DEFAULT '[]',
            risk_metadata JSONB DEFAULT '{}', graph_metadata JSONB DEFAULT '{}',
            metadata JSONB DEFAULT '{}',
            created_by TEXT DEFAULT 'system', updated_by TEXT DEFAULT 'system',
            created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Oil Fields
    op.execute("""
        CREATE TABLE energy.oil_fields (
            id BIGSERIAL PRIMARY KEY, uuid UUID UNIQUE DEFAULT gen_random_uuid(),
            name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
            description TEXT, notes TEXT,
            latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, geojson JSONB DEFAULT '{}',
            location_id UUID REFERENCES energy.locations(uuid),
            organization_id BIGINT REFERENCES energy.organizations(id),
            reserve_estimate_barrels DOUBLE PRECISION, production_bpd DOUBLE PRECISION,
            api_gravity DOUBLE PRECISION, sulfur_content DOUBLE PRECISION,
            status energy.lifecycle_state DEFAULT 'draft',
            operational_status energy.operational_status DEFAULT 'active',
            criticality energy.criticality_level DEFAULT 'medium',
            importance INTEGER DEFAULT 50, confidence DOUBLE PRECISION DEFAULT 0.8,
            is_deleted BOOLEAN DEFAULT FALSE, deleted_at TIMESTAMPTZ, deleted_by TEXT,
            version INTEGER DEFAULT 1, last_verified TIMESTAMPTZ DEFAULT NOW(),
            source_type TEXT, source_name TEXT, source_url TEXT, source_version TEXT,
            ingested_at TIMESTAMPTZ DEFAULT NOW(),
            tags TEXT[] DEFAULT '{}', external_references JSONB DEFAULT '[]',
            risk_metadata JSONB DEFAULT '{}', graph_metadata JSONB DEFAULT '{}', metadata JSONB DEFAULT '{}',
            created_by TEXT DEFAULT 'system', updated_by TEXT DEFAULT 'system',
            created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Gas Fields
    op.execute("""
        CREATE TABLE energy.gas_fields (
            id BIGSERIAL PRIMARY KEY, uuid UUID UNIQUE DEFAULT gen_random_uuid(),
            name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
            description TEXT, notes TEXT,
            latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, geojson JSONB DEFAULT '{}',
            location_id UUID REFERENCES energy.locations(uuid),
            organization_id BIGINT REFERENCES energy.organizations(id),
            reserve_estimate_cf DOUBLE PRECISION, production_mcfd DOUBLE PRECISION,
            status energy.lifecycle_state DEFAULT 'draft',
            operational_status energy.operational_status DEFAULT 'active',
            criticality energy.criticality_level DEFAULT 'medium',
            importance INTEGER DEFAULT 50, confidence DOUBLE PRECISION DEFAULT 0.8,
            is_deleted BOOLEAN DEFAULT FALSE, deleted_at TIMESTAMPTZ, deleted_by TEXT,
            version INTEGER DEFAULT 1, last_verified TIMESTAMPTZ DEFAULT NOW(),
            source_type TEXT, source_name TEXT, source_url TEXT, source_version TEXT,
            ingested_at TIMESTAMPTZ DEFAULT NOW(),
            tags TEXT[] DEFAULT '{}', external_references JSONB DEFAULT '[]',
            risk_metadata JSONB DEFAULT '{}', graph_metadata JSONB DEFAULT '{}', metadata JSONB DEFAULT '{}',
            created_by TEXT DEFAULT 'system', updated_by TEXT DEFAULT 'system',
            created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Pipelines
    op.execute("""
        CREATE TABLE energy.pipelines (
            id BIGSERIAL PRIMARY KEY, uuid UUID UNIQUE DEFAULT gen_random_uuid(),
            name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
            description TEXT, notes TEXT,
            latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, geojson JSONB DEFAULT '{}',
            location_id UUID REFERENCES energy.locations(uuid),
            organization_id BIGINT REFERENCES energy.organizations(id),
            length_km DOUBLE PRECISION, capacity_bpd DOUBLE PRECISION,
            diameter_inches DOUBLE PRECISION, max_pressure_psi DOUBLE PRECISION,
            commodity_type VARCHAR(50) DEFAULT 'crude', flow_direction VARCHAR(20) DEFAULT 'bidirectional',
            status energy.lifecycle_state DEFAULT 'draft',
            operational_status energy.operational_status DEFAULT 'active',
            criticality energy.criticality_level DEFAULT 'medium',
            importance INTEGER DEFAULT 50, confidence DOUBLE PRECISION DEFAULT 0.8,
            is_deleted BOOLEAN DEFAULT FALSE, deleted_at TIMESTAMPTZ, deleted_by TEXT,
            version INTEGER DEFAULT 1, last_verified TIMESTAMPTZ DEFAULT NOW(),
            source_type TEXT, source_name TEXT, source_url TEXT, source_version TEXT,
            ingested_at TIMESTAMPTZ DEFAULT NOW(),
            tags TEXT[] DEFAULT '{}', external_references JSONB DEFAULT '[]',
            risk_metadata JSONB DEFAULT '{}', graph_metadata JSONB DEFAULT '{}', metadata JSONB DEFAULT '{}',
            created_by TEXT DEFAULT 'system', updated_by TEXT DEFAULT 'system',
            created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Refineries
    op.execute("""
        CREATE TABLE energy.refineries (
            id BIGSERIAL PRIMARY KEY, uuid UUID UNIQUE DEFAULT gen_random_uuid(),
            name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
            description TEXT, notes TEXT,
            latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, geojson JSONB DEFAULT '{}',
            location_id UUID REFERENCES energy.locations(uuid),
            organization_id BIGINT REFERENCES energy.organizations(id),
            capacity_bpd DOUBLE PRECISION, nelson_complexity_index DOUBLE PRECISION,
            crude_types_accepted TEXT[] DEFAULT '{}', output_products TEXT[] DEFAULT '{}',
            status energy.lifecycle_state DEFAULT 'draft',
            operational_status energy.operational_status DEFAULT 'active',
            criticality energy.criticality_level DEFAULT 'medium',
            importance INTEGER DEFAULT 50, confidence DOUBLE PRECISION DEFAULT 0.8,
            is_deleted BOOLEAN DEFAULT FALSE, deleted_at TIMESTAMPTZ, deleted_by TEXT,
            version INTEGER DEFAULT 1, last_verified TIMESTAMPTZ DEFAULT NOW(),
            source_type TEXT, source_name TEXT, source_url TEXT, source_version TEXT,
            ingested_at TIMESTAMPTZ DEFAULT NOW(),
            tags TEXT[] DEFAULT '{}', external_references JSONB DEFAULT '[]',
            risk_metadata JSONB DEFAULT '{}', graph_metadata JSONB DEFAULT '{}', metadata JSONB DEFAULT '{}',
            created_by TEXT DEFAULT 'system', updated_by TEXT DEFAULT 'system',
            created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Power Plants
    op.execute("""
        CREATE TABLE energy.power_plants (
            id BIGSERIAL PRIMARY KEY, uuid UUID UNIQUE DEFAULT gen_random_uuid(),
            name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
            description TEXT, notes TEXT,
            latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, geojson JSONB DEFAULT '{}',
            location_id UUID REFERENCES energy.locations(uuid),
            organization_id BIGINT REFERENCES energy.organizations(id),
            capacity_mw DOUBLE PRECISION, fuel_type VARCHAR(50), plant_type VARCHAR(50),
            status energy.lifecycle_state DEFAULT 'draft',
            operational_status energy.operational_status DEFAULT 'active',
            criticality energy.criticality_level DEFAULT 'medium',
            importance INTEGER DEFAULT 50, confidence DOUBLE PRECISION DEFAULT 0.8,
            is_deleted BOOLEAN DEFAULT FALSE, deleted_at TIMESTAMPTZ, deleted_by TEXT,
            version INTEGER DEFAULT 1, last_verified TIMESTAMPTZ DEFAULT NOW(),
            source_type TEXT, source_name TEXT, source_url TEXT, source_version TEXT,
            ingested_at TIMESTAMPTZ DEFAULT NOW(),
            tags TEXT[] DEFAULT '{}', external_references JSONB DEFAULT '[]',
            risk_metadata JSONB DEFAULT '{}', graph_metadata JSONB DEFAULT '{}', metadata JSONB DEFAULT '{}',
            created_by TEXT DEFAULT 'system', updated_by TEXT DEFAULT 'system',
            created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Storage Facilities
    op.execute("""
        CREATE TABLE energy.storage_facilities (
            id BIGSERIAL PRIMARY KEY, uuid UUID UNIQUE DEFAULT gen_random_uuid(),
            name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
            description TEXT, notes TEXT,
            latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, geojson JSONB DEFAULT '{}',
            location_id UUID REFERENCES energy.locations(uuid),
            organization_id BIGINT REFERENCES energy.organizations(id),
            capacity_barrels DOUBLE PRECISION,
            facility_type VARCHAR(50) DEFAULT 'above_ground',
            status energy.lifecycle_state DEFAULT 'draft',
            operational_status energy.operational_status DEFAULT 'active',
            criticality energy.criticality_level DEFAULT 'medium',
            importance INTEGER DEFAULT 50, confidence DOUBLE PRECISION DEFAULT 0.8,
            is_deleted BOOLEAN DEFAULT FALSE, deleted_at TIMESTAMPTZ, deleted_by TEXT,
            version INTEGER DEFAULT 1, last_verified TIMESTAMPTZ DEFAULT NOW(),
            source_type TEXT, source_name TEXT, source_url TEXT, source_version TEXT,
            ingested_at TIMESTAMPTZ DEFAULT NOW(),
            tags TEXT[] DEFAULT '{}', external_references JSONB DEFAULT '[]',
            risk_metadata JSONB DEFAULT '{}', graph_metadata JSONB DEFAULT '{}', metadata JSONB DEFAULT '{}',
            created_by TEXT DEFAULT 'system', updated_by TEXT DEFAULT 'system',
            created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Strategic Petroleum Reserves
    op.execute("""
        CREATE TABLE energy.strategic_petroleum_reserves (
            id BIGSERIAL PRIMARY KEY, uuid UUID UNIQUE DEFAULT gen_random_uuid(),
            name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
            description TEXT, notes TEXT,
            latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, geojson JSONB DEFAULT '{}',
            location_id UUID REFERENCES energy.locations(uuid),
            organization_id BIGINT REFERENCES energy.organizations(id),
            capacity_barrels DOUBLE PRECISION, current_inventory_barrels DOUBLE PRECISION,
            max_drawdown_rate_bpd DOUBLE PRECISION, replenishment_rate_bpd DOUBLE PRECISION,
            status energy.lifecycle_state DEFAULT 'draft',
            operational_status energy.operational_status DEFAULT 'active',
            criticality energy.criticality_level DEFAULT 'critical',
            importance INTEGER DEFAULT 95, confidence DOUBLE PRECISION DEFAULT 0.8,
            is_deleted BOOLEAN DEFAULT FALSE, deleted_at TIMESTAMPTZ, deleted_by TEXT,
            version INTEGER DEFAULT 1, last_verified TIMESTAMPTZ DEFAULT NOW(),
            source_type TEXT, source_name TEXT, source_url TEXT, source_version TEXT,
            ingested_at TIMESTAMPTZ DEFAULT NOW(),
            tags TEXT[] DEFAULT '{}', external_references JSONB DEFAULT '[]',
            risk_metadata JSONB DEFAULT '{}', graph_metadata JSONB DEFAULT '{}', metadata JSONB DEFAULT '{}',
            created_by TEXT DEFAULT 'system', updated_by TEXT DEFAULT 'system',
            created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Import Corridors
    op.execute("""
        CREATE TABLE energy.import_corridors (
            id BIGSERIAL PRIMARY KEY, uuid UUID UNIQUE DEFAULT gen_random_uuid(),
            name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
            description TEXT, notes TEXT,
            origin_location_id UUID REFERENCES energy.locations(uuid),
            destination_location_id UUID REFERENCES energy.locations(uuid),
            distance_km DOUBLE PRECISION, transit_time_days DOUBLE PRECISION,
            status energy.lifecycle_state DEFAULT 'draft',
            operational_status energy.operational_status DEFAULT 'active',
            criticality energy.criticality_level DEFAULT 'high',
            importance INTEGER DEFAULT 75, confidence DOUBLE PRECISION DEFAULT 0.8,
            is_deleted BOOLEAN DEFAULT FALSE, deleted_at TIMESTAMPTZ, deleted_by TEXT,
            version INTEGER DEFAULT 1, last_verified TIMESTAMPTZ DEFAULT NOW(),
            source_type TEXT, source_name TEXT, source_url TEXT, source_version TEXT,
            ingested_at TIMESTAMPTZ DEFAULT NOW(),
            tags TEXT[] DEFAULT '{}', external_references JSONB DEFAULT '[]',
            risk_metadata JSONB DEFAULT '{}', graph_metadata JSONB DEFAULT '{}', metadata JSONB DEFAULT '{}',
            created_by TEXT DEFAULT 'system', updated_by TEXT DEFAULT 'system',
            created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Shipping Routes
    op.execute("""
        CREATE TABLE energy.shipping_routes (
            id BIGSERIAL PRIMARY KEY, uuid UUID UNIQUE DEFAULT gen_random_uuid(),
            name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
            description TEXT, notes TEXT,
            origin_port_id BIGINT REFERENCES energy.ports(id),
            destination_port_id BIGINT REFERENCES energy.ports(id),
            distance_nm DOUBLE PRECISION, transit_time_days DOUBLE PRECISION,
            insurance_multiplier DOUBLE PRECISION DEFAULT 1.0,
            risk_score DOUBLE PRECISION DEFAULT 0.0,
            status energy.lifecycle_state DEFAULT 'draft',
            operational_status energy.operational_status DEFAULT 'active',
            criticality energy.criticality_level DEFAULT 'high',
            importance INTEGER DEFAULT 75, confidence DOUBLE PRECISION DEFAULT 0.8,
            is_deleted BOOLEAN DEFAULT FALSE, deleted_at TIMESTAMPTZ, deleted_by TEXT,
            version INTEGER DEFAULT 1, last_verified TIMESTAMPTZ DEFAULT NOW(),
            source_type TEXT, source_name TEXT, source_url TEXT, source_version TEXT,
            ingested_at TIMESTAMPTZ DEFAULT NOW(),
            tags TEXT[] DEFAULT '{}', external_references JSONB DEFAULT '[]',
            risk_metadata JSONB DEFAULT '{}', graph_metadata JSONB DEFAULT '{}', metadata JSONB DEFAULT '{}',
            created_by TEXT DEFAULT 'system', updated_by TEXT DEFAULT 'system',
            created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Suppliers
    op.execute("""
        CREATE TABLE energy.suppliers (
            id BIGSERIAL PRIMARY KEY, uuid UUID UNIQUE DEFAULT gen_random_uuid(),
            name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
            description TEXT, notes TEXT,
            organization_id BIGINT REFERENCES energy.organizations(id),
            location_id UUID REFERENCES energy.locations(uuid),
            supplier_type VARCHAR(50) DEFAULT 'national_oil_company',
            market_share_pct DOUBLE PRECISION,
            status energy.lifecycle_state DEFAULT 'draft',
            operational_status energy.operational_status DEFAULT 'active',
            criticality energy.criticality_level DEFAULT 'medium',
            importance INTEGER DEFAULT 50, confidence DOUBLE PRECISION DEFAULT 0.8,
            is_deleted BOOLEAN DEFAULT FALSE, deleted_at TIMESTAMPTZ, deleted_by TEXT,
            version INTEGER DEFAULT 1, last_verified TIMESTAMPTZ DEFAULT NOW(),
            source_type TEXT, source_name TEXT, source_url TEXT, source_version TEXT,
            ingested_at TIMESTAMPTZ DEFAULT NOW(),
            tags TEXT[] DEFAULT '{}', external_references JSONB DEFAULT '[]',
            risk_metadata JSONB DEFAULT '{}', graph_metadata JSONB DEFAULT '{}', metadata JSONB DEFAULT '{}',
            created_by TEXT DEFAULT 'system', updated_by TEXT DEFAULT 'system',
            created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Entity Relationships
    op.execute("""
        CREATE TABLE energy.entity_relationships (
            id BIGSERIAL PRIMARY KEY, uuid UUID UNIQUE DEFAULT gen_random_uuid(),
            source_entity_type energy.asset_type NOT NULL,
            source_entity_id BIGINT NOT NULL,
            target_entity_type energy.asset_type NOT NULL,
            target_entity_id BIGINT NOT NULL,
            relationship_type energy.relationship_type NOT NULL,
            confidence DOUBLE PRECISION DEFAULT 0.8,
            valid_from TIMESTAMPTZ DEFAULT NOW(), valid_to TIMESTAMPTZ,
            metadata JSONB DEFAULT '{}',
            created_by TEXT DEFAULT 'system', updated_by TEXT DEFAULT 'system',
            created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Infrastructure Events
    op.execute("""
        CREATE TABLE energy.infrastructure_events (
            id BIGSERIAL PRIMARY KEY, uuid UUID UNIQUE DEFAULT gen_random_uuid(),
            entity_type energy.asset_type NOT NULL, entity_id BIGINT NOT NULL,
            event_type energy.event_type NOT NULL,
            severity energy.severity_level NOT NULL DEFAULT 'medium',
            description TEXT,
            occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), resolved_at TIMESTAMPTZ,
            metadata JSONB DEFAULT '{}',
            created_by TEXT DEFAULT 'system', updated_by TEXT DEFAULT 'system',
            created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Capacity History
    op.execute("""
        CREATE TABLE energy.capacity_history (
            id BIGSERIAL PRIMARY KEY, uuid UUID UNIQUE DEFAULT gen_random_uuid(),
            entity_type energy.asset_type NOT NULL, entity_id BIGINT NOT NULL,
            metric_type VARCHAR(50) NOT NULL,
            value DOUBLE PRECISION NOT NULL, unit VARCHAR(20),
            recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), metadata JSONB DEFAULT '{}',
            created_by TEXT DEFAULT 'system', created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Indexes
    op.execute("CREATE INDEX idx_locations_type ON energy.locations(location_type)")
    op.execute("CREATE INDEX idx_locations_parent ON energy.locations(parent_location_id)")
    op.execute("CREATE INDEX idx_locations_active ON energy.locations(is_deleted) WHERE is_deleted = FALSE")
    op.execute("CREATE INDEX idx_organizations_type ON energy.organizations(organization_type)")
    op.execute("CREATE INDEX idx_orgs_active ON energy.organizations(is_deleted) WHERE is_deleted = FALSE")
    op.execute("CREATE INDEX idx_relationships_source ON energy.entity_relationships(source_entity_type, source_entity_id)")
    op.execute("CREATE INDEX idx_relationships_target ON energy.entity_relationships(target_entity_type, target_entity_id)")
    op.execute("CREATE INDEX idx_relationships_type ON energy.entity_relationships(relationship_type)")
    op.execute("CREATE INDEX idx_events_entity ON energy.infrastructure_events(entity_type, entity_id)")
    op.execute("CREATE INDEX idx_events_occurred ON energy.infrastructure_events(occurred_at DESC)")
    op.execute("CREATE INDEX idx_history_entity ON energy.capacity_history(entity_type, entity_id, metric_type)")
    op.execute("CREATE INDEX idx_history_recorded ON energy.capacity_history(recorded_at DESC)")
    op.execute("CREATE INDEX idx_ports_active ON energy.ports(is_deleted) WHERE is_deleted = FALSE")
    op.execute("CREATE INDEX idx_oil_fields_active ON energy.oil_fields(is_deleted) WHERE is_deleted = FALSE")
    op.execute("CREATE INDEX idx_gas_fields_active ON energy.gas_fields(is_deleted) WHERE is_deleted = FALSE")
    op.execute("CREATE INDEX idx_pipelines_active ON energy.pipelines(is_deleted) WHERE is_deleted = FALSE")
    op.execute("CREATE INDEX idx_refineries_active ON energy.refineries(is_deleted) WHERE is_deleted = FALSE")
    op.execute("CREATE INDEX idx_ports_tags ON energy.ports USING GIN(tags)")
    op.execute("CREATE INDEX idx_oil_fields_tags ON energy.oil_fields USING GIN(tags)")
    op.execute("CREATE INDEX idx_gas_fields_tags ON energy.gas_fields USING GIN(tags)")
    op.execute("CREATE INDEX idx_pipelines_tags ON energy.pipelines USING GIN(tags)")
    op.execute("CREATE INDEX idx_refineries_tags ON energy.refineries USING GIN(tags)")
    op.execute("CREATE INDEX idx_orgs_tags ON energy.organizations USING GIN(tags)")
    op.execute("CREATE INDEX idx_ports_name ON energy.ports(name)")
    op.execute("CREATE INDEX idx_oil_fields_name ON energy.oil_fields(name)")
    op.execute("CREATE INDEX idx_gas_fields_name ON energy.gas_fields(name)")
    op.execute("CREATE INDEX idx_pipelines_name ON energy.pipelines(name)")
    op.execute("CREATE INDEX idx_refineries_name ON energy.refineries(name)")


def downgrade() -> None:
    table_names = [
        "capacity_history", "infrastructure_events", "entity_relationships",
        "suppliers", "shipping_routes", "import_corridors",
        "strategic_petroleum_reserves", "storage_facilities", "power_plants",
        "refineries", "pipelines", "gas_fields", "oil_fields", "ports",
        "commodities", "organizations", "locations",
    ]
    for t in table_names:
        op.execute(f"DROP TABLE IF EXISTS energy.{t} CASCADE")

    for e in reversed(ENUMS):
        op.execute(f"DROP TYPE IF EXISTS energy.{e} CASCADE")

    op.execute("DROP SCHEMA IF EXISTS energy CASCADE")
