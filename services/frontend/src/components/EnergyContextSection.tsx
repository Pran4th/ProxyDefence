import { AlertTriangle, Anchor, Factory, Globe2, Droplets, Pipette, Zap, Building2, Fuel, Warehouse, Ship, Waypoints } from "lucide-react";

interface InfraItem {
  uuid: string;
  name: string;
  slug: string;
  status?: string;
  operational_status?: string;
  criticality?: string;
  importance?: number;
  confidence?: number;
  asset_category?: string;
}

interface LocationItem {
  uuid: string;
  name: string;
  slug: string;
  location_type?: string;
  iso_code?: string;
  region?: string;
}

interface OrgItem {
  uuid: string;
  name: string;
  slug: string;
  organization_type?: string;
  tags?: string[];
}

interface CommodityItem {
  uuid: string;
  name: string;
  slug: string;
  commodity_type?: string;
  unit?: string;
  benchmark_price?: number;
}

interface InfraEventItem {
  uuid: string;
  event_type?: string;
  severity?: string;
  description?: string;
  occurred_at?: string;
  asset_name?: string;
  asset_type?: string;
}

interface EnergyContext {
  locations: LocationItem[];
  infrastructure: InfraItem[];
  organizations: OrgItem[];
  commodities: CommodityItem[];
  infrastructure_events: InfraEventItem[];
  context: {
    countries_mentioned: string[];
    infrastructure_mentioned: string[];
    organizations_mentioned: string[];
    commodities_mentioned: string[];
    infrastructure_event_count: number;
    total_linked_assets: number;
  };
}

const assetIcons: Record<string, React.ComponentType<any>> = {
  port: Anchor,
  oil_field: Droplets,
  gas_field: Fuel,
  pipeline: Pipette,
  refinery: Factory,
  power_plant: Zap,
  storage_facility: Warehouse,
  strategic_petroleum_reserve: Building2,
  import_corridor: Waypoints,
  shipping_route: Ship,
};

const assetColors: Record<string, string> = {
  port: "text-blue-400 bg-blue-500/10",
  oil_field: "text-purple-400 bg-purple-500/10",
  gas_field: "text-cyan-400 bg-cyan-500/10",
  pipeline: "text-amber-400 bg-amber-500/10",
  refinery: "text-red-400 bg-red-500/10",
  power_plant: "text-green-400 bg-green-500/10",
  storage_facility: "text-orange-400 bg-orange-500/10",
  strategic_petroleum_reserve: "text-rose-400 bg-rose-500/10",
  import_corridor: "text-violet-400 bg-violet-500/10",
  shipping_route: "text-teal-400 bg-teal-500/10",
};

const EnergyContextSection = ({ energyContext }: { energyContext?: EnergyContext | null }) => {
  if (!energyContext) return null;

  const ctx = energyContext.context;

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <div className="grid h-10 w-10 place-items-center rounded-xl bg-primary/10">
          <Zap className="h-5 w-5 text-primary" />
        </div>
        <div>
          <h2 className="text-xl font-bold">Energy Impact</h2>
          <p className="text-sm text-muted-foreground">
            {ctx.total_linked_assets} energy asset{ctx.total_linked_assets !== 1 ? "s" : ""} linked
          </p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {ctx.countries_mentioned.length > 0 && (
          <div className="rounded-2xl border border-border bg-background p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-medium">
              <Globe2 className="h-4 w-4 text-blue-400" />
              Affected Countries
            </div>
            <div className="flex flex-wrap gap-2">
              {ctx.countries_mentioned.map((c) => (
                <span key={c} className="rounded-full bg-blue-500/10 px-3 py-1 text-xs text-blue-400 border border-blue-500/20">
                  {c}
                </span>
              ))}
            </div>
          </div>
        )}

        {ctx.organizations_mentioned.length > 0 && (
          <div className="rounded-2xl border border-border bg-background p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-medium">
              <Building2 className="h-4 w-4 text-purple-400" />
              Organizations
            </div>
            <div className="flex flex-wrap gap-2">
              {ctx.organizations_mentioned.map((o) => (
                <span key={o} className="rounded-full bg-purple-500/10 px-3 py-1 text-xs text-purple-400 border border-purple-500/20">
                  {o}
                </span>
              ))}
            </div>
          </div>
        )}

        {ctx.commodities_mentioned.length > 0 && (
          <div className="rounded-2xl border border-border bg-background p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-medium">
              <Droplets className="h-4 w-4 text-cyan-400" />
              Commodities
            </div>
            <div className="flex flex-wrap gap-2">
              {ctx.commodities_mentioned.map((c) => (
                <span key={c} className="rounded-full bg-cyan-500/10 px-3 py-1 text-xs text-cyan-400 border border-cyan-500/20">
                  {c}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {energyContext.infrastructure.length > 0 && (
        <div>
          <h3 className="mb-3 text-lg font-semibold">Affected Infrastructure</h3>
          <div className="grid gap-3 md:grid-cols-2">
            {energyContext.infrastructure.map((item) => {
              const Icon = assetIcons[item.asset_category || ""] || Factory;
              const colorClass = assetColors[item.asset_category || ""] || "text-gray-400 bg-gray-500/10";
              return (
                <div key={item.uuid} className="rounded-2xl border border-border bg-background p-4">
                  <div className="flex items-center gap-3">
                    <div className={`grid h-9 w-9 place-items-center rounded-lg ${colorClass}`}>
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate">{item.name}</p>
                      <p className="text-xs text-muted-foreground capitalize">
                        {item.asset_category?.replace(/_/g, " ")}
                        {item.criticality && ` · ${item.criticality} criticality`}
                      </p>
                    </div>
                    {item.status && (
                      <span className="shrink-0 rounded-full border px-2 py-0.5 text-xs capitalize">
                        {item.status}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {energyContext.infrastructure_events.length > 0 && (
        <div>
          <h3 className="mb-3 flex items-center gap-2 text-lg font-semibold">
            <AlertTriangle className="h-4 w-4 text-destructive" />
            Infrastructure Events
          </h3>
          <div className="space-y-3">
            {energyContext.infrastructure_events.map((evt) => (
              <div key={evt.uuid} className="rounded-2xl border border-destructive/20 bg-destructive/5 p-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="font-medium capitalize">{evt.event_type?.replace(/_/g, " ")}</p>
                    <p className="text-sm text-muted-foreground">{evt.asset_name}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {evt.severity && (
                      <span className="rounded-full border border-destructive/30 bg-destructive/10 px-2 py-0.5 text-xs capitalize text-destructive">
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
                {evt.description && (
                  <p className="mt-2 text-sm text-muted-foreground">{evt.description}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default EnergyContextSection;
