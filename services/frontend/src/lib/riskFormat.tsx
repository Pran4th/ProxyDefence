import type { ReactNode } from "react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export type RiskTone = "destructive" | "warning" | "success" | "muted";

export interface ThreatScoreFormat {
  label: string;
  tone: RiskTone;
  tooltip: string;
}

const TONE_CLASS: Record<RiskTone, string> = {
  destructive: "bg-destructive text-destructive-foreground",
  warning: "bg-warning text-warning-foreground",
  success: "bg-success text-success-foreground",
  muted: "bg-muted text-muted-foreground",
};

/** Bands the platform's 0-100 threat score into a plain-language label a
 * non-technical reader can act on without knowing the underlying scale. */
export const formatThreatScore = (score: number | undefined | null): ThreatScoreFormat => {
  const value = Math.round(score ?? 0);
  if (value >= 70) {
    return {
      label: "High Priority",
      tone: "destructive",
      tooltip: `Threat score ${value}/100 — model flags this as a high-priority disruption signal. Review promptly.`,
    };
  }
  if (value >= 40) {
    return {
      label: "Moderate",
      tone: "warning",
      tooltip: `Threat score ${value}/100 — some risk indicators present. Worth monitoring.`,
    };
  }
  return {
    label: "Low",
    tone: "success",
    tooltip: `Threat score ${value}/100 — few risk indicators detected in this report.`,
  };
};

const RISK_DIMENSION_LABELS: Record<string, { label: string; description: string }> = {
  geopolitical: {
    label: "Political & Conflict Risk",
    description: "Sanctions, conflict, and diplomatic tension affecting supply routes.",
  },
  operational: {
    label: "Supply Chain Disruption",
    description: "Port congestion, chokepoint blockages, and logistics bottlenecks.",
  },
  economic: {
    label: "Market & Price Risk",
    description: "Commodity price volatility and market-driven cost exposure.",
  },
  environmental: {
    label: "Environmental & Safety Risk",
    description: "Weather, accidents, and infrastructure safety incidents.",
  },
};

/** Translates internal risk-dimension keys (geopolitical/operational/...) into
 * business-friendly labels. Falls back to a titleized version of the raw key
 * for any dimension not in the map, so new dimensions don't render blank. */
export const formatRiskDimension = (key: string): { label: string; description: string } =>
  RISK_DIMENSION_LABELS[key] ?? {
    label: key.charAt(0).toUpperCase() + key.slice(1).replace(/_/g, " "),
    description: "",
  };

/** Drop-in badge for a threat/risk score: shows the banded label, with the
 * raw score available on hover for analysts who want the underlying number. */
export const ThreatBadge = ({ score, className }: { score: number | undefined | null; className?: string }) => {
  const { label, tone, tooltip } = formatThreatScore(score);
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${TONE_CLASS[tone]} ${className ?? ""}`}
        >
          {label}
        </span>
      </TooltipTrigger>
      <TooltipContent>{tooltip}</TooltipContent>
    </Tooltip>
  );
};

/** Wraps arbitrary content (a chart label, dimension key, etc.) with a hover
 * tooltip explaining what it means in plain language. */
export const RiskDimensionLabel = ({ dimensionKey, children }: { dimensionKey: string; children: ReactNode }) => {
  const { label, description } = formatRiskDimension(dimensionKey);
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="cursor-help underline decoration-dotted underline-offset-4">{children ?? label}</span>
      </TooltipTrigger>
      {description && <TooltipContent>{description}</TooltipContent>}
    </Tooltip>
  );
};
