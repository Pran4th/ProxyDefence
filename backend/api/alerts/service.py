from typing import Any

from backend.api.alerts.repository import AlertRepository


class AlertService:
    def __init__(self, repository: AlertRepository) -> None:
        self.repository = repository

    async def list_alerts(self, status: str | None, limit: int, offset: int) -> list[dict[str, Any]]:
        return await self.repository.list_alerts(status, limit, offset)

    async def get_alert(self, alert_id: int) -> dict[str, Any] | None:
        return await self.repository.get_alert(alert_id)

    async def update_alert_status(self, alert_id: int, status: str) -> dict[str, Any] | None:
        return await self.repository.update_alert_status(alert_id, status)

    async def generate_alerts(self) -> dict[str, int]:
        return await self.repository.generate_alerts()
