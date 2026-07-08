import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Map, Layers, Anchor, Droplets, Factory, Pipette, Zap, Warehouse, Building2, Ship, Waypoints, Fuel, Filter } from "lucide-react";

import AppShell from "@/components/AppShell";
import { fetchEntities } from "@/lib/api-energy";
import { Button } from "@/components/ui/button";
import type { Port, OilField, Pipeline, Refinery, PowerPlant, StorageFacility, StrategicPetroleumReserve, ShippingRoute, ImportCorridor, GasField, Location } from "@/types/energy";

type AssetEntry = {
  type: string;
  name: string;
  lat: number;
  lng: number;
  uuid: string;
  criticality?: string;
  importance?: number;
  extra?: Record<string, unknown>;
};

const assetConfig: Record<string, { label: string; color: string; icon: React.ComponentType<any> }> = {
  ports: { label: "Ports", color: "#2563eb", icon: Anchor },
  oil_fields: { label: "Oil Fields", color: "#7c3aed", icon: Droplets },
  gas_fields: { label: "Gas Fields", color: "#06b6d4", icon: Fuel },
  pipelines: { label: "Pipelines", color: "#f59e0b", icon: Pipette },
  refineries: { label: "Refineries", color: "#ef4444", icon: Factory },
  power_plants: { label: "Power Plants", color: "#10b981", icon: Zap },
  storage_facilities: { label: "Storage Facilities", color: "#f97316", icon: Warehouse },
  strategic_petroleum_reserves: { label: "SPRs", color: "#dc2626", icon: Building2 },
  shipping_routes: { label: "Shipping Routes", color: "#06b6d4", icon: Ship },
  import_corridors: { label: "Import Corridors", color: "#8b5cf6", icon: Waypoints },
};

const TABLE_LIST = [
  "ports", "oil_fields", "gas_fields", "pipelines", "refineries",
  "power_plants", "storage_facilities", "strategic_petroleum_reserves",
  "shipping_routes", "import_corridors",
];

const toLng = (lng: number) => ((lng + 180) / 360) * 1000;
const toLat = (lat: number) => ((90 - lat) / 180) * 500;

const EnergyMap = () => {
  const navigate = useNavigate();
  const [assets, setAssets] = useState<AssetEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeLayers, setActiveLayers] = useState<Record<string, boolean>>(
    Object.fromEntries(TABLE_LIST.map((t) => [t, true]))
  );
  const [selectedAsset, setSelectedAsset] = useState<AssetEntry | null>(null);

  useEffect(() => {
    let cancelled = false;
    const loadAll = async () => {
      const all: AssetEntry[] = [];
      for (const table of TABLE_LIST) {
        try {
          const resp = await fetchEntities<any>(table, { limit: 500 });
          const items = resp.items || [];
          for (const item of items) {
            if (item.latitude != null && item.longitude != null) {
              all.push({
                type: table,
                name: item.name || "Unknown",
                lat: Number(item.latitude),
                lng: Number(item.longitude),
                uuid: item.uuid || "",
                criticality: item.criticality,
                importance: item.importance,
                extra: item,
              });
            }
          }
        } catch {
          // table may not be available
        }
      }
      if (!cancelled) {
        setAssets(all);
        setLoading(false);
      }
    };
    loadAll();
    return () => { cancelled = true; };
  }, []);

  const filteredAssets = assets.filter((a) => activeLayers[a.type]);

  const toggleLayer = (type: string) => {
    setActiveLayers((prev) => ({ ...prev, [type]: !prev[type] }));
  };

  return (
    <AppShell title="Energy Asset Map" subtitle="Geospatial visualization of global energy infrastructure">
      <div className="flex flex-col gap-4 lg:flex-row">
        <div className="w-full lg:w-64 shrink-0">
          <div className="rounded-2xl border border-border bg-card p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-medium">
              <Layers className="h-4 w-4 text-primary" />
              Layers
            </div>
            <div className="space-y-1.5">
              {TABLE_LIST.map((type) => {
                const cfg = assetConfig[type];
                const Icon = cfg?.icon || Map;
                return (
                  <button
                    key={type}
                    onClick={() => toggleLayer(type)}
                    className={`flex w-full items-center gap-2 rounded-xl px-3 py-2 text-xs transition-colors ${
                      activeLayers[type]
                        ? "bg-primary/10 text-foreground"
                        : "text-muted-foreground hover:bg-muted"
                    }`}
                  >
                    <div className="grid h-6 w-6 place-items-center rounded-md" style={{ backgroundColor: `${cfg?.color}20` }}>
                      <Icon className="h-3 w-3" style={{ color: cfg?.color }} />
                    </div>
                    <span className="flex-1 text-left">{cfg?.label || type}</span>
                    <span className="text-muted-foreground">
                      {assets.filter((a) => a.type === type).length}
                    </span>
                  </button>
                );
              })}
            </div>

            <div className="mt-4 border-t border-border pt-3">
              <p className="text-xs text-muted-foreground">
                {filteredAssets.length} / {assets.length} assets visible
              </p>
            </div>
          </div>
        </div>

        <div className="flex-1">
          <div className="relative overflow-hidden rounded-2xl border border-border bg-[#0a1628]">
            {loading ? (
              <div className="flex h-[600px] items-center justify-center text-sm text-muted-foreground">
                Loading energy assets...
              </div>
            ) : (
              <svg viewBox="0 0 1000 500" className="h-auto w-full" style={{ minHeight: "500px" }}>
                <rect x="0" y="0" width="1000" height="500" fill="#0a1628" />
                {Array.from({ length: 18 }).map((_, i) => (
                  <line key={`h${i}`} x1="0" y1={i * 27.8} x2="1000" y2={i * 27.8} stroke="#1a2744" strokeWidth="0.5" />
                ))}
                {Array.from({ length: 36 }).map((_, i) => (
                  <line key={`v${i}`} x1={i * 27.8} y1="0" x2={i * 27.8} y2="500" stroke="#1a2744" strokeWidth="0.5" />
                ))}

                {filteredAssets.map((asset, idx) => {
                  const x = toLng(asset.lng);
                  const y = toLat(asset.lat);
                  const cfg = assetConfig[asset.type];
                  const r = Math.max(3, Math.min(8, (asset.importance || 50) / 12));
                  return (
                    <g key={`${asset.type}-${idx}`} className="cursor-pointer" onClick={() => setSelectedAsset(asset)}>
                      <circle cx={x} cy={y} r={r + 2} fill="none" stroke={cfg?.color || "#666"} strokeWidth="0.5" opacity="0.4" />
                      <circle cx={x} cy={y} r={r} fill={cfg?.color || "#666"} opacity="0.8" className="hover:opacity-100" />
                    </g>
                  );
                })}
              </svg>
            )}

            {selectedAsset && (
              <div className="absolute bottom-4 left-4 right-4 rounded-2xl border border-border bg-card p-4 shadow-lg lg:left-auto lg:right-4 lg:w-80">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    {(() => {
                      const Icon = assetConfig[selectedAsset.type]?.icon || Map;
                      return <Icon className="h-4 w-4 text-primary" />;
                    })()}
                    <p className="font-semibold">{selectedAsset.name}</p>
                  </div>
                  <button onClick={() => setSelectedAsset(null)} className="text-muted-foreground hover:text-foreground text-sm">&times;</button>
                </div>
                <p className="text-xs text-muted-foreground capitalize mb-2">
                  {selectedAsset.type.replace(/_/g, " ")} · {selectedAsset.lat.toFixed(2)}, {selectedAsset.lng.toFixed(2)}
                </p>
                <div className="flex flex-wrap gap-1 mb-2">
                  {selectedAsset.criticality && (
                    <span className="rounded-full border px-2 py-0.5 text-xs capitalize">{selectedAsset.criticality}</span>
                  )}
                  {selectedAsset.importance && (
                    <span className="rounded-full border px-2 py-0.5 text-xs">Importance: {selectedAsset.importance}</span>
                  )}
                </div>
                <Button size="sm" variant="secondary" className="w-full" onClick={() => {
                  navigate(`/energy/assets/${selectedAsset.type}/${selectedAsset.uuid}`);
                }}>
                  View Details
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
};

export default EnergyMap;
