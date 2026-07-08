"""Standalone procurement validation test runner. Run with:

cd services/energy-service
$env:PYTHONPATH="C:\ProxyWars\ProxyDefence"
.venv\Scripts\python ../../tests/run_procurement_tests.py
"""

import asyncio
import json
import os
import sys
import time
from httpx import AsyncClient, ASGITransport

# Add paths
sys.path.insert(0, r"C:\ProxyWars\ProxyDefence")
sys.path.insert(0, r"C:\ProxyWars\ProxyDefence\services\energy-service")

# Force import of app before any conftest
from app import app
from db import bootstrap

transport = ASGITransport(app=app)
BASE = "/api/v1/intelligence/procurement"

passed = 0
failed = 0
errors = []


async def test(name: str, method: str, path: str, expect_status: int = 200, **kwargs):
    global passed, failed
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.request(method, f"{BASE}{path}", **kwargs)
            data = resp.json()
            status = resp.status_code
            if status == expect_status:
                passed += 1
                print(f"  PASS  {name}")
            else:
                failed += 1
                msg = f"  FAIL  {name}: expected {expect_status}, got {status}: {json.dumps(data)[:200]}"
                print(msg)
                errors.append(msg)
            return status, data
    except Exception as e:
        failed += 1
        msg = f"  FAIL  {name}: exception: {e}"
        print(msg)
        errors.append(msg)
        return None, {"error": str(e)}


async def main():
    global passed, failed

    t0 = time.time()
    print(f"\n{'='*60}")
    print(f"  PROCUREMENT ORCHESTRATOR - VALIDATION SUITE")
    print(f"{'='*60}\n")

    # Bootstrap database schema
    from db import get_pool
    p = await get_pool()
    await bootstrap(p)

    # Initialize procurement data
    from services.procurement.supplier_intel import SupplierIntelligence
    from services.procurement.compatibility import RefineryCompatibility
    from services.procurement.optimizer import ProcurementOptimizer
    intel = SupplierIntelligence(p)
    await intel.enrich_all()
    compat = RefineryCompatibility(p)
    await compat.compute_all()
    opt = ProcurementOptimizer(p)
    await opt.compute_route_costs()

    # ── 1. Health ──
    print("\n-- Health --")
    await test("Health endpoint", "GET", "/health")

    # -- 2. Supplier Intelligence --
    print("\n-- Supplier Intelligence --")
    await test("Enrich suppliers", "POST", "/suppliers/enrich")
    s, suppliers = await test("List suppliers", "GET", "/suppliers")
    if s == 200:
        print(f"       Total suppliers: {suppliers['total']}")
        if suppliers["total"] > 0:
            suuid = suppliers["items"][0]["uuid"]
            await test("Get supplier profile", "GET", f"/suppliers/{suuid}")
            await test("Get supplier not found", "GET", "/suppliers/00000000-0000-0000-0000-000000000000", expect_status=404)

            # Test alternatives (need a commodity)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                from db import get_pool
                pool = await get_pool()
                commodity = await pool.fetchval(
                    "SELECT uuid FROM energy.commodities WHERE commodity_type = 'crude' LIMIT 1"
                )
                if commodity:
                    await test("Find alternatives", "GET",
                               f"/suppliers/{suuid}/alternatives?commodity_uuid={commodity}")

    # ── 3. Refinery Compatibility ──
    print("\n── Refinery Compatibility ──")
    s, compat = await test("Compute compatibility", "POST", "/compatibility/compute")
    if s == 200:
        print(f"       Refineries: {compat['refineries_evaluated']}, Pairs: {compat['pairs_created']}")
    s, compat_list = await test("List compatibility", "GET", "/compatibility")
    if s == 200:
        print(f"       Total pairs: {compat_list['total']}")
        if compat_list["total"] > 0:
            ref_uuid = compat_list["items"][0]["refinery_uuid"]
            await test("Filter by refinery", "GET", f"/compatibility?refinery_uuid={ref_uuid}")
            await test("Filter by min_score=optimal", "GET", "/compatibility?min_score=optimal")
            await test("Refinery recommendations", "GET", f"/compatibility/refinery/{ref_uuid}")

    # ── 4. Route Costs ──
    print("\n── Route Costs ──")
    s, routes = await test("Compute route costs", "POST", "/routes/compute")
    if s == 200:
        print(f"       Evaluated: {routes['routes_evaluated']}, Created: {routes['route_costs_created']}")
    await test("List routes", "GET", "/routes")

    # ── 5. Optimization ──
    print("\n── Procurement Optimization ──")
    s, opt = await test("Run optimization (balanced)", "POST", "/optimize", json={
        "supply_gap_bpd": 500000,
        "optimization_goal": "balanced",
        "max_cost_bbl": 100,
        "max_risk_score": 0.8,
        "max_lead_days": 60,
    })
    if s == 200:
        print(f"       Options: {opt['total_options']}, Pareto: {opt['pareto_count']}, Recommended: {opt.get('recommended', {}).get('supplier_name', 'none')}")

    await test("Optimization (cost goal)", "POST", "/optimize", json={
        "supply_gap_bpd": 300000,
        "optimization_goal": "cost",
    })
    await test("Optimization (risk goal)", "POST", "/optimize", json={
        "supply_gap_bpd": 300000,
        "optimization_goal": "risk",
    })
    await test("Optimization (speed goal)", "POST", "/optimize", json={
        "supply_gap_bpd": 300000,
        "optimization_goal": "speed",
    })
    await test("Optimization (no suppliers — tight cost)", "POST", "/optimize", json={
        "supply_gap_bpd": 500000,
        "max_cost_bbl": 1.0,
    })

    # ── 6. Procurement Orchestration ──
    print("\n── Procurement Orchestration ──")
    s, run = await test("Run procurement (standalone)", "POST", "/run", json={
        "name": "Validation Test Run",
        "supply_gap_bpd": 500000,
        "optimization_goal": "balanced",
    })
    run_uuid = run.get("run_uuid") if s == 200 else None
    if run_uuid:
        print(f"       Run UUID: {run_uuid}")
        print(f"       Recommendations: {run.get('recommendations_count', 0)}, Cards: via exec")
        print(f"       Exec time: {run.get('execution_time_ms', 0):.0f}ms")

    await test("List runs", "GET", "/runs")
    if run_uuid:
        await test("Get run detail", "GET", f"/runs/{run_uuid}")
        await test("Get executive summary", "GET", f"/runs/{run_uuid}/executive-summary")

        # Test linking with simulation
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            from db import get_pool
            pool = await get_pool()
            sim = await pool.fetchrow(
                "SELECT uuid FROM energy.digital_twin_runs WHERE status = 'completed' ORDER BY created_at DESC LIMIT 1"
            )
            if sim:
                await test("Run with simulation link", "POST", "/run", json={
                    "simulation_run_uuid": str(sim["uuid"]),
                    "name": "Simulation-Linked Run",
                })

    await test("Runs by status", "GET", "/runs?status=completed")
    await test("Run not found", "GET", "/runs/00000000-0000-0000-0000-000000000000", expect_status=404)

    # ── 7. Executive Cards ──
    print("\n── Executive Cards ──")
    s, cards = await test("List executive cards", "GET", "/executive-cards")
    if s == 200:
        print(f"       Total cards: {cards['total']}")
        if cards["total"] > 0:
            severity = cards["items"][0]["severity"]
            await test("Filter cards by severity", "GET", f"/executive-cards?severity={severity}")
            # Acknowledge first unacknowledged card
            unacked = [c for c in cards["items"] if not c["is_acknowledged"]]
            if unacked:
                await test("Acknowledge card", "POST", f"/executive-cards/{unacked[0]['uuid']}/ack", json={
                    "acknowledged_by": "test_runner",
                })

    # ── 8. Recommendations ──
    print("\n── Recommendations ──")
    s, recs = await test("List recommendations", "GET", "/recommendations")
    if s == 200:
        print(f"       Total: {recs['total']}")

    # ── 9. Edge Cases ──
    print("\n── Edge Cases ──")
    await test("Zero gap run", "POST", "/run", json={
        "name": "Zero Gap", "supply_gap_bpd": 0,
    })
    await test("Very large gap", "POST", "/run", json={
        "name": "Large Gap", "supply_gap_bpd": 5000000, "max_cost_bbl": 200,
    })
    await test("Invalid simulation run", "POST", "/run", json={
        "simulation_run_uuid": "00000000-0000-0000-0000-000000000000",
        "name": "Invalid",
    }, expect_status=404)
    await test("Two concurrent runs 1", "POST", "/run", json={
        "name": "Concurrent 1", "supply_gap_bpd": 200000,
    })
    await test("Two concurrent runs 2", "POST", "/run", json={
        "name": "Concurrent 2", "supply_gap_bpd": 400000,
    })

    # ── Summary ──
    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"  RESULTS: {passed} passed, {failed} failed, {elapsed:.1f}s")
    print(f"{'='*60}")

    if errors:
        print(f"\nErrors:")
        for e in errors[:10]:
            print(f"  {e}")

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
