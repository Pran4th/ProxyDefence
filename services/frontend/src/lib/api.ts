import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export interface EntityProfile {
  entity_text: string;
  entity_type: string;
  mention_frequency: number;
  risk_trend: number;
  associated_events: number[];
  associated_relationships: number[];
  last_seen: string;
}

export interface Article {
  id: number;
  article_id: number;
  title: string;
  content: string;
  source: string;
  published_at: string;
  summary?: string;
  topic?: string;
  threat_score?: number;
  geopolitical_risk?: number;
  risk_level?: "low" | "medium" | "high" | "critical";
  sentiment?: "positive" | "negative" | "neutral";
  confidence?: number;
  url?: string;
  image_url?: string;
  energy_context?: {
    locations: any[];
    infrastructure: any[];
    organizations: any[];
    commodities: any[];
    infrastructure_events: any[];
    context: {
      countries_mentioned: string[];
      infrastructure_mentioned: string[];
      organizations_mentioned: string[];
      commodities_mentioned: string[];
      infrastructure_event_count: number;
      total_linked_assets: number;
    };
  } | null;
}

export interface AnalyticsSummary {
  total_articles: number;
  articles_last_24h: number;
  avg_confidence: number;
  avg_threat_score: number;
  high_risk_articles: number;
  sentiment_distribution: Record<string, number>;
  top_topics: Array<{ topic: string; count: number }>;
}

export interface DashboardStats {
  articles: number;
  events: number;
  entities: number;
  relationships: number;
}

export interface ThreatAnalytics {
  risk_distribution: {
    risk_level: string;
    count: number;
  }[];
  topic_distribution: {
    topic: string;
    count: number;
  }[];
}

export interface TimeSeriesPoint {
  bucket: string;
  articles: number;
  avg_threat_score: number;
}

export interface EntityInsight {
  entity: string;
  type: string;
  mentions: number;
  avg_confidence: number;
}

export interface TopicBreakdown {
  topic: string;
  count: number;
  avg_threat_score: number;
}

export interface GraphNode {
  id: string;
  group?: string;
  val?: number;
  label?: string;
}

export interface GraphLink {
  source: string;
  target: string;
  value?: number;
  type?: string;
  relationship?: string;
  confidence?: number;
}

export interface AttackGraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

export interface NetworkGraphData {
  nodes: GraphNode[];
  edges: GraphLink[];
}

export interface NotificationPreferences {
  critical_threat_alerts: boolean;
  weekly_reports: boolean;
  simulation_results: boolean;
  system_updates: boolean;
}

export interface AuthUser {
  id: number;
  email: string;
  username: string;
  role: string;
  organization?: string | null;
  location?: string | null;
  notification_preferences?: NotificationPreferences;
  created_at: string;
}
export interface Event {
  id: number;
  title: string;
  summary: string;
  topic: string;
  risk_score: number;
  risk_level: string;
  confidence: number;
  article_count: number;
  last_seen?: string;
  updated_at?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}
export interface SearchResponse {
  query: string;
  total_results: number;
  results: Article[];
  limit: number;
  offset: number;
}

export interface Case {
  id: number;
  title: string;
  description?: string;
  status: string;
  priority: string;
  owner_id?: number;
  created_at: string;
  updated_at: string;
  item_count?: number;
  notes_count?: number;
}

export interface CaseNote {
  id: number;
  case_id: number;
  note_text: string;
  created_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface IntelligenceReport {
  id: number;
  title: string;
  executive_summary: string;
  key_actors: any[];
  key_events: any[];
  threat_assessment: string;
  confidence_score: number;
  recommendations: string[];
  source_article_ids: number[];
  source_case_id: number | null;
  created_by: number | null;
  created_at: string;
}
export interface DashboardV2 {
  events: number;
  alerts: number;
  open_alerts: number;
  investigating_alerts: number;
  closed_alerts: number;

  watchlists: number;
  cases: number;
  reports: number;

  high_risk_events: number;
  critical_events: number;

  average_risk_score: number;

  top_event?: {
    id: number;
    title: string;
    risk_score: number;
    risk_level: string;
    last_seen: string;
  };

  recent_reports?: {
    id: number;
    title: string;
    created_at: string;
  }[];

  risk_distribution: {
    low: number;
    medium: number;
    high: number;
    critical: number;
  };
}
export interface EnergyImpact {
  severity: string;
  countries_involved: string[];
  infrastructure_affected: string[];
  organizations_involved: string[];
  commodities_involved: string[];
  infrastructure_event_count: number;
  total_energy_articles: number;
}

export interface CopilotResponse {
  question: string;
  conversation_id: number | null;
  threat_level: string;
  summary: string;
  articles: Article[];
  entities: { entity_text: string; entity_type: string; mentions: number }[];
  entity_profiles: EntityProfile[];
  threat_indicators: { military: number; economic: number; diplomatic: number };
  relationships: {
    source_entity: string;
    target_entity: string;
    relationship_type: string;
    confidence: number;
  }[];
  events: { id: number; title: string; topic: string; risk_level: string; risk_score: number }[];
  energy_impact?: EnergyImpact;
  energy_assessment?: string;
}

export interface CopilotConversation {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface CopilotMessage {
  id: number;
  role: string;
  content: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface CaseDetails extends Case {
  items: {
    item_type: string;
    item_id: number;
    created_at: string;
  }[];

  notes: CaseNote[];
}
interface LoginPayload {
  email: string;
  password: string;
}

interface RegisterPayload extends LoginPayload {
  username: string;
}


export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});
export const queryCopilot = async (
  question: string
) => {
  const response = await api.post<CopilotResponse>(
    "/copilot/query",
    {
      question,
    }
  );

  return response.data;
};

export const saveCopilotAnswerToCase = async (payload: {
  case_id: number;
  question: string;
  answer: CopilotResponse;
}) => {
  const response = await api.post("/copilot/save-to-case", payload);
  return response.data;
};
export const queryCopilotStream = (
  question: string,
  onEvent: (event: { type: string; value: unknown }) => void,
  onDone: () => void,
  onError: (error: string) => void,
  conversationId?: number,
): AbortController => {
  const controller = new AbortController();

  fetch(`${API_BASE_URL}/copilot/query/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${localStorage.getItem("proxydefence.token")}`,
    },
    body: JSON.stringify({ question, conversation_id: conversationId }),
    signal: controller.signal,
  })
    .then(async (response) => {
      const reader = response.body?.getReader();
      if (!reader) return;
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === "done") onDone();
              else if (data.type === "error") onError(data.value);
              else onEvent(data);
            } catch {
              // skip malformed events
            }
          }
        }
      }
      onDone();
    })
    .catch((err) => {
      if (err.name !== "AbortError") onError(err.message);
    });

  return controller;
};

export const createCopilotConversation = async (title: string) => {
  const response = await api.post<{ conversation_id: number; title: string }>(
    "/copilot/chat",
    { title },
  );
  return response.data;
};

export const listCopilotConversations = async (limit = 20) => {
  const response = await api.get<{ conversations: CopilotConversation[] }>(
    "/copilot/chat",
    { params: { limit } },
  );
  return response.data;
};

export const getCopilotConversationMessages = async (conversationId: number) => {
  const response = await api.get<{ conversation_id: number; messages: CopilotMessage[] }>(
    `/copilot/chat/${conversationId}`,
  );
  return response.data;
};

export const setAuthToken = (token: string | null) => {
  if (token) {
    api.defaults.headers.common.Authorization = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common.Authorization;
  }
};

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("proxydefence.token");
      localStorage.removeItem("proxydefence.user");
      setAuthToken(null);
    }
    return Promise.reject(error);
  },
);

export const loginUser = async (payload: LoginPayload) => {
  const response = await api.post<AuthResponse>("/auth/login", payload);
  return response.data;
};

export const registerUser = async (payload: RegisterPayload) => {
  const response = await api.post<AuthResponse>("/auth/register", payload);
  return response.data;
};

export const getCurrentUser = async () => {
  const response = await api.get<AuthUser>("/auth/me");
  return response.data;
};

export interface SystemStatus {
  status: "healthy" | "unhealthy" | "degraded";
  [key: string]: unknown;
}

/** Real Postgres/Elasticsearch/Kafka health, not a hardcoded "ACTIVE" label. */
export const fetchSystemStatus = async () => {
  const response = await api.get<SystemStatus>("/status");
  return response.data;
};

export const updateProfile = async (params: { organization?: string | null; location?: string | null }) => {
  const response = await api.patch<AuthUser>("/auth/me", params);
  return response.data;
};

export const updateNotificationPreferences = async (params: NotificationPreferences) => {
  const response = await api.patch<AuthUser>("/auth/me/notifications", params);
  return response.data;
};

export const changePassword = async (params: { current_password: string; new_password: string }) => {
  const response = await api.patch("/auth/me/password", params);
  return response.data;
};

export const fetchArticles = async (params?: {
  limit?: number;
  offset?: number;
  sentiment?: string;
  topic?: string;
  risk_level?: string;
}) => {
  const response = await api.get<Article[]>("/articles", { params });
  return response.data;
};

export const fetchArticle = async (id: number) => {
  const response = await api.get<Article>(`/articles/${id}`);
  return response.data;
};

export const fetchAnalyticsSummary = async () => {
  const response = await api.get<AnalyticsSummary>("/analytics/summary");
  return response.data;
};

export interface PublicPreviewArticle {
  title: string;
  source: string;
  topic: string;
  summary: string;
  risk_level: string;
  threat_score: number;
  sentiment: string;
  published_at: string;
}

export interface PublicPreview {
  articles: PublicPreviewArticle[];
  stats: {
    total_articles: number;
    high_risk_articles: number;
    avg_confidence: number;
    avg_threat_score: number;
    trained_models: number;
    datasets: number;
  };
}

/** Unauthenticated preview data for the landing page — works before sign-in. */
export const fetchPublicPreview = async () => {
  const response = await api.get<PublicPreview>("/public/preview");
  return response.data;
};

export interface PublicArticleSummary {
  id: number;
  title: string;
  source: string;
  topic?: string;
  summary?: string;
  risk_level?: Article["risk_level"];
  threat_score?: number;
  sentiment?: Article["sentiment"];
  published_at: string;
}

/** Unauthenticated, paginated article list — powers the intel feed for anonymous visitors. */
export const fetchPublicArticles = async (params?: {
  limit?: number;
  offset?: number;
  sentiment?: string;
  topic?: string;
  risk_level?: string;
}) => {
  const response = await api.get<PublicArticleSummary[]>("/public/articles", { params });
  return response.data;
};

export const fetchPublicArticle = async (id: number) => {
  const response = await api.get<PublicArticleSummary>(`/public/articles/${id}`);
  return response.data;
};

export const fetchDashboardStats = async () => {
  const response = await api.get<DashboardV2>(
    "/analytics/dashboard-v2"
  );

  return response.data;
};

export const fetchThreatAnalytics = async () => {
  const response = await api.get<ThreatAnalytics>("/analytics/threat-trends");
  return response.data;
};

export const fetchAttackGraph = async () => {
  const response = await api.get<AttackGraphData>("/analytics/graph");
  return response.data;
};

export const fetchTimeSeries = async () => {
  const response = await api.get<TimeSeriesPoint[]>("/analytics/timeseries");
  return response.data;
};

export const fetchEntityInsights = async () => {
  const response = await api.get<EntityInsight[]>("/analytics/entities");
  return response.data;
};

export const fetchTopicBreakdown = async () => {
  const response = await api.get<TopicBreakdown[]>("/analytics/topics");
  return response.data;
};

export const searchArticles = async (
  query: string,
  filters?: { topic?: string; risk_level?: string; limit?: number; offset?: number }
) => {
  const response = await api.get<SearchResponse>(
    "/search",
    {
      params: {
        q: query,
        ...filters,
      },
    }
  );

  return response.data;
};

export const fetchArticleEntities = async (articleId: number) => {
  const response = await api.get<Array<{ entity_text: string; entity_type: string; confidence: number }>>(
    `/articles/${articleId}/entities`,
  );
  return response.data;
};

export const fetchNetworkGraph = async () => {
  const response = await api.get<NetworkGraphData>("/graph/network");
  return response.data;
};
export const fetchTopEvents = async (limit = 20) => {
  const response = await api.get<Event[]>("/analytics/events", {
    params: { limit },
  });
  return response.data;
};

export const fetchCases = async () => {
  const response = await api.get<Case[]>(
    "/cases"
  );

  return response.data;
};

export const fetchCase = async (
  caseId: number
) => {
  const response = await api.get(
    `/cases/${caseId}`
  );

  return response.data;
};

export const createCase = async (
  payload: {
    title: string;
    description?: string;
    priority?: string;
  }
) => {
  const response = await api.post(
    "/cases",
    payload
  );

  return response.data;
};

export const addCaseNote = async (
  caseId: number,
  note: string
) => {
  const response = await api.post(
    `/cases/${caseId}/notes`,
    {
      note,
    }
  );

  return response.data;
};
export const fetchReports = async () => {
  const response = await api.get<
    IntelligenceReport[]
  >("/cases/reports");

  return response.data;
};

export const fetchReport = async (
  reportId: number
) => {
  const response = await api.get<
    IntelligenceReport
  >(`/cases/reports/${reportId}`);

  return response.data;
};

export const generateCaseReport = async (
  caseId: number
) => {
  const response = await api.post(
    `/cases/${caseId}/report`
  );

  return response.data;
};
export const addCaseItem = async (
  caseId: number,
  item_type: string,
  item_id: number
) => {
  const response = await api.post(
    `/cases/${caseId}/items`,
    {
      item_type,
      item_id,
    }
  );

  return response.data;
};
export const removeCaseItem = async (
  caseId: number,
  itemType: string,
  itemId: number
) => {
  const response = await api.delete(
    `/cases/${caseId}/items/${itemType}/${itemId}`
  );

  return response.data;
};
export const fetchCaseNotes = async (
  caseId: number
) => {
  const response = await api.get<CaseNote[]>(
    `/cases/${caseId}/notes`
  );

  return response.data;
};

// ── Digital Twin API ────────────────────────────────────────────────────────

export interface NetworkNode {
  id: number;
  uuid: string;
  name: string;
  node_type: string;
  category: string;
  capacity_bpd?: number;
  current_inventory_barrels?: number;
  operational_status: string;
  criticality: string;
  country?: string;
}

export interface NetworkEdge {
  id: number;
  source_node_id: number;
  target_node_id: number;
  edge_type: string;
  max_capacity_bpd?: number;
  current_flow_bpd: number;
  utilization_pct: number;
  source_name: string;
  target_name: string;
  source_type: string;
  target_type: string;
}

export interface SimulationRun {
  uuid: string;
  name: string;
  status: string;
  tick_interval: string;
  max_ticks: number;
  current_tick: number;
  supply_gap_bpd: number;
  economic_impact_usd: number;
  gdp_impact_pct: number;
  execution_time_ms: number;
  created_at: string;
}

export interface SimulationScenario {
  id: number;
  uuid: string;
  name: string;
  description: string;
  category: string;
  severity: string;
  is_template: boolean;
  config: any;
  assumptions: any;
}

export const buildNetwork = async () => {
  const response = await api.post("/api/v1/intelligence/digital-twin/network/build");
  return response.data;
};

export const fetchDigitalTwinNetwork = async () => {
  const response = await api.get("/api/v1/intelligence/digital-twin/network");
  return response.data;
};

export const fetchFlows = async () => {
  const response = await api.get("/api/v1/intelligence/digital-twin/flows");
  return response.data;
};

export const fetchAssets = async (nodeType?: string) => {
  const params = nodeType ? { node_type: nodeType } : {};
  const response = await api.get("/api/v1/intelligence/digital-twin/assets", { params });
  return response.data;
};

export const fetchDigitalTwinHealth = async () => {
  const response = await api.get("/api/v1/intelligence/digital-twin/health");
  return response.data;
};

export const fetchScenarios = async (templateOnly?: boolean) => {
  const params: any = {};
  if (templateOnly !== undefined) params.is_template = templateOnly;
  const response = await api.get("/api/v1/intelligence/digital-twin/scenarios", { params });
  return response.data;
};

export const createScenario = async (scenario: {
  name: string;
  description?: string;
  category?: string;
  severity?: string;
  config: any;
  assumptions?: any;
}) => {
  const response = await api.post("/api/v1/intelligence/digital-twin/scenarios", scenario);
  return response.data;
};

export const runSimulation = async (params: {
  scenario_uuid?: string;
  name?: string;
  description?: string;
  tick_interval?: string;
  max_ticks?: number;
  config?: any;
}) => {
  const response = await api.post("/api/v1/intelligence/digital-twin/run", params);
  return response.data;
};

export const fetchSimulationRuns = async (status?: string) => {
  const params: any = {};
  if (status) params.status = status;
  const response = await api.get("/api/v1/intelligence/digital-twin/runs", { params });
  return response.data;
};

export const fetchSimulationRun = async (uuid: string) => {
  const response = await api.get(`/api/v1/intelligence/digital-twin/runs/${uuid}`);
  return response.data;
};

export const fetchRunTimeline = async (uuid: string) => {
  const response = await api.get(`/api/v1/intelligence/digital-twin/runs/${uuid}/timeline`);
  return response.data;
};

export const fetchRunImpacts = async (uuid: string) => {
  const response = await api.get(`/api/v1/intelligence/digital-twin/runs/${uuid}/impacts`);
  return response.data;
};

export const fetchRunNetwork = async (uuid: string, tick?: number) => {
  const params: any = {};
  if (tick !== undefined) params.tick = tick;
  const response = await api.get(`/api/v1/intelligence/digital-twin/runs/${uuid}/network`, { params });
  return response.data;
};

export const deleteSimulationRun = async (uuid: string) => {
  const response = await api.delete(`/api/v1/intelligence/digital-twin/runs/${uuid}`);
  return response.data;
};

export const compareSimulationRuns = async (uuids: string[]) => {
  const response = await api.get("/api/v1/intelligence/digital-twin/compare", {
    params: { run_uuids: uuids.join(",") },
  });
  return response.data;
};

export const fetchRecommendations = async (runUuid?: string) => {
  const params: any = {};
  if (runUuid) params.run_uuid = runUuid;
  const response = await api.get("/api/v1/intelligence/digital-twin/recommendations", { params });
  return response.data;
};

export const fetchDemandProfiles = async () => {
  const response = await api.get("/api/v1/intelligence/digital-twin/demand");
  return response.data;
};

export const seedScenarios = async () => {
  const response = await api.post("/api/v1/intelligence/digital-twin/scenarios/seed");
  return response.data;
};

export const seedDemandProfiles = async () => {
  const response = await api.post("/api/v1/intelligence/digital-twin/demand/seed");
  return response.data;
};

export const estimateBaselineFlows = async () => {
  const response = await api.post("/api/v1/intelligence/digital-twin/flows/estimate-baseline");
  return response.data;
};

export const fetchDownstream = async (nodeId: number) => {
  const response = await api.get(`/api/v1/intelligence/digital-twin/network/downstream/${nodeId}`);
  return response.data;
};

export const fetchUpstream = async (nodeId: number) => {
  const response = await api.get(`/api/v1/intelligence/digital-twin/network/upstream/${nodeId}`);
  return response.data;
};

export const fetchDependencies = async (nodeId: number, depth?: number) => {
  const params: any = {};
  if (depth !== undefined) params.depth = depth;
  const response = await api.get(`/api/v1/intelligence/digital-twin/network/dependencies/${nodeId}`, { params });
  return response.data;
};

export const findPath = async (fromNode: number, toNode: number) => {
  const response = await api.get("/api/v1/intelligence/digital-twin/network/path", {
    params: { from_node: fromNode, to_node: toNode },
  });
  return response.data;
};

// ── Procurement Orchestrator API ────────────────────────────────────────

export const enrichSuppliers = async () => {
  const response = await api.post("/api/v1/intelligence/procurement/suppliers/enrich");
  return response.data;
};

export const fetchSuppliers = async () => {
  const response = await api.get("/api/v1/intelligence/procurement/suppliers");
  return response.data;
};

export const fetchSupplierProfile = async (uuid: string) => {
  const response = await api.get(`/api/v1/intelligence/procurement/suppliers/${uuid}`);
  return response.data;
};

export const findAlternativeSuppliers = async (supplierUuid: string, commodityUuid: string) => {
  const response = await api.get(`/api/v1/intelligence/procurement/suppliers/${supplierUuid}/alternatives`, {
    params: { commodity_uuid: commodityUuid },
  });
  return response.data;
};

export const computeCompatibility = async () => {
  const response = await api.post("/api/v1/intelligence/procurement/compatibility/compute");
  return response.data;
};

export const fetchCompatibility = async (refineryUuid?: string, commodityUuid?: string, minScore?: string) => {
  const params: any = {};
  if (refineryUuid) params.refinery_uuid = refineryUuid;
  if (commodityUuid) params.commodity_uuid = commodityUuid;
  if (minScore) params.min_score = minScore;
  const response = await api.get("/api/v1/intelligence/procurement/compatibility", { params });
  return response.data;
};

export const fetchRefineryRecommendations = async (refineryUuid: string) => {
  const response = await api.get(`/api/v1/intelligence/procurement/compatibility/refinery/${refineryUuid}`);
  return response.data;
};

export const computeRouteCosts = async () => {
  const response = await api.post("/api/v1/intelligence/procurement/routes/compute");
  return response.data;
};

export const fetchRouteCosts = async (originNodeId?: number, destNodeId?: number) => {
  const params: any = {};
  if (originNodeId) params.origin_node_id = originNodeId;
  if (destNodeId) params.destination_node_id = destNodeId;
  const response = await api.get("/api/v1/intelligence/procurement/routes", { params });
  return response.data;
};

export const runOptimization = async (body: {
  supply_gap_bpd?: number;
  commodity_uuid?: string;
  destination_region?: string;
  max_cost_bbl?: number;
  max_risk_score?: number;
  max_lead_days?: number;
  optimization_goal?: string;
  top_n?: number;
}) => {
  const response = await api.post("/api/v1/intelligence/procurement/optimize", body);
  return response.data;
};

export const runProcurementOrchestrator = async (body: {
  simulation_run_uuid?: string;
  name?: string;
  description?: string;
  supply_gap_bpd?: number;
  commodity_uuid?: string;
  destination_region?: string;
  optimization_goal?: string;
  max_cost_bbl?: number;
  max_risk_score?: number;
  max_lead_days?: number;
}) => {
  const response = await api.post("/api/v1/intelligence/procurement/run", body);
  return response.data;
};

export const fetchProcurementRuns = async (status?: string, limit?: number) => {
  const params: any = {};
  if (status) params.status = status;
  if (limit) params.limit = limit;
  const response = await api.get("/api/v1/intelligence/procurement/runs", { params });
  return response.data;
};

export const fetchProcurementRun = async (uuid: string) => {
  const response = await api.get(`/api/v1/intelligence/procurement/runs/${uuid}`);
  return response.data;
};

export const fetchExecutiveSummary = async (runUuid: string) => {
  const response = await api.get(`/api/v1/intelligence/procurement/runs/${runUuid}/executive-summary`);
  return response.data;
};

export const acknowledgeExecutiveCard = async (cardUuid: string, acknowledgedBy?: string) => {
  const response = await api.post(`/api/v1/intelligence/procurement/executive-cards/${cardUuid}/ack`, {
    acknowledged_by: acknowledgedBy || "user",
  });
  return response.data;
};

export const fetchProcurementRecommendations = async (runUuid?: string, priority?: string) => {
  const params: any = {};
  if (runUuid) params.run_uuid = runUuid;
  if (priority) params.priority = priority;
  const response = await api.get("/api/v1/intelligence/procurement/recommendations", { params });
  return response.data;
};

export const fetchExecutiveCards = async (severity?: string, category?: string) => {
  const params: any = {};
  if (severity) params.severity = severity;
  if (category) params.category = category;
  const response = await api.get("/api/v1/intelligence/procurement/executive-cards", { params });
  return response.data;
};

export const fetchProcurementHealth = async () => {
  const response = await api.get("/api/v1/intelligence/procurement/health");
  return response.data;
};

// ── SPR Decision Intelligence API ───────────────────────────────────────

export const initSPR = async () => {
  const response = await api.post("/api/v1/intelligence/procurement/spr/init");
  return response.data;
};

export const fetchSPRFacilities = async () => {
  const response = await api.get("/api/v1/intelligence/procurement/spr/facilities");
  return response.data;
};

export const fetchSPRInventory = async (facilityUuid?: string, limit?: number) => {
  const params: any = {};
  if (facilityUuid) params.facility_uuid = facilityUuid;
  if (limit) params.limit = limit;
  const response = await api.get("/api/v1/intelligence/procurement/spr/inventory", { params });
  return response.data;
};

export const fetchSPRPolicies = async () => {
  const response = await api.get("/api/v1/intelligence/procurement/spr/policies");
  return response.data;
};

export const createSPRPolicy = async (body: any) => {
  const response = await api.post("/api/v1/intelligence/procurement/spr/policies", body);
  return response.data;
};

export const computeSPRDemand = async () => {
  const response = await api.get("/api/v1/intelligence/procurement/spr/demand");
  return response.data;
};

export const runSPRAnalysis = async (body: {
  name?: string;
  description?: string;
  scenario_uuid?: string;
  simulation_run_uuid?: string;
  procurement_run_uuid?: string;
  disruption_reason?: string;
  disruption_days?: number;
  supply_gap_bpd?: number;
  strategy?: string;
  policy_name?: string;
}) => {
  const response = await api.post("/api/v1/intelligence/procurement/spr/analyze", body);
  return response.data;
};

export const fetchSPRRuns = async (limit?: number) => {
  const params: any = {};
  if (limit) params.limit = limit;
  const response = await api.get("/api/v1/intelligence/procurement/spr/runs", { params });
  return response.data;
};

export const fetchSPRRun = async (uuid: string) => {
  const response = await api.get(`/api/v1/intelligence/procurement/spr/runs/${uuid}`);
  return response.data;
};

export const acknowledgeSPRCard = async (cardUuid: string, acknowledgedBy?: string) => {
  const response = await api.post(`/api/v1/intelligence/procurement/spr/executive-cards/${cardUuid}/ack`, {
    acknowledged_by: acknowledgedBy || "user",
  });
  return response.data;
};

export const fetchSPRHealth = async () => {
  const response = await api.get("/api/v1/intelligence/procurement/spr/health");
  return response.data;
};