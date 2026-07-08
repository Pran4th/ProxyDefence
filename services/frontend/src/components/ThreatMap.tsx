import { Globe2, Link2, Radar } from "lucide-react";

import type { AttackGraphData } from "@/lib/api";

const severityColor = (value: number) => {
  if (value >= 0.8) return "bg-destructive";
  if (value >= 0.6) return "bg-accent";
  if (value >= 0.4) return "bg-warning";
  return "bg-primary";
};

const ThreatMap = ({ graph }: { graph: AttackGraphData }) => {
  const topNodes = graph.nodes.slice(0, 6);
  const topLinks = graph.links.slice(0, 6);

  return (
    <div className="overflow-hidden rounded-[1.75rem] border border-border bg-card shadow-elevation">
      <div className="border-b border-border bg-gradient-to-r from-primary/10 to-accent/10 px-6 py-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.28em] text-muted-foreground">Threat graph</p>
            <h3 className="mt-2 text-2xl font-semibold">Actor relationship surface</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Live relationship view derived from negative-sentiment articles and inferred actor links.
            </p>
          </div>
          <Radar className="h-9 w-9 text-primary" />
        </div>
      </div>

      <div className="grid gap-6 px-6 py-6 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-3xl border border-border bg-[#08111e] p-5">
          <div className="mb-5 flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-slate-300">
              <Globe2 className="h-4 w-4 text-primary" />
              High-signal actors
            </div>
            <p className="text-xs uppercase tracking-[0.22em] text-slate-400">{graph.nodes.length} nodes</p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {topNodes.map((node, index) => (
              <div key={node.id} className="rounded-2xl border border-slate-800 bg-slate-950/50 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-xs uppercase tracking-[0.22em] text-slate-500">Actor {index + 1}</span>
                  <span className="rounded-full bg-primary/10 px-2 py-1 text-xs text-primary">{node.val ?? 0}</span>
                </div>
                <p className="text-lg font-medium text-white">{node.id}</p>
                <div className="mt-3 h-2 rounded-full bg-slate-800">
                  <div
                    className={`h-2 rounded-full ${severityColor((node.val ?? 1) / 20)}`}
                    style={{ width: `${Math.min(((node.val ?? 1) / 20) * 100, 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <Link2 className="h-4 w-4 text-primary" />
            Relationship edges
          </div>
          {topLinks.map((link, index) => (
            <div key={`${link.source}-${link.target}-${index}`} className="rounded-2xl border border-border bg-background/60 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="font-medium">{link.source}</p>
                  <p className="text-sm text-muted-foreground">{link.type || "association"} with {link.target}</p>
                </div>
                <span className="rounded-full border border-border px-2 py-1 text-xs text-muted-foreground">
                  {Math.round((link.value ?? 0) * 100)}%
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default ThreatMap;
