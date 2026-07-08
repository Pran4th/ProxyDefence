"""Digital Twin API — simulation execution, scenario management, network graph, and flow results."""

import json
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from db import get_pool
from backend.shared.logging_config import get_logger
from services.digital_twin.engine import SimulationEngine
from services.digital_twin.graph import NetworkGraph
from services.digital_twin.scenarios import SCENARIO_TEMPLATES


def _ensure_dict(val: Any) -> dict:
    """Return a dict whether the value is already a dict or a JSON string."""
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return {}
    if val is None:
        return {}
    if hasattr(val, "get"):
        return val
    return {}

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/intelligence/digital-twin", tags=["Digital Twin"])


def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    return dict(row)


# ── Network Graph ──────────────────────────────────────────────────────────


@router.post("/network/build")
async def build_network(pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    graph = NetworkGraph(pool)
    result = await graph.build_from_entities()
    return result


@router.get("/network")
async def get_network(pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    graph = NetworkGraph(pool)
    return await graph.get_graph()


@router.get("/network/nodes/{node_id}")
async def get_node(
    node_id: int, pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    row = await pool.fetchrow(
        "SELECT * FROM energy.network_nodes WHERE id = $1 AND is_deleted = false", node_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Node not found")
    return _row_to_dict(row)


@router.get("/network/path")
async def find_path(
    from_node: int = Query(..., description="Source node ID"),
    to_node: int = Query(..., description="Target node ID"),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    graph = NetworkGraph(pool)
    path = await graph.find_path(from_node, to_node)
    return {"path": path, "hops": len(path)}


@router.get("/network/downstream/{node_id}")
async def get_downstream(
    node_id: int, pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    graph = NetworkGraph(pool)
    edges = await graph.get_downstream(node_id)
    return {"edges": edges, "count": len(edges)}


@router.get("/network/upstream/{node_id}")
async def get_upstream(
    node_id: int, pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    graph = NetworkGraph(pool)
    edges = await graph.get_upstream(node_id)
    return {"edges": edges, "count": len(edges)}


@router.get("/network/dependencies/{node_id}")
async def get_dependencies(
    node_id: int, depth: int = Query(5, ge=1, le=10),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    graph = NetworkGraph(pool)
    deps = await graph.get_dependencies(node_id, depth)
    return {"dependencies": deps, "count": len(deps)}


# ── Scenarios ──────────────────────────────────────────────────────────────


@router.post("/scenarios/seed")
async def seed_scenarios(pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    engine = SimulationEngine(pool)
    count = await engine.seed_scenarios()
    return {"seeded": count}


@router.get("/scenarios")
async def list_scenarios(
    category: str | None = Query(None),
    is_template: bool | None = Query(None),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    conditions = ["1=1"]
    params: list[Any] = []
    if category:
        conditions.append(f"category = ${len(params) + 1}")
        params.append(category)
    if is_template is not None:
        conditions.append(f"is_template = ${len(params) + 1}")
        params.append(is_template)
    where = " AND ".join(conditions)
    rows = await pool.fetch(
        f"SELECT * FROM energy.simulation_scenarios WHERE {where} ORDER BY is_template DESC, name LIMIT 100",
        *params,
    )
    return {"items": [_row_to_dict(r) for r in rows], "total": len(rows)}


@router.get("/scenarios/{scenario_uuid}")
async def get_scenario(
    scenario_uuid: str, pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    row = await pool.fetchrow(
        "SELECT * FROM energy.simulation_scenarios WHERE uuid = $1::uuid", scenario_uuid,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return _row_to_dict(row)


@router.post("/scenarios")
async def create_scenario(
    body: dict[str, Any], pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    engine = SimulationEngine(pool)
    result = await engine.create_custom_scenario(
        name=body.get("name", "Custom Scenario"),
        description=body.get("description", ""),
        config=body.get("config", {}),
        assumptions=body.get("assumptions"),
        category=body.get("category", "custom"),
        severity=body.get("severity", "medium"),
    )
    return result


# ── Simulations (Runs) ────────────────────────────────────────────────────


@router.post("/run")
async def run_simulation(
    body: dict[str, Any], pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    engine = SimulationEngine(pool)

    scenario_uuid = body.get("scenario_uuid")
    scenario_id = None
    if scenario_uuid:
        row = await pool.fetchrow(
            "SELECT id FROM energy.simulation_scenarios WHERE uuid = $1::uuid", scenario_uuid,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Scenario not found")
        scenario_id = row["id"]

    result = await engine.run_simulation(
        scenario_id=scenario_id,
        name=body.get("name", "Simulation Run"),
        description=body.get("description", ""),
        config=body.get("config"),
        tick_interval=body.get("tick_interval", "day"),
        max_ticks=body.get("max_ticks", 90),
        risk_snapshot=body.get("risk_snapshot"),
    )
    return result


@router.get("/runs")
async def list_runs(
    status: str | None = Query(None),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    conditions = ["1=1"]
    params: list[Any] = []
    if status:
        conditions.append(f"status = ${len(params) + 1}")
        params.append(status)
    where = " AND ".join(conditions)
    rows = await pool.fetch(
        f"SELECT * FROM energy.digital_twin_runs WHERE {where} ORDER BY created_at DESC LIMIT 50",
        *params,
    )
    return {"items": [_row_to_dict(r) for r in rows], "total": len(rows)}


@router.get("/runs/{run_uuid}")
async def get_run(
    run_uuid: str, pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    engine = SimulationEngine(pool)
    result = await engine.get_run_results(run_uuid)
    if not result:
        raise HTTPException(status_code=404, detail="Run not found")
    return result


@router.get("/runs/{run_uuid}/timeline")
async def get_run_timeline(
    run_uuid: str, pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    engine = SimulationEngine(pool)
    result = await engine.get_run_timeline(run_uuid)
    if not result:
        raise HTTPException(status_code=404, detail="Run not found")
    return result


@router.get("/runs/{run_uuid}/network")
async def get_run_network(
    run_uuid: str,
    tick: int | None = Query(None),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    engine = SimulationEngine(pool)
    result = await engine.get_run_network(run_uuid, tick)
    if not result:
        raise HTTPException(status_code=404, detail="Run not found")
    return result


@router.get("/runs/{run_uuid}/flows")
async def get_run_flows(
    run_uuid: str,
    tick: int | None = Query(None),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    run = await pool.fetchrow(
        "SELECT id FROM energy.digital_twin_runs WHERE uuid = $1::uuid", run_uuid,
    )
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    target_tick = tick or (await pool.fetchval(
        "SELECT MAX(tick) FROM energy.flow_states WHERE run_id = $1", run["id"],
    ) or 0)
    rows = await pool.fetch(
        """SELECT fs.*, nn.name as node_name, nn.node_type, nn.category,
                  ne.edge_type, ne.max_capacity_bpd
           FROM energy.flow_states fs
           LEFT JOIN energy.network_nodes nn ON nn.id = fs.node_id
           LEFT JOIN energy.network_edges ne ON ne.id = fs.edge_id
           WHERE fs.run_id = $1 AND fs.tick = $2 AND fs.edge_id IS NOT NULL
           ORDER BY nn.name""",
        run["id"], target_tick,
    )
    return {
        "run_uuid": run_uuid,
        "tick": target_tick,
        "flows": [_row_to_dict(r) for r in rows],
        "total": len(rows),
    }


@router.get("/runs/{run_uuid}/impacts")
async def get_run_impacts(
    run_uuid: str, pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    run = await pool.fetchrow(
        "SELECT * FROM energy.digital_twin_runs WHERE uuid = $1::uuid", run_uuid,
    )
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "run_uuid": run_uuid,
        "name": run["name"],
        "supply_gap_bpd": run.get("supply_gap_bpd", 0),
        "max_supply_gap_bpd": run.get("max_supply_gap_bpd", 0),
        "days_until_critical": run.get("days_until_critical"),
        "economic_impact_usd": run.get("economic_impact_usd", 0),
        "gdp_impact_pct": run.get("gdp_impact_pct", 0),
        "aggregate_impacts": _ensure_dict(run.get("aggregate_impacts")),
        "execution_time_ms": run.get("execution_time_ms", 0),
    }


@router.delete("/runs/{run_uuid}")
async def delete_run(
    run_uuid: str, pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    run = await pool.fetchrow(
        "SELECT id FROM energy.digital_twin_runs WHERE uuid = $1::uuid", run_uuid,
    )
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    await pool.execute("DELETE FROM energy.digital_twin_runs WHERE id = $1", run["id"])
    return {"deleted": run_uuid}


@router.get("/compare")
async def compare_runs(
    run_uuids: str = Query(..., description="Comma-separated run UUIDs"),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    uuids = [u.strip() for u in run_uuids.split(",") if u.strip()]
    if not uuids:
        raise HTTPException(status_code=400, detail="At least one run UUID required")
    engine = SimulationEngine(pool)
    results = await engine.compare_runs(uuids)
    return {"comparison": results, "count": len(results)}


# ── Demand Profiles ────────────────────────────────────────────────────────


@router.post("/demand/seed")
async def seed_demand(pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    profiles = [
        {"region": "India", "daily_demand_bpd": 5000000, "source": "IEA"},
        {"region": "India - Gujarat", "daily_demand_bpd": 1500000, "source": "PPAC"},
        {"region": "India - Maharashtra", "daily_demand_bpd": 1200000, "source": "PPAC"},
        {"region": "India - Tamil Nadu", "daily_demand_bpd": 600000, "source": "PPAC"},
        {"region": "India - Andhra Pradesh", "daily_demand_bpd": 500000, "source": "PPAC"},
        {"region": "India - Kerala", "daily_demand_bpd": 400000, "source": "PPAC"},
        {"region": "India - West Bengal", "daily_demand_bpd": 300000, "source": "PPAC"},
        {"region": "India - Uttar Pradesh", "daily_demand_bpd": 200000, "source": "PPAC"},
    ]
    count = 0
    for p in profiles:
        exists = await pool.fetchval(
            "SELECT id FROM energy.demand_profiles WHERE region = $1 AND profile_type = 'baseline'", p["region"],
        )
        if not exists:
            await pool.execute(
                "INSERT INTO energy.demand_profiles (region, daily_demand_bpd, source) VALUES ($1,$2,$3)",
                p["region"], p["daily_demand_bpd"], p["source"],
            )
            count += 1
    return {"seeded": count}


@router.get("/demand")
async def list_demand(pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    rows = await pool.fetch(
        "SELECT * FROM energy.demand_profiles WHERE is_active = true ORDER BY region"
    )
    return {"items": [_row_to_dict(r) for r in rows], "total": len(rows)}


# ── Flows ──────────────────────────────────────────────────────────────────


@router.post("/flows/estimate-baseline")
async def estimate_baseline(pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    from services.digital_twin.flow import FlowEngine
    engine = FlowEngine(pool)
    return await engine.estimate_baseline_flow()


@router.get("/flows")
async def get_flows(pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    rows = await pool.fetch(
        """SELECT e.*, sn.name as source_name, sn.node_type as source_type,
                  tn.name as target_name, tn.node_type as target_type
           FROM energy.network_edges e
           JOIN energy.network_nodes sn ON sn.id = e.source_node_id
           JOIN energy.network_nodes tn ON tn.id = e.target_node_id
           WHERE e.is_deleted = false AND e.is_active = true
           ORDER BY e.utilization_pct DESC"""
    )
    return {"items": [_row_to_dict(r) for r in rows], "total": len(rows)}


# ── Recommendations (lightweight — full engine in later sprint) ────────────


@router.get("/recommendations")
async def get_recommendations(
    run_uuid: str | None = Query(None),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    """Generate lightweight recommendations from simulation results."""
    engine = SimulationEngine(pool)
    recommendations = []

    if run_uuid:
        results = await engine.get_run_results(run_uuid)
        if results and results["run"].get("status") == "completed":
            r = results["run"]
            impacts = _ensure_dict(r.get("aggregate_impacts"))
            gap = impacts.get("supply_gap_bpd", 0)

            if gap > 0:
                idle = impacts.get("idle_refineries", 0)
                if idle > 0:
                    recommendations.append({
                        "type": "supply_restoration",
                        "priority": "critical",
                        "recommendation": f"Restore supply to {idle} idle refineries. Total capacity lost: {impacts.get('total_refinery_capacity_lost_bpd', 0):,.0f} bpd.",
                        "evidence": f"Simulation {run_uuid} identified {idle} refineries at risk",
                    })
                if r.get("gdp_impact_pct", 0) > 0.1:
                    recommendations.append({
                        "type": "spr_drawdown",
                        "priority": "high",
                        "recommendation": f"Authorize SPR drawdown to mitigate {gap:,.0f} bpd supply gap. Estimated GDP impact: {r.get('gdp_impact_pct', 0):.2f}%.",
                        "evidence": f"Economic impact analysis from simulation {run_uuid}",
                    })

            bottleneck_events = [
                e for e in (results.get("tick_events") or [])
                if e.get("event_type") in ("supply_disruption", "port_closure", "refinery_shutdown")
            ]
            if bottleneck_events:
                recommendations.append({
                    "type": "bottleneck_analysis",
                    "priority": "high",
                    "recommendation": f"Address {len(bottleneck_events)} critical bottlenecks identified during simulation.",
                    "evidence": [e.get("description", "") for e in bottleneck_events[:5]],
                })

    if not recommendations:
        latest_run = await pool.fetchrow(
            "SELECT uuid, name FROM energy.digital_twin_runs WHERE status = 'completed' ORDER BY created_at DESC LIMIT 1"
        )
        if latest_run:
            recommendations.append({
                "type": "info",
                "priority": "low",
                "recommendation": f"No critical issues detected in latest run '{latest_run['name']}'. Run ID: {latest_run['uuid']}.",
                "evidence": "All simulated metrics within normal parameters.",
            })
        else:
            recommendations.append({
                "type": "info",
                "priority": "low",
                "recommendation": "Run a simulation first to generate recommendations.",
                "evidence": "No completed simulation runs found.",
            })

    return {"recommendations": recommendations, "count": len(recommendations)}


# ── History ─────────────────────────────────────────────────────────────────


@router.get("/history")
async def get_history(
    limit: int = Query(20, ge=1, le=100),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    rows = await pool.fetch(
        "SELECT * FROM energy.digital_twin_runs ORDER BY created_at DESC LIMIT $1", limit,
    )
    return {"items": [_row_to_dict(r) for r in rows], "total": len(rows)}


# ── Assets ──────────────────────────────────────────────────────────────────


@router.get("/assets")
async def list_assets(
    node_type: str | None = Query(None),
    category: str | None = Query(None),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    conditions = ["is_deleted = false"]
    params: list[Any] = []
    if node_type:
        conditions.append(f"node_type = ${len(params) + 1}")
        params.append(node_type)
    if category:
        conditions.append(f"category = ${len(params) + 1}")
        params.append(category)
    where = " AND ".join(conditions)
    rows = await pool.fetch(
        f"SELECT * FROM energy.network_nodes WHERE {where} ORDER BY name LIMIT 200",
        *params,
    )
    return {"items": [_row_to_dict(r) for r in rows], "total": len(rows)}


@router.get("/health")
async def digital_twin_health(pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    node_count = await pool.fetchval(
        "SELECT COUNT(*) FROM energy.network_nodes WHERE is_deleted = false"
    ) or 0
    edge_count = await pool.fetchval(
        "SELECT COUNT(*) FROM energy.network_edges WHERE is_deleted = false"
    ) or 0
    run_count = await pool.fetchval(
        "SELECT COUNT(*) FROM energy.digital_twin_runs"
    ) or 0
    scenario_count = await pool.fetchval(
        "SELECT COUNT(*) FROM energy.simulation_scenarios"
    ) or 0
    return {
        "status": "ok",
        "nodes": node_count,
        "edges": edge_count,
        "simulation_runs": run_count,
        "scenarios": scenario_count,
        "scenario_templates": len(SCENARIO_TEMPLATES),
    }
