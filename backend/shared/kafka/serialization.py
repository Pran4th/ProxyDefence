"""JSON serialization for Kafka messages — the only (de)serializers used."""

import json


def json_serializer(data: dict) -> bytes:
    """Serialize a dict to UTF-8 JSON bytes sent to Kafka."""
    return json.dumps(data, default=str).encode("utf-8")


def json_deserializer(data: bytes) -> dict:
    """Deserialize UTF-8 JSON bytes from Kafka into a dict."""
    return json.loads(data.decode("utf-8"))
