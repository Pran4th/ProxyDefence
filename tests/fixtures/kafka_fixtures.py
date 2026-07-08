import json


def raw_article_message(topic: str = "raw_articles") -> dict:
    return {
        "topic": topic,
        "value": json.dumps({
            "title": "Kafka Pipeline Test Article",
            "content": "Article generated for Kafka pipeline integration test.",
            "source": "PipelineTest",
            "url": "https://example.com/pipeline-test",
        }).encode("utf-8"),
    }


def processed_article_message(topic: str = "processed_articles") -> dict:
    return {
        "topic": topic,
        "value": json.dumps({
            "title": "Processed Kafka Test Article",
            "content": "Article processed by ML service in Kafka pipeline.",
            "source": "PipelineTest",
            "url": "https://example.com/processed-pipeline-test",
            "sentiment": "negative",
            "confidence": 0.88,
            "threat_score": 7.5,
            "risk_level": "high",
            "topic": "cyber warfare",
            "ml_processed": True,
            "entities": [
                {"text": "Iran", "type": "GPE", "confidence": 0.98},
                {"text": "Israel", "type": "GPE", "confidence": 0.97},
            ],
        }).encode("utf-8"),
    }


def malformed_message(topic: str = "raw_articles") -> dict:
    return {
        "topic": topic,
        "value": b"not valid json",
    }
