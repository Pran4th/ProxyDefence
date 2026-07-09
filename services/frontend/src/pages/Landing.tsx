import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  ArrowRight,
  Clock,
  Newspaper,
  BrainCircuit,
  Share2,
  Radar,
  Database,
  ShieldAlert,
} from "lucide-react";

import Navbar from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { fetchPublicPreview, type PublicPreview, type PublicPreviewArticle } from "@/lib/api";
import heroBg from "@/assets/hero-bg.png";

type Severity = "low" | "medium" | "high" | "critical";
type Tone = "primary" | "success" | "warning" | "destructive";

const getSeverity = (article: PublicPreviewArticle): Severity => {
  if (article.risk_level === "critical") return "critical";
  if (article.risk_level === "high") return "high";
  if (article.sentiment === "negative") return "high";
  if (article.sentiment === "positive") return "low";
  return "medium";
};

// Left-edge tab + label color, keyed to the same semantic tokens used across
// the platform: success = low, warning = medium, destructive = high/critical.
const severityTab: Record<Severity, string> = {
  low: "bg-success",
  medium: "bg-warning",
  high: "bg-destructive",
  critical: "bg-destructive",
};

const severityText: Record<Severity, string> = {
  low: "text-success",
  medium: "text-warning",
  high: "text-destructive",
  critical: "text-destructive",
};

const toneColor: Record<Tone, string> = {
  primary: "hsl(var(--primary))",
  success: "hsl(var(--success))",
  warning: "hsl(var(--warning))",
  destructive: "hsl(var(--destructive))",
};

interface SignalMetric {
  label: string;
  value: string;
  level: number; // 0-100, drives the waveform height
  tone: Tone;
}

const STRIP_W = 400;
const STRIP_H = 64;
const STRIP_PAD = 8;

// Builds a jittered polyline between the real anchor points so the strip
// reads as a live waveform rather than four straight-line segments. The
// jitter is deterministic (sine-based) so the render is stable across
// re-renders, not randomized.
const buildWavePoints = (levels: number[]) => {
  const n = levels.length;
  const usableW = STRIP_W - STRIP_PAD * 2;
  const usableH = STRIP_H - STRIP_PAD * 2;
  const segW = usableW / (n - 1);
  const yFor = (level: number) => STRIP_PAD + usableH - (Math.min(100, Math.max(0, level)) / 100) * usableH;

  const points: [number, number][] = [];
  const steps = 10;
  for (let i = 0; i < n - 1; i++) {
    const y1 = yFor(levels[i]);
    const y2 = yFor(levels[i + 1]);
    for (let s = 0; s <= steps; s++) {
      if (i > 0 && s === 0) continue; // avoid duplicating shared anchor
      const t = s / steps;
      const x = STRIP_PAD + i * segW + t * segW;
      const jitter = s === 0 || s === steps ? 0 : Math.sin((i * steps + s) * 1.7) * usableH * 0.05;
      points.push([x, y1 + (y2 - y1) * t + jitter]);
    }
  }

  const anchors = levels.map((level, i) => [STRIP_PAD + i * segW, yFor(level)] as [number, number]);
  return { points, anchors };
};

const SignalStrip = ({ metrics }: { metrics: SignalMetric[] }) => {
  const { points, anchors } = buildWavePoints(metrics.map((m) => m.level));

  return (
    <div>
      <svg
        viewBox={`0 0 ${STRIP_W} ${STRIP_H}`}
        preserveAspectRatio="none"
        className="h-16 w-full"
        aria-hidden="true"
      >
        <polyline
          points={points.map(([x, y]) => `${x},${y}`).join(" ")}
          fill="none"
          stroke="hsl(var(--primary))"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity={0.85}
        />
        {anchors.map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r={4.5} fill={toneColor[metrics[i].tone]} stroke="hsl(var(--card))" strokeWidth={2} />
        ))}
      </svg>
      <div className="mt-2 grid grid-cols-4 gap-2 text-center">
        {metrics.map((metric) => (
          <div key={metric.label}>
            <p className="font-mono text-base font-semibold tabular-nums leading-none">{metric.value}</p>
            <p className="mt-1 text-[10px] uppercase tracking-wider text-muted-foreground">{metric.label}</p>
          </div>
        ))}
      </div>
    </div>
  );
};

interface Capability {
  icon: typeof Newspaper;
  title: string;
  description: string;
}

const CAPABILITIES: Capability[] = [
  {
    icon: Newspaper,
    title: "Live news fusion",
    description: "Continuous ingestion from GNews and NewsData.io streamed straight into the analysis pipeline.",
  },
  {
    icon: BrainCircuit,
    title: "Trained ML scoring",
    description: "XGBoost topic and disruption-risk classifiers trained on real GDELT and sanctions data score every article.",
  },
  {
    icon: Share2,
    title: "Entity & relationship graphing",
    description: "Named-entity extraction links actors, organizations, and locations into an explorable intelligence graph.",
  },
  {
    icon: Radar,
    title: "Digital twin simulations",
    description: "Stress-test supply-chain scenarios — chokepoint closures, refinery outages — against a live network model.",
  },
  {
    icon: Database,
    title: "Multi-source data fusion",
    description: "GDELT, EIA, AIS vessel tracking, OFAC/EU/UN sanctions lists, and commodity prices, unified in one platform.",
  },
  {
    icon: ShieldAlert,
    title: "Risk intelligence",
    description: "Chokepoint and infrastructure risk scores blend rule-based signals with calibrated model output.",
  },
];

const Landing = () => {
  const [preview, setPreview] = useState<PublicPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const location = useLocation();

  useEffect(() => {
    fetchPublicPreview()
      .then(setPreview)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (location.hash) {
      const el = document.querySelector(location.hash);
      el?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [location.hash, loading]);

  const stats = preview?.stats;
  const totalArticles = stats?.total_articles ?? 0;
  const highRisk = stats?.high_risk_articles ?? 0;
  const avgThreat = stats?.avg_threat_score ?? 0;
  const avgConfidencePct = (stats?.avg_confidence ?? 0) * 100;
  const highRiskRatio = totalArticles > 0 ? (highRisk / totalArticles) * 100 : 0;

  const metrics: SignalMetric[] = [
    {
      label: "Active articles",
      value: loading ? "—" : `${totalArticles}`,
      // Heuristic volume scale: a few hundred indexed articles reads as "full signal".
      level: Math.min(100, (totalArticles / 300) * 100),
      tone: "primary",
    },
    {
      label: "High risk",
      value: loading ? "—" : `${highRisk}`,
      level: highRiskRatio,
      tone: highRiskRatio >= 30 ? "destructive" : highRiskRatio >= 10 ? "warning" : "success",
    },
    {
      label: "Avg threat score",
      value: loading ? "—" : `${Math.round(avgThreat)}`,
      level: avgThreat,
      tone: avgThreat >= 70 ? "destructive" : avgThreat >= 40 ? "warning" : "success",
    },
    {
      label: "ML confidence",
      value: loading ? "—" : `${Math.round(avgConfidencePct)}%`,
      level: avgConfidencePct,
      tone: avgConfidencePct >= 70 ? "success" : avgConfidencePct >= 40 ? "warning" : "destructive",
    },
  ];

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
            <p className="mb-4 flex items-center gap-2 font-mono text-xs uppercase tracking-[0.35em] text-primary">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-primary" />
              Signal
            </p>
            <h1 className="max-w-4xl font-display text-5xl font-bold leading-tight md:text-6xl">
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

          <div className="rounded-lg border border-border bg-card/60 p-6 backdrop-blur">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.28em] text-muted-foreground">Operational snapshot</p>
                <h2 className="font-display text-2xl font-semibold">Live threat posture</h2>
              </div>
              <span className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-success">
                <span className="h-2 w-2 rounded-full bg-success animate-pulse-slow" />
                Live
              </span>
            </div>
            <SignalStrip metrics={metrics} />
            {!loading && stats && (
              <p className="mt-4 border-t border-border pt-4 text-xs text-muted-foreground">
                Backed by <span className="font-semibold text-foreground">{stats.trained_models}</span> trained ML models across{" "}
                <span className="font-semibold text-foreground">{stats.datasets}</span> live data sources.
              </p>
            )}
          </div>
        </div>
      </section>

      <section id="capabilities" className="scroll-mt-20 pb-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6">
          <div className="mb-10 text-center">
            <p className="font-mono text-xs uppercase tracking-[0.35em] text-primary">Platform</p>
            <h2 className="mt-2 font-display text-3xl font-semibold">What's actually running under the hood</h2>
            <p className="mx-auto mt-3 max-w-2xl text-muted-foreground">
              No vaporware — every capability below is a real, trained model or live data pipeline you can inspect after signing in.
            </p>
          </div>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {CAPABILITIES.map((cap) => (
              <div
                key={cap.title}
                className="rounded-lg border border-border bg-card p-6 transition-colors hover:border-primary/40"
              >
                <div className="mb-4 grid h-11 w-11 place-items-center rounded-lg bg-primary/10">
                  <cap.icon className="h-5 w-5 text-primary" />
                </div>
                <h3 className="mb-2 font-display text-lg font-semibold">{cap.title}</h3>
                <p className="text-sm text-muted-foreground">{cap.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="pb-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6">
          <div className="mb-6 flex items-center justify-between">
            <div>
              <p className="font-mono text-xs uppercase tracking-[0.35em] text-primary">Situation</p>
              <h2 className="font-display text-3xl font-semibold">Recent high-signal articles</h2>
            </div>
            <Link to="/news" className="inline-flex items-center gap-2 text-sm text-primary">
              View full feed
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>

          <div className="grid gap-5 lg:grid-cols-3">
            {(preview?.articles ?? []).map((article, i) => {
              const severity = getSeverity(article);
              return (
                <div
                  key={i}
                  className="group flex overflow-hidden rounded-md border border-border bg-card"
                >
                  <span className={cn("w-1 shrink-0", severityTab[severity])} aria-hidden="true" />
                  <div className="flex-1 p-5">
                    <div className="mb-2 flex items-center gap-3">
                      <span className={cn("font-mono text-xs uppercase tracking-wider", severityText[severity])}>
                        {severity}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {article.source} &middot; {article.topic || "general"}
                      </span>
                    </div>
                    <h3 className="mb-2 font-display text-lg font-semibold leading-snug">
                      {article.title}
                    </h3>
                    <p className="mb-4 line-clamp-3 text-sm text-muted-foreground">
                      {article.summary}
                    </p>
                    <div className="flex items-center gap-2 font-mono text-xs tabular-nums text-muted-foreground">
                      <Clock className="h-3 w-3" />
                      <span>{new Date(article.published_at).toLocaleString()}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
          <div className="mt-8 text-center">
            <Link to="/auth">
              <Button variant="outline">
                Sign in for full analysis, entities, and threat breakdowns
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
};

export default Landing;
