# Dataset Builder Workflow

13 builder types in `services/ml-platform/datasets/builders/`:

| Builder | Sources | Target Domain |
|---------|---------|-------------|
| `energy_infrastructure` | locations, orgs, commodities, ports, pipelines, refineries, power_plants, oil/gas fields | Infrastructure catalog |
| `news_articles` | processed_articles, extracted_entities, article_sentiments | News intelligence |
| `risk_signals` | drift_results, infrastructure_events, model_predictions | Risk assessment |
| `commodity_prices` | commodities, capacity_history, entity_relationships | Price forecasting |
| `spr` | strategic_petroleum_reserves, storage_facilities | SPR analytics |
| `procurement` | suppliers, entity_relationships | Procurement intelligence |
| `events` | infrastructure_events | Incident analysis |
| `entity_relationships` | entity_relationships | Relationship graphs |
| `knowledge_graph` | all entities + relationships | Graph analytics |
| `digital_twin` | all infrastructure + telemetry | Digital twin |
| `graph_embeddings` | entity_relationships | Graph ML features |
| `hybrid` | any combination of above | Multi-domain |

## Workflow

### 1. Define Sources

```python
class MyBuilder(BaseDatasetBuilder):
    def define_sources(self) -> list[dict]:
        return [{
            "name": "assets",
            "table": "energy.infrastructure_assets",
            "columns": ["id", "type", "capacity", "status"],
        }]
```

### 2. Define Joins
### 3. Define Cleaning (drop columns, fill nulls, clip outliers)
### 4. Define Features (select which columns become ML features)
### 5. Define Labels (target column specification)

### Register Trigger

```bash
curl -X POST http://localhost:8007/api/v1/ml/build \
  -H "Content-Type: application/json" \
  -d '{"builder": "energy_infrastructure", "name": "energy_assets_v1"}'
```

### Query Catalog

```bash
curl http://localhost:8007/api/v1/ml/datasets/catalog/search?q=energy
```

See `services/ml-platform/datasets/builders/base.py` for the full `BaseDatasetBuilder` API.
