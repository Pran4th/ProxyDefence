// src/lib/api.ts
import axios from 'axios';

// Use environment variable or default to localhost
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8004'; 

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface Article {
  id: number;
  title: string;
  content: string;
  source: string;
  published_at: string;
  sentiment?: 'positive' | 'negative' | 'neutral';
  confidence?: number;
}

export interface AnalyticsSummary {
  total_articles: number;
  articles_last_24h: number;
  avg_confidence: number;
  sentiment_distribution: Record<string, number>;
}

export interface GraphNode {
  id: string;
  group: string;
  val: number;
}

export interface GraphLink {
  source: string;
  target: string;
  value: number;
}

export interface AttackGraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

// API Endpoints
export const fetchArticles = async (limit = 20, offset = 0) => {
  const response = await api.get<Article[]>('/articles', { params: { limit, offset } });
  return response.data;
};

export const fetchAnalyticsSummary = async () => {
  const response = await api.get<AnalyticsSummary>('/analytics/summary');
  return response.data;
};

export const fetchAttackGraph = async () => {
  const response = await api.get<AttackGraphData>('/analytics/graph');
  return response.data;
};