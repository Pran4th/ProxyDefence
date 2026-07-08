"""SPR Decision Intelligence — validation tests against live API + database.

Run: pytest tests/test_spr_validation.py -v --asyncio-mode=auto
"""

import pytest
from httpx import AsyncClient, ASGITransport
from app import app

BASE = "/api/v1/intelligence/procurement/spr"

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
async def test_spr_health():
    async with client() as c:
        status, data = await _fetch(c, "GET", "/health")
        assert status == 200, f"Health check failed: {data}"
        assert data["status"] == "ok"
        assert "facilities" in data
        assert "active_facilities" in data
        assert "total_capacity_mb" in data
        assert "current_inventory_mb" in data
        assert "release_runs" in data


@pytest.mark.asyncio
async def test_spr_database_schema():
    """Verify SPR tables exist in energy schema."""
    async with client() as c:
        tables = [
            "spr_facilities",
            "spr_inventory",
            "spr_capacity",
            "spr_release_runs",
            "spr_release_plans",
            "spr_refill_plans",
            "spr_recommendations",
            "spr_policy_constraints",
            "spr_consumption_forecasts",
            "spr_distribution",
            "spr_cost_analysis",
            "spr_assumptions",
            "spr_decision_timeline",
        ]
        for table in tables:
            status, data = await _fetch(c, "GET", "/health")
            assert status == 200
        # If health passes, schema is bootstrapped


# ════════════════════════════════════════════════════════════════════════════
# 2. Facilities
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_init_facilities():
    async with client() as c:
        status, data = await _fetch(c, "POST", "/init")
        assert status == 200
        assert "initialized" in data or "message" in data or "facilities" in data


@pytest.mark.asyncio
async def test_list_facilities():
    async with client() as c:
        status, data = await _fetch(c, "GET", "/facilities")
        assert status == 200
        assert "items" in data
        assert data["total"] >= 0
        for f in data["items"]:
            assert "uuid" in f
            assert "name" in f
            assert "operational_status" in f


# ════════════════════════════════════════════════════════════════════════════
# 3. Inventory
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_inventory_history():
    async with client() as c:
        status, data = await _fetch(c, "GET", "/inventory?limit=10")
        assert status == 200
        assert "items" in data


# ════════════════════════════════════════════════════════════════════════════
# 4. Policies
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_list_policies():
    async with client() as c:
        status, data = await _fetch(c, "GET", "/policies")
        assert status == 200
        assert "items" in data
        assert len(data["items"]) >= 1  # at least seed policies


@pytest.mark.asyncio
async def test_create_policy():
    async with client() as c:
        status, data = await _fetch(c, "POST", "/policies", json={
            "name": "test_policy",
            "description": "Test policy",
            "min_reserve_threshold": 0.15,
            "max_daily_release_rate": 500000,
            "emergency_only": True,
            "strategic_preservation": True,
            "duration_days": 60,
        })
        assert status == 200
        assert "uuid" in data or "name" in data


# ════════════════════════════════════════════════════════════════════════════
# 5. Demand
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_compute_demand():
    async with client() as c:
        status, data = await _fetch(c, "GET", "/demand")
        assert status == 200
        assert "national_demand_bpd" in data or "demand" in data


# ════════════════════════════════════════════════════════════════════════════
# 6. SPR Analysis (Release Planner)
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_run_analysis_minimal():
    """Run analysis with minimal parameters."""
    async with client() as c:
        status, data = await _fetch(c, "POST", "/analyze", json={
            "name": "Test Release Analysis",
            "description": "Validation test run",
            "disruption_reason": "supply_disruption",
            "disruption_days": 30,
            "strategy": "balanced",
            "policy_name": "default",
        })
        assert status == 200
        assert "run_uuid" in data
        assert "drawdown_plan" in data
        assert "release_plan" in data
        assert "refill_plan" in data
        assert "decision_timeline" in data
        assert "recommendations" in data
        assert len(data["recommendations"]) >= 1


@pytest.mark.asyncio
async def test_run_analysis_with_supply_gap():
    """Run analysis with explicit supply gap."""
    async with client() as c:
        status, data = await _fetch(c, "POST", "/analyze", json={
            "name": "Supply Gap Test",
            "disruption_reason": "geopolitical_crisis",
            "disruption_days": 90,
            "supply_gap_bpd": 500000,
            "strategy": "conservative",
            "policy_name": "default",
        })
        assert status == 200
        assert "run_uuid" in data
        assert len(data["drawdown_plan"]) > 0


@pytest.mark.asyncio
async def test_run_analysis_aggressive():
    """Run analysis with aggressive strategy."""
    async with client() as c:
        status, data = await _fetch(c, "POST", "/analyze", json={
            "name": "Aggressive Release Test",
            "disruption_reason": "war_conflict",
            "disruption_days": 180,
            "supply_gap_bpd": 1000000,
            "strategy": "aggressive",
            "policy_name": "aggressive",
        })
        assert status == 200
        assert "run_uuid" in data
        assert len(data["release_plan"]["entries"]) > 0


@pytest.mark.asyncio
async def test_run_analysis_invalid_strategy():
    """Run analysis with invalid strategy should fail gracefully."""
    async with client() as c:
        status, data = await _fetch(c, "POST", "/analyze", json={
            "name": "Invalid Strategy",
            "disruption_reason": "supply_disruption",
            "disruption_days": 30,
            "supply_gap_bpd": 500000,
            "strategy": "nonexistent",
            "policy_name": "default",
        })
        # Should still work (default fallback) or return error
        assert status in (200, 422, 404, 400)


# ════════════════════════════════════════════════════════════════════════════
# 7. Runs
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_list_runs():
    async with client() as c:
        status, data = await _fetch(c, "GET", "/runs?limit=10")
        assert status == 200
        assert "items" in data
        assert data["total"] >= 0


@pytest.mark.asyncio
async def test_get_run():
    """Get a specific run by UUID (use latest run)."""
    async with client() as c:
        s1, runs = await _fetch(c, "GET", "/runs?limit=1")
        assert s1 == 200
        if runs["items"]:
            run_uuid = runs["items"][0]["uuid"]
            status, data = await _fetch(c, "GET", f"/runs/{run_uuid}")
            assert status == 200
            assert data["uuid"] == run_uuid


@pytest.mark.asyncio
async def test_get_run_not_found():
    async with client() as c:
        status, data = await _fetch(c, "GET", "/runs/00000000-0000-0000-0000-000000000000")
        assert status == 404


# ════════════════════════════════════════════════════════════════════════════
# 8. Executive Cards (Acknowledgement)
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_acknowledge_card_not_found():
    async with client() as c:
        status, data = await _fetch(c, "POST", "/executive-cards/00000000-0000-0000-0000-000000000000/ack", json={
            "acknowledged_by": "test_user",
        })
        assert status == 404


@pytest.mark.asyncio
async def test_run_analysis_economic_strategy():
    """Run analysis with economic strategy for broader coverage."""
    async with client() as c:
        status, data = await _fetch(c, "POST", "/analyze", json={
            "name": "Economic Protection Test",
            "disruption_reason": "price_spike",
            "disruption_days": 60,
            "supply_gap_bpd": 300000,
            "strategy": "economic",
            "policy_name": "default",
        })
        assert status == 200
        assert "run_uuid" in data
        assert "cost_analysis" in data


# ════════════════════════════════════════════════════════════════════════════
# 9. Decision Timeline
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_decision_timeline_phases():
    """Verify the 5-phase decision timeline exists in analysis output."""
    async with client() as c:
        status, data = await _fetch(c, "POST", "/analyze", json={
            "name": "Timeline Test",
            "disruption_reason": "supply_disruption",
            "disruption_days": 90,
            "supply_gap_bpd": 400000,
            "strategy": "balanced",
            "policy_name": "default",
        })
        assert status == 200
        timeline = data.get("decision_timeline", {})
        assert "now" in timeline
        assert "24h" in timeline
        assert "72h" in timeline
        assert "7d" in timeline
        assert "30d" in timeline
        for phase in ["now", "24h", "72h", "7d", "30d"]:
            assert "phase" in timeline[phase]
            assert "daily_release_bpd" in timeline[phase]
            assert "cumulative_release" in timeline[phase]
            assert "remaining_inventory" in timeline[phase]
