import uuid
from datetime import datetime, timezone


def build_alert(**overrides) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    alert = {
        "title": f"Test Alert {uuid.uuid4().hex[:8]}",
        "message": "Test alert message.",
        "severity": "medium",
        "alert_type": "threat",
        "source": "TestSource",
        "is_read": False,
    }
    alert.update(overrides)
    return alert
