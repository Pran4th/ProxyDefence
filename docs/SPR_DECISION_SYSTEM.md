# SPR Decision Intelligence System

Strategic Petroleum Reserve (SPR) management module — release planning, refill optimization, policy enforcement, and executive decision support integrated with the Adaptive Procurement Orchestrator and Supply Chain Digital Twin.

## Architecture

```
Digital Twin Simulation Run
    ↓ supply_gap_bpd, scenario config
SPR Engine (run_optimization)
    ├── Demand Model → national/regional demand from DT profiles
    ├── Policy Engine → min_reserve, max_daily_release, emergency_only
    ├── Drawdown Calculator → per-facility release schedules
    ├── Gap Estimator → remaining shortfall after SPR coverage
    ├── Facility Selector → order by strategy (conservative/aggressive/...)
    ├── Refill Planner → post-crisis refill schedule
    ├── Cost Analyzer → release/refill/transport/economic impact costs
    ├── Decision Timeline → Now / +24h / +72h / +7d / +30d
    └── Recommendation Generator → executive decision cards
        ├── Release Cards
        ├── Procurement Cards (links to Procurement Orchestrator)
        ├── Refill Cards
        └── Policy Cards
```

## Schema

13 tables in `energy.` schema:

| Table | Purpose |
|-------|---------|
| `spr_facilities` | Reserve facilities synced from `strategic_petroleum_reserves` |
| `spr_inventory` | Time-series inventory snapshots per facility |
| `spr_capacity` | Historical capacity records |
| `spr_release_runs` | Optimization run metadata |
| `spr_release_plans` | Per-facility release schedules |
| `spr_refill_plans` | Post-crisis refill schedules |
| `spr_recommendations` | Executive decision cards |
| `spr_policy_constraints` | Configurable release policies |
| `spr_consumption_forecasts` | Demand projections |
| `spr_distribution` | Distribution routing plans |
| `spr_cost_analysis` | Cost breakdowns per run |
| `spr_assumptions` | Assumptions used in each run |
| `spr_decision_timeline` | Normalized timeline entries |

## Core Engine

**`services/procurement/spr_engine.py`** — `SPREngine` class:

### `initialize_facilities()`
Syncs SPR facilities from `strategic_petroleum_reserves` seed data. Creates `spr_facilities` records and initial inventory snapshots. Idempotent (upserts on name).

### `compute_demand()`
Reads Digital Twin demand profiles, computes national/regional demand, strategic reserve requirement, and coverage days. Returns demand model used by optimization.

### `run_optimization(params)`
Main entry point. Accepts disruption parameters, supply gap, strategy, policy. Returns complete decision package:

- **drawdown_plan**: Day-by-day inventory trajectory
- **release_plan**: Per-facility release schedule with daily volumes
- **refill_plan**: Post-crisis refill schedule with daily volumes and duration
- **decision_timeline**: 5-phase timeline (Now → +24h → +72h → +7d → +30d)
- **recommendations**: Executive decision cards with cost/operational impact
- **cost_analysis**: Total cost breakdown (release, refill, transport, emergency procurement, economic impact)

### Strategies

| Strategy | Behavior |
|----------|----------|
| `conservative` | Minimize release, preserve maximum reserve | 
| `aggressive` | Maximize release to cover gap |
| `balanced` | Moderate release, moderate preservation |
| `economic` | Prioritize economic stability over reserve |
| `strategic_preservation` | Only release to protect critical infrastructure |
| `critical_infrastructure_first` | Reserve capacity for critical infrastructure |

### Policies (seed)

| Policy | Min Reserve | Max Daily Release | Emergency Only | Strategic Preservation |
|--------|-------------|-------------------|----------------|----------------------|
| default | 20% | 500,000 bpd | false | false |
| conservative | 50% | 300,000 bpd | true | true |
| aggressive | 10% | 1,000,000 bpd | false | false |

## API Endpoints

All endpoints under `/api/v1/intelligence/procurement/spr/`:

| Method | Path | Description |
|--------|------|-------------|
| POST | `/init` | Initialize facilities from seed data |
| GET | `/facilities` | List SPR facilities |
| GET | `/inventory` | Inventory time-series |
| GET | `/policies` | List policies |
| POST | `/policies` | Create policy |
| GET | `/demand` | Compute demand |
| POST | `/analyze` | Run full SPR optimization |
| GET | `/runs` | List optimization runs |
| GET | `/runs/{uuid}` | Get run details |
| POST | `/executive-cards/{uuid}/ack` | Acknowledge card |
| GET | `/health` | System health |

## Integration Points

- **Digital Twin**: Reads demand profiles, simulation runs for supply gap
- **Procurement Orchestrator**: Procurement cards link to procurement runs
- **Copilot**: SPR advisor queries available via `/copilot/query`
- **Frontend**: 5-tab dashboard at `/intelligence/spr`

## Executive Decision Timeline

The 5-phase timeline enables decision-making at escalating horizons:

1. **Now** — Immediate emergency release, activate emergency procurement
2. **+24 Hours** — Ramp up to max daily release, mobilize logistics
3. **+72 Hours** — Strategic release from secondary facilities, international coordination
4. **+7 Days** — Refill planning begins, assess long-term supply alternatives
5. **+30 Days** — Full refill schedule, policy review, strategic repositioning

Each phase includes: action trigger, daily release rate, cumulative release, remaining inventory, and specific operational directives.
