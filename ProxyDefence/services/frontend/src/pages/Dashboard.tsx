import { useEffect, useState } from "react";
import { AlertTriangle, BarChart3, Globe2, Shield, Sparkles } from "lucide-react";

import AppShell from "@/components/AppShell";
import MetricCard from "@/components/MetricCard";
import NewsCard from "@/components/NewsCard";
import ThreatMap from "@/components/ThreatMap";
import {
  fetchAnalyticsSummary,
  fetchArticles,
  fetchAttackGraph,
  fetchEntityInsights,
  type AnalyticsSummary,
  type Article,
  type AttackGraphData,
  type EntityInsight,
} from "@/lib/api";

const severityFromArticle = (article: Article): "low" | "medium" | "high" | "critical" => {
  if (article.risk_level === "critical") return "critical";
  if (article.risk_level === "high") return "high";
  if (article.sentiment === "positive") return "low";
  return "medium";
};

const Dashboard = () => {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [articles, setArticles] = useState<Article[]>([]);
  const [graph, setGraph] = useState<AttackGraphData>({ nodes: [], links: [] });
  const [entities, setEntities] = useState<EntityInsight[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetchAnalyticsSummary(),
      fetchArticles({ limit: 5 }),
      fetchAttackGraph(),
      fetchEntityInsights(),
    ])
      .then(([summaryData, articleData, graphData, entityData]) => {
        setSummary(summaryData);
        setArticles(articleData);
        setGraph(graphData);
        setEntities(entityData.slice(0, 6));
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <AppShell
      title="Operations dashboard"
      subtitle="Track topic shifts, high-risk actors, ML confidence, and the latest geopolitical risk narratives."
    >
      <div className="grid gap-5 lg:grid-cols-4">
        <MetricCard
          title="Articles indexed"
          value={loading ? "..." : summary?.total_articles ?? 0}
          icon={Shield}
          trend="up"
          trendValue="Total processed intelligence"
        />
        <MetricCard
          title="High risk"
          value={loading ? "..." : summary?.high_risk_articles ?? 0}
          icon={AlertTriangle}
          trend="down"
          trendValue="High or critical risk level"
          variant="threat"
        />
        <MetricCard
          title="Threat score"
          value={loading ? "..." : Math.round(summary?.avg_threat_score ?? 0)}
          icon={Sparkles}
          trend="neutral"
          trendValue="Average geopolitical risk"
          variant="warning"
        />
        <MetricCard
          title="ML confidence"
          value={loading ? "..." : `${Math.round((summary?.avg_confidence ?? 0) * 100)}%`}
          icon={BarChart3}
          trend="up"
          trendValue="Blended model certainty"
          variant="safe"
        />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <ThreatMap graph={graph} />

        <div className="space-y-5">
          <div className="rounded-[1.75rem] border border-border bg-card p-6 shadow-elevation">
            <div className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
              <Globe2 className="h-4 w-4 text-primary" />
              Most mentioned actors
            </div>
            <div className="space-y-3">
              {entities.map((entity) => (
                <div key={`${entity.entity}-${entity.type}`} className="rounded-2xl border border-border bg-background/60 p-4">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <p className="font-medium">{entity.entity}</p>
                      <p className="text-sm text-muted-foreground">{entity.type} · {entity.mentions} mentions</p>
                    </div>
                    <span className="rounded-full bg-primary/10 px-3 py-1 text-xs text-primary">
                      {Math.round(entity.avg_confidence * 100)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[1.75rem] border border-border bg-card p-6 shadow-elevation">
            <p className="text-xs uppercase tracking-[0.28em] text-muted-foreground">Top themes</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {summary?.top_topics?.map((topic) => (
                <span key={topic.topic} className="rounded-full border border-border bg-background/60 px-3 py-2 text-sm">
                  {topic.topic} · {topic.count}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="mt-6 rounded-[1.75rem] border border-border bg-card p-6 shadow-elevation">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.28em] text-muted-foreground">Recent articles</p>
            <h2 className="text-2xl font-semibold">Operator briefing queue</h2>
          </div>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          {articles.map((article) => (
            <NewsCard
              key={article.id}
              title={article.title}
              description={article.summary || article.content}
              timestamp={new Date(article.published_at).toLocaleString()}
              severity={severityFromArticle(article)}
              source={`${article.source} · ${article.topic || "general"}`}
            />
          ))}
        </div>
      </div>
    </AppShell>
  );
};

export default Dashboard;
