import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Network, RefreshCw, Search, ZoomIn, ZoomOut, Zap } from "lucide-react";
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
  nodes: GraphNode[];
  edges: GraphEdge[];
  node_count?: number;
  edge_count?: number;
};

const GraphExplorer = () => {
  const [searchParams] = useSearchParams();
  const cyRef = useRef<any>(null);
  const [graph, setGraph] = useState<GraphPayload>({ nodes: [], edges: [] });
  const [entity, setEntity] = useState(() => searchParams.get("entity") ?? "");
  const [activeEntity, setActiveEntity] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

        for (const rel of (energyData.relationships || [])) {
          const sourceLabel = `${rel.source_entity_type}:${rel.source_entity_id}`;
          const targetLabel = `${rel.target_entity_type}:${rel.target_entity_id}`;
          if (seenEdges.has(`${sourceLabel}|${targetLabel}`)) continue;
          seenEdges.add(`${sourceLabel}|${targetLabel}`);

          if (!existingNodeIds.has(sourceLabel)) {
            merged.nodes.push({ id: sourceLabel, label: sourceLabel, group: "energy", val: 10 });
            existingNodeIds.add(sourceLabel);
          }
          if (!existingNodeIds.has(targetLabel)) {
            merged.nodes.push({ id: targetLabel, label: targetLabel, group: "energy", val: 10 });
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

  const graphElements = useMemo(() => {
    const nodes = new Map<string, { data: { id: string; label: string } }>();
    const edges: { data: { id: string; source: string; target: string; label: string; confidence: number } }[] = [];

    graph.nodes.forEach((node) => {
      const id = node.id || node.label;
      if (!id) return;

      nodes.set(id, {
        data: {
          id,
          label: node.label || id,
        },
      });
    });

    graph.edges.forEach((edge, index) => {
      const source = edge.source || edge.source_entity;
      const target = edge.target || edge.target_entity;
      if (!source || !target || source === target) return;

      nodes.set(source, {
        data: {
          id: source,
          label: source,
        },
      });
      nodes.set(target, {
        data: {
          id: target,
          label: target,
        },
      });

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

    return [...nodes.values(), ...edges];
  }, [graph]);

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

        <div className="overflow-hidden rounded-3xl border border-border bg-[#08111e]">
          {loading ? (
            <div className="flex h-[620px] items-center justify-center text-sm text-slate-300">
              Loading graph...
            </div>
          ) : error ? (
            <div className="flex h-[620px] items-center justify-center text-sm text-destructive">
              {error}
            </div>
          ) : (
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
              }}
                stylesheet={[
                  {
                    selector: "node",
                    style: {
                      "background-color": "hsl(var(--primary))",
                      "border-color": "rgba(255,255,255,0.35)",
                      "border-width": 1,
                      color: "#f8fafc",
                      "font-size": 12,
                      label: "data(label)",
                      "overlay-opacity": 0,
                      "text-background-color": "#08111e",
                      "text-background-opacity": 0.85,
                      "text-background-padding": 4,
                      "text-margin-y": -10,
                      "text-max-width": 120,
                      "text-wrap": "wrap",
                      width: 28,
                      height: 28,
                    },
                  },
                  {
                    selector: "node[group = 'energy']",
                    style: {
                      "background-color": "#f59e0b",
                      "border-color": "rgba(245,158,11,0.6)",
                      "border-width": 2,
                      width: 20,
                      height: 20,
                    },
                  },
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
                  selector: "node:selected",
                  style: {
                    "background-color": "hsl(var(--accent))",
                    "border-color": "hsl(var(--accent))",
                    "border-width": 3,
                  },
                },
              ]}
            />
          )}
        </div>
      </div>
    </AppShell>
  );
};

export default GraphExplorer;
