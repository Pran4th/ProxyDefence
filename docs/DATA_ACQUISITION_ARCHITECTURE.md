# Data Acquisition Layer Architecture

## 1. Architecture Overview

```
 External Source    Connector        Raw Data Lake        Parser          Normalization       Quality         Dataset Builder
 ┌────────────┐    ┌──────────┐    ┌──────────────┐    ┌──────────┐    ┌──────────────┐   ┌───────────┐    ┌──────────────────┐
 │ GDELT      │───▶│ REST API │───▶│ datasets/raw │───▶│ GDELT     │───▶│ canonical    │──▶│ checksums │───▶│ EnergyInfra      │
 │ EIA        │───▶│ REST API │───▶│ /gdelt/      │───▶│ Event     │───▶│ record       │   │ schema    │    │ RiskSignals      │
 │ OFAC       │───▶│ CSV      │───▶│ /eia/        │───▶│ EIA       │───▶│ mapping      │   │ profiling │    │ KnowledgeGraph   │
 │ AIS        │───▶│ REST API │───▶│ /ofac/       │───▶│ OFAC      │───▶│              │   │ stats     │    │ CommodityPrices  │
 │ Kaggle     │───▶│ CSV      │───▶│ /kaggle/     │───▶│ Kaggle    │   └──────────────┘   └───────────┘    │ DigitalTwin      │
 │ UN Comtrade│───▶│ REST API │───▶│ /comtrade/   │───▶│ Comtrade  │                      ┌───────────┐    │ Events           │
 │ WorldBank  │───▶│ REST API │───▶│ /worldbank/  │───▶│ WorldBank │                      │  Dataset  │    │ EntityRelations  │
 └────────────┘    └──────────┘    └──────────────┘    └──────────┘                      │ Registry  │    │ Procurement      │
                                                                                         │  Catalog  │    │ SPR              │
          Feature Engineering           Feature Store    Dataset Registry │  Manifest │    │ GraphEmbeddings  │
          ┌──────────────────┐    ┌──────────────────┐  └───────────┘    │  Metadata  │    │ Hybrid           │
          │ datasets/features│───▶│ ml.feature_      │         │         └───────────┘    └────────┬─────────┘
          │ /{dataset}/{ver} │    │ definitions      │         │                │                  │
          └──────────────────┘    └──────────────────┘         ▼                ▼                  ▼
                                                   ┌───────────────────────────────────────────────────┐
                                                   │            TRAINING PIPELINE                       │
                                                   │  datasets/training/ → train/val/test splits       │
                                                   │  Model training → Experiment tracking (MLflow)    │
                                                   │  Model Registry → Prediction API                  │
                                                   └───────────────────────────────────────────────────┘
```

### Layer Map

| Layer | Directory / Module | Responsibility |
|-------|-------------------|----------------|
| Connector | `data_acquisition/download_manager.py` | HTTP/CSV download with resume, checksums, decompression |
| Raw Data Lake | `datasets/raw/{source}/{version}/` | Versioned archives and raw source files |
| Parser | `data_acquisition/parser/sources/*.py` | Source-specific format parsing to canonical schema |
| Normalization | `data_acquisition/canonical.py` | CanonicalRecord with unified entity model |
| Quality | `data_acquisition/registration.py` | Statistics, profiling, checksums, feature classification |
| Dataset Builder | `datasets/builders/*.py` (12 builders) | Domain-specific dataset assembly pipelines |
| Feature Engineering | `datasets/features/{name}/{ver}/` | Feature-engineered data artifacts |
| Feature Store | `ml.feature_definitions` (PostgreSQL) | Feature metadata registry |
| Dataset Registry | `datasets/registry/{name}/` | Manifest files, catalog entries, lineage |
| Training Pipeline | `datasets/training/{name}/{ver}/` | Train/val/test splits ready for model training |

---

## 2. Directory Structure

```
services/ml-platform/
├── data_acquisition/                          # Core acquisition code
│   ├── __init__.py                            # Public API: DataLake, SourceRegistry, CanonicalRecord, etc.
│   ├── config.py                              # DataAcquisitionConfig (env: DATASET_DIR, DA_MAX_RETRIES, etc.)
│   ├── canonical.py                           # CanonicalRecord, CanonicalSchema (15-field unified model)
│   ├── download_manager.py                    # DownloadManager with resume, SHA256, decompression, retry
│   ├── lake.py                                # DataLake — filesystem abstraction (raw/processed/normalized/...)
│   ├── manifest.py                            # DatasetManifest, ManifestGenerator (YAML output)
│   ├── source_registry.py                     # SourceRegistry, SourceDefinition, 23 pre-registered sources
│   ├── registration.py                        # DatasetRegistrationPipeline (stats, profiling, preview)
│   ├── registration_flow.py                   # RegistrationFlow — orchestrates raw→processed→registered
│   ├── research_integration.py                # DatasetResolver, ExperimentDatasetResolver
│   └── parser/
│       ├── __init__.py                        # Exports BaseParser, ParserResult, ParseConfig
│       ├── base.py                            # BaseParser ABC (7 abstract methods)
│       └── sources/
│           ├── __init__.py                    # All 17 parsers exported
│           ├── gdelt.py                       # GDELTEventParser, GDELTMentionParser, GKGParser, GCAMParser
│           ├── eia.py                         # EIAParser, FREDParser
│           ├── opec.py                        # OPECParser
│           ├── ais.py                         # AISParser, PortCongestionParser, WorldPortIndexParser
│           ├── commodity.py                   # CommodityPriceParser, CommodityFuturesParser
│           ├── sanctions.py                   # OFACParser, UNSanctionsParser
│           ├── world_bank.py                  # WorldBankParser
│           ├── un_comtrade.py                 # UNComtradeParser
│           └── kaggle.py                      # KaggleParser
│
├── datasets/                                  # Dataset management code
│   ├── builder.py                             # DatasetBuilder orchestrator
│   ├── catalog.py                             # DatasetCatalog (PostgreSQL-backed)
│   ├── metadata.py / cards.py / loader.py / lineage.py / hashing.py
│   ├── statistics.py / profiling.py / splitter.py / schema_registry.py / versioning.py / validation.py
│   └── builders/                              # 12 domain-specific builders
│       ├── base.py                            # BaseDatasetBuilder ABC
│       ├── energy_infrastructure.py / news_articles.py / knowledge_graph.py / risk_signals.py
│       ├── commodity_prices.py / digital_twin.py / procurement.py / spr.py / events.py
│       └── entity_relationships.py / graph_embeddings.py / hybrid.py
│
├── cli/main.py                                # `ml` CLI — 9 commands, PARSER_MAP, BUILDER_MAP
└── routers/data_acquisition.py               # FastAPI router — 14 REST endpoints

datasets/  (runtime data lake)
├── raw/{source}/{version}/        # Downloaded archives + _metadata.json + _download_history.json
├── processed/{dataset}/{version}/ # Parsed data.parquet + dataset.yaml manifest
├── normalized/{dataset}/{version}/
├── features/{dataset}/{version}/
├── training/{dataset}/{version}/  # train.parquet / val.parquet / test.parquet
└── registry/{dataset}/           # Latest manifest copies
```

---

## 3. Data Flow

### Step 1: Download (`DownloadManager`)
Accepts `DownloadConfig` → checks for partial file (HTTP Range resume) → streams via `aiohttp` (8KB chunks) → verifies SHA256 → decompresses (zip/tar.gz/tar.bz2/gz/bz2) → writes `_metadata.json` + `_download_history.json` → stores in `datasets/raw/{source}/{version}/`.

### Step 2: Parse (`BaseParser`)
Each parser implements: `parse()`, `parse_file()`, `discover_schema()` (100-row sampling), `validate()`, `get_metadata()`, `to_canonical()`, `canonical_schema`. Converts source format to canonical structure. Output: `datasets/processed/{source}/{version}/data.parquet`.

### Step 3: Normalize (`CanonicalRecord`)
15-field unified model: entity_type, entity_id, entity_name, timestamp, timestamp_precision, lat/lon, location_name/code, attributes (dict), relationships (list), source, source_record_id, confidence, metadata.

### Step 4: Quality (`DatasetRegistrationPipeline`)
Computes row/column count, memory, missing cells, duplicates, column type breakdowns. Per-column: dtype, cardinality, missing rate. Distributions: numerical (min/max/mean/std/quartiles), categorical (top-10), temporal (range). SHA256 checksum. Schema inference. Feature classification (targets/numerical/categorical/temporal/geographical/entity).

### Step 5: Register (`DatasetRegistrationPipeline` + `DatasetCatalog`)
Registers in PostgreSQL `ml.datasets` via `DatasetCatalog` → generates YAML manifest with checksum, schema hash, row/column counts → saves to `processed/{name}/{ver}/dataset.yaml` → returns `DatasetRegistrationResult` with UUID.

### Step 6: Build (`DatasetBuilder`)
Executes domain-specific builder (one of 12). Produces feature-engineered data and training-ready splits (train/val/test).

---

## 4. Data Lake

| Zone | Path | Content |
|------|------|---------|
| Raw | `datasets/raw/{source}/{version}/` | Original archives + `_metadata.json` (source, url, checksum, duration, retries) + `_download_history.json` |
| Processed | `datasets/processed/{dataset}/{version}/` | `data.parquet` (canonical) + `dataset.yaml` (manifest) |
| Normalized | `datasets/normalized/{dataset}/{version}/` | Cross-source entity resolution outputs |
| Features | `datasets/features/{dataset}/{version}/` | Feature-engineered data artifacts |
| Training | `datasets/training/{dataset}/{version}/` | `train.parquet`, `val.parquet`, `test.parquet` |
| Registry | `datasets/registry/{dataset}/` | Latest manifest copies for cataloged datasets |

`DataLake` API: `ensure_directories()`, `list_versions(source)`, `list_sources()`, `get_source_info()`, `get_lake_stats()`, `get_disk_usage()`, `create_version_dir()`.

---

## 5. Source Registry

23 pre-registered sources in `DATASET_REGISTRY` (list in `source_registry.py:241-573`).

| Category | Sources | Connectors | Parsers |
|----------|---------|-----------|---------|
| **Geopolitical** (4) | gdelt-events, gdelt-mentions, gdelt-gkg, gdelt-gcam | rest_api | GDELTEventParser, GDELTMentionParser, GKGParser, GCAMParser |
| **Energy** (8) | eia-petroleum, eia-natural-gas, eia-coal, eia-electricity, fred-oil-prices, fred-gas-prices, opec-production, opec-exports | rest_api, csv | EIAParser, FREDParser, OPECParser |
| **Shipping** (3) | ais-global, port-congestion, world-port-index | rest_api, csv | AISParser, PortCongestionParser, WorldPortIndexParser |
| **Commodity** (2) | commodity-prices, commodity-futures | rest_api | CommodityPriceParser, CommodityFuturesParser |
| **Sanctions** (2) | ofac-sanctions, un-sanctions | csv | OFACParser, UNSanctionsParser |
| **Economics** (2) | world-bank-indicators, un-comtrade | rest_api | WorldBankParser, UNComtradeParser |
| **Other** (2) | kaggle-competition, kaggle-dataset | csv | KaggleParser |

Each `SourceDefinition` includes: name, display_name, description, category, update_frequency, connector_type, default_parser, url_template, expected_schema, version, license, citation, tags, is_active. Schema sizes range from 4 fields (FRED) to 58 fields (GDELT Events).

---

## 6. Download Manager

### Resume Support (HTTP Range)
```python
# Checks Accept-Ranges header via HEAD request
# Sets Range: bytes={offset}- if supported
# Opens file in append ("ab") mode for continuation
```

### Checksum Verification (SHA256)
8KB chunked reading, configurable via `DA_VERIFY_CHECKSUMS`. Mismatch sets status to `"partial"`.

### Decompression
| Format | Library | Method |
|--------|---------|--------|
| `.zip` | `zipfile` | `_extract_zip()` |
| `.tar.gz` / `.tgz` | `tarfile` (r:gz) | `_extract_tar()` |
| `.tar.bz2` | `tarfile` (r:bz2) | `_extract_tar()` |
| `.gz` | `gzip` | `_decompress_gzip()` |
| `.bz2` | `bz2` | `_decompress_bz2()` |

### Retry with Exponential Backoff
```python
wait = config.retry_delay * (2 ** (retries - 1))  # 5s, 10s, 20s
```
Config: `max_retries=3`, `retry_delay=5.0`. Handles `aiohttp.ClientError`, `asyncio.TimeoutError`, `OSError`.

### Version Management
```python
version_dir = await data_lake.create_version_dir(source, version)
# datasets/raw/{source}/{version}/
await download_manager.clean_old_versions(source, keep_last=3)
```

### Metadata
Per-version: `_metadata.json` (source, version, url, downloaded_at, status, size, checksum, duration, retries, files). Per-source: `_download_history.json` (append-only chronological log).

### Configuration
`DATASET_DIR` (./datasets), `DA_MAX_RETRIES` (3), `DA_RETRY_DELAY` (5.0), `DA_CHUNK_SIZE` (8192), `DA_VERIFY_CHECKSUMS` (1), `DA_PRESERVE_ARCHIVES` (0), `DA_LOG_LEVEL` (INFO).

---

## 7. Parser Framework

### BaseParser Interface

```python
class BaseParser(ABC):
    async def parse(self, config: ParseConfig) -> ParserResult
    async def parse_file(self, input_path, output_path, **kwargs) -> ParserResult
    async def discover_schema(self, input_path) -> dict
    async def validate(self, input_path) -> list[str]
    async def get_metadata(self, input_path) -> dict
    async def to_canonical(self, records: list[dict]) -> list[dict]
    @property
    def canonical_schema(self) -> dict
```

**ParseConfig**: source, version, input_path, output_path, encoding, batch_size (10k), max_records, schema, params.

**ParserResult**: source, version, records_parsed, records_failed, output_path, schema_discovered, columns, row_count, duration_seconds, errors, metadata.

### 17 Parsers

| Parser | Input Format | entity_type | Key Canonical Mapping |
|--------|-------------|-------------|----------------------|
| `GDELTEventParser` | TSV | event | GlobalEventID→id, Day→timestamp, Geo_Lat/Long→lat/lon, all→attributes |
| `GDELTMentionParser` | TSV | mention | GlobalEventID→id, EventTimeDate→timestamp |
| `GKGParser` | TSV | gkg_record | GKGRECORDID→id, themes/persons→relationships |
| `GCAMParser` | TSV | geographic_event | Geo_FullName→location, Geo_Lat/Long→coordinates |
| `EIAParser` | JSON/CSV | timeseries | series_id→id, period→timestamp, area→location |
| `FREDParser` | JSON/CSV | timeseries | series_id→id, date→timestamp |
| `OPECParser` | CSV | timeseries | country→name, year/month→timestamp |
| `AISParser` | JSON/CSV | vessel | mmsi→id, lat/lon→coordinates |
| `PortCongestionParser` | CSV | port | port_name→name, congestion→attributes |
| `WorldPortIndexParser` | CSV | port | port_name→name, unlocode→location_code |
| `CommodityPriceParser` | JSON/CSV | commodity | commodity→name, price→attribute |
| `CommodityFuturesParser` | JSON/CSV | futures_contract | symbol+contract→id |
| `OFACParser` | CSV | sanctioned_entity | uid→id, sdnType→entity_type |
| `UNSanctionsParser` | XML/CSV | sanctioned_entity | id→id, regime→relationships |
| `WorldBankParser` | JSON/CSV | development_indicator | indicator+country→id |
| `UNComtradeParser` | JSON/CSV | trade_flow | reporter+commodity→id |
| `KaggleParser` | CSV | kaggle_dataset | id→id, size→attribute |

### Canonical Schema

```python
CanonicalSchema(
    entity_type: str,             # event, vessel, port, timeseries, etc.
    entity_id: str,               # Unique ID from source
    entity_name: str,             # Human-readable name
    timestamp: str,               # ISO 8601
    timestamp_precision: str,     # year/month/day/hour/minute/second
    latitude: float | None,       # Decimal degrees
    longitude: float | None,
    location_name: str | None,
    location_code: str | None,    # ISO country code, UNLOCODE
    attributes: dict,             # Dataset-specific key-value pairs
    relationships: list[dict],    # [{type, target_id}, ...]
    source: str,                  # Source name (gdelt, eia, ofac, ...)
    source_record_id: str | None,
    confidence: float | None,     # [0, 1]
    metadata: dict,               # Provenance, version, parser info
)
```

`CanonicalRecord` methods: `to_dict()`, `from_dict()`, `validate()` (required fields, lat/lng range, confidence range), `to_dataframe_row()` (flattens attributes with `attr_` prefix).

---

## 8. Dataset Registration

### Pipeline

```
processed_path → load_dataframe → compute_statistics → profile → feature_summary
                                    ↓
                      missing_values → distributions → preview
                                    ↓
                      checksum → schema_inference → feature_columns
                                    ↓
                      DatasetCatalog.register() → ManifestGenerator → result
```

### Statistics Computed
- General: row_count, column_count, memory_bytes, missing_cells, total_cells, duplicate_count
- Column types: numerical_columns, categorical_columns, boolean_columns, datetime_columns
- Per-column: dtype, cardinality, cardinality_ratio, missing_count, missing_rate
- Distributions: numerical (min/max/mean/std/p25/p50/p75), categorical (top-10 values), temporal (min/max/range_days)

### Feature Classification
Auto-detects targets (`target`, `label`, `criticality_score`), geographical (lat/lon/geo), temporal (datetime), entity (id/uuid/code/mmsi), numerical (numeric dtypes), categorical (low-cardinality objects).

### Metadata Generated
- **Catalog Entry**: PostgreSQL `ml.datasets` row (UUID, name, type, source, description, tags)
- **Manifest**: `dataset.yaml` (dataset_name, version, source, download_date, file_count, total_size_bytes, checksum, schema_hash, row_count, column_count, license)
- **Registration ID**: UUID from catalog

### RegistrationFlow Orchestrator
```python
await flow.process_raw_to_registered(source, version, raw_path, parser)
await flow.process_registered_to_builder(dataset_name, version, builder_name)
await flow.get_registration_status(dataset_name)
await flow.list_registered_datasets(source=None)
```

---

## 9. CLI Reference

The `ml` CLI (`cli/main.py`) with 9 commands, 17 parsers in `PARSER_MAP`, 12 builders in `BUILDER_MAP`.

### Commands

| Command | Arguments | Description |
|---------|-----------|-------------|
| `ml download` | `<source> [--version V] [--dry-run] [--force]` | Download from registered source |
| `ml list` | `<sources\|datasets\|versions> [--category C] [--source S]` | List registry/datasets/versions |
| `ml describe` | `<source_or_dataset>` | Show source or dataset metadata |
| `ml parse` | `<source> <input_path> [--version V] [--output-dir D]` | Parse raw data with source's parser |
| `ml register` | `<dataset_name> [--source S] [--version V] [--path P]` | Register processed dataset in catalog |
| `ml build` | `<dataset_name> [--builder NAME]` | Build dataset using builder |
| `ml validate` | `<dataset_name> [--version V]` | Run validation checks |
| `ml info` | _(none)_ | Show lake stats and system config |
| `ml config` | `[--show] [--key K --value V]` | Show or set configuration |

### Examples
```bash
ml download gdelt-events --version 2024-01
ml list sources --category energy
ml describe gdelt-events
ml parse gdelt-events ./datasets/raw/gdelt/events.export.txt
ml register risk_dataset --source gdelt-events --version 1.0
ml build risk_dataset --builder energy_infrastructure
ml validate risk_dataset
ml info
ml config --show
```

### Available Builders
`news_articles`, `energy_infrastructure`, `knowledge_graph`, `risk_signals`, `commodity_prices`, `digital_twin`, `procurement`, `spr`, `events`, `entity_relationships`, `graph_embeddings`, `hybrid`.

---

## 10. API Reference

All endpoints under `/api/v1/ml/acquisition` (FastAPI router at `routers/data_acquisition.py`).

### Endpoints

| # | Method | Path | Description |
|---|--------|------|-------------|
| 1 | `POST` | `/download` | Download dataset from registered source |
| 2 | `POST` | `/parse` | Parse raw data using source's parser |
| 3 | `POST` | `/register` | Register processed dataset in catalog |
| 4 | `POST` | `/build` | Build dataset from registered data |
| 5 | `GET` | `/sources` | List registered sources (`?category=energy`) |
| 6 | `GET` | `/sources/{name}` | Get source definition with schema |
| 7 | `GET` | `/datasets` | List registered datasets (`?source=gdelt`) |
| 8 | `GET` | `/datasets/{name}` | Get dataset details + versions + manifest |
| 9 | `GET` | `/datasets/{name}/statistics` | Get computed statistics |
| 10 | `GET` | `/datasets/{name}/preview` | Get preview rows + schema |
| 11 | `POST` | `/datasets/validate` | Run schema/statistics/integrity checks |
| 12 | `GET` | `/lake/stats` | Get data lake statistics |
| 13 | `GET` | `/resolve/{dataset_spec}` | Resolve dataset to canonical path |
| 14 | `GET` | `/health` | Health check |

### Request Schemas

**POST /download**: `{ source, version?, force?, dry_run? }`
**POST /parse**: `{ source, input_path, version?, output_dir? }`
**POST /register**: `{ dataset_name, source, version, path }`
**POST /build**: `{ dataset_name, builder_name?, version? }`
**POST /datasets/validate**: `{ dataset_name, version? }`

---

## 11. Research Integration

### DatasetResolver
Three-tier resolution strategy in `data_acquisition/research_integration.py`:
1. Check `SourceRegistry` (23 pre-registered sources)
2. Check `DatasetCatalog` (PostgreSQL-registered datasets)
3. Treat as filesystem path if starts with `"."`

### `experiment.dataset="name"` Resolution

```python
from data_acquisition.research_integration import DatasetResolver

resolver = DatasetResolver()
resolved = await resolver.resolve_dataset("gdelt-events")
# Returns: { path, source, display_name, description, category,
#            schema (58 fields), version, features, target,
#            license, citation, tags }
```

### Experiment Enrichment

```python
resolver = ExperimentDatasetResolver()
config = await resolver.prepare_experiment(
    experiment_name="energy_risk_v1",
    config={"dataset": "eia-petroleum", "model": {"type": "xgboost"}},
)
# config now enriched with:
#   dataset.name = "eia-petroleum"
#   dataset.version = "1.0"
#   dataset.path = "./datasets/raw/eia-petroleum/1.0"
#   dataset.feature_names = [period, duoarea, value, ...]
```

### Dataset Cards

```python
card = await resolver.get_dataset_card("ofac-sanctions")
# Returns: name, display_name, description, category, version,
#          source, path, schema, feature_count, features, target,
#          license, citation, tags, update_frequency, connector_type
```

### Notebook Usage
```python
# In Jupyter:
import asyncio
from data_acquisition.research_integration import DatasetResolver
resolver = DatasetResolver()
datasets = asyncio.run(resolver.list_available_datasets())
resolved = asyncio.run(resolver.resolve_dataset("eia-petroleum"))
df = pd.read_parquet(resolved["path"])
```

---

## 12. Future Integration

### Adding a New Source
1. Add `SourceDefinition` to `DATASET_REGISTRY` in `source_registry.py`
2. Create parser in `data_acquisition/parser/sources/my_source.py` extending `BaseParser`
3. Register in: `parser/sources/__init__.py`, `cli/main.py` `PARSER_MAP`, `routers/data_acquisition.py` `_PARSER_MAP`

### Adding a New Connector
Implicit in `connector_type` field. Extend `DownloadManager` for new protocols (s3, gcs, kafka).

### Adding a New Dataset Builder
1. Create builder in `datasets/builders/my_builder.py` extending `BaseDatasetBuilder`
2. Implement `get_dependencies()`, `build()`, `transform()`
3. Register in `builders/__init__.py` and `cli/main.py` `BUILDER_MAP`

### Extending Canonical Schema
- Add fields to `CanonicalSchema` dataclass
- Update `to_dict()`, `from_dict()`, `validate()`, `to_dataframe_row()`
- All parsers inherit new fields automatically

### Integration Points
| Integration | Module | Approach |
|-------------|--------|----------|
| Kafka Stream | `data_acquisition/` | Add `KafkaConnector` using `aiokafka` |
| S3/GCS | `download_manager.py` | Add cloud storage client in `download()` |
| MLflow | `datasets/` | Log dataset stats as MLflow artifacts |
| DVC | `datasets/` | Track dataset versions with DVC |
| Webhook | `routers/data_acquisition.py` | Add POST callback on registration complete |
| Custom Auth | `download_manager.py` | Inject auth headers from `DownloadConfig.headers` |
