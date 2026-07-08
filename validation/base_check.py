import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    warning: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "message": self.message,
            "detail": self.detail,
            "duration_ms": round(self.duration_ms, 2),
            "warning": self.warning,
        }


class BaseCheck:
    name: str = ""
    description: str = ""
    dependencies: list[str] = []

    def __init__(self, config: Any):
        self.config = config

    def run(self) -> CheckResult:
        start = time.perf_counter()
        try:
            result = self._run()
            result.duration_ms = (time.perf_counter() - start) * 1000
            return result
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return CheckResult(
                name=self.name,
                passed=False,
                message=f"Check raised exception: {e}",
                duration_ms=duration,
            )

    def _run(self) -> CheckResult:
        raise NotImplementedError
