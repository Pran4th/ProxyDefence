"""Procurement Orchestrator — validation tests against live API + database.

Run: pytest tests/test_procurement_validation.py -v --asyncio-mode=auto
"""

import pytest
from httpx import AsyncClient, ASGITransport
from app import app

BASE = "/api/v1/intelligence/procurement"

# ── Helpers ──────────────────────────────────────────────────────────────

transport = ASGITransport(app=app)


@pytest.fixture
def client():
    return AsyncClient(transport=transport, base_url="http://test")


async def _fetch(client: AsyncClient, method: str, path: str, **kwargs):
    resp = await client.request(method, f"{BASE}{path}", **kwargs)
    return resp.status_code, resp.json()


# ════════════════════════════════════════════════════════════════════════════
# 1. Health & Schema
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_health():
    async with client() as c:
        status, data = await _fetch(c, "GET", "/health")
        assert status == 200, f"Health check failed: {data}"
        assert data["status"] == "ok"
        assert "procurement_runs" in data
        assert "suppliers_with_intel" in data
        assert "refinery_crude_pairs" in data
        assert "executive_cards" in data
        assert "route_costs" in data


@pytest.mark.asyncio
async def test_database_schema_tables():
    """Verify procurement tables exist in energy schema."""
    async with client() as c:
        tables = [
            "procurement_runs",
            "procurement_recommendations",
            "executive_recommendations",
            "supplier_intelligence",
            "refinery_crude_compatibility",
            "route_costs",
            "alternative_suppliers",
            "procurement_assumptions",
            "rfq_outputs",
        ]
        for table in tables:
            resp = await c.get(f"http://test/health")
            # Direct DB check
            from db import get_pool
            pool = await get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchval(
                    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'energy' AND table_name = $1)",
                    table,
                )
                assert row is True, f"Table energy.{table} does not exist"


# ════════════════════════════════════════════════════════════════════════════
# 2. Supplier Intelligence
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_enrich_suppliers():
    async with client() as c:
        status, data = await _fetch(c, "POST", "/suppliers/enrich")
        assert status == 200
        assert "enriched" in data
        assert data["enriched"] >= 0


@pytest.mark.asyncio
async def test_list_suppliers():
    async with client() as c:
        status, data = await _fetch(c, "GET", "/suppliers")
        assert status == 200
        assert "items" in data
        assert "total" in data
        if data["total"] > 0:
            s = data["items"][0]
            assert "name" in s
            assert "composite_score" in s
            assert "supplier_type" in s
            assert "country" in s


@pytest.mark.asyncio
async def test_supplier_scoring():
    async with client() as c:
        status, data = await _fetch(c, "GET", "/suppliers")
        assert status == 200
        if data["total"] > 1:
            scores = [s["composite_score"] for s in data["items"]]
            for i in range(len(scores) - 1):
                assert scores[i] >= scores[i + 1], "Suppliers not sorted by composite score"


@pytest.mark.asyncio
async def test_supplier_profile():
    async with client() as c:
        status, list_data = await _fetch(c, "GET", "/suppliers")
        assert status == 200
        if list_data["total"] > 0:
            suuid = list_data["items"][0]["uuid"]
            status, data = await _fetch(c, "GET", f"/suppliers/{suuid}")
            assert status == 200
            assert "uuid" in data


@pytest.mark.asyncio
async def test_supplier_profile_not_found():
    async with client() as c:
        status, data = await _fetch(c, "GET", "/suppliers/00000000-0000-0000-0000-000000000000")
        assert status == 404


@pytest.mark.asyncio
async def test_supplier_alternatives():
    """Find alternatives for a supplier (empty is OK — may have no commodity filter)."""
    async with client() as c:
        status, list_data = await _fetch(c, "GET", "/suppliers")
        if list_data["total"] < 2:
            pytest.skip("Need at least 2 suppliers")

        from db import get_pool
        pool = await get_pool()
        commodity = await pool.fetchval(
            "SELECT uuid FROM energy.commodities WHERE commodity_type = 'crude' LIMIT 1"
        )
        if not commodity:
            pytest.skip("No crude commodities seeded")

        suuid = list_data["items"][0]["uuid"]
        status, data = await _fetch(c, "GET", f"/suppliers/{suuid}/alternatives?commodity_uuid={commodity}")
        assert status == 200
        assert "items" in data
        assert "total" in data


@pytest.mark.asyncio
async def test_supplier_alternatives_excludes_self():
    async with client() as c:
        status, list_data = await _fetch(c, "GET", "/suppliers")
        if list_data["total"] < 2:
            pytest.skip("Need at least 2 suppliers")

        from db import get_pool
        pool = await get_pool()
        commodity = await pool.fetchval(
            "SELECT uuid FROM energy.commodities WHERE commodity_type = 'crude' LIMIT 1"
        )
        if not commodity:
            pytest.skip("No crude commodities")

        suuid = list_data["items"][0]["uuid"]
        status, data = await _fetch(c, "GET", f"/suppliers/{suuid}/alternatives?commodity_uuid={commodity}")
        for alt in data.get("items", []):
            assert alt["supplier_uuid"] != suuid, "Alternative supplier should exclude original"


# ════════════════════════════════════════════════════════════════════════════
# 3. Refinery-Crude Compatibility
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_compute_compatibility():
    async with client() as c:
        status, data = await _fetch(c, "POST", "/compatibility/compute")
        assert status == 200
        assert "refineries_evaluated" in data
        assert "commodities_evaluated" in data
        assert data["refineries_evaluated"] > 0
        assert data["commodities_evaluated"] > 0


@pytest.mark.asyncio
async def test_get_compatibility():
    async with client() as c:
        status, data = await _fetch(c, "GET", "/compatibility")
        assert status == 200
        assert "items" in data
        if data["total"] > 0:
            item = data["items"][0]
            assert "compatibility" in item
            assert "refinery_name" in item
            assert "commodity_name" in item
            assert item["compatibility"] in ("optimal", "compatible", "partial", "incompatible")


@pytest.mark.asyncio
async def test_compatibility_filter_by_refinery():
    async with client() as c:
        status, data = await _fetch(c, "GET", "/compatibility")
        if data["total"] == 0:
            pytest.skip("No compatibility data")
        ref_uuid = data["items"][0]["refinery_uuid"]
        status, filtered = await _fetch(c, "GET", f"/compatibility?refinery_uuid={ref_uuid}")
        assert status == 200
        for item in filtered["items"]:
            assert item["refinery_uuid"] == ref_uuid


@pytest.mark.asyncio
async def test_compatibility_filter_by_min_score():
    async with client() as c:
        status, data = await _fetch(c, "GET", "/compatibility?min_score=optimal")
        assert status == 200
        for item in data["items"]:
            assert item["compatibility"] in ("optimal",)


@pytest.mark.asyncio
async def test_refinery_recommendations():
    async with client() as c:
        status, compat_data = await _fetch(c, "GET", "/compatibility")
        if compat_data["total"] == 0:
            pytest.skip("No compatibility data")
        ref_uuid = compat_data["items"][0]["refinery_uuid"]
        status, data = await _fetch(c, "GET", f"/compatibility/refinery/{ref_uuid}")
        assert status == 200
        assert "items" in data
        if data["total"] > 0:
            assert data["items"][0]["refinery_uuid"] == ref_uuid


# ════════════════════════════════════════════════════════════════════════════
# 4. Route Costs
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_compute_route_costs():
    async with client() as c:
        status, data = await _fetch(c, "POST", "/routes/compute")
        assert status == 200
        assert "routes_evaluated" in data
        assert "route_costs_created" in data


@pytest.mark.asyncio
async def test_list_routes():
    async with client() as c:
        status, data = await _fetch(c, "GET", "/routes")
        assert status == 200
        assert "items" in data
        if data["total"] > 0:
            r = data["items"][0]
            assert "total_cost_bbl" in r
            assert "transport_cost_bbl" in r
            assert "origin_node_id" in r


# ════════════════════════════════════════════════════════════════════════════
# 5. Procurement Optimization
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_run_optimization_default():
    async with client() as c:
        status, data = await _fetch(c, "POST", "/optimize", json={
            "supply_gap_bpd": 500000,
            "optimization_goal": "balanced",
            "max_cost_bbl": 100,
            "max_risk_score": 0.8,
            "max_lead_days": 60,
        })
        assert status == 200
        assert "options" in data
        assert "pareto_frontier" in data
        assert "recommended" in data or data["total_options"] == 0
        assert "optimization_goal" in data
        assert data["supply_gap_bpd"] == 500000


@pytest.mark.asyncio
async def test_optimization_cost_goal():
    async with client() as c:
        status, data = await _fetch(c, "POST", "/optimize", json={
            "supply_gap_bpd": 300000,
            "optimization_goal": "cost",
        })
        assert status == 200
        if data["recommended"]:
            costs = [o["cost_bbl"] for o in data["options"]]
            assert data["recommended"]["cost_bbl"] == min(costs)


@pytest.mark.asyncio
async def test_optimization_risk_goal():
    async with client() as c:
        status, data = await _fetch(c, "POST", "/optimize", json={
            "supply_gap_bpd": 300000,
            "optimization_goal": "risk",
        })
        assert status == 200
        if data["recommended"]:
            risks = [o["risk_score"] for o in data["options"]]
            assert data["recommended"]["risk_score"] == min(risks)


@pytest.mark.asyncio
async def test_optimization_speed_goal():
    async with client() as c:
        status, data = await _fetch(c, "POST", "/optimize", json={
            "supply_gap_bpd": 300000,
            "optimization_goal": "speed",
        })
        assert status == 200
        if data["recommended"]:
            leads = [o["lead_time_days"] for o in data["options"]]
            assert data["recommended"]["lead_time_days"] == min(leads)


@pytest.mark.asyncio
async def test_optimization_no_suppliers():
    async with client() as c:
        status, data = await _fetch(c, "POST", "/optimize", json={
            "supply_gap_bpd": 500000,
            "max_cost_bbl": 1.0,
        })
        assert status == 200
        assert data["total_options"] == 0
        assert "message" in data


# ════════════════════════════════════════════════════════════════════════════
# 6. Procurement Orchestration (End-to-End)
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_run_procurement_standalone():
    async with client() as c:
        status, data = await _fetch(c, "POST", "/run", json={
            "name": "Test Procurement Run",
            "supply_gap_bpd": 500000,
            "optimization_goal": "balanced",
            "max_cost_bbl": 100,
            "max_risk_score": 0.8,
            "max_lead_days": 60,
        })
        assert status == 200
        assert "run_uuid" in data
        assert data["name"] == "Test Procurement Run"
        assert data["supply_gap_bpd"] == 500000
        assert "executive_summary" in data
        assert "recommended" in data or data["recommendations_count"] == 0
        assert "execution_time_ms" in data
        return data["run_uuid"]


@pytest.mark.asyncio
async def test_run_procurement_with_simulation():
    """Link procurement run to a simulation run."""
    async with client() as c:
        from db import get_pool
        pool = await get_pool()
        sim = await pool.fetchrow(
            "SELECT uuid FROM energy.digital_twin_runs WHERE status = 'completed' ORDER BY created_at DESC LIMIT 1"
        )
        if not sim:
            pytest.skip("No completed simulation runs")

        status, data = await _fetch(c, "POST", "/run", json={
            "simulation_run_uuid": str(sim["uuid"]),
            "name": "Simulation-Linked Procurement",
            "optimization_goal": "balanced",
        })
        assert status == 200
        assert "run_uuid" in data


@pytest.mark.asyncio
async def test_run_procurement_invalid_simulation():
    async with client() as c:
        status, data = await _fetch(c, "POST", "/run", json={
            "simulation_run_uuid": "00000000-0000-0000-0000-000000000000",
            "name": "Invalid Sim Run",
        })
        assert status == 404


@pytest.mark.asyncio
async def test_list_procurement_runs():
    async with client() as c:
        status, data = await _fetch(c, "GET", "/runs")
        assert status == 200
        assert "items" in data
        assert "total" in data
        if data["total"] > 0:
            r = data["items"][0]
            assert "uuid" in r
            assert "name" in r
            assert "status" in r


@pytest.mark.asyncio
async def test_list_procurement_runs_by_status():
    async with client() as c:
        status, data = await _fetch(c, "GET", "/runs?status=completed")
        assert status == 200
        for r in data["items"]:
            assert r["status"] == "completed"


@pytest.mark.asyncio
async def test_get_procurement_run():
    async with client() as c:
        status, list_data = await _fetch(c, "GET", "/runs")
        if list_data["total"] == 0:
            pytest.skip("No procurement runs")
        ruuid = list_data["items"][0]["uuid"]
        status, data = await _fetch(c, "GET", f"/runs/{ruuid}")
        assert status == 200
        assert "run" in data
        assert "recommendations" in data
        assert "executive_cards" in data
        assert "assumptions" in data


@pytest.mark.asyncio
async def test_get_procurement_run_not_found():
    async with client() as c:
        status, data = await _fetch(c, "GET", "/runs/00000000-0000-0000-0000-000000000000")
        assert status == 404


@pytest.mark.asyncio
async def test_executive_summary():
    async with client() as c:
        status, list_data = await _fetch(c, "GET", "/runs")
        if list_data["total"] == 0:
            pytest.skip("No procurement runs")
        ruuid = list_data["items"][0]["uuid"]
        status, data = await _fetch(c, "GET", f"/runs/{ruuid}/executive-summary")
        assert status == 200
        assert "run" in data
        assert "executive_cards" in data


# ════════════════════════════════════════════════════════════════════════════
# 7. Executive Recommendation Cards
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_list_executive_cards():
    async with client() as c:
        status, data = await _fetch(c, "GET", "/executive-cards")
        assert status == 200
        assert "items" in data
        if data["total"] > 0:
            card = data["items"][0]
            assert "title" in card
            assert "summary" in card
            assert "category" in card
            assert "severity" in card
            assert "financial_impact" in card
            assert "operational_impact" in card
            assert "recommended_actions" in card


@pytest.mark.asyncio
async def test_list_executive_cards_filtered():
    async with client() as c:
        status, data = await _fetch(c, "GET", "/executive-cards")
        if data["total"] == 0:
            pytest.skip("No executive cards")
        # Test severity filter with first non-null severity
        severity = data["items"][0]["severity"]
        status, filtered = await _fetch(c, "GET", f"/executive-cards?severity={severity}")
        assert status == 200
        for card in filtered["items"]:
            assert card["severity"] == severity


@pytest.mark.asyncio
async def test_acknowledge_card():
    async with client() as c:
        status, list_data = await _fetch(c, "GET", "/executive-cards")
        if list_data["total"] == 0:
            pytest.skip("No executive cards to acknowledge")
        unacked = [c for c in list_data["items"] if not c["is_acknowledged"]]
        if not unacked:
            pytest.skip("All cards already acknowledged")
        card_uuid = unacked[0]["uuid"]
        status, data = await _fetch(c, "POST", f"/executive-cards/{card_uuid}/ack", json={
            "acknowledged_by": "test_user",
        })
        assert status == 200
        assert data["acknowledged"] == card_uuid

        # Verify
        status, after = await _fetch(c, "GET", f"/executive-cards")
        for card in after["items"]:
            if card["uuid"] == card_uuid:
                assert card["is_acknowledged"] is True
                break


# ════════════════════════════════════════════════════════════════════════════
# 8. Procurement Recommendations
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_list_recommendations():
    async with client() as c:
        status, data = await _fetch(c, "GET", "/recommendations")
        assert status == 200
        assert "items" in data
        if data["total"] > 0:
            rec = data["items"][0]
            assert "title" in rec
            assert "priority" in rec
            assert "recommendation_type" in rec


@pytest.mark.asyncio
async def test_recommendations_filtered_by_run():
    async with client() as c:
        status, runs_data = await _fetch(c, "GET", "/runs")
        if runs_data["total"] == 0:
            pytest.skip("No procurement runs")
        ruuid = runs_data["items"][0]["uuid"]
        status, data = await _fetch(c, "GET", f"/recommendations?run_uuid={ruuid}")
        assert status == 200
        for rec in data["items"]:
            assert rec["procurement_run_uuid"] == ruuid


# ════════════════════════════════════════════════════════════════════════════
# 9. Data Integrity
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_procurement_run_has_executive_summary():
    """Every completed procurement run should have an executive summary."""
    async with client() as c:
        status, data = await _fetch(c, "GET", "/runs?status=completed")
        for run in data["items"]:
            assert run.get("executive_summary"), f"Run {run['uuid']} has no executive summary"


@pytest.mark.asyncio
async def test_recommendations_have_required_fields():
    """Every recommendation must have required fields."""
    async with client() as c:
        status, data = await _fetch(c, "GET", "/recommendations")
        for rec in data["items"]:
            assert rec["title"]
            assert rec["recommendation_type"]
            assert rec["priority"] in ("critical", "high", "medium", "low")


@pytest.mark.asyncio
async def test_executive_cards_have_required_fields():
    """Every executive card must have required fields."""
    async with client() as c:
        status, data = await _fetch(c, "GET", "/executive-cards")
        for card in data["items"]:
            assert card["title"]
            assert card["summary"]
            assert card["category"]
            assert card["severity"] in ("critical", "warning", "info")
            assert card["recommended_actions"] is not None


@pytest.mark.asyncio
async def test_suppliers_have_unique_uuids():
    """All suppliers should have unique UUIDs."""
    async with client() as c:
        status, data = await _fetch(c, "GET", "/suppliers")
        uuids = [s["uuid"] for s in data["items"]]
        assert len(uuids) == len(set(uuids))


@pytest.mark.asyncio
async def test_compatibility_scores_valid():
    """All compatibility scores must be valid enum values."""
    async with client() as c:
        status, data = await _fetch(c, "GET", "/compatibility")
        for item in data["items"]:
            assert item["compatibility"] in ("optimal", "compatible", "partial", "incompatible")


# ════════════════════════════════════════════════════════════════════════════
# 10. Edge Cases
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_procurement_run_zero_gap():
    """Test procurement run with zero supply gap."""
    async with client() as c:
        status, data = await _fetch(c, "POST", "/run", json={
            "name": "Zero Gap Test",
            "supply_gap_bpd": 0,
        })
        assert status == 200
        assert data["supply_gap_bpd"] == 0


@pytest.mark.asyncio
async def test_procurement_run_very_large_gap():
    """Test procurement run with very large supply gap."""
    async with client() as c:
        status, data = await _fetch(c, "POST", "/run", json={
            "name": "Large Gap Test",
            "supply_gap_bpd": 10000000,
            "max_cost_bbl": 200,
        })
        assert status == 200


@pytest.mark.asyncio
async def test_concurrent_runs():
    """Two procurement runs back to back should both succeed."""
    async with client() as c:
        status1, data1 = await _fetch(c, "POST", "/run", json={
            "name": "Concurrent Test 1",
            "supply_gap_bpd": 200000,
        })
        assert status1 == 200

        status2, data2 = await _fetch(c, "POST", "/run", json={
            "name": "Concurrent Test 2",
            "supply_gap_bpd": 400000,
        })
        assert status2 == 200

        assert data1["run_uuid"] != data2["run_uuid"]


@pytest.mark.asyncio
async def test_optimize_invalid_goal():
    """Test optimization with an invalid goal should still return options."""
    async with client() as c:
        status, data = await _fetch(c, "POST", "/optimize", json={
            "supply_gap_bpd": 100000,
            "optimization_goal": "invalid_goal",
        })
        assert status == 200
        # Should default to balanced behavior



# ════════════════════════════════════════════════════════════════════════════
# Summary
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_validation_summary():
    """Print summary of all validation checks."""
    async with client() as c:
        health = await (await c.get(f"{BASE}/health")).json()
        runs = await (await c.get(f"{BASE}/runs")).json()
        suppliers = await (await c.get(f"{BASE}/suppliers")).json()
        compat = await (await c.get(f"{BASE}/compatibility")).json()
        recs = await (await c.get(f"{BASE}/recommendations")).json()
        cards = await (await c.get(f"{BASE}/executive-cards")).json()

        print(f"\n{'='*60}")
        print(f"  PROCUREMENT ORCHESTRATOR — VALIDATION SUMMARY")
        print(f"{'='*60}")
        print(f"  Health:           {health['status']}")
        print(f"  Procurement Runs: {health['procurement_runs']}")
        print(f"  Recommendations:  {health['recommendations']}")
        print(f"  Executive Cards:  {health['executive_cards']}")
        print(f"  Suppliers Intel:  {health['suppliers_with_intel']}")
        print(f"  Compat Pairs:     {health['refinery_crude_pairs']}")
        print(f"  Route Costs:      {health['route_costs']}")
        print(f"  Latest Run:       {health['latest_run'] or 'none'}")
        print(f"  Total Runs:       {runs['total']}")
        print(f"  Total Suppliers:  {suppliers['total']}")
        print(f"  Total Compat:     {compat['total']}")
        print(f"  Total Recs:       {recs['total']}")
        print(f"  Total Cards:      {cards['total']}")
        print(f"{'='*60}")
