-- Energy Domain Schema
-- Canonical source of truth for all energy infrastructure models.
-- SINGLE SOURCE OF TRUTH: Alembic migration #0003 is the programmatic version.
-- This file is the authoritative DDL reference.

CREATE SCHEMA IF NOT EXISTS energy;

-- ============================================================================
-- ENUMS
-- ============================================================================

CREATE TYPE energy.lifecycle_state AS ENUM (
    'draft', 'verified', 'operational', 'deprecated', 'archived'
);

CREATE TYPE energy.operational_status AS ENUM (
    'active', 'maintenance', 'offline', 'damaged',
    'under_construction', 'mothballed', 'decommissioned'
);

CREATE TYPE energy.criticality_level AS ENUM (
    'low', 'medium', 'high', 'critical'
);

CREATE TYPE energy.organization_type AS ENUM (
    'national_oil_company', 'international_oil_company', 'independent',
    'trader', 'utility', 'government', 'regulatory_body', 'consortium'
);

CREATE TYPE energy.relationship_type AS ENUM (
    'supplies', 'connects_to', 'located_in', 'owned_by',
    'operated_by', 'feeds_into', 'receives_from',
    'monitored_by', 'regulated_by', 'adjacent_to', 'crosses'
);

CREATE TYPE energy.event_type AS ENUM (
    'shutdown', 'maintenance', 'cyber_attack', 'expansion',
    'inspection', 'explosion', 'natural_disaster',
    'sanctions', 'conflict', 'piracy', 'labor_strike', 'oil_spill'
);

CREATE TYPE energy.severity_level AS ENUM (
    'low', 'medium', 'high', 'critical'
);

CREATE TYPE energy.location_type AS ENUM (
    'country', 'eez', 'sea', 'region', 'economic_zone',
    'strategic_area', 'strait', 'canal', 'territory'
);

CREATE TYPE energy.asset_type AS ENUM (
    'port', 'oil_field', 'gas_field', 'pipeline', 'refinery',
    'power_plant', 'storage_facility', 'strategic_petroleum_reserve',
    'import_corridor', 'shipping_route', 'supplier',
    'location', 'organization'
);

-- ============================================================================
-- SYSTEM TABLES
-- ============================================================================

CREATE TABLE energy.locations (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    location_type energy.location_type NOT NULL DEFAULT 'country',
    parent_location_id UUID REFERENCES energy.locations(uuid),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    geojson JSONB DEFAULT '{}',
    iso_code VARCHAR(2),
    iso_code_3 VARCHAR(3),
    region TEXT,
    metadata JSONB DEFAULT '{}',
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    version INTEGER DEFAULT 1,
    created_by TEXT DEFAULT 'system',
    updated_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE energy.organizations (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    description TEXT,
    notes TEXT,
    organization_type energy.organization_type NOT NULL DEFAULT 'national_oil_company',
    country_id UUID REFERENCES energy.locations(uuid),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    tags TEXT[] DEFAULT '{}',
    external_references JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    deleted_by TEXT,
    version INTEGER DEFAULT 1,
    created_by TEXT DEFAULT 'system',
    updated_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE energy.commodities (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    description TEXT,
    commodity_type VARCHAR(50) NOT NULL,
    unit VARCHAR(20),
    benchmark_price DOUBLE PRECISION,
    api_gravity DOUBLE PRECISION,
    sulfur_content DOUBLE PRECISION,
    category TEXT,
    tags TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    is_deleted BOOLEAN DEFAULT FALSE,
    version INTEGER DEFAULT 1,
    created_by TEXT DEFAULT 'system',
    updated_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE energy.entity_relationships (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    source_entity_type energy.asset_type NOT NULL,
    source_entity_id BIGINT NOT NULL,
    target_entity_type energy.asset_type NOT NULL,
    target_entity_id BIGINT NOT NULL,
    relationship_type energy.relationship_type NOT NULL,
    confidence DOUBLE PRECISION DEFAULT 0.8 CHECK (confidence BETWEEN 0 AND 1),
    valid_from TIMESTAMPTZ DEFAULT NOW(),
    valid_to TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_by TEXT DEFAULT 'system',
    updated_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE energy.infrastructure_events (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    entity_type energy.asset_type NOT NULL,
    entity_id BIGINT NOT NULL,
    event_type energy.event_type NOT NULL,
    severity energy.severity_level NOT NULL DEFAULT 'medium',
    description TEXT,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_by TEXT DEFAULT 'system',
    updated_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE energy.capacity_history (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    entity_type energy.asset_type NOT NULL,
    entity_id BIGINT NOT NULL,
    metric_type VARCHAR(50) NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    unit VARCHAR(20),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    created_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- INFRASTRUCTURE ENTITY TABLES
-- ============================================================================

CREATE TABLE energy.ports (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    description TEXT,
    notes TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    geojson JSONB DEFAULT '{}',
    location_id UUID REFERENCES energy.locations(uuid),
    organization_id BIGINT REFERENCES energy.organizations(id),
    port_type VARCHAR(50) DEFAULT 'crude',
    throughput_mtpa DOUBLE PRECISION,
    storage_capacity_barrels DOUBLE PRECISION,
    max_draft_m DOUBLE PRECISION,
    annual_capacity_mtpa DOUBLE PRECISION,
    status energy.lifecycle_state DEFAULT 'draft',
    operational_status energy.operational_status DEFAULT 'active',
    criticality energy.criticality_level DEFAULT 'medium',
    importance INTEGER DEFAULT 50 CHECK (importance BETWEEN 1 AND 100),
    confidence DOUBLE PRECISION DEFAULT 0.8,
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    deleted_by TEXT,
    version INTEGER DEFAULT 1,
    last_verified TIMESTAMPTZ DEFAULT NOW(),
    source_type TEXT,
    source_name TEXT,
    source_url TEXT,
    source_version TEXT,
    ingested_at TIMESTAMPTZ DEFAULT NOW(),
    tags TEXT[] DEFAULT '{}',
    external_references JSONB DEFAULT '[]',
    risk_metadata JSONB DEFAULT '{}',
    graph_metadata JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_by TEXT DEFAULT 'system',
    updated_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Remaining infrastructure tables use the same column template as ports.
-- For brevity, only entity-specific columns are shown for each.

CREATE TABLE energy.oil_fields (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    description TEXT, notes TEXT,
    latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, geojson JSONB DEFAULT '{}',
    location_id UUID REFERENCES energy.locations(uuid),
    organization_id BIGINT REFERENCES energy.organizations(id),
    reserve_estimate_barrels DOUBLE PRECISION,
    production_bpd DOUBLE PRECISION,
    api_gravity DOUBLE PRECISION,
    sulfur_content DOUBLE PRECISION,
    status energy.lifecycle_state DEFAULT 'draft',
    operational_status energy.operational_status DEFAULT 'active',
    criticality energy.criticality_level DEFAULT 'medium',
    importance INTEGER DEFAULT 50, confidence DOUBLE PRECISION DEFAULT 0.8,
    is_deleted BOOLEAN DEFAULT FALSE, deleted_at TIMESTAMPTZ, deleted_by TEXT,
    version INTEGER DEFAULT 1, last_verified TIMESTAMPTZ DEFAULT NOW(),
    source_type TEXT, source_name TEXT, source_url TEXT, source_version TEXT, ingested_at TIMESTAMPTZ DEFAULT NOW(),
    tags TEXT[] DEFAULT '{}', external_references JSONB DEFAULT '[]',
    risk_metadata JSONB DEFAULT '{}', graph_metadata JSONB DEFAULT '{}', metadata JSONB DEFAULT '{}',
    created_by TEXT DEFAULT 'system', updated_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE energy.gas_fields (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
    description TEXT, notes TEXT,
    latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, geojson JSONB DEFAULT '{}',
    location_id UUID REFERENCES energy.locations(uuid),
    organization_id BIGINT REFERENCES energy.organizations(id),
    reserve_estimate_cf DOUBLE PRECISION,
    production_mcfd DOUBLE PRECISION,
    status energy.lifecycle_state DEFAULT 'draft',
    operational_status energy.operational_status DEFAULT 'active',
    criticality energy.criticality_level DEFAULT 'medium',
    importance INTEGER DEFAULT 50, confidence DOUBLE PRECISION DEFAULT 0.8,
    is_deleted BOOLEAN DEFAULT FALSE, deleted_at TIMESTAMPTZ, deleted_by TEXT,
    version INTEGER DEFAULT 1, last_verified TIMESTAMPTZ DEFAULT NOW(),
    source_type TEXT, source_name TEXT, source_url TEXT, source_version TEXT, ingested_at TIMESTAMPTZ DEFAULT NOW(),
    tags TEXT[] DEFAULT '{}', external_references JSONB DEFAULT '[]',
    risk_metadata JSONB DEFAULT '{}', graph_metadata JSONB DEFAULT '{}', metadata JSONB DEFAULT '{}',
    created_by TEXT DEFAULT 'system', updated_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE energy.pipelines (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
    description TEXT, notes TEXT,
    latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, geojson JSONB DEFAULT '{}',
    location_id UUID REFERENCES energy.locations(uuid),
    organization_id BIGINT REFERENCES energy.organizations(id),
    length_km DOUBLE PRECISION,
    capacity_bpd DOUBLE PRECISION,
    diameter_inches DOUBLE PRECISION,
    max_pressure_psi DOUBLE PRECISION,
    commodity_type VARCHAR(50) DEFAULT 'crude',
    flow_direction VARCHAR(20) DEFAULT 'bidirectional',
    status energy.lifecycle_state DEFAULT 'draft',
    operational_status energy.operational_status DEFAULT 'active',
    criticality energy.criticality_level DEFAULT 'medium',
    importance INTEGER DEFAULT 50, confidence DOUBLE PRECISION DEFAULT 0.8,
    is_deleted BOOLEAN DEFAULT FALSE, deleted_at TIMESTAMPTZ, deleted_by TEXT,
    version INTEGER DEFAULT 1, last_verified TIMESTAMPTZ DEFAULT NOW(),
    source_type TEXT, source_name TEXT, source_url TEXT, source_version TEXT, ingested_at TIMESTAMPTZ DEFAULT NOW(),
    tags TEXT[] DEFAULT '{}', external_references JSONB DEFAULT '[]',
    risk_metadata JSONB DEFAULT '{}', graph_metadata JSONB DEFAULT '{}', metadata JSONB DEFAULT '{}',
    created_by TEXT DEFAULT 'system', updated_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE energy.refineries (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
    description TEXT, notes TEXT,
    latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, geojson JSONB DEFAULT '{}',
    location_id UUID REFERENCES energy.locations(uuid),
    organization_id BIGINT REFERENCES energy.organizations(id),
    capacity_bpd DOUBLE PRECISION,
    nelson_complexity_index DOUBLE PRECISION,
    crude_types_accepted TEXT[] DEFAULT '{}',
    output_products TEXT[] DEFAULT '{}',
    status energy.lifecycle_state DEFAULT 'draft',
    operational_status energy.operational_status DEFAULT 'active',
    criticality energy.criticality_level DEFAULT 'medium',
    importance INTEGER DEFAULT 50, confidence DOUBLE PRECISION DEFAULT 0.8,
    is_deleted BOOLEAN DEFAULT FALSE, deleted_at TIMESTAMPTZ, deleted_by TEXT,
    version INTEGER DEFAULT 1, last_verified TIMESTAMPTZ DEFAULT NOW(),
    source_type TEXT, source_name TEXT, source_url TEXT, source_version TEXT, ingested_at TIMESTAMPTZ DEFAULT NOW(),
    tags TEXT[] DEFAULT '{}', external_references JSONB DEFAULT '[]',
    risk_metadata JSONB DEFAULT '{}', graph_metadata JSONB DEFAULT '{}', metadata JSONB DEFAULT '{}',
    created_by TEXT DEFAULT 'system', updated_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE energy.power_plants (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
    description TEXT, notes TEXT,
    latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, geojson JSONB DEFAULT '{}',
    location_id UUID REFERENCES energy.locations(uuid),
    organization_id BIGINT REFERENCES energy.organizations(id),
    capacity_mw DOUBLE PRECISION,
    fuel_type VARCHAR(50),
    plant_type VARCHAR(50),
    status energy.lifecycle_state DEFAULT 'draft',
    operational_status energy.operational_status DEFAULT 'active',
    criticality energy.criticality_level DEFAULT 'medium',
    importance INTEGER DEFAULT 50, confidence DOUBLE PRECISION DEFAULT 0.8,
    is_deleted BOOLEAN DEFAULT FALSE, deleted_at TIMESTAMPTZ, deleted_by TEXT,
    version INTEGER DEFAULT 1, last_verified TIMESTAMPTZ DEFAULT NOW(),
    source_type TEXT, source_name TEXT, source_url TEXT, source_version TEXT, ingested_at TIMESTAMPTZ DEFAULT NOW(),
    tags TEXT[] DEFAULT '{}', external_references JSONB DEFAULT '[]',
    risk_metadata JSONB DEFAULT '{}', graph_metadata JSONB DEFAULT '{}', metadata JSONB DEFAULT '{}',
    created_by TEXT DEFAULT 'system', updated_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE energy.storage_facilities (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
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
    source_type TEXT, source_name TEXT, source_url TEXT, source_version TEXT, ingested_at TIMESTAMPTZ DEFAULT NOW(),
    tags TEXT[] DEFAULT '{}', external_references JSONB DEFAULT '[]',
    risk_metadata JSONB DEFAULT '{}', graph_metadata JSONB DEFAULT '{}', metadata JSONB DEFAULT '{}',
    created_by TEXT DEFAULT 'system', updated_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE energy.strategic_petroleum_reserves (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
    description TEXT, notes TEXT,
    latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, geojson JSONB DEFAULT '{}',
    location_id UUID REFERENCES energy.locations(uuid),
    organization_id BIGINT REFERENCES energy.organizations(id),
    capacity_barrels DOUBLE PRECISION,
    current_inventory_barrels DOUBLE PRECISION,
    max_drawdown_rate_bpd DOUBLE PRECISION,
    replenishment_rate_bpd DOUBLE PRECISION,
    status energy.lifecycle_state DEFAULT 'draft',
    operational_status energy.operational_status DEFAULT 'active',
    criticality energy.criticality_level DEFAULT 'critical',
    importance INTEGER DEFAULT 95, confidence DOUBLE PRECISION DEFAULT 0.8,
    is_deleted BOOLEAN DEFAULT FALSE, deleted_at TIMESTAMPTZ, deleted_by TEXT,
    version INTEGER DEFAULT 1, last_verified TIMESTAMPTZ DEFAULT NOW(),
    source_type TEXT, source_name TEXT, source_url TEXT, source_version TEXT, ingested_at TIMESTAMPTZ DEFAULT NOW(),
    tags TEXT[] DEFAULT '{}', external_references JSONB DEFAULT '[]',
    risk_metadata JSONB DEFAULT '{}', graph_metadata JSONB DEFAULT '{}', metadata JSONB DEFAULT '{}',
    created_by TEXT DEFAULT 'system', updated_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE energy.import_corridors (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
    description TEXT, notes TEXT,
    origin_location_id UUID REFERENCES energy.locations(uuid),
    destination_location_id UUID REFERENCES energy.locations(uuid),
    distance_km DOUBLE PRECISION,
    transit_time_days DOUBLE PRECISION,
    status energy.lifecycle_state DEFAULT 'draft',
    operational_status energy.operational_status DEFAULT 'active',
    criticality energy.criticality_level DEFAULT 'high',
    importance INTEGER DEFAULT 75, confidence DOUBLE PRECISION DEFAULT 0.8,
    is_deleted BOOLEAN DEFAULT FALSE, deleted_at TIMESTAMPTZ, deleted_by TEXT,
    version INTEGER DEFAULT 1, last_verified TIMESTAMPTZ DEFAULT NOW(),
    source_type TEXT, source_name TEXT, source_url TEXT, source_version TEXT, ingested_at TIMESTAMPTZ DEFAULT NOW(),
    tags TEXT[] DEFAULT '{}', external_references JSONB DEFAULT '[]',
    risk_metadata JSONB DEFAULT '{}', graph_metadata JSONB DEFAULT '{}', metadata JSONB DEFAULT '{}',
    created_by TEXT DEFAULT 'system', updated_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE energy.shipping_routes (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
    name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
    description TEXT, notes TEXT,
    origin_port_id BIGINT REFERENCES energy.ports(id),
    destination_port_id BIGINT REFERENCES energy.ports(id),
    distance_nm DOUBLE PRECISION,
    transit_time_days DOUBLE PRECISION,
    insurance_multiplier DOUBLE PRECISION DEFAULT 1.0,
    risk_score DOUBLE PRECISION DEFAULT 0.0,
    status energy.lifecycle_state DEFAULT 'draft',
    operational_status energy.operational_status DEFAULT 'active',
    criticality energy.criticality_level DEFAULT 'high',
    importance INTEGER DEFAULT 75, confidence DOUBLE PRECISION DEFAULT 0.8,
    is_deleted BOOLEAN DEFAULT FALSE, deleted_at TIMESTAMPTZ, deleted_by TEXT,
    version INTEGER DEFAULT 1, last_verified TIMESTAMPTZ DEFAULT NOW(),
    source_type TEXT, source_name TEXT, source_url TEXT, source_version TEXT, ingested_at TIMESTAMPTZ DEFAULT NOW(),
    tags TEXT[] DEFAULT '{}', external_references JSONB DEFAULT '[]',
    risk_metadata JSONB DEFAULT '{}', graph_metadata JSONB DEFAULT '{}', metadata JSONB DEFAULT '{}',
    created_by TEXT DEFAULT 'system', updated_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE energy.suppliers (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT gen_random_uuid(),
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
    source_type TEXT, source_name TEXT, source_url TEXT, source_version TEXT, ingested_at TIMESTAMPTZ DEFAULT NOW(),
    tags TEXT[] DEFAULT '{}', external_references JSONB DEFAULT '[]',
    risk_metadata JSONB DEFAULT '{}', graph_metadata JSONB DEFAULT '{}', metadata JSONB DEFAULT '{}',
    created_by TEXT DEFAULT 'system', updated_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- INDEXES
-- ============================================================================

CREATE INDEX idx_locations_type ON energy.locations(location_type);
CREATE INDEX idx_locations_parent ON energy.locations(parent_location_id);
CREATE INDEX idx_locations_is_deleted ON energy.locations(is_deleted) WHERE is_deleted = FALSE;

CREATE INDEX idx_organizations_type ON energy.organizations(organization_type);
CREATE INDEX idx_organizations_country ON energy.organizations(country_id);
CREATE INDEX idx_organizations_is_deleted ON energy.organizations(is_deleted) WHERE is_deleted = FALSE;

CREATE INDEX idx_relationships_source ON energy.entity_relationships(source_entity_type, source_entity_id);
CREATE INDEX idx_relationships_target ON energy.entity_relationships(target_entity_type, target_entity_id);
CREATE INDEX idx_relationships_type ON energy.entity_relationships(relationship_type);
CREATE INDEX idx_relationships_valid ON energy.entity_relationships(valid_from, valid_to);

CREATE INDEX idx_events_entity ON energy.infrastructure_events(entity_type, entity_id);
CREATE INDEX idx_events_type ON energy.infrastructure_events(event_type);
CREATE INDEX idx_events_occurred ON energy.infrastructure_events(occurred_at DESC);

CREATE INDEX idx_history_entity ON energy.capacity_history(entity_type, entity_id, metric_type);
CREATE INDEX idx_history_recorded ON energy.capacity_history(recorded_at DESC);

-- Per-entity indexes
CREATE INDEX idx_ports_location ON energy.ports(location_id);
CREATE INDEX idx_ports_org ON energy.ports(organization_id);
CREATE INDEX idx_ports_is_deleted ON energy.ports(is_deleted) WHERE is_deleted = FALSE;

CREATE INDEX idx_oil_fields_location ON energy.oil_fields(location_id);
CREATE INDEX idx_oil_fields_org ON energy.oil_fields(organization_id);
CREATE INDEX idx_oil_fields_is_deleted ON energy.oil_fields(is_deleted) WHERE is_deleted = FALSE;

CREATE INDEX idx_gas_fields_location ON energy.gas_fields(location_id);
CREATE INDEX idx_gas_fields_org ON energy.gas_fields(organization_id);
CREATE INDEX idx_gas_fields_is_deleted ON energy.gas_fields(is_deleted) WHERE is_deleted = FALSE;

CREATE INDEX idx_pipelines_location ON energy.pipelines(location_id);
CREATE INDEX idx_pipelines_org ON energy.pipelines(organization_id);
CREATE INDEX idx_pipelines_is_deleted ON energy.pipelines(is_deleted) WHERE is_deleted = FALSE;

CREATE INDEX idx_refineries_location ON energy.refineries(location_id);
CREATE INDEX idx_refineries_org ON energy.refineries(organization_id);
CREATE INDEX idx_refineries_is_deleted ON energy.refineries(is_deleted) WHERE is_deleted = FALSE;

-- Generic GIN indexes for JSONB and arrays
CREATE INDEX idx_ports_tags ON energy.ports USING GIN(tags);
CREATE INDEX idx_oil_fields_tags ON energy.oil_fields USING GIN(tags);
CREATE INDEX idx_gas_fields_tags ON energy.gas_fields USING GIN(tags);
CREATE INDEX idx_pipelines_tags ON energy.pipelines USING GIN(tags);
CREATE INDEX idx_refineries_tags ON energy.refineries USING GIN(tags);
CREATE INDEX idx_organizations_tags ON energy.organizations USING GIN(tags);

-- Name search indexes on all entities
CREATE INDEX idx_ports_name ON energy.ports(name);
CREATE INDEX idx_oil_fields_name ON energy.oil_fields(name);
CREATE INDEX idx_gas_fields_name ON energy.gas_fields(name);
CREATE INDEX idx_pipelines_name ON energy.pipelines(name);
CREATE INDEX idx_refineries_name ON energy.refineries(name);
CREATE INDEX idx_power_plants_name ON energy.power_plants(name);
CREATE INDEX idx_storage_facilities_name ON energy.storage_facilities(name);
CREATE INDEX idx_strategic_petroleum_reserves_name ON energy.strategic_petroleum_reserves(name);
CREATE INDEX idx_suppliers_name ON energy.suppliers(name);
