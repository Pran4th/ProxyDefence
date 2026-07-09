# Data Source Status

## Live and registered (Tier 1 — keyless)

- **eu-sanctions** — EU FSF sanctions list (public token, no signup). 5,994 canonical entities.
- **opensanctions** — OpenSanctions.org bulk export, filtered to Iran/Russia/Syria/N.Korea/Belarus/UAE/Saudi/Iraq/India + sanctioned schema types. 49,073 rows from a 1.3M-row scan.
- **global-fuel-prices** — WFP fuel prices, USD-normalized via World Bank `PA.NUS.FCRF` (annual average official rate). AFN and SOS have zero World Bank coverage and are left null, not fabricated.

## Live and registered (Tier 2 — keyed, keys in `.env`)

- **eia-crude-stocks** — EIA v2 API (`EIA_API_KEY`). Weekly U.S. crude oil stock levels, national total + 5 PADD regions, including SPR-specific stocks (`WCSSTUS1`). 2,592 records, 2021-present.
- **crude-price-api** — crudepriceapi.com (`CRUDE_PRICE_API_KEY`). Free tier only exposes `/latest` (spot price + 2-month forward predictions); `recent_prices`/`past_week`/etc all 404 without a paid plan. Capped at 100 requests/month, so `scripts/ingest_crude_price_api.py` makes exactly one call per run and accumulates a real time series across repeated runs rather than polling.
- **ais-chokepoints** — AISstream.io websocket (`AISSTREAM_API_KEY`). Real-time vessel PositionReports scoped to 7 chokepoints (Hormuz, Bab-el-Mandeb, Suez, Malacca, Turkish Straits, Gibraltar, Panama). Only `PositionReport` messages are subscribed to, so vessel name/type/dimensions (from the separate `ShipStaticData` message type) are frequently null — this is a live position snapshot, not a full vessel registry.
- **NewsData.io** (`NEWSDATA_API_KEY`) — wired into `services/ingest-service` as a second live source alongside GNews, publishing to the same `raw_articles` Kafka topic with an identical schema. Free tier locks full article `content` behind a paywall placeholder string (`"ONLY AVAILABLE IN PAID PLANS"`); the fetcher detects and falls back to `description`.

## Still blocked

- **NGA World Port Index** — no key provided yet. `WorldPortIndexParser` exists and is proven against the alternate `global_port_traffic` schema (already registered as `global-ports`), but the canonical NGA text-file export requires a data request.

## Notes for future runs

- `crude-price-api` and `ais-chokepoints` are designed to be re-run periodically (cron/scheduler) — both scripts append + dedupe against the existing processed CSV rather than overwriting, so repeated runs build up a genuine time series instead of a single thin snapshot.
- All Tier 2 scripts read their key from the environment (`EIA_API_KEY`, `CRUDE_PRICE_API_KEY`, `AISSTREAM_API_KEY`) — never hardcoded in source.
