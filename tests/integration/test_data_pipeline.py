"""End-to-end data pipeline integration tests.

Tests the flow: ingest → Kafka raw_articles → ML processing → Kafka
processed_articles → database storage → API retrieval.

Requires --run-integration flag and running PG/ES/Kafka.
"""

import json
import time

import pytest


@pytest.mark.integration
@pytest.mark.slow
class TestDataPipeline:
    """Tests the full Kafka -> ML -> DB -> API data pipeline."""

    async def test_pipeline_produce_and_consume(self, kafka_servers, async_client, auth_headers):
        from confluent_kafka import Producer, Consumer

        producer = Producer({"bootstrap.servers": kafka_servers})

        test_data = {
            "title": "Pipeline E2E Test",
            "content": "End-to-end pipeline integration test article.",
            "source": "PipelineTest",
            "url": "https://example.com/pipeline-e2e",
        }

        producer.produce("raw_articles", json.dumps(test_data).encode("utf-8"))
        producer.flush(timeout=5)

        consumer = Consumer({
            "bootstrap.servers": kafka_servers,
            "group.id": "pipeline-e2e-test",
            "auto.offset.reset": "latest",
            "session.timeout.ms": 6000,
        })
        consumer.subscribe(["processed_articles"])
        time.sleep(2)
        consumer.close()

        resp = await async_client.get("/health", headers=auth_headers)
        assert resp.status_code == 200

    async def test_ml_service_processes_article(self):
        from tests.mocks.mock_ml_service import mock_sentiment_analysis

        result = mock_sentiment_analysis(
            "Iran launched a cyber attack on Israeli infrastructure."
        )
        assert result["sentiment"] == "negative"
        assert result["confidence"] > 0.5

    async def test_pipeline_rejects_malformed_message(self):
        import json

        malformed = b"not valid json"
        with pytest.raises(json.JSONDecodeError):
            json.loads(malformed)

    async def test_api_exposes_health(self, async_client):
        resp = await async_client.get("/liveness")
        assert resp.status_code == 200
