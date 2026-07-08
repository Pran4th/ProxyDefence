import uuid
from datetime import datetime, timezone


def build_case(**overrides) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    case = {
        "title": f"Test Case {uuid.uuid4().hex[:8]}",
        "description": "Test case description.",
        "status": "open",
        "priority": "medium",
        "assigned_to": None,
    }
    case.update(overrides)
    return case
