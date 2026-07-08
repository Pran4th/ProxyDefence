"""Refinery-Crude Compatibility Engine — determines which crude types a refinery can process."""

import uuid
from typing import Any

import asyncpg

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class RefineryCompatibility:
    """Determines compatibility between refineries and crude commodities."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def compute_all(self) -> dict[str, Any]:
        """Compute compatibility for all refinery-commodity pairs and persist."""
        refineries = await self.pool.fetch(
            "SELECT uuid, name, crude_types_accepted, nelson_complexity_index FROM energy.refineries WHERE is_deleted = false"
        )
        commodities = await self.pool.fetch(
            "SELECT uuid, name, slug, api_gravity, sulfur_content, category FROM energy.commodities WHERE commodity_type = 'crude'"
        )

        pairs_created = 0
        for ref in refineries:
            accepted = ref.get("crude_types_accepted") or []
            nci = ref.get("nelson_complexity_index") or 8.0

            for cm in commodities:
                score, reason = self._evaluate(ref["name"], accepted, nci, cm)

                existing = await self.pool.fetchval(
                    """SELECT id FROM energy.refinery_crude_compatibility
                       WHERE refinery_uuid = $1::uuid AND commodity_uuid = $2::uuid""",
                    ref["uuid"],
                    cm["uuid"],
                )
                if existing:
                    await self.pool.execute(
                        """UPDATE energy.refinery_crude_compatibility
                           SET compatibility = $2::energy.compatibility_score,
                               compatibility_reason = $3,
                               yield_impact_pct = $4,
                               updated_at = NOW()
                           WHERE id = $1""",
                        existing,
                        score,
                        reason,
                        -abs(10 - nci) * 0.5,
                    )
                else:
                    max_blend = 100.0
                    throughput_penalty = 0.0
                    if score == "partial":
                        max_blend = 30.0
                        throughput_penalty = 15.0
                    elif score == "incompatible":
                        max_blend = 0.0
                        throughput_penalty = 100.0

                    yield_impact = -abs(10 - nci) * 0.5 if score != "incompatible" else -100.0

                    await self.pool.execute(
                        """INSERT INTO energy.refinery_crude_compatibility
                           (uuid, refinery_uuid, commodity_uuid, compatibility, compatibility_reason,
                            max_blend_pct, yield_impact_pct, throughput_penalty_pct)
                           VALUES ($1,$2,$3,$4::energy.compatibility_score,$5,$6,$7,$8)
                           ON CONFLICT (refinery_uuid, commodity_uuid) DO NOTHING""",
                        str(uuid.uuid4()),
                        ref["uuid"],
                        cm["uuid"],
                        score,
                        reason,
                        max_blend,
                        round(yield_impact, 2),
                        throughput_penalty,
                    )
                    pairs_created += 1

        return {
            "refineries_evaluated": len(refineries),
            "commodities_evaluated": len(commodities),
            "pairs_created": pairs_created,
        }

    def _evaluate(
        self,
        refinery_name: str,
        accepted: list[str],
        nci: float,
        commodity: asyncpg.Record,
    ) -> tuple[str, str]:
        """Evaluate compatibility and return (compatibility_score, reason)."""
        slug = commodity["slug"]
        name = commodity["name"]
        api = commodity.get("api_gravity") or 30.0
        sulfur = commodity.get("sulfur_content") or 1.0
        category = commodity.get("category") or "medium_sour"

        if accepted:
            for a in accepted:
                if slug.startswith(a.replace("_", "-")) or a.replace("-", "_") in slug:
                    return ("optimal", f"Explicitly accepted crude type '{a}' for {refinery_name}")

            slug_lower = slug.lower()
            for a in accepted:
                a_lower = a.lower()
                if a_lower in slug_lower or slug_lower in a_lower:
                    return ("optimal", f"Accepted crude type '{a}' matches {name}")

        if nci >= 12.0:
            if api >= 30:
                return ("optimal", f"High-complexity refinery (NCI={nci}) can process {name} optimally")
            return ("compatible", f"High-complexity refinery (NCI={nci}) can process {name} with minor blending")

        if nci >= 8.0:
            if "light" in category and sulfur < 1.0:
                return ("optimal", f"Medium-complexity refinery (NCI={nci}) optimized for {category}")
            if api >= 25:
                return ("compatible", f"Medium-complexity refinery (NCI={nci}) can process {name}")
            return ("partial", f"Medium-complexity refinery (NCI={nci}) requires blending for {name}")

        if api > 35 and sulfur < 0.5:
            return ("compatible", f"Low-complexity refinery (NCI={nci}) can process light sweet {name}")
        if api > 30:
            return ("partial", f"Low-complexity refinery (NCI={nci}) requires significant blending for {name}")
        return ("incompatible", f"Low-complexity refinery (NCI={nci}) cannot process {name}")

    async def get_compatibility(
        self,
        refinery_uuid: str | None = None,
        commodity_uuid: str | None = None,
        min_score: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get compatibility records, optionally filtered."""
        conditions = ["rcc.is_deleted = false"]
        params = []
        if refinery_uuid:
            conditions.append(f"rcc.refinery_uuid = ${len(params) + 1}::uuid")
            params.append(refinery_uuid)
        if commodity_uuid:
            conditions.append(f"rcc.commodity_uuid = ${len(params) + 1}::uuid")
            params.append(commodity_uuid)
        if min_score and min_score in ("optimal", "compatible", "partial", "incompatible"):
            score_order = {"optimal": 0, "compatible": 1, "partial": 2, "incompatible": 3}
            threshold = score_order[min_score]
            case_expr = "CASE rcc.compatibility WHEN 'optimal' THEN 0 WHEN 'compatible' THEN 1 WHEN 'partial' THEN 2 WHEN 'incompatible' THEN 3 END"
            conditions.append(f"{case_expr} <= {threshold}")

        where = " AND ".join(conditions)
        rows = await self.pool.fetch(
            f"""SELECT rcc.*, r.name as refinery_name, r.nelson_complexity_index,
                       c.name as commodity_name, c.api_gravity, c.sulfur_content, c.category
                FROM energy.refinery_crude_compatibility rcc
                JOIN energy.refineries r ON r.uuid = rcc.refinery_uuid
                JOIN energy.commodities c ON c.uuid = rcc.commodity_uuid
                WHERE {where}
                ORDER BY r.name, rcc.compatibility, c.name
                LIMIT 200""",
            *params,
        )
        return [dict(r) for r in rows]

    async def get_refinery_recommendations(self, refinery_uuid: str) -> list[dict[str, Any]]:
        """Get recommended crude types for a specific refinery, ranked by compatibility."""
        rows = await self.pool.fetch(
            """SELECT rcc.*, c.name as commodity_name, c.api_gravity,
                      c.sulfur_content, c.category, c.benchmark_price
               FROM energy.refinery_crude_compatibility rcc
               JOIN energy.commodities c ON c.uuid = rcc.commodity_uuid
               WHERE rcc.refinery_uuid = $1::uuid AND rcc.is_deleted = false
               ORDER BY CASE rcc.compatibility
                   WHEN 'optimal' THEN 0 WHEN 'compatible' THEN 1
                   WHEN 'partial' THEN 2 WHEN 'incompatible' THEN 3 END,
                   c.benchmark_price ASC NULLS LAST
               LIMIT 20""",
            refinery_uuid,
        )
        return [dict(r) for r in rows]
