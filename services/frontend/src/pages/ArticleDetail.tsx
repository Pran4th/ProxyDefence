import { useEffect, useState } from "react";
import { useParams, Link, useLocation } from "react-router-dom";
import { ArrowLeft, Globe2, AlertTriangle, Clock, ExternalLink, Lock } from "lucide-react";

import AppShell from "@/components/AppShell";
import EnergyContextSection from "@/components/EnergyContextSection";
import ArticleMarketImpact from "@/components/ArticleMarketImpact";
import { fetchArticle, fetchArticleEntities, fetchPublicArticle, type Article, type PublicArticleSummary } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { ThreatBadge } from "@/lib/riskFormat";

const severityColors: Record<string, string> = {
  critical: "bg-destructive/20 text-destructive border-destructive/30",
  high: "bg-accent/20 text-accent border-accent/30",
  medium: "bg-warning/20 text-warning border-warning/30",
  low: "bg-success/20 text-success border-success/30",
};

const sentimentColors: Record<string, string> = {
  negative: "text-destructive bg-destructive/10",
  positive: "text-success bg-success/10",
  neutral: "text-muted-foreground bg-muted",
};

const ArticleDetail = () => {
  const { id } = useParams<{ id: string }>();
  const { token } = useAuth();
  const location = useLocation();
  const [article, setArticle] = useState<Article | PublicArticleSummary | null>(null);
  const [entities, setEntities] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    const articleId = parseInt(id);
    if (isNaN(articleId)) { setError("Invalid article ID"); setLoading(false); return; }

    setLoading(true);
    setError(null);
    setEntities([]);

    const load = token
      ? Promise.all([fetchArticle(articleId), fetchArticleEntities(articleId)]).then(
          ([articleData, entityData]) => {
            setArticle(articleData);
            setEntities(entityData);
          },
        )
      : fetchPublicArticle(articleId).then((articleData) => setArticle(articleData));

    load
      .catch(() => setError("Failed to load article"))
      .finally(() => setLoading(false));
  }, [id, token]);

  // Only the authenticated shape carries these — narrows `article` for the
  // full-detail sections below.
  const fullArticle = token && article && "content" in article ? (article as Article) : null;

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
            {article.threat_score !== undefined && <ThreatBadge score={article.threat_score} />}
            {fullArticle?.confidence !== undefined && (
              <span className="text-muted-foreground">
                Confidence: <span className="font-semibold text-foreground">{Math.round(fullArticle.confidence * 100)}%</span>
              </span>
            )}
            {fullArticle?.url && (
              <a href={fullArticle.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-primary hover:underline">
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

          {fullArticle?.content && (
            <div className="prose prose-sm prose-invert max-w-none leading-7 text-muted-foreground">
              {fullArticle.content}
            </div>
          )}

          {!token && (
            <div className="mt-4 flex items-start gap-3 rounded-2xl border border-primary/30 bg-primary/5 p-4">
              <Lock className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
              <div className="text-sm text-muted-foreground">
                <p className="font-medium text-foreground">Sign in to read the full report</p>
                <p className="mt-1">
                  The complete article text, extracted entities, and energy infrastructure linkage are available to
                  signed-in analysts.
                </p>
                <Link
                  to="/auth"
                  state={{ from: location.pathname }}
                  className="mt-2 inline-flex text-primary hover:underline"
                >
                  Sign in
                </Link>
              </div>
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
                  to={`/graph?entity=${encodeURIComponent(entity.entity_text)}`}
                  className="rounded-full border border-border bg-background px-3 py-1.5 text-sm transition-colors hover:border-primary hover:text-primary"
                >
                  {entity.entity_text}
                  <span className="ml-1.5 text-xs text-muted-foreground">({entity.entity_type})</span>
                </Link>
              ))}
            </div>
          </div>
        )}

        {fullArticle?.energy_context && (
          <div className="rounded-3xl border border-border bg-card p-6">
            <EnergyContextSection energyContext={fullArticle.energy_context} />
          </div>
        )}

        {fullArticle && <ArticleMarketImpact articleId={fullArticle.id} />}
      </div>
    </AppShell>
  );
};

export default ArticleDetail;
