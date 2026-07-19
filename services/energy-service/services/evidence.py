"""Decision evidence and source-provenance helpers for pilot workflows."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import asyncpg


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _iso(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None


class EvidenceService:
    """Stores a self-contained, exportable record of an operational decision."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def provenance(self, signal: asyncpg.Record) -> list[dict[str, Any]]:
        """Return honest provenance for inputs used by the decision path.

        Connector status rows take precedence. Until a connector has written a
        status row, the safe default is cached or disabled, never live.
        """
        rows = await self.pool.fetch("SELECT * FROM energy.intelligence_source_status")
        configured = {r["source_key"]: dict(r) for r in rows}

        article_mode = "live" if str(signal["source"]).startswith("article:") else "replay"
        defaults = [
            {
                "source_key": "news_signal",
                "display_name": "ML-enriched news signal",
                "mode": article_mode,
                "observed_at": signal["created_at"],
                "ingested_at": signal["created_at"],
                "fallback_reason": None,
                "source_url": (signal["evidence_urls"] or [None])[0],
            },
            {
                "source_key": "ais_chokepoints",
                "display_name": "AIS chokepoint observations",
                "mode": "cached",
                "observed_at": None,
                "ingested_at": None,
                "fallback_reason": "No persisted AIS connector status has been recorded.",
                "source_url": None,
            },
            {
                "source_key": "sanctions",
                "display_name": "Sanctions intelligence",
                "mode": "disabled",
                "observed_at": None,
                "ingested_at": None,
                "fallback_reason": "Country-level sanctions aggregation is not wired to a live source.",
                "source_url": None,
            },
            {
                "source_key": "commodity_prices",
                "display_name": "Commodity price benchmark",
                "mode": "cached",
                "observed_at": None,
                "ingested_at": None,
                "fallback_reason": "Latest validated dataset snapshot is used until a live price connector reports status.",
                "source_url": None,
            },
        ]

        now = datetime.now(timezone.utc)
        result: list[dict[str, Any]] = []
        for default in defaults:
            row = configured.get(default["source_key"], default)
            observed = row.get("observed_at")
            ingested = row.get("ingested_at")
            freshness = row.get("freshness_seconds")
            if freshness is None and observed is not None:
                freshness = round((now - observed).total_seconds(), 1)
            result.append({
                "source": row["source_key"],
                "display_name": row["display_name"],
                "mode": row["mode"],
                "observed_at": _iso(observed),
                "ingested_at": _iso(ingested),
                "freshness_seconds": freshness,
                "fallback_reason": row.get("fallback_reason"),
                "source_url": row.get("source_url"),
                "metadata": _as_dict(row.get("metadata")),
            })
        return result

    async def create_bundle(
        self,
        *,
        telemetry_uuid: str,
        signal: asyncpg.Record,
        scenario: asyncpg.Record,
        twin: dict[str, Any],
        spr_run: dict[str, Any],
        procurement_run: dict[str, Any],
        max_ticks: int,
        refinery_target: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        provenance = await self.provenance(signal)
        modes = {item["mode"] for item in provenance}
        mode = "fallback" if "fallback" in modes or "disabled" in modes else ("cached" if "cached" in modes else "live")
        impacts = twin.get("aggregate_impacts") or {}
        spr_results = spr_run.get("results") or {}
        top_option = procurement_run.get("recommended") or {}
        decision_brief = {
            "affected_exposure": {
                "signal_title": signal["title"],
                "severity": signal["severity"],
                "regions": signal["affected_regions"] or [],
                "commodities": signal["affected_commodities"] or [],
            },
            "supply_gap_bpd": impacts.get("max_supply_gap_bpd") or impacts.get("supply_gap_bpd") or 0,
            "scenario": {"name": scenario["name"], "severity": scenario["severity"], "horizon_days": max_ticks},
            "spr": {
                "coverage_pct": spr_results.get("coverage_pct"),
                "daily_draw_bpd": spr_results.get("daily_draw_bpd"),
                "uncovered_gap_bpd": spr_results.get("uncovered_gap_bpd"),
            },
            "procurement": {
                "recommended_bpd": procurement_run.get("total_recommended_bpd"),
                "recommendations_count": procurement_run.get("recommendations_count"),
                "top_supplier": top_option.get("supplier_name"),
                "top_supplier_country": top_option.get("country"),
                "cost_bbl": top_option.get("cost_bbl"),
                "risk_score": top_option.get("risk_score"),
                "lead_time_days": top_option.get("lead_time_days"),
                "grade_compatibility": top_option.get("compatibility"),
            },
            "target_refinery": ({
                "uuid": refinery_target["uuid"],
                "name": refinery_target["name"],
                "country": refinery_target.get("country"),
                "capacity_bpd": refinery_target.get("capacity_bpd"),
                "nelson_complexity_index": refinery_target.get("nelson_complexity_index"),
                "accepted_crude_types": refinery_target.get("crude_types_accepted") or [],
                "qualification_status": "catalog constraints recorded; supplier-grade pairing requires a verified supplier cargo specification.",
            } if refinery_target else None),
            "caveat": "This is decision support. A human operator must review contractual, compliance, and operational constraints before execution.",
        }
        assumptions = {
            "scenario_assumptions": _as_dict(scenario.get("assumptions")),
            "twin_config": _as_dict(twin.get("config")),
            "optimization_goal": procurement_run.get("optimization_goal", "balanced"),
        }
        bundle_uuid = str(uuid.uuid4())
        await self.pool.execute(
            """INSERT INTO energy.response_evidence_bundles
               (uuid, telemetry_uuid, signal_uuid, scenario_uuid, twin_run_uuid, spr_run_uuid,
                procurement_run_uuid, mode, assumptions, input_provenance, decision_brief)
               VALUES ($1,$2::uuid,$3::uuid,$4::uuid,$5::uuid,$6::uuid,$7::uuid,$8,$9,$10,$11)""",
            bundle_uuid, telemetry_uuid, str(signal["uuid"]), str(scenario["uuid"]),
            twin.get("run_uuid"), spr_run.get("run_uuid"), procurement_run.get("run_uuid"), mode,
            json.dumps(assumptions), json.dumps(provenance), json.dumps(decision_brief),
        )
        await self.record_approval(bundle_uuid, "draft", "system", "Decision generated; awaiting operator review.")
        return {"uuid": bundle_uuid, "mode": mode, "input_provenance": provenance, "decision_brief": decision_brief}

    async def record_approval(self, bundle_uuid: str, status: str, actor: str, note: str | None = None) -> None:
        await self.pool.execute(
            """INSERT INTO energy.decision_approvals (uuid, evidence_bundle_uuid, status, actor, note)
               VALUES ($1,$2::uuid,$3,$4,$5)""",
            str(uuid.uuid4()), bundle_uuid, status, actor, note,
        )

    async def get_bundle(self, bundle_uuid: str) -> dict[str, Any] | None:
        row = await self.pool.fetchrow("SELECT * FROM energy.response_evidence_bundles WHERE uuid = $1::uuid", bundle_uuid)
        if not row:
            return None
        approvals = await self.pool.fetch(
            "SELECT uuid, status, actor, note, recorded_at FROM energy.decision_approvals WHERE evidence_bundle_uuid = $1::uuid ORDER BY recorded_at",
            bundle_uuid,
        )
        result = dict(row)
        for key in ("assumptions", "input_provenance", "decision_brief"):
            parsed = result.get(key)
            if isinstance(parsed, str):
                result[key] = json.loads(parsed)
        result["approvals"] = [dict(item) for item in approvals]
        return result
