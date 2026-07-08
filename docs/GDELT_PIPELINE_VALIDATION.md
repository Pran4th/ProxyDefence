# GDELT Pipeline Validation Report

**Generated:** 2026-07-06T07:42:26.892683+00:00
**Version:** 20240101
**Date Range:** 2024-01-01 → 2024-01-01
**Overall Status:** completed
**Total Duration:** 46.4s

## Summary

| Metric | Value |
|---|---|
| Files Discovered | 1174880 |
| Files Filtered | 3 |
| Files Downloaded | 3 |
| Total Bytes | 3.2 MB |
| Records Parsed | 4218 |
| Records Failed | 0 |
| Throughput | 90.92 rec/s |
| Stages | 4 ok / 0 failed / 1 partial |

## Stage Results

### ✅ Discover

- **Status:** completed
- **Duration:** 37.0s
- **total_discovered:** `1174880`
- **by_type:** `{'export.CSV.zip': 391625, 'mentions.CSV.zip': 391625, 'gkg.csv.zip': 391630}`

### ✅ Filter

- **Status:** completed
- **Duration:** 100ms
- **total_filtered:** `3`
- **by_type:** `{'export.CSV.zip': 1, 'mentions.CSV.zip': 1, 'gkg.csv.zip': 1}`

### ✅ Download

- **Status:** completed
- **Duration:** 1.6s
- **completed:** `3`
- **failed:** `0`
- **total_bytes:** `3399093`

### ✅ Parse

- **Status:** completed
- **Duration:** 890ms
- **records_parsed:** `4218`
- **records_failed:** `0`
- **canonical_valid:** `4218`
- **canonical_invalid:** `0`

### ⚠️ Register

- **Status:** partial
- **Duration:** 0ms
- **registered:** `0`
- **failed:** `0`

## Verification Steps

To independently verify the downloaded data:

1. **Check GDELT master file list:**
   ```bash
   curl -s http://data.gdeltproject.org/gdeltv2/masterfilelist.txt | head -20
   ```
2. **Verify a specific file checksum:**
   ```bash
   md5sum datasets/raw/gdelt/events/<version>/*.zip
   ```
3. **Compare with GDELT master list entry for the same file**
4. **Inspect parsed CSV output:**
   ```bash
   head -5 datasets/processed/gdelt/events/<version>/*.csv
   ```
5. **Count records:**
   ```bash
   wc -l datasets/processed/gdelt/events/<version>/*.csv
   ```
