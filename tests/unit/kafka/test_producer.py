"""Unit tests for backend.shared.kafka.producer."""

from unittest.mock import patch

import pytest


class TestJsonProducer:
    @patch("backend.shared.kafka.producer.Producer")
    def test_init_creates_producer(self, mock_producer_cls, monkeypatch):
        monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "test-kafka:9092")
        import importlib
        from backend.shared import kafka
        importlib.reload(kafka)

        from backend.shared.kafka.producer import JsonProducer
        producer = JsonProducer()
        assert producer._producer is not None
        mock_producer_cls.assert_called_once()

    @patch("backend.shared.kafka.producer.Producer")
    def test_produce_calls_internal_producer(self, mock_producer_cls, monkeypatch):
        mock_producer_instance = mock_producer_cls.return_value
        monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "test-kafka:9092")

        import importlib
        from backend.shared import kafka
        importlib.reload(kafka)

        from backend.shared.kafka.producer import JsonProducer
        producer = JsonProducer()
        producer.produce("test-topic", {"key": "value"})

        mock_producer_instance.produce.assert_called_once()
        args, kwargs = mock_producer_instance.produce.call_args
        assert kwargs["topic"] == "test-topic"
        assert isinstance(kwargs["value"], bytes)
        assert kwargs["callback"] is not None

    @patch("backend.shared.kafka.producer.Producer")
    def test_flush_delegates(self, mock_producer_cls, monkeypatch):
        mock_producer_instance = mock_producer_cls.return_value
        monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "test-kafka:9092")

        import importlib
        from backend.shared import kafka
        importlib.reload(kafka)

        from backend.shared.kafka.producer import JsonProducer
        producer = JsonProducer()
        producer.flush(timeout=2.0)

        mock_producer_instance.flush.assert_called_once_with(timeout=2.0)
