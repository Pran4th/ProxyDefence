"""Digital Twin Simulation Engine — tick-based what-if simulation for the energy supply chain."""

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import asyncpg

from backend.shared.logging_config import get_logger
from services.digital_twin.flow import FlowEngine
from services.digital_twin.graph import NetworkGraph
from services.digital_twin.scenarios import SCENARIO_TEMPLATES

logger = get_logger(__name__)


def _ensure_dict(val: Any) -> dict:
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return {}
    if val is None:
        return {}
    return val if hasattr(val, "get") else {}


class SimulationEngine:
    """Tick-based simulation engine that executes scenarios against the supply chain graph."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
        self.flow = FlowEngine(pool)
        self.graph = NetworkGraph(pool)

    async def seed_scenarios(self) -> int:
        """Seed pre-built scenario templates into the database."""
        count = 0
        for tmpl in SCENARIO_TEMPLATES:
            exists = await self.pool.fetchval(
                "SELECT id FROM energy.simulation_scenarios WHERE name = $1 AND is_template = true",
                tmpl["name"],
            )
            if not exists:
                await self.pool.execute(
                    """INSERT INTO energy.simulation_scenarios
                       (uuid, name, description, category, config, assumptions, is_template, severity)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8)""",
                    str(uuid.uuid4()),
                    tmpl["name"],
                    tmpl["description"],
                    tmpl["category"],
                    json.dumps(tmpl["config"]),
                    json.dumps(tmpl["assumptions"]),
                    tmpl["is_template"],
                    tmpl["severity"],
                )
                count += 1
        return count

    async def run_simulation(
        self,
        scenario_id: int | None = None,
        name: str = "Simulation Run",
        description: str = "",
        config: dict | None = None,
        scenario_config: dict | None = None,
        tick_interval: str = "day",
        max_ticks: int = 90,
        risk_snapshot: dict | None = None,
    ) -> dict[str, Any]:
        """Run a full tick-based simulation and persist results."""
        t0 = time.time()

        if scenario_id:
            scenario = await self.pool.fetchrow(
                "SELECT * FROM energy.simulation_scenarios WHERE id = $1", scenario_id,
            )
            if not scenario:
                raise ValueError(f"Scenario {scenario_id} not found")
            effective_config = dict(_ensure_dict(scenario["config"]))
            effective_config["assumptions"] = _ensure_dict(scenario.get("assumptions"))
            effective_config["tick_interval"] = tick_interval
            effective_config["duration_days"] = effective_config.get("duration_days", max_ticks)
        else:
            effective_config = {
                **(config or {}),
                "tick_interval": tick_interval,
                "duration_days": max_ticks,
            }

        run_uuid = str(uuid.uuid4())
        run_id = await self.pool.fetchval(
            """INSERT INTO energy.digital_twin_runs
               (uuid, scenario_id, name, description, mode, status, tick_interval, max_ticks,
                config, risk_snapshot, started_at)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
               RETURNING id""",
            run_uuid, scenario_id, name, description, "scenario", "running",
            tick_interval, max_ticks,
            json.dumps(effective_config),
            json.dumps(risk_snapshot or {}),
            datetime.now(timezone.utc),
        )

        node_states, edge_states = await self.flow.snapshot_to_states()

        await self.flow.estimate_baseline_flow()

        all_tick_events = []
        tick_summaries = []

        for tick in range(1, max_ticks + 1):
            node_states, edge_states, tick_events = await self.flow.compute_tick(
                run_id, tick, node_states, edge_states, effective_config, risk_snapshot or {},
            )

            await self._persist_tick_state(run_id, tick, node_states, edge_states)

            for event in tick_events:
                event["run_id"] = run_id
                await self._persist_tick_event(run_id, tick, event)
                all_tick_events.append(event)

            supply_gap = sum(n.get("supply_gap_bpd", 0) for n in node_states.values())
            idle_count = sum(1 for n in node_states.values() if n.get("status") == "idle")
            inventory_total = sum(n.get("current_inventory_barrels", 0) for n in node_states.values())

            tick_summaries.append({
                "tick": tick,
                "supply_gap_bpd": round(supply_gap, 0),
                "idle_assets": idle_count,
                "total_inventory_barrels": round(inventory_total, 0),
                "events_this_tick": len(tick_events),
            })

            await self.pool.execute(
                "UPDATE energy.digital_twin_runs SET current_tick = $1 WHERE id = $2",
                tick, run_id,
            )

        impacts = await self.flow.compute_aggregate_impacts(node_states, sum(t["tick"] for t in tick_summaries) // len(tick_summaries) if tick_summaries else 0, max_ticks)

        exec_time_ms = (time.time() - t0) * 1000
        await self.pool.execute(
            """UPDATE energy.digital_twin_runs
               SET status = 'completed', current_tick = $1, completed_at = $2,
                   execution_time_ms = $3, aggregate_impacts = $4,
                   supply_gap_bpd = $5, max_supply_gap_bpd = $6,
                   economic_impact_usd = $7, gdp_impact_pct = $8
               WHERE id = $9""",
            max_ticks,
            datetime.now(timezone.utc),
            round(exec_time_ms, 1),
            json.dumps(impacts),
            impacts.get("supply_gap_bpd", 0),
            impacts.get("max_supply_gap_bpd", 0),
            impacts.get("economic_impact_usd", 0),
            impacts.get("gdp_impact_pct", 0),
            run_id,
        )

        return {
            "run_id": run_id,
            "run_uuid": run_uuid,
            "status": "completed",
            "execution_time_ms": round(exec_time_ms, 1),
            "ticks_executed": max_ticks,
            "tick_summaries": tick_summaries,
            "final_node_states": {str(k): v for k, v in node_states.items()},
            "final_edge_states": {str(k): v for k, v in edge_states.items()},
            "total_events": len(all_tick_events),
            "aggregate_impacts": impacts,
        }

    async def _persist_tick_state(
        self, run_id: int, tick: int,
        node_states: dict[int, dict], edge_states: dict[int, dict],
    ) -> int:
        count = 0
        for nid, node in node_states.items():
            await self.pool.execute(
                """INSERT INTO energy.flow_states
                   (uuid, run_id, tick, node_id, flow_bpd, capacity_bpd,
                    utilization_pct, inventory_barrels, supply_gap_bpd,
                    is_bottleneck, is_idle, status)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)""",
                str(uuid.uuid4()), run_id, tick, nid,
                node.get("outbound_bpd", 0),
                node.get("capacity_bpd", 0),
                node.get("capacity_bpd", 1) and min(100, node.get("outbound_bpd", 0) / max(node.get("capacity_bpd", 1), 1) * 100) or 0,
                node.get("current_inventory_barrels", 0),
                node.get("supply_gap_bpd", 0),
                node.get("supply_gap_bpd", 0) > node.get("demand_bpd", 0) * 0.5 if node.get("demand_bpd", 0) else False,
                node.get("status") == "idle",
                node.get("status", "normal"),
            )
            count += 1
        for eid, edge in edge_states.items():
            await self.pool.execute(
                """INSERT INTO energy.flow_states
                   (uuid, run_id, tick, node_id, edge_id, flow_bpd, capacity_bpd,
                    utilization_pct, status)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)""",
                str(uuid.uuid4()), run_id, tick,
                edge.get("source_node_id"), eid,
                edge.get("current_flow_bpd", 0),
                edge.get("max_capacity_bpd", 0),
                edge.get("utilization_pct", 0),
                "active" if edge.get("is_active", True) else "inactive",
            )
            count += 1
        return count

    async def _persist_tick_event(self, run_id: int, tick: int, event: dict) -> None:
        await self.pool.execute(
            """INSERT INTO energy.simulation_tick_events
               (uuid, run_id, tick, event_type, node_id, description, severity, impact)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8)""",
            str(uuid.uuid4()), run_id, tick,
            event.get("event_type", "unknown"),
            event.get("node_id"),
            event.get("description", ""),
            event.get("severity", "medium"),
            json.dumps(event.get("impact", {})),
        )

    async def get_run_results(self, run_uuid: str) -> dict[str, Any] | None:
        run = await self.pool.fetchrow(
            "SELECT * FROM energy.digital_twin_runs WHERE uuid = $1", run_uuid,
        )
        if not run:
            return None

        tick_events = await self.pool.fetch(
            "SELECT * FROM energy.simulation_tick_events WHERE run_id = $1 ORDER BY tick",
            run["id"],
        )
        flow_states = await self.pool.fetch(
            "SELECT * FROM energy.flow_states WHERE run_id = $1 ORDER BY tick, node_id",
            run["id"],
        )

        return {
            "run": dict(run),
            "tick_events": [dict(r) for r in tick_events],
            "flow_states": [dict(r) for r in flow_states],
            "event_count": len(tick_events),
            "tick_count": run["current_tick"],
        }

    async def get_run_timeline(self, run_uuid: str) -> dict[str, Any] | None:
        run = await self.pool.fetchrow(
            "SELECT id, name, current_tick, max_ticks, tick_interval FROM energy.digital_twin_runs WHERE uuid = $1",
            run_uuid,
        )
        if not run:
            return None

        tick_events = await self.pool.fetch(
            """SELECT tick, event_type, severity, COUNT(*) as event_count
               FROM energy.simulation_tick_events
               WHERE run_id = $1
               GROUP BY tick, event_type, severity
               ORDER BY tick""",
            run["id"],
        )

        flow_states = await self.pool.fetch(
            """SELECT tick,
                      SUM(flow_bpd) as total_flow,
                      SUM(supply_gap_bpd) as total_gap,
                      SUM(inventory_barrels) as total_inventory,
                      COUNT(*) FILTER (WHERE is_idle = true) as idle_nodes
               FROM energy.flow_states
               WHERE run_id = $1 AND node_id IS NOT NULL
               GROUP BY tick
               ORDER BY tick""",
            run["id"],
        )

        timeline = []
        for fs in flow_states:
            tick_evts = [e for e in tick_events if e["tick"] == fs["tick"]]
            timeline.append({
                "tick": fs["tick"],
                "total_flow_bpd": round(fs["total_flow"] or 0, 0),
                "supply_gap_bpd": round(fs["total_gap"] or 0, 0),
                "total_inventory_barrels": round(fs["total_inventory"] or 0, 0),
                "idle_nodes": fs["idle_nodes"] or 0,
                "events": [dict(e) for e in tick_evts],
            })

        return {
            "run_name": run["name"],
            "total_ticks": run["current_tick"],
            "max_ticks": run["max_ticks"],
            "tick_interval": run["tick_interval"],
            "timeline": timeline,
        }

    async def get_run_network(self, run_uuid: str, tick: int | None = None) -> dict[str, Any] | None:
        run = await self.pool.fetchrow(
            "SELECT id FROM energy.digital_twin_runs WHERE uuid = $1", run_uuid,
        )
        if not run:
            return None

        target_tick = tick or (await self.pool.fetchval(
            "SELECT MAX(tick) FROM energy.flow_states WHERE run_id = $1", run["id"],
        ) or 0)

        states = await self.pool.fetch(
            """SELECT fs.*, nn.name as node_name, nn.node_type, nn.category
               FROM energy.flow_states fs
               JOIN energy.network_nodes nn ON nn.id = fs.node_id
               WHERE fs.run_id = $1 AND fs.tick = $2
               ORDER BY nn.name""",
            run["id"], target_tick,
        )

        return {
            "run_uuid": run_uuid,
            "tick": target_tick,
            "nodes": [dict(r) for r in states],
            "total_nodes": len(states),
        }

    async def compare_runs(self, run_uuids: list[str]) -> list[dict[str, Any]]:
        results = []
        for ruid in run_uuids[:5]:
            run_data = await self.get_run_results(ruid)
            if run_data:
                r = run_data["run"]
                results.append({
                    "run_uuid": ruid,
                    "name": r["name"],
                    "status": r["status"],
                    "tick_interval": r["tick_interval"],
                    "max_ticks": r["max_ticks"],
                    "current_tick": r["current_tick"],
                    "supply_gap_bpd": r.get("supply_gap_bpd", 0),
                    "max_supply_gap_bpd": r.get("max_supply_gap_bpd", 0),
                    "economic_impact_usd": r.get("economic_impact_usd", 0),
                    "gdp_impact_pct": r.get("gdp_impact_pct", 0),
                    "days_until_critical": r.get("days_until_critical"),
                    "execution_time_ms": r.get("execution_time_ms", 0),
                    "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
                })
        return results

    async def create_custom_scenario(
        self, name: str, description: str, config: dict, assumptions: dict | None = None,
        category: str = "custom", severity: str = "medium",
    ) -> dict[str, Any]:
        sc_uuid = str(uuid.uuid4())
        row = await self.pool.fetchrow(
            """INSERT INTO energy.simulation_scenarios
               (uuid, name, description, category, config, assumptions, is_template, severity)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
               RETURNING id, uuid, created_at""",
            sc_uuid, name, description, category,
            json.dumps(config), json.dumps(assumptions or {}),
            False, severity,
        )
        return {
            "id": row["id"],
            "uuid": row["uuid"],
            "name": name,
            "description": description,
            "category": category,
            "severity": severity,
            "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        }
