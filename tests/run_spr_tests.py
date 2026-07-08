"""Standalone SPR validation test runner. Run with:

cd services/energy-service
$env:PYTHONPATH="C:\ProxyWars\ProxyDefence"
.venv\Scripts\python ../../tests/run_spr_tests.py
"""

import asyncio
import json
import os
import sys
import time
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, r"C:\ProxyWars\ProxyDefence")
sys.path.insert(0, r"C:\ProxyWars\ProxyDefence\services\energy-service")

from app import app
from db import bootstrap

transport = ASGITransport(app=app)
BASE = "/api/v1/intelligence/procurement/spr"

passed = 0
failed = 0
errors = []


async def test(name: str, method: str, path: str, expected_status: int = 200, **kwargs):
    global passed, failed
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.request(method, f"{BASE}{path}", **kwargs)
            data = resp.json()
            ok = resp.status_code == expected_status
            status_str = f"\033[92mPASS\033[0m" if ok else f"\033[91mFAIL\033[0m"
            print(f"  {status_str} [{resp.status_code}] {name}")
            if not ok:
                failed += 1
                errors.append(f"{name}: got {resp.status_code}, expected {expected_status}: {json.dumps(data, indent=2)[:200]}")
            else:
                passed += 1
            return data
    except Exception as e:
        failed += 1
        errors.append(f"{name}: exception {e}")
        print(f"  \033[91mFAIL\033[0m [ERR] {name}: {e}")


async def main():
    global passed, failed
    print("\n=== SPR Decision Intelligence — Validation Suite ===\n")

    # Bootstrap schema
    print("\n[Setup] Bootstrapping schema...")
    await bootstrap()
    print("[Setup] Schema ready.\n")

    # ── 1. Health ──
    print("── Health & Schema ──")
    health = await test("SPR health", "GET", "/health")
    if health:
        print(f"     Facilities: {health.get('facilities')}, Active: {health.get('active_facilities')}, "
              f"Capacity: {health.get('total_capacity_mb')}M, Inventory: {health.get('current_inventory_mb')}M, "
              f"Runs: {health.get('release_runs')}")
    print()

    # ── 2. Facilities ──
    print("── Facilities ──")
    init_resp = await test("Initialize facilities", "POST", "/init")
    if init_resp:
        print(f"     {json.dumps(init_resp, indent=2)[:200]}")
    facs = await test("List facilities", "GET", "/facilities")
    facility_count = len(facs.get("items", [])) if facs else 0
    print(f"     Found {facility_count} facilities")
    print()

    # ── 3. Inventory ──
    print("── Inventory ──")
    inv = await test("Inventory history", "GET", "/inventory?limit=10")
    inv_count = len(inv.get("items", [])) if inv else 0
    print(f"     {inv_count} inventory records")
    print()

    # ── 4. Policies ──
    print("── Policies ──")
    pols = await test("List policies", "GET", "/policies")
    pol_count = len(pols.get("items", [])) if pols else 0
    print(f"     {pol_count} policies found")
    await test("Create policy", "POST", "/policies", json={
        "name": "validation_test_policy",
        "description": "Created by test runner",
        "min_reserve_threshold": 0.15,
        "max_daily_release_rate": 500000,
        "emergency_only": True,
        "strategic_preservation": True,
        "duration_days": 60,
    })
    print()

    # ── 5. Demand ──
    print("── Demand ──")
    demand = await test("Compute demand", "GET", "/demand")
    if demand:
        nat = demand.get("national_demand_bpd", 0)
        print(f"     National demand: {nat:,} bpd")
    print()

    # ── 6. Analysis (Release Planner) ──
    print("── Analysis / Release Planner ──")
    r1 = await test("Minimal analysis", "POST", "/analyze", json={
        "name": "Test Release Analysis",
        "disruption_reason": "supply_disruption",
        "disruption_days": 30,
        "strategy": "balanced",
        "policy_name": "default",
    })
    run_uuid = r1.get("run_uuid", "N/A") if r1 else "N/A"
    print(f"     Run UUID: {run_uuid}")
    n_recs = len(r1.get("recommendations", [])) if r1 else 0
    print(f"     Recommendations: {n_recs}")
    timeline_phases = list(r1.get("decision_timeline", {}).keys()) if r1 else []
    print(f"     Timeline phases: {timeline_phases}")

    await test("With supply gap", "POST", "/analyze", json={
        "name": "Supply Gap Test",
        "disruption_reason": "geopolitical_crisis",
        "disruption_days": 90,
        "supply_gap_bpd": 500000,
        "strategy": "conservative",
    })
    await test("Aggressive strategy", "POST", "/analyze", json={
        "name": "Aggressive Release",
        "disruption_reason": "war_conflict",
        "disruption_days": 180,
        "supply_gap_bpd": 1000000,
        "strategy": "aggressive",
        "policy_name": "aggressive",
    })
    print()

    # ── 7. Runs ──
    print("── Runs ──")
    runs = await test("List runs", "GET", "/runs?limit=10")
    run_count = len(runs.get("items", [])) if runs else 0
    print(f"     {run_count} runs")
    if run_count > 0:
        uuid = runs["items"][0]["uuid"]
        await test("Get run by UUID", "GET", f"/runs/{uuid}")
    await test("Run not found", "GET", "/runs/00000000-0000-0000-0000-000000000000", expected_status=404)
    print()

    # ── 8. Executive Cards ──
    print("── Executive Cards ──")
    await test("Ack card not found", "POST",
               "/executive-cards/00000000-0000-0000-0000-000000000000/ack",
               expected_status=404,
               json={"acknowledged_by": "test"})
    print()

    # ── 9. Decision Timeline ──
    print("── Decision Timeline ──")
    tl = await test("Economic strategy timeline", "POST", "/analyze", json={
        "name": "Timeline Test",
        "disruption_reason": "price_spike",
        "disruption_days": 60,
        "supply_gap_bpd": 300000,
        "strategy": "economic",
        "policy_name": "default",
    })
    if tl:
        tl_phases = tl.get("decision_timeline", {})
        for phase in ["now", "24h", "72h", "7d", "30d"]:
            if phase in tl_phases:
                entry = tl_phases[phase]
                print(f"     {phase}: {entry.get('daily_release_bpd', 0):,} bpd → {entry.get('cumulative_release', 0):,} bbl cumulative")
    print()

    # ── Summary ──
    total = passed + failed
    print(f"{'='*50}")
    print(f"Results: {passed}/{total} passed, {failed} failed")
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors[:5]:
            print(f"  - {e}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
