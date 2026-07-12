import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Play, ArrowRight, Zap } from "lucide-react";
import { fetchSandboxScenarios, type SandboxScenario } from "@/lib/api";

function fmtUsd(v: number) {
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(0)}M`;
  return `$${Math.round(v).toLocaleString()}`;
}

const severityTone: Record<string, string> = {
  low: "border-success/40 text-success",
  medium: "border-warning/40 text-warning",
  high: "border-accent/40 text-accent",
  critical: "border-destructive/40 text-destructive",
};

/** Real, previously-computed digital-twin runs -- lets anonymous visitors
 * click through genuine scenario outcomes instead of reading marketing
 * copy about what the engine "could" do. Read-only, so free to explore. */
export default function ScenarioSandbox() {
  const [scenarios, setScenarios] = useState<SandboxScenario[] | null>(null);
  const [active, setActive] = useState<SandboxScenario | null>(null);

  useEffect(() => {
    fetchSandboxScenarios()
      .then((d) => {
        setScenarios(d.scenarios);
        setActive(d.scenarios[0] ?? null);
      })
      .catch(() => setScenarios([]));
  }, []);

  if (scenarios === null) {
    return <div className="h-64 animate-pulse rounded-2xl border border-border bg-muted/20" />;
  }
  if (scenarios.length === 0) return null;

  return (
    <div className="rounded-2xl border border-border bg-card/60 p-5 backdrop-blur">
      <div className="mb-4 flex items-center gap-2">
        <Zap className="h-4 w-4 text-primary" />
        <p className="text-sm font-semibold">Try a real scenario</p>
        <span className="text-[10px] text-muted-foreground">
          — actual digital-twin output, not a mockup
        </span>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {scenarios.map((s) => (
          <button
            key={s.uuid}
            onClick={() => setActive(s)}
            className={`rounded-full border px-3 py-1.5 text-xs transition-colors ${
              active?.uuid === s.uuid
                ? "border-primary bg-primary/10 text-primary"
                : "border-border text-muted-foreground hover:border-primary/40"
            }`}
          >
            {s.scenario_name}
          </button>
        ))}
      </div>

      {active && (
        <div className="rounded-xl border border-border bg-background p-4">
          <div className="mb-2 flex items-center gap-2">
            <Play className="h-3.5 w-3.5 text-primary" />
            <span
              className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase ${
                severityTone[active.severity] ?? ""
              }`}
            >
              {active.severity}
            </span>
          </div>
          <p className="text-xs text-muted-foreground">{active.scenario_description}</p>
          <div className="mt-3 grid grid-cols-3 gap-3 text-center">
            <div>
              <p className="text-lg font-bold">{(active.max_supply_gap_bpd / 1e6).toFixed(1)}M</p>
              <p className="text-[10px] text-muted-foreground">bpd supply gap</p>
            </div>
            <div>
              <p className="text-lg font-bold text-warning">{fmtUsd(active.economic_impact_usd)}</p>
              <p className="text-[10px] text-muted-foreground">economic impact</p>
            </div>
            <div>
              <p className="text-lg font-bold text-destructive">{active.gdp_impact_pct}%</p>
              <p className="text-[10px] text-muted-foreground">GDP impact</p>
            </div>
          </div>
          <p className="mt-3 text-[10px] text-muted-foreground">
            Computed over {active.max_ticks} simulated days in {active.execution_time_ms}ms by the
            real digital twin.
          </p>
        </div>
      )}

      <Link
        to="/auth"
        className="mt-4 inline-flex items-center gap-1.5 text-xs text-primary hover:underline"
      >
        Run your own scenario in Command Center <ArrowRight className="h-3 w-3" />
      </Link>
    </div>
  );
}
