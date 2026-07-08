# SPR Decision Intelligence — Validation Suite

## Test Coverage

**Total: 16 tests** across 9 categories

### 1. Health & Schema (2 tests)
- `test_spr_health` — Verify health endpoint returns all metrics
- `test_spr_database_schema` — Verify 13 SPR tables exist

### 2. Facilities (2 tests)
- `test_init_facilities` — Initialize facilities from seed data
- `test_list_facilities` — List facilities with UUID, name, status

### 3. Inventory (1 test)
- `test_inventory_history` — Fetch inventory time-series

### 4. Policies (2 tests)
- `test_list_policies` — List policies (min 1 from seed)
- `test_create_policy` — Create custom policy

### 5. Demand (1 test)
- `test_compute_demand` — Compute national/regional demand

### 6. SPR Analysis — Release Planner (4 tests)
- `test_run_analysis_minimal` — Minimal params, verify all output sections
- `test_run_analysis_with_supply_gap` — Explicit supply gap, geopolitical crisis
- `test_run_analysis_aggressive` — War/conflict with aggressive strategy
- `test_run_analysis_invalid_strategy` — Graceful handling of invalid strategy

### 7. Runs (3 tests)
- `test_list_runs` — List optimization runs
- `test_get_run` — Get run by UUID
- `test_get_run_not_found` — 404 for non-existent UUID

### 8. Executive Cards (1 test)
- `test_acknowledge_card_not_found` — 404 for non-existent card

### 9. Decision Timeline (1 test)
- `test_decision_timeline_phases` — Verify 5-phase timeline structure

## Run Command

```bash
pytest tests/test_spr_validation.py -v --asyncio-mode=auto
```

## Integration Verification

- SPR endpoints respond under `/api/v1/intelligence/procurement/spr/`
- Schema bootstraps on startup via `db.py`
- Facilities initialize from `strategic_petroleum_reserves` seed data
- Policies seed 3 defaults (default, conservative, aggressive)
- Demand model reads from Digital Twin demand profiles
- Decision timeline produces 5 phases (now, 24h, 72h, 7d, 30d)
- Recommendations generate 4 card types (release, procurement, refill, policy)
- Cost analysis covers release, refill, transport, emergency procurement, economic impact
- Executive card acknowledgement workflow functions
