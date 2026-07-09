"""Publishes real-shaped test articles to raw_articles for the Phase 3
parallel-run validation (compares ml-service's output vs ml-platform's).

Run with KAFKA_BOOTSTRAP_SERVERS set:
    .venv/Scripts/python.exe scripts/publish_test_articles.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.shared.kafka import JsonProducer  # noqa: E402

ARTICLES = [
    {
        "title": "Iran missile strike hits Hormuz tanker",
        "content": "Officials reported an airstrike near the Strait of Hormuz targeting an oil tanker, raising fears of military escalation and disruption to global crude supply.",
        "source": "test-wire",
        "url": "http://test.example/parallel-run-1",
    },
    {
        "title": "Central bank raises interest rates amid inflation concerns",
        "content": "The central bank announced a rate hike today as trade tariff disputes and inflation continue to pressure the domestic economy.",
        "source": "test-wire",
        "url": "http://test.example/parallel-run-2",
    },
    {
        "title": "Local bakery wins award for best croissant",
        "content": "A small bakery in town has been recognized for its excellent pastries at a regional food festival this weekend.",
        "source": "test-wire",
        "url": "http://test.example/parallel-run-3",
    },
    {
        "title": "Diplomatic summit yields ceasefire agreement",
        "content": "Leaders from both nations met for peace talks and announced a ceasefire agreement following weeks of negotiation.",
        "source": "test-wire",
        "url": "http://test.example/parallel-run-4",
    },
]


def main() -> None:
    producer = JsonProducer()
    for article in ARTICLES:
        producer.produce("raw_articles", article)
        print(f"published: {article['title']}")
    producer.flush()
    print(f"\npublished {len(ARTICLES)} articles to raw_articles")


if __name__ == "__main__":
    main()
