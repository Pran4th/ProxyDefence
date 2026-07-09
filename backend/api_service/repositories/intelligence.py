"""Audit logging repository. Writes to the `audit_logs` table defined in
infra/sql/init.sql (user_id, action, resource, metadata, created_at)."""
import json
from typing import Any


class IntelligenceRepository:
    def __init__(self, pool):
        self.pool = pool

    async def audit(
        self,
        user_id: int | None,
        action: str,
        resource: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.pool.execute(
            "INSERT INTO audit_logs (user_id, action, resource, metadata) VALUES ($1, $2, $3, $4::jsonb)",
            user_id, action, resource, json.dumps(metadata or {}),
        )
