from datetime import datetime, timezone
from typing import Any

from backend.shared.logging_config import get_logger
from research.config import ResearchConfigLoader
from research.execution.stage import StageStatus
from research.execution.engine import ExecutionEngine, ExecutionResult
from research.execution.pipeline import ExecutionPipeline
from research.experiment import ExperimentManager

logger = get_logger(__name__)


class ExperimentRunner:
    def __init__(self, engine: ExecutionEngine | None = None, experiment_manager: ExperimentManager | None = None):
        self._engine = engine or ExecutionEngine()
        self._manager = experiment_manager or ExperimentManager()
        self._config_loader = ResearchConfigLoader()
        self._execution_to_experiment: dict[str, str] = {}

    async def run_experiment(self, config: dict | str, pool=None) -> str:
        if isinstance(config, str):
            config = self._config_loader.load(config)

        experiment_section = config.get("experiment", {})
        experiment = await self._manager.create_experiment(
            name=experiment_section.get("name", "unnamed_experiment"),
            experiment_type=experiment_section.get("type", "classification"),
            description=experiment_section.get("description"),
            author=experiment_section.get("author"),
            random_seed=experiment_section.get("random_seed"),
            tags=experiment_section.get("tags"),
        )
        experiment_uuid = experiment["uuid"]

        pipeline = ExecutionPipeline(config=config)
        pipeline.build_from_config(config)

        run = await self._manager.start_run(
            experiment_uuid=experiment_uuid,
            run_name=f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            config=config,
            random_seed=experiment_section.get("random_seed"),
        )
        run_uuid = run["uuid"]

        result = await self._engine.execute_pipeline(
            pipeline=pipeline,
            experiment_name=experiment_section.get("name", "unnamed_experiment"),
            context={"experiment_uuid": experiment_uuid, "run_uuid": run_uuid},
            pool=pool,
        )

        self._execution_to_experiment[result.execution_id] = experiment_uuid

        status_map = {
            StageStatus.COMPLETED: "completed",
            StageStatus.FAILED: "failed",
            StageStatus.CANCELLED: "cancelled",
        }
        run_status = status_map.get(result.status, "completed")
        error_message = result.error if result.status in (StageStatus.FAILED, StageStatus.CANCELLED) else None

        await self._manager.finish_run(
            run_uuid=run_uuid,
            status=run_status,
            metrics=result.context_summary,
            error_message=error_message,
        )

        logger.info(
            "experiment run completed: execution=%s experiment=%s status=%s",
            result.execution_id, experiment_uuid, run_status,
        )
        return result.execution_id

    async def cancel_experiment(self, execution_id: str) -> None:
        await self._engine.cancel_execution(execution_id)
        logger.info("experiment cancelled: execution=%s", execution_id)

    async def get_status(self, execution_id: str) -> dict:
        execution = self._engine.get_execution(execution_id)
        if execution is None:
            return {"execution_id": execution_id, "status": "not_found"}

        experiment_uuid = self._execution_to_experiment.get(execution_id)
        run_info = None
        if experiment_uuid:
            runs, _ = await self._manager.get_runs(experiment_uuid, limit=1)
            if runs:
                run_info = runs[0]

        completed_stages = sum(1 for s in execution.stages if s.status.value == "completed")
        total_stages = len(execution.stages)

        return {
            "execution_id": execution.execution_id,
            "experiment_name": execution.experiment_name,
            "pipeline_name": execution.pipeline_name,
            "status": execution.status.value,
            "started_at": execution.started_at.isoformat() if execution.started_at else None,
            "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
            "duration_seconds": execution.duration_seconds,
            "current_stage": execution.current_stage,
            "stages_completed": completed_stages,
            "stages_total": total_stages,
            "stages_progress": f"{completed_stages}/{total_stages}",
            "error": execution.error,
            "artifacts": list(execution.artifacts),
            "model_uuids": list(execution.model_uuids),
            "run": run_info,
        }

    async def compare_experiments(self, execution_ids: list[str]) -> dict:
        run_uuids = []
        exec_map: dict[str, ExecutionResult | None] = {}
        for eid in execution_ids:
            exec_map[eid] = self._engine.get_execution(eid)
            exp_uuid = self._execution_to_experiment.get(eid)
            if exp_uuid:
                runs, _ = await self._manager.get_runs(exp_uuid, limit=1)
                if runs:
                    run_uuids.append(runs[0]["uuid"])

        comparison = await self._manager.compare_runs(run_uuids) if run_uuids else []

        return {
            "executions": {
                eid: {
                    "status": exec_map[eid].status.value if exec_map[eid] else "not_found",
                    "duration_seconds": exec_map[eid].duration_seconds if exec_map[eid] else None,
                    "stages": [
                        {"name": s.stage_name, "type": s.stage_type, "status": s.status.value}
                        for s in (exec_map[eid].stages if exec_map[eid] else [])
                    ],
                    "error": exec_map[eid].error if exec_map[eid] else None,
                }
                for eid in execution_ids
            },
            "run_comparison": comparison,
            "execution_count": len(execution_ids),
        }

    async def resume_experiment(
        self,
        execution_id: str,
        from_stage: str | None = None,
        pool=None,
    ) -> str:
        previous = self._engine.get_execution(execution_id)
        if previous is None:
            raise ValueError(f"Execution not found: {execution_id}")

        config = {}
        experiment_section = {"name": previous.experiment_name, "type": "classification"}
        config["experiment"] = experiment_section
        context = dict(previous.context_summary)

        pipeline = ExecutionPipeline(config=config)
        pipeline.build_from_config(config)

        if from_stage:
            stage_types = [s.stage_type for s in pipeline.stages]
            if from_stage in stage_types:
                idx = stage_types.index(from_stage)
                pipeline._stages = pipeline._stages[idx:]
            else:
                raise ValueError(f"Stage '{from_stage}' not found in pipeline stages")

        result = await self._engine.execute_pipeline(
            pipeline=pipeline,
            experiment_name=previous.experiment_name,
            context=context,
            pool=pool,
        )

        exp_uuid = self._execution_to_experiment.get(execution_id)
        if exp_uuid:
            self._execution_to_experiment[result.execution_id] = exp_uuid
            run = await self._manager.start_run(
                experiment_uuid=exp_uuid,
                run_name=f"resume_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                config=config,
            )
            status_map = {
                StageStatus.COMPLETED: "completed",
                StageStatus.FAILED: "failed",
                StageStatus.CANCELLED: "cancelled",
            }
            await self._manager.finish_run(
                run_uuid=run["uuid"],
                status=status_map.get(result.status, "completed"),
                error_message=result.error,
            )

        logger.info("experiment resumed: new_execution=%s from_stage=%s", result.execution_id, from_stage)
        return result.execution_id

    async def get_execution_history(
        self,
        experiment_name: str | None = None,
        limit: int = 20,
        pool=None,
    ) -> list[dict]:
        experiments, _ = await self._manager.list_experiments(limit=limit)
        if experiment_name:
            experiments = [e for e in experiments if e["name"] == experiment_name]

        history = []
        for exp in experiments:
            runs, _ = await self._manager.get_runs(exp["uuid"], limit=limit)
            for run in runs:
                history.append({
                    "experiment_uuid": exp["uuid"],
                    "experiment_name": exp["name"],
                    "experiment_type": exp["experiment_type"],
                    "run_uuid": run["uuid"],
                    "run_name": run["run_name"],
                    "run_number": run["run_number"],
                    "status": run["status"],
                    "metrics": run.get("metrics"),
                    "duration_seconds": run.get("duration_seconds"),
                    "error_message": run.get("error_message"),
                    "created_at": run.get("created_at"),
                })

        history.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return history[:limit]

    async def run_experiment_with_dataset(
        self,
        experiment_name: str,
        dataset_spec: str,
        model_config: dict | None = None,
        pool=None,
    ) -> str:
        from data_acquisition.research_integration import DatasetResolver

        resolver = DatasetResolver()
        enriched = await resolver.resolve_for_experiment(
            dataset_spec,
            {
                "experiment": {
                    "name": experiment_name,
                    "type": model_config.get("model_type", "classification")
                    if model_config
                    else "classification",
                },
                "model": model_config or {},
            },
            pool=pool,
        )
        return await self.run_experiment(enriched, pool=pool)

    async def get_execution_logs(self, execution_id: str) -> list[dict]:
        return self._engine.get_execution_log(execution_id)

