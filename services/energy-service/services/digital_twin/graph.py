"""Supply chain network graph — builds and queries the directed weighted graph."""

import json
from typing import Any

import asyncpg

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class NetworkGraph:
    """Builds and manages the supply chain directed weighted graph from existing entity data."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def build_from_entities(self) -> dict[str, Any]:
        """Auto-build network nodes and edges from existing energy entity data."""
        nodes_created = await self._build_nodes()
        edges_created = await self._build_edges()
        return {"nodes": nodes_created, "edges": edges_created}

    async def _build_nodes(self) -> int:
        """Populate network_nodes from all existing energy entity types."""
        count = 0
        mappings = [
            ("oil_fields", "producer", "capacity_bpd", "reserve_estimate_barrels"),
            ("gas_fields", "producer", None, "reserve_estimate_cf"),
            ("ports", "import", "annual_capacity_mtpa", "storage_capacity_barrels"),
            ("pipelines", "pipeline", "capacity_bpd", None),
            ("refineries", "refinery", "capacity_bpd", None),
            ("storage_facilities", "storage", None, "capacity_barrels"),
            ("strategic_petroleum_reserves", "spr", "max_drawdown_rate_bpd", "capacity_barrels"),
            ("suppliers", "producer", "market_share_pct", None),
            ("shipping_routes", "shipping", None, None),
            ("power_plants", "power_generator", "capacity_mw", None),
        ]

        for table, category, cap_col, storage_col in mappings:
            try:
                rows = await self.pool.fetch(f"SELECT * FROM energy.{table} WHERE is_deleted = false")
                for row in rows:
                    cap = row.get(cap_col) if cap_col else None
                    storage = row.get(storage_col) if storage_col else None
                    loc = await self._get_node_location(row, table)

                    node_type = table.rstrip("s") if not table.endswith("ies") else table[:-3] + "y"
                    if node_type == "strategic_petroleum_reserve":
                        node_type = "strategic_petroleum_reserve"

                    exists = await self.pool.fetchval(
                        "SELECT id FROM energy.network_nodes WHERE node_type = $1 AND entity_id = $2 AND is_deleted = false",
                        node_type, row["id"],
                    )
                    if exists:
                        continue

                    loc_id = loc.get("location_id")
                    await self.pool.execute(
                        """INSERT INTO energy.network_nodes
                           (node_type, entity_id, name, category, location_id, country,
                            latitude, longitude, capacity_bpd, storage_capacity_barrels,
                            current_inventory_barrels, max_drawdown_bpd, operational_status, criticality)
                           VALUES ($1,$2,$3,$4,$5::uuid,$6,$7,$8,$9,$10,$11,$12,$13,$14)""",
                        node_type, row["id"], row["name"], category,
                        loc_id, loc.get("country"),
                        row.get("latitude"), row.get("longitude"),
                        cap, storage,
                        row.get("current_inventory_barrels") if "current_inventory_barrels" in row else None,
                        row.get("max_drawdown_rate_bpd") if "max_drawdown_rate_bpd" in row else None,
                        row.get("operational_status", "active"),
                        row.get("criticality", "medium"),
                    )
                    count += 1
            except Exception as exc:
                logger.warning("node_build_skipped", table=table, error=str(exc))

        return count

    async def _get_node_location(self, row: asyncpg.Record, table: str) -> dict:
        result = {"location_id": None, "country": None}
        loc_id = row.get("location_id")
        if loc_id:
            result["location_id"] = str(loc_id)
            loc_row = await self.pool.fetchrow(
                "SELECT name, iso_code_3 FROM energy.locations WHERE uuid = $1::uuid", loc_id,
            )
            if loc_row:
                result["country"] = loc_row.get("name") or loc_row.get("iso_code_3")
        else:
            org_id = row.get("organization_id")
            if org_id:
                org_row = await self.pool.fetchrow(
                    "SELECT country_id FROM energy.organizations WHERE id = $1", org_id,
                )
                if org_row and org_row["country_id"]:
                    loc_row = await self.pool.fetchrow(
                        "SELECT uuid, name FROM energy.locations WHERE id = $1", org_row["country_id"],
                    )
                    if loc_row:
                        result["location_id"] = str(loc_row["uuid"])
                        result["country"] = loc_row["name"]
        return result

    async def _build_edges(self) -> int:
        """Build network edges from entity_relationships and known supply chain connections."""
        count = 0

        node_map = await self._get_node_map()

        try:
            rels = await self.pool.fetch(
                """SELECT * FROM energy.entity_relationships
                   WHERE is_deleted = false OR is_deleted IS NULL"""
            )
            for rel in rels:
                source_type = rel["source_entity_type"]
                target_type = rel["target_entity_type"]
                source_id = rel["source_entity_id"]
                target_id = rel["target_entity_id"]

                src_node = node_map.get((source_type, source_id))
                tgt_node = node_map.get((target_type, target_id))
                if not src_node or not tgt_node:
                    continue

                edge_type = self._infer_edge_type(source_type, target_type)
                exists = await self.pool.fetchval(
                    """SELECT id FROM energy.network_edges
                       WHERE source_node_id = $1 AND target_node_id = $2 AND edge_type = $3 AND is_deleted = false""",
                    src_node, tgt_node, edge_type,
                )
                if exists:
                    continue

                await self.pool.execute(
                    """INSERT INTO energy.network_edges
                       (source_node_id, target_node_id, edge_type, max_capacity_bpd,
                        travel_time_hours, transport_cost_bbl, reliability, commodity_type)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8)""",
                    src_node, tgt_node, edge_type,
                    await self._estimate_capacity(source_type, source_id),
                    await self._estimate_travel_time(source_type, source_id, target_type, target_id),
                    None, 0.95, "crude",
                )
                count += 1
        except Exception as exc:
            logger.warning("edge_build_skipped", error=str(exc))

        count += await self._build_supply_chain_edges(node_map)
        count += await self._build_spr_drawdown_edges()

        return count

    async def _build_spr_drawdown_edges(self) -> int:
        """SPRs only ever get a `located_in -> location` entity_relationships
        row, never a link to a refinery, so the relationship-driven loop above
        never creates a `drawdown` edge -- SPR release capacity has never
        actually been wired into the flow network. Connect each SPR to every
        refinery in its own country, splitting its drawdown capacity evenly
        across them, as a defensible proxy until finer-grained SPR->refinery
        logistics data exists."""
        count = 0
        sprs = await self.pool.fetch(
            """SELECT id, country, max_drawdown_bpd FROM energy.network_nodes
               WHERE node_type = 'strategic_petroleum_reserve' AND is_deleted = false"""
        )
        refineries = await self.pool.fetch(
            """SELECT id, country FROM energy.network_nodes
               WHERE node_type = 'refinery' AND is_deleted = false"""
        )
        refineries_by_country: dict[str, list[int]] = {}
        for r in refineries:
            refineries_by_country.setdefault(r["country"], []).append(r["id"])

        for spr in sprs:
            targets = refineries_by_country.get(spr["country"], [])
            if not targets:
                continue
            per_target_capacity = (spr["max_drawdown_bpd"] or 0) / len(targets)
            for target_id in targets:
                exists = await self.pool.fetchval(
                    """SELECT id FROM energy.network_edges
                       WHERE source_node_id = $1 AND target_node_id = $2
                             AND edge_type = 'drawdown' AND is_deleted = false""",
                    spr["id"], target_id,
                )
                if exists:
                    continue
                await self.pool.execute(
                    """INSERT INTO energy.network_edges
                       (source_node_id, target_node_id, edge_type, max_capacity_bpd, reliability, commodity_type)
                       VALUES ($1,$2,'drawdown',$3,0.95,'crude')""",
                    spr["id"], target_id, per_target_capacity,
                )
                count += 1
        return count

    async def _get_node_map(self) -> dict[tuple[str, int], int]:
        rows = await self.pool.fetch(
            "SELECT id, node_type, entity_id FROM energy.network_nodes WHERE entity_id IS NOT NULL AND is_deleted = false"
        )
        return {(r["node_type"], r["entity_id"]): r["id"] for r in rows}

    def _infer_edge_type(self, source_type: str, target_type: str) -> str:
        mappings = {
            ("oil_field", "pipeline"): "crude_flow",
            ("gas_field", "pipeline"): "crude_flow",
            ("oil_field", "port"): "crude_flow",
            ("port", "pipeline"): "crude_flow",
            ("pipeline", "refinery"): "crude_flow",
            ("refinery", "storage_facility"): "storage_inject",
            ("storage_facility", "port"): "crude_flow",
            ("refinery", "port"): "product_flow",
            ("supplier", "port"): "crude_flow",
            ("port", "shipping_route"): "transit",
            ("shipping_route", "port"): "transit",
            ("port", "storage_facility"): "storage_inject",
            ("strategic_petroleum_reserve", "refinery"): "drawdown",
            ("storage_facility", "refinery"): "crude_flow",
            ("pipeline", "storage_facility"): "storage_inject",
            ("refinery", "power_plant"): "product_flow",
        }
        return mappings.get((source_type, target_type), "crude_flow")

    async def _estimate_capacity(self, source_type: str, source_id: int) -> float | None:
        if source_type == "strategic_petroleum_reserve":
            # This table has no capacity_bpd/production_bpd/throughput_mtpa columns
            # at all -- only max_drawdown_rate_bpd -- so the generic query below
            # would raise UndefinedColumnError and silently return None via the
            # broad except. Special-cased so SPR drawdown edges get real capacity.
            try:
                return await self.pool.fetchval(
                    "SELECT max_drawdown_rate_bpd FROM energy.strategic_petroleum_reserves WHERE id = $1",
                    source_id,
                )
            except Exception:
                return None
        try:
            row = await self.pool.fetchrow(
                f"SELECT capacity_bpd, production_bpd, throughput_mtpa FROM energy.{source_type}s WHERE id = $1",
                source_id,
            )
            if row:
                return row.get("capacity_bpd") or row.get("production_bpd") or row.get("throughput_mtpa")
        except Exception:
            pass
        return None

    async def _estimate_travel_time(self, source_type: str, source_id: int, target_type: str, target_id: int) -> float | None:
        try:
            row = await self.pool.fetchrow(
                f"SELECT transit_time_days, distance_nm FROM energy.{source_type}s WHERE id = $1",
                source_id,
            )
            if row and row.get("transit_time_days"):
                return row["transit_time_days"] * 24
            if row and row.get("distance_nm"):
                return row["distance_nm"] / 15  # ~15 knots avg speed
        except Exception:
            pass
        return None

    async def _build_supply_chain_edges(self, node_map: dict) -> int:
        """Build additional supply chain edges from route/corridor data."""
        count = 0

        routes = await self.pool.fetch(
            """SELECT sr.id, sr.name, sr.origin_port_id, sr.destination_port_id,
                      sr.distance_nm, sr.transit_time_days, sr.risk_score
               FROM energy.shipping_routes sr WHERE sr.is_deleted = false"""
        )
        for route in routes:
            orig_node = None
            dest_node = None
            if route["origin_port_id"]:
                orig_node = node_map.get(("port", route["origin_port_id"]))
            if route["destination_port_id"]:
                dest_node = node_map.get(("port", route["destination_port_id"]))
            if orig_node and dest_node:
                exists = await self.pool.fetchval(
                    """SELECT id FROM energy.network_edges
                       WHERE source_node_id = $1 AND target_node_id = $2 AND edge_type = 'transit' AND is_deleted = false""",
                    orig_node, dest_node,
                )
                if not exists:
                    await self.pool.execute(
                        """INSERT INTO energy.network_edges
                           (source_node_id, target_node_id, edge_type, category,
                            max_capacity_bpd, travel_time_hours, risk_multiplier, reliability, commodity_type)
                           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)""",
                        orig_node, dest_node, "transit", "primary",
                        None,
                        (route["transit_time_days"] or route["distance_nm"] / 360) * 24,
                        max(0.5, 1.0 - (route["risk_score"] or 0) / 2),
                        0.9, "crude",
                    )
                    count += 1

        corridors = await self.pool.fetch(
            """SELECT ic.id, ic.name, ic.origin_location_id, ic.destination_location_id,
                      ic.distance_km, ic.transit_time_days
               FROM energy.import_corridors ic WHERE ic.is_deleted = false"""
        )
        for corr in corridors:
            orig_ports = await self.pool.fetch(
                "SELECT id FROM energy.ports WHERE location_id = $1 AND is_deleted = false LIMIT 1",
                corr["origin_location_id"],
            )
            dest_ports = await self.pool.fetch(
                "SELECT id FROM energy.ports WHERE location_id = $1 AND is_deleted = false LIMIT 1",
                corr["destination_location_id"],
            )
            for op in orig_ports:
                orig_node = node_map.get(("port", op["id"]))
                for dp in dest_ports:
                    dest_node = node_map.get(("port", dp["id"]))
                    if orig_node and dest_node:
                        exists = await self.pool.fetchval(
                            "SELECT id FROM energy.network_edges WHERE source_node_id=$1 AND target_node_id=$2 AND edge_type='crude_flow' AND is_deleted=false",
                            orig_node, dest_node,
                        )
                        if not exists:
                            await self.pool.execute(
                                "INSERT INTO energy.network_edges (source_node_id, target_node_id, edge_type, travel_time_hours) VALUES ($1,$2,$3,$4)",
                                orig_node, dest_node, "crude_flow",
                                (corr["transit_time_days"] or corr["distance_km"] / 800) * 24,
                            )
                            count += 1

        return count

    async def get_graph(self) -> dict[str, Any]:
        rows = await self.pool.fetch(
            "SELECT * FROM energy.network_nodes WHERE is_deleted = false AND is_active = true ORDER BY name"
        )
        edges = await self.pool.fetch(
            """SELECT e.*, sn.name as source_name, sn.node_type as source_type,
                      tn.name as target_name, tn.node_type as target_type
               FROM energy.network_edges e
               JOIN energy.network_nodes sn ON sn.id = e.source_node_id
               JOIN energy.network_nodes tn ON tn.id = e.target_node_id
               WHERE e.is_deleted = false AND e.is_active = true"""
        )
        return {
            "nodes": [dict(r) for r in rows],
            "edges": [dict(r) for r in edges],
            "node_count": len(rows),
            "edge_count": len(edges),
        }

    async def find_path(self, from_node_id: int, to_node_id: int) -> list[dict]:
        """BFS shortest path through the network graph."""
        visited = set()
        queue = [[from_node_id]]
        while queue:
            path = queue.pop(0)
            node = path[-1]
            if node == to_node_id:
                return await self._resolve_path(path)
            if node not in visited:
                visited.add(node)
                edges = await self.pool.fetch(
                    "SELECT target_node_id FROM energy.network_edges WHERE source_node_id = $1 AND is_active = true AND is_deleted = false",
                    node,
                )
                for edge in edges:
                    new_path = list(path)
                    new_path.append(edge["target_node_id"])
                    queue.append(new_path)
        return []

    async def _resolve_path(self, node_ids: list[int]) -> list[dict]:
        path_data = []
        for i, nid in enumerate(node_ids):
            node = await self.pool.fetchrow(
                "SELECT id, uuid, name, node_type, category FROM energy.network_nodes WHERE id = $1", nid,
            )
            if node:
                path_data.append(dict(node))
            if i < len(node_ids) - 1:
                edge = await self.pool.fetchrow(
                    """SELECT * FROM energy.network_edges
                       WHERE source_node_id = $1 AND target_node_id = $2 AND is_active = true""",
                    node_ids[i], node_ids[i + 1],
                )
                if edge:
                    path_data[-1]["edge"] = dict(edge)
        return path_data

    async def get_downstream(self, node_id: int) -> list[dict]:
        edges = await self.pool.fetch(
            """SELECT e.*, sn.name as source_name, tn.name as target_name, tn.node_type as target_type
               FROM energy.network_edges e
               JOIN energy.network_nodes sn ON sn.id = e.source_node_id
               JOIN energy.network_nodes tn ON tn.id = e.target_node_id
               WHERE e.source_node_id = $1 AND e.is_active = true AND e.is_deleted = false""",
            node_id,
        )
        return [dict(r) for r in edges]

    async def get_upstream(self, node_id: int) -> list[dict]:
        edges = await self.pool.fetch(
            """SELECT e.*, sn.name as source_name, sn.node_type as source_type,
                      tn.name as target_name
               FROM energy.network_edges e
               JOIN energy.network_nodes sn ON sn.id = e.source_node_id
               JOIN energy.network_nodes tn ON tn.id = e.target_node_id
               WHERE e.target_node_id = $1 AND e.is_active = true AND e.is_deleted = false""",
            node_id,
        )
        return [dict(r) for r in edges]

    async def get_dependencies(self, node_id: int, depth: int = 5) -> list[dict]:
        """Get all downstream dependencies recursively."""
        all_downstream = []
        visited = set()

        async def _traverse(nid: int, remaining: int):
            if remaining <= 0 or nid in visited:
                return
            visited.add(nid)
            edges = await self.pool.fetch(
                "SELECT * FROM energy.network_edges WHERE source_node_id = $1 AND is_active = true AND is_deleted = false",
                nid,
            )
            for edge in edges:
                target = await self.pool.fetchrow(
                    "SELECT id, uuid, name, node_type, category FROM energy.network_nodes WHERE id = $1", edge["target_node_id"],
                )
                if target:
                    entry = dict(target)
                    entry["edge"] = dict(edge)
                    entry["depth"] = depth - remaining + 1
                    all_downstream.append(entry)
                    await _traverse(target["id"], remaining - 1)

        await _traverse(node_id, depth)
        return all_downstream
