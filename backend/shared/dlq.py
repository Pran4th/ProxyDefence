import json
import time
from typing import Any

from backend.shared.kafka.producer import JsonProducer
from backend.shared.kafka.topics import TOPICS
from backend.shared.logging_config import get_logger

logger = get_logger(__name__)

TOPICS["dlq_articles"] = {
    "partitions": 1,
    "replication_factor": 1,
    "config": {
        "cleanup.policy": "delete",
        "retention.ms": "259200000",
    },
}


class DlqWriter:
    def __init__(self, topic: str = "dlq_articles", producer: JsonProducer | None = None) -> None:
        self.topic = topic
        self._producer = producer or JsonProducer()

    async def write(
        self,
        original_topic: str,
        message: dict[str, Any],
        error: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        dlq_payload = {
            "original_topic": original_topic,
            "original_message": message,
            "error": error,
            "metadata": metadata or {},
            "dlq_timestamp": time.time(),
        }

        self._producer.produce(
            topic=self.topic,
            value=dlq_payload,
        )
        self._producer.flush()

        logger.info(
            "dlq_written",
            original_topic=original_topic,
            dlq_topic=self.topic,
            error=error,
        )
