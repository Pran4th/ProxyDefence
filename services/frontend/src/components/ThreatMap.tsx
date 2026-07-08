import { Globe2, Link2, Radar } from "lucide-react";

import { cn } from "@/lib/utils";
import type { AttackGraphData } from "@/lib/api";

// Encodes actor prominence/threat-weight using only the semantic status
// tokens, matching the left-edge tab treatment used across dossier cards.
const nodeTabClass = (weight: number) => {
  if (weight >= 0.7) return "bg-destructive";
  if (weight >= 0.4) return "bg-warning";
  return "bg-success";
};

const ThreatMap = ({ graph }: { graph: AttackGraphData }) => {
  const topNodes = graph.nodes.slice(0, 6);
  const topLinks = graph.links.slice(0, 6);

  return (
    <div className="overflow-hidden rounded-md border border-border bg-card">
      <div className="border-b border-border px-6 py-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
              Entity relationship signals
            </p>
            <h3 className="mt-2 text-2xl font-semibold">Actor relationship surface</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Live relationship view derived from negative-sentiment articles and inferred actor links.
            </p>
          </div>
          <Radar className="h-8 w-8 shrink-0 text-primary" />
        </div>
      </div>

      <div className="grid gap-6 px-6 py-6 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-md border border-border bg-muted/30 p-5">
          <div className="mb-5 flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Globe2 className="h-4 w-4 text-primary" />
              High-signal actors
            </div>
            <p className="font-mono text-xs uppercase tracking-[0.2em] tabular-nums text-muted-foreground">
              {graph.nodes.length} nodes
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {topNodes.map((node, index) => {
              const weight = Math.min((node.val ?? 1) / 20, 1);
              return (
                <div
                  key={node.id}
                  className="relative overflow-hidden rounded-md border border-border bg-card p-4"
                >
                  <span
                    className={cn("absolute inset-y-0 left-0 w-1", nodeTabClass(weight))}
                    aria-hidden="true"
                  />
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
                      Actor {index + 1}
                    </span>
                    <span className="font-mono text-xs tabular-nums text-muted-foreground">
                      {node.val ?? 0}
                    </span>
                  </div>
                  <p className="text-base font-medium">{node.id}</p>
                </div>
              );
            })}
          </div>
        </div>

        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <Link2 className="h-4 w-4 text-primary" />
            Relationship edges
          </div>
          {topLinks.map((link, index) => (
            <div
              key={`${link.source}-${link.target}-${index}`}
              className="rounded-md border border-border bg-card p-4"
            >
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="font-medium">{link.source}</p>
                  <p className="text-sm text-muted-foreground">
                    {link.type || "association"} with {link.target}
                  </p>
                </div>
                <span className="rounded border border-border px-2 py-1 font-mono text-xs tabular-nums text-muted-foreground">
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
