from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.shared.logging_config import get_logger

from ingestion.errors import IngestionScheduleError

logger = get_logger(__name__)


@dataclass
class ScheduleDefinition:
    name: str
    pipeline_name: str
    cron_expression: str
    config: dict | None = None
    is_active: bool = True
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None


class IngestionScheduler:
    def __init__(self):
        self._schedules: dict[str, ScheduleDefinition] = {}
        self._schedule_config: dict[str, Any] = {}

    async def register_schedule(
        self, definition: ScheduleDefinition, pool=None
    ) -> str:
        if definition.name in self._schedules:
            raise IngestionScheduleError(
                f"Schedule '{definition.name}' is already registered"
            )

        if pool is not None:
            try:
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        """
                        INSERT INTO ml.ingestion_pipelines
                            (name, connector_name, pipeline_type, schedule_cron,
                             is_active, metadata)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT (name, version) DO UPDATE SET
                            schedule_cron = EXCLUDED.schedule_cron,
                            is_active = EXCLUDED.is_active,
                            metadata = EXCLUDED.metadata,
                            updated_at = NOW()
                        RETURNING name
                        """,
                        definition.name,
                        definition.pipeline_name,
                        "ingestion",
                        definition.cron_expression,
                        definition.is_active,
                        definition.config or {},
                    )
                    logger.info("registered schedule '%s' in database", definition.name)
                    return row["name"]
            except Exception as e:
                raise IngestionScheduleError(
                    f"Failed to register schedule '{definition.name}' in database: {e}"
                ) from e
        else:
            self._schedules[definition.name] = definition
            logger.info("registered schedule '%s' in memory", definition.name)
            return definition.name

    async def list_schedules(self, pool=None) -> list[dict]:
        if pool is not None:
            try:
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        """
                        SELECT name, connector_name, schedule_cron,
                               is_active, metadata, created_at, updated_at
                        FROM ml.ingestion_pipelines
                        ORDER BY name
                        """
                    )
                    return [dict(row) for row in rows]
            except Exception as e:
                raise IngestionScheduleError(f"Failed to list schedules: {e}") from e
        else:
            return [
                {
                    "name": s.name,
                    "pipeline_name": s.pipeline_name,
                    "cron_expression": s.cron_expression,
                    "config": s.config or {},
                    "is_active": s.is_active,
                    "last_run_at": s.last_run_at,
                    "next_run_at": s.next_run_at,
                }
                for s in self._schedules.values()
            ]

    async def pause_schedule(self, name: str, pool=None):
        if pool is not None:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        UPDATE ml.ingestion_pipelines
                        SET is_active = FALSE, updated_at = NOW()
                        WHERE name = $1
                        """,
                        name,
                    )
            except Exception as e:
                raise IngestionScheduleError(
                    f"Failed to pause schedule '{name}': {e}"
                ) from e
        elif name in self._schedules:
            self._schedules[name].is_active = False

    async def resume_schedule(self, name: str, pool=None):
        if pool is not None:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        UPDATE ml.ingestion_pipelines
                        SET is_active = TRUE, updated_at = NOW()
                        WHERE name = $1
                        """,
                        name,
                    )
            except Exception as e:
                raise IngestionScheduleError(
                    f"Failed to resume schedule '{name}': {e}"
                ) from e
        elif name in self._schedules:
            self._schedules[name].is_active = True

    async def delete_schedule(self, name: str, pool=None):
        if pool is not None:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        "DELETE FROM ml.ingestion_pipelines WHERE name = $1",
                        name,
                    )
            except Exception as e:
                raise IngestionScheduleError(
                    f"Failed to delete schedule '{name}': {e}"
                ) from e
        else:
            self._schedules.pop(name, None)

    async def get_due_schedules(self, pool=None) -> list[ScheduleDefinition]:
        due: list[ScheduleDefinition] = []
        now = datetime.now(timezone.utc)

        schedules = await self.list_schedules(pool)

        for sched_data in schedules:
            name = sched_data["name"]
            cron_expr = (
                sched_data.get("cron_expression")
                or sched_data.get("schedule_cron")
                or ""
            )
            is_active = sched_data.get("is_active", True)

            if not is_active or not cron_expr:
                continue

            try:
                next_run = self.next_cron_trigger(cron_expr)
                if next_run <= now + timedelta(seconds=60):
                    last_run = sched_data.get("last_run_at")
                    due.append(
                        ScheduleDefinition(
                            name=name,
                            pipeline_name=sched_data.get("connector_name", name),
                            cron_expression=cron_expr,
                            config=sched_data.get("config") or sched_data.get("metadata"),
                            is_active=is_active,
                            last_run_at=last_run,
                            next_run_at=next_run,
                        )
                    )
            except ValueError as e:
                logger.warning("invalid cron for schedule '%s': %s", name, e)

        return due

    async def get_next_run(
        self, cron_expression: str, after: datetime | None = None
    ) -> datetime:
        after = after or datetime.now(timezone.utc)
        result = self.next_cron_trigger(cron_expression, after=after)
        return result

    def next_cron_trigger(
        self, cron_expr: str, after: datetime | None = None
    ) -> datetime:
        fields = cron_expr.strip().split()
        if len(fields) != 5:
            raise IngestionScheduleError(
                f"Invalid cron expression: '{cron_expr}'. Expected 5 fields."
            )

        minute_set = self._parse_cron_field(fields[0], 0, 59)
        hour_set = self._parse_cron_field(fields[1], 0, 23)
        day_set = self._parse_cron_field(fields[2], 1, 31)
        month_set = self._parse_cron_field(fields[3], 1, 12)
        dow_set = self._parse_cron_field(fields[4], 0, 6)

        now = after or datetime.now(timezone.utc)
        current = now.replace(second=0, microsecond=0) + timedelta(minutes=1)

        max_iterations = 365 * 24 * 60
        for _ in range(max_iterations):
            cron_dow = (current.weekday() + 1) % 7

            month_match = current.month in month_set
            dom_match = current.day in day_set
            dow_match = cron_dow in dow_set

            day_match = dom_match or dow_match
            if fields[2] == "*" and fields[4] == "*":
                day_match = dom_match

            if (
                month_match
                and day_match
                and current.hour in hour_set
                and current.minute in minute_set
            ):
                return current

            current += timedelta(minutes=1)

        raise IngestionScheduleError(
            f"No matching time found within 365 days for cron: '{cron_expr}'"
        )

    def _parse_cron_field(self, field: str, min_val: int, max_val: int) -> set[int]:
        values: set[int] = set()

        for part in field.split(","):
            part = part.strip()
            if not part:
                continue

            step = 1
            if "/" in part:
                part, step_str = part.split("/", 1)
                step = int(step_str)

            if part == "*":
                values.update(range(min_val, max_val + 1, step))
            elif "-" in part:
                start_str, end_str = part.split("-", 1)
                start, end = int(start_str), int(end_str)
                values.update(range(start, end + 1, step))
            else:
                values.add(int(part))

        return values
