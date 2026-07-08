import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.shared.logging_config import get_logger
from config import ARTIFACT_DIR, DEFAULT_RANDOM_SEED
from db import get_pool

logger = get_logger(__name__)


class ExperimentManager:
    def __init__(self):
        self._current_run: dict[str, Any] | None = None

    async def create_experiment(self, name: str, experiment_type: str,
                                 description: str | None = None,
                                 author: str | None = None,
                                 random_seed: int | None = None,
                                 tags: list[str] | None = None,
                                 metadata: dict | None = None) -> dict[str, Any]:
        pool = await get_pool()
        git_commit = self._get_git_commit()
        row = await pool.fetchrow(
            "INSERT INTO ml.experiments (name, description, experiment_type, author, "
            "git_commit, random_seed, tags, metadata) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING *",
            name, description, experiment_type,
            author or "system", git_commit,
            random_seed or DEFAULT_RANDOM_SEED,
            tags or [], metadata or {},
        )
        logger.info("experiment created", name=name, type=experiment_type)
        return dict(row)

    async def start_run(self, experiment_uuid: str, run_name: str,
                         config: dict | None = None,
                         random_seed: int | None = None) -> dict[str, Any]:
        pool = await get_pool()
        max_run = await pool.fetchval(
            "SELECT MAX(run_number) FROM ml.experiment_runs WHERE experiment_uuid = $1",
            experiment_uuid,
        )
        run_number = (max_run or 0) + 1
        git_commit = self._get_git_commit()

        row = await pool.fetchrow(
            "INSERT INTO ml.experiment_runs (experiment_uuid, run_name, run_number, status, "
            "config, git_commit, random_seed, start_time) "
            "VALUES ($1, $2, $3, 'running', $4, $5, $6, $7) RETURNING *",
            experiment_uuid, run_name, run_number,
            json.dumps(config or {}), git_commit,
            random_seed or DEFAULT_RANDOM_SEED, datetime.now(timezone.utc),
        )
        self._current_run = dict(row)
        logger.info("experiment run started", experiment=experiment_uuid, run=run_number, name=run_name)
        return self._current_run

    async def finish_run(self, run_uuid: str, status: str = "completed",
                          metrics: dict | None = None,
                          params: dict | None = None,
                          model_version_uuid: str | None = None,
                          error_message: str | None = None) -> dict[str, Any]:
        pool = await get_pool()
        now = datetime.now(timezone.utc)
        row = await pool.fetchrow(
            "UPDATE ml.experiment_runs SET status = $2, metrics = $3, params = $4, "
            "model_version_uuid = $5, error_message = $6, end_time = $7, "
            "duration_seconds = EXTRACT(EPOCH FROM ($7 - start_time)) "
            "WHERE uuid = $1 RETURNING *",
            run_uuid, status, json.dumps(metrics or {}),
            json.dumps(params or {}), model_version_uuid,
            error_message, now,
        )
        self._current_run = None
        logger.info("experiment run finished", run=run_uuid, status=status)
        return dict(row)

    async def get_experiment(self, uuid_or_name: str) -> dict[str, Any] | None:
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT * FROM ml.experiments WHERE uuid = $1 OR name = $1", uuid_or_name,
        )
        return dict(row) if row else None

    async def list_experiments(self, experiment_type: str | None = None,
                                status: str | None = None,
                                limit: int = 100, offset: int = 0) -> tuple[list[dict[str, Any]], int]:
        pool = await get_pool()
        conditions: list[str] = []
        params: list[Any] = []
        if experiment_type:
            conditions.append(f"experiment_type = ${len(params) + 1}")
            params.append(experiment_type)
        if status:
            conditions.append(f"status = ${len(params) + 1}")
            params.append(status)
        where = " AND ".join(conditions) if conditions else "TRUE"
        total = await pool.fetchval(f"SELECT COUNT(*) FROM ml.experiments WHERE {where}", *params)
        params.append(limit)
        params.append(offset)
        rows = await pool.fetch(
            f"SELECT * FROM ml.experiments WHERE {where} ORDER BY created_at DESC LIMIT ${len(params) - 1} OFFSET ${len(params)}",
            *params,
        )
        return [dict(r) for r in rows], total or 0

    async def get_runs(self, experiment_uuid: str, limit: int = 100,
                        offset: int = 0) -> tuple[list[dict[str, Any]], int]:
        pool = await get_pool()
        total = await pool.fetchval(
            "SELECT COUNT(*) FROM ml.experiment_runs WHERE experiment_uuid = $1", experiment_uuid,
        )
        rows = await pool.fetch(
            "SELECT * FROM ml.experiment_runs WHERE experiment_uuid = $1 "
            "ORDER BY run_number DESC LIMIT $2 OFFSET $3",
            experiment_uuid, limit, offset,
        )
        return [dict(r) for r in rows], total or 0

    async def get_run(self, run_uuid: str) -> dict[str, Any] | None:
        pool = await get_pool()
        row = await pool.fetchrow("SELECT * FROM ml.experiment_runs WHERE uuid = $1", run_uuid)
        return dict(row) if row else None

    async def compare_runs(self, run_uuids: list[str]) -> list[dict[str, Any]]:
        results = []
        for ruid in run_uuids:
            run = await self.get_run(ruid)
            if run:
                experiment = await self.get_experiment(run["experiment_uuid"])
                results.append({
                    "run_uuid": run["uuid"],
                    "run_name": run["run_name"],
                    "run_number": run["run_number"],
                    "experiment_name": experiment["name"] if experiment else None,
                    "status": run["status"],
                    "metrics": run["metrics"],
                    "params": run["params"],
                    "duration_seconds": run["duration_seconds"],
                    "created_at": run["created_at"],
                })
        return results

    def _get_git_commit(self) -> str | None:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, cwd=os.getcwd(),
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception:
            return None
