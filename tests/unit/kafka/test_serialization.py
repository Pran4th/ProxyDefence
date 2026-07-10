"""Unit tests for backend.shared.kafka.serialization."""

import json

import pytest


class TestJsonSerializer:
    def test_serializes_dict_to_utf8_bytes(self):
        from backend.shared.kafka.serialization import json_serializer
        data = {"key": "value", "num": 42}
        result = json_serializer(data)
        assert isinstance(result, bytes)
        assert result.decode("utf-8") == json.dumps(data)

    def test_handles_nested_objects(self):
        from backend.shared.kafka.serialization import json_serializer
        data = {"outer": {"inner": [1, 2, 3]}}
        result = json_serializer(data)
        assert isinstance(result, bytes)
        decoded = json.loads(result)
        assert decoded["outer"]["inner"] == [1, 2, 3]

    def test_handles_datetime_with_default_str(self):
        from datetime import datetime
        from backend.shared.kafka.serialization import json_serializer
        data = {"timestamp": datetime(2026, 7, 4, 12, 0, 0)}
        result = json_serializer(data)
        assert isinstance(result, bytes)
        decoded = json.loads(result)
        assert "2026" in decoded["timestamp"]


class TestJsonDeserializer:
    def test_deserializes_bytes_to_dict(self):
        from backend.shared.kafka.serialization import json_deserializer
        data = json.dumps({"key": "value"}).encode("utf-8")
        result = json_deserializer(data)
        assert result == {"key": "value"}

    def test_handles_empty_object(self):
        from backend.shared.kafka.serialization import json_deserializer
        data = b"{}"
        result = json_deserializer(data)
        assert result == {}

    def test_handles_arrays(self):
        from backend.shared.kafka.serialization import json_deserializer
        data = json.dumps([1, 2, 3]).encode("utf-8")
        result = json_deserializer(data)
        assert result == [1, 2, 3]

    def test_raises_on_invalid_json(self):
        from backend.shared.kafka.serialization import json_deserializer
        import json
        with pytest.raises(json.JSONDecodeError):
            json_deserializer(b"not valid json")
