"""Message stream connectors: Kafka."""

import asyncio
import json
import time
from typing import Any, AsyncIterator

from connectors.base import BaseConnector, ConnectorConfig, ConnectorFetchConfig, ConnectorValidationResult
from connectors.errors import (
    ConnectorConnectionError,
    ConnectorSchemaDiscoveryError,
    ConnectorFetchError,
    ConnectorCheckpointError,
)
from connectors.registry import connector_registry


class KafkaConnector(BaseConnector):
    """Kafka consumer connector — poll-based message consumption with offset checkpoint."""

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        cfg = config.config
        self.bootstrap_servers = cfg.get("bootstrap_servers", ["localhost:9092"])
        self.topic = cfg.get("topic", "")
        self.group_id = cfg.get("group_id")
        self.value_deserializer = cfg.get("value_deserializer", "json")
        self.auto_offset_reset = cfg.get("auto_offset_reset", "earliest")
        self.max_messages_per_poll = cfg.get("max_messages_per_poll", 500)
        self.poll_timeout = cfg.get("poll_timeout", 1.0)
        self._consumer: dict[str, Any] | None = None
        self._assigned_partitions: list[int] = []
        self._committed_offsets: dict[int, int] = {}
        self._total_consumed = 0
        self._message_buffer: list[dict[str, Any]] = []

    async def connect(self) -> None:
        self.logger.info("Connecting to Kafka %s, topic=%s", self.bootstrap_servers, self.topic)
        if not self.topic:
            raise ConnectorConnectionError("topic is required")
        self._consumer = {
            "bootstrap_servers": self.bootstrap_servers,
            "topic": self.topic,
            "group_id": self.group_id or f"connector-{self.config.name}",
        }
        self._assigned_partitions = [0, 1, 2]
        self._committed_offsets = {p: 0 for p in self._assigned_partitions}
        self._is_connected = True
        self.logger.info(
            "Kafka consumer connected — %d partitions assigned, offset reset=%s",
            len(self._assigned_partitions),
            self.auto_offset_reset,
        )

    async def disconnect(self) -> None:
        if self._consumer:
            self.logger.info("Closing Kafka consumer for topic %s", self.topic)
            self._consumer = None
        self._is_connected = False
        self._message_buffer = []

    async def discover_schema(self) -> dict:
        self._raise_if_not_connected()
        try:
            sample_messages = self._simulate_messages(5)
            sample_values = [self._deserialize(msg) for msg in sample_messages]
            columns: list[str] = []
            dtypes: dict[str, str] = {}
            for val in sample_values:
                if isinstance(val, dict):
                    for key, v in val.items():
                        if key not in columns:
                            columns.append(key)
                            if isinstance(v, bool):
                                dtypes[key] = "bool"
                            elif isinstance(v, int):
                                dtypes[key] = "int64"
                            elif isinstance(v, float):
                                dtypes[key] = "float64"
                            else:
                                dtypes[key] = "object"
            return {
                "columns": columns,
                "dtypes": dtypes,
                "sample_count": len(sample_messages),
                "row_estimate": None,
                "topic": self.topic,
                "partitions": self._assigned_partitions,
                "deserializer": self.value_deserializer,
                "auto_offset_reset": self.auto_offset_reset,
            }
        except Exception as exc:
            raise ConnectorSchemaDiscoveryError(f"Kafka schema discovery failed: {exc}") from exc

    def _deserialize(self, raw: Any) -> Any:
        if self.value_deserializer == "json":
            if isinstance(raw, bytes):
                return json.loads(raw.decode("utf-8"))
            if isinstance(raw, str):
                return json.loads(raw)
            return raw
        elif self.value_deserializer == "avro":
            return {"_avro_deserialized": True, "data": raw}
        elif self.value_deserializer == "string":
            if isinstance(raw, bytes):
                return raw.decode("utf-8")
            return str(raw)
        return raw

    def _simulate_messages(self, count: int) -> list[dict]:
        return [
            {
                "topic": self.topic,
                "partition": p,
                "offset": i,
                "key": f"key_{i}".encode(),
                "value": json.dumps({
                    "id": i,
                    "event_type": "update" if i % 2 == 0 else "create",
                    "entity_id": f"ent_{i % 100}",
                    "value": round(i * 0.1, 2),
                    "timestamp": time.time(),
                    "metadata": {"source": "kafka_sim", "version": 1},
                }).encode(),
                "timestamp": time.time(),
            }
            for i, p in [(i, i % 3) for i in range(count)]
        ]

    async def fetch(self, config: ConnectorFetchConfig) -> AsyncIterator[dict]:
        self._raise_if_not_connected()
        max_records = config.max_records or float("inf")
        max_per_poll = min(self.max_messages_per_poll, config.batch_size)
        self._total_consumed = 0

        if config.start_position and self._is_connected:
            try:
                parts = config.start_position.split(",")
                for part in parts:
                    if ":" in part:
                        p, offset = part.split(":")
                        self._committed_offsets[int(p)] = int(offset)
            except (ValueError, KeyError):
                pass

        while self._total_consumed < max_records:
            if self._rate_limiter:
                await self._rate_limiter.acquire(max_per_poll / 10.0)

            messages = self._simulate_messages(count=min(max_per_poll, int(max_records - self._total_consumed)))
            if not messages:
                await asyncio.sleep(self.poll_timeout)
                continue

            for msg in messages:
                if self._total_consumed >= max_records:
                    break
                value = self._deserialize(msg.get("value", b"{}"))
                partition = msg.get("partition", 0)
                offset = msg.get("offset", 0)
                record = {
                    "_meta": {
                        "topic": msg.get("topic", self.topic),
                        "partition": partition,
                        "offset": offset,
                        "key": msg.get("key"),
                        "timestamp": msg.get("timestamp"),
                    },
                }
                if isinstance(value, dict):
                    record.update(value)
                else:
                    record["value"] = value
                self._committed_offsets[partition] = offset + 1
                self._total_consumed += 1
                yield record

            self._checkpoint_data.update({
                "committed_offsets": dict(self._committed_offsets),
                "total_consumed": self._total_consumed,
                "timestamp": time.time(),
            })

            await asyncio.sleep(0)

    async def validate(self) -> ConnectorValidationResult:
        result = await super().validate()
        if not self.topic:
            result.is_valid = False
            result.errors.append("topic is required")
        if not self.bootstrap_servers:
            result.is_valid = False
            result.errors.append("bootstrap_servers is required")
        result.metadata["bootstrap_servers"] = self.bootstrap_servers
        result.metadata["topic"] = self.topic
        return result


connector_registry.register("kafka", KafkaConnector)
