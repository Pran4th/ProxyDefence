"""ProxyDefence shared Kafka layer.

Every service produces or consumes Kafka messages through these building
blocks, guaranteeing consistent bootstrap servers, serialization, commit
strategy, and error handling across the entire pipeline.
"""

from backend.shared.settings import settings

KAFKA_BOOTSTRAP_SERVERS = settings.KAFKA_BOOTSTRAP_SERVERS


def producer_config(**overrides) -> dict:
    """Return a Kafka producer configuration dict."""
    config: dict = {"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS}
    config.update(overrides)
    return config


def consumer_config(group_id: str, **overrides) -> dict:
    """Return a Kafka consumer configuration dict for the given group."""
    config: dict = {
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "group.id": group_id,
        "auto.offset.reset": "earliest",
        "session.timeout.ms": 6000,
        "enable.auto.commit": False,
    }
    config.update(overrides)
    return config


from backend.shared.kafka.serialization import json_deserializer, json_serializer
from backend.shared.kafka.producer import JsonProducer
from backend.shared.kafka.consumer import ConsumerRunner, install_signal_handlers
from backend.shared.kafka.health import check_kafka_connection
from backend.shared.kafka.topics import TOPICS, ensure_topics

__all__ = [
    "KAFKA_BOOTSTRAP_SERVERS",
    "producer_config",
    "consumer_config",
    "json_serializer",
    "json_deserializer",
    "JsonProducer",
    "ConsumerRunner",
    "install_signal_handlers",
    "check_kafka_connection",
    "TOPICS",
    "ensure_topics",
]
