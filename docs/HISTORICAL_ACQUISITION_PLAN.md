# Historical Data Acquisition Plan

## Current State

The GDELT pipeline is fully operational end-to-end:
- **Master file reader**: 1,174,988 GDELT entries spanning 2015-02-18 through 2026-07-06
- **Filter**: Date range + dataset type filtering
- **Download**: Concurrent download with MD5 verification + resume support
- **Parser**: 4 GDELT parsers (events/mentions/GKG/GCAM) with NUL byte fix
- **Registration**: PostgreSQL catalog registration with stats + profiling + manifest
- **Report**: Markdown/JSON validation report generation

## Phase 1: GDELT Multi-Year Ingestion

### Strategy
- **Incremental date-based batches** — one day at a time, oldest to newest
- **Checkpointed** — each day's version is immutable once registered
- **Deterministic** — same date + same source = same data (MD5 verified)
- **Resumable** — already-downloaded files skip via MD5 match

### Batch Schedule

| Batch Size | Est. Records | Est. Time | Frequency |
|-----------|-------------|-----------|-----------|
| 1 day (3 files) | ~15,000 events + mentions + GKG | ~2 min | Per batch |
| 1 week (21 files) | ~105,000 records | ~15 min | Optimal |
| 1 month (~90 files) | ~450,000 records | ~1 hour | Large batch |
| 1 year (~1095 files) | ~5.5M records | ~12 hours | Full year |

### Daily GDELT File Count
- Events (export.CSV.zip): 391,661 files
- Mentions (mentions.CSV.zip): 391,661 files
- GKG (gkg.csv.zip): 391,666 files
- **Total: 1,174,988 files across all 11+ years**

### Storage Estimates
- Per event file (compressed): ~150KB
- Per event file (parsed CSV): ~800KB
- Total raw storage: ~180 GB compressed
- Total parsed storage: ~950 GB
- With dedup/indexing: ~1.2 TB

### Recommended Approach
1. **Backfill oldest (2015-2018)** — weekly batches, verify checkpointing
2. **Backfill middle (2019-2022)** — weekly batches, monitor throughput
3. **Backfill recent (2023-2026)** — daily batches
4. **Ongoing** — daily cron for latest day's data

## Phase 2: Source Expansion

After GDELT, extend to remaining DATASET_REGISTRY sources:

| Priority | Source | Type | Est. Size | Dependency |
|----------|--------|------|-----------|------------|
| 1 | OFAC Sanctions | CSV download | < 100 MB | None |
| 2 | OPEC Production | CSV download | < 50 MB | None |
| 3 | World Bank Indicators | REST API | Moderate | API key |
| 4 | EIA Petroleum/NatGas | REST API | Moderate | API key |
| 5 | FRED Oil/Gas Prices | REST API | Small | API key |
| 6 | UN Comtrade | REST API | Large | API key |
| 7 | World Port Index | CSV download | < 10 MB | None |
| 8 | AIS Shipping | REST API | Very Large | Provider key |
| 9 | Port Congestion | CSV/API | Moderate | Provider |
| 10 | Kaggle Datasets | API | Variable | Kaggle API key |

### Implementation Requirements

Each source needs:
1. Parser implementation (most already in `data_acquisition/parser/sources/`)
2. Integration into the acquisition pipeline (or standalone)
3. Registration in the dataset catalog
4. Quality validation report

## Infrastructure Requirements

| Service | Status | Notes |
|---------|--------|-------|
| PostgreSQL | ✅ Running | `admin:change-me@localhost:5432/defenseintel` |
| Disk (raw) | ⚠️ Need ~200 GB | GDELT only, external SSD or NAS |
| Disk (parsed) | ⚠️ Need ~1 TB | Parquet + CSV storage |
| Network | ✅ 150KB/sec per file | ~2 min per day's 3 files |
| Energy Service | ❌ Not running | Needed for synthetic data fallback |

## Bugs Fixed (this session)

| Bug | File | Fix |
|-----|------|-----|
| NUL byte crash | `gdelt.py:228` | Binary read + NUL filter + line ending normalize |
| `Path.suffixes_str()` | `pipeline.py:211` | Changed to `''.join(fp.suffixes)` |
| ZIP not decompressed | `pipeline.py:204-215` | Added extract step before parse |
| CSV round-trip type loss | `canonical.py` | `_none_if_empty` converts empty strings to None |
| String confidence/lat/lon | `canonical.py` | `_none_if_empty` converts numeric strings to float |
| Registration dataset_type | `registration.py` | Used short type name (e.g. "events") |
| Missing `datasets` package | `datasets/` | Created `catalog.py`, `statistics.py`, `profiling.py` |

## Next Steps

1. **Run a 1-week backfill**: `python -m cli ml gdelt --start 2015-02-18 --end 2015-02-24 --max-per-type 20`
2. **Verify checkpointing**: re-run same range, confirm no duplicates
3. **Generate performance report**: throughput, disk usage, error rates
4. **Scale to 1 month**: monitor for edge cases
5. **Add OFAC sanctions** as second source (simplest next source)
