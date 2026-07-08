# Energy Intelligence — Frontend Integration

## Architecture

```
Energy Service (8006)
  → energy.* schema (PostgreSQL)
  → energy-service catalog REST API (modular-api)
  → api-energy.ts client

database-service consumer pipeline:
  → enrich_energy_context()
  → article_energy_enrichments table
  → modular-api GET /articles/{id} returns energy_context

modular-api endpoints used:
  GET /articles/{id}             → Article.energy_context
  POST /copilot/query            → CopilotResponse.energy_impact + energy_assessment
  GET /api/v1/energy/{table}     → Energy catalog entities (via api-energy.ts)
  GET /api/v1/energy/graph/network → Energy relationship graph
  GET /api/v1/energy/{table}/{uuid}/relationships → Per-asset relationships
  GET /api/v1/energy/{table}/{uuid}/events       → Per-asset events
```

## Pages Updated or Created

| Page | File | Change |
|------|------|--------|
| Article Detail | `pages/ArticleDetail.tsx` | **NEW** — `/article/:id` route. Renders full article with extracted entities, energy context section (countries, infrastructure, organizations, commodities, infrastructure events) |
| Copilot | `pages/Copilot.tsx` | **MODIFIED** — Renders `EnergyImpactCard` with severity badge, country/infrastructure/org/commodity counts, badges, and infrastructure event alerts. Energy assessment text shown in card header |
| Search | `pages/Search.tsx` | **MODIFIED** — Search results now link to `/article/:id` for full article detail with energy context |
| News | `pages/News.tsx` | **MODIFIED** — NewsCards pass `articleId` prop, making them clickable links to Article Detail |
| Energy Map | `pages/EnergyMap.tsx` | **NEW** — `/energy/map` route. SVG-based interactive world map overlaying all energy asset types (ports, oil fields, gas fields, pipelines, refineries, power plants, storage facilities, SPRs, shipping routes, import corridors). Layer toggle panel. Click-on-asset info popup with link to detail page |
| Energy Asset Detail | `pages/EnergyAssetDetail.tsx` | **NEW** — `/energy/assets/:type/:uuid` route. Full asset detail page showing all fields, relationships, infrastructure events, and location with Google Maps link |
| Energy Analytics | `pages/EnergyAnalytics.tsx` | **NEW** — `/energy/analytics` route. Infrastructure catalog metrics (total assets, countries, orgs, commodities counts). Inventory list with per-type counts. Asset distribution bar chart. Quick links to map and graph |
| Graph Explorer | `pages/GraphExplorer.tsx` | **MODIFIED** — `/graph` route now merges energy entity relationships from `energy-service/graph/network` with the existing intelligence graph. Energy nodes rendered as amber-colored nodes (group="energy") for visual distinction |
| Dashboard | `pages/Dashboard.tsx` | No backend changes needed — energy data is visible through linked articles and existing energy nav items |
| Analytics | `pages/Analytics.tsx` | No backend changes needed — energy analytics has its own dedicated page |

## Components Created

| Component | File | Purpose |
|-----------|------|---------|
| EnergyImpactCard | `components/EnergyImpactCard.tsx` | Reusable card showing energy impact severity with color-coded badge, 4-column metrics (countries, infrastructure, organizations, commodities), asset tags, infrastructure event alerts |
| EnergyContextSection | `components/EnergyContextSection.tsx` | Per-article energy context section showing affected countries, organizations, commodities with badges; infrastructure assets with type-specific icons and colors; infrastructure events with severity indicators and dates |
| NewsCard | `components/NewsCard.tsx` | **MODIFIED** — Added optional `articleId` prop. When provided, card wraps in `<Link to="/article/:id">` for drill-down navigation |

## API Client Additions

**`lib/api.ts`**:
- Added `fetchArticle(id: number)` — calls `GET /articles/{id}`, returns `Article` with `energy_context`

**`lib/api-energy.ts`** (existing, now consumed by new pages):
- `fetchEntities<T>(table, params)` — paginated energy catalog queries
- `fetchEntity<T>(table, uuid)` — single asset detail
- `fetchEntityRelationships(table, uuid)` — per-asset relationships
- `fetchEntityEvents(table, uuid)` — per-asset infrastructure events
- `fetchNetworkGraph(limit)` — energy relationship graph for Graph Explorer merge

## Data Flow per Page

### Article Detail (`/article/:id`)
```
Frontend → fetchArticle(id) → GET /articles/{id}
  → processed_articles row
  → article_energy_enrichments row (LEFT JOIN)
  → response.energy_context
    → energy_context.locations (countries with iso_code, region, lat/lng)
    → energy_context.infrastructure (ports, pipelines, refineries with status, criticality)
    → energy_context.organizations (companies with type, tags)
    → energy_context.commodities (crude, LNG with benchmark_price)
    → energy_context.infrastructure_events (recent events on matched assets)
    → energy_context.context (aggregated summary counts)
```

### Copilot (`/copilot`)
```
Frontend → queryCopilot(question) → POST /copilot/query
  → embedding-service semantic search → article IDs
  → article_energy_enrichments for matched articles
  → CopilotService.compute_energy_impact()
    → severity, countries_involved, infrastructure_affected,
      organizations_involved, commodities_involved,
      infrastructure_event_count, total_energy_articles
  → CopilotService.build_energy_assessment() → text summary
  → response.energy_impact + energy_assessment
```

### Energy Map (`/energy/map`)
```
Frontend → fetchEntities(table, {limit:500}) for each of 10 asset tables
  → Ports, Oil Fields, Gas Fields, Pipelines, Refineries,
    Power Plants, Storage Facilities, SPRs, Shipping Routes,
    Import Corridors
  → Renders on SVG canvas (cylindrical projection)
  → Layer toggle (show/hide per asset type)
  → Click popup → link to /energy/assets/:type/:uuid
```

### Energy Asset Detail (`/energy/assets/:type/:uuid`)
```
Frontend → fetchEntity(type, uuid) → asset detail
  → fetchEntityRelationships(type, uuid) → relationships
  → fetchEntityEvents(type, uuid) → infrastructure events
  → Renders all fields in card grid
  → Google Maps link for geolocated assets
```

### Graph Explorer (`/graph`)
```
Frontend → fetchNetworkGraph() → intelligence graph (nodes + edges)
  + fetchEnergyGraph(2000) → energy relationships
  → Merge: add energy nodes (group="energy", amber color) and edges
  → Cytoscape renders merged graph with energy-specific styling
```

## Asset Type Mapping

| Energy Asset Type | Icon | Color | Map Layer | Detail Route |
|-------------------|------|-------|-----------|--------------|
| ports | Anchor | Blue | Yes | /energy/assets/ports/:uuid |
| oil_fields | Droplets | Purple | Yes | /energy/assets/oil_fields/:uuid |
| gas_fields | Fuel | Cyan | Yes | /energy/assets/gas_fields/:uuid |
| pipelines | Pipette | Amber | Yes | /energy/assets/pipelines/:uuid |
| refineries | Factory | Red | Yes | /energy/assets/refineries/:uuid |
| power_plants | Zap | Green | Yes | /energy/assets/power_plants/:uuid |
| storage_facilities | Warehouse | Orange | Yes | /energy/assets/storage_facilities/:uuid |
| strategic_petroleum_reserves | Building2 | Rose | Yes | /energy/assets/strategic_petroleum_reserves/:uuid |
| import_corridors | Waypoints | Violet | Yes | /energy/assets/import_corridors/:uuid |
| shipping_routes | Ship | Teal | Yes | /energy/assets/shipping_routes/:uuid |

## Frontend Build

```
npm run build → SUCCESS
2563 modules transformed
0 errors
```

## Navigation

AppShell sidebar now includes two new items below Reports:
- **Energy Analytics** (`/energy/analytics`) — Zap icon
- **Energy Map** (`/energy/map`) — Map icon

Article Detail is accessible via:
- News cards (clickable via `articleId` prop)
- Search results (linked to `/article/:id`)
- Copilot intelligence reports (not linked yet — future improvement)

## Remaining Work

1. **Energy context in Copilot article cards** — Currently Copilot article list items are not linked to article detail. Adding `articleId` links would complete the drill-down flow.
2. **Dashboard energy widget** — Add a row of energy KPIs (most-linked countries, total enrichments) by querying `article_energy_enrichments` counts. Backend `GET /analytics/summary` would need an energy extension.
3. **Search result energy badges** — Search results come from Elasticsearch which doesn't store energy context yet. Optional optimization: enrich ES documents with energy context, or batch-fetch enrichments for displayed results.
4. **Frontend unit tests** — No test framework is currently configured. Jest/Vitest setup would enable component-level validation of EnergyImpactCard, EnergyContextSection.
5. **Article Detail map embed** — Show a mini SVG map of matched asset locations directly on the article page.

## Files Changed (Summary)

| Path | Status |
|------|--------|
| `services/frontend/src/lib/api.ts` | Modified (added fetchArticle) |
| `services/frontend/src/components/NewsCard.tsx` | Modified (added articleId link) |
| `services/frontend/src/components/EnergyImpactCard.tsx` | **NEW** |
| `services/frontend/src/components/EnergyContextSection.tsx` | **NEW** |
| `services/frontend/src/pages/ArticleDetail.tsx` | **NEW** |
| `services/frontend/src/pages/EnergyMap.tsx` | **NEW** |
| `services/frontend/src/pages/EnergyAssetDetail.tsx` | **NEW** |
| `services/frontend/src/pages/EnergyAnalytics.tsx` | **NEW** |
| `services/frontend/src/pages/Copilot.tsx` | Modified (added EnergyImpactCard) |
| `services/frontend/src/pages/Search.tsx` | Modified (linked to article detail) |
| `services/frontend/src/pages/News.tsx` | Modified (passed articleId to NewsCard) |
| `services/frontend/src/pages/GraphExplorer.tsx` | Modified (merged energy graph) |
| `services/frontend/src/components/AppShell.tsx` | Modified (added energy nav items) |
| `services/frontend/src/App.tsx` | Modified (added 4 new routes) |
| `docs/ENERGY_FRONTEND_INTEGRATION.md` | **NEW** |
