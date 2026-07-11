"""Adaptive Procurement Orchestrator API — supplier intelligence, refinery compatibility, optimization, and executive recommendations."""

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from db import get_pool
from backend.shared.logging_config import get_logger
from services.procurement.orchestrator import ProcurementOrchestrator, normalize_executive_card
from services.procurement.compatibility import RefineryCompatibility
from services.procurement.supplier_intel import SupplierIntelligence
from services.procurement.optimizer import ProcurementOptimizer
from services.procurement.spr_engine import SPREngine

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/intelligence/procurement", tags=["Procurement"])


def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    return dict(row)


# ── Supplier Intelligence ────────────────────────────────────────────────


@router.post("/suppliers/enrich")
async def enrich_suppliers(pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    """Auto-generate intelligence profiles for all suppliers."""
    intel = SupplierIntelligence(pool)
    count = await intel.enrich_all()
    return {"enriched": count}


@router.get("/suppliers")
async def list_suppliers(pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    """List all suppliers with composite procurement scores."""
    intel = SupplierIntelligence(pool)
    suppliers = await intel.score_suppliers()
    return {"items": suppliers, "total": len(suppliers)}


@router.get("/suppliers/{supplier_uuid}")
async def get_supplier(
    supplier_uuid: str, pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    """Get supplier profile with intelligence data."""
    intel = SupplierIntelligence(pool)
    profile = await intel.get_supplier_profile(supplier_uuid)
    if not profile:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return profile


@router.get("/suppliers/{supplier_uuid}/alternatives")
async def find_alternatives(
    supplier_uuid: str,
    commodity_uuid: str = Query(..., description="UUID of the commodity to source"),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    """Find alternative suppliers for a commodity, excluding the current supplier."""
    intel = SupplierIntelligence(pool)
    alternatives = await intel.find_alternatives(
        commodity_uuid=commodity_uuid,
        exclude_supplier_uuid=supplier_uuid,
    )
    return {"items": alternatives, "total": len(alternatives)}


# ── Refinery Compatibility ──────────────────────────────────────────────


@router.post("/compatibility/compute")
async def compute_compatibility(pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    """Compute and persist refinery-crude compatibility for all pairs."""
    engine = RefineryCompatibility(pool)
    result = await engine.compute_all()
    return result


@router.get("/compatibility")
async def get_compatibility(
    refinery_uuid: str | None = Query(None),
    commodity_uuid: str | None = Query(None),
    min_score: str | None = Query(None),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    """Get refinery-crude compatibility records."""
    engine = RefineryCompatibility(pool)
    items = await engine.get_compatibility(
        refinery_uuid=refinery_uuid,
        commodity_uuid=commodity_uuid,
        min_score=min_score,
    )
    return {"items": items, "total": len(items)}


@router.get("/compatibility/refinery/{refinery_uuid}")
async def get_refinery_recommendations(
    refinery_uuid: str, pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    """Get recommended crude types for a specific refinery."""
    engine = RefineryCompatibility(pool)
    items = await engine.get_refinery_recommendations(refinery_uuid)
    return {"items": items, "total": len(items)}


# ── Route Costs ─────────────────────────────────────────────────────────


@router.post("/routes/compute")
async def compute_route_costs(pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    """Compute and persist route costs from the network graph."""
    optimizer = ProcurementOptimizer(pool)
    result = await optimizer.compute_route_costs()
    return result


@router.get("/routes")
async def list_routes(
    origin_node_id: int | None = Query(None),
    destination_node_id: int | None = Query(None),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    """List route costs."""
    conditions = ["is_deleted = false"]
    params = []
    if origin_node_id:
        conditions.append(f"origin_node_id = ${len(params) + 1}")
        params.append(origin_node_id)
    if destination_node_id:
        conditions.append(f"destination_node_id = ${len(params) + 1}")
        params.append(destination_node_id)
    where = " AND ".join(conditions) if conditions else "1=1"
    rows = await pool.fetch(
        f"SELECT * FROM energy.route_costs WHERE {where} ORDER BY total_cost_bbl ASC LIMIT 200",
        *params,
    )
    return {"items": [_row_to_dict(r) for r in rows], "total": len(rows)}


# ── Optimization ────────────────────────────────────────────────────────


@router.post("/optimize")
async def run_optimization(
    body: dict[str, Any], pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    """Run multi-objective procurement optimization."""
    optimizer = ProcurementOptimizer(pool)
    result = await optimizer.optimize(
        supply_gap_bpd=body.get("supply_gap_bpd", 100000),
        commodity_uuid=body.get("commodity_uuid"),
        destination_region=body.get("destination_region"),
        max_cost_bbl=body.get("max_cost_bbl", 100.0),
        max_risk_score=body.get("max_risk_score", 0.8),
        max_lead_days=body.get("max_lead_days", 60),
        optimization_goal=body.get("optimization_goal", "balanced"),
        top_n=body.get("top_n", 5),
    )
    return result


# ── Orchestration ───────────────────────────────────────────────────────


@router.post("/run")
async def run_procurement(
    body: dict[str, Any], pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    """Execute a full procurement orchestration run."""
    orchestrator = ProcurementOrchestrator(pool)
    try:
        result = await orchestrator.run_procurement(
            simulation_run_uuid=body.get("simulation_run_uuid"),
            name=body.get("name", "Procurement Optimization Run"),
            description=body.get("description", ""),
            supply_gap_bpd=body.get("supply_gap_bpd"),
            commodity_uuid=body.get("commodity_uuid"),
            destination_region=body.get("destination_region"),
            optimization_goal=body.get("optimization_goal", "balanced"),
            max_cost_bbl=body.get("max_cost_bbl", 100.0),
            max_risk_score=body.get("max_risk_score", 0.8),
            max_lead_days=body.get("max_lead_days", 60),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/runs")
async def list_procurement_runs(
    status: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    """List procurement optimization runs."""
    orchestrator = ProcurementOrchestrator(pool)
    items = await orchestrator.list_runs(status=status, limit=limit)
    return {"items": items, "total": len(items)}


@router.get("/runs/{run_uuid}")
async def get_procurement_run(
    run_uuid: str, pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    """Get a procurement run with all recommendations and executive cards."""
    orchestrator = ProcurementOrchestrator(pool)
    result = await orchestrator.get_run(run_uuid)
    if not result:
        raise HTTPException(status_code=404, detail="Procurement run not found")
    return result


@router.get("/runs/{run_uuid}/executive-summary")
async def get_executive_summary(
    run_uuid: str, pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    """Get executive summary for a procurement run."""
    orchestrator = ProcurementOrchestrator(pool)
    result = await orchestrator.get_executive_summary(run_uuid)
    if not result:
        raise HTTPException(status_code=404, detail="Procurement run not found")
    return result


@router.post("/executive-cards/{card_uuid}/ack")
async def acknowledge_card(
    card_uuid: str,
    body: dict[str, Any] | None = None,
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    """Acknowledge an executive recommendation card."""
    orchestrator = ProcurementOrchestrator(pool)
    user = (body or {}).get("acknowledged_by", "user")
    success = await orchestrator.ack_card(card_uuid, acknowledged_by=user)
    if not success:
        raise HTTPException(status_code=404, detail="Card not found")
    return {"acknowledged": card_uuid, "by": user}


# ── Recommendations ─────────────────────────────────────────────────────


@router.get("/recommendations")
async def list_recommendations(
    run_uuid: str | None = Query(None),
    priority: str | None = Query(None),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    """List procurement recommendations."""
    conditions = ["is_deleted = false"]
    params = []
    if run_uuid:
        conditions.append(f"procurement_run_uuid = ${len(params) + 1}::uuid")
        params.append(run_uuid)
    if priority:
        conditions.append(f"priority = ${len(params) + 1}")
        params.append(priority)
    where = " AND ".join(conditions)
    rows = await pool.fetch(
        f"SELECT * FROM energy.procurement_recommendations WHERE {where} ORDER BY priority, created_at DESC LIMIT 100",
        *params,
    )
    return {"items": [_row_to_dict(r) for r in rows], "total": len(rows)}


@router.get("/executive-cards")
async def list_executive_cards(
    severity: str | None = Query(None),
    category: str | None = Query(None),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    """List executive recommendation cards."""
    conditions = ["is_deleted = false"]
    params = []
    if severity:
        conditions.append(f"severity = ${len(params) + 1}")
        params.append(severity)
    if category:
        conditions.append(f"category = ${len(params) + 1}")
        params.append(category)
    where = " AND ".join(conditions)
    rows = await pool.fetch(
        f"SELECT * FROM energy.executive_recommendations WHERE {where} ORDER BY created_at DESC LIMIT 50",
        *params,
    )
    items = [normalize_executive_card(_row_to_dict(r)) for r in rows]
    return {"items": items, "total": len(items)}


# ── SPR Optimizer ───────────────────────────────────────────────────────


@router.post("/spr/init")
async def spr_initialize(pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    """Initialize SPR facilities from strategic_petroleum_reserves data."""
    engine = SPREngine(pool)
    return await engine.initialize_facilities()


@router.get("/spr/facilities")
async def spr_facilities(pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    """List SPR facilities with current status."""
    engine = SPREngine(pool)
    items = await engine.get_facilities()
    return {"items": items, "total": len(items)}


@router.get("/spr/inventory")
async def spr_inventory(
    facility_uuid: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    """Get SPR inventory time-series."""
    engine = SPREngine(pool)
    items = await engine.get_inventory_history(facility_uuid, limit)
    return {"items": items, "total": len(items)}


@router.get("/spr/policies")
async def spr_policies(pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    """Get SPR policy constraints."""
    engine = SPREngine(pool)
    items = await engine.get_policies()
    return {"items": items, "total": len(items)}


@router.post("/spr/policies")
async def spr_create_policy(body: dict[str, Any], pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    """Create a new SPR policy."""
    engine = SPREngine(pool)
    return await engine.create_policy(body)


@router.get("/spr/demand")
async def spr_demand(pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    """Compute SPR demand from Digital Twin demand profiles."""
    engine = SPREngine(pool)
    return await engine.compute_demand()


@router.post("/spr/analyze")
async def spr_run_analysis(body: dict[str, Any], pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    """Run a complete SPR optimization and generate executive recommendations."""
    engine = SPREngine(pool)
    try:
        result = await engine.run_optimization(
            name=body.get("name", "SPR Release Analysis"),
            description=body.get("description", ""),
            scenario_uuid=body.get("scenario_uuid"),
            simulation_run_uuid=body.get("simulation_run_uuid"),
            procurement_run_uuid=body.get("procurement_run_uuid"),
            disruption_reason=body.get("disruption_reason", "supply_disruption"),
            disruption_days=body.get("disruption_days", 90),
            supply_gap_bpd=body.get("supply_gap_bpd"),
            strategy=body.get("strategy", "balanced"),
            policy_name=body.get("policy_name", "default"),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/spr/runs")
async def spr_list_runs(
    limit: int = Query(20, ge=1, le=100),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    """List SPR optimization runs."""
    engine = SPREngine(pool)
    items = await engine.list_runs(limit)
    return {"items": items, "total": len(items)}


@router.get("/spr/runs/{run_uuid}")
async def spr_get_run(run_uuid: str, pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    """Get SPR optimization run with full details."""
    engine = SPREngine(pool)
    result = await engine.get_run(run_uuid)
    if not result:
        raise HTTPException(status_code=404, detail="SPR run not found")
    return result


@router.post("/spr/executive-cards/{card_uuid}/ack")
async def spr_ack_card(
    card_uuid: str, body: dict[str, Any] | None = None,
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    """Acknowledge an SPR recommendation."""
    acknowledged_by = (body or {}).get("acknowledged_by", "user")
    result = await pool.execute(
        "UPDATE energy.spr_recommendations SET is_acknowledged = TRUE, acknowledged_at = NOW(), acknowledged_by = $2 WHERE uuid = $1::uuid",
        card_uuid, acknowledged_by,
    )
    if "UPDATE 0" in result:
        raise HTTPException(status_code=404, detail="Card not found")
    return {"acknowledged": card_uuid, "by": acknowledged_by}


@router.get("/spr/health")
async def spr_health(pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    """Get SPR system health status."""
    engine = SPREngine(pool)
    return await engine.health()


# ── Health ──────────────────────────────────────────────────────────────


@router.get("/health")
async def procurement_health(pool: asyncpg.Pool = Depends(get_pool)) -> dict[str, Any]:
    """Get procurement system health status."""
    orchestrator = ProcurementOrchestrator(pool)
    return await orchestrator.health()
