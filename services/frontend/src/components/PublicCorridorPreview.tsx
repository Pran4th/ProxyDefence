import { useEffect, useState } from "react";
import { Waves } from "lucide-react";
import { fetchPublicCorridorRisk, type PublicCorridorRisk } from "@/lib/api";

function tone(p: number) {
  if (p >= 0.7) return { bar: "bg-destructive", text: "text-destructive" };
  if (p >= 0.45) return { bar: "bg-warning", text: "text-warning" };
  return { bar: "bg-success", text: "text-success" };
}

/** Real, live, unauthenticated -- lets anonymous visitors interact with an
 * actual slice of the product instead of static marketing copy. Polls so
 * the "Live" badge on the page is telling the truth. */
export default function PublicCorridorPreview() {
  const [corridors, setCorridors] = useState<PublicCorridorRisk[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      fetchPublicCorridorRisk()
        .then((d) => !cancelled && setCorridors(d.corridors))
        .catch(() => {});
    };
    load();
    const interval = setInterval(load, 30000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  if (!corridors) {
    return (
      <div className="grid gap-2 sm:grid-cols-3">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-16 animate-pulse rounded-xl border border-border bg-muted/30" />
        ))}
      </div>
    );
  }

  return (
    <div>
      <div className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
        <Waves className="h-3.5 w-3.5 text-primary" />
        Live 30-day disruption probability, computed from real news this minute
      </div>
      <div className="grid gap-2 sm:grid-cols-3">
        {corridors.slice(0, 3).map((c) => {
          const t = tone(c.probability_30d);
          const pct = Math.round(c.probability_30d * 100);
          return (
            <div key={c.key} className="rounded-xl border border-border bg-card/60 p-3 backdrop-blur">
              <div className="flex items-center justify-between">
                <span className="truncate text-xs font-medium">{c.name.split("(")[0].trim()}</span>
                <span className={`text-sm font-bold ${t.text}`}>{pct}%</span>
              </div>
              <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-muted">
                <div className={`h-full rounded-full ${t.bar}`} style={{ width: `${pct}%` }} />
              </div>
              {c.drivers[0] && (
                <p className="mt-1.5 line-clamp-1 text-[10px] text-muted-foreground">
                  {c.drivers[0].title}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
