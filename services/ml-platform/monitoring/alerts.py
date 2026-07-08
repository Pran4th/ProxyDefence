from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class AlertRule:
    name: str
    metric: str
    operator: str
    threshold: float
    cooldown_seconds: int = 300
    channels: list[str] = field(default_factory=lambda: ["log"])

    def evaluate(self, value: float) -> bool:
        if self.operator == "gt":
            return value > self.threshold
        elif self.operator == "lt":
            return value < self.threshold
        elif self.operator == "gte":
            return value >= self.threshold
        elif self.operator == "lte":
            return value <= self.threshold
        elif self.operator == "eq":
            return value == self.threshold
        return False


@dataclass
class Alert:
    rule: AlertRule
    value: float
    model_name: str
    model_version: int
    timestamp: datetime
    message: str
    severity: str = "warning"


AlertHandler = Callable[[Alert], None]


def _log_handler(alert: Alert):
    logger.warning("ALERT [%s] %s: %.4f (threshold: %.4f, rule: %s)",
                   alert.severity.upper(), alert.message, alert.value,
                   alert.rule.threshold, alert.rule.name)


class AlertManager:
    def __init__(self):
        self._rules: list[AlertRule] = []
        self._handlers: list[AlertHandler] = [_log_handler]
        self._last_fired: dict[str, float] = {}

    def add_rule(self, rule: AlertRule):
        self._rules.append(rule)

    def add_handler(self, handler: AlertHandler):
        self._handlers.append(handler)

    def evaluate(self, metric_name: str, value: float,
                 model_name: str = "", model_version: int = 0) -> list[Alert]:
        fired: list[Alert] = []
        now = datetime.now(timezone.utc)
        now_ts = now.timestamp()

        for rule in self._rules:
            if rule.metric != metric_name:
                continue
            last_ts = self._last_fired.get(rule.name, 0)
            if now_ts - last_ts < rule.cooldown_seconds:
                continue
            if rule.evaluate(value):
                alert = Alert(
                    rule=rule, value=value,
                    model_name=model_name, model_version=model_version,
                    timestamp=now,
                    message=f"{rule.metric} = {value:.4f} {rule.operator} {rule.threshold}",
                    severity="critical" if abs(value - rule.threshold) / rule.threshold > 0.5 else "warning",
                )
                fired.append(alert)
                self._last_fired[rule.name] = now_ts
                for handler in self._handlers:
                    handler(alert)

        return fired


_alert_manager: AlertManager | None = None


def get_alert_manager() -> AlertManager:
    global _alert_manager
    if _alert_manager is None:
        am = AlertManager()
        am.add_rule(AlertRule("high_prediction_drift", "drift_score", "gt", 0.25))
        am.add_rule(AlertRule("critical_prediction_drift", "drift_score", "gt", 0.4))
        am.add_rule(AlertRule("low_confidence", "avg_confidence", "lt", 0.5))
        am.add_rule(AlertRule("high_latency", "avg_latency_ms", "gt", 1000))
        _alert_manager = am
    return _alert_manager
