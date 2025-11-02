import { Clock, TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";

interface NewsCardProps {
  title: string;
  description: string;
  timestamp: string;
  severity?: "low" | "medium" | "high" | "critical";
  source?: string;
}

const NewsCard = ({
  title,
  description,
  timestamp,
  severity = "medium",
  source = "ProxyDefence Intel",
}: NewsCardProps) => {
  const severityStyles = {
    low: "bg-success/10 text-success border-success/30",
    medium: "bg-warning/10 text-warning border-warning/30",
    high: "bg-accent/10 text-accent border-accent/30",
    critical: "bg-destructive/10 text-destructive border-destructive/30",
  };

  return (
    <div className="rounded-lg border border-border bg-card p-5 shadow-elevation hover:shadow-glow transition-all cursor-pointer group">
      <div className="flex items-start gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <span
              className={cn(
                "px-2 py-1 rounded text-xs font-medium border uppercase",
                severityStyles[severity]
              )}
            >
              {severity}
            </span>
            <span className="text-xs text-muted-foreground">{source}</span>
          </div>
          <h3 className="text-lg font-semibold mb-2 group-hover:text-primary transition-colors">
            {title}
          </h3>
          <p className="text-sm text-muted-foreground mb-3">{description}</p>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Clock className="h-3 w-3" />
            <span>{timestamp}</span>
          </div>
        </div>
        <TrendingUp className="h-5 w-5 text-primary opacity-50 group-hover:opacity-100 transition-opacity" />
      </div>
    </div>
  );
};

export default NewsCard;
