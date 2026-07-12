import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Radio, TrendingDown, Clock } from "lucide-react";
import AppShell from "@/components/AppShell";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchImpactFeed } from "@/lib/api-intelligence";

const severityTone: Record<string, string> = {
  low: "bg-success/15 text-success border-success/30",
  moderate: "bg-warning/15 text-warning border-warning/30",
  elevated: "bg-warning/20 text-warning border-warning/40",
  high: "bg-accent/15 text-accent border-accent/30",
  critical: "bg-destructive/15 text-destructive border-destructive/30",
};

function fmtUsd(v: number | null) {
  if (v == null) return null;
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(0)}M`;
  return `$${Math.round(v).toLocaleString()}`;
}

function relativeTime(iso: string) {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export default function MarketImpactFeed() {
  const { data, isLoading } = useQuery({
    queryKey: ["impact-feed"],
    queryFn: () => fetchImpactFeed(20),
    refetchInterval: 20000,
  });

  return (
    <AppShell
      title="Market Impact Feed"
      subtitle="Live: real news, scored by real ML, turned into an estimated market impact — continuously"
    >
      <div className="mb-6 flex items-center gap-2 rounded-2xl border border-primary/20 bg-primary/5 px-4 py-3 text-xs text-muted-foreground">
        <Radio className="h-4 w-4 animate-pulse text-destructive" />
        <p>
          Every item below is a real signal our ML pipeline just derived from live news — not a
          demo. Refreshes every 20 seconds.
        </p>
      </div>

      <div className="space-y-3">
        {isLoading &&
          [...Array(6)].map((_, i) => <Skeleton key={i} className="h-28 rounded-2xl" />)}

        {!isLoading && data?.items.length === 0 && (
          <p className="py-12 text-center text-sm text-muted-foreground">
            No active signals right now — check back shortly.
          </p>
        )}

        {data?.items.map((item) => (
          <Card key={item.signal_uuid} className="rounded-2xl border-border bg-card">
            <CardContent className="pt-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="mb-1.5 flex flex-wrap items-center gap-2">
                    <Badge className={`border text-[10px] uppercase ${severityTone[item.severity] ?? ""}`}>
                      {item.severity}
                    </Badge>
                    {item.corridor_name && (
                      <span className="text-[11px] text-muted-foreground">{item.corridor_name}</span>
                    )}
                    <span className="flex items-center gap-1 text-[11px] text-muted-foreground">
                      <Clock className="h-3 w-3" /> {relativeTime(item.detected_at)}
                    </span>
                  </div>
                  <p className="text-sm font-medium leading-snug">{item.title}</p>
                  <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                    {item.reasoning}
                  </p>
                </div>
                {item.estimated_exposure_usd != null && (
                  <div className="shrink-0 text-right">
                    <div className="flex items-center gap-1 text-warning">
                      <TrendingDown className="h-3.5 w-3.5" />
                      <span className="text-lg font-bold tabular-nums">
                        {fmtUsd(item.estimated_exposure_usd)}
                      </span>
                    </div>
                    <p className="text-[10px] text-muted-foreground">estimated exposure</p>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <p className="mt-6 text-center text-[11px] text-muted-foreground">
        Want the full response pipeline — scenario simulation, SPR, and procurement recommendations
        for any of these?{" "}
        <Link to="/command" className="text-primary hover:underline">
          Open Command Center
        </Link>
      </p>
    </AppShell>
  );
}
