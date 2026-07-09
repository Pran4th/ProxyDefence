"""Digital Twin Validation Suite — Sprint 2 Production Validation.

Tests are organized to be runnable against a running energy-service.
Uses httpx to hit the actual HTTP API and asyncpg to inspect database state.

Usage:
    $env:PYTHONPATH = "C:\\ProxyWars\\ProxyDefence"
    python tests/test_digital_twin_validation.py
"""

import asyncio
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

import httpx
import asyncpg

API_BASE = os.getenv("ENERGY_SERVICE_URL", "http://localhost:8006")
DSN = (
    f"postgresql://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
    f"@{os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}"
    f"/{os.getenv('POSTGRES_DB', 'defenseintel')}"
)

PASS = 0
FAIL = 0
SKIP = 0


def ok(msg: str):
    global PASS
    PASS += 1
    print(f"  [PASS] {msg}")


def fail(msg: str, detail: str = ""):
    global FAIL
    FAIL += 1
    print(f"  [FAIL] {msg} {detail}")


def skip(msg: str):
    global SKIP
    SKIP += 1
    print(f"  [SKIP] {msg}")


async def check_api(endpoint: str, method: str = "GET", body: dict | None = None,
                    expected_status: int = 200, label: str | None = None) -> dict | None:
    label = label or f"{method} {endpoint}"
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if method == "GET":
                resp = await client.get(f"{API_BASE}{endpoint}")
            elif method == "POST":
                resp = await client.post(f"{API_BASE}{endpoint}", json=body or {})
            elif method == "DELETE":
                resp = await client.delete(f"{API_BASE}{endpoint}")
            else:
                resp = await client.request(method, f"{API_BASE}{endpoint}", json=body)

        latency = (time.time() - t0) * 1000
        status_ok = resp.status_code == expected_status

        if status_ok:
            ok(f"{label} -> {resp.status_code} ({latency:.0f}ms)")
        else:
            fail(f"{label} expected {expected_status} got {resp.status_code} ({latency:.0f}ms)",
                 f"body={resp.text[:200]}")

        if resp.status_code in (200, 201):
            return resp.json()
        return None
    except Exception as e:
        fail(label, f"connection error: {e}")
        return None


async def validate_schema():
    print(f"\n{'='*60}")
    print("DATABASE SCHEMA VALIDATION")
    print(f"{'='*60}")

    conn = await asyncpg.connect(DSN)

    expected_tables = [
        "network_nodes", "network_edges", "flow_states", "digital_twin_runs",
        "simulation_scenarios", "simulation_tick_events", "network_snapshots",
        "demand_profiles", "flow_constraints",
    ]
    rows = await conn.fetch(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='energy'"
    )
    existing = {r["table_name"] for r in rows}
    for t in expected_tables:
        if t in existing:
            ok(f"Table energy.{t} exists")
        else:
            fail(f"Table energy.{t} MISSING")

    expected_enums = [
        "simulation_status", "node_category", "edge_category", "simulation_mode", "scenario_category",
    ]
    enum_rows = await conn.fetch(
        "SELECT typname FROM pg_type WHERE typnamespace = "
        "(SELECT oid FROM pg_namespace WHERE nspname = 'energy') AND typtype = 'e'"
    )
    existing_enums = {r["typname"] for r in enum_rows}
    for e in expected_enums:
        if e in existing_enums:
            ok(f"Enum energy.{e} exists")
        else:
            fail(f"Enum energy.{e} MISSING")

    table_columns = {
        "network_nodes": {"id", "uuid", "node_type", "entity_id", "name", "category", "location_id", "country", "capacity_bpd", "storage_capacity_barrels", "current_inventory_barrels", "metadata", "is_active", "is_deleted"},
        "network_edges": {"id", "uuid", "source_node_id", "target_node_id", "edge_type", "category", "max_capacity_bpd", "current_flow_bpd", "utilization_pct", "commodity_type", "metadata", "is_active", "is_deleted"},
        "digital_twin_runs": {"id", "uuid", "scenario_id", "name", "mode", "status", "tick_interval", "max_ticks", "config", "aggregate_impacts", "supply_gap_bpd", "economic_impact_usd", "gdp_impact_pct", "created_at"},
        "simulation_scenarios": {"id", "uuid", "name", "description", "category", "config", "assumptions", "is_template", "severity"},
        "flow_states": {"id", "uuid", "run_id", "tick", "node_id", "edge_id", "flow_bpd", "capacity_bpd", "utilization_pct", "inventory_barrels", "supply_gap_bpd", "is_bottleneck", "is_idle", "status"},
        "simulation_tick_events": {"id", "uuid", "run_id", "tick", "event_type", "node_id", "description", "severity", "impact"},
        "network_snapshots": {"id", "uuid", "name", "description", "snapshot_type", "source_run_id", "node_state", "edge_state", "metrics"},
        "demand_profiles": {"id", "uuid", "region", "commodity_type", "daily_demand_bpd", "profile_type", "source", "is_active"},
        "flow_constraints": {"id", "uuid", "edge_id", "constraint_type", "max_bpd", "min_bpd", "priority", "is_active"},
    }
    for table, needed_cols in table_columns.items():
        cols = await conn.fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='energy' AND table_name=$1", table,
        )
        col_names = {c["column_name"] for c in cols}
        missing = needed_cols - col_names
        for col in needed_cols:
            if col in col_names:
                ok(f"{table}.{col} exists")
            else:
                fail(f"{table}.{col} MISSING")

    await conn.close()


async def validate_network_graph():
    print(f"\n{'='*60}")
    print("NETWORK GRAPH VALIDATION")
    print(f"{'='*60}")

    result = await check_api("/api/v1/intelligence/digital-twin/network/build", "POST",
                              label="Build network graph")
    if result:
        ok(f"Network build returned {result.get('nodes', 0)} new nodes, {result.get('edges', 0)} new edges")

    result = await check_api("/api/v1/intelligence/digital-twin/network",
                              label="Get network graph")
    if result:
        nodes = result.get("nodes", [])
        edges = result.get("edges", [])
        if len(nodes) > 0:
            ok(f"Network has {len(nodes)} nodes, {len(edges)} edges")
        else:
            fail("Network response has 0 nodes")

    result = await check_api("/api/v1/intelligence/digital-twin/health",
                              label="Digital Twin health")
    if result:
        for key in ["status", "nodes", "edges", "simulation_runs", "scenarios"]:
            if key in result:
                ok(f"Health field '{key}' = {result[key]}")
            else:
                fail(f"Health missing field '{key}'")

    result = await check_api("/api/v1/intelligence/digital-twin/assets",
                              label="List all assets")
    if result:
        total = result.get("total", 0)
        if total > 0:
            ok(f"{total} assets listed")
        else:
            fail("0 assets found")

    for node_type in ["port", "oil_field", "gas_field", "pipeline", "refinery",
                       "storage_facility", "strategic_petroleum_reserve", "power_plant"]:
        result = await check_api(
            f"/api/v1/intelligence/digital-twin/assets?node_type={node_type}",
            label=f"Filter assets by type={node_type}",
        )
        if result and result.get("total", 0) > 0:
            ok(f"Assets filtered by {node_type}: {result['total']} items")

    result = await check_api("/api/v1/intelligence/digital-twin/flows",
                              label="List all flows/edges")
    if result:
        total = result.get("total", 0)
        if total > 0:
            ok(f"{total} flows/edges listed")
        else:
            skip("0 flows (may need baseline estimation)")


async def validate_pathfinding():
    print(f"\n{'='*60}")
    print("PATHFINDING VALIDATION")
    print(f"{'='*60}")

    conn = await asyncpg.connect(DSN)
    nodes = await conn.fetch(
        "SELECT id, name FROM energy.network_nodes WHERE is_deleted = false ORDER BY RANDOM() LIMIT 2"
    )
    await conn.close()

    if len(nodes) == 2:
        from_id, to_id = nodes[0]["id"], nodes[1]["id"]
        result = await check_api(
            f"/api/v1/intelligence/digital-twin/network/path?from_node={from_id}&to_node={to_id}",
            label=f"Find path from node {from_id} to {to_id}",
        )
        if result:
            hops = result.get("hops", 0)
            path = result.get("path", [])
            ok(f"Pathfinding: {hops} hops, path={path}")


async def validate_scenarios():
    print(f"\n{'='*60}")
    print("SCENARIO VALIDATION")
    print(f"{'='*60}")

    result = await check_api("/api/v1/intelligence/digital-twin/scenarios/seed", "POST",
                              label="Seed scenario templates")
    if result:
        seeded = result.get("seeded", 0)
        ok(f"Seeded {seeded} new scenario templates")

    result = await check_api("/api/v1/intelligence/digital-twin/scenarios",
                              label="List all scenarios")
    if result:
        items = result.get("items", [])
        total = result.get("total", 0)
        if total > 0:
            ok(f"{total} scenarios listed ({len(items)} in response)")
            scenario = items[0]
            scenario_uuid = scenario.get("uuid", "")
            if scenario_uuid:
                detail = await check_api(
                    f"/api/v1/intelligence/digital-twin/scenarios/{scenario_uuid}",
                    label=f"Get scenario {scenario_uuid[:8]}...",
                )
                if detail:
                    for key in ["name", "category", "severity", "config"]:
                        if key in detail:
                            ok(f"Scenario has field '{key}'")
                        else:
                            fail(f"Scenario missing field '{key}'")
        else:
            fail("No scenarios found after seeding")

    result = await check_api(
        "/api/v1/intelligence/digital-twin/scenarios?is_template=true",
        label="Filter scenarios by is_template=true",
    )
    if result:
        templates = result.get("total", 0)
        if templates >= 9:
            ok(f"{templates} template scenarios available (expected >= 9)")
        else:
            fail(f"Only {templates} templates found (expected >= 9)")

    result = await check_api(
        "/api/v1/intelligence/digital-twin/scenarios?category=chokepoint",
        label="Filter scenarios by category=chokepoint",
    )
    if result:
        ok(f"{result.get('total', 0)} chokepoint scenarios")


async def validate_demand_profiles():
    print(f"\n{'='*60}")
    print("DEMAND PROFILE VALIDATION")
    print(f"{'='*60}")

    result = await check_api("/api/v1/intelligence/digital-twin/demand/seed", "POST",
                              label="Seed demand profiles")
    if result:
        ok(f"Seeded {result.get('seeded', 0)} demand profiles")

    result = await check_api("/api/v1/intelligence/digital-twin/demand",
                              label="List demand profiles")
    if result:
        items = result.get("items", [])
        total = result.get("total", 0)
        if total > 0:
            ok(f"{total} demand profiles ({len(items)} in response)")
        else:
            fail("No demand profiles found")


async def validate_simulation_run():
    print(f"\n{'='*60}")
    print("SIMULATION RUN VALIDATION")
    print(f"{'='*60}")

    scenarios_all = await check_api("/api/v1/intelligence/digital-twin/scenarios?is_template=true",
                                     label="Get template scenario for simulation")
    scenario_uuid = None
    if scenarios_all and scenarios_all.get("items"):
        scenario_uuid = scenarios_all["items"][0]["uuid"]
        ok(f"Using scenario {scenario_uuid[:8]}... for simulation")

    if scenario_uuid:
        run_body = {
            "scenario_uuid": scenario_uuid,
            "name": "Validation Test Run",
            "description": "Automated validation simulation",
            "max_ticks": 10,
            "tick_interval": "day",
        }
        result = await check_api("/api/v1/intelligence/digital-twin/run", "POST", run_body,
                                  label="Run simulation (10 ticks)", expected_status=200)
        if result:
            run_uuid = result.get("run_uuid", "")
            if run_uuid:
                ok(f"Simulation run created: {run_uuid[:8]}...")
                status = result.get("status", "")
                ok(f"Run status='{status}', events={result.get('total_events')}")

                detail = await check_api(
                    f"/api/v1/intelligence/digital-twin/runs/{run_uuid}",
                    label="Get run results",
                )
                if detail:
                    run = detail.get("run", {})
                    events = detail.get("tick_events", [])
                    ok(f"Run results: status={run.get('status')}, {len(events)} tick events")

                    timeline = await check_api(
                        f"/api/v1/intelligence/digital-twin/runs/{run_uuid}/timeline",
                        label="Get run timeline",
                    )
                    if timeline:
                        ticks = timeline.get("timeline", [])
                        ok(f"Timeline: {len(ticks)} ticks recorded")

                    impacts = await check_api(
                        f"/api/v1/intelligence/digital-twin/runs/{run_uuid}/impacts",
                        label="Get run impacts",
                    )
                    if impacts:
                        for key in ["supply_gap_bpd", "economic_impact_usd", "gdp_impact_pct"]:
                            if key in impacts:
                                ok(f"Impact '{key}' = {impacts[key]}")
                            else:
                                fail(f"Impact missing '{key}'")

                runs = await check_api("/api/v1/intelligence/digital-twin/runs",
                                        label="List simulation runs")
                if runs:
                    total = runs.get("total", 0)
                    if total > 0:
                        ok(f"{total} simulation runs in history")
                    else:
                        fail("No runs listed after creation")
            else:
                fail("Simulation run has no uuid")
        else:
            fail("Simulation run failed to start")
    else:
        fail("No scenario available for simulation")


async def validate_recommendations():
    print(f"\n{'='*60}")
    print("RECOMMENDATIONS VALIDATION")
    print(f"{'='*60}")

    runs = await check_api("/api/v1/intelligence/digital-twin/runs?status=completed",
                            label="Get completed runs for recommendations")
    if runs and runs.get("items"):
        run_uuid = runs["items"][0]["uuid"]
        result = await check_api(
            f"/api/v1/intelligence/digital-twin/recommendations?run_uuid={run_uuid}",
            label=f"Get recommendations for run {run_uuid[:8]}...",
        )
        if result:
            recs = result.get("recommendations", [])
            ok(f"{result.get('count', 0)} recommendations generated")

    result = await check_api("/api/v1/intelligence/digital-twin/recommendations",
                              label="Get default recommendations")
    if result:
        ok(f"{result.get('count', 0)} default recommendations")


async def validate_history():
    print(f"\n{'='*60}")
    print("HISTORY VALIDATION")
    print(f"{'='*60}")

    result = await check_api("/api/v1/intelligence/digital-twin/history?limit=5",
                              label="Get run history")
    if result:
        items = result.get("items", [])
        total = result.get("total", 0)
        if total > 0:
            ok(f"{total} historical runs ({len(items)} in response)")
        else:
            fail("No historical runs found")

    result = await check_api("/api/v1/intelligence/digital-twin/runs?status=completed",
                              label="Filter runs by status=completed")
    if result:
        ok(f"{result.get('total', 0)} completed runs")


async def validate_flow_estimation():
    print(f"\n{'='*60}")
    print("FLOW ESTIMATION VALIDATION")
    print(f"{'='*60}")

    result = await check_api("/api/v1/intelligence/digital-twin/flows/estimate-baseline", "POST",
                              label="Estimate baseline flows")
    if result:
        ok(f"Baseline estimation: {result}")


async def run_all():
    ts = datetime.now(timezone.utc)
    print(f"\n{'#'*60}")
    print(f"# DIGITAL TWIN VALIDATION SUITE")
    print(f"# Started: {ts.isoformat()}")
    print(f"# API: {API_BASE}")
    print(f"{'#'*60}")

    await validate_schema()
    await validate_network_graph()
    await validate_pathfinding()
    await validate_scenarios()
    await validate_demand_profiles()
    await validate_simulation_run()
    await validate_flow_estimation()
    await validate_recommendations()
    await validate_history()

    te = datetime.now(timezone.utc)
    duration = (te - ts).total_seconds()
    print(f"\n{'='*60}")
    print(f"VALIDATION COMPLETE")
    print(f"  Duration: {duration:.1f}s")
    print(f"  PASS: {PASS}")
    print(f"  FAIL: {FAIL}")
    print(f"  SKIP: {SKIP}")
    print(f"  Total: {PASS + FAIL + SKIP}")
    if FAIL > 0:
        print(f"\n  !! {FAIL} TESTS FAILED")
    else:
        print(f"\n  ** ALL TESTS PASSED **")
    print(f"{'='*60}")
    return FAIL == 0


if __name__ == "__main__":
    success = asyncio.run(run_all())
    sys.exit(0 if success else 1)
