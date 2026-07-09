from backend.shared.entity_normalization import IGNORE_ENTITIES
from backend.shared.entity_normalization import normalize_entity as normalize_name
from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


def normalize_entity_name(name: str) -> str:
    return normalize_name(name)


def extract_entities(full_text: str) -> list[dict]:
    from ml_core.models import get_ner_pipeline, get_nlp

    ner = get_ner_pipeline()
    nlp = get_nlp()

    if ner is not None:
        try:
            ner_results = ner(full_text[:1200])
            relevant = [
                {"text": e["word"], "type": e["entity_group"], "score": float(e["score"])}
                for e in ner_results
                if e["entity_group"] in {"LOC", "ORG", "PER", "MISC"} and e["score"] > 0.70
            ]
            unique, seen = [], set()
            for e in relevant:
                e["text"] = normalize_entity_name(e["text"])
                key = e["text"].lower()
                if key in IGNORE_ENTITIES or not key or key in seen:
                    continue
                unique.append(e)
                seen.add(key)
            return unique[:12]
        except Exception as exc:
            logger.warning("ner_transformers_failed", error=str(exc))

    if nlp is not None:
        try:
            doc = nlp(full_text)
            entities = []
            for ent in doc.ents:
                if ent.label_ in {"PERSON", "ORG", "GPE"}:
                    name = normalize_entity_name(ent.text)
                    if name.lower() in IGNORE_ENTITIES:
                        continue
                    entities.append({"text": ent.text, "type": ent.label_, "score": 0.90})
            unique, seen = [], set()
            for e in entities:
                key = e["text"].strip().lower()
                if key and key not in seen:
                    unique.append(e)
                    seen.add(key)
            return unique[:12]
        except Exception as exc:
            logger.warning("ner_spacy_failed", error=str(exc))

    return []
