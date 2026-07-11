import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  BarChart3,
  Bell,
  ChevronDown,
  ChevronUp,
  Cpu,
  Droplets,
  Globe,
  Play,
  RefreshCw,
  Shield,
  Ship,
  TrendingUp,
  Warehouse,
  Zap,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import AppShell from "@/components/AppShell";
import MetricCard from "@/components/MetricCard";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  fetchRiskDashboard,
  fetchCommodityPrices,
  fetchPortCongestion,
  fetchTankerAvailability,
  fetchSignals,
  evaluateScenario,
} from "@/lib/api-intelligence";
import type { RiskDashboard, DisruptionSignal, ScenarioResult } from "@/types/intelligence";
import { formatRiskDimension, RiskDimensionLabel } from "@/lib/riskFormat";

// Semantic status tokens only (matches Search.tsx's precedent for the same
// 5-level severity scale) -- never raw Tailwind palette colors here.
const severityColor: Record<string, string> = {
  low: "bg-success/10 text-success border-success/20",
  moderate: "bg-warning/10 text-warning border-warning/20",
  elevated: "bg-warning/20 text-warning border-warning/30",
  high: "bg-accent/10 text-accent border-accent/20",
  critical: "bg-destructive/10 text-destructive border-destructive/20",
};

// Recharts fills need resolved color values (can't use Tailwind classes),
// so these read the same CSS custom properties the rest of the design
// system uses rather than inventing a separate hex palette.
const dimColor: Record<string, string> = {
  geopolitical: "hsl(var(--primary))",
  operational: "hsl(var(--warning))",
  economic: "hsl(var(--success))",
  environmental: "hsl(var(--accent))",
};

const dimLabel: Record<string, string> = {
  geopolitical: formatRiskDimension("geopolitical").label,
  operational: formatRiskDimension("operational").label,
  economic: formatRiskDimension("economic").label,
  environmental: formatRiskDimension("environmental").label,
};

const CHART_COLORS = [dimColor.geopolitical, dimColor.operational, dimColor.economic, dimColor.environmental];

const RiskDashboardPage = () => {
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState<RiskDashboard | null>(null);
  const [signals, setSignals] = useState<DisruptionSignal[]>([]);
  const [loading, setLoading] = useState(true);
  const [prices, setPrices] = useState<any[]>([]);
  const [congestion, setCongestion] = useState<any[]>([]);
  const [tankers, setTankers] = useState<any[]>([]);
  const [scenarioOpen, setScenarioOpen] = useState(false);
  const [scenarioName, setScenarioName] = useState("Hormuz Closure");
  const [scenarioDesc, setScenarioDesc] = useState("Strait of Hormuz blocked for 2 weeks");
  const [scenarioResult, setScenarioResult] = useState<ScenarioResult | null>(null);
  const [scenarioRunning, setScenarioRunning] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [dash, sigs, priceData, congData, tankData] = await Promise.all([
        fetchRiskDashboard(),
        fetchSignals({ limit: 10 }),
        fetchCommodityPrices({ limit: 10 }),
        fetchPortCongestion({ limit: 10 }),
        fetchTankerAvailability({ limit: 10 }),
      ]);
      setDashboard(dash);
      setSignals(sigs.items);
      setPrices(priceData.items);
      setCongestion(congData.items);
      setTankers(tankData.items);
    } catch (err) {
      console.error("Failed to load risk dashboard", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleScenarioEvaluate = async () => {
    setScenarioRunning(true);
    setScenarioResult(null);
    try {
      const result = await evaluateScenario({
        name: scenarioName,
        description: scenarioDesc,
        assumptions: {
          chokepoint_blockage: 0.85,
          regional_conflict: 0.6,
          price_volatility: 0.7,
          supply_shortage: 0.65,
          port_disruption: 0.4,
        },
        risk_dimensions: ["geopolitical", "operational", "economic", "environmental"],
      });
      setScenarioResult(result);
    } catch (err) {
      console.error("Scenario evaluation failed", err);
    } finally {
      setScenarioRunning(false);
    }
  };

  const chartData =
    dashboard?.risk_by_dimension.map((d) => ({
      label: dimLabel[d.dimension] || d.dimension,
      score: Math.round(d.score * 100),
      fill: dimColor[d.dimension] || "#6366f1",
    })) || [];

  if (loading) {
    return (
      <AppShell title="Risk Intelligence" subtitle="Loading risk dashboard...">
        <div className="flex h-64 items-center justify-center">
          <div className="text-muted-foreground">Loading intelligence data...</div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell
      title="Risk Intelligence"
      subtitle="Real-time geopolitical and operational risk assessment for energy supply chains"
    >
      {/* Controls */}
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <Button
          variant="outline"
          size="sm"
          onClick={() => navigate("/energy/analytics")}
          className="gap-2"
        >
          <Zap className="h-4 w-4" />
          Energy Assets
        </Button>
      </div>

      {/* Metric Cards */}
      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="Active Signals"
          value={dashboard?.total_active_signals ?? 0}
          icon={Bell}
          variant={dashboard && dashboard.high_severity_signals > 0 ? "threat" : "safe"}
          trendValue={`${dashboard?.high_severity_signals ?? 0} high severity`}
        />
        <MetricCard
          title="Average Risk Score"
          value={
            dashboard
              ? `${Math.round((dashboard.average_risk_score ?? 0) * 100)}%`
              : "N/A"
          }
          icon={Shield}
          variant={
            dashboard && (dashboard.average_risk_score ?? 0) > 0.5
              ? "warning"
              : "safe"
          }
        />
        <MetricCard
          title="Commodities Tracked"
          value={prices.length}
          icon={BarChart3}
          variant="default"
        />
        <MetricCard
          title="Ports Monitored"
          value={congestion.length + tankers.length}
          icon={Ship}
          variant="default"
        />
      </div>

      {/* Two-column layout */}
      <div className="mb-6 grid gap-6 lg:grid-cols-3">
        {/* Risk by Dimension Chart */}
        <Card className="rounded-[1.75rem] border-border bg-card shadow-elevation lg:col-span-1">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <BarChart3 className="h-4 w-4 text-primary" />
              Risk by Dimension
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={chartData} layout="vertical">
                <CartesianGrid
                  strokeDasharray="3 3"
                  horizontal={false}
                  stroke="hsl(var(--border))"
                />
                <XAxis
                  type="number"
                  domain={[0, 100]}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }}
                />
                <YAxis
                  type="category"
                  dataKey="label"
                  tickLine={false}
                  axisLine={false}
                  tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }}
                  width={100}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--popover))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: "12px",
                  }}
                  formatter={(value: number) => [`${value}%`, "Risk Score"]}
                />
                <Bar dataKey="score" radius={[0, 8, 8, 0]} barSize={24}>
                  {chartData.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={entry.fill}
                      opacity={0.8}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Latest Signals */}
        <Card className="rounded-[1.75rem] border-border bg-card shadow-elevation lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <AlertTriangle className="h-4 w-4 text-destructive" />
              Latest Disruption Signals
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {signals.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  No active disruption signals right now.
                </p>
              )}
              {signals.slice(0, 8).map((signal) => (
                <div
                  key={signal.uuid}
                  className="flex items-start gap-3 rounded-xl border border-border bg-background p-3 transition hover:border-primary/50"
                >
                  <div
                    className={`mt-0.5 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
                      severityColor[signal.severity]
                    }`}
                  >
                    {signal.severity}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">
                      {signal.title}
                    </p>
                    <p className="line-clamp-1 text-xs text-muted-foreground">
                      {signal.description}
                    </p>
                    <div className="mt-1 flex flex-wrap gap-1.5">
                      <Badge
                        variant="outline"
                        className="text-[10px]"
                        style={{
                          borderColor: `${dimColor[signal.risk_dimension]}40`,
                          color: dimColor[signal.risk_dimension],
                        }}
                      >
                        {dimLabel[signal.risk_dimension] ||
                          signal.risk_dimension}
                      </Badge>
                      {signal.affected_regions?.map((r) => (
                        <Badge
                          key={r}
                          variant="outline"
                          className="text-[10px]"
                        >
                          {r}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Bottom row: Data tables */}
      <div className="mb-6 grid gap-6 lg:grid-cols-3">
        {/* Commodity Prices */}
        <Card className="rounded-[1.75rem] border-border bg-card shadow-elevation">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <TrendingUp className="h-4 w-4 text-success" />
              Commodity Prices
            </CardTitle>
          </CardHeader>
          <CardContent>
            {prices.length === 0 ? (
              <p className="py-4 text-center text-xs text-muted-foreground">
                Not yet connected to a live commodity price feed.
              </p>
            ) : (
            <div className="space-y-2">
              {prices.map((p: any) => (
                <div
                  key={p.uuid}
                  className="flex items-center justify-between rounded-lg border border-border bg-background px-3 py-2"
                >
                  <div>
                    <p className="text-xs font-medium">{p.commodity_name}</p>
                    <p className="text-[10px] text-muted-foreground">
                      {p.unit}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-semibold">${p.price}</p>
                    <p
                      className={`text-[10px] ${
                        (p.change_pct ?? 0) >= 0
                          ? "text-success"
                          : "text-destructive"
                      }`}
                    >
                      {p.change_pct >= 0 ? "+" : ""}
                      {p.change_pct}%
                    </p>
                  </div>
                </div>
              ))}
            </div>
            )}
          </CardContent>
        </Card>

        {/* Port Congestion */}
        <Card className="rounded-[1.75rem] border-border bg-card shadow-elevation">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Ship className="h-4 w-4 text-warning" />
              Port Congestion
            </CardTitle>
          </CardHeader>
          <CardContent>
            {congestion.length === 0 ? (
              <p className="py-4 text-center text-xs text-muted-foreground">
                Not yet connected to a live AIS/port data feed.
              </p>
            ) : (
            <div className="space-y-2">
              {congestion.map((c: any) => (
                <div
                  key={c.uuid}
                  className="flex items-center justify-between rounded-lg border border-border bg-background px-3 py-2"
                >
                  <div>
                    <p className="text-xs font-medium">{c.port_name}</p>
                    <p className="text-[10px] text-muted-foreground">
                      {c.country} · {c.waiting_vessels} vessels waiting
                    </p>
                  </div>
                  <div className="text-right">
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
                        <div
                          className={`h-full rounded-full ${
                            c.congestion_pct > 80
                              ? "bg-destructive"
                              : c.congestion_pct > 50
                                ? "bg-warning"
                                : "bg-success"
                          }`}
                          style={{ width: `${c.congestion_pct}%` }}
                        />
                      </div>
                      <span className="text-xs font-semibold">
                        {c.congestion_pct}%
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            )}
          </CardContent>
        </Card>

        {/* Tanker Availability */}
        <Card className="rounded-[1.75rem] border-border bg-card shadow-elevation">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Warehouse className="h-4 w-4 text-accent" />
              Tanker Availability
            </CardTitle>
          </CardHeader>
          <CardContent>
            {tankers.length === 0 ? (
              <p className="py-4 text-center text-xs text-muted-foreground">
                Not yet connected to a live AIS data feed.
              </p>
            ) : (
            <div className="space-y-2">
              {tankers.map((t: any) => (
                <div
                  key={t.uuid}
                  className="flex items-center justify-between rounded-lg border border-border bg-background px-3 py-2"
                >
                  <div>
                    <p className="text-xs font-medium">{t.vessel_type}</p>
                    <p className="text-[10px] text-muted-foreground">
                      {t.vessels_available} / {t.total_vessels} available
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs font-semibold">
                      ${(t.avg_daily_rate_usd / 1000).toFixed(0)}k/day
                    </p>
                    <p
                      className={`text-[10px] ${
                        t.utilization_pct > 80
                          ? "text-destructive"
                          : "text-muted-foreground"
                      }`}
                    >
                      {t.utilization_pct}% utilized
                    </p>
                  </div>
                </div>
              ))}
            </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Scenario Evaluation */}
      <div className="mb-6 rounded-[1.75rem] border border-border bg-card shadow-elevation">
        <button
          onClick={() => setScenarioOpen(!scenarioOpen)}
          className="flex w-full items-center justify-between p-4"
        >
          <div className="flex items-center gap-2">
            <Cpu className="h-5 w-5 text-primary" />
            <span className="font-semibold">Scenario Evaluator</span>
          </div>
          {scenarioOpen ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}
        </button>
        {scenarioOpen && (
          <div className="border-t border-border p-4">
            <div className="mb-4 grid gap-4 md:grid-cols-2">
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">
                  Scenario Name
                </label>
                <input
                  type="text"
                  value={scenarioName}
                  onChange={(e) => setScenarioName(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">
                  Description
                </label>
                <input
                  type="text"
                  value={scenarioDesc}
                  onChange={(e) => setScenarioDesc(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
                />
              </div>
            </div>
            <div className="mb-4">
              <p className="mb-2 text-xs font-medium text-muted-foreground">
                Preset: Strait of Hormuz Closure (2 weeks) — evaluates risk across all dimensions
              </p>
              <Button
                onClick={handleScenarioEvaluate}
                disabled={scenarioRunning}
                variant="default"
                size="sm"
                className="gap-2"
              >
                {scenarioRunning ? (
                  <RefreshCw className="h-4 w-4 animate-spin" />
                ) : (
                  <Play className="h-4 w-4" />
                )}
                {scenarioRunning ? "Evaluating..." : "Evaluate Scenario"}
              </Button>
            </div>
            {scenarioResult && (
              <div className="rounded-xl border border-border bg-background p-4">
                <div className="mb-3 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold">{scenarioResult.name}</p>
                    <p className="text-xs text-muted-foreground">
                      Risk Level:{" "}
                      <span
                        className={`font-semibold ${
                          scenarioResult.risk_level === "critical"
                            ? "text-destructive"
                            : scenarioResult.risk_level === "high"
                              ? "text-accent"
                              : scenarioResult.risk_level === "elevated" || scenarioResult.risk_level === "moderate"
                                ? "text-warning"
                                : "text-success"
                        }`}
                      >
                        {scenarioResult.risk_level.toUpperCase()}
                      </span>
                    </p>
                  </div>
                  <Shield className="h-8 w-8 text-primary/60" />
                </div>
                <p className="mb-3 text-sm">{scenarioResult.assessment}</p>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  {Object.entries(scenarioResult.risk_scores).map(
                    ([dim, score]) =>
                      dim !== "overall" && (
                        <div
                          key={dim}
                          className="rounded-lg border border-border p-2 text-center"
                        >
                          <p className="text-[10px] capitalize text-muted-foreground">
                            {dim}
                          </p>
                          <p className="text-lg font-bold">
                            {Math.round((score as number) * 100)}%
                          </p>
                        </div>
                      )
                  )}
                </div>
                <p className="mt-2 text-[10px] text-muted-foreground">
                  Overall risk: {Math.round((scenarioResult.risk_scores.overall ?? 0) * 100)}%
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Quick Links Footer */}
      <div className="flex flex-wrap items-center gap-4 rounded-2xl border border-border bg-card p-4">
        <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Quick Actions
        </span>
        <Button
          variant="ghost"
          size="sm"
          className="gap-2"
          onClick={() => navigate("/simulations")}
        >
          <Cpu className="h-4 w-4" />
          Scenario Simulation
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="gap-2"
          onClick={() => navigate("/energy/map")}
        >
          <Globe className="h-4 w-4" />
          Energy Map
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="gap-2"
          onClick={() => navigate("/copilot")}
        >
          <Droplets className="h-4 w-4" />
          Risk Analysis
        </Button>
      </div>
    </AppShell>
  );
};

export default RiskDashboardPage;
