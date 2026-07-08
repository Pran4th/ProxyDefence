import { AlertTriangle, BarChart3, Globe2, Droplets, Factory, Zap } from "lucide-react";
import type { EnergyImpact } from "@/lib/api";

const severityColors: Record<string, { bg: string; text: string; border: string }> = {
  critical: { bg: "bg-red-500/20", text: "text-red-400", border: "border-red-500/30" },
  high: { bg: "bg-orange-500/20", text: "text-orange-400", border: "border-orange-500/30" },
  medium: { bg: "bg-yellow-500/20", text: "text-yellow-400", border: "border-yellow-500/30" },
  low: { bg: "bg-blue-500/20", text: "text-blue-400", border: "border-blue-500/30" },
  none: { bg: "bg-green-500/10", text: "text-green-400", border: "border-green-500/20" },
};

const EnergyImpactCard = ({ impact, assessment }: { impact?: EnergyImpact | null; assessment?: string }) => {
  if (!impact || impact.severity === "none") return null;

  const colors = severityColors[impact.severity] || severityColors.none;

  return (
    <div className="rounded-3xl border border-border bg-card p-6">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-primary/10">
            <Zap className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h2 className="text-2xl font-bold">Energy Impact</h2>
            <p className="text-sm text-muted-foreground">Infrastructure and commodity exposure</p>
          </div>
        </div>
        <span className={`rounded-full border px-4 py-2 text-sm font-semibold ${colors.bg} ${colors.text} ${colors.border}`}>
          {impact.severity.toUpperCase()}
        </span>
      </div>

      {assessment && (
        <div className="mb-5 rounded-2xl border border-border bg-background p-4 text-sm leading-6 text-muted-foreground">
          {assessment}
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-2xl border border-border bg-background p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Globe2 className="h-4 w-4 text-blue-400" />
            Countries
          </div>
          <div className="mt-2 text-lg font-semibold">{impact.countries_involved.length}</div>
          {impact.countries_involved.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-1">
              {impact.countries_involved.map((c) => (
                <span key={c} className="rounded-full bg-blue-500/10 px-2 py-0.5 text-xs text-blue-400">{c}</span>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-2xl border border-border bg-background p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Factory className="h-4 w-4 text-orange-400" />
            Infrastructure
          </div>
          <div className="mt-2 text-lg font-semibold">{impact.infrastructure_affected.length}</div>
          {impact.infrastructure_affected.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-1">
              {impact.infrastructure_affected.map((i) => (
                <span key={i} className="rounded-full bg-orange-500/10 px-2 py-0.5 text-xs text-orange-400">{i}</span>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-2xl border border-border bg-background p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <BarChart3 className="h-4 w-4 text-purple-400" />
            Organizations
          </div>
          <div className="mt-2 text-lg font-semibold">{impact.organizations_involved.length}</div>
          {impact.organizations_involved.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-1">
              {impact.organizations_involved.map((o) => (
                <span key={o} className="rounded-full bg-purple-500/10 px-2 py-0.5 text-xs text-purple-400">{o}</span>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-2xl border border-border bg-background p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Droplets className="h-4 w-4 text-cyan-400" />
            Commodities
          </div>
          <div className="mt-2 text-lg font-semibold">{impact.commodities_involved.length}</div>
          {impact.commodities_involved.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-1">
              {impact.commodities_involved.map((c) => (
                <span key={c} className="rounded-full bg-cyan-500/10 px-2 py-0.5 text-xs text-cyan-400">{c}</span>
              ))}
            </div>
          )}
        </div>
      </div>

      {impact.infrastructure_event_count > 0 && (
        <div className="mt-4 flex items-center gap-2 rounded-2xl border border-destructive/30 bg-destructive/5 p-3 text-sm">
          <AlertTriangle className="h-4 w-4 text-destructive" />
          <span className="text-muted-foreground">
            {impact.infrastructure_event_count} infrastructure event{impact.infrastructure_event_count !== 1 ? "s" : ""} reported across {impact.total_energy_articles} article{impact.total_energy_articles !== 1 ? "s" : ""}
          </span>
        </div>
      )}
    </div>
  );
};

export default EnergyImpactCard;
