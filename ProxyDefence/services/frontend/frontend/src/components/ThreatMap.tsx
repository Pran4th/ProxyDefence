import { useState, useEffect } from "react";
import { Globe, ShieldAlert, MapPin } from "lucide-react";

// Mock coordinates for major conflict zones (approximate)
const conflictZones = [
  { id: 1, x: "30%", y: "40%", name: "Eastern Europe", severity: "critical" }, // Ukraine/Russia
  { id: 2, x: "55%", y: "50%", name: "Middle East", severity: "high" }, // Gaza/Israel/Syria
  { id: 3, x: "75%", y: "45%", name: "East Asia", severity: "medium" }, // Taiwan/SCS
  { id: 4, x: "45%", y: "60%", name: "Central Africa", severity: "medium" }, // Sudan/DRC
];

const ThreatMap = () => {
  const [activeThreats, setActiveThreats] = useState(247);
  const [selectedZone, setSelectedZone] = useState<string | null>(null);

  useEffect(() => {
    // Simulate live threat counter updates
    const interval = setInterval(() => {
      setActiveThreats((prev) => {
        const change = Math.floor(Math.random() * 5) - 2; // -2 to +2
        return Math.max(100, prev + change);
      });
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="relative rounded-lg border border-border bg-card p-6 shadow-elevation overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-accent/5" />
      
      <div className="relative z-10">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-lg font-semibold mb-1 flex items-center gap-2">
              <Globe className="h-5 w-5 text-primary" />
              Global Threat Map
            </h3>
            <p className="text-sm text-muted-foreground">
              Real-time conflict zone monitoring
            </p>
          </div>
          <div className="text-right">
            <p className="text-3xl font-bold text-accent animate-pulse-slow">
              {activeThreats}
            </p>
            <p className="text-xs text-muted-foreground">Active Incidents</p>
          </div>
        </div>

        {/* Simplified Map Visualization */}
        <div className="aspect-[2/1] rounded-lg bg-[#0f172a] relative overflow-hidden border border-border/50 group">
          {/* World Map Background (Abstract SVG or Image could go here) */}
          <div className="absolute inset-0 opacity-30 bg-[url('https://upload.wikimedia.org/wikipedia/commons/8/80/World_map_-_low_resolution.svg')] bg-cover bg-center grayscale contrast-125" />
          
          {/* Radar Sweep Animation */}
          <div className="absolute inset-0 bg-[conic-gradient(from_0deg,transparent_0deg,transparent_270deg,rgba(34,197,94,0.1)_360deg)] animate-[spin_4s_linear_infinite] rounded-full scale-[2] origin-center opacity-30 pointer-events-none" />

          {/* Interactive Conflict Zones */}
          {conflictZones.map((zone) => (
            <div
              key={zone.id}
              className="absolute group/marker cursor-pointer"
              style={{ left: zone.x, top: zone.y }}
              onMouseEnter={() => setSelectedZone(zone.name)}
              onMouseLeave={() => setSelectedZone(null)}
            >
              {/* Ping Animation */}
              <div className={`absolute -inset-4 rounded-full animate-ping opacity-75 ${
                zone.severity === 'critical' ? 'bg-destructive' : 
                zone.severity === 'high' ? 'bg-accent' : 'bg-warning'
              }`} />
              
              {/* Marker Dot */}
              <div className={`relative h-3 w-3 rounded-full shadow-[0_0_10px_currentColor] ${
                zone.severity === 'critical' ? 'bg-destructive text-destructive' : 
                zone.severity === 'high' ? 'bg-accent text-accent' : 'bg-warning text-warning'
              }`} />

              {/* Tooltip */}
              <div className="absolute bottom-6 left-1/2 -translate-x-1/2 opacity-0 group-hover/marker:opacity-100 transition-opacity whitespace-nowrap bg-background/90 backdrop-blur border border-border px-3 py-1 rounded text-xs z-20 pointer-events-none">
                <span className="font-bold">{zone.name}</span>
                <span className="block text-[10px] text-muted-foreground uppercase">{zone.severity} Activity</span>
              </div>
            </div>
          ))}

          {/* Overlay Grid */}
          <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.03)_1px,transparent_1px)] bg-[size:40px_40px] pointer-events-none" />
        </div>

        {/* Legend */}
        <div className="flex gap-6 mt-6 justify-center text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-destructive animate-pulse" />
            <span>Critical Conflict</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-accent" />
            <span>High Tension</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-warning" />
            <span>Elevated Risk</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ThreatMap;
