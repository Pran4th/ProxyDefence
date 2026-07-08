"""Mock Kafka producer, consumer, and admin client for unit tests."""

from collections.abc import Callable
from unittest.mock import MagicMock


class MockProducer:
    """In-memory mock for JsonProducer that records produced messages."""

    def __init__(self, config_override: dict | None = None):
        self.config_override = config_override or {}
        self.messages: list[dict] = []
        self.flushed = False

    def produce(self, topic: str, value: dict, key: str | None = None, on_delivery=None):
        self.messages.append({"topic": topic, "value": value, "key": key})
        if on_delivery:
            on_delivery(None, MagicMock(topic=lambda: topic, partition=lambda: 0, offset=lambda: len(self.messages)))

    def flush(self, timeout: float = 5.0):
        self.flushed = True

    def poll(self, timeout: float = 0):
        return None


class MockConsumer:
    """In-memory mock for ConsumerRunner that returns pre-built messages."""

    def __init__(self, messages: list[dict] | None = None):
        self.messages = messages or []
        self._index = 0
        self._running = True

    def poll(self, timeout: float = 1.0):
        if self._index >= len(self.messages):
            return None
        msg_data = self.messages[self._index]
        self._index += 1
        msg = MagicMock()
        msg.value.return_value = msg_data.get("value", b"{}")
        msg.error.return_value = None
        msg.topic.return_value = msg_data.get("topic", "test-topic")
        msg.partition.return_value = 0
        msg.offset.return_value = self._index
        msg.key.return_value = msg_data.get("key")
        return msg

    def subscribe(self, topics: list[str]):
        pass

    def commit(self):
        pass

    def close(self):
        self._running = False


class MockAdminClient:
    """Mock confluent_kafka.admin.AdminClient for health checks."""

    def __init__(self, conf: dict | None = None):
        self.conf = conf or {}

    def list_topics(self, timeout: float = 5.0):
        metadata = MagicMock()
        metadata.topics = {
            "raw_articles": MagicMock(),
            "processed_articles": MagicMock(),
        }
        return metadata

    def create_topics(self, new_topics: list):
        return {}

    def list_consumer_groups(self, requested_group_names=None, timeout=5.0):
        from unittest.mock import MagicMock
        from concurrent.futures import Future
        result = {}
        for group in (requested_group_names or []):
            f = Future()
            mock_result = MagicMock()
            mock_result.group_name = group
            mock_result.state = "STABLE"
            mock_result.members = []
            f.set_result(mock_result)
            result[group] = f
        return result

    def list_consumer_group_offsets(self, group_name, timeout=5.0):
        return {}


def make_delivery_callback_ok():
    def callback(err, msg):
        pass
    return callback


def make_delivery_callback_error(error_msg: str = "Test error"):
    def callback(err, msg):
        pass
    return callback
