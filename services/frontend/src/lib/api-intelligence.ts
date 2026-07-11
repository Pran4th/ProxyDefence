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
