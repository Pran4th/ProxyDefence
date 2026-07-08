# ProxyDefence Local Development — Progress Summary

## Status: ALL STAGES VALIDATED

## Bugs Fixed (Round 4)

### Bug 1: Embedding Foreign Key Violation
- **Root Cause**: Embedding consumer used `article.get("id")` (SHA-256 hash of URL) as the FK value for `article_embeddings.article_id`, which references `processed_articles.id` (SERIAL PK). The hash never matches the DB serial ID.
- **Fix**: Embedding consumer now looks up `processed_articles.id` by `dedupe_key` before inserting the embedding.
- **Files Modified**:
  - `services/embedding-service/consumer.py` — `store_embedding()` now accepts `dedupe_key`, queries DB for serial id; caller passes `article.get("dedupe_key")` instead of `article.get("id")`
- **Verification**: 46 embeddings, 0 orphan FK violations. All FK constraints pass.

### Bug 2: `install_signal_handlers` not exported
- **Root Cause**: `backend/shared/kafka/__init__.py` did not export `install_signal_handlers`, causing all 3 consumers to crash on startup with `ImportError`.
- **Fix**: Added `install_signal_handlers` to imports and `__all__`.
- **Files Modified**:
  - `backend/shared/kafka/__init__.py`

### Bug 3: Consumer launch in start-local.ps1
- **Root Cause**: Consumer launch code used wrapping PowerShell here-string (PS 5.1 stream redirection bug); log files not created for consumers.
- **Fix**: Replaced wrapping PowerShell with direct `Start-Process` on `python.exe` using `-RedirectStandardOutput` / `-RedirectStandardError` with separate log files.
- **Files Modified**:
  - `scripts/dev/start-local.ps1` — consumer launch section

### Bug 4: Embedding consumer `create_pool` → `get_pool`
- **Root Cause**: Embedded service consumer tried to import `create_pool` which doesn't exist in `db.py` (uses `Pool` auto-init).
- **Fix**: Changed import to `get_pool` which returns the lazy-initialized pool.
- **Files Modified**:
  - `services/embedding-service/consumer.py`

## Verified: "Missing Articles" was a False Alarm

Previous tests showed `Articles in DB: 5` but this was a `limit=5` query. The actual total was 46 articles. Full verification confirms all 10 GNews articles are stored correctly.

## Full Pipeline Validation Results

| Stage | Status | Details |
|-------|--------|---------|
| Infrastructure | ✅ | PostgreSQL, Kafka, Elasticsearch healthy |
| All 7 API services | ✅ | All health endpoints pass |
| Kafka topics | ✅ | raw_articles: 140 msgs, processed_articles: 280 msgs |
| ML Consumer | ✅ | Processes articles, publishes enriched output |
| DB Consumer | ✅ | Upserts to PostgreSQL, indexes to Elasticsearch |
| Embedding Consumer | ✅ | Generates embeddings, FK violations resolved |
| PostgreSQL | ✅ | 46 articles, 231 entities, 46 sentiments, 11 rels, 40 events, 46 embeddings |
| FK Integrity | ✅ | 0 orphan FK violations across all child tables |
| Elasticsearch | ✅ | 32 results for "war" query |
| Semantic Search | ✅ | 5 results for "threat" query |
| Copilot | ✅ | threat=critical, 5 articles, 3 entities, 362-char summary |
| Frontend | ✅ | Serves on port 8080 |
| Energy Service | ✅ | 31 locations, 22 ports, 15 oil fields |
| ML Platform | ✅ | 4 feature definitions |

## Remaining Technical Debt (Non-Blocking)

1. **`image` field name mismatch**: GNews API returns `image`, published as `image` in Kafka message, inserted into `processed_articles.image_url` DB column. Works correctly but naming inconsistency.
2. **Consumer log capture not robust**: When consumers are launched via batch files (not start-local.ps1), stdout goes to hidden console window, not log files. start-local.ps1 uses proper `Start-Process -RedirectStandardOutput`.
3. **`POSTGRES_PASSWORD` mismatch**: `.env` has `change-me` but `CLAUDE.md` documents `admin123`. Should sync documentation with actual config.
4. **No trained ML models**: ML Platform has 0 trained models (needs training pipeline to be run).
5. **Database-service uses psycopg2 (sync)**: All other async services use asyncpg. Documented inconsistency.

## Architecture Diagrams

- Complete pipeline diagram: `docs/PIPELINE_VALIDATION.md`
- Kafka topic flow: `docs/PIPELINE_VALIDATION.md`
- Database write flow: `docs/PIPELINE_VALIDATION.md`
- Entity/Embedding/Search/Copilot lifecycles: `docs/PIPELINE_VALIDATION.md`
- Failure modes and recovery: `docs/PIPELINE_VALIDATION.md`
