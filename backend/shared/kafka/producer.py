"""Reusable JSON Kafka producer with delivery logging.

Every service that publishes to Kafka uses ``JsonProducer`` instead of
raw ``confluent_kafka.Producer``, ensuring consistent delivery callbacks,
serialization, and error handling.
"""

from confluent_kafka import Producer

from backend.shared.kafka import producer_config
from backend.shared.kafka.serialization import json_serializer
from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class JsonProducer:
    """Kafka producer that accepts Python dicts and handles serialization.

    Usage::

        producer = JsonProducer()
        producer.produce("my-topic", {"key": "value"})
        producer.flush()
    """

    def __init__(self, config_override: dict | None = None):
        cfg = producer_config(**(config_override or {}))
        self._producer = Producer(cfg)

    def produce(
        self,
        topic: str,
        value: dict,
        key: str | None = None,
        on_delivery=None,
    ) -> None:
        """Publish a JSON-serializable dict to *topic*."""
        self._producer.produce(
            topic=topic,
            value=json_serializer(value),
            key=key,
            callback=on_delivery or self._delivery_callback,
        )
        self._producer.poll(0)

    def flush(self, timeout: float = 5.0) -> None:
        self._producer.flush(timeout=timeout)

    def poll(self, timeout: float = 0) -> None:
        self._producer.poll(timeout=timeout)

    @staticmethod
    def _delivery_callback(err, msg) -> None:
        if err:
            logger.error(
                "kafka_produce_failed",
                topic=msg.topic(),
                partition=msg.partition(),
                error=str(err),
            )
        else:
            logger.debug(
                "kafka_produce_ok",
                topic=msg.topic(),
                partition=msg.partition(),
                offset=msg.offset(),
            )
