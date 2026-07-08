from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


@dataclass
class ExecutionStage:
    name: str
    stage_type: str
    status: StageStatus = StageStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: float | None = None
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    config: dict = field(default_factory=dict)
    error: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class StageResult:
    stage_name: str
    stage_type: str
    status: StageStatus
    started_at: datetime
    completed_at: datetime
    duration_ms: float
    metrics: dict = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    output_data: dict = field(default_factory=dict)
    error: str | None = None
    metadata: dict = field(default_factory=dict)
