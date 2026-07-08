import json
from typing import Any

from backend.shared.logging_config import get_logger

from db import get_connection, return_connection

logger = get_logger(__name__)

_bridge_schema_ready = False

ENERGY_ENTITY_TABLES = [
    ("location", "energy.locations", "name"),
    ("port", "energy.ports", "name"),
    ("oil_field", "energy.oil_fields", "name"),
    ("gas_field", "energy.gas_fields", "name"),
    ("pipeline", "energy.pipelines", "name"),
    ("refinery", "energy.refineries", "name"),
    ("power_plant", "energy.power_plants", "name"),
    ("storage_facility", "energy.storage_facilities", "name"),
    ("strategic_petroleum_reserve", "energy.strategic_petroleum_reserves", "name"),
    ("organization", "energy.organizations", "name"),
    ("commodity", "energy.commodities", "name"),
    ("supplier", "energy.suppliers", "name"),
    ("import_corridor", "energy.import_corridors", "name"),
    ("shipping_route", "energy.shipping_routes", "name"),
]


def ensure_energy_bridge_schema(conn) -> None:
    """Create the public bridge tables needed by Energy enrichment."""
    global _bridge_schema_ready
    if _bridge_schema_ready:
        return

    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS energy_entity_mappings (
                id SERIAL PRIMARY KEY,
                article_id INTEGER NOT NULL REFERENCES processed_articles(id) ON DELETE CASCADE,
                entity_text TEXT NOT NULL,
                entity_type VARCHAR(50) NOT NULL,
                energy_asset_type VARCHAR(50) NOT NULL,
                energy_asset_uuid UUID NOT NULL,
                energy_asset_name TEXT NOT NULL,
                energy_asset_slug TEXT NOT NULL,
                match_method VARCHAR(20) DEFAULT 'exact',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS article_energy_enrichments (
                id SERIAL PRIMARY KEY,
                article_id INTEGER UNIQUE NOT NULL REFERENCES processed_articles(id) ON DELETE CASCADE,
                locations JSONB DEFAULT '[]'::jsonb,
                infrastructure JSONB DEFAULT '[]'::jsonb,
                organizations JSONB DEFAULT '[]'::jsonb,
                commodities JSONB DEFAULT '[]'::jsonb,
                infrastructure_events JSONB DEFAULT '[]'::jsonb,
                context JSONB DEFAULT '{}'::jsonb,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_energy_entity_mappings_article_id ON energy_entity_mappings(article_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_energy_entity_mappings_entity_text ON energy_entity_mappings(entity_text)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_energy_entity_mappings_asset_type ON energy_entity_mappings(energy_asset_type)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_energy_entity_mappings_asset_uuid ON energy_entity_mappings(energy_asset_uuid)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_article_energy_enrichments_article_id ON article_energy_enrichments(article_id)")

    _bridge_schema_ready = True


def _match_energy_entity(cur, entity_text: str) -> list[dict[str, Any]]:
    """Try to match an NER entity text against all energy asset tables."""
    if not entity_text or len(entity_text.strip()) < 2:
        return []

    text = entity_text.strip().lower()
    matches = []

    for asset_type, table, name_col in ENERGY_ENTITY_TABLES:
        cur.execute(
            f"""
            SELECT uuid, {name_col} AS name, slug
            FROM {table}
            WHERE is_deleted = FALSE
              AND (LOWER({name_col}) = %s OR LOWER(slug) = %s)
            LIMIT 1
            """,
            (text, text),
        )
        row = cur.fetchone()
        if row:
            matches.append({
                "asset_type": asset_type,
                "uuid": row[0],
                "name": row[1],
                "slug": row[2],
                "method": "exact",
            })
            continue

        cur.execute(
            f"""
            SELECT uuid, {name_col} AS name, slug
            FROM {table}
            WHERE is_deleted = FALSE
              AND LOWER({name_col}) LIKE %s
            LIMIT 1
            """,
            (f"%{text}%",),
        )
        row = cur.fetchone()
        if row:
            matches.append({
                "asset_type": asset_type,
                "uuid": row[0],
                "name": row[1],
                "slug": row[2],
                "method": "partial",
            })

    return matches


def _build_infrastructure_context(cur, article_id: int) -> dict[str, Any]:
    """Aggregate infrastructure context for matched energy assets."""
    cur.execute(
        """
        SELECT energy_asset_type, energy_asset_uuid, energy_asset_name
        FROM energy_entity_mappings
        WHERE article_id = %s
        """,
        (article_id,),
    )
    mapped_assets = cur.fetchall()

    if not mapped_assets:
        return {"locations": [], "infrastructure": [], "organizations": [], "commodities": [], "infrastructure_events": []}

    location_uuids = []
    infra_assets = []
    org_uuids = []
    commodity_uuids = []

    for asset_type, asset_uuid, asset_name in mapped_assets:
        if asset_type == "location":
            location_uuids.append(asset_uuid)
        elif asset_type == "organization":
            org_uuids.append(asset_uuid)
        elif asset_type == "commodity":
            commodity_uuids.append(asset_uuid)
        else:
            infra_assets.append((asset_type, asset_uuid, asset_name))

    locations = []
    if location_uuids:
        cur.execute(
            """
            SELECT uuid, name, slug, location_type, iso_code, region,
                   latitude, longitude
            FROM energy.locations
            WHERE uuid = ANY(%s::uuid[]) AND is_deleted = FALSE
            """,
            (location_uuids,),
        )
        cols = [desc[0] for desc in cur.description]
        for row in cur.fetchall():
            locations.append(dict(zip(cols, row)))

    infrastructure = []
    for asset_type, asset_uuid, asset_name in infra_assets:
        table_map = {
            "port": "energy.ports",
            "oil_field": "energy.oil_fields",
            "gas_field": "energy.gas_fields",
            "pipeline": "energy.pipelines",
            "refinery": "energy.refineries",
            "power_plant": "energy.power_plants",
            "storage_facility": "energy.storage_facilities",
            "strategic_petroleum_reserve": "energy.strategic_petroleum_reserves",
            "import_corridor": "energy.import_corridors",
            "shipping_route": "energy.shipping_routes",
            "supplier": "energy.suppliers",
        }
        table = table_map.get(asset_type)
        if not table:
            continue
        cur.execute(
            f"""
            SELECT uuid, name, slug, status, operational_status, criticality,
                   importance, confidence
            FROM {table}
            WHERE uuid = %s::uuid AND is_deleted = FALSE
            """,
            (asset_uuid,),
        )
        row = cur.fetchone()
        if row:
            cols = [desc[0] for desc in cur.description]
            item = dict(zip(cols, row))
            item["asset_category"] = asset_type
            infrastructure.append(item)

    organizations = []
    if org_uuids:
        cur.execute(
            """
            SELECT o.uuid, o.name, o.slug, o.organization_type, o.tags
            FROM energy.organizations o
            WHERE o.uuid = ANY(%s::uuid[]) AND o.is_deleted = FALSE
            """,
            (org_uuids,),
        )
        cols = [desc[0] for desc in cur.description]
        for row in cur.fetchall():
            organizations.append(dict(zip(cols, row)))

    commodities = []
    if commodity_uuids:
        cur.execute(
            """
            SELECT uuid, name, slug, commodity_type, unit, benchmark_price
            FROM energy.commodities
            WHERE uuid = ANY(%s::uuid[])
            """,
            (commodity_uuids,),
        )
        cols = [desc[0] for desc in cur.description]
        for row in cur.fetchall():
            commodities.append(dict(zip(cols, row)))

    entity_table_map = {
        "port": "ports",
        "oil_field": "oil_fields",
        "gas_field": "gas_fields",
        "pipeline": "pipelines",
        "refinery": "refineries",
        "power_plant": "power_plants",
        "storage_facility": "storage_facilities",
        "strategic_petroleum_reserve": "strategic_petroleum_reserves",
        "import_corridor": "import_corridors",
        "shipping_route": "shipping_routes",
        "location": "locations",
        "organization": "organizations",
        "supplier": "suppliers",
    }
    infrastructure_events = []
    for entry in mapped_assets:
        asset_type, asset_uuid, asset_name = entry
        table_name = entity_table_map.get(asset_type)
        if not table_name:
            continue
        cur.execute(
            f"""
            SELECT ie.uuid, ie.event_type, ie.severity, ie.description, ie.occurred_at
            FROM energy.infrastructure_events ie
            JOIN energy.{table_name} e ON e.id = ie.entity_id
            WHERE ie.entity_type = %s AND e.uuid = %s::uuid
            ORDER BY ie.occurred_at DESC
            LIMIT 5
            """,
            (asset_type, asset_uuid),
        )
        cols = [desc[0] for desc in cur.description]
        for row in cur.fetchall():
            evt = dict(zip(cols, row))
            evt["asset_name"] = asset_name
            evt["asset_type"] = asset_type
            infrastructure_events.append(evt)

    return {
        "locations": locations,
        "infrastructure": infrastructure,
        "organizations": organizations,
        "commodities": commodities,
        "infrastructure_events": infrastructure_events,
    }


def _build_summary_context(article_id: int, enrichment: dict[str, Any]) -> dict[str, Any]:
    """Build a concise summary context from the enrichment data."""
    countries = [
        loc["name"]
        for loc in enrichment["locations"]
        if loc.get("location_type") == "country"
    ]
    infra_names = [item["name"] for item in enrichment["infrastructure"]]
    org_names = [org["name"] for org in enrichment["organizations"]]
    commodity_names = [c["name"] for c in enrichment["commodities"]]
    event_count = len(enrichment["infrastructure_events"])

    return {
        "countries_mentioned": countries,
        "infrastructure_mentioned": infra_names,
        "organizations_mentioned": org_names,
        "commodities_mentioned": commodity_names,
        "infrastructure_event_count": event_count,
        "total_linked_assets": (
            len(countries) + len(infra_names) + len(org_names) + len(commodity_names)
        ),
    }


def replace_energy_mappings(article_db_id: int, conn) -> None:
    """Clean up old energy mappings before entities are refreshed."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM energy_entity_mappings WHERE article_id = %s", (article_db_id,))
        cur.execute("DELETE FROM article_energy_enrichments WHERE article_id = %s", (article_db_id,))


def enrich_energy_context(article_db_id: int, conn=None) -> None:
    """Link extracted entities to energy assets and build enrichment context."""
    owns_connection = conn is None
    if conn is None:
        conn = get_connection()
    try:
        ensure_energy_bridge_schema(conn)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM energy_entity_mappings WHERE article_id = %s", (article_db_id,))
            cur.execute("DELETE FROM article_energy_enrichments WHERE article_id = %s", (article_db_id,))

            cur.execute(
                "SELECT entity_text, entity_type FROM extracted_entities WHERE article_id = %s",
                (article_db_id,),
            )
            entities = cur.fetchall()

            for entity_text, entity_type in entities:
                if not entity_text:
                    continue
                matches = _match_energy_entity(cur, entity_text)
                for match in matches:
                    cur.execute(
                        """
                        INSERT INTO energy_entity_mappings
                            (article_id, entity_text, entity_type, energy_asset_type,
                             energy_asset_uuid, energy_asset_name, energy_asset_slug, match_method)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            article_db_id, entity_text, entity_type,
                            match["asset_type"], match["uuid"],
                            match["name"], match["slug"], match["method"],
                        ),
                    )

            enrichment = _build_infrastructure_context(cur, article_db_id)
            summary = _build_summary_context(article_db_id, enrichment)

            cur.execute(
                """
                INSERT INTO article_energy_enrichments
                    (article_id, locations, infrastructure, organizations,
                     commodities, infrastructure_events, context)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (article_id) DO UPDATE SET
                    locations = EXCLUDED.locations,
                    infrastructure = EXCLUDED.infrastructure,
                    organizations = EXCLUDED.organizations,
                    commodities = EXCLUDED.commodities,
                    infrastructure_events = EXCLUDED.infrastructure_events,
                    context = EXCLUDED.context,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    article_db_id,
                    json.dumps(enrichment["locations"], default=str),
                    json.dumps(enrichment["infrastructure"], default=str),
                    json.dumps(enrichment["organizations"], default=str),
                    json.dumps(enrichment["commodities"], default=str),
                    json.dumps(enrichment["infrastructure_events"], default=str),
                    json.dumps(summary, default=str),
                ),
            )

            matched_count = len(enrichment["locations"]) + len(enrichment["infrastructure"]) \
                          + len(enrichment["organizations"]) + len(enrichment["commodities"])
            if matched_count > 0:
                logger.info(
                    "energy_enrichment_complete",
                    article_id=article_db_id,
                    matched_assets=matched_count,
                    countries=len(enrichment["locations"]),
                    infrastructure=len(enrichment["infrastructure"]),
                    organizations=len(enrichment["organizations"]),
                )

        if owns_connection:
            conn.commit()
    except Exception:
        if owns_connection:
            conn.rollback()
        raise
    finally:
        if owns_connection:
            return_connection(conn)
