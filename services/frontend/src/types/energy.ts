export interface EnergyExternalReference {
  system: string;
  id: string;
  url?: string;
  label?: string;
}

export interface EnergyProvenance {
  source_type?: string;
  source_name?: string;
  source_url?: string;
  source_version?: string;
  ingested_at?: string;
}

export interface EnergyAuditFields {
  created_by: string;
  updated_by: string;
  created_at?: string;
  updated_at?: string;
}

export interface EnergyBaseEntity {
  uuid?: string;
  name: string;
  slug?: string;
  description?: string;
  notes?: string;
  latitude?: number;
  longitude?: number;
  geojson?: Record<string, unknown>;
  location_id?: string;
  organization_id?: number;
  status?: string;
  operational_status?: string;
  criticality?: string;
  importance?: number;
  confidence?: number;
  is_deleted?: boolean;
  version?: number;
  last_verified?: string;
  tags?: string[];
  external_references?: EnergyExternalReference[];
  risk_metadata?: Record<string, unknown>;
  graph_metadata?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  provenance?: EnergyProvenance;
  audit?: EnergyAuditFields;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface BulkImportResult {
  created: number;
  updated: number;
  errors: string[];
}

export interface Location extends EnergyBaseEntity {
  location_type?: string;
  parent_location_id?: string;
  iso_code?: string;
  iso_code_3?: string;
  region?: string;
}

export interface Organization extends EnergyBaseEntity {
  organization_type?: string;
  country_id?: string;
}

export interface Commodity extends EnergyBaseEntity {
  commodity_type?: string;
  unit?: string;
  benchmark_price?: number;
  api_gravity?: number;
  sulfur_content?: number;
  category?: string;
}

export interface Port extends EnergyBaseEntity {
  port_type?: string;
  throughput_mtpa?: number;
  storage_capacity_barrels?: number;
  max_draft_m?: number;
  annual_capacity_mtpa?: number;
}

export interface OilField extends EnergyBaseEntity {
  reserve_estimate_barrels?: number;
  production_bpd?: number;
  api_gravity?: number;
  sulfur_content?: number;
}

export interface GasField extends EnergyBaseEntity {
  reserve_estimate_cf?: number;
  production_mcfd?: number;
}

export interface Pipeline extends EnergyBaseEntity {
  length_km?: number;
  capacity_bpd?: number;
  diameter_inches?: number;
  max_pressure_psi?: number;
  commodity_type?: string;
  flow_direction?: string;
}

export interface Refinery extends EnergyBaseEntity {
  capacity_bpd?: number;
  nelson_complexity_index?: number;
  crude_types_accepted?: string[];
  output_products?: string[];
}

export interface PowerPlant extends EnergyBaseEntity {
  capacity_mw?: number;
  fuel_type?: string;
  plant_type?: string;
}

export interface StorageFacility extends EnergyBaseEntity {
  capacity_barrels?: number;
  facility_type?: string;
}

export interface StrategicPetroleumReserve extends EnergyBaseEntity {
  capacity_barrels?: number;
  current_inventory_barrels?: number;
  max_drawdown_rate_bpd?: number;
  replenishment_rate_bpd?: number;
}

export interface ImportCorridor extends EnergyBaseEntity {
  origin_location_id?: string;
  destination_location_id?: string;
  distance_km?: number;
  transit_time_days?: number;
}

export interface ShippingRoute extends EnergyBaseEntity {
  origin_port_id?: number;
  destination_port_id?: number;
  distance_nm?: number;
  transit_time_days?: number;
  insurance_multiplier?: number;
  risk_score?: number;
}

export interface Supplier extends EnergyBaseEntity {
  supplier_type?: string;
  market_share_pct?: number;
}

export interface EntityRelationship {
  source_entity_type: string;
  source_entity_id: number;
  target_entity_type: string;
  target_entity_id: number;
  relationship_type: string;
  confidence?: number;
  valid_from?: string;
  valid_to?: string;
  metadata?: Record<string, unknown>;
  source_name?: string | null;
  source_country?: string | null;
  target_name?: string | null;
  target_country?: string | null;
}

export interface InfrastructureEvent {
  entity_type: string;
  entity_id: number;
  event_type: string;
  severity?: string;
  description?: string;
  occurred_at?: string;
  resolved_at?: string;
  metadata?: Record<string, unknown>;
}

export interface CapacityRecord {
  entity_type: string;
  entity_id: number;
  metric_type: string;
  value: number;
  unit?: string;
  recorded_at?: string;
  metadata?: Record<string, unknown>;
}
