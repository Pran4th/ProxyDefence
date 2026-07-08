export interface GeoJsonGeometry {
  type: "Point" | "MultiPoint" | "LineString" | "MultiLineString" | "Polygon" | "MultiPolygon" | "GeometryCollection";
  coordinates: number[] | number[][] | number[][][] | number[][][][];
}

export interface GeoJsonFeature {
  type: "Feature";
  geometry: GeoJsonGeometry | null;
  properties: Record<string, unknown>;
  id?: string | number;
}

export interface GeoJsonFeatureCollection {
  type: "FeatureCollection";
  features: GeoJsonFeature[];
}

export interface MapLayerStyle {
  color: string;
  weight?: number;
  opacity?: number;
  fillColor?: string;
  fillOpacity?: number;
  radius?: number;
}

export interface EnergyMapLayer {
  id: string;
  name: string;
  entityType: string;
  visible: boolean;
  style: MapLayerStyle;
  data: GeoJsonFeatureCollection;
}

export interface MapViewport {
  center: [number, number];
  zoom: number;
  bounds?: [[number, number], [number, number]];
}

export interface MapLayerConfig {
  ports: MapLayerStyle;
  oil_fields: MapLayerStyle;
  gas_fields: MapLayerStyle;
  pipelines: MapLayerStyle;
  refineries: MapLayerStyle;
  power_plants: MapLayerStyle;
  storage_facilities: MapLayerStyle;
  strategic_petroleum_reserves: MapLayerStyle;
  import_corridors: MapLayerStyle;
  shipping_routes: MapLayerStyle;
  suppliers: MapLayerStyle;
  locations: MapLayerStyle;
  chokepoints: MapLayerStyle;
  events: MapLayerStyle;
}

export const DEFAULT_MAP_LAYER_STYLES: MapLayerConfig = {
  ports: { color: "#2563eb", weight: 2, opacity: 0.8, fillColor: "#3b82f6", fillOpacity: 0.6, radius: 8 },
  oil_fields: { color: "#7c3aed", weight: 2, opacity: 0.8, fillColor: "#8b5cf6", fillOpacity: 0.5, radius: 10 },
  gas_fields: { color: "#06b6d4", weight: 2, opacity: 0.8, fillColor: "#22d3ee", fillOpacity: 0.5, radius: 10 },
  pipelines: { color: "#f59e0b", weight: 3, opacity: 0.9, fillColor: "#fbbf24", fillOpacity: 0.4 },
  refineries: { color: "#ef4444", weight: 2, opacity: 0.8, fillColor: "#f87171", fillOpacity: 0.6, radius: 9 },
  power_plants: { color: "#10b981", weight: 2, opacity: 0.8, fillColor: "#34d399", fillOpacity: 0.5, radius: 7 },
  storage_facilities: { color: "#f97316", weight: 2, opacity: 0.8, fillColor: "#fb923c", fillOpacity: 0.5, radius: 6 },
  strategic_petroleum_reserves: { color: "#dc2626", weight: 2, opacity: 0.9, fillColor: "#ef4444", fillOpacity: 0.7, radius: 12 },
  import_corridors: { color: "#8b5cf6", weight: 2, opacity: 0.6, fillColor: "#a78bfa", fillOpacity: 0.3 },
  shipping_routes: { color: "#06b6d4", weight: 1.5, opacity: 0.5, fillColor: "#22d3ee", fillOpacity: 0.2 },
  suppliers: { color: "#14b8a6", weight: 2, opacity: 0.8, fillColor: "#2dd4bf", fillOpacity: 0.5, radius: 5 },
  locations: { color: "#6b7280", weight: 1, opacity: 0.5, fillColor: "#9ca3af", fillOpacity: 0.3 },
  chokepoints: { color: "#ef4444", weight: 2, opacity: 0.9, fillColor: "#fca5a5", fillOpacity: 0.6, radius: 6 },
  events: { color: "#dc2626", weight: 1, opacity: 0.7, fillColor: "#fca5a5", fillOpacity: 0.4, radius: 5 },
};
