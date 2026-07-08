"""Debug the entity risk-profile and propagate endpoints."""
import asyncio
import asyncpg

DSN = "postgresql://admin:change-me@localhost:5432/defenseintel"


async def test_risk_profile_query():
    conn = await asyncpg.connect(DSN)
    uuid = await conn.fetchval("SELECT uuid FROM energy.import_corridors LIMIT 1")
    print(f"Corridor UUID: {uuid}")

    entity_row = await conn.fetchrow(
        "SELECT id FROM energy.import_corridors WHERE uuid = $1", uuid
    )
    entity_id = entity_row["id"]
    entity_table = "import_corridors"
    print(f"Entity ID: {entity_id}")

    # Test related_risks query
    try:
        related = await conn.fetch(
            """SELECT rs.entity_uuid, rs.entity_type, rs.dimension, rs.score, rs.confidence
               FROM energy.risk_scores rs
               WHERE rs.expires_at > NOW()
               AND rs.entity_type IN (
                   SELECT DISTINCT unnest(ARRAY[er.source_entity_type, er.target_entity_type])
                   FROM energy.entity_relationships er
                   WHERE (er.source_entity_type = $2 AND er.source_entity_id = $3)
                      OR (er.target_entity_type = $2 AND er.target_entity_id = $3)
               )
               AND rs.entity_uuid != $1::uuid
               AND rs.dimension = 'overall'
               ORDER BY rs.score DESC LIMIT 10""",
            str(uuid), entity_table, entity_id,
        )
        print(f"[OK] related_risks query: {len(related)} rows")
    except Exception as e:
        print(f"[FAIL] related_risks query: {e}")

    # Test propagation lookup
    try:
        related = await conn.fetch(
            """SELECT source_entity_type, source_entity_id, target_entity_type, target_entity_id
               FROM energy.entity_relationships
               WHERE (source_entity_type = $1 AND source_entity_id = $2)
                  OR (target_entity_type = $1 AND target_entity_id = $2)""",
            entity_table, entity_id,
        )
        print(f"[OK] propagation relationships: {len(related)} rows")
        for r in related:
            print(f"  {r['source_entity_type']}:{r['source_entity_id']} -> {r['target_entity_type']}:{r['target_entity_id']}")
    except Exception as e:
        print(f"[FAIL] propagation relationships: {e}")

    await conn.close()


async def test_disruption_signals():
    conn = await asyncpg.connect(DSN)

    # Check expires_at values
    rows = await conn.fetch(
        "SELECT uuid, title, severity, expires_at, created_at FROM energy.disruption_signals LIMIT 5"
    )
    for r in rows:
        print(f"Signal: {r['title'][:40]:40s} severity={r['severity']} expires={r['expires_at']}")

    # Check risk_scores
    scores = await conn.fetch("SELECT COUNT(*) as cnt FROM energy.risk_scores")
    print(f"Risk scores: {scores[0]['cnt']}")

    await conn.close()


async def main():
    print("=" * 60)
    print("DEBUG: Entity risk profile query")
    print("=" * 60)
    await test_risk_profile_query()

    print("\n" + "=" * 60)
    print("DEBUG: Disruption signals")
    print("=" * 60)
    await test_disruption_signals()


asyncio.run(main())
