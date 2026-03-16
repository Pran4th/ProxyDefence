import { cn } from "@/lib/utils";
import { LucideIcon } from "lucide-react";

interface MetricCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  trend?: "up" | "down" | "neutral";
  trendValue?: string;
  variant?: "default" | "threat" | "safe" | "warning";
}

const MetricCard = ({
  title,
  value,
  icon: Icon,
  trend = "neutral",
  trendValue,
  variant = "default",
}: MetricCardProps) => {
  const variantStyles = {
    default: "border-border",
    threat: "border-accent/50 bg-accent/5",
    safe: "border-success/50 bg-success/5",
    warning: "border-warning/50 bg-warning/5",
  };

  const trendColors = {
    up: "text-success",
    down: "text-accent",
    neutral: "text-muted-foreground",
  };

  return (
    <div
      className={cn(
        "rounded-lg border bg-card p-6 shadow-elevation transition-all hover:shadow-glow",
        variantStyles[variant]
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-muted-foreground mb-1">{title}</p>
          <p className="text-3xl font-bold">{value}</p>
          {trendValue && (
            <p className={cn("text-sm mt-1", trendColors[trend])}>
              {trendValue}
            </p>
          )}
        </div>
        <div className="p-3 rounded-lg bg-primary/10">
          <Icon className="h-6 w-6 text-primary" />
        </div>
      </div>
    </div>
  );
};

export default MetricCard;