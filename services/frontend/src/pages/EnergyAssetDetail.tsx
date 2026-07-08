import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Globe2, AlertTriangle, Clock, ExternalLink, MapPin } from "lucide-react";

import AppShell from "@/components/AppShell";
import { fetchEntity, fetchEntityRelationships, fetchEntityEvents } from "@/lib/api-energy";
import { Button } from "@/components/ui/button";

const entityLabel: Record<string, string> = {
  ports: "Port", oil_fields: "Oil Field", gas_fields: "Gas Field", pipelines: "Pipeline",
  refineries: "Refinery", power_plants: "Power Plant", storage_facilities: "Storage Facility",
  strategic_petroleum_reserves: "Strategic Petroleum Reserve", import_corridors: "Import Corridor",
  shipping_routes: "Shipping Route", suppliers: "Supplier", locations: "Location", organizations: "Organization", commodities: "Commodity",
};

const EnergyAssetDetail = () => {
  const { type, uuid } = useParams<{ type: string; uuid: string }>();
  const [entity, setEntity] = useState<any>(null);
  const [relationships, setRelationships] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!type || !uuid) { setError("Missing asset type or UUID"); setLoading(false); return; }
    setLoading(true);
    Promise.all([
      fetchEntity(type, uuid),
      fetchEntityRelationships(type, uuid).catch(() => []),
      fetchEntityEvents(type, uuid).catch(() => []),
    ])
      .then(([entityData, rels, evts]) => {
        setEntity(entityData);
        setRelationships(rels);
        setEvents(evts);
      })
      .catch(() => setError("Failed to load asset details"))
      .finally(() => setLoading(false));
  }, [type, uuid]);

  if (loading) {
    return (
      <AppShell title="Energy Asset" subtitle="Loading">
        <div className="flex min-h-[400px] items-center justify-center text-muted-foreground">Loading asset details...</div>
      </AppShell>
    );
  }

  if (error || !entity) {
    return (
      <AppShell title="Energy Asset" subtitle="Error">
        <div className="flex min-h-[400px] flex-col items-center justify-center gap-4 text-muted-foreground">
          <AlertTriangle className="h-8 w-8 text-destructive" />
          <p>{error || "Asset not found"}</p>
          <Link to="/energy/map" className="text-primary hover:underline">Back to map</Link>
        </div>
      </AppShell>
    );
  }

  const simpleFields = [
    ["Name", entity.name],
    ["Type", entityLabel[type || ""] || type],
    ["Status", entity.status],
    ["Operational Status", entity.operational_status],
    ["Criticality", entity.criticality],
    ["Importance", entity.importance],
    ["Confidence", entity.confidence != null ? `${Math.round(entity.confidence * 100)}%` : null],
    ["Latitude", entity.latitude?.toFixed(4)],
    ["Longitude", entity.longitude?.toFixed(4)],
    ["Description", entity.description],
    ["Tags", entity.tags?.join(", ")],
  ].filter(([, v]) => v != null && v !== "");

  return (
    <AppShell title={entity.name || "Energy Asset"} subtitle={`${entityLabel[type || ""] || type} · ${uuid?.slice(0, 8)}...`}>
      <div className="space-y-6">
        <Link to="/energy/map" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" />
          Back to energy map
        </Link>

        <div className="rounded-3xl border border-border bg-card p-6">
          <div className="mb-6 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="grid h-12 w-12 place-items-center rounded-xl bg-primary/10">
                <MapPin className="h-6 w-6 text-primary" />
              </div>
              <div>
                <h1 className="text-2xl font-bold">{entity.name}</h1>
                <p className="text-sm text-muted-foreground capitalize">{entityLabel[type || ""] || type}</p>
              </div>
            </div>
            {entity.criticality && (
              <span className="rounded-full border px-4 py-2 text-sm font-semibold capitalize">
                {entity.criticality} criticality
              </span>
            )}
          </div>

          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {simpleFields.map(([label, value]) => (
              <div key={label} className="rounded-xl border border-border bg-background p-3">
                <p className="text-xs uppercase tracking-wider text-muted-foreground">{label}</p>
                <p className="mt-1 text-sm font-medium capitalize">{String(value)}</p>
              </div>
            ))}
          </div>
        </div>

        {relationships.length > 0 && (
          <div className="rounded-3xl border border-border bg-card p-6">
            <h2 className="mb-4 text-xl font-bold">Relationships ({relationships.length})</h2>
            <div className="space-y-2">
              {relationships.map((rel, i) => (
                <div key={i} className="rounded-xl border border-border bg-background p-3 text-sm">
                  <span className="font-medium">{rel.source_entity_type}</span>
                  <span className="mx-2 text-primary">{rel.relationship_type}</span>
                  <span className="font-medium">{rel.target_entity_type}</span>
                  {rel.confidence != null && (
                    <span className="ml-2 text-muted-foreground">({Math.round(rel.confidence * 100)}%)</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {events.length > 0 && (
          <div className="rounded-3xl border border-border bg-card p-6">
            <h2 className="mb-4 flex items-center gap-2 text-xl font-bold">
              <AlertTriangle className="h-5 w-5 text-destructive" />
              Infrastructure Events ({events.length})
            </h2>
            <div className="space-y-3">
              {events.map((evt) => (
                <div key={evt.uuid || evt.id} className="rounded-xl border border-destructive/20 bg-destructive/5 p-4">
                  <div className="flex items-center justify-between gap-4">
                    <p className="font-medium capitalize">{evt.event_type?.replace(/_/g, " ")}</p>
                    <div className="flex items-center gap-2">
                      {evt.severity && (
                        <span className="rounded-full border border-destructive/30 px-2 py-0.5 text-xs capitalize text-destructive">
                          {evt.severity}
                        </span>
                      )}
                      {evt.occurred_at && (
                        <span className="text-xs text-muted-foreground">
                          {new Date(evt.occurred_at).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                  </div>
                  {evt.description && <p className="mt-1 text-sm text-muted-foreground">{evt.description}</p>}
                </div>
              ))}
            </div>
          </div>
        )}

        {entity.latitude != null && entity.longitude != null && (
          <div className="rounded-3xl border border-border bg-card p-6">
            <h2 className="mb-4 text-xl font-bold">Location</h2>
            <div className="rounded-2xl border border-border bg-[#0a1628] p-6 text-center">
              <Globe2 className="mx-auto h-10 w-10 text-primary mb-2" />
              <p className="text-sm text-muted-foreground">
                {entity.latitude.toFixed(4)}, {entity.longitude.toFixed(4)}
              </p>
              <a
                href={`https://www.google.com/maps?q=${entity.latitude},${entity.longitude}`}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 inline-flex items-center gap-1 text-xs text-primary hover:underline"
              >
                <ExternalLink className="h-3 w-3" />
                Open in Google Maps
              </a>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
};

export default EnergyAssetDetail;
