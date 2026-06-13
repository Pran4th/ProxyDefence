from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
import httpx

router = APIRouter(
    prefix="/copilot",
    tags=["Copilot"]
)


class CopilotRequest(BaseModel):
    question: str


@router.post("/query")
async def query_copilot(
    payload: CopilotRequest,
    request: Request
):
    try:

        query = payload.question

        # -----------------------------
        # Semantic Search
        # -----------------------------

        async with httpx.AsyncClient() as client:

            response = await client.get(
                "http://embedding-service:8000/search",
                params={"q": query}
            )

            semantic_data = response.json()
            articles = semantic_data["results"]

        print("\n=== COPILOT ARTICLES ===")

        for article in articles:
            print(article)

        article_ids = [
            article["id"]
            for article in articles
        ]

        print("ARTICLE IDS:", article_ids)

        entities = []
        relationships = []
        related_events = []

        # -----------------------------
        # Entity / Relationship Lookup
        # -----------------------------

        async with request.app.state.pg_pool.acquire() as conn:

            if article_ids:

                entities = await conn.fetch(
                    """
                    SELECT
                        entity_text,
                        entity_type,
                        COUNT(*) AS mentions
                    FROM extracted_entities
                    WHERE article_id = ANY($1)
                    AND entity_type IN (
                        'PERSON',
                        'ORG',
                        'GPE'
                    )
                    GROUP BY entity_text, entity_type
                    ORDER BY mentions DESC
                    LIMIT 15
                    """,
                    article_ids
                )

                print("\n=== RAW ENTITIES ===")

                for entity in entities:
                    print(dict(entity))

                relationships = await conn.fetch(
                    """
                    SELECT
                        source_entity,
                        target_entity,
                        relationship_type,
                        confidence,
                        article_id
                    FROM relationships
                    WHERE article_id = ANY($1)
                    ORDER BY confidence DESC
                    LIMIT 15
                    """,
                    article_ids
                )

                related_events = await conn.fetch(
                    """
                    SELECT DISTINCT
                        e.id,
                        e.title,
                        e.topic,
                        e.risk_level,
                        e.risk_score
                    FROM events e
                    JOIN event_articles ea
                        ON e.id = ea.event_id
                    WHERE ea.article_id = ANY($1)
                    ORDER BY e.risk_score DESC
                    LIMIT 10
                    """,
                    article_ids
                )

        # -----------------------------
        # Threat Level Calculation
        # -----------------------------

        high_risk_count = 0

        for article in articles:

            risk = str(
                article.get(
                    "risk_level",
                    "low"
                )
            ).lower()

            if risk in ["high", "critical"]:
                high_risk_count += 1

        if high_risk_count >= 4:
            threat_level = "critical"

        elif high_risk_count >= 2:
            threat_level = "high"

        elif high_risk_count >= 1:
            threat_level = "medium"

        else:
            threat_level = "low"

        # -----------------------------
        # Entity Normalization
        # -----------------------------

        entity_aliases = {
            "Trump": "Donald Trump",
            "US": "United States",
            "U.S.": "United States",
            "USA": "United States",
            "The United States": "United States",
            "United States of America": "United States",
            "Central Command": "US Central Command"
        }

        blacklist_entities = {
            "AI Generated Image",
            "Brink of War"
        }

        normalized_entities = {}

        for row in entities:

            name = row["entity_text"]

            if name in blacklist_entities:
                continue

            if name in entity_aliases:
                name = entity_aliases[name]

            if name not in normalized_entities:

                normalized_entities[name] = {
                    "entity_text": name,
                    "entity_type": row["entity_type"],
                    "mentions": int(row["mentions"])
                }

            else:

                normalized_entities[name]["mentions"] += int(
                    row["mentions"]
                )

        normalized_entities_list = sorted(
            normalized_entities.values(),
            key=lambda x: x["mentions"],
            reverse=True
        )

        top_entities = [
            entity["entity_text"]
            for entity in normalized_entities_list[:5]
        ]


        entity_profiles = []
        async with request.app.state.pg_pool.acquire() as conn:
            for entity_name in top_entities:
                row = await conn.fetchrow(
            """
            SELECT
                entity_text,
                entity_type,
                mention_frequency,
                risk_trend,
                associated_events,
                associated_relationships,
                    CARDINALITY(associated_events) AS event_count,
    CARDINALITY(associated_relationships) AS relationship_count,
                last_seen
            FROM entity_profiles
            WHERE LOWER(entity_text) = LOWER($1)
            """,
            entity_name
        ) 
                print("FOUND:", row)

                if row:
                    entity_profiles.append(
                    dict(row))
                    print("ENTITY PROFILE COUNT:", len(entity_profiles)
            )
        # -----------------------------
        # Threat Indicators
        # -----------------------------

        military = 0
        economic = 0
        diplomatic = 0

        for article in articles:

            topic = str(
                article.get("topic", "")
            ).lower()

            if topic in [
                "war",
                "military",
                "conflict"
            ]:
                military += 1

            elif topic in [
                "economy",
                "energy"
            ]:
                economic += 1

            else:
                diplomatic += 1

        # -----------------------------
        # Dynamic Assessment
        # -----------------------------

        assessment = []

        if threat_level in ["high", "critical"]:
            assessment.append(
                "Multiple high-risk reports indicate elevated escalation potential."
            )

        if len(relationships) > 10:
            assessment.append(
                "Dense actor interactions detected across reporting."
            )

        if len(related_events) > 0:
            assessment.append(
                f"{len(related_events)} linked geopolitical events identified."
            )

        if len(top_entities) > 0:
            assessment.append(
                f"Primary actors include {', '.join(top_entities[:3])}."
            )

        assessment_text = " ".join(assessment)

                # -----------------------------
                # Relationship Normalization
                # -----------------------------

        relationship_blacklist = {
                    "AI Generated Image",
                    "Brink of War"
                }

        normalized_relationships = []

        for row in relationships:

                    relationship = dict(row)

                    relationship["source_entity"] = entity_aliases.get(
                        relationship["source_entity"],
                        relationship["source_entity"]
                    )

                    relationship["target_entity"] = entity_aliases.get(
                        relationship["target_entity"],
                        relationship["target_entity"]
                    )

                    if (
                        relationship["source_entity"] in relationship_blacklist
                        or
                        relationship["target_entity"] in relationship_blacklist
                    ):
                        continue

                    normalized_relationships.append(
                        relationship
                    )
        # -----------------------------
        # Summary
        # -----------------------------

        summary = f"""
Retrieved {len(articles)} intelligence reports.

Threat Level: {threat_level.upper()}

Military Signals:
{military}

Economic Signals:
{economic}

Diplomatic Signals:
{diplomatic}

Key Actors:
{", ".join(top_entities) if top_entities else "No major actors detected"}

Relationships Identified:
{len(relationships)}

Related Events:
{len(related_events)}

Assessment:
{assessment_text}
""".strip()
        # -----------------------------
        # Response
        # -----------------------------

        return {
            "question": query,
            "threat_level": threat_level,
            "summary": summary,
            "articles": articles,
            "entities": normalized_entities_list,
            "entity_profiles": entity_profiles,
            "threat_indicators": {
    "military": military,
    "economic": economic,
    "diplomatic": diplomatic
},
            "relationships": normalized_relationships,
            "events": [
                dict(row)
                for row in related_events
            ]
        }

    except Exception as e:

        print("COPILOT ERROR:", str(e))

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )