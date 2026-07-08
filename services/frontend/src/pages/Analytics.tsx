import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Globe2,
  Network,
  Radar,
  ShieldAlert,
  TimerReset,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  XAxis,
  YAxis,
} from "recharts";

import AppShell from "@/components/AppShell";
import MetricCard from "@/components/MetricCard";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import {
  fetchAnalyticsSummary,
  fetchEntityInsights,
  fetchNetworkGraph,
  fetchTimeSeries,
  fetchTopicBreakdown,
  type AnalyticsSummary,
  type EntityInsight,
  type NetworkGraphData,
  type TimeSeriesPoint,
  type TopicBreakdown,
} from "@/lib/api";

const chartConfig = {
  articles: { label: "Articles", color: "hsl(var(--primary))" },
  avg_threat_score: { label: "Threat score", color: "hsl(var(--accent))" },
  count: { label: "Coverage", color: "hsl(var(--primary))" },
};

const riskPalette = ["#0f766e", "#d97706", "#ea580c", "#dc2626"];

const formatBucket = (value: string) =>
  new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" });

const Analytics = () => {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [timeseries, setTimeseries] = useState<TimeSeriesPoint[]>([]);
  const [entities, setEntities] = useState<EntityInsight[]>([]);
  const [topics, setTopics] = useState<TopicBreakdown[]>([]);
  const [network, setNetwork] = useState<NetworkGraphData>({ nodes: [], edges: [] });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetchAnalyticsSummary(),
      fetchTimeSeries(),
      fetchEntityInsights(),
      fetchTopicBreakdown(),
      fetchNetworkGraph(),
    ])
      .then(([summaryData, timeseriesData, entityData, topicData, networkData]) => {
        setSummary(summaryData);
        setTimeseries(timeseriesData);
        setEntities(entityData.slice(0, 8));
        setTopics(topicData.slice(0, 6));
        setNetwork(networkData);
      })
      .finally(() => setLoading(false));
  }, []);

  const sentimentData = useMemo(() => {
    const distribution = summary?.sentiment_distribution ?? {};
    return Object.entries(distribution).map(([name, value]) => ({ name, value }));
  }, [summary]);

  return (
    <AppShell
      title="Analytics command center"
      subtitle="Explore sentiment drift, topic concentration, entity pressure, and relationship density across the intelligence stream."
    >
      <div className="grid gap-5 lg:grid-cols-4">
        <MetricCard
          title="Events in window"
          value={loading ? "..." : summary?.articles_last_24h ?? 0}
          icon={Activity}
          trend="up"
          trendValue="Articles processed in the last day"
        />
        <MetricCard
          title="Average threat"
          value={loading ? "..." : Math.round(summary?.avg_threat_score ?? 0)}
          icon={ShieldAlert}
          trend="neutral"
          trendValue="Current geopolitical risk baseline"
          variant="warning"
        />
        <MetricCard
          title="High-risk queue"
          value={loading ? "..." : summary?.high_risk_articles ?? 0}
          icon={AlertTriangle}
          trend="down"
          trendValue="Items requiring analyst attention"
          variant="threat"
        />
        <MetricCard
          title="Relationship edges"
          value={loading ? "..." : network.edges.length}
          icon={Network}
          trend="up"
          trendValue="Inferred actor-to-actor links"
          variant="safe"
        />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-[1.75rem] border border-border bg-card p-6 shadow-elevation">
          <div className="mb-5 flex items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.28em] text-muted-foreground">Signal tempo</p>
              <h2 className="mt-2 text-2xl font-semibold">Sentiment and threat over time</h2>
            </div>
            <TimerReset className="h-6 w-6 text-primary" />
          </div>
          <ChartContainer config={chartConfig} className="h-[320px] w-full">
            <AreaChart data={timeseries}>
              <defs>
                <linearGradient id="articlesFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--color-articles)" stopOpacity={0.45} />
                  <stop offset="95%" stopColor="var(--color-articles)" stopOpacity={0.05} />
                </linearGradient>
                <linearGradient id="threatFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--color-avg_threat_score)" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="var(--color-avg_threat_score)" stopOpacity={0.05} />
                </linearGradient>
              </defs>
              <CartesianGrid vertical={false} strokeDasharray="3 3" />
              <XAxis
                dataKey="bucket"
                tickFormatter={formatBucket}
                tickLine={false}
                axisLine={false}
                minTickGap={24}
              />
              <YAxis yAxisId="articles" tickLine={false} axisLine={false} width={36} />
              <YAxis yAxisId="threat" orientation="right" tickLine={false} axisLine={false} width={36} />
              <ChartTooltip content={<ChartTooltipContent labelFormatter={(value) => formatBucket(String(value))} />} />
              <Area
                yAxisId="articles"
                type="monotone"
                dataKey="articles"
                stroke="var(--color-articles)"
                fill="url(#articlesFill)"
                strokeWidth={2}
              />
              <Area
                yAxisId="threat"
                type="monotone"
                dataKey="avg_threat_score"
                stroke="var(--color-avg_threat_score)"
                fill="url(#threatFill)"
                strokeWidth={2}
              />
            </AreaChart>
          </ChartContainer>
        </div>

        <div className="rounded-[1.75rem] border border-border bg-card p-6 shadow-elevation">
          <div className="mb-5 flex items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.28em] text-muted-foreground">Sentiment balance</p>
              <h2 className="mt-2 text-2xl font-semibold">Distribution snapshot</h2>
            </div>
            <Radar className="h-6 w-6 text-primary" />
          </div>
          <ChartContainer config={chartConfig} className="h-[320px] w-full">
            <PieChart>
              <Pie
                data={sentimentData}
                dataKey="value"
                nameKey="name"
                innerRadius={72}
                outerRadius={104}
                paddingAngle={3}
              >
                {sentimentData.map((entry, index) => (
                  <Cell key={entry.name} fill={riskPalette[index % riskPalette.length]} />
                ))}
              </Pie>
              <ChartTooltip content={<ChartTooltipContent hideIndicator />} />
            </PieChart>
          </ChartContainer>
          <div className="mt-3 flex flex-wrap gap-2">
            {sentimentData.map((item, index) => (
              <span
                key={item.name}
                className="rounded-full border border-border px-3 py-1.5 text-sm text-muted-foreground"
              >
                <span
                  className="mr-2 inline-block h-2.5 w-2.5 rounded-full align-middle"
                  style={{ backgroundColor: riskPalette[index % riskPalette.length] }}
                />
                {item.name}: {item.value}
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <div className="rounded-[1.75rem] border border-border bg-card p-6 shadow-elevation">
          <div className="mb-5 flex items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.28em] text-muted-foreground">Topic exposure</p>
              <h2 className="mt-2 text-2xl font-semibold">Coverage and risk by topic</h2>
            </div>
            <BarChart3 className="h-6 w-6 text-primary" />
          </div>
          <ChartContainer config={chartConfig} className="h-[320px] w-full">
            <BarChart data={topics}>
              <CartesianGrid vertical={false} strokeDasharray="3 3" />
              <XAxis dataKey="topic" tickLine={false} axisLine={false} />
              <YAxis tickLine={false} axisLine={false} width={36} />
              <ChartTooltip content={<ChartTooltipContent />} />
              <Bar dataKey="count" radius={[10, 10, 0, 0]} fill="var(--color-count)" />
            </BarChart>
          </ChartContainer>
          <div className="mt-4 space-y-3">
            {topics.map((topic) => (
              <div key={topic.topic} className="rounded-2xl border border-border bg-background/60 p-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="font-medium capitalize">{topic.topic}</p>
                    <p className="text-sm text-muted-foreground">{topic.count} articles tracked</p>
                  </div>
                  <span className="rounded-full bg-accent/10 px-3 py-1 text-xs text-accent">
                    Threat {Math.round(topic.avg_threat_score)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-[1.75rem] border border-border bg-card p-6 shadow-elevation">
          <div className="mb-5 flex items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.28em] text-muted-foreground">Entity pressure</p>
              <h2 className="mt-2 text-2xl font-semibold">Most active actors in the feed</h2>
            </div>
            <Globe2 className="h-6 w-6 text-primary" />
          </div>
          <div className="space-y-3">
            {entities.map((entity) => (
              <div key={`${entity.entity}-${entity.type}`} className="rounded-2xl border border-border bg-background/60 p-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="font-medium">{entity.entity}</p>
                    <p className="text-sm text-muted-foreground">
                      {entity.type} · {entity.mentions} mentions
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-medium">{Math.round(entity.avg_confidence * 100)}%</p>
                    <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">confidence</p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6 rounded-3xl border border-border bg-[#08111e] p-5">
            <div className="mb-3 flex items-center gap-2 text-sm text-slate-300">
              <Network className="h-4 w-4 text-primary" />
              Network coverage
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-2xl border border-slate-800 bg-slate-950/50 p-4">
                <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Nodes</p>
                <p className="mt-2 text-3xl font-semibold text-white">{network.nodes.length}</p>
              </div>
              <div className="rounded-2xl border border-slate-800 bg-slate-950/50 p-4">
                <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Edges</p>
                <p className="mt-2 text-3xl font-semibold text-white">{network.edges.length}</p>
              </div>
              <div className="rounded-2xl border border-slate-800 bg-slate-950/50 p-4">
                <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Top actor</p>
                <p className="mt-2 text-lg font-semibold text-white">
                  {network.nodes[0]?.label || network.nodes[0]?.id || "Pending"}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
};

export default Analytics;
