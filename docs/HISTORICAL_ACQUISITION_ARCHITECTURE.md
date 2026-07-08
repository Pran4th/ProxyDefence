# Historical Acquisition Architecture

## Overview

The historical data acquisition framework is a modular, event-driven pipeline for ingesting, parsing, normalizing, validating, registering, and making available multi-source intelligence datasets. It lives entirely within `services/ml-platform/data_acquisition/` and is designed for deterministic, reproducible, checkpointed acquisition.

## Module Map (25 files)

```
data_acquisition/
├── config.py                  # DataAcquisitionConfig — base_dir, retry, chunk settings
├── source_registry.py         # SourceDefinition model + DATASET_REGISTRY (22 sources)
├── download_manager.py        # DownloadManager — async HTTP(S) download with resume, retry, checksum, decompression
├── lake.py                    # DataLake — filesystem abstraction: raw/processed/normalized/features/training/registry dirs
├── manifest.py                # DatasetManifest + ManifestGenerator — YAML manifests with checksums
├── canonical.py               # CanonicalRecord — normalized entity schema (entity_type, id, geo, confidence, etc.)
├── registration.py            # DatasetRegistrationPipeline — stats, profiling, schema inference, catalog registration
├── registration_flow.py       # RegistrationFlow — orchestration: raw → parse → register → build
├── research_integration.py    # DatasetResolver + ExperimentDatasetResolver — resolve dataset specs to paths
├── parser/
│   ├── base.py                # BaseParser ABC — parse, parse_file, discover_schema, validate, to_canonical
│   └── sources/
│       ├── gdelt.py           # GDELTEventParser, GDELTMentionParser, GKGParser, GCAMParser
│       ├── eia.py             # EIAParser — US Energy Information Administration
│       ├── world_bank.py      # WorldBankParser — World Bank Development Indicators
│       ├── un_comtrade.py     # UNComtradeParser — international trade statistics
│       ├── sanctions.py       # OFACParser + UNSanctionsParser
│       ├── opec.py            # OPECParser — monthly oil production
│       ├── kaggle.py          # KaggleParser — competition and community datasets
│       ├── commodity.py       # CommodityPriceParser + CommodityFuturesParser
│       └── ais.py             # AISParser + PortCongestionParser + WorldPortIndexParser
└── gdelt_pipeline/
    ├── master_file_reader.py  # MasterFileReader — fetches/parses GDELT masterfilelist.txt
    ├── filter.py              # GDELTFilter — date range + dataset type filtering
    ├── downloader.py          # GDELTDownloader — concurrent download with MD5 verification + resume
    ├── parser.py              # GDELTParser — dispatches to GDELTEventParser/MentionParser/GKGParser
    ├── registration.py        # GDELTRegistration — batch registration of parsed GDELT datasets
    ├── validation.py          # GDELTValidator — file, parsed CSV, and registration validation checks
    ├── report.py              # ReportGenerator — Markdown/JSON validation reports
    └── pipeline.py            # GDELTPipeline — orchestrates discover → filter → download → parse → register
```

## Data Flow

```
SourceRegistry (22 sources defined)
    ↓
GDELTPipeline.run()
    ├── Stage 1: Discover
    │   └── MasterFileReader.fetch() → MasterFileResult (1.17M entries, 2015-02-18 to present)
    ├── Stage 2: Filter
    │   └── GDELTFilter.filter() by date range + dataset type
    ├── Stage 3: Download
    │   └── GDELTDownloader.download_batch() → ZIP files with MD5 verification
    ├── Stage 4: Parse
    │   └── GDELTParser.parse_file() → Canonical CSV (entity_type/id, geo, confidence)
    │       ├── GDELTEventParser  → 61 fields → canonical events
    │       ├── GDELTMentionParser → 13 fields → canonical mentions
    │       └── GKGParser         → GKG records with themes/locations/persons
    └── Stage 5: Register
        └── GDELTRegistration.register_batch()
            └── DatasetRegistrationPipeline.register_dataset()
                ├── Stats computation (row/col/missing/duplicates)
                ├── Profiling
                ├── Feature classification
                ├── Manifest generation (dataset.yaml)
                └── Catalog entry creation (ml.dataset_catalog)

RegistrationFlow.process_raw_to_registered()
    ├── Parser → Canonical CSV
    └── RegistrationPipeline → Catalog entry + Manifest + Stats

DatasetResolver
    ├── Known source (from registry) → return path/schema
    ├── Catalog entry (previously registered) → return path
    └── Local file path → return path
```

## Source Registry

22 sources across 7 categories:

| Category | Sources |
|----------|---------|
| Geopolitical | gdelt-events, gdelt-mentions, gdelt-gkg, gdelt-gcam |
| Energy | eia-petroleum, eia-natural-gas, eia-coal, eia-electricity, fred-oil-prices, fred-gas-prices, opec-production, opec-exports |
| Shipping | ais-global, port-congestion, world-port-index |
| Commodity | commodity-prices, commodity-futures |
| Sanctions | ofac-sanctions, un-sanctions |
| Economics | world-bank-indicators, un-comtrade |
| Other | kaggle-competition, kaggle-dataset |

## Key Design Decisions

1. **Async-first**: All I/O uses `asyncio` + `aiohttp` for concurrent downloads
2. **Checkpointed**: Every download version is stored in `raw/<source>/<version>/` with `_metadata.json`
3. **Immutable versions**: Once a dataset version is registered, it is never modified
4. **Canonical schema**: All sources normalized to `CanonicalRecord` (entity_type, entity_id, timestamp, geo, confidence)
5. **Deterministic**: Same version + same source = same data (MD5/SHA256 verified)
6. **Graceful degradation**: Optional deps (DVC, MLflow, SHAP) degrade to warnings
7. **Self-describing**: Every dataset has a `dataset.yaml` manifest with checksums, schema, stats

## Key Files

| File | Lines | Role |
|------|-------|------|
| `gdelt.py` | 896 | 4 parsers: GDELTEventParser, GDELTMentionParser, GKGParser, GCAMParser |
| `source_registry.py` | 574 | SourceDefinition model + 22-source DATASET_REGISTRY |
| `download_manager.py` | 449 | Async download with resume, checksum, decompression |
| `pipeline.py` | 327 | Full 5-stage GDELT pipeline orchestrator |
| `registration.py` | 339 | Dataset registration pipeline with stats, profiling, manifest |
| `lake.py` | 171 | DataLake filesystem abstraction |
| `canonical.py` | 128 | CanonicalRecord model with validation |
| `manifest.py` | 115 | YAML manifest generation and verification |
| `research_integration.py` | 187 | DatasetResolver for experiment setup |
| `master_file_reader.py` | 134 | GDELT master file list fetcher |

## Bugs Fixed

1. **NUL byte crash** (`gdelt.py:228`): GDELT export files contain binary NUL bytes that crash `csv.reader`. Fixed with binary read + NUL filter generator.
2. **`Path.suffixes_str()`** (`pipeline.py:211`): `Path` has no `suffixes_str()` method. Fixed with `''.join(fp.suffixes)`.

## Infrastructure Dependencies

| Service | Port | Required For |
|---------|------|-------------|
| PostgreSQL | 5432 | Dataset registration (ml.dataset_catalog) |
| Energy Service | 8006 | Data source for ML Platform (optional) |
| Internet | - | GDELT master file + download URLs |

## Next Sources to Implement

Based on DATASET_REGISTRY, the following parsers are defined but not yet fully integrated into the pipeline:
- eia.py, world_bank.py, un_comtrade.py, sanctions.py, opec.py, kaggle.py, commodity.py, ais.py
