import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Globe2, AlertTriangle, Clock, ExternalLink } from "lucide-react";

import AppShell from "@/components/AppShell";
import EnergyContextSection from "@/components/EnergyContextSection";
import { fetchArticle, fetchArticleEntities, type Article } from "@/lib/api";

const severityColors: Record<string, string> = {
  critical: "bg-red-500/20 text-red-400 border-red-500/30",
  high: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  medium: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  low: "bg-green-500/20 text-green-400 border-green-500/30",
};

const sentimentColors: Record<string, string> = {
  negative: "text-red-400 bg-red-500/10",
  positive: "text-green-400 bg-green-500/10",
  neutral: "text-gray-400 bg-gray-500/10",
};

const ArticleDetail = () => {
  const { id } = useParams<{ id: string }>();
  const [article, setArticle] = useState<Article | null>(null);
  const [entities, setEntities] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    const articleId = parseInt(id);
    if (isNaN(articleId)) { setError("Invalid article ID"); setLoading(false); return; }

    Promise.all([
      fetchArticle(articleId),
      fetchArticleEntities(articleId),
    ])
      .then(([articleData, entityData]) => {
        setArticle(articleData);
        setEntities(entityData);
      })
      .catch(() => setError("Failed to load article"))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <AppShell title="Article" subtitle="Loading intelligence report">
        <div className="flex min-h-[400px] items-center justify-center text-muted-foreground">
          Loading article...
        </div>
      </AppShell>
    );
  }

  if (error || !article) {
    return (
      <AppShell title="Article" subtitle="Error">
        <div className="flex min-h-[400px] flex-col items-center justify-center gap-4 text-muted-foreground">
          <AlertTriangle className="h-8 w-8 text-destructive" />
          <p>{error || "Article not found"}</p>
          <Link to="/search" className="text-primary hover:underline">Back to search</Link>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell title={article.title || "Intelligence Report"} subtitle={`${article.source || "Unknown source"} · ${new Date(article.published_at).toLocaleDateString()}`}>
      <div className="space-y-6">
        <Link to="/news" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" />
          Back to intelligence feed
        </Link>

        <div className="rounded-3xl border border-border bg-card p-6">
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${severityColors[article.risk_level || "low"]}`}>
              {article.risk_level?.toUpperCase() || "UNKNOWN"}
            </span>
            {article.sentiment && (
              <span className={`rounded-full px-3 py-1 text-xs font-semibold ${sentimentColors[article.sentiment]}`}>
                {article.sentiment}
              </span>
            )}
            {article.topic && (
              <span className="rounded-full border border-border bg-background px-3 py-1 text-xs capitalize">
                {article.topic}
              </span>
            )}
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              <Clock className="h-3 w-3" />
              {new Date(article.published_at).toLocaleString()}
            </span>
          </div>

          <h1 className="mb-4 text-3xl font-bold leading-tight">{article.title}</h1>

          <div className="mb-6 flex items-center gap-4 text-sm">
            <span className="flex items-center gap-1 text-muted-foreground">
              <Globe2 className="h-4 w-4" />
              {article.source}
            </span>
            {article.threat_score !== undefined && (
              <span className="text-muted-foreground">
                Threat Score: <span className="font-semibold text-foreground">{Math.round(article.threat_score)}</span>
              </span>
            )}
            {article.confidence !== undefined && (
              <span className="text-muted-foreground">
                Confidence: <span className="font-semibold text-foreground">{Math.round(article.confidence * 100)}%</span>
              </span>
            )}
            {article.url && (
              <a href={article.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-primary hover:underline">
                <ExternalLink className="h-3 w-3" />
                Source
              </a>
            )}
          </div>

          {article.summary && (
            <div className="mb-4 rounded-2xl border border-border bg-background/60 p-4 italic text-muted-foreground">
              {article.summary}
            </div>
          )}

          {article.content && (
            <div className="prose prose-sm prose-invert max-w-none leading-7 text-muted-foreground">
              {article.content}
            </div>
          )}
        </div>

        {entities.length > 0 && (
          <div className="rounded-3xl border border-border bg-card p-6">
            <h2 className="mb-4 text-xl font-bold">Extracted Entities</h2>
            <div className="flex flex-wrap gap-2">
              {entities.map((entity: any) => (
                <Link
                  key={`${entity.entity_text}-${entity.entity_type}`}
                  to={`/entities/${encodeURIComponent(entity.entity_text)}`}
                  className="rounded-full border border-border bg-background px-3 py-1.5 text-sm transition-colors hover:border-primary hover:text-primary"
                >
                  {entity.entity_text}
                  <span className="ml-1.5 text-xs text-muted-foreground">({entity.entity_type})</span>
                </Link>
              ))}
            </div>
          </div>
        )}

        {article.energy_context && (
          <div className="rounded-3xl border border-border bg-card p-6">
            <EnergyContextSection energyContext={article.energy_context} />
          </div>
        )}
      </div>
    </AppShell>
  );
};

export default ArticleDetail;
