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

export interface EntityRelationship {
  source_entity: string;
  target_entity: string;
  relationship_type: string;
  confidence: number;
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

export interface AuthUser {
  id: number;
  email: string;
  username: string;
  role: string;
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
}

export interface EventEntity {
  entity_text: string;
  entity_type: string;
  mention_count: number;
  avg_confidence: number;
}

export interface EventDetails extends Event {
  entities: EventEntity[];
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
}
export interface Alert {
  id: number;
  watchlist_id: number | null;
  entity_text: string | null;
  event_id: number | null;
  alert_type: string;
  message: string;
  risk_score: number;
  status: string;
  created_at: string;
}

export interface Watchlist {
  id: number;
  name: string;
  description: string | null;
  owner_id: number | null;
  created_at: string;
  updated_at: string;
  entities: string[];
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
export interface CopilotResponse {
  question: string;
  summary: string;
  articles: Article[];
  entities: {
    entity_text: string;
    entity_type: string;
    mentions: number;
  }[];
  relationships: {
    source_entity: string;
    target_entity: string;
    relationship_type: string;
    confidence: number;
  }[];
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

export const fetchAnalyticsSummary = async () => {
  const response = await api.get<AnalyticsSummary>("/analytics/summary");
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

export const searchArticles = async (query: string) => {
  const response = await api.get<SearchResponse>(
    "/search",
    {
      params: {
        q: query,
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
export const fetchEntities = async () => {
  const response = await api.get("/entities");
  return response.data;
};

export const fetchEntityProfile = async (entity: string) => {
  const response = await api.get(
    `/entities/${encodeURIComponent(entity)}`
  );
  return response.data;
};

export const fetchEntityArticles = async (entity: string) => {
  const response = await api.get(
    `/entities/${encodeURIComponent(entity)}/articles`
  );
  return response.data;
};

export const fetchEntityRelationships = async (
  entity: string
) => {
  const response = await api.get(
    `/entities/${encodeURIComponent(entity)}/relationships`
  );
  return response.data;
};
export const fetchEvents = async () => {
  const response = await api.get<Event[]>("/events");
  return response.data;
};

export const fetchEvent = async (eventId: number) => {
  const response = await api.get<EventDetails>(
    `/events/${eventId}`
  );
  return response.data;
};

export const fetchEventArticles = async (
  eventId: number
) => {
  const response = await api.get<Article[]>(
    `/events/${eventId}/articles`
  );
  return response.data;
};
export const fetchAlerts = async () => {
  const response = await api.get<Alert[]>(
    "/alerts"
  );

  return response.data;
};

export const fetchAlert = async (
  alertId: number
) => {
  const response = await api.get<Alert>(
    `/alerts/${alertId}`
  );

  return response.data;
};


export const generateAlerts = async () => {
  const response = await api.post(
    "/alerts/generate"
  );

  return response.data;
};
export const fetchWatchlists = async () => {
  const response = await api.get<Watchlist[]>(
    "/watchlists"
  );

  return response.data;
};

export const createWatchlist = async (
  payload: {
    name: string;
    description?: string;
    entities?: string[];
  }
) => {
  const response = await api.post(
    "/watchlists",
    payload
  );

  return response.data;
};

export const fetchWatchlist = async (
  watchlistId: number
) => {
  const response = await api.get<Watchlist>(
    `/watchlists/${watchlistId}`
  );

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
  note_text: string
) => {
  const response = await api.post(
    `/cases/${caseId}/notes`,
    {
      note_text,
    }
  );

  return response.data;
};
export const fetchReports = async () => {
  const response = await api.get<
    IntelligenceReport[]
  >("/reports");

  return response.data;
};

export const fetchReport = async (
  reportId: number
) => {
  const response = await api.get<
    IntelligenceReport
  >(`/reports/${reportId}`);

  return response.data;
};

export const generateCaseReport = async (
  caseId: number
) => {
  const response = await api.post(
    `/reports/case/${caseId}`
  );

  return response.data;
};
export const fetchDashboardV2 = async () => {
  const response =
    await api.get<DashboardV2>(
      "/analytics/dashboard-v2"
    );

  return response.data;
};
export const addWatchlistEntity = async (
  watchlistId: number,
  entityText: string
) => {
  const response = await api.post(
    `/watchlists/${watchlistId}/entities`,
    {
      entity_text: entityText,
    }
  );

  return response.data;
};
export const deleteWatchlist = async (
  watchlistId: number
) => {
  const response = await api.delete(
    `/watchlists/${watchlistId}`
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