from itertools import combinations

from backend.shared.logging_config import get_logger
from ml_core.text import summarize_text

logger = get_logger(__name__)

RELATIONSHIP_KEYWORDS = {
    "attack": ["attack", "strike", "bomb", "target", "retaliation", "airstrike", "missile"],
    "alliance": ["alliance", "cooperation", "support", "backing", "joint", "partnership"],
    "sanction": ["sanction", "restriction", "embargo", "penalty"],
    "diplomacy": ["talks", "summit", "ceasefire", "agreement", "negotiation", "dialogue"],
}


def infer_relationship_type(full_text: str) -> str:
    text = full_text.lower()
    for rtype, keywords in RELATIONSHIP_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return rtype
    return "association"


def infer_relationships(entities: list[dict], full_text: str) -> list[dict]:
    actors = [e for e in entities if e["type"] in {"GPE", "ORG", "PERSON"}]
    if len(actors) < 2:
        return []

    rtype = infer_relationship_type(full_text)
    confidence = 0.80 if rtype != "association" else 0.55

    relationships = []
    for source, target in list(combinations(actors[:5], 2))[:6]:
        relationships.append({
            "source": source["text"],
            "target": target["text"],
            "type": rtype,
            "confidence": confidence,
            "context": summarize_text(full_text),
        })
    return relationships
