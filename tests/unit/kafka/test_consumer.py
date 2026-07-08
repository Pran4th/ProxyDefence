"""Unit tests for backend.shared.kafka.consumer."""

from unittest.mock import MagicMock, patch

import pytest


class TestConsumerRunner:
    @patch("backend.shared.kafka.consumer.Consumer")
    def test_init_subscribes_to_topic(self, mock_consumer_cls, monkeypatch):
        monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "test-kafka:9092")

        import importlib
        from backend.shared import kafka
        importlib.reload(kafka)

        from backend.shared.kafka.consumer import ConsumerRunner

        handler = MagicMock()
        runner = ConsumerRunner("test-group", "test-topic", handler)

        mock_consumer_cls.assert_called_once()
        runner._consumer.subscribe.assert_called_once_with(["test-topic"])

    @patch("backend.shared.kafka.consumer.Consumer")
    def test_stop_sets_running_false(self, mock_consumer_cls, monkeypatch):
        monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "test-kafka:9092")

        import importlib
        from backend.shared import kafka
        importlib.reload(kafka)

        from backend.shared.kafka.consumer import ConsumerRunner

        handler = MagicMock()
        runner = ConsumerRunner("test-group", "test-topic", handler)
        assert runner.running is True

        runner.stop()
        assert runner.running is False

    @patch("backend.shared.kafka.consumer.Consumer")
    def test_properties(self, mock_consumer_cls, monkeypatch):
        monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "test-kafka:9092")

        import importlib
        from backend.shared import kafka
        importlib.reload(kafka)

        from backend.shared.kafka.consumer import ConsumerRunner

        handler = MagicMock()
        runner = ConsumerRunner("test-group", "test-topic", handler)
        assert runner.running is True
        assert runner.consumer is runner._consumer
