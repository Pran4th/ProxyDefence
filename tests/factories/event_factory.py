import uuid
from datetime import datetime, timezone


def build_event(**overrides) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    event = {
        "title": f"Test Event {uuid.uuid4().hex[:8]}",
        "description": "Test event description.",
        "event_type": "cyber_attack",
        "severity": "medium",
        "status": "active",
        "confidence": 0.80,
        "start_date": now,
        "source_entity": "TestSource",
        "target_entity": "TestTarget",
    }
    event.update(overrides)
    return event
