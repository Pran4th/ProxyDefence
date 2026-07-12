import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { Map as MapIcon, Layers, Anchor, Droplets, Factory, Pipette, Zap, Warehouse, Building2, Ship, Waypoints, Fuel, AlertTriangle } from "lucide-react";

import AppShell from "@/components/AppShell";
import { fetchEntities } from "@/lib/api-energy";
import { fetchRunImpacts } from "@/lib/api";
import { fetchAisPositions, fetchCorridorRisk } from "@/lib/api-intelligence";
import { Button } from "@/components/ui/button";

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
  chokepoints: { label: "Chokepoints", color: "#ff2d55", icon: AlertTriangle },
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
  "chokepoints", "ports", "oil_fields", "gas_fields", "pipelines", "refineries",
  "power_plants", "storage_facilities", "strategic_petroleum_reserves",
  "shipping_routes", "import_corridors",
];

// Free dark raster basemap (CARTO), no API key required.
const MAP_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    carto: {
      type: "raster",
      tiles: [
        "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
        "https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
        "https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
      ],
      tileSize: 256,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
    },
  },
  layers: [{ id: "carto", type: "raster", source: "carto" }],
};

const colorMatchExpression = (): maplibregl.ExpressionSpecification => {
  const expr: any[] = ["match", ["get", "type"]];
  for (const [type, cfg] of Object.entries(assetConfig)) {
    expr.push(type, cfg.color);
  }
  expr.push("#94a3b8");
  return expr as maplibregl.ExpressionSpecification;
};

const toGeoJSON = (assets: AssetEntry[]): GeoJSON.FeatureCollection => ({
  type: "FeatureCollection",
  features: assets.map((a, idx) => ({
    type: "Feature",
    id: idx,
    geometry: { type: "Point", coordinates: [a.lng, a.lat] },
    properties: {
      idx,
      type: a.type,
      name: a.name,
      importance: a.importance ?? 50,
      isChokepoint: a.type === "chokepoints" ? 1 : 0,
    },
  })),
});

const EnergyMap = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const runUuid = searchParams.get("run_uuid");
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [assets, setAssets] = useState<AssetEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeLayers, setActiveLayers] = useState<Record<string, boolean>>(
    Object.fromEntries(TABLE_LIST.map((t) => [t, true]))
  );
  const [selectedAsset, setSelectedAsset] = useState<AssetEntry | null>(null);

  // Live corridor risk (drives corridor line color) and real AIS vessels
  const { data: corridorData } = useQuery({
    queryKey: ["map-corridors"],
    queryFn: fetchCorridorRisk,
    refetchInterval: 30000,
  });
  const { data: aisData } = useQuery({
    queryKey: ["map-ais"],
    queryFn: fetchAisPositions,
    refetchInterval: 30000,
  });
  const { data: runImpacts } = useQuery({
    queryKey: ["map-run-impacts", runUuid],
    queryFn: () => fetchRunImpacts(runUuid!),
    enabled: !!runUuid,
  });

  // load assets from energy-service
  useEffect(() => {
    let cancelled = false;
    const loadAll = async () => {
      const all: AssetEntry[] = [];
      try {
        const CHOKEPOINT_TYPES = new Set(["strait", "canal", "strategic_area"]);
        const locs = await fetchEntities<any>("locations", { limit: 500 });
        for (const item of locs.items || []) {
          if (CHOKEPOINT_TYPES.has(item.location_type) && item.latitude != null && item.longitude != null) {
            all.push({
              type: "chokepoints",
              name: item.name || "Chokepoint",
              lat: Number(item.latitude),
              lng: Number(item.longitude),
              uuid: item.uuid || "",
              criticality: "critical",
              importance: 100,
              extra: item,
            });
          }
        }
      } catch { /* locations unavailable */ }

      for (const table of TABLE_LIST) {
        if (table === "chokepoints") continue;
        try {
          const resp = await fetchEntities<any>(table, { limit: 500 });
          for (const item of resp.items || []) {
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
        } catch { /* table may not be available */ }
      }
      if (!cancelled) {
        setAssets(all);
        setLoading(false);
      }
    };
    loadAll();
    return () => { cancelled = true; };
  }, []);

  // init map once
  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: MAP_STYLE,
      center: [65, 18],   // Arabian Sea — India's import corridors in frame
      zoom: 3,
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

    map.on("load", () => {
      const empty: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

      // Corridor polylines, color-interpolated by live disruption probability
      map.addSource("corridors", { type: "geojson", data: empty });
      map.addLayer({
        id: "corridor-lines-glow",
        type: "line",
        source: "corridors",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-width": 10,
          "line-blur": 6,
          "line-opacity": 0.35,
          "line-color": [
            "interpolate", ["linear"], ["get", "probability"],
            0, "#22c55e", 0.45, "#f59e0b", 0.7, "#ef4444",
          ],
        },
      });
      map.addLayer({
        id: "corridor-lines",
        type: "line",
        source: "corridors",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-width": ["interpolate", ["linear"], ["get", "indiaShare"], 0, 1.5, 50, 5],
          "line-opacity": 0.9,
          "line-color": [
            "interpolate", ["linear"], ["get", "probability"],
            0, "#22c55e", 0.45, "#f59e0b", 0.7, "#ef4444",
          ],
          "line-dasharray": [2, 1],
        },
      });
      map.addLayer({
        id: "corridor-labels",
        type: "symbol",
        source: "corridors",
        layout: {
          "symbol-placement": "line-center",
          "text-field": ["concat", ["get", "name"], "  ", ["get", "probabilityLabel"]],
          "text-size": 10,
        },
        paint: {
          "text-color": "#e2e8f0",
          "text-halo-color": "#0a1628",
          "text-halo-width": 1.5,
        },
      });

      // Real AIS vessel positions
      map.addSource("vessels", { type: "geojson", data: empty });
      map.addLayer({
        id: "vessel-points",
        type: "circle",
        source: "vessels",
        paint: {
          "circle-radius": 3.5,
          "circle-color": "#22d3ee",
          "circle-opacity": 0.95,
          "circle-stroke-width": 1,
          "circle-stroke-color": "#0a1628",
        },
      });
      map.addLayer({
        id: "vessel-labels",
        type: "symbol",
        source: "vessels",
        minzoom: 6,
        layout: {
          "text-field": ["get", "name"],
          "text-size": 9,
          "text-offset": [0, 1],
          "text-anchor": "top",
        },
        paint: { "text-color": "#67e8f9", "text-halo-color": "#0a1628", "text-halo-width": 1 },
      });

      map.addSource("assets", { type: "geojson", data: toGeoJSON([]) });

      map.addLayer({
        id: "asset-glow",
        type: "circle",
        source: "assets",
        paint: {
          "circle-radius": ["+", ["interpolate", ["linear"], ["get", "importance"], 0, 4, 100, 11], 4],
          "circle-color": colorMatchExpression(),
          "circle-opacity": 0.18,
        },
      });
      map.addLayer({
        id: "asset-points",
        type: "circle",
        source: "assets",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["get", "importance"], 0, 3, 100, 8],
          "circle-color": colorMatchExpression(),
          "circle-opacity": 0.9,
          "circle-stroke-width": ["case", ["==", ["get", "isChokepoint"], 1], 2, 0.5],
          "circle-stroke-color": ["case", ["==", ["get", "isChokepoint"], 1], "#ffffff", "#0a1628"],
        },
      });
      map.addLayer({
        id: "asset-labels",
        type: "symbol",
        source: "assets",
        minzoom: 4.5,
        layout: {
          "text-field": ["get", "name"],
          "text-size": 10,
          "text-offset": [0, 1.2],
          "text-anchor": "top",
        },
        paint: {
          "text-color": "#cbd5e1",
          "text-halo-color": "#0a1628",
          "text-halo-width": 1,
        },
      });

      map.on("mouseenter", "asset-points", () => { map.getCanvas().style.cursor = "pointer"; });
      map.on("mouseleave", "asset-points", () => { map.getCanvas().style.cursor = ""; });
      setMapReady(true);
    });

    mapRef.current = map;
    return () => { map.remove(); mapRef.current = null; };
  }, []);

  const filteredAssets = useMemo(
    () => assets.filter((a) => activeLayers[a.type]),
    [assets, activeLayers],
  );

  // push data + click handler whenever the filtered set changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    const source = map.getSource("assets") as maplibregl.GeoJSONSource | undefined;
    if (source) source.setData(toGeoJSON(filteredAssets));

    const onClick = (e: maplibregl.MapLayerMouseEvent) => {
      const f = e.features?.[0];
      if (f && typeof f.properties?.idx === "number") {
        setSelectedAsset(filteredAssets[f.properties.idx] ?? null);
      }
    };
    map.on("click", "asset-points", onClick);
    return () => { map.off("click", "asset-points", onClick); };
  }, [filteredAssets, mapReady]);

  // Push live corridor risk into the corridor line source
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady || !corridorData) return;
    const source = map.getSource("corridors") as maplibregl.GeoJSONSource | undefined;
    if (!source) return;
    source.setData({
      type: "FeatureCollection",
      features: corridorData.corridors.map((c) => ({
        type: "Feature",
        geometry: { type: "LineString", coordinates: c.polyline },
        properties: {
          name: c.name.split("(")[0].trim(),
          probability: c.probability_30d,
          probabilityLabel: `${Math.round(c.probability_30d * 100)}%`,
          indiaShare: c.india_import_share_pct,
        },
      })),
    });
  }, [corridorData, mapReady]);

  // Push real AIS vessels into the vessel source
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady || !aisData) return;
    const source = map.getSource("vessels") as maplibregl.GeoJSONSource | undefined;
    if (!source) return;
    source.setData({
      type: "FeatureCollection",
      features: aisData.items.map((v) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [v.longitude, v.latitude] },
        properties: { name: v.name, chokepoint: v.chokepoint },
      })),
    });
  }, [aisData, mapReady]);

  // Scenario mode: pulse chokepoints while a run's impact overlay is active
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady || !runUuid) return;
    let up = true;
    const pulse = setInterval(() => {
      if (!map.getLayer("asset-points")) return;
      up = !up;
      map.setPaintProperty("asset-points", "circle-stroke-width", [
        "case", ["==", ["get", "isChokepoint"], 1], up ? 6 : 2, 0.5,
      ]);
    }, 600);
    return () => {
      clearInterval(pulse);
      if (map.getLayer("asset-points")) {
        map.setPaintProperty("asset-points", "circle-stroke-width", [
          "case", ["==", ["get", "isChokepoint"], 1], 2, 0.5,
        ]);
      }
    };
  }, [runUuid, mapReady]);

  const toggleLayer = (type: string) => {
    setActiveLayers((prev) => ({ ...prev, [type]: !prev[type] }));
  };

  return (
    <AppShell title="Energy Supply Map" subtitle="India's import corridors, live corridor risk, and real AIS tanker traffic">
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
                const Icon = cfg?.icon || MapIcon;
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

            <div className="mt-4 space-y-1.5 border-t border-border pt-3">
              <p className="text-xs text-muted-foreground">
                {filteredAssets.length} / {assets.length} assets visible
              </p>
              <p className="text-xs text-muted-foreground">
                <span className="mr-1 inline-block h-2 w-2 rounded-full bg-[#22d3ee]" />
                {aisData?.total ?? 0} live AIS vessels
                {aisData?.snapshot_at ? ` · ${aisData.snapshot_at.slice(0, 16)}` : ""}
              </p>
              <p className="text-xs text-muted-foreground">
                Corridor lines colored by live 30-day disruption probability
              </p>
            </div>
          </div>
        </div>

        <div className="flex-1">
          <div className="relative overflow-hidden rounded-2xl border border-border bg-[#0a1628]">
            <div ref={mapContainer} className="h-[600px] w-full" />

            {loading && (
              <div className="absolute inset-0 z-10 flex items-center justify-center bg-[#0a1628]/70 text-sm text-muted-foreground">
                Loading energy assets...
              </div>
            )}

            {runUuid && (
              <div className="absolute left-4 top-4 z-10 max-w-sm rounded-2xl border border-destructive/50 bg-card/95 p-3 shadow-lg">
                <p className="text-xs font-semibold text-destructive">
                  Scenario impact overlay active
                </p>
                {runImpacts?.aggregate_impacts ? (
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    Supply gap{" "}
                    {((runImpacts.aggregate_impacts.max_supply_gap_bpd ??
                      runImpacts.aggregate_impacts.supply_gap_bpd ?? 0) / 1e6).toFixed(1)}
                    M bpd · GDP impact {runImpacts.aggregate_impacts.gdp_impact_pct ?? 0}% ·{" "}
                    {runImpacts.aggregate_impacts.idle_refineries ?? 0} refineries idle
                  </p>
                ) : (
                  <p className="mt-1 text-[11px] text-muted-foreground">Loading run impacts…</p>
                )}
              </div>
            )}

            {selectedAsset && (
              <div className="absolute bottom-4 left-4 right-4 z-10 rounded-2xl border border-border bg-card p-4 shadow-lg lg:left-auto lg:right-4 lg:w-80">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    {(() => {
                      const Icon = assetConfig[selectedAsset.type]?.icon || MapIcon;
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
                {selectedAsset.type !== "chokepoints" && (
                  <Button size="sm" variant="secondary" className="w-full" onClick={() => {
                    navigate(`/energy/assets/${selectedAsset.type}/${selectedAsset.uuid}`);
                  }}>
                    View Details
                  </Button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
};

export default EnergyMap;
