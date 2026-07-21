import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Network, RefreshCw, Search, ZoomIn, ZoomOut } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import CytoscapeComponent from "react-cytoscapejs";

import AppShell from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, fetchNetworkGraph, type GraphNode, type NetworkGraphData } from "@/lib/api";
import { fetchNetworkGraph as fetchEnergyGraph } from "@/lib/api-energy";

type GraphEdge = {
  source?: string;
  target?: string;
  source_entity?: string;
  target_entity?: string;
  relationship?: string;
  relationship_type?: string;
  type?: string;
  confidence?: number;
  value?: number;
};

type GraphPayload = {
  nodes: (GraphNode & { country?: string | null })[];
  edges: GraphEdge[];
  node_count?: number;
  edge_count?: number;
};

// Real entity types from energy.entity_relationships (source_entity_type /
// target_entity_type) plus the intel graph's "Actor" bucket -- every value
// here is a type that genuinely appears in the data, not decorative.
const ENTITY_COLORS: Record<string, string> = {
  refinery: "#f59e0b",
  port: "#38bdf8",
  pipeline: "#a78bfa",
  oil_field: "#84cc16",
  gas_field: "#2dd4bf",
  storage_facility: "#fb923c",
  strategic_petroleum_reserve: "#ef4444",
  supplier: "#eab308",
  power_plant: "#f472b6",
  shipping_route: "#60a5fa",
  organization: "#c084fc",
  location: "#34d399",
  actor: "#94a3b8",
};
const DEFAULT_COLOR = "#6b7280";

function colorFor(entityType: string | undefined): string {
  if (!entityType) return DEFAULT_COLOR;
  return ENTITY_COLORS[entityType.toLowerCase()] ?? DEFAULT_COLOR;
}

function labelFor(entityType: string): string {
  return entityType
    .split("_")
    .map((w) => w[0]?.toUpperCase() + w.slice(1))
    .join(" ");
}

type TooltipState = {
  x: number;
  y: number;
  label: string;
  entityType: string;
  country: string | null;
  degree: number;
} | null;

const GraphExplorer = () => {
  const [searchParams] = useSearchParams();
  const cyRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [graph, setGraph] = useState<GraphPayload>({ nodes: [], edges: [] });
  const [entity, setEntity] = useState(() => searchParams.get("entity") ?? "");
  const [activeEntity, setActiveEntity] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(new Set());
  const [tooltip, setTooltip] = useState<TooltipState>(null);

  const loadNetwork = () => {
    setLoading(true);
    setError(null);
    setActiveEntity(null);

    Promise.all([
      fetchNetworkGraph(),
      fetchEnergyGraph(2000).catch(() => ({ relationships: [] })),
    ])
      .then(([intelData, energyData]) => {
        const merged: GraphPayload = {
          nodes: [...intelData.nodes],
          edges: [...intelData.edges],
        };
        const existingNodeIds = new Set(intelData.nodes.map((n) => n.id || n.label));
        const seenEdges = new Set<string>();
        merged.edges.forEach((e) => {
          const s = e.source || e.source_entity;
          const t = e.target || e.target_entity;
          if (s && t) seenEdges.add(`${s}|${t}`);
        });

        // entity_relationships only stores type:id pairs -- source_name/
        // source_country (and target_ equivalents) are resolved server-side in
        // relationships.py's get_network_graph by joining each entity to its
        // real catalog row + energy.locations. Country is baked directly into
        // the node label (not just a hover tooltip) since the whole point is
        // to see at a glance which country each node belongs to.
        const displayLabel = (name: string | null | undefined, country: string | null | undefined, fallback: string) => {
          if (!name) return fallback;
          if (country && country !== name) return `${name} (${country})`;
          return name;
        };

        for (const rel of (energyData.relationships || [])) {
          const sourceLabel = `${rel.source_entity_type}:${rel.source_entity_id}`;
          const targetLabel = `${rel.target_entity_type}:${rel.target_entity_id}`;
          if (seenEdges.has(`${sourceLabel}|${targetLabel}`)) continue;
          seenEdges.add(`${sourceLabel}|${targetLabel}`);

          if (!existingNodeIds.has(sourceLabel)) {
            merged.nodes.push({
              id: sourceLabel,
              label: displayLabel(rel.source_name, rel.source_country, sourceLabel),
              group: rel.source_entity_type,
              country: rel.source_country,
              val: 10,
            });
            existingNodeIds.add(sourceLabel);
          }
          if (!existingNodeIds.has(targetLabel)) {
            merged.nodes.push({
              id: targetLabel,
              label: displayLabel(rel.target_name, rel.target_country, targetLabel),
              group: rel.target_entity_type,
              country: rel.target_country,
              val: 10,
            });
            existingNodeIds.add(targetLabel);
          }

          merged.edges.push({
            source: sourceLabel,
            target: targetLabel,
            relationship_type: rel.relationship_type,
            confidence: rel.confidence,
            value: rel.confidence,
          });
        }

        setGraph(merged);
      })
      .catch(() => setError("Unable to load relationship network."))
      .finally(() => setLoading(false));
  };

  const loadEntityGraph = (entityName: string) => {
    setLoading(true);
    setError(null);
    setActiveEntity(entityName);

    api
      .get<GraphPayload>(`/graph/${encodeURIComponent(entityName)}`)
      .then((response) => setGraph(response.data))
      .catch(() => setError("Unable to load entity graph."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    const linkedEntity = searchParams.get("entity");
    if (linkedEntity) {
      loadEntityGraph(linkedEntity);
    } else {
      loadNetwork();
    }
    // Only meant to run once on mount against whatever ?entity= was present
    // when the page loaded -- not on every searchParams identity change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const { elements: allElements, typeCounts } = useMemo(() => {
    const nodes = new Map<string, { data: { id: string; label: string; entityType: string; country: string | null; degree: number } }>();
    const edges: { data: { id: string; source: string; target: string; label: string; confidence: number } }[] = [];
    const degree = new Map<string, number>();

    const ensureNode = (id: string, label: string, entityType: string | undefined, country?: string | null) => {
      if (!nodes.has(id)) {
        nodes.set(id, {
          data: { id, label, entityType: (entityType || "actor").toLowerCase(), country: country ?? null, degree: 0 },
        });
      }
    };

    graph.nodes.forEach((node) => {
      const id = node.id || node.label;
      if (!id) return;
      ensureNode(id, node.label || id, node.group, node.country);
    });

    graph.edges.forEach((edge, index) => {
      const source = edge.source || edge.source_entity;
      const target = edge.target || edge.target_entity;
      if (!source || !target || source === target) return;

      ensureNode(source, source, undefined);
      ensureNode(target, target, undefined);
      degree.set(source, (degree.get(source) || 0) + 1);
      degree.set(target, (degree.get(target) || 0) + 1);

      edges.push({
        data: {
          id: `${source}-${target}-${index}`,
          source,
          target,
          label: edge.relationship || edge.relationship_type || edge.type || "relationship",
          confidence: edge.confidence ?? edge.value ?? 0,
        },
      });
    });

    const counts: Record<string, number> = {};
    for (const [id, n] of nodes) {
      n.data.degree = degree.get(id) || 0;
      counts[n.data.entityType] = (counts[n.data.entityType] || 0) + 1;
    }

    return { elements: [...nodes.values(), ...edges], typeCounts: counts };
  }, [graph]);

  const graphElements = useMemo(() => {
    if (hiddenTypes.size === 0) return allElements;
    const visibleNodeIds = new Set(
      allElements
        .filter((el: any) => "entityType" in el.data && !hiddenTypes.has(el.data.entityType))
        .map((el: any) => el.data.id)
    );
    return allElements.filter((el: any) => {
      if ("entityType" in el.data) return visibleNodeIds.has(el.data.id);
      return visibleNodeIds.has(el.data.source) && visibleNodeIds.has(el.data.target);
    });
  }, [allElements, hiddenTypes]);

  const toggleType = (type: string) => {
    setHiddenTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  const handleSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedEntity = entity.trim();
    if (!trimmedEntity) return;
    loadEntityGraph(trimmedEntity);
  };

  const zoomBy = (amount: number) => {
    const cy = cyRef.current;
    if (!cy) return;

    cy.zoom({
      level: cy.zoom() * amount,
      renderedPosition: {
        x: cy.width() / 2,
        y: cy.height() / 2,
      },
    });
  };

  const resetView = () => {
    cyRef.current?.fit(undefined, 48);
  };

  return (
    <AppShell
      title="Graph Explorer"
      subtitle="Explore entity relationships across the intelligence graph. Zoom, pan, and click nodes to open entity profiles."
    >
      <div className="rounded-[1.75rem] border border-border bg-card p-6 shadow-elevation">
        <div className="mb-5 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Network className="h-4 w-4 text-primary" />
              {activeEntity ? `Expanded graph for ${activeEntity}` : "Global relationship network"}
            </div>
            <h2 className="mt-2 text-2xl font-semibold">Entity relationship graph</h2>
          </div>

          <form onSubmit={handleSearch} className="flex w-full gap-2 lg:max-w-md">
            <Input
              value={entity}
              onChange={(event) => setEntity(event.target.value)}
              placeholder="Expand an entity..."
              className="bg-background/60"
            />
            <Button type="submit" size="icon" aria-label="Search entity graph">
              <Search className="h-4 w-4" />
            </Button>
          </form>
        </div>

        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap gap-2 text-sm text-muted-foreground">
            <span className="rounded-full border border-border bg-background/60 px-3 py-1">
              Nodes: {graph.node_count ?? graph.nodes.length}
            </span>
            <span className="rounded-full border border-border bg-background/60 px-3 py-1">
              Relationships: {graph.edge_count ?? graph.edges.length}
            </span>
          </div>

          <div className="flex gap-2">
            <Button type="button" variant="outline" size="icon" onClick={() => zoomBy(1.2)} aria-label="Zoom in">
              <ZoomIn className="h-4 w-4" />
            </Button>
            <Button type="button" variant="outline" size="icon" onClick={() => zoomBy(0.8)} aria-label="Zoom out">
              <ZoomOut className="h-4 w-4" />
            </Button>
            <Button type="button" variant="outline" size="icon" onClick={resetView} aria-label="Reset graph view">
              <RefreshCw className="h-4 w-4" />
            </Button>
            <Button type="button" variant="secondary" onClick={loadNetwork}>
              Global graph
            </Button>
          </div>
        </div>

        {Object.keys(typeCounts).length > 0 && (
          <div className="mb-4 flex flex-wrap gap-2">
            {Object.entries(typeCounts)
              .sort((a, b) => b[1] - a[1])
              .map(([type, count]) => {
                const hidden = hiddenTypes.has(type);
                return (
                  <button
                    key={type}
                    type="button"
                    onClick={() => toggleType(type)}
                    className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] transition-opacity ${
                      hidden ? "border-border/50 opacity-40" : "border-border"
                    }`}
                  >
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ backgroundColor: colorFor(type) }}
                    />
                    <span>{labelFor(type)}</span>
                    <span className="text-muted-foreground">{count}</span>
                  </button>
                );
              })}
          </div>
        )}

        <div ref={containerRef} className="relative overflow-hidden rounded-3xl border border-border bg-[#08111e]">
          {loading ? (
            <div className="flex h-[620px] items-center justify-center text-sm text-slate-300">
              Loading graph...
            </div>
          ) : error ? (
            <div className="flex h-[620px] items-center justify-center text-sm text-destructive">
              {error}
            </div>
          ) : (
            <>
              <CytoscapeComponent
                elements={graphElements}
                style={{ width: "100%", height: "620px" }}
                minZoom={0.25}
                maxZoom={2.5}
                zoomingEnabled
                userZoomingEnabled
                panningEnabled
                userPanningEnabled
                layout={{
                  name: "cose",
                  animate: true,
                  fit: true,
                  padding: 48,
                }}
                cy={(cy) => {
                  cyRef.current = cy;
                  cy.removeAllListeners();
                  cy.on("tap", "node", (event) => {
                    const nodeId = event.target.id();
                    setEntity(nodeId);
                    loadEntityGraph(nodeId);
                  });
                  cy.on("mouseover", "node", (event) => {
                    const n = event.target;
                    const pos = n.renderedPosition();
                    setTooltip({
                      x: pos.x,
                      y: pos.y,
                      label: n.data("label"),
                      entityType: n.data("entityType"),
                      country: n.data("country"),
                      degree: n.data("degree"),
                    });
                  });
                  cy.on("mousemove", "node", (event) => {
                    const n = event.target;
                    const pos = n.renderedPosition();
                    setTooltip((prev) => (prev ? { ...prev, x: pos.x, y: pos.y } : prev));
                  });
                  cy.on("mouseout", "node", () => setTooltip(null));
                }}
                stylesheet={[
                  {
                    selector: "node",
                    style: {
                      "background-color": DEFAULT_COLOR,
                      "border-color": "rgba(255,255,255,0.35)",
                      "border-width": 1,
                      color: "#f8fafc",
                      "font-size": 11,
                      label: "data(label)",
                      "overlay-opacity": 0,
                      "text-background-color": "#08111e",
                      "text-background-opacity": 0.85,
                      "text-background-padding": 4,
                      "text-margin-y": -10,
                      "text-max-width": 120,
                      "text-wrap": "wrap",
                      width: "mapData(degree, 0, 15, 18, 52)",
                      height: "mapData(degree, 0, 15, 18, 52)",
                    },
                  },
                  ...Object.entries(ENTITY_COLORS).map(([type, color]) => ({
                    selector: `node[entityType = "${type}"]`,
                    style: { "background-color": color, "border-color": color },
                  })),
                  {
                    selector: "edge",
                    style: {
                      "curve-style": "bezier",
                      "font-size": 10,
                      label: "data(label)",
                      "line-color": "rgba(148,163,184,0.55)",
                      "target-arrow-color": "rgba(148,163,184,0.55)",
                      "target-arrow-shape": "triangle",
                      "text-background-color": "#08111e",
                      "text-background-opacity": 0.8,
                      "text-background-padding": 3,
                      color: "#cbd5e1",
                      width: 1.5,
                    },
                  },
                  {
                    // Cytoscape's stylesheet isn't real CSS -- it doesn't
                    // resolve var(), so `hsl(var(--accent))` silently failed
                    // here (pre-existing, not introduced by this change; a
                    // literal color is required).
                    selector: "node:selected",
                    style: {
                      "border-color": "#2dd4bf",
                      "border-width": 3,
                    },
                  },
                ]}
              />
              {tooltip && (
                <div
                  className="pointer-events-none absolute z-10 rounded-lg border border-border bg-card px-3 py-2 text-xs shadow-elevation"
                  style={{ left: tooltip.x + 14, top: tooltip.y + 14, maxWidth: 220 }}
                >
                  <p className="font-semibold leading-tight">{tooltip.label}</p>
                  <p className="mt-0.5 flex items-center gap-1.5 text-muted-foreground">
                    <span
                      className="h-1.5 w-1.5 rounded-full"
                      style={{ backgroundColor: colorFor(tooltip.entityType) }}
                    />
                    {labelFor(tooltip.entityType)}
                    {tooltip.country ? ` · ${tooltip.country}` : ""} · {tooltip.degree} connection{tooltip.degree === 1 ? "" : "s"}
                  </p>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </AppShell>
  );
};

export default GraphExplorer;
