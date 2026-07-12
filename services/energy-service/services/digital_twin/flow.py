"""Flow simulation engine — simulates crude/product flow through the supply chain network with capacity constraints."""

import math
from typing import Any

import asyncpg

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class FlowEngine:
    """Simulates flow through the supply chain network with capacity constraints, alternative routing, and cascade effects."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def compute_tick(
        self,
        run_id: int,
        tick: int,
        node_states: dict[int, dict],
        edge_states: dict[int, dict],
        scenario_config: dict,
        risk_snapshot: dict,
    ) -> tuple[dict[int, dict], dict[int, dict], list[dict]]:
        """Execute one simulation tick. Returns updated node_states, edge_states, tick_events."""
        events = []
        tick_interval_hours = self._interval_hours(scenario_config.get("tick_interval", "day"))

        disrupted_edges = await self._compute_disruptions(scenario_config, tick, edge_states)

        for eid, edge in edge_states.items():
            if eid in disrupted_edges:
                edge["current_flow_bpd"] *= disrupted_edges[eid]["multiplier"]
                edge["utilization_pct"] = edge.get("current_flow_bpd", 0) / max(edge.get("max_capacity_bpd", 1), 1) * 100
                edge["is_active"] = disrupted_edges[eid]["multiplier"] > 0
                if disrupted_edges[eid].get("event"):
                    events.append(disrupted_edges[eid]["event"])
            await self._apply_risk_modifier(edge, risk_snapshot)

        edge_states = await self._rebalance_flow(node_states, edge_states)

        for nid, node in node_states.items():
            inbound = sum(
                es["current_flow_bpd"]
                for es in edge_states.values()
                if es["target_node_id"] == nid and es.get("is_active", True)
            )
            outbound = sum(
                es["current_flow_bpd"]
                for es in edge_states.values()
                if es["source_node_id"] == nid and es.get("is_active", True)
            )

            prev_inventory = node.get("current_inventory_barrels") or 0
            net_flow = inbound - outbound
            new_inventory = max(0, prev_inventory + net_flow * tick_interval_hours / 24)

            node["inbound_bpd"] = round(inbound, 2)
            node["outbound_bpd"] = round(outbound, 2)
            node["current_inventory_barrels"] = round(new_inventory, 2)
            node["supply_gap_bpd"] = max(0, node.get("demand_bpd", 0) - inbound)

            if node.get("supply_gap_bpd", 0) > 0 and node.get("demand_bpd", 0) > 0:
                gap_pct = node["supply_gap_bpd"] / node["demand_bpd"]
                if gap_pct > 0.5:
                    node["status"] = "critical"
                    events.append({
                        "event_type": "supply_deficit",
                        "node_id": nid,
                        "tick": tick,
                        "description": f"Supply deficit of {node['supply_gap_bpd']:,.0f} bpd at {node.get('name', 'unknown')}",
                        "severity": "critical" if gap_pct > 0.8 else "high",
                        "impact": {
                            "supply_gap_bpd": node["supply_gap_bpd"],
                            "deficit_pct": round(gap_pct * 100, 1),
                        },
                    })
                elif gap_pct > 0.2:
                    node["status"] = "elevated"
                    events.append({
                        "event_type": "supply_stress",
                        "node_id": nid,
                        "tick": tick,
                        "description": f"Supply stress at {node.get('name', 'unknown')}: {node['supply_gap_bpd']:,.0f} bpd gap",
                        "severity": "elevated",
                        "impact": {"supply_gap_bpd": node["supply_gap_bpd"]},
                    })

            if node.get("current_inventory_barrels", 0) <= 0 and outbound > 0:
                if node.get("node_type") in ("refinery", "power_plant", "storage_facility"):
                    node["status"] = "idle"
                    edge_ids = [eid for eid, es in edge_states.items() if es["source_node_id"] == nid]
                    for eid in edge_ids:
                        edge_states[eid]["current_flow_bpd"] = 0
                        edge_states[eid]["is_active"] = False
                    events.append({
                        "event_type": "node_idle",
                        "node_id": nid,
                        "tick": tick,
                        "description": f"{node.get('name', 'Node')} is idle — no inventory remaining",
                        "severity": "critical",
                        "impact": {"lost_throughput_bpd": outbound},
                    })

            inv = node.get("current_inventory_barrels") or 0
            if node.get("category") == "spr" and inv > 0:
                days_remaining = inv / max(outbound, node.get("max_drawdown_bpd") or 1)
                node["days_remaining"] = round(days_remaining, 1)

        return node_states, edge_states, events

    async def _compute_disruptions(
        self, config: dict, tick: int, edge_states: dict[int, dict]
    ) -> dict[int, dict]:
        """Apply scenario disruptions to edges."""
        disruptions = {}
        duration = config.get("duration_days", 30)

        affected_routes = config.get("affected_routes", [])
        severity = config.get("severity", 0.5)
        supply_cut = config.get("assumptions", {}).get("middle_east_supply_cut_pct", 0)

        for eid, edge in edge_states.items():
            route_name = edge.get("route_name", "")
            if any(r in route_name for r in affected_routes):
                if tick <= duration:
                    multiplier = max(0, 1.0 - severity * supply_cut) if supply_cut else max(0, 1.0 - severity)
                    disruptions[eid] = {
                        "multiplier": multiplier,
                        "event": {
                            "event_type": "supply_disruption",
                            "node_id": edge["source_node_id"],
                            "tick": tick,
                            "description": f"Supply disruption on route {route_name}: capacity reduced to {multiplier*100:.0f}%",
                            "severity": "critical" if multiplier < 0.3 else "high",
                            "impact": {
                                "capacity_multiplier": multiplier,
                                "expected_flow_loss_bpd": edge.get("current_flow_bpd", 0) * (1 - multiplier),
                            },
                        },
                    }

        for eid, edge in edge_states.items():
            node_type = edge.get("source_type", "")
            # Match on BOTH source and target side: a refinery going offline has
            # to zero its INBOUND crude edges (what supply_gap_bpd is computed
            # from, since a refinery is the target of those) as well as its
            # outbound product edges -- matching source-only never touched
            # inbound flow, so a "shut down" refinery kept reading full inbound
            # and every scenario looked identical regardless of what it disrupted.
            if config.get("affected_refineries"):
                target_match = "refinery" in edge.get("target_type", "") and any(
                    aff.lower() in edge.get("target_name", "").lower()
                    for aff in config["affected_refineries"]
                )
                source_match = "refinery" in node_type and any(
                    aff.lower() in edge.get("source_name", "").lower()
                    for aff in config["affected_refineries"]
                )
                if target_match or source_match:
                    offline_days = config.get("refinery_offline_days", 14)
                    if tick <= offline_days:
                        ref_label = edge.get("target_name") if target_match else edge.get("source_name")
                        disruptions[eid] = {
                            "multiplier": 0,
                            "event": {
                                "event_type": "refinery_shutdown",
                                "node_id": edge["source_node_id"],
                                "tick": tick,
                                "description": f"Refinery {ref_label} offline due to disruption",
                                "severity": "critical",
                                "impact": {"lost_capacity_bpd": edge.get("current_flow_bpd", 0)},
                            },
                        }

            if config.get("affected_ports") and "port" in node_type:
                port_name = edge.get("source_name", "").lower()
                for aff in config.get("affected_ports", []):
                    if aff.lower() in port_name:
                        closure_days = config.get("port_closure_days", 7)
                        if tick <= closure_days:
                            disruptions[eid] = {
                                "multiplier": 0.1,
                                "event": {
                                    "event_type": "port_closure",
                                    "node_id": edge["source_node_id"],
                                    "tick": tick,
                                    "description": f"Port {edge.get('source_name', '')} closed due to disruption",
                                    "severity": "high",
                                    "impact": {"lost_throughput_bpd": edge.get("current_flow_bpd", 0)},
                                },
                            }

        return disruptions

    async def _apply_risk_modifier(self, edge: dict, risk_snapshot: dict) -> None:
        if risk_snapshot and edge.get("risk_multiplier", 1.0) > 0:
            source_type = edge.get("source_type", "")
            risk = risk_snapshot.get(source_type, {}).get("risk_score", 0)
            if risk > 0:
                edge["risk_multiplier"] = max(0.1, 1.0 - risk / 2)

    async def _rebalance_flow(
        self, node_states: dict[int, dict], edge_states: dict[int, dict]
    ) -> dict[int, dict]:
        """Rebalance flow after disruptions — reroute through alternative paths."""
        for nid, node in node_states.items():
            if node.get("status") == "idle":
                affected_edges = [
                    eid for eid, es in edge_states.items()
                    if es["source_node_id"] == nid
                ]
                for eid in affected_edges:
                    edge_states[eid]["current_flow_bpd"] = 0

        return edge_states

    def _interval_hours(self, interval: str) -> float:
        return {"hour": 1, "day": 24, "week": 168}.get(interval, 24)

    # ── Macro cascade assumptions (every value named, sourced, falsifiable) ──
    INDIA_GDP_USD = 3.7e12          # World Bank, nominal GDP FY24 approx
    FALLBACK_BRENT_USD_BBL = 85.0   # used only if no live price row exists
    # Retail pass-through of a crude price shock to Indian pump prices.
    # PPAC analyses put diesel/petrol pass-through in the 0.4-0.5 range under
    # the current dynamic pricing regime.
    FUEL_PASS_THROUGH = 0.45
    INDIA_RETAIL_DIESEL_INR_L = 90.0   # indicative national average
    CRUDE_COST_SHARE_OF_RETAIL = 0.50  # crude ≈ half the pump price pre-tax

    async def _live_brent_usd_bbl(self) -> tuple[float, str]:
        """Latest live Brent from energy.commodity_prices (crude-price-api
        ingest); falls back to a named constant if the table is empty."""
        row = await self.pool.fetchrow(
            """SELECT price FROM energy.commodity_prices
               WHERE commodity_name ILIKE '%brent%'
               ORDER BY recorded_at DESC LIMIT 1"""
        )
        if row and row["price"]:
            return float(row["price"]), "crude_price_api (live)"
        return self.FALLBACK_BRENT_USD_BBL, "fallback constant"

    async def compute_aggregate_impacts(
        self, node_states: dict[int, dict], tick: int, max_ticks: int
    ) -> dict:
        """Compute aggregate economic and supply impact, plus the downstream
        cascades judges of scenario fidelity care about: per-refinery run
        rates, a retail fuel-price delta, and power-sector capacity at risk.
        Every macro coefficient is surfaced in the assumptions[] block."""
        total_supply_gap = sum(
            n.get("supply_gap_bpd", 0) for n in node_states.values()
        )
        max_gap = total_supply_gap

        refineries = [
            n for n in node_states.values() if n.get("node_type") == "refinery"
        ]
        idle_refineries = sum(1 for n in refineries if n.get("status") == "idle")
        total_refinery_capacity_lost = sum(
            n.get("capacity_bpd", 0) for n in refineries if n.get("status") == "idle"
        )
        total_refinery_capacity = sum(n.get("capacity_bpd", 0) for n in refineries)
        # Continuous run rate = allocated inbound crude / capacity. Only
        # meaningful for refineries actually connected to supply edges in the
        # network graph -- unconnected ones would read a misleading 0%, so
        # they are excluded and the metric is null when none are connected.
        connected = [
            n for n in refineries
            if n.get("capacity_bpd") and (n.get("inbound_bpd", 0) > 0 or n.get("status") == "idle")
        ]
        refinery_run_rates = [
            {
                "name": n.get("name", "refinery"),
                "run_rate_pct": round(
                    min(100.0, (n.get("inbound_bpd", 0) / n["capacity_bpd"]) * 100), 1,
                ),
                "status": n.get("status", "normal"),
            }
            for n in connected
        ]
        fleet_run_rate_pct = round(
            sum(r["run_rate_pct"] for r in refinery_run_rates) / len(refinery_run_rates), 1,
        ) if refinery_run_rates else None

        total_days = max_ticks
        crude_price_bbl, price_source = await self._live_brent_usd_bbl()
        economic_impact = total_supply_gap * crude_price_bbl * total_days
        gdp_impact_pct = (economic_impact / self.INDIA_GDP_USD) * 100

        # Fuel price cascade: supply-gap share of demand → crude shock → pump
        # price delta via pass-through. Bounded so an extreme scenario reads
        # as a large-but-finite shock, not an absurdity.
        total_demand = sum(n.get("demand_bpd", 0) for n in node_states.values()) or 1
        gap_fraction = min(total_supply_gap / total_demand, 1.0)
        crude_shock_pct = min(gap_fraction * 100 * 0.8, 120.0)  # 80% gap→price elasticity, capped
        retail_diesel_delta_inr_l = round(
            self.INDIA_RETAIL_DIESEL_INR_L
            * self.CRUDE_COST_SHARE_OF_RETAIL
            * (crude_shock_pct / 100)
            * self.FUEL_PASS_THROUGH, 2,
        )

        # Power stress: generation capacity attached to idle/starved plants
        power_plants = [
            n for n in node_states.values() if n.get("node_type") == "power_plant"
        ]
        power_capacity_at_risk_bpd = sum(
            n.get("capacity_bpd", 0) for n in power_plants if n.get("status") == "idle"
        )

        return {
            "supply_gap_bpd": round(total_supply_gap, 0),
            "max_supply_gap_bpd": round(max_gap, 0),
            "idle_refineries": idle_refineries,
            "total_refinery_capacity_lost_bpd": round(total_refinery_capacity_lost, 0),
            "total_refinery_capacity_bpd": round(total_refinery_capacity, 0),
            "fleet_run_rate_pct": fleet_run_rate_pct,
            "refinery_run_rates": sorted(refinery_run_rates, key=lambda r: r["run_rate_pct"])[:12],
            "crude_shock_pct": round(crude_shock_pct, 1),
            "retail_diesel_delta_inr_l": retail_diesel_delta_inr_l,
            "power_capacity_at_risk_bpd": round(power_capacity_at_risk_bpd, 0),
            "economic_impact_usd": round(economic_impact, 0),
            "gdp_impact_pct": round(gdp_impact_pct, 4),
            "crude_price_assumption_bpd": crude_price_bbl,
            "total_days_affected": total_days,
            "assumptions": [
                {
                    "name": "refinery_demand_allocation",
                    "value": "national_demand_bpd × (refinery.capacity_bpd / total_national_refining_capacity_bpd)",
                    "source": "Analyst-set proxy -- only refineries carry demand; SPRs/ports/pipelines carry none",
                    "how_to_test": "Compare allocated per-refinery demand against PPAC's published refinery-wise throughput",
                },
                {
                    "name": "crude_price_usd_bbl",
                    "value": crude_price_bbl,
                    "source": price_source,
                    "how_to_test": "Compare against the live Brent quote at run time",
                },
                {
                    "name": "india_gdp_usd",
                    "value": self.INDIA_GDP_USD,
                    "source": "World Bank nominal GDP, FY24 approx",
                    "how_to_test": "Swap in the latest MoSPI/World Bank release",
                },
                {
                    "name": "fuel_pass_through",
                    "value": self.FUEL_PASS_THROUGH,
                    "source": "PPAC pass-through analyses (0.4-0.5 range)",
                    "how_to_test": "Regress PPAC daily pump prices on Brent over 2022-24",
                },
                {
                    "name": "gap_to_price_elasticity",
                    "value": 0.8,
                    "source": "Analyst-set; capped at +120% crude shock",
                    "how_to_test": "Backtest against 2022 Russia-invasion price response",
                },
                {
                    "name": "crude_cost_share_of_retail",
                    "value": self.CRUDE_COST_SHARE_OF_RETAIL,
                    "source": "PPAC retail price build-up (pre-tax crude share)",
                    "how_to_test": "Recompute from the current PPAC price build-up sheet",
                },
            ],
        }

    async def estimate_baseline_flow(self) -> dict[str, Any]:
        """Estimate baseline flow values for all edges based on entity capacities."""
        edges = await self.pool.fetch(
            "SELECT * FROM energy.network_edges WHERE is_active = true AND is_deleted = false"
        )
        updated = 0
        for edge in edges:
            max_cap = edge.get("max_capacity_bpd")
            if max_cap:
                flow = max_cap * 0.75
                util = 75.0
                await self.pool.execute(
                    "UPDATE energy.network_edges SET current_flow_bpd = $1, utilization_pct = $2 WHERE id = $3",
                    flow, util, edge["id"],
                )
                updated += 1
        return {"edges_updated": updated}

    async def snapshot_to_states(self) -> tuple[dict[int, dict], dict[int, dict]]:
        """Build current node_states and edge_states dicts from the database.

        Demand only applies to refineries -- they're the actual crude-consuming
        nodes in this network; SPRs are reserves and ports/pipelines/storage are
        pass-through. National demand (energy.demand_profiles, country-level rows
        only -- the seed also has state-level rows like "India - Gujarat" that no
        node.country ever matches) is allocated across a country's refineries
        proportional to each refinery's capacity_bpd share of that country's total
        refining capacity. Previously every node -- refineries, SPRs, ports, the
        works -- independently got the full flat national figure, which swamped
        whatever a scenario actually disrupted and made supply_gap_bpd read as
        near-constant across runs."""
        nodes = await self.pool.fetch(
            """SELECT * FROM energy.network_nodes
               WHERE is_deleted = false AND is_active = true"""
        )
        demand_rows = await self.pool.fetch(
            "SELECT region, daily_demand_bpd FROM energy.demand_profiles WHERE is_active = true"
        )
        national_demand_bpd = {
            r["region"]: float(r["daily_demand_bpd"])
            for r in demand_rows
            if " - " not in r["region"]
        }

        raw_nodes = {n["id"]: dict(n) for n in nodes}
        refinery_capacity_by_country: dict[str, float] = {}
        for node in raw_nodes.values():
            if node.get("node_type") == "refinery" and node.get("country") in national_demand_bpd:
                country = node["country"]
                refinery_capacity_by_country[country] = (
                    refinery_capacity_by_country.get(country, 0) + (node.get("capacity_bpd") or 0)
                )

        node_states = {}
        for nid, node in raw_nodes.items():
            demand = 0.0
            country = node.get("country")
            if node.get("node_type") == "refinery" and country in national_demand_bpd:
                total_capacity = refinery_capacity_by_country.get(country) or 0
                if total_capacity > 0:
                    demand = national_demand_bpd[country] * ((node.get("capacity_bpd") or 0) / total_capacity)
            node["demand_bpd"] = round(demand, 2)
            node["status"] = "normal"
            node["inbound_bpd"] = 0
            node["outbound_bpd"] = 0
            node["supply_gap_bpd"] = 0
            node_states[nid] = node

        edges = await self.pool.fetch(
            """SELECT e.*, sn.name as source_name, sn.node_type as source_type,
                      tn.name as target_name, tn.node_type as target_type
               FROM energy.network_edges e
               JOIN energy.network_nodes sn ON sn.id = e.source_node_id
               JOIN energy.network_nodes tn ON tn.id = e.target_node_id
               WHERE e.is_deleted = false AND e.is_active = true"""
        )
        edge_states = {}
        for e in edges:
            es = dict(e)
            if not es.get("current_flow_bpd") and es.get("max_capacity_bpd"):
                es["current_flow_bpd"] = es["max_capacity_bpd"] * 0.75
            # network_edges has no FK to shipping_routes/import_corridors (no
            # route_id column exists), so there was never a real relationship
            # to join on -- the previous `LEFT JOIN ... ON sr.is_deleted =
            # false` had no join condition at all, producing a Cartesian
            # product that silently corrupted this dict (last-route-wins per
            # edge id). Use a deterministic per-edge label instead; it won't
            # match scenario keywords like "suez_canal_transit" since no such
            # slug exists anywhere in the schema today (a real gap -- see
            # affected_refineries/affected_ports for the disruption paths that
            # do work off real column data).
            es["route_name"] = f"{es.get('source_name', '')} -> {es.get('target_name', '')}"
            edge_states[e["id"]] = es

        return node_states, edge_states
