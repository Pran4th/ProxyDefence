import hashlib
import re
from collections import Counter

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)

STOPWORDS = {
    "the", "and", "for", "that", "with", "from", "this", "have", "will", "into", "amid", "their",
    "about", "after", "before", "while", "under", "over", "they", "them", "were", "been", "said",
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def build_full_text(article: dict) -> str:
    title = normalize_text(article.get("title", ""))
    content = normalize_text(article.get("content", ""))
    return f"{title}. {content}".strip()


def build_dedupe_key(article: dict, full_text: str) -> str:
    """Content-only key so wire-syndicated stories collapse to one row.

    Previously mixed in url/source, which defeats the point of dedup: the
    same AP/Reuters story gets republished verbatim (identical content_hash)
    under a different URL on every local affiliate site (e.g. wistv.com,
    live5news.com, weau.com all ran the same "US to impose 20% toll in
    Strait of Hormuz" piece) -- each got its own dedupe_key and its own
    processed_articles row, which then each fanned out into their own
    ArticleSignalIngestor signals, showing as the same headline repeated
    many times in the Command Center's live signal feed.
    """
    base = normalize_text(full_text[:500])
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def summarize_text(full_text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", full_text)
    clean_sentences = [s.strip() for s in sentences if len(s.strip()) > 30]
    if not clean_sentences:
        return full_text[:240]
    summary = " ".join(clean_sentences[:2])
    return summary[:360]


def extract_keywords(full_text: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z\-]{3,}", full_text.lower())
    filtered = [w for w in words if w not in STOPWORDS]
    return [w for w, _ in Counter(filtered).most_common(8)]
