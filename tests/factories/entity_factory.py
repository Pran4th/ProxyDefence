import uuid


def build_entity(**overrides) -> dict:
    entity = {
        "entity_text": f"Entity_{uuid.uuid4().hex[:6]}",
        "entity_type": "GPE",
        "confidence": 0.90,
    }
    entity.update(overrides)
    return entity


def build_entities_for_article(count: int = 3) -> list[dict]:
    types = ["GPE", "ORG", "PERSON", "LOC", "PRODUCT"]
    return [
        build_entity(entity_type=types[i % len(types)])
        for i in range(count)
    ]
