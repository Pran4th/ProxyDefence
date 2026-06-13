from fastapi import APIRouter, HTTPException, Request

from backend.api_service.repositories.intelligence import (
    IntelligenceRepository
)

router = APIRouter(
    prefix="/graph",
    tags=["Graph"]
)


ENTITY_ALIASES = {
    "US": "United States",
    "U.S.": "United States",
    "U.S": "United States",
    "The United States": "United States",
    "the United States": "United States",
    "USA": "United States",
    "Trump": "Donald Trump",
    "Central Command": "US Central Command"
}


BLACKLIST_ENTITIES = {
    "AI Generated Image",
    "Brink of War",
    "Tanker Hit",
    "US Strike",
    "Islamabad Agreement'",
    "81st Commemoration of Australia's",
    "Stop Bombing"
}


@router.get("/network")
async def get_network(request: Request):
    try:

        async with request.app.state.pg_pool.acquire() as conn:

            rows = await conn.fetch(
                """
                SELECT
                    source_entity,
                    target_entity,
                    relationship_type,
                    confidence
                FROM relationships
                WHERE confidence >= 0.55
                ORDER BY confidence DESC NULLS LAST,
                         created_at DESC
                LIMIT 250
                """
            )

        nodes = {}
        edges = []
        seen_edges = set()

        for row in rows:

            source = row["source_entity"]
            target = row["target_entity"]

            source = ENTITY_ALIASES.get(
                source,
                source
            )

            target = ENTITY_ALIASES.get(
                target,
                target
            )

            if (
                source in BLACKLIST_ENTITIES
                or target in BLACKLIST_ENTITIES
            ):
                continue

            if source == target:
                continue

            edge_key = (
                source,
                target,
                row["relationship_type"]
            )

            if edge_key in seen_edges:
                continue

            seen_edges.add(edge_key)

            nodes.setdefault(
                source,
                {
                    "id": source,
                    "label": source
                }
            )

            nodes.setdefault(
                target,
                {
                    "id": target,
                    "label": target
                }
            )

            edges.append(
                {
                    "source": source,
                    "target": target,
                    "relationship": row["relationship_type"],
                    "confidence": float(
                        row["confidence"] or 0
                    )
                }
            )

        return {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": list(nodes.values()),
            "edges": edges
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Graph network error: {str(e)}"
        )


@router.get("/{entity}")
async def get_entity_graph(
    entity: str,
    request: Request,
    depth: int = 2,
    limit: int = 50
):
    try:

        entity = ENTITY_ALIASES.get(
            entity,
            entity
        )

        repo = IntelligenceRepository(
            request.app.state.pg_pool
        )

        graph = await repo.expand_graph(
            entity=entity,
            depth=depth,
            limit=limit
        )

        return graph

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Entity graph error: {str(e)}"
        )