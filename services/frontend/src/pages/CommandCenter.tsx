import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowRight,
  CheckCircle2,
  Clock,
  Factory,
  Loader2,
  Map as MapIcon,
  Radio,
  Ship,
  Warehouse,
  Zap,
} from "lucide-react";
import AppShell from "@/components/AppShell";
import CorridorRiskStrip from "@/components/CorridorRiskStrip";
import SignalWhy from "@/components/SignalWhy";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";
import {
  fetchResponseTelemetry,
  fetchSignals,
  respondToSignal,
  type CommandResponseBundle,
} from "@/lib/api-intelligence";
import type { DisruptionSignal } from "@/types/intelligence";

const STAGES = [
  { key: "signal", label: "Signal", icon: Radio },
  { key: "scenario", label: "Scenario", icon: Activity },
  { key: "twin", label: "Digital Twin", icon: Factory },
  { key: "spr", label: "SPR", icon: Warehouse },
  { key: "procurement", label: "Procurement", icon: Ship },
] as const;

const severityBadge: Record<string, string> = {
  low: "bg-success/15 text-success",
  moderate: "bg-warning/15 text-warning",
  elevated: "bg-warning/20 text-warning",
  high: "bg-accent/20 text-accent",
  critical: "bg-destructive/15 text-destructive",
};

function fmtBpd(v?: number) {
  if (v == null) return "—";
  return v >= 1e6 ? `${(v / 1e6).toFixed(1)}M bpd` : `${Math.round(v / 1e3)}k bpd`;
}

function fmtUsd(v?: number) {
  if (v == null) return "—";
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(0)}M`;
  return `$${Math.round(v).toLocaleString()}`;
}

export default function CommandCenter() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [bundle, setBundle] = useState<CommandResponseBundle | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const { data: signalData } = useQuery({
    queryKey: ["cc-signals"],
    queryFn: () => fetchSignals({ limit: 12 }),
    refetchInterval: 10000,
  });

  const { data: telemetry } = useQuery({
    queryKey: ["cc-telemetry"],
    queryFn: fetchResponseTelemetry,
    refetchInterval: 30000,
  });

  const respond = useMutation({
    mutationFn: respondToSignal,
    onMutate: () => {
      setBundle(null);
      setElapsed(0);
      timerRef.current = setInterval(() => setElapsed((e) => e + 0.1), 100);
    },
    onSuccess: (data) => {
      setBundle(data);
      queryClient.invalidateQueries({ queryKey: ["cc-telemetry"] });
      toast({
        title: `Recommendation ready in ${data.telemetry.pipeline_latency_seconds}s`,
        description: `Scenario: ${data.scenario.name}`,
      });
    },
    onError: (err: Error & { response?: { data?: { detail?: string } } }) => {
      toast({
        title: "Response pipeline failed",
        description: err.response?.data?.detail ?? err.message,
        variant: "destructive",
      });
    },
    onSettled: () => {
      if (timerRef.current) clearInterval(timerRef.current);
    },
  });

  useEffect(() => () => {
    if (timerRef.current) clearInterval(timerRef.current);
  }, []);

  const running = respond.isPending;
  // While running, walk stages on a rough schedule; snap all-complete on result.
  const activeStage = bundle ? STAGES.length : running ? Math.min(1 + Math.floor(elapsed / 8), STAGES.length - 1) : 0;

  const signals: DisruptionSignal[] = signalData?.items ?? [];
  const impacts = bundle?.twin_run.aggregate_impacts ?? {};
  const sprResults = (bundle?.spr_run as { results?: Record<string, number> })?.results ?? {};
  const sprRecs =
    (bundle?.spr_run as { recommendations?: { title: string; summary: string; severity: string }[] })
      ?.recommendations ?? [];
  const proc = (bundle?.procurement_run ?? {}) as Record<string, number | string>;

  return (
    <AppShell
      title="Command Center"
      subtitle="From live disruption signal to executable procurement decision — one click, real latency"
    >
      <div className="mb-6">
        <CorridorRiskStrip />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* ── Live signal feed ── */}
        <Card className="rounded-[1.75rem] border-border bg-card shadow-elevation lg:col-span-1">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-2">
                <Radio className="h-4 w-4 animate-pulse text-destructive" />
                Live Disruption Signals
              </span>
              <Button
                size="sm"
                disabled={running}
                onClick={() => respond.mutate({ auto: true })}
              >
                {running ? <Loader2 className="h-4 w-4 animate-spin" /> : "Respond to top threat"}
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent className="max-h-[520px] space-y-2 overflow-y-auto">
            {signals.length === 0 && (
              <p className="py-6 text-center text-xs text-muted-foreground">
                No active signals right now.
              </p>
            )}
            {signals.map((s) => (
              <div
                key={s.uuid}
                className="rounded-lg border border-border bg-background px-3 py-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="line-clamp-2 text-xs font-medium">{s.title}</p>
                  <Badge className={`shrink-0 text-[9px] uppercase ${severityBadge[s.severity] ?? ""}`}>
                    {s.severity}
                  </Badge>
                </div>
                <div className="mt-1.5 flex items-center justify-between">
                  <span className="text-[10px] text-muted-foreground">
                    {new Date(s.created_at).toLocaleString()}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-6 px-2 text-[10px]"
                    disabled={running}
                    onClick={() => respond.mutate({ signal_uuid: s.uuid })}
                  >
                    Respond
                  </Button>
                </div>
                <SignalWhy signalUuid={s.uuid} />
              </div>
            ))}
          </CardContent>
        </Card>

        {/* ── Response pipeline ── */}
        <div className="space-y-6 lg:col-span-2">
          <Card className="rounded-[1.75rem] border-border bg-card shadow-elevation">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center justify-between text-sm">
                <span>Response Pipeline</span>
                <span className="flex items-center gap-2 text-xs font-normal text-muted-foreground">
                  <Clock className="h-3.5 w-3.5" />
                  {bundle
                    ? `${bundle.telemetry.pipeline_latency_seconds}s`
                    : running
                      ? `${elapsed.toFixed(1)}s`
                      : telemetry?.pipeline_latency_p50_seconds
                        ? `p50 ${telemetry.pipeline_latency_p50_seconds}s over ${telemetry.total} responses`
                        : "idle"}
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-1 overflow-x-auto pb-2">
                {STAGES.map((stage, i) => {
                  const done = bundle !== null || i < activeStage;
                  const active = running && i === activeStage;
                  const Icon = stage.icon;
                  return (
                    <div key={stage.key} className="flex items-center gap-1">
                      <div
                        className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs transition-colors ${
                          done
                            ? "border-success/50 bg-success/10 text-success"
                            : active
                              ? "border-primary/60 bg-primary/10 text-primary"
                              : "border-border text-muted-foreground"
                        }`}
                      >
                        {done ? (
                          <CheckCircle2 className="h-3.5 w-3.5" />
                        ) : active ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Icon className="h-3.5 w-3.5" />
                        )}
                        {stage.label}
                      </div>
                      {i < STAGES.length - 1 && (
                        <ArrowRight className="h-3 w-3 shrink-0 text-muted-foreground" />
                      )}
                    </div>
                  );
                })}
              </div>

              {bundle && (
                <div className="mt-3 rounded-xl border border-success/40 bg-success/5 px-4 py-3">
                  <p className="text-sm font-semibold text-success">
                    Signal → executable recommendation in{" "}
                    {bundle.telemetry.pipeline_latency_seconds}s
                  </p>
                  <p className="mt-0.5 text-[11px] text-muted-foreground">
                    Industry benchmark for supply-shock response: ~47 days (McKinsey).
                    Scenario applied: {bundle.scenario.name}.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* ── Results ── */}
          {bundle && (
            <>
              <div className="grid gap-4 sm:grid-cols-3">
                <Card className="rounded-2xl border-border bg-card">
                  <CardContent className="pt-4">
                    <p className="text-[10px] uppercase text-muted-foreground">Supply gap</p>
                    <p className="text-xl font-bold">{fmtBpd(impacts.max_supply_gap_bpd ?? impacts.supply_gap_bpd)}</p>
                    <p className="text-[10px] text-muted-foreground">
                      over {bundle.twin_run.ticks_executed} simulated days
                    </p>
                  </CardContent>
                </Card>
                <Card className="rounded-2xl border-border bg-card">
                  <CardContent className="pt-4">
                    <p className="text-[10px] uppercase text-muted-foreground">Economic impact</p>
                    <p className="text-xl font-bold">{fmtUsd(impacts.economic_impact_usd)}</p>
                    <p className="text-[10px] text-muted-foreground">
                      {impacts.gdp_impact_pct != null ? `${impacts.gdp_impact_pct}% of GDP` : ""}
                    </p>
                  </CardContent>
                </Card>
                <Card className="rounded-2xl border-border bg-card">
                  <CardContent className="pt-4">
                    <p className="text-[10px] uppercase text-muted-foreground">SPR coverage</p>
                    <p className="text-xl font-bold">
                      {sprResults.coverage_pct != null ? `${sprResults.coverage_pct}%` : "—"}
                    </p>
                    <p className="text-[10px] text-muted-foreground">
                      {sprResults.days_until_depletion != null
                        ? `${sprResults.days_until_depletion} days to depletion`
                        : ""}
                    </p>
                  </CardContent>
                </Card>
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <Card className="rounded-2xl border-border bg-card">
                  <CardHeader className="pb-2">
                    <CardTitle className="flex items-center gap-2 text-xs">
                      <Warehouse className="h-4 w-4 text-primary" /> SPR Decision
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {sprRecs.slice(0, 2).map((r, i) => (
                      <div key={i} className="rounded-lg border border-border bg-background p-2.5">
                        <p className="text-xs font-medium">{r.title}</p>
                        <p className="mt-0.5 line-clamp-2 text-[10px] text-muted-foreground">{r.summary}</p>
                      </div>
                    ))}
                    <Link
                      to="/intelligence/spr"
                      className="inline-flex items-center gap-1 text-[11px] text-primary hover:underline"
                    >
                      Full SPR analysis <ArrowRight className="h-3 w-3" />
                    </Link>
                  </CardContent>
                </Card>

                <Card className="rounded-2xl border-border bg-card">
                  <CardHeader className="pb-2">
                    <CardTitle className="flex items-center gap-2 text-xs">
                      <Ship className="h-4 w-4 text-accent" /> Procurement Decision
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <p className="line-clamp-4 text-[11px] text-muted-foreground">
                      {String(proc.executive_summary ?? "")}
                    </p>
                    <div className="flex flex-wrap gap-3 text-[10px] text-muted-foreground">
                      <span>{proc.recommendations_count ?? 0} options evaluated</span>
                      <span>{proc.pareto_count ?? 0} Pareto-optimal</span>
                      <span>risk {typeof proc.total_risk_score === "number" ? proc.total_risk_score.toFixed(2) : "—"}</span>
                    </div>
                    <Link
                      to="/intelligence/procurement"
                      className="inline-flex items-center gap-1 text-[11px] text-primary hover:underline"
                    >
                      Full procurement run <ArrowRight className="h-3 w-3" />
                    </Link>
                  </CardContent>
                </Card>
              </div>

              <div className="flex flex-wrap gap-3">
                <Button asChild variant="outline" size="sm" className="gap-2">
                  <Link to={`/energy/map?run_uuid=${bundle.twin_run.run_uuid}`}>
                    <MapIcon className="h-4 w-4" /> View impact on map
                  </Link>
                </Button>
                <Button asChild variant="outline" size="sm" className="gap-2">
                  <Link to="/simulations">
                    <Zap className="h-4 w-4" /> Open simulation
                  </Link>
                </Button>
              </div>
            </>
          )}
        </div>
      </div>
    </AppShell>
  );
}
