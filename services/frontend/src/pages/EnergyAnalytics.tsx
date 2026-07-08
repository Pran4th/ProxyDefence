import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Zap, Globe2, Factory, Droplets, AlertTriangle, Ship, Anchor, BarChart3 } from "lucide-react";

import AppShell from "@/components/AppShell";
import MetricCard from "@/components/MetricCard";
import { fetchEntities } from "@/lib/api-energy";
import type { Location, Port, OilField, Pipeline, Refinery, Organization, Commodity, ShippingRoute } from "@/types/energy";

const TABLE_LIST = [
  "locations", "organizations", "commodities", "ports", "oil_fields",
  "gas_fields", "pipelines", "refineries", "power_plants",
  "storage_facilities", "strategic_petroleum_reserves",
  "import_corridors", "shipping_routes", "suppliers",
];

const EnergyAnalytics = () => {
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const loadCounts = async () => {
      const result: Record<string, number> = {};
      for (const table of TABLE_LIST) {
        try {
          const resp = await fetchEntities<any>(table, { limit: 1 });
          result[table] = resp.total || 0;
        } catch { result[table] = 0; }
      }
      if (!cancelled) { setCounts(result); setLoading(false); }
    };
    loadCounts();
    return () => { cancelled = true; };
  }, []);

  const totalAssets = Object.values(counts).reduce((a, b) => a + b, 0);

  return (
    <AppShell title="Energy Analytics" subtitle="Infrastructure catalog metrics and energy intelligence insights">
      <div className="grid gap-5 lg:grid-cols-4">
        <MetricCard title="Total Assets" value={loading ? "..." : totalAssets} icon={Zap} trend="neutral" trendValue="Energy infrastructure catalog" />
        <MetricCard title="Countries" value={loading ? "..." : counts.locations || 0} icon={Globe2} trend="neutral" trendValue="Tracked locations" />
        <MetricCard title="Organizations" value={loading ? "..." : counts.organizations || 0} icon={Factory} trend="neutral" trendValue="Energy companies" />
        <MetricCard title="Commodities" value={loading ? "..." : counts.commodities || 0} icon={Droplets} trend="neutral" trendValue="Traded energy products" />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="rounded-3xl border border-border bg-card p-6">
          <h2 className="mb-5 text-xl font-bold">Infrastructure Inventory</h2>
          <div className="space-y-3">
            {[
              ["Ports", counts.ports || 0, "ports", Anchor, "#2563eb"],
              ["Oil Fields", counts.oil_fields || 0, "oil_fields", Droplets, "#7c3aed"],
              ["Gas Fields", counts.gas_fields || 0, "gas_fields", Fuel, "#06b6d4"],
              ["Pipelines", counts.pipelines || 0, "pipelines", Droplets, "#f59e0b"],
              ["Refineries", counts.refineries || 0, "refineries", Factory, "#ef4444"],
              ["Power Plants", counts.power_plants || 0, "power_plants", Zap, "#10b981"],
              ["Storage Facilities", counts.storage_facilities || 0, "storage_facilities", null, "#f97316"],
              ["SPRs", counts.strategic_petroleum_reserves || 0, "strategic_petroleum_reserves", null, "#dc2626"],
              ["Import Corridors", counts.import_corridors || 0, "import_corridors", null, "#8b5cf6"],
              ["Shipping Routes", counts.shipping_routes || 0, "shipping_routes", Ship, "#06b6d4"],
              ["Suppliers", counts.suppliers || 0, "suppliers", null, "#14b8a6"],
            ].map(([label, count, table, Icon, color]) => (
              <Link key={table as string} to={`/energy/assets/${table}`} className="flex items-center gap-3 rounded-xl border border-border bg-background p-3 transition-colors hover:border-primary/50">
                {Icon && (
                  <div className="grid h-8 w-8 place-items-center rounded-lg" style={{ backgroundColor: `${color}20` }}>
                    {(Icon as any) && <Icon className="h-4 w-4" style={{ color }} />}
                  </div>
                )}
                <span className="flex-1 text-sm font-medium">{label as string}</span>
                <span className="rounded-full bg-primary/10 px-3 py-1 text-sm font-semibold">{count as number}</span>
              </Link>
            ))}
          </div>
        </div>

        <div className="space-y-6">
          <div className="rounded-3xl border border-border bg-card p-6">
            <h2 className="mb-5 text-xl font-bold">Asset Distribution</h2>
            <div className="space-y-4">
              {[
                { label: "Ports", count: counts.ports || 0, color: "#2563eb" },
                { label: "Oil & Gas Fields", count: (counts.oil_fields || 0) + (counts.gas_fields || 0), color: "#7c3aed" },
                { label: "Pipelines", count: counts.pipelines || 0, color: "#f59e0b" },
                { label: "Refineries", count: counts.refineries || 0, color: "#ef4444" },
                { label: "Power Plants", count: counts.power_plants || 0, color: "#10b981" },
                { label: "Storage & SPRs", count: (counts.storage_facilities || 0) + (counts.strategic_petroleum_reserves || 0), color: "#f97316" },
                { label: "Routes & Corridors", count: (counts.shipping_routes || 0) + (counts.import_corridors || 0), color: "#06b6d4" },
              ].map((item) => {
                const pct = totalAssets > 0 ? ((item.count / totalAssets) * 100).toFixed(1) : "0";
                return (
                  <div key={item.label}>
                    <div className="mb-1 flex justify-between text-sm">
                      <span>{item.label}</span>
                      <span className="text-muted-foreground">{item.count} ({pct}%)</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-muted">
                      <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: item.color }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="rounded-3xl border border-border bg-card p-6">
            <h2 className="mb-4 text-xl font-bold">Quick Links</h2>
            <div className="space-y-2">
              <Link to="/energy/map" className="flex items-center gap-2 rounded-xl border border-border bg-background p-3 text-sm transition-colors hover:border-primary/50">
                <Map className="h-4 w-4 text-primary" />
                Energy Asset Map
              </Link>
              <Link to="/graph" className="flex items-center gap-2 rounded-xl border border-border bg-background p-3 text-sm transition-colors hover:border-primary/50">
                <BarChart3 className="h-4 w-4 text-primary" />
                Knowledge Graph (merged with energy)
              </Link>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
};

const Fuel = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 22V12a9 9 0 0 1 18 0v10" /><path d="M3 12h18" /><path d="M12 2v4" /><path d="M8 12v6" /><path d="M16 12v6" />
  </svg>
);

const Map = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6" /><line x1="8" y1="2" x2="8" y2="18" /><line x1="16" y1="6" x2="16" y2="22" />
  </svg>
);

export default EnergyAnalytics;
