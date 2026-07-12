"""Intelligence API — risk scoring, signals, scenarios, and dashboards."""

import uuid
from datetime import datetime, timezone
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from db import get_pool
from filters import FilterParams
from models import ASSET_TYPE_BY_TABLE
from backend.shared.logging_config import get_logger
from services.risk_engine import (
    ArticleSignalIngestor,
    CommodityPriceIngestor,
    RiskScoringEngine,
    SignalDetector,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/intelligence", tags=["Intelligence"])


def _table_to_asset(table_name: str) -> str:
    """Convert plural table name to singular asset type (e.g. import_corridors -> import_corridor)."""
    return ASSET_TYPE_BY_TABLE.get(table_name, table_name.rstrip("s"))


def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    return dict(row)


# ── Signals ─────────────────────────────────────────────────────────────────


@router.post("/signals", status_code=201)
async def create_signal(
    body: dict[str, Any],
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    detector = SignalDetector(pool)
    try:
        result = await detector.ingest_signal(body)
        return _row_to_dict(result)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/signals")
async def list_signals(
    severity: str | None = Query(None, regex="^(low|moderate|elevated|high|critical)$"),
    risk_dimension: str | None = Query(None, regex="^(geopolitical|operational|economic|environmental)$"),
    pool: asyncpg.Pool = Depends(get_pool),
    filters: FilterParams = Depends(),
) -> dict[str, Any]:
    conditions = ["expires_at > NOW()"]
    params: list[Any] = []

    if severity:
        conditions.append(f"severity = ${len(params) + 1}")
        params.append(severity)
    if risk_dimension:
        conditions.append(f"risk_dimension = ${len(params) + 1}")
        params.append(risk_dimension)

    where = " AND ".join(conditions)
    count_sql = f"SELECT COUNT(*) FROM energy.disruption_signals WHERE {where}"
    total = await pool.fetchval(count_sql, *params)

    order = "created_at DESC"
    params.append(filters.limit)
    params.append(filters.offset)
    data_sql = f"SELECT * FROM energy.disruption_signals WHERE {where} ORDER BY {order} LIMIT ${len(params)-1} OFFSET ${len(params)}"
    rows = await pool.fetch(data_sql, *params)

    return {
        "items": [_row_to_dict(r) for r in rows],
        "total": total or 0,
        "limit": filters.limit,
        "offset": filters.offset,
    }


@router.get("/signals/{signal_uuid}")
async def get_signal(
    signal_uuid: str,
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    row = await pool.fetchrow(
        "SELECT * FROM energy.disruption_signals WHERE uuid = $1::uuid",
        signal_uuid,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Signal not found")
    return _row_to_dict(row)


@router.get("/signals/{signal_uuid}/explain")
async def explain_signal(
    signal_uuid: str,
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    """Plain-language reasoning + a rough, assumption-labeled economic
    exposure estimate for one signal -- the "why is this high" the
    dashboard shows only a severity badge for today."""
    from services.corridor_risk import CorridorRiskEngine

    row = await pool.fetchrow(
        "SELECT * FROM energy.disruption_signals WHERE uuid = $1::uuid",
        signal_uuid,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Signal not found")

    engine = CorridorRiskEngine(pool)
    explanation = await engine.explain_signal(_row_to_dict(row))
    return {"signal_uuid": signal_uuid, **explanation}


# ── Risk scores ─────────────────────────────────────────────────────────────


@router.get("/risk")
async def get_risk_dashboard(
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    detector = SignalDetector(pool)
    return await detector.get_dashboard()


@router.get("/risk/entity/{entity_uuid}")
async def get_entity_risk(
    entity_uuid: str,
    entity_type: str = Query("import_corridors"),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    engine = RiskScoringEngine(pool)
    scores = await engine.score_entity(entity_uuid, entity_type)
    await engine.persist_score(entity_uuid, entity_type, "overall", scores.get("overall", 0.5))

    scores_row = await pool.fetchrow(
        """SELECT * FROM energy.risk_scores
           WHERE entity_uuid = $1::uuid AND dimension = 'overall'
           ORDER BY created_at DESC LIMIT 1""",
        entity_uuid,
    )

    return {
        "entity_uuid": entity_uuid,
        "entity_type": entity_type,
        "scores": scores,
        "recorded_at": scores_row["created_at"].isoformat() if scores_row else None,
    }


@router.get("/risk/trends")
async def get_risk_trends(
    entity_uuid: str | None = Query(None),
    dimension: str | None = Query(None, regex="^(geopolitical|operational|economic|environmental|overall)$"),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    conditions: list[str] = ["1=1"]
    params: list[Any] = []

    if entity_uuid:
        conditions.append(f"entity_uuid = ${len(params) + 1}::uuid")
        params.append(entity_uuid)
    if dimension:
        conditions.append(f"dimension = ${len(params) + 1}")
        params.append(dimension)

    where = " AND ".join(conditions)
    rows = await pool.fetch(
        f"""SELECT dimension, entity_uuid, score, confidence, created_at
            FROM energy.risk_scores WHERE {where}
            ORDER BY created_at DESC LIMIT 200""",
        *params,
    )

    return {
        "items": [_row_to_dict(r) for r in rows],
        "total": len(rows),
    }


# ── Scenarios ───────────────────────────────────────────────────────────────


@router.post("/scenarios/evaluate")
async def evaluate_scenario(
    body: dict[str, Any],
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    detector = SignalDetector(pool)
    return await detector.evaluate_scenario(body)


@router.get("/scenarios")
async def list_scenarios(
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    rows = await pool.fetch(
        """SELECT * FROM energy.scenario_assumptions
           ORDER BY created_at DESC LIMIT 50"""
    )
    return {"items": [_row_to_dict(r) for r in rows], "total": len(rows)}


@router.get("/scenarios/{scenario_uuid}")
async def get_scenario(
    scenario_uuid: str,
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    row = await pool.fetchrow(
        "SELECT * FROM energy.scenario_assumptions WHERE uuid = $1::uuid",
        scenario_uuid,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return _row_to_dict(row)


# ── Risk factors ────────────────────────────────────────────────────────────


@router.get("/risk-factors")
async def list_risk_factors(
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    rows = await pool.fetch(
        """SELECT * FROM energy.risk_factors ORDER BY created_at DESC LIMIT 100"""
    )
    return {"items": [_row_to_dict(r) for r in rows], "total": len(rows)}


# ── Data ingestion (admin) ──────────────────────────────────────────────────
#
# CommodityPriceIngestor/SanctionsIngestor/AISIngestor previously generated
# fabricated data (hash-jittered "prices", a hardcoded sanctions snapshot, a
# hash-jittered "AIS" feed) and fed it into the live risk-scoring pipeline as
# if it were real intelligence. None of the three has a ready-made live data
# source with a compatible shape to swap in within this pass: AIS data from
# ml-platform's scripts/ingest_aisstream.py lands in a flat file, not a
# queryable table; the live crude-price-api dataset covers only Brent (one of
# ten benchmarks this ingestor claimed to cover); and the OFAC/EU/OpenSanctions
# catalog is individual/entity-level, not the country-program shape
# energy.sanctions expects. Rather than ship a fragile partial integration
# under time pressure, these endpoints stay disabled until a real source is
# wired per-commodity/per-country -- serving fabricated data as if real is
# worse than serving nothing.
#
# ArticleSignalIngestor (news-signals) is the one real source: it derives
# disruption_signals directly from the live news pipeline's own ML output
# (real threat scores, real energy-entity matches), already running as a
# background task on a timer (see app.py). This endpoint exists for a manual
# trigger/visibility into that same real pathway, not a separate source.


@router.post("/ingest/commodity-prices")
async def trigger_commodity_ingest(
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    ingestor = CommodityPriceIngestor(pool)
    created = await ingestor.ingest()
    return {"source": "commodity_prices", "rows_written": created}


@router.post("/ingest/sanctions")
async def trigger_sanctions_ingest() -> None:
    raise HTTPException(
        status_code=501,
        detail="Not wired to a live sanctions source yet. This previously served a hardcoded "
               "10-country snapshot and has been disabled rather than continue serving stale data.",
    )


@router.post("/ingest/ais")
async def trigger_ais_ingest() -> None:
    raise HTTPException(
        status_code=501,
        detail="Not wired to a live AIS source yet. This previously generated simulated vessel/"
               "congestion data and has been disabled rather than continue serving fake positions.",
    )


@router.post("/ingest/news-signals")
async def trigger_news_signal_ingest(
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    ingestor = ArticleSignalIngestor(pool)
    created = await ingestor.ingest()
    return {"source": "news_signals", "signals_created": created}


@router.post("/ingest/all")
async def trigger_all_ingestors(
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    signal_count = await ArticleSignalIngestor(pool).ingest()
    price_count = await CommodityPriceIngestor(pool).ingest()
    return {
        "news_signals": {"signals_created": signal_count},
        "commodity_prices": {"rows_written": price_count},
        "sanctions": "not wired to a live source -- see /ingest/sanctions",
        "ais": "not wired to a live source -- see /ingest/ais",
    }


# ── Commodity prices view ───────────────────────────────────────────────────


@router.get("/commodity-prices")
async def list_commodity_prices(
    pool: asyncpg.Pool = Depends(get_pool),
    filters: FilterParams = Depends(),
) -> dict[str, Any]:
    total = await pool.fetchval("SELECT COUNT(*) FROM energy.commodity_prices")
    rows = await pool.fetch(
        """SELECT * FROM energy.commodity_prices
           ORDER BY recorded_at DESC
           LIMIT $1 OFFSET $2""",
        filters.limit, filters.offset,
    )
    return {"items": [_row_to_dict(r) for r in rows], "total": total or 0, "limit": filters.limit, "offset": filters.offset}


@router.get("/port-congestion")
async def list_port_congestion(
    pool: asyncpg.Pool = Depends(get_pool),
    filters: FilterParams = Depends(),
) -> dict[str, Any]:
    total = await pool.fetchval("SELECT COUNT(*) FROM energy.port_congestion")
    rows = await pool.fetch(
        """SELECT * FROM energy.port_congestion
           ORDER BY congestion_pct DESC
           LIMIT $1 OFFSET $2""",
        filters.limit, filters.offset,
    )
    return {"items": [_row_to_dict(r) for r in rows], "total": total or 0, "limit": filters.limit, "offset": filters.offset}


@router.get("/tanker-availability")
async def list_tanker_availability(
    pool: asyncpg.Pool = Depends(get_pool),
    filters: FilterParams = Depends(),
) -> dict[str, Any]:
    total = await pool.fetchval("SELECT COUNT(*) FROM energy.tanker_availability")
    rows = await pool.fetch(
        """SELECT * FROM energy.tanker_availability
           ORDER BY recorded_at DESC
           LIMIT $1 OFFSET $2""",
        filters.limit, filters.offset,
    )
    return {"items": [_row_to_dict(r) for r in rows], "total": total or 0, "limit": filters.limit, "offset": filters.offset}


@router.get("/sanctions")
async def list_sanctions(
    pool: asyncpg.Pool = Depends(get_pool),
    filters: FilterParams = Depends(),
) -> dict[str, Any]:
    total = await pool.fetchval("SELECT COUNT(*) FROM energy.sanctions")
    rows = await pool.fetch(
        """SELECT * FROM energy.sanctions
           ORDER BY updated_at DESC
           LIMIT $1 OFFSET $2""",
        filters.limit, filters.offset,
    )
    return {"items": [_row_to_dict(r) for r in rows], "total": total or 0, "limit": filters.limit, "offset": filters.offset}


# ── Risk-linked entity details ──────────────────────────────────────────────


@router.get("/entity/{entity_table}/{entity_uuid}/risk-profile")
async def get_entity_risk_profile(
    entity_table: str,
    entity_uuid: str,
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    asset_type = _table_to_asset(entity_table)
    entity_row = await pool.fetchrow(
        f"SELECT * FROM energy.{entity_table} WHERE uuid = $1::uuid AND is_deleted = false",
        entity_uuid,
    )
    if not entity_row:
        raise HTTPException(status_code=404, detail="Entity not found")

    risk_scores = await pool.fetch(
        """SELECT dimension, score, confidence, created_at
           FROM energy.risk_scores
           WHERE entity_uuid = $1::uuid AND expires_at > NOW()
           ORDER BY created_at DESC""",
        entity_uuid,
    )

    signals = await pool.fetch(
        """SELECT * FROM energy.disruption_signals
           WHERE (affected_entity_uuid = $1::uuid OR affected_entity_type = $2)
           AND expires_at > NOW()
           ORDER BY created_at DESC LIMIT 20""",
        entity_uuid,
        asset_type,
    )

    related_risks = await pool.fetch(
        """SELECT rs.entity_uuid, rs.entity_type, rs.dimension, rs.score, rs.confidence
           FROM energy.risk_scores rs
           WHERE rs.expires_at > NOW()
           AND rs.entity_type::text IN (
               SELECT er.source_entity_type::text FROM energy.entity_relationships er
               WHERE (er.source_entity_type::text = $2 AND er.source_entity_id = $3)
               UNION
               SELECT er.target_entity_type::text FROM energy.entity_relationships er
               WHERE (er.target_entity_type::text = $2 AND er.target_entity_id = $3)
           )
           AND rs.entity_uuid != $1::uuid
           AND rs.dimension = 'overall'
           ORDER BY rs.score DESC LIMIT 10""",
        entity_uuid, asset_type, entity_row["id"],
    )

    return {
        "entity": _row_to_dict(entity_row),
        "risk_scores": [_row_to_dict(r) for r in risk_scores],
        "active_signals": [_row_to_dict(r) for r in signals],
        "related_entity_risks": [_row_to_dict(r) for r in related_risks],
    }


@router.get("/articles/{article_id}/impact")
async def get_article_impact(
    article_id: int,
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    """Real market-impact reasoning for one article -- reuses whatever
    disruption_signals ArticleSignalIngestor already derived from it (real
    threat score + real energy-entity match), so an article only shows
    impact data when it genuinely qualified for one; no fabricated numbers
    for articles the pipeline didn't match to anything real."""
    from services.corridor_risk import CorridorRiskEngine

    rows = await pool.fetch(
        """SELECT * FROM energy.disruption_signals
           WHERE source = $1 ORDER BY confidence DESC LIMIT 3""",
        f"article:{article_id}",
    )
    if not rows:
        return {"has_impact_data": False, "signals": []}

    engine = CorridorRiskEngine(pool)
    signals = []
    for r in rows:
        explanation = await engine.explain_signal(_row_to_dict(r))
        signals.append({
            "signal_uuid": str(r["uuid"]),
            "affected_entity_type": r["affected_entity_type"],
            "severity": r["severity"],
            "risk_dimension": r["risk_dimension"],
            **explanation,
        })
    return {"has_impact_data": True, "signals": signals}


_SEVERITY_RANK = {"critical": 4, "high": 3, "elevated": 2, "moderate": 1, "low": 0}


@router.get("/impact-feed")
async def get_impact_feed(
    limit: int = Query(15, ge=1, le=50),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    """The continuous 'this news, X hours ago -> this much estimated market
    pressure' feed: recent active signals, each with its reasoning and
    exposure estimate pre-computed. One CorridorRiskEngine instance is
    reused across every signal in the batch so the corridor blend, live
    Brent price, and national demand are each fetched once per request,
    not once per signal (see CorridorRiskEngine's caching).

    Multiple articles about the same real-world event routinely match the
    same corridor within the same day (ArticleSignalIngestor dedupes per
    article, not across articles covering one event), which made the feed
    look repetitive -- N near-identical cards for one event. Signals are
    grouped by (matched corridor, day) and collapsed to one representative
    card noting how many signals fed into it."""
    from services.corridor_risk import CorridorRiskEngine

    # Over-fetch so there's enough raw signal pool left to fill `limit`
    # distinct groups after collapsing near-duplicates.
    fetch_limit = min(limit * 4, 80)
    rows = await pool.fetch(
        """SELECT * FROM energy.disruption_signals
           WHERE expires_at > NOW()
           ORDER BY CASE severity
                        WHEN 'critical' THEN 4
                        WHEN 'high' THEN 3
                        WHEN 'elevated' THEN 2
                        WHEN 'moderate' THEN 1
                        ELSE 0
                    END DESC,
                    created_at DESC
           LIMIT $1""",
        fetch_limit,
    )

    engine = CorridorRiskEngine(pool)
    groups: dict[tuple[Any, Any], dict[str, Any]] = {}
    for r in rows:
        explanation = await engine.explain_signal(_row_to_dict(r))
        group_key = (explanation.get("matched_corridor"), r["created_at"].date())
        candidate = {
            "signal_uuid": str(r["uuid"]),
            "title": r["title"],
            "severity": r["severity"],
            "risk_dimension": r["risk_dimension"],
            "source": r["source"],
            "detected_at": r["created_at"].isoformat(),
            "based_on_signals": 1,
            **explanation,
        }
        existing = groups.get(group_key)
        if existing is None:
            groups[group_key] = candidate
        else:
            existing["based_on_signals"] += 1
            if _SEVERITY_RANK.get(r["severity"], 0) > _SEVERITY_RANK.get(existing["severity"], 0):
                # keep the count, swap in the higher-severity signal as the representative
                candidate["based_on_signals"] = existing["based_on_signals"]
                groups[group_key] = candidate

    items = sorted(
        groups.values(),
        key=lambda it: (_SEVERITY_RANK.get(it["severity"], 0), it["detected_at"]),
        reverse=True,
    )[:limit]

    return {
        "items": items,
        "total": len(items),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Corridor & supplier disruption probability ──────────────────────────────


@router.get("/corridors")
async def list_corridor_risk(
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    """Live 30-day disruption probability per import corridor, with named
    drivers and published assumptions (see services/corridor_risk.py)."""
    from services.corridor_risk import CorridorRiskEngine

    engine = CorridorRiskEngine(pool)
    return await engine.compute_all()


@router.get("/suppliers/risk")
async def list_supplier_risk(
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    """Composite supplier disruption exposure (own risk × corridor risk)."""
    from services.corridor_risk import CorridorRiskEngine

    engine = CorridorRiskEngine(pool)
    return await engine.supplier_risk()


@router.get("/ais/positions")
async def list_ais_positions() -> dict[str, Any]:
    """Latest real AISstream vessel positions near monitored chokepoints,
    served from the ml-platform-ingested snapshot for the map overlay."""
    import csv
    import json as json_mod

    from backend.shared.paths import project_root

    path = project_root() / "datasets" / "processed" / "ais-chokepoints" / "ais-chokepoints.csv"
    try:
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    except OSError:
        return {"items": [], "total": 0, "snapshot_at": None}

    items = []
    latest = None
    for r in rows:
        try:
            attrs = json_mod.loads(r.get("attributes") or "{}")
        except json_mod.JSONDecodeError:
            attrs = {}
        ts = (r.get("timestamp") or "")[:19]
        if latest is None or ts > latest:
            latest = ts
        items.append({
            "mmsi": r.get("entity_id"),
            "name": r.get("entity_name"),
            "latitude": float(r["latitude"]),
            "longitude": float(r["longitude"]),
            "chokepoint": r.get("location_name"),
            "speed_knots": attrs.get("speed_over_ground_knots"),
            "heading": attrs.get("true_heading"),
            "timestamp": ts,
        })
    return {"items": items, "total": len(items), "snapshot_at": latest}


# ── Knowledge Graph Risk Propagation ────────────────────────────────────────


@router.post("/propagate")
async def propagate_risk(
    body: dict[str, Any],
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    from services.ml_bridge import RiskPropagator

    entity_uuid = body.get("entity_uuid")
    entity_type = body.get("entity_type", "import_corridors")
    risk_score = body.get("risk_score", 0.5)

    propagator = RiskPropagator(pool)
    count = await propagator.propagate(entity_uuid, entity_type, risk_score)

    return {
        "source": entity_uuid,
        "source_type": entity_type,
        "propagated_to": count,
        "propagation_factor": RiskPropagator.PROPAGATION_FACTOR,
    }


@router.get("/propagation-map")
async def get_propagation_map(
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    rows = await pool.fetch(
        """SELECT rs.entity_uuid, rs.entity_type, rs.score, rs.confidence,
                  rs.breakdown, rs.created_at
           FROM energy.risk_scores rs
           WHERE rs.dimension = 'overall'
           AND rs.expires_at > NOW()
           AND rs.breakdown ? 'propagated_from'
           ORDER BY rs.score DESC LIMIT 50"""
    )

    sources = await pool.fetch(
        """SELECT rs.entity_uuid, rs.entity_type, rs.score
           FROM energy.risk_scores rs
           WHERE rs.dimension = 'overall'
           AND rs.expires_at > NOW()
           AND NOT (rs.breakdown ? 'propagated_from')
           ORDER BY rs.score DESC LIMIT 20"""
    )

    return {
        "propagated_scores": [_row_to_dict(r) for r in rows],
        "source_scores": [_row_to_dict(r) for r in sources],
        "total_propagated": len(rows),
        "total_sources": len(sources),
    }
