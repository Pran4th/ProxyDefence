"""Unit tests for backend.shared.kafka.health."""

from unittest.mock import patch


class TestCheckKafkaConnection:
    # check_kafka_connection() imports Producer lazily from confluent_kafka
    # inside the function body (not at module level), so the patch target
    # must be the real source module, not backend.shared.kafka.health.
    @patch("confluent_kafka.Producer")
    def test_returns_healthy_when_reachable(self, mock_producer_cls, monkeypatch):
        monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "test-kafka:9092")

        import importlib
        from backend.shared import kafka
        importlib.reload(kafka)

        from backend.shared.kafka.health import check_kafka_connection
        result = check_kafka_connection("test-kafka:9092")
        assert result["status"] == "healthy"
        assert result["kafka_brokers"] == "test-kafka:9092"

    @patch("confluent_kafka.Producer", side_effect=Exception("Connection refused"))
    def test_returns_unhealthy_on_error(self, mock_producer_cls, monkeypatch):
        monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "test-kafka:9092")

        import importlib
        from backend.shared import kafka
        importlib.reload(kafka)

        from backend.shared.kafka.health import check_kafka_connection
        result = check_kafka_connection("test-kafka:9092")
        assert result["status"] == "unhealthy"
        assert "error" in result
