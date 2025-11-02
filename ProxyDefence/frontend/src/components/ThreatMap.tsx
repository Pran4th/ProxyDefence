import { useState, useEffect } from "react";
import { Globe } from "lucide-react";

const ThreatMap = () => {
  const [activeThreats, setActiveThreats] = useState(247);

  useEffect(() => {
    const interval = setInterval(() => {
      setActiveThreats((prev) => prev + Math.floor(Math.random() * 10) - 5);
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="relative rounded-lg border border-border bg-card p-6 shadow-elevation overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-accent/5" />
      
      <div className="relative z-10">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-lg font-semibold mb-1">Global Threat Map</h3>
            <p className="text-sm text-muted-foreground">
              Real-time proxy attack monitoring
            </p>
          </div>
          <div className="text-right">
            <p className="text-3xl font-bold text-accent animate-pulse-slow">
              {activeThreats}
            </p>
            <p className="text-xs text-muted-foreground">Active Threats</p>
          </div>
        </div>

        <div className="aspect-video rounded-lg bg-muted/20 flex items-center justify-center relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-accent/10" />
          <Globe className="h-32 w-32 text-primary/20 animate-pulse-slow" />
          
          {/* Simulated threat indicators */}
          <div className="absolute top-1/4 left-1/3 h-3 w-3 rounded-full bg-accent animate-ping" />
          <div className="absolute top-1/2 right-1/4 h-3 w-3 rounded-full bg-warning animate-ping delay-75" />
          <div className="absolute bottom-1/3 left-1/2 h-3 w-3 rounded-full bg-destructive animate-ping delay-150" />
          
          <div className="absolute inset-0 flex items-center justify-center">
            <p className="text-sm text-muted-foreground bg-background/80 px-4 py-2 rounded-lg backdrop-blur">
              Interactive map visualization - Coming soon
            </p>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4 mt-6">
          <div className="text-center">
            <p className="text-2xl font-bold text-accent">127</p>
            <p className="text-xs text-muted-foreground">High Priority</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-warning">89</p>
            <p className="text-xs text-muted-foreground">Medium Priority</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-success">31</p>
            <p className="text-xs text-muted-foreground">Low Priority</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ThreatMap;
