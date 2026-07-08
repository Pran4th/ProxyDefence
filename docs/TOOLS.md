# Tool Layer

All 25 tools call existing REST API endpoints through the modular API (port 8000). Each tool maps to a specific `GET` endpoint.

## Search Tools

| Tool | Endpoint | Description |
|------|----------|-------------|
| `search_articles` | `GET /search/?q=` | Full-text search via Elasticsearch |
| `semantic_search` | `GET /semantic-search?q=` | Semantic search via embedding vectors |
| `get_entity_articles` | `GET /entities/{name}/articles` | Articles mentioning an entity |

## Intelligence Tools

| Tool | Endpoint | Description |
|------|----------|-------------|
| `get_risk_dashboard` | `GET /api/v1/intelligence/risk` | Aggregated risk scores |
| `get_active_signals` | `GET /api/v1/intelligence/signals` | Active disruption signals |
| `get_entity_risk_profile` | `GET /api/v1/intelligence/entity/{table}/{uuid}/risk-profile` | Full risk profile for an entity |
| `get_risk_trends` | `GET /api/v1/intelligence/risk/trends` | Risk score trends |
| `get_commodity_prices` | `GET /api/v1/intelligence/commodity-prices` | Commodity price records |
| `get_alerts` | `GET /alerts/` | System alerts |
| `get_events` | `GET /events/` | Intelligence events |
| `get_threat_trends` | `GET /analytics/threat-trends` | Threat level trends |

## Energy Tools

| Tool | Endpoint | Description |
|------|----------|-------------|
| `lookup_entity` | `GET /api/v1/energy/{type}/{uuid}` | Single entity by UUID |
| `list_entities` | `GET /api/v1/energy/{type}` | List entities with filters |
| `get_entity_relationships` | `GET /api/v1/energy/{type}/{uuid}/relationships` | Entity relationships |
| `get_port_congestion` | `GET /api/v1/intelligence/port-congestion` | Port congestion data |
| `get_tanker_availability` | `GET /api/v1/intelligence/tanker-availability` | Tanker availability |
| `get_sanctions_data` | `GET /api/v1/intelligence/sanctions` | Sanctions records |

## Analytics Tools

| Tool | Endpoint | Description |
|------|----------|-------------|
| `get_analytics_summary` | `GET /analytics/summary` | Platform analytics summary |
| `get_entity_analytics` | `GET /analytics/entities` | Top mentioned entities |
| `get_topic_analytics` | `GET /analytics/topics` | Topic breakdown |
| `get_dashboard_stats` | `GET /analytics/dashboard` | Dashboard statistics |

## Graph Tools

| Tool | Endpoint | Description |
|------|----------|-------------|
| `get_entity_network` | `GET /graph/network` | Entity relationship network |
| `expand_entity_graph` | `GET /graph/{entity}` | Graph expansion for an entity |
| `get_energy_knowledge_graph` | `GET /api/v1/energy/graph/network` | Energy infrastructure KG |
| `get_risk_propagation_map` | `GET /api/v1/intelligence/propagation-map` | Risk propagation through graph |

## Registration

All tools registered at import time in `backend/api/tools/__init__.py`:

```python
tools = [SearchArticlesTool(), SemanticSearchTool(), ...]
for tool in tools:
    tool_registry.register(tool)
```

OpenAI tool definitions auto-generated via `to_openai_tool()` method.
