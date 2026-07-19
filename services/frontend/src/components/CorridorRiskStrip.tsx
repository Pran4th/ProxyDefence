import { useQuery } from "@tanstack/react-query";
import { TrendingUp, Waves } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { fetchCorridorRisk, type CorridorRisk } from "@/lib/api-intelligence";
import { Skeleton } from "@/components/ui/skeleton";

function probabilityTone(p: number): { bar: string; text: string; label: string } {
  if (p >= 0.7) return { bar: "bg-destructive", text: "text-destructive", label: "Severe" };
  if (p >= 0.45) return { bar: "bg-warning", text: "text-warning", label: "Elevated" };
  return { bar: "bg-success", text: "text-success", label: "Stable" };
}

function CorridorCard({ corridor }: { corridor: CorridorRisk }) {
  const tone = probabilityTone(corridor.probability_30d);
  const pct = Math.round(corridor.probability_30d * 100);
  const topDriver = corridor.drivers[0];

  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="min-w-[220px] flex-1 cursor-default rounded-xl border border-border bg-card px-4 py-3">
            <div className="flex items-start justify-between gap-2">
              <p className="text-xs font-medium leading-tight">{corridor.name}</p>
              <span className={`text-sm font-bold tabular-nums ${tone.text}`}>{pct}%</span>
            </div>
            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div
                className={`h-full rounded-full ${tone.bar}`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <div className="mt-2 flex items-center justify-between text-[10px] text-muted-foreground">
              <span>
                {tone.label} · 30-day disruption
              </span>
              <span>
                {corridor.india_import_share_pct > 0 &&
                  `${corridor.india_import_share_pct}% of India crude`}
              </span>
            </div>
            {topDriver && (
              <p className="mt-1.5 line-clamp-1 text-[10px] text-muted-foreground">
                <TrendingUp className="mr-1 inline h-3 w-3 text-warning" />
                {topDriver.title}
              </p>
            )}
          </div>
        </TooltipTrigger>
        <TooltipContent side="bottom" className="max-w-xs">
          <p className="mb-1 font-semibold">
            {corridor.name} — {pct}% (confidence {Math.round(corridor.confidence * 100)}%)
          </p>
          {corridor.drivers.length > 0 ? (
            <ul className="space-y-1 text-xs">
              {corridor.drivers.map((d) => (
                <li key={d.signal_uuid}>
                  <span className="uppercase text-warning">[{d.severity}]</span> {d.title}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-muted-foreground">
              No active disruption signals on this corridor.
            </p>
          )}
          {corridor.india_import_share_year && (
            <p className="mt-1 text-[10px] text-muted-foreground">
              Import share: UN Comtrade {corridor.india_import_share_year}
            </p>
          )}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

export default function CorridorRiskStrip() {
  const { data, isLoading } = useQuery({
    queryKey: ["corridor-risk"],
    queryFn: fetchCorridorRisk,
    refetchInterval: 30000,
  });

  if (isLoading) {
    return (
      <div className="flex gap-3 overflow-x-auto pb-1">
        {[...Array(5)].map((_, i) => (
          <Skeleton key={i} className="h-24 min-w-[220px] flex-1 rounded-xl" />
        ))}
      </div>
    );
  }

  if (!data?.corridors?.length) return null;

  return (
    <div>
      <div className="mb-2 flex items-center gap-2">
        <Waves className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-semibold">Corridor Disruption Probability</h3>
        <span className="text-[10px] text-muted-foreground">
          current scored view · signal, entity-risk, stability and AIS inputs
        </span>
      </div>
      <div className="flex gap-3 overflow-x-auto pb-1">
        {data.corridors.map((c) => (
          <CorridorCard key={c.key} corridor={c} />
        ))}
      </div>
    </div>
  );
}
