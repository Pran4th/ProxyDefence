import { api } from "./api";
import type {
  DisruptionSignal,
  RiskDashboard,
  ScenarioResult,
  ScenarioAssumption,
  CommodityPrice,
  PortCongestion,
  TankerAvailability,
  SanctionEntry,
} from "@/types/intelligence";

const BASE = "/api/v1/intelligence";

interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export async function fetchRiskDashboard(): Promise<RiskDashboard> {
  const { data } = await api.get(`${BASE}/risk`);
  return data;
}

export async function fetchEntityRisk(entityUuid: string, entityType: string = "import_corridors") {
  const { data } = await api.get(`${BASE}/risk/entity/${entityUuid}`, {
    params: { entity_type: entityType },
  });
  return data;
}

export async function fetchRiskTrends(
  entityUuid?: string,
  dimension?: string
) {
  const { data } = await api.get(`${BASE}/risk/trends`, {
    params: { entity_uuid: entityUuid, dimension },
  });
  return data;
}

export async function fetchSignals(params?: {
  severity?: string;
  risk_dimension?: string;
  limit?: number;
  offset?: number;
}): Promise<PaginatedResponse<DisruptionSignal>> {
  const { data } = await api.get(`${BASE}/signals`, { params });
  return data;
}

export async function fetchSignal(uuid: string): Promise<DisruptionSignal> {
  const { data } = await api.get(`${BASE}/signals/${uuid}`);
  return data;
}

export async function createSignal(body: Partial<DisruptionSignal>): Promise<DisruptionSignal> {
  const { data } = await api.post(`${BASE}/signals`, body);
  return data;
}

export async function fetchRiskFactors() {
  const { data } = await api.get(`${BASE}/risk-factors`);
  return data;
}

export async function evaluateScenario(body: {
  name: string;
  description?: string;
  assumptions: Record<string, number>;
  risk_dimensions?: string[];
}): Promise<ScenarioResult> {
  const { data } = await api.post(`${BASE}/scenarios/evaluate`, body);
  return data;
}

export async function fetchScenarios(): Promise<PaginatedResponse<ScenarioAssumption>> {
  const { data } = await api.get(`${BASE}/scenarios`);
  return data;
}

export async function fetchScenario(uuid: string): Promise<ScenarioAssumption> {
  const { data } = await api.get(`${BASE}/scenarios/${uuid}`);
  return data;
}

export async function fetchCommodityPrices(params?: {
  limit?: number;
  offset?: number;
}): Promise<PaginatedResponse<CommodityPrice>> {
  const { data } = await api.get(`${BASE}/commodity-prices`, { params });
  return data;
}

export async function fetchPortCongestion(params?: {
  limit?: number;
  offset?: number;
}): Promise<PaginatedResponse<PortCongestion>> {
  const { data } = await api.get(`${BASE}/port-congestion`, { params });
  return data;
}

export async function fetchTankerAvailability(params?: {
  limit?: number;
  offset?: number;
}): Promise<PaginatedResponse<TankerAvailability>> {
  const { data } = await api.get(`${BASE}/tanker-availability`, { params });
  return data;
}

export async function fetchSanctions(params?: {
  limit?: number;
  offset?: number;
}): Promise<PaginatedResponse<SanctionEntry>> {
  const { data } = await api.get(`${BASE}/sanctions`, { params });
  return data;
}

// ── Corridor & supplier disruption probability ──────────────────────────

export interface CorridorDriver {
  signal_uuid: string;
  title: string;
  severity: string;
  detected_at: string;
  weight: number;
}

export interface CorridorRisk {
  key: string;
  name: string;
  probability_30d: number;
  confidence: number;
  components: {
    signal_pressure: number | null;
    entity_risk: number | null;
    instability: number | null;
    ais_anomaly: number | null;
  };
  drivers: CorridorDriver[];
  india_import_share_pct: number;
  india_import_share_year: number | null;
  polyline: [number, number][];
}

export interface CorridorRiskResponse {
  corridors: CorridorRisk[];
  assumptions: { name: string; value: unknown; source: string; how_to_test: string }[];
  ais_snapshot_at: string | null;
  computed_at: string;
}

export interface SupplierRisk {
  supplier_uuid: string;
  name: string;
  country: string | null;
  iso_code: string | null;
  own_risk: number;
  corridor_factor: number;
  disruption_probability_30d: number;
}

export async function fetchCorridorRisk(): Promise<CorridorRiskResponse> {
  const { data } = await api.get(`${BASE}/corridors`);
  return data;
}

export async function fetchSupplierRisk(): Promise<{ items: SupplierRisk[]; total: number }> {
  const { data } = await api.get(`${BASE}/suppliers/risk`);
  return data;
}

// ── Command Center (signal → decision golden thread) ────────────────────

export interface CommandResponseBundle {
  signal: DisruptionSignal;
  scenario: { uuid: string; name: string; severity: string };
  twin_run: {
    run_uuid: string;
    ticks_executed: number;
    execution_time_ms: number;
    aggregate_impacts: Record<string, number>;
  };
  spr_run: Record<string, unknown>;
  procurement_run: Record<string, unknown>;
  evidence_bundle: {
    uuid: string;
    mode: "live" | "cached" | "replay" | "fallback";
    input_provenance: Array<{
      source: string;
      display_name: string;
      mode: string;
      observed_at: string | null;
      freshness_seconds: number | null;
      fallback_reason: string | null;
    }>;
    decision_brief: Record<string, unknown>;
  };
  telemetry: {
    uuid: string;
    signal_detected_at: string;
    analysis_started_at: string;
    analysis_completed_at: string;
    recommendation_generated_at: string;
    total_latency_seconds: number;
    pipeline_latency_seconds: number;
  };
}

export async function respondToSignal(body: {
  signal_uuid?: string;
  auto?: boolean;
  refinery_uuid?: string;
}): Promise<CommandResponseBundle> {
  const { data } = await api.post(`${BASE}/command/respond`, body, {
    timeout: 180000,
  });
  return data;
}

export interface ResponseTelemetryEntry {
  uuid: string;
  signal_title: string | null;
  signal_severity: string | null;
  signal_detected_at: string;
  analysis_started_at: string;
  recommendation_generated_at: string;
  total_latency_seconds: number;
}

export async function fetchResponseTelemetry(): Promise<{
  items: ResponseTelemetryEntry[];
  total: number;
  pipeline_latency_p50_seconds: number | null;
  pipeline_latency_p95_seconds: number | null;
}> {
  const { data } = await api.get(`${BASE}/command/telemetry`);
  return data;
}

export async function recordEvidenceApproval(
  bundleUuid: string,
  body: { status: "reviewed" | "approved" | "executed" | "outcome_recorded"; actor?: string; note?: string }
) {
  const { data } = await api.post(`${BASE}/command/evidence/${bundleUuid}/approval`, body);
  return data;
}

// ── AIS vessel positions (cached AISstream snapshot) ────────────────────

export interface AisVessel {
  mmsi: string;
  name: string;
  latitude: number;
  longitude: number;
  chokepoint: string;
  speed_knots: number | null;
  heading: number | null;
  timestamp: string;
}

export async function fetchAisPositions(): Promise<{
  items: AisVessel[];
  total: number;
  snapshot_at: string | null;
}> {
  const { data } = await api.get(`${BASE}/ais/positions`);
  return data;
}

// ── Signal reasoning ("why is this high") ────────────────────────────────

export interface SignalExplanation {
  signal_uuid: string;
  reasoning: string;
  matched_corridor: string | null;
  corridor_name: string | null;
  corridor_probability_30d: number | null;
  india_import_share_pct: number | null;
  corridor_partner_countries: string[];
  estimated_exposure_usd: number | null;
  assumptions: { name: string; value: unknown; source: string; how_to_test: string }[];
}

export async function fetchSignalExplanation(signalUuid: string): Promise<SignalExplanation> {
  const { data } = await api.get(`${BASE}/signals/${signalUuid}/explain`);
  return data;
}

// ── Article market impact ────────────────────────────────────────────────

export interface ArticleImpact {
  has_impact_data: boolean;
  signals: (SignalExplanation & {
    signal_uuid: string;
    affected_entity_type: string | null;
    severity: string;
    risk_dimension: string;
  })[];
}

export async function fetchArticleImpact(articleId: number): Promise<ArticleImpact> {
  const { data } = await api.get(`${BASE}/articles/${articleId}/impact`);
  return data;
}

// ── Real-time market impact feed ─────────────────────────────────────────

export interface ImpactFeedItem extends SignalExplanation {
  title: string;
  severity: string;
  risk_dimension: string;
  source: string;
  detected_at: string;
  based_on_signals: number;
}

export async function fetchImpactFeed(limit = 15): Promise<{
  items: ImpactFeedItem[];
  total: number;
  generated_at: string;
}> {
  const { data } = await api.get(`${BASE}/impact-feed`, { params: { limit } });
  return data;
}
