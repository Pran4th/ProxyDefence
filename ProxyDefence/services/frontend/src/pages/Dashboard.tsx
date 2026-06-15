import { useEffect, useState } from "react";
import {
  AlertTriangle,
  BarChart3,
  Globe2,
  Shield,
  FileText,
  CalendarDays,
} from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, XAxis, YAxis } from "recharts";

import AppShell from "@/components/AppShell";
import MetricCard from "@/components/MetricCard";
import NewsCard from "@/components/NewsCard";
import ThreatMap from "@/components/ThreatMap";
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
  fetchEvents,
  fetchNetworkGraph,
  fetchThreatAnalytics,
  
  type Article,
  type AttackGraphData,
  type DashboardV2,
  type Event,
} from "@/lib/api";

const severityFromArticle = (article: Article): "low" | "medium" | "high" | "critical" => {
  if (article.risk_level === "critical") return "critical";
  if (article.risk_level === "high") return "high";
  if (article.sentiment === "positive") return "low";
  return "medium";
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
  { risk_level: "high", label: "High", fill: "hsl(var(--accent))" },
  { risk_level: "medium", label: "Medium", fill: "hsl(var(--warning))" },
  { risk_level: "low", label: "Low", fill: "hsl(var(--primary))" },
];

const RiskDistributionChart = ({ data }: { data: RiskDistributionPoint[] }) => (
  <Card className="mt-6 rounded-[1.75rem] border-border bg-card shadow-elevation">
    <CardHeader>
      <CardDescription>Threat trends</CardDescription>
      <CardTitle>Risk distribution</CardTitle>
    </CardHeader>
    <CardContent>
      <ChartContainer config={riskChartConfig} className="h-[280px] w-full">
        <BarChart data={data}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis dataKey="label" tickLine={false} axisLine={false} />
          <YAxis tickLine={false} axisLine={false} width={36} allowDecimals={false} />
          <ChartTooltip content={<ChartTooltipContent />} />
          <Bar dataKey="count" radius={[10, 10, 0, 0]}>
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
  <Card className="mt-6 rounded-[1.75rem] border-border bg-card shadow-elevation">
    <CardHeader>
      <CardDescription>Topic exposure</CardDescription>
      <CardTitle>Topic distribution</CardTitle>
    </CardHeader>
    <CardContent>
      <ChartContainer config={topicChartConfig} className="h-[320px] w-full">
        <BarChart data={data}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis dataKey="topic" tickLine={false} axisLine={false} />
          <YAxis tickLine={false} axisLine={false} width={36} allowDecimals={false} />
          <ChartTooltip content={<ChartTooltipContent />} />
          <Bar dataKey="count" fill="var(--color-count)" radius={[10, 10, 0, 0]} />
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
      fetchEvents(),
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
            const timestamp = (event as Event & { last_seen?: string; updated_at?: string }).last_seen
              ?? (event as Event & { last_seen?: string; updated_at?: string }).updated_at
              ?? new Date().toISOString();

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
  <MetricCard
    title="Events"
    value={loading ? "..." : stats?.events ?? 0}
    icon={CalendarDays}
    trend="up"
    trendValue="Tracked intelligence events"
  />

  <MetricCard
    title="Open Alerts"
    value={loading ? "..." : stats?.open_alerts ?? 0}
    icon={AlertTriangle}
    trend="up"
    trendValue="Active analyst alerts"
    variant="threat"
  />

  <MetricCard
    title="Cases"
    value={loading ? "..." : stats?.cases ?? 0}
    icon={Shield}
    trend="neutral"
    trendValue="Active investigations"
  />

  <MetricCard
    title="Reports"
    value={loading ? "..." : stats?.reports ?? 0}
    icon={FileText}
    trend="up"
    trendValue="Generated intelligence briefs"
    variant="safe"
  />
</div>
<div className="mt-5 grid gap-5 lg:grid-cols-4">

  <MetricCard
    title="Avg Risk Score"
    value={stats?.average_risk_score?.toFixed(2) ?? "0"}
    icon={BarChart3}
    trend="neutral"
    trendValue="Average event risk"
  />

  <MetricCard
    title="High Risk"
    value={stats?.high_risk_events ?? 0}
    icon={AlertTriangle}
    trend="up"
    trendValue="High severity events"
    variant="warning"
  />

  <MetricCard
    title="Critical"
    value={stats?.critical_events ?? 0}
    icon={AlertTriangle}
    trend="up"
    trendValue="Critical severity events"
    variant="threat"
  />

  <MetricCard
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
          <div className="rounded-[1.75rem] border border-border bg-card p-6 shadow-elevation">

  <div className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
    <AlertTriangle className="h-4 w-4 text-red-500" />
    Top Threat Event
  </div>
  {topEvent ? (
    <div className="space-y-4">

      <h3 className="text-lg font-semibold">
        {topEvent.title}
      </h3>

      <div className="flex flex-wrap gap-2">

        <span className="rounded-full border px-3 py-1 text-sm">
          Risk Score: {topEvent.risk_score}
        </span>

        <span className="rounded-full border px-3 py-1 text-sm">
          {topEvent.risk_level}
        </span>

      </div>

      <p className="text-sm text-muted-foreground">
        Last Seen:{" "}
        {new Date(topEvent.last_seen).toLocaleString()}
      </p>

    </div>
  ) : (
    <p className="text-muted-foreground">
      No threat event available.
    </p>
  )}

</div>
          <div className="rounded-[1.75rem] border border-border bg-card p-6 shadow-elevation">

  <p className="text-xs uppercase tracking-[0.28em] text-muted-foreground">
    Recent Reports
  </p>

  <div className="mt-4 space-y-3">

    {stats?.recent_reports?.length ? (
      stats.recent_reports.map((report) => (

        <div
          key={report.id}
          className="rounded-xl border border-border p-3"
        >
          <div className="font-medium">
            {report.title}
          </div>

          <div className="text-xs text-muted-foreground">
            {new Date(report.created_at)
              .toLocaleString()}
          </div>
        </div>

      ))
    ) : (
      <div className="text-sm text-muted-foreground">
        No reports generated yet.
      </div>
    )}

  </div>

</div>

      <div className="mt-6 rounded-[1.75rem] border border-border bg-card p-6 shadow-elevation">
        <div className="mb-5 flex items-center justify-between">
          <div>
           <p className="text-xs uppercase tracking-[0.28em] text-muted-foreground">
  Latest Threat Events
</p>

<h2 className="text-2xl font-semibold">
  Intelligence Monitoring Feed
</h2>
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
        </div> {/* closes Latest Threat Events card */}

</div> {/* closes space-y-5 */}

</div> {/* closes xl:grid-cols layout */}
    </AppShell>
  );
};

export default Dashboard;
