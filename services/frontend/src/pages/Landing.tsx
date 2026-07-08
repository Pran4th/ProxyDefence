import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Activity, ArrowRight, Globe, Radar, Shield, Sparkles } from "lucide-react";

import MetricCard from "@/components/MetricCard";
import Navbar from "@/components/Navbar";
import NewsCard from "@/components/NewsCard";
import { Button } from "@/components/ui/button";
import { fetchAnalyticsSummary, fetchArticles, type AnalyticsSummary, type Article } from "@/lib/api";
import heroBg from "@/assets/hero-bg.png";

const getSeverity = (article: Article): "low" | "medium" | "high" | "critical" => {
  if (article.risk_level === "critical") return "critical";
  if (article.risk_level === "high") return "high";
  if (article.sentiment === "negative") return "high";
  if (article.sentiment === "positive") return "low";
  return "medium";
};

const Landing = () => {
  const [articles, setArticles] = useState<Article[]>([]);
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([fetchArticles({ limit: 3 }), fetchAnalyticsSummary()])
      .then(([articleData, summaryData]) => {
        setArticles(articleData);
        setSummary(summaryData);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      <section className="relative overflow-hidden pb-16 pt-32">
        <div
          className="absolute inset-0 opacity-20"
          style={{ backgroundImage: `url(${heroBg})`, backgroundPosition: "center", backgroundSize: "cover" }}
        />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(37,99,235,0.24),transparent_30%),radial-gradient(circle_at_bottom_right,rgba(239,68,68,0.18),transparent_28%)]" />
        <div className="relative mx-auto grid max-w-7xl gap-10 px-4 sm:px-6 lg:grid-cols-[1.1fr_0.9fr]">
          <div>
            <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-4 py-2 text-xs uppercase tracking-[0.3em] text-primary">
              <Sparkles className="h-4 w-4" />
              AI Geopolitical Threat Intelligence
            </p>
            <h1 className="max-w-4xl text-5xl font-bold leading-tight md:text-6xl">
              From raw headlines to a live
              <span className="bg-gradient-primary bg-clip-text text-transparent"> geopolitical risk picture</span>
            </h1>
            <p className="mt-5 max-w-2xl text-lg text-muted-foreground">
              ProxyDefence fuses streaming news ingestion, ML enrichment, entity extraction, threat scoring, and graph analytics into a single operator workflow.
            </p>
            <div className="mt-8 flex flex-wrap gap-4">
              <Link to="/auth">
                <Button variant="hero" size="lg">
                  Launch analyst workspace
                </Button>
              </Link>
              <Link to="/news">
                <Button variant="outline" size="lg">
                  Explore live feed
                </Button>
              </Link>
            </div>
          </div>

          <div className="rounded-[2rem] border border-border bg-card/60 p-6 shadow-elevation backdrop-blur">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.28em] text-muted-foreground">Operational snapshot</p>
                <h2 className="text-2xl font-semibold">Live threat posture</h2>
              </div>
              <Radar className="h-8 w-8 text-primary" />
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <MetricCard
                title="Active articles"
                value={loading ? "..." : summary?.total_articles ?? 0}
                icon={Activity}
                trend="up"
                trendValue="Current indexed intelligence"
              />
              <MetricCard
                title="High risk"
                value={loading ? "..." : summary?.high_risk_articles ?? 0}
                icon={Shield}
                trend="down"
                trendValue="Articles with elevated threat score"
                variant="threat"
              />
              <MetricCard
                title="Avg threat score"
                value={loading ? "..." : `${Math.round(summary?.avg_threat_score ?? 0)}`}
                icon={Globe}
                trend="neutral"
                trendValue="Composite geopolitical risk"
                variant="warning"
              />
              <MetricCard
                title="ML confidence"
                value={loading ? "..." : `${Math.round((summary?.avg_confidence ?? 0) * 100)}%`}
                icon={Sparkles}
                trend="up"
                trendValue="Model certainty across articles"
                variant="safe"
              />
            </div>
          </div>
        </div>
      </section>

      <section className="pb-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6">
          <div className="mb-6 flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.28em] text-muted-foreground">Latest intelligence</p>
              <h2 className="text-3xl font-semibold">Recent high-signal articles</h2>
            </div>
            <Link to="/news" className="inline-flex items-center gap-2 text-sm text-primary">
              View full feed
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>

          <div className="grid gap-5 lg:grid-cols-3">
            {articles.map((article) => (
              <NewsCard
                key={article.id}
                title={article.title}
                description={article.summary || article.content}
                timestamp={new Date(article.published_at).toLocaleString()}
                severity={getSeverity(article)}
                source={`${article.source} · ${article.topic || "general"}`}
              />
            ))}
          </div>
        </div>
      </section>
    </div>
  );
};

export default Landing;
