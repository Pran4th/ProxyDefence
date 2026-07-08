export interface DisruptionSignal {
  id: number;
  uuid: string;
  title: string;
  description: string;
  source: string;
  severity: "low" | "moderate" | "elevated" | "high" | "critical";
  risk_dimension: "geopolitical" | "operational" | "economic" | "environmental";
  affected_entity_type: string | null;
  affected_entity_uuid: string | null;
  affected_commodities: string[];
  affected_regions: string[];
  confidence: number;
  evidence_urls: string[];
  expires_at: string;
  created_at: string;
}

export interface RiskScore {
  id: number;
  uuid: string;
  entity_uuid: string;
  entity_type: string;
  dimension: string;
  score: number;
  confidence: number;
  breakdown: Record<string, number>;
  expires_at: string;
  created_at: string;
}

export interface RiskDashboard {
  total_active_signals: number;
  high_severity_signals: number;
  average_risk_score: number;
  latest_signals: DisruptionSignal[];
  risk_by_dimension: { dimension: string; score: number }[];
}

export interface ScenarioResult {
  scenario_id: number;
  scenario_uuid: string;
  created_at: string;
  name: string;
  risk_scores: Record<string, number>;
  risk_level: string;
  assessment: string;
}

export interface CommodityPrice {
  id: number;
  uuid: string;
  commodity_name: string;
  commodity_family: string;
  price: number;
  unit: string;
  change_pct: number;
  source: string;
  recorded_at: string;
}

export interface PortCongestion {
  id: number;
  uuid: string;
  port_name: string;
  country: string;
  congestion_pct: number;
  waiting_vessels: number;
  avg_wait_hours: number;
  recorded_at: string;
}

export interface TankerAvailability {
  id: number;
  uuid: string;
  vessel_type: string;
  vessels_available: number;
  total_vessels: number;
  avg_daily_rate_usd: number;
  utilization_pct: number;
  recorded_at: string;
}

export interface SanctionEntry {
  id: number;
  uuid: string;
  country_code: string;
  country_name: string;
  sanction_scope: string;
  imposed_by: string;
  affected_commodities: string;
  status: string;
  is_active: boolean;
  source: string;
  created_at: string;
}

export interface ScenarioAssumption {
  id: number;
  uuid: string;
  name: string;
  description: string;
  assumptions: Record<string, number>;
  risk_dimensions: string[];
  created_by: string;
  created_at: string;
}
