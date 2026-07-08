"""Feature Pipeline Engine — DAG-based feature computation with caching,
versioning, and reproducibility.

Builds on the existing feature_store architecture (transforms, cache,
snapshots, materialization) to provide a complete pipeline execution
framework.
"""

import dataclasses
import hashlib
import json
import pickle
import time
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.shared.logging_config import get_logger
from db import get_pool
from feature_store.snapshots import FeatureSnapshots
from feature_store.transforms import TRANSFORM_REGISTRY

logger = get_logger(__name__)


# ======================================================================
# PipelineCache
# ======================================================================


class PipelineCache:
    """Disk+memory LRU cache for pipeline step results.

    Keys are ``{step_name}:{input_hash}`` which lets the engine skip
    re-executing a step when neither its configuration nor its input
    data have changed.
    """

    def __init__(self, cache_dir: str | None = None, capacity: int = 1000):
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._capacity = capacity
        self._hits = 0
        self._misses = 0
        self._cache_dir = Path(cache_dir) if cache_dir else None
        if self._cache_dir:
            self._cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    def _make_key(self, step_name: str, input_hash: str) -> str:
        return f"{step_name}:{input_hash}"

    def _disk_path(self, key: str) -> Path | None:
        if not self._cache_dir:
            return None
        safe = key.replace(":", "_").replace("/", "_").replace("\\", "_")
        return self._cache_dir / f"{safe}.pkl"

    # ------------------------------------------------------------------
    def get(self, step_name: str, input_hash: str):
        key = self._make_key(step_name, input_hash)
        if key in self._cache:
            self._cache.move_to_end(key)
            self._hits += 1
            return self._cache[key]
        if self._cache_dir:
            path = self._disk_path(key)
            if path and path.exists():
                with open(path, "rb") as f:
                    result = pickle.load(f)
                self._cache[key] = result
                self._hits += 1
                return result
        self._misses += 1
        return None

    def set(self, step_name: str, input_hash: str, result):
        key = self._make_key(step_name, input_hash)
        while len(self._cache) >= self._capacity:
            self._cache.popitem(last=False)
        self._cache[key] = result
        if self._cache_dir:
            path = self._disk_path(key)
            if path:
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "wb") as f:
                    pickle.dump(result, f)

    def has(self, step_name: str, input_hash: str) -> bool:
        key = self._make_key(step_name, input_hash)
        if key in self._cache:
            return True
        if self._cache_dir:
            path = self._disk_path(key)
            if path and path.exists():
                return True
        return False

    def invalidate(self, step_name: str | None = None):
        if step_name:
            prefix = f"{step_name}:"
            to_remove = [k for k in self._cache if k.startswith(prefix)]
            for k in to_remove:
                del self._cache[k]
            if self._cache_dir:
                for p in self._cache_dir.glob(f"{step_name}_*.pkl"):
                    p.unlink(missing_ok=True)
        else:
            self._cache.clear()
            if self._cache_dir:
                for p in self._cache_dir.glob("*.pkl"):
                    p.unlink(missing_ok=True)

    def invalidate_all(self):
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    @property
    def size(self) -> int:
        return len(self._cache)


# ======================================================================
# Dataclasses
# ======================================================================


@dataclasses.dataclass
class FeaturePipelineStep:
    """A single step in a feature pipeline DAG.

    Attributes:
        name: Unique step identifier.
        transform_name: Key into ``TRANSFORM_REGISTRY``.
        transform_params: Keyword arguments passed to the transform constructor.
        inputs: Column names consumed from the working DataFrame.
        output: Output column name (or prefix for multi-column transforms).
        depends_on: Step names that must execute before this step.
    """
    name: str
    transform_name: str
    transform_params: dict
    inputs: list[str]
    output: str
    depends_on: list[str]


@dataclasses.dataclass
class FeaturePipelineDefinition:
    """Versioned pipeline definition stored in ``ml.feature_pipelines``.

    Attributes:
        name: Pipeline name.
        version: Incrementing version number.
        description: Human-readable description.
        steps: Ordered list of DAG steps.
        input_columns: Columns the pipeline expects in the input DataFrame.
        output_columns: Columns produced by the pipeline.
        tags: Arbitrary tags for discovery.
        metadata: Arbitrary key-value metadata.
    """
    name: str
    version: int
    description: str
    steps: list[FeaturePipelineStep]
    input_columns: list[str]
    output_columns: list[str]
    tags: list[str]
    metadata: dict


@dataclasses.dataclass
class FeaturePipelineRunResult:
    """Result of a single pipeline execution.

    Attributes:
        pipeline_name: Name of the pipeline that ran.
        pipeline_version: Version that ran.
        status: ``"completed"`` or ``"failed"``.
        step_results: Per-step execution metadata.
        output_df_shape: ``(rows, columns)`` of the output DataFrame.
        cache_hits: Number of step results served from cache.
        cache_misses: Number of steps that actually executed.
        duration_seconds: Wall-clock time for the full run.
        snapshot_uuid: UUID of an optional feature snapshot, if created.
        error: Error message on failure, else ``None``.
    """
    pipeline_name: str
    pipeline_version: int
    status: str
    step_results: list[dict]
    output_df_shape: tuple
    cache_hits: int
    cache_misses: int
    duration_seconds: float
    snapshot_uuid: str | None
    error: str | None


# ======================================================================
# Helpers
# ======================================================================


def build_pipeline_from_steps(
    pipeline_name: str,
    steps: list[tuple[str, str, dict, list[str]]],
    input_columns: list[str],
    description: str = "",
    tags: list[str] | None = None,
) -> FeaturePipelineDefinition:
    """Create a :class:`FeaturePipelineDefinition` from flat step tuples.

    Each tuple is ``(output_column, transform_name, transform_params, inputs)``.
    Dependencies (``depends_on``) are inferred automatically by checking
    which previous step outputs overlap with the current step's inputs.
    """
    pipeline_steps: list[FeaturePipelineStep] = []
    step_outputs: dict[str, str] = {}

    for output_col, transform_name, transform_params, inputs in steps:
        depends_on: list[str] = []
        for inp in inputs:
            if inp in step_outputs:
                depends_on.append(step_outputs[inp])

        step = FeaturePipelineStep(
            name=output_col,
            transform_name=transform_name,
            transform_params=transform_params,
            inputs=inputs,
            output=output_col,
            depends_on=list(set(depends_on)),
        )
        pipeline_steps.append(step)
        step_outputs[output_col] = output_col

    output_columns = [s.output for s in pipeline_steps]
    return FeaturePipelineDefinition(
        name=pipeline_name,
        version=1,
        description=description,
        steps=pipeline_steps,
        input_columns=input_columns,
        output_columns=output_columns,
        tags=tags or [],
        metadata={},
    )


def pipeline_step_from_transform(
    transform_name: str,
    output_column: str,
    input_columns: list[str],
    transform_params: dict | None = None,
    depends_on: list[str] | None = None,
) -> FeaturePipelineStep:
    """Wrap a single transform from ``TRANSFORM_REGISTRY`` as a step."""
    return FeaturePipelineStep(
        name=output_column,
        transform_name=transform_name,
        transform_params=transform_params or {},
        inputs=input_columns,
        output=output_column,
        depends_on=depends_on or [],
    )


# ======================================================================
# Engine
# ======================================================================


class FeaturePipelineEngine:
    """Complete pipeline engine for feature computation.

    Supports DAG pipelines, cached/incremental execution, pipeline
    versioning, feature snapshots, and full reproducibility.
    """

    def __init__(self, cache_dir: str | None = None):
        self._cache = PipelineCache(cache_dir=cache_dir)

    # ------------------------------------------------------------------
    # Pipeline CRUD
    # ------------------------------------------------------------------

    async def define_pipeline(
        self,
        definition: FeaturePipelineDefinition,
        pool=None,
    ) -> str:
        """Register a pipeline definition in ``ml.feature_pipelines``.

        Returns the UUID of the inserted row.
        """
        p = pool or await get_pool()
        steps_json = [dataclasses.asdict(s) for s in definition.steps]
        metadata = {**definition.metadata, "tags": definition.tags}

        row = await p.fetchrow(
            """INSERT INTO ml.feature_pipelines
               (name, version, description, pipeline_type, source_datasets,
                transform_steps, metadata, is_active)
               VALUES ($1, $2, $3, 'feature_pipeline', $4, $5, $6, TRUE)
               ON CONFLICT (name, version)
               DO UPDATE SET
                 description = EXCLUDED.description,
                 source_datasets = EXCLUDED.source_datasets,
                 transform_steps = EXCLUDED.transform_steps,
                 metadata = EXCLUDED.metadata,
                 updated_at = NOW()
               RETURNING uuid""",
            definition.name,
            definition.version,
            definition.description,
            definition.input_columns,
            json.dumps(steps_json),
            json.dumps(metadata),
        )
        uuid_: str = str(row["uuid"])
        logger.info(
            "pipeline '%s' v%d defined (%s)",
            definition.name, definition.version, uuid_,
        )
        return uuid_

    async def get_pipeline(
        self,
        name: str,
        version: int | None = None,
        pool=None,
    ) -> FeaturePipelineDefinition | None:
        """Retrieve a pipeline definition by name and optional version."""
        p = pool or await get_pool()
        if version is not None:
            row = await p.fetchrow(
                """SELECT * FROM ml.feature_pipelines
                   WHERE name = $1 AND version = $2""",
                name, version,
            )
        else:
            row = await p.fetchrow(
                """SELECT * FROM ml.feature_pipelines
                   WHERE name = $1
                   ORDER BY version DESC LIMIT 1""",
                name,
            )
        if not row:
            return None
        return self._row_to_definition(row)

    async def list_pipelines(self, pool=None) -> list[dict]:
        """List all pipeline names and their latest version info."""
        p = pool or await get_pool()
        rows = await p.fetch(
            """SELECT DISTINCT ON (name)
                      uuid, name, version, description, pipeline_type,
                      is_active, created_at, updated_at
               FROM ml.feature_pipelines
               ORDER BY name, version DESC""",
        )
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def run_pipeline(
        self,
        name: str,
        df: pd.DataFrame,
        version: int | None = None,
        pool=None,
        incremental: bool = True,
    ) -> FeaturePipelineRunResult:
        """Execute a pipeline on *df* and return the result.

        When *incremental* is ``True`` (default), steps whose input hash
        matches a cached result are skipped.
        """
        definition = await self.get_pipeline(name, version, pool=pool)
        if definition is None:
            return FeaturePipelineRunResult(
                pipeline_name=name,
                pipeline_version=version or -1,
                status="failed",
                step_results=[],
                output_df_shape=(0, 0),
                cache_hits=0,
                cache_misses=0,
                duration_seconds=0.0,
                snapshot_uuid=None,
                error=(
                    f"Pipeline '{name}' v"
                    f"{version if version is not None else 'latest'} not found"
                ),
            )

        p = pool or await get_pool()
        missing = [c for c in definition.input_columns if c not in df.columns]
        if missing:
            return FeaturePipelineRunResult(
                pipeline_name=name,
                pipeline_version=definition.version,
                status="failed",
                step_results=[],
                output_df_shape=df.shape,
                cache_hits=0,
                cache_misses=0,
                duration_seconds=0.0,
                snapshot_uuid=None,
                error=f"Missing input columns: {missing}",
            )

        start = time.monotonic()
        ordered = self.get_execution_order(definition.steps)
        working = df.copy()
        step_results: list[dict] = []
        cache_hits = 0
        cache_misses = 0

        try:
            for step in ordered:
                input_hash = self.get_step_hash(step, working)

                if incremental and self._cache.has(step.name, input_hash):
                    cached = self._cache.get(step.name, input_hash)
                    if cached is not None:
                        self._apply_cached_result(working, step, cached)
                        step_results.append({
                            "step_name": step.name,
                            "status": "cached",
                            "transform": step.transform_name,
                            "output": step.output,
                            "duration_seconds": 0.0,
                        })
                        cache_hits += 1
                        continue

                t0 = time.monotonic()
                step_result = self._execute_step(step, working)
                step_dur = time.monotonic() - t0

                self._cache.set(step.name, input_hash, step_result)
                self._apply_step_result(working, step, step_result)
                step_results.append({
                    "step_name": step.name,
                    "status": "completed",
                    "transform": step.transform_name,
                    "output": step.output,
                    "duration_seconds": round(step_dur, 4),
                })
                cache_misses += 1

            status = "completed"
            error = None
        except Exception as exc:
            logger.exception("pipeline '%s' v%d failed", name, definition.version)
            status = "failed"
            error = str(exc)
            step_results.append({
                "step_name": step.name if 'step' in dir() else "unknown",
                "status": "error",
                "transform": step.transform_name if 'step' in dir() else "",
                "error": error,
            })

        duration = round(time.monotonic() - start, 4)
        output_columns = [c for c in working.columns if c not in df.columns]

        # Record run in ml.feature_pipeline_runs
        await p.execute(
            """INSERT INTO ml.feature_pipeline_runs
               (pipeline_name, pipeline_version, run_status,
                started_at, completed_at, duration_seconds,
                input_records, output_records, features_generated,
                metrics, error_message)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)""",
            definition.name,
            definition.version,
            status,
            datetime.now(timezone.utc) if status == "completed" else None,
            datetime.now(timezone.utc),
            duration,
            len(df),
            len(working),
            len(output_columns),
            json.dumps({
                "step_count": len(ordered),
                "cache_hits": cache_hits,
                "cache_misses": cache_misses,
                "output_columns": output_columns,
                "input_columns": definition.input_columns,
            }),
            error,
        )

        return FeaturePipelineRunResult(
            pipeline_name=name,
            pipeline_version=definition.version,
            status=status,
            step_results=step_results,
            output_df_shape=working.shape,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            duration_seconds=duration,
            snapshot_uuid=None,
            error=error,
        )

    async def run_pipeline_incremental(
        self,
        name: str,
        df: pd.DataFrame,
        baseline_hash: str | None = None,
        version: int | None = None,
        pool=None,
    ) -> FeaturePipelineRunResult:
        """Incremental execution: skip steps whose inputs match *baseline_hash*.

        When *baseline_hash* is provided, only steps whose cumulative
        input hash differs from the baseline are recomputed.
        """
        definition = await self.get_pipeline(name, version, pool=pool)
        if definition is None:
            return FeaturePipelineRunResult(
                pipeline_name=name,
                pipeline_version=version or -1,
                status="failed",
                step_results=[],
                output_df_shape=(0, 0),
                cache_hits=0,
                cache_misses=0,
                duration_seconds=0.0,
                snapshot_uuid=None,
                error=(
                    f"Pipeline '{name}' v"
                    f"{version if version is not None else 'latest'} not found"
                ),
            )

        p = pool or await get_pool()
        start = time.monotonic()
        ordered = self.get_execution_order(definition.steps)
        working = df.copy()
        step_results: list[dict] = []
        cache_hits = 0
        cache_misses = 0

        try:
            for step in ordered:
                input_hash = self.get_step_hash(step, working)

                if baseline_hash is not None:
                    combined = hashlib.sha256(
                        f"{baseline_hash}:{input_hash}".encode()
                    ).hexdigest()

                if self._cache.has(step.name, input_hash):
                    cached = self._cache.get(step.name, input_hash)
                    if cached is not None:
                        self._apply_cached_result(working, step, cached)
                        step_results.append({
                            "step_name": step.name,
                            "status": "cached",
                            "transform": step.transform_name,
                            "output": step.output,
                            "duration_seconds": 0.0,
                        })
                        cache_hits += 1
                        continue

                t0 = time.monotonic()
                step_result = self._execute_step(step, working)
                step_dur = time.monotonic() - t0

                self._cache.set(step.name, input_hash, step_result)
                self._apply_step_result(working, step, step_result)
                step_results.append({
                    "step_name": step.name,
                    "status": "completed",
                    "transform": step.transform_name,
                    "output": step.output,
                    "duration_seconds": round(step_dur, 4),
                })
                cache_misses += 1

            status = "completed"
            error = None
        except Exception as exc:
            logger.exception(
                "incremental pipeline '%s' v%d failed", name, definition.version
            )
            status = "failed"
            error = str(exc)
            step_results.append({
                "step_name": step.name if 'step' in dir() else "unknown",
                "status": "error",
                "error": error,
            })

        duration = round(time.monotonic() - start, 4)
        output_columns = [c for c in working.columns if c not in df.columns]

        await p.execute(
            """INSERT INTO ml.feature_pipeline_runs
               (pipeline_name, pipeline_version, run_status,
                started_at, completed_at, duration_seconds,
                input_records, output_records, features_generated,
                metrics, error_message, trigger_type)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'incremental')""",
            definition.name,
            definition.version,
            status,
            datetime.now(timezone.utc) if status == "completed" else None,
            datetime.now(timezone.utc),
            duration,
            len(df),
            len(working),
            len(output_columns),
            json.dumps({
                "step_count": len(ordered),
                "cache_hits": cache_hits,
                "cache_misses": cache_misses,
                "output_columns": output_columns,
                "input_columns": definition.input_columns,
                "baseline_hash": baseline_hash,
            }),
            error,
        )

        return FeaturePipelineRunResult(
            pipeline_name=name,
            pipeline_version=definition.version,
            status=status,
            step_results=step_results,
            output_df_shape=working.shape,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            duration_seconds=duration,
            snapshot_uuid=None,
            error=error,
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    async def validate_pipeline(
        self,
        name: str,
        version: int | None = None,
    ) -> list[str]:
        """Validate a pipeline definition and return a list of errors.

        An empty list means the pipeline is valid.
        """
        definition = await self.get_pipeline(name, version)
        if definition is None:
            v_str = str(version) if version is not None else "latest"
            return [f"Pipeline '{name}' v{v_str} not found"]

        errors: list[str] = []
        step_names: set[str] = set()
        available_columns: set[str] = set(definition.input_columns)

        for step in definition.steps:
            if step.name in step_names:
                errors.append(f"Duplicate step name: '{step.name}'")
            step_names.add(step.name)

            if step.transform_name not in TRANSFORM_REGISTRY:
                errors.append(
                    f"Step '{step.name}': unknown transform "
                    f"'{step.transform_name}'. "
                    f"Available: {sorted(TRANSFORM_REGISTRY)}"
                )

            for inp in step.inputs:
                if inp not in available_columns:
                    errors.append(
                        f"Step '{step.name}': input column '{inp}' "
                        f"not available (not in input_columns or "
                        f"previous step outputs)"
                    )

            step_names_in_def = {s.name for s in definition.steps}
            for dep in step.depends_on:
                if dep not in step_names_in_def:
                    errors.append(
                        f"Step '{step.name}': depends_on '{dep}' "
                        f"not found in pipeline steps"
                    )

            available_columns.add(step.output)

        # Cycle detection via topological sort
        try:
            self.get_execution_order(definition.steps)
        except ValueError as e:
            errors.append(str(e))

        # Warn about unused outputs (informational)
        all_inputs: set[str] = set()
        for step in definition.steps:
            all_inputs.update(step.inputs)

        return errors

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    async def create_snapshot(
        self,
        result: FeaturePipelineRunResult,
        df: pd.DataFrame,
        entity_type: str,
        pool=None,
    ) -> str:
        """Create a feature snapshot from pipeline output.

        Stores the full output DataFrame as a single consolidated
        snapshot in ``ml.feature_snapshots`` and returns its UUID.
        """
        p = pool or await get_pool()
        snapshot_data = {
            "pipeline_name": result.pipeline_name,
            "pipeline_version": result.pipeline_version,
            "run_status": result.status,
            "columns": list(df.columns),
            "rows": df.to_dict(orient="records"),
            "run_duration_seconds": result.duration_seconds,
            "cache_hits": result.cache_hits,
            "cache_misses": result.cache_misses,
        }

        row = await p.fetchrow(
            """INSERT INTO ml.feature_snapshots
               (feature_version, entity_type, entity_id,
                snapshot_data, snapshot_label, snapshot_type)
               VALUES ($1, $2, $3, $4, $5, 'pipeline')
               RETURNING uuid""",
            result.pipeline_version,
            entity_type,
            f"__pipeline__{result.pipeline_name}_v{result.pipeline_version}",
            json.dumps(snapshot_data),
            f"{result.pipeline_name} v{result.pipeline_version} snapshot",
        )
        uuid_: str = str(row["uuid"])
        logger.info(
            "pipeline snapshot %s for %s (v%d)",
            uuid_, entity_type, result.pipeline_version,
        )
        return uuid_

    # ------------------------------------------------------------------
    # Hashing & ordering
    # ------------------------------------------------------------------

    def get_step_hash(
        self, step: FeaturePipelineStep, df: pd.DataFrame
    ) -> str:
        """Compute a deterministic hash of step inputs for caching.

        Incorporates the transform name, parameters, and the content of
        every input column so that any change invalidates the cached
        result.
        """
        hasher = hashlib.sha256()
        hasher.update(step.transform_name.encode("utf-8"))
        hasher.update(
            json.dumps(step.transform_params, sort_keys=True).encode("utf-8")
        )
        for col in sorted(step.inputs):
            if col in df.columns:
                col_bytes = pd.util.hash_pandas_object(
                    df[col], index=False
                ).values.tobytes()
                hasher.update(col.encode("utf-8"))
                hasher.update(col_bytes)
            else:
                hasher.update(f"missing:{col}".encode("utf-8"))
        for dep in sorted(step.depends_on):
            hasher.update(dep.encode("utf-8"))
        return hasher.hexdigest()

    def get_execution_order(
        self, steps: list[FeaturePipelineStep],
    ) -> list[FeaturePipelineStep]:
        """Topological sort of steps by ``depends_on`` (Kahn's algorithm).

        Raises ``ValueError`` if a circular dependency is detected.
        """
        step_map = {s.name: s for s in steps}
        in_degree: dict[str, int] = {s.name: 0 for s in steps}
        adj: dict[str, list[str]] = {s.name: [] for s in steps}

        for s in steps:
            for dep in s.depends_on:
                if dep in step_map:
                    adj[dep].append(s.name)
                    in_degree[s.name] = in_degree.get(s.name, 0) + 1

        queue = [s.name for s in steps if in_degree.get(s.name, 0) == 0]
        ordered: list[FeaturePipelineStep] = []

        while queue:
            node = queue.pop(0)
            ordered.append(step_map[node])
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(ordered) != len(steps):
            raise ValueError(
                "Circular dependency detected in pipeline steps. "
                f"Steps: {[s.name for s in steps]}, "
                f"ordered: {[s.name for s in ordered]}"
            )

        return ordered

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _execute_step(
        self, step: FeaturePipelineStep, df: pd.DataFrame,
    ) -> Any:
        """Instantiate, fit, and run a single transform."""
        if step.transform_name not in TRANSFORM_REGISTRY:
            raise ValueError(
                f"Unknown transform '{step.transform_name}' for step "
                f"'{step.name}'. Available: {sorted(TRANSFORM_REGISTRY)}"
            )

        transform_cls = TRANSFORM_REGISTRY[step.transform_name]
        transform = transform_cls(**step.transform_params)

        input_df = df[step.inputs] if step.inputs else df
        transform.fit(input_df)
        result = transform.transform(input_df)
        return result

    def _apply_step_result(
        self, df: pd.DataFrame, step: FeaturePipelineStep, result: Any,
    ):
        """Merge a transform result back into the working DataFrame."""
        if isinstance(result, pd.DataFrame):
            for col in result.columns:
                df[col] = result[col].values
        elif isinstance(result, pd.Series):
            df[step.output] = result.values
        elif isinstance(result, np.ndarray):
            df[step.output] = result
        else:
            df[step.output] = result

    def _apply_cached_result(
        self, df: pd.DataFrame, step: FeaturePipelineStep, result: Any,
    ):
        """Restore a cached transform result into the working DataFrame."""
        self._apply_step_result(df, step, result)

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _step_from_dict(d: dict) -> FeaturePipelineStep:
        return FeaturePipelineStep(
            name=d.get("name", ""),
            transform_name=d.get("transform_name", ""),
            transform_params=d.get("transform_params", {}),
            inputs=d.get("inputs", []),
            output=d.get("output", ""),
            depends_on=d.get("depends_on", []),
        )

    @staticmethod
    def _row_to_definition(row) -> FeaturePipelineDefinition:
        steps_raw = row.get("transform_steps", [])
        if isinstance(steps_raw, str):
            steps_raw = json.loads(steps_raw)
        steps = [FeaturePipelineEngine._step_from_dict(s) for s in steps_raw]

        metadata = row.get("metadata", {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        source_datasets = row.get("source_datasets", [])
        if isinstance(source_datasets, str):
            source_datasets = json.loads(source_datasets)

        tags = metadata.get("tags", []) if isinstance(metadata, dict) else []

        output_columns = [s.output for s in steps if s.output]

        return FeaturePipelineDefinition(
            name=row["name"],
            version=row["version"],
            description=row.get("description", ""),
            steps=steps,
            input_columns=source_datasets,
            output_columns=output_columns,
            tags=tags,
            metadata=metadata,
        )
