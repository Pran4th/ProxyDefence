import { useEffect, useState } from "react";
import {
  AlertTriangle,
  BarChart3,
  Clock,
  Shield,
  FileText,
  CalendarDays,
  type LucideIcon,
} from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, XAxis, YAxis } from "recharts";

import AppShell from "@/components/AppShell";
import ThreatMap from "@/components/ThreatMap";
import { cn } from "@/lib/utils";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  fetchDashboardStats,
  fetchTopEvents,
  fetchNetworkGraph,
  fetchThreatAnalytics,
  type Article,
  type AttackGraphData,
  type DashboardV2,
} from "@/lib/api";

type Severity = "low" | "medium" | "high" | "critical";

const severityFromArticle = (article: Article): Severity => {
  if (article.risk_level === "critical") return "critical";
  if (article.risk_level === "high") return "high";
  if (article.sentiment === "positive") return "low";
  return "medium";
};

// Signature dossier motif: a 4px left-edge tab that encodes severity/status
// using only the semantic status tokens (never invented colors).
const riskTabClass = (level?: string | null) => {
  switch (level) {
    case "critical":
      return "bg-destructive";
    case "high":
      return "bg-destructive/60";
    case "medium":
      return "bg-warning";
    case "low":
      return "bg-success";
    default:
      return "bg-muted-foreground/40";
  }
};

const severityTabClass: Record<Severity, string> = {
  critical: "bg-destructive",
  high: "bg-destructive/60",
  medium: "bg-warning",
  low: "bg-success",
};

type RiskDistributionPoint = {
  risk_level: string;
  label: string;
  count: number;
  fill: string;
};

type TopicDistributionPoint = {
  topic: string;
  count: number;
};

const riskChartConfig = {
  count: { label: "Events", color: "hsl(var(--primary))" },
};

const topicChartConfig = {
  count: { label: "Articles", color: "hsl(var(--primary))" },
};

const riskLevels = [
  { risk_level: "critical", label: "Critical", fill: "hsl(var(--destructive))" },
  { risk_level: "high", label: "High", fill: "hsl(var(--destructive) / 0.6)" },
  { risk_level: "medium", label: "Medium", fill: "hsl(var(--warning))" },
  { risk_level: "low", label: "Low", fill: "hsl(var(--success))" },
];

type MetricVariant = "default" | "threat" | "safe" | "warning";

const metricTabClass: Record<MetricVariant, string> = {
  default: "bg-muted-foreground/40",
  threat: "bg-destructive",
  safe: "bg-success",
  warning: "bg-warning",
};

const metricIconClass: Record<MetricVariant, string> = {
  default: "text-muted-foreground",
  threat: "text-destructive",
  safe: "text-success",
  warning: "text-warning",
};

const metricTrendClass: Record<"up" | "down" | "neutral", string> = {
  up: "text-success",
  down: "text-destructive",
  neutral: "text-muted-foreground",
};

// Flat dossier-style metric tile: hairline border, no glow/shadow, a
// status-tab on the left edge, and tabular-nums monospace value.
const MetricTile = ({
  title,
  value,
  icon: Icon,
  trend = "neutral",
  trendValue,
  variant = "default",
}: {
  title: string;
  value: string | number;
  icon: LucideIcon;
  trend?: "up" | "down" | "neutral";
  trendValue?: string;
  variant?: MetricVariant;
}) => (
  <div className="relative overflow-hidden rounded-md border border-border bg-card py-5 pl-5 pr-4">
    <span className={cn("absolute inset-y-0 left-0 w-1", metricTabClass[variant])} aria-hidden="true" />
    <div className="flex items-start justify-between gap-3">
      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">{title}</p>
        <p className="mt-2 font-mono text-3xl font-semibold tabular-nums">{value}</p>
        {trendValue && (
          <p className={cn("mt-1 text-xs", metricTrendClass[trend])}>{trendValue}</p>
        )}
      </div>
      <Icon className={cn("h-5 w-5 shrink-0", metricIconClass[variant])} />
    </div>
  </div>
);

// Flat dossier card for a single monitored signal/article, severity encoded
// via the same left-edge tab motif as everywhere else severity appears.
const SignalCard = ({
  title,
  description,
  timestamp,
  severity,
  source,
}: {
  title: string;
  description: string;
  timestamp: string;
  severity: Severity;
  source: string;
}) => (
  <div className="relative overflow-hidden rounded-md border border-border bg-card p-4 pl-5">
    <span className={cn("absolute inset-y-0 left-0 w-1", severityTabClass[severity])} aria-hidden="true" />
    <div className="flex items-center justify-between gap-3">
      <p className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
        {severity} risk &middot; {source}
      </p>
      <span className="flex shrink-0 items-center gap-1 font-mono text-[11px] tabular-nums text-muted-foreground">
        <Clock className="h-3 w-3" />
        {timestamp}
      </span>
    </div>
    <h3 className="mt-2 text-base font-semibold leading-snug">{title}</h3>
    <p className="mt-1 text-sm text-muted-foreground line-clamp-2">{description}</p>
  </div>
);

const RiskDistributionChart = ({ data }: { data: RiskDistributionPoint[] }) => (
  <Card className="mt-6 rounded-md shadow-none">
    <CardHeader>
      <CardDescription className="text-xs uppercase tracking-[0.2em]">
        Severity ladder &middot; live tally
      </CardDescription>
      <CardTitle>Risk distribution across tracked events</CardTitle>
    </CardHeader>
    <CardContent>
      <ChartContainer config={riskChartConfig} className="h-[280px] w-full font-mono tabular-nums">
        <BarChart data={data}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis dataKey="label" tickLine={false} axisLine={false} />
          <YAxis tickLine={false} axisLine={false} width={36} allowDecimals={false} />
          <ChartTooltip content={<ChartTooltipContent />} />
          <Bar dataKey="count" radius={[3, 3, 0, 0]}>
            {data.map((item) => (
              <Cell key={item.risk_level} fill={item.fill} />
            ))}
          </Bar>
        </BarChart>
      </ChartContainer>
    </CardContent>
  </Card>
);

const TopicDistributionChart = ({ data }: { data: TopicDistributionPoint[] }) => (
  <Card className="mt-6 rounded-md shadow-none">
    <CardHeader>
      <CardDescription className="text-xs uppercase tracking-[0.2em]">
        Subject-matter concentration &middot; top 8
      </CardDescription>
      <CardTitle>Topic exposure across monitored events</CardTitle>
    </CardHeader>
    <CardContent>
      <ChartContainer config={topicChartConfig} className="h-[320px] w-full font-mono tabular-nums">
        <BarChart data={data}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis dataKey="topic" tickLine={false} axisLine={false} />
          <YAxis tickLine={false} axisLine={false} width={36} allowDecimals={false} />
          <ChartTooltip content={<ChartTooltipContent />} />
          <Bar dataKey="count" fill="var(--color-count)" radius={[3, 3, 0, 0]} />
        </BarChart>
      </ChartContainer>
    </CardContent>
  </Card>
);

const Dashboard = () => {
  const [stats, setStats] = useState<DashboardV2 | null>(null);
  const [topEvent, setTopEvent] = useState<any>(null);
  const [articles, setArticles] = useState<Article[]>([]);
  const [graph, setGraph] = useState<AttackGraphData>({ nodes: [], links: [] });
  const [riskDistribution, setRiskDistribution] = useState<RiskDistributionPoint[]>(
    riskLevels.map((level) => ({ ...level, count: 0 }))
  );
  const [topicDistribution, setTopicDistribution] = useState<TopicDistributionPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetchDashboardStats(),
      fetchThreatAnalytics(),
      fetchTopEvents(),
      fetchNetworkGraph(),
    ])
      .then(([statsData, threatData, eventData, networkData]) => {
        const highRiskEvents = threatData.risk_distribution
          .filter((item) => ["high", "critical"].includes(item.risk_level))
          .reduce((total, item) => total + item.count, 0);
        const avgThreatScore = eventData.length
          ? eventData.reduce((total, event) => total + (event.risk_score ?? 0), 0) / eventData.length
          : 0;
        const avgConfidence = eventData.length
          ? eventData.reduce((total, event) => total + (event.confidence ?? 0), 0) / eventData.length
          : 0;

        setStats(statsData);
        setTopEvent(statsData.top_event);
        setRiskDistribution(
          riskLevels.map((level) => ({
            ...level,
            count:
              threatData.risk_distribution.find(
                (item) => item.risk_level?.toLowerCase() === level.risk_level
              )?.count ?? 0,
          }))
        );
        setTopicDistribution(
          [...threatData.topic_distribution]
            .sort((a, b) => b.count - a.count)
            .slice(0, 8)
        );
        setArticles(
          eventData.slice(0, 5).map((event) => {
            const timestamp = event.last_seen ?? event.updated_at ?? new Date().toISOString();

            return {
              id: event.id,
              article_id: event.id,
              title: event.title,
              content: event.summary,
              source: "Event",
              published_at: timestamp,
              summary: event.summary,
              topic: event.topic,
              threat_score: event.risk_score,
              risk_level: event.risk_level as Article["risk_level"],
              confidence: event.confidence,
            };
          })
        );
        setGraph({
          nodes: networkData.nodes,
          links: networkData.edges.map((edge) => ({
            ...edge,
            value: edge.value ?? edge.confidence ?? 0,
          })),
        });
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <AppShell title="Operations dashboard" subtitle="Monitor intelligence events, alerts, investigations, watchlists and operational threat activity.">
      <div className="grid gap-5 lg:grid-cols-4">
        <MetricTile
          title="Tracked events"
          value={loading ? "..." : stats?.events ?? 0}
          icon={CalendarDays}
          trend="up"
          trendValue="Tracked intelligence events"
        />

        <MetricTile
          title="Open alerts"
          value={loading ? "..." : stats?.open_alerts ?? 0}
          icon={AlertTriangle}
          trend="up"
          trendValue="Active analyst alerts"
          variant="threat"
        />

        <MetricTile
          title="Active cases"
          value={loading ? "..." : stats?.cases ?? 0}
          icon={Shield}
          trend="neutral"
          trendValue="Active investigations"
        />

        <MetricTile
          title="Reports filed"
          value={loading ? "..." : stats?.reports ?? 0}
          icon={FileText}
          trend="up"
          trendValue="Generated intelligence briefs"
          variant="safe"
        />
      </div>
      <div className="mt-5 grid gap-5 lg:grid-cols-4">
        <MetricTile
          title="Avg risk score"
          value={stats?.average_risk_score?.toFixed(2) ?? "0"}
          icon={BarChart3}
          trend="neutral"
          trendValue="Average event risk"
        />

        <MetricTile
          title="High-risk events"
          value={stats?.high_risk_events ?? 0}
          icon={AlertTriangle}
          trend="up"
          trendValue="High severity events"
          variant="warning"
        />

        <MetricTile
          title="Critical events"
          value={stats?.critical_events ?? 0}
          icon={AlertTriangle}
          trend="up"
          trendValue="Critical severity events"
          variant="threat"
        />

        <MetricTile
          title="Watchlists"
          value={stats?.watchlists ?? 0}
          icon={Shield}
          trend="neutral"
          trendValue="Active monitoring lists"
        />
      </div>

      <RiskDistributionChart data={riskDistribution} />
      <TopicDistributionChart data={topicDistribution} />

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <ThreatMap graph={graph} />

        <div className="space-y-5">
          <div className="relative overflow-hidden rounded-md border border-border bg-card p-6">
            {topEvent && (
              <span
                className={cn("absolute inset-y-0 left-0 w-1", riskTabClass(topEvent.risk_level))}
                aria-hidden="true"
              />
            )}

            <div className="mb-4 flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-muted-foreground">
              <AlertTriangle className="h-4 w-4 text-destructive" />
              Highest-priority open signal
            </div>

            {topEvent ? (
              <div className="space-y-4">
                <h3 className="text-lg font-semibold">{topEvent.title}</h3>

                <div className="flex flex-wrap gap-2">
                  <span className="rounded border border-border px-2.5 py-1 font-mono text-xs tabular-nums text-muted-foreground">
                    Risk score {topEvent.risk_score}
                  </span>

                  <span className="rounded border border-border px-2.5 py-1 text-xs uppercase tracking-wide text-muted-foreground">
                    {topEvent.risk_level}
                  </span>
                </div>

                <p className="font-mono text-xs tabular-nums text-muted-foreground">
                  Last seen {new Date(topEvent.last_seen).toLocaleString()}
                </p>
              </div>
            ) : (
              <p className="text-muted-foreground">No threat event available.</p>
            )}
          </div>

          <div className="rounded-md border border-border bg-card p-6">
            <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
              Latest finished intelligence briefs
            </p>

            <div className="mt-4 space-y-2">
              {stats?.recent_reports?.length ? (
                stats.recent_reports.map((report) => (
                  <div
                    key={report.id}
                    className="flex items-center justify-between gap-3 rounded border border-border px-3 py-2"
                  >
                    <span className="text-sm font-medium">{report.title}</span>

                    <span className="shrink-0 font-mono text-xs tabular-nums text-muted-foreground">
                      {new Date(report.created_at).toLocaleString()}
                    </span>
                  </div>
                ))
              ) : (
                <div className="text-sm text-muted-foreground">
                  No reports generated yet.
                </div>
              )}
            </div>
          </div>

          <div className="rounded-md border border-border bg-card p-6">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                  Live-scored incoming signals
                </p>

                <h2 className="mt-1 text-2xl font-semibold">
                  Intelligence monitoring feed
                </h2>
              </div>
            </div>
            <div className="grid gap-4">
              {articles.map((article) => (
                <SignalCard
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
        </div>
      </div>
    </AppShell>
  );
};

export default Dashboard;
