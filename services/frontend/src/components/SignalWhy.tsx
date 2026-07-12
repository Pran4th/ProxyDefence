import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, Loader2 } from "lucide-react";
import { fetchSignalExplanation } from "@/lib/api-intelligence";

function fmtUsd(v: number | null) {
  if (v == null) return null;
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(0)}M`;
  return `$${Math.round(v).toLocaleString()}`;
}

function probabilityTone(p: number): string {
  if (p >= 0.7) return "bg-destructive";
  if (p >= 0.45) return "bg-warning";
  return "bg-success";
}

/** Collapsed by default -- expand on demand since the explanation involves
 * live DB queries (corridor blend, live Brent) and isn't cheap to compute
 * for every signal in a list up front. */
export default function SignalWhy({ signalUuid }: { signalUuid: string }) {
  const [open, setOpen] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["signal-explain", signalUuid],
    queryFn: () => fetchSignalExplanation(signalUuid),
    enabled: open,
    staleTime: 60000,
  });

  return (
    <div className="mt-1">
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((o) => !o);
        }}
        className="flex items-center gap-1 text-[10px] font-medium text-primary hover:underline"
      >
        Why is this high?
        {open ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
      </button>
      {open && (
        <div className="mt-1.5 rounded-lg border border-primary/20 bg-primary/5 p-2.5">
          {isLoading ? (
            <p className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" /> Computing exposure…
            </p>
          ) : data ? (
            <>
              <p className="text-[11px] leading-relaxed text-foreground/90">{data.reasoning}</p>
              {data.corridor_probability_30d != null && (
                <div className="mt-1.5 flex items-center gap-1.5">
                  <div className="h-1 w-16 overflow-hidden rounded-full bg-muted">
                    <div
                      className={`h-full rounded-full ${probabilityTone(data.corridor_probability_30d)}`}
                      style={{ width: `${Math.round(data.corridor_probability_30d * 100)}%` }}
                    />
                  </div>
                  <span className="text-[10px] text-muted-foreground">
                    {Math.round(data.corridor_probability_30d * 100)}% 30-day corridor disruption probability
                  </span>
                </div>
              )}
              {data.estimated_exposure_usd != null && (
                <p className="mt-1.5 text-[11px] font-semibold text-warning">
                  Estimated exposure: {fmtUsd(data.estimated_exposure_usd)}
                </p>
              )}
              {data.assumptions.length > 0 && (
                <ul className="mt-1.5 space-y-0.5 border-t border-border/50 pt-1.5">
                  {data.assumptions.map((a) => (
                    <li key={a.name} className="text-[10px] text-muted-foreground">
                      <span className="font-medium">{a.name}:</span> {String(a.value)}
                    </li>
                  ))}
                </ul>
              )}
            </>
          ) : (
            <p className="text-[11px] text-muted-foreground">Could not compute reasoning.</p>
          )}
        </div>
      )}
    </div>
  );
}
