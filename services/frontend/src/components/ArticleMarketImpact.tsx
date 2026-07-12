import { useQuery } from "@tanstack/react-query";
import { TrendingDown, Loader2 } from "lucide-react";
import { fetchArticleImpact } from "@/lib/api-intelligence";

function fmtUsd(v: number | null) {
  if (v == null) return null;
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(0)}M`;
  return `$${Math.round(v).toLocaleString()}`;
}

const severityTone: Record<string, string> = {
  low: "text-success",
  moderate: "text-warning",
  elevated: "text-warning",
  high: "text-accent",
  critical: "text-destructive",
};

/** Renders only when the article genuinely qualified as a real disruption
 * signal (real threat score + real energy-entity match, via
 * ArticleSignalIngestor) -- silent for articles with nothing to say,
 * rather than fabricating an estimate for every article. */
export default function ArticleMarketImpact({ articleId }: { articleId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ["article-impact", articleId],
    queryFn: () => fetchArticleImpact(articleId),
    staleTime: 60000,
  });

  if (isLoading) {
    return (
      <div className="rounded-3xl border border-border bg-card p-6">
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Checking market impact…
        </p>
      </div>
    );
  }

  if (!data?.has_impact_data || data.signals.length === 0) return null;

  return (
    <div className="rounded-3xl border border-warning/30 bg-warning/5 p-6">
      <div className="mb-4 flex items-center gap-2">
        <TrendingDown className="h-5 w-5 text-warning" />
        <h2 className="text-xl font-bold">Market Impact</h2>
      </div>
      <div className="space-y-4">
        {data.signals.map((s) => (
          <div key={s.signal_uuid} className="rounded-2xl border border-border bg-background p-4">
            <div className="mb-2 flex items-center gap-2">
              <span className={`text-xs font-semibold uppercase tracking-wide ${severityTone[s.severity] ?? ""}`}>
                {s.severity}
              </span>
              {s.corridor_name && (
                <span className="text-xs text-muted-foreground">{s.corridor_name}</span>
              )}
            </div>
            <p className="text-sm leading-relaxed text-foreground/90">{s.reasoning}</p>
            {s.estimated_exposure_usd != null && (
              <p className="mt-2 text-sm font-semibold text-warning">
                Estimated exposure: {fmtUsd(s.estimated_exposure_usd)}
              </p>
            )}
          </div>
        ))}
      </div>
      <p className="mt-3 text-[11px] text-muted-foreground">
        Rough, severity-weighted estimate — not a guaranteed loss. Derived from live corridor
        risk, live Brent price, and India's real crude import mix.
      </p>
    </div>
  );
}
