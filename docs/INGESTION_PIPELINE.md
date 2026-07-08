# Ingestion Pipeline

## Overview

The ingestion pipeline engine provides a configurable, step-based execution framework for fetching, transforming, and storing data from external sources. It leverages the Data Connector Framework for source connectivity and feeds into the Dataset Lifecycle for versioning, cataloging, and feature engineering.

Pipelines are defined as Directed Acyclic Graphs (DAGs) of `PipelineStep` objects, each performing a discrete transformation. Steps execute in topological order with context propagation, per-step error isolation, retry, and timeout enforcement.

## PipelineStep

Every step in a pipeline is defined by the `PipelineStep` dataclass:

```python
@dataclass
class PipelineStep:
    name: str
    func: Callable                              # async handler function
    step_type: str = "generic"                  # semantic type
    inputs: list[str] = field(default_factory=list)     # context keys consumed
    outputs: list[str] = field(default_factory=list)    # context keys produced
    dependencies: list[str] = field(default_factory=list)  # step names that must precede
    config: dict[str, Any] = field(default_factory=dict)   # step-specific configuration
    retry: int = 0                              # max retries on failure
    retry_delay: float = 1.0                    # base delay for exponential backoff
    timeout: float = 300.0                      # max execution time in seconds
    cache_key: str | None = None                # optional cache key for result caching
```

| Field | Description |
|-------|-------------|
| `name` | Unique step identifier within the pipeline |
| `func` | Async callable that receives `**inputs` from context |
| `step_type` | Semantic classification for monitoring and routing |
| `inputs` | Context keys to extract and pass as kwargs to `func` |
| `outputs` | Context keys to set with the return value of `func` |
| `dependencies` | Step names that must complete before this step starts |
| `config` | Arbitrary configuration dictionary passed to the handler |
| `retry` | Number of retry attempts on failure (0 = no retry) |
| `retry_delay` | Base delay in seconds for exponential backoff |
| `timeout` | Maximum execution wall-clock time in seconds |
| `cache_key` | If set, results are cached and reused on subsequent runs |

## Step Types

| Step Type | Purpose | Typical Handler |
|-----------|---------|-----------------|
| `download` | Fetch data from external source | Connector.fetch() with pagination |
| `extract` | Parse and extract relevant fields | JSON/XML/CVS parser |
| `validate` | Run quality checks | DatasetValidationPipeline |
| `normalize` | Apply normalization rules | NormalizationRegistry.apply_all() |
| `profile` | Compute statistical profiles | DatasetProfiler.profile() |
| `version` | Assign version and compute hashes | DatasetManifest.create() |
| `catalog` | Register in dataset catalog | DatasetCatalog.register() |
| `register` | Record in dataset registry | SchemaRegistry.register() |
| `store` | Persist to storage | Parquet/ZSTD writer |

## Pipeline DAG

The `PipelineDAG` class manages step registration, topological ordering, validation, and execution.

```python
pipeline = PipelineDAG(name="energy_infrastructure_ingest")

pipeline.add_step(PipelineStep(
    name="download",
    func=connector_download_handler,
    step_type="download",
    outputs=["raw_data"],
    config={"connector_type": "energy_service", "batch_size": 1000},
    retry=3,
    retry_delay=2.0,
    timeout=600.0,
))

pipeline.add_step(PipelineStep(
    name="extract",
    func=extract_handler,
    step_type="extract",
    inputs=["raw_data"],
    outputs=["extracted_df"],
    dependencies=["download"],
))

pipeline.add_step(PipelineStep(
    name="validate",
    func=validate_handler,
    step_type="validate",
    inputs=["extracted_df"],
    outputs=["validation_results"],
    dependencies=["extract"],
    config={"checks": ["missing_values", "duplicates", "outliers"]},
))

pipeline.add_step(PipelineStep(
    name="store",
    func=store_handler,
    step_type="store",
    inputs=["extracted_df"],
    outputs=["store_path"],
    dependencies=["validate"],
    config={"format": "parquet", "compression": "zstd"},
))
```

### Topological Ordering

The `get_execution_order()` method computes a valid execution order using DFS-based topological sort:

```python
def get_execution_order(self) -> list[str]:
    visited: set[str] = set()
    order: list[str] = []

    def _visit(name: str):
        if name in visited:
            return
        visited.add(name)
        step = self._steps.get(name)
        if step:
            for dep in step.dependencies:
                _visit(dep)
            order.append(name)

    for name in self._steps:
        _visit(name)
    return order
```

### Validation

Before execution, the DAG is validated:

- Unknown dependencies are flagged
- Cycles are detected (reachability check)
- Missing input context keys are identified

## Execution

The `PipelineDAG.execute()` method runs steps in topological order, propagating context between steps.

### Context Propagation

`IngestionContext` (a `dict[str, Any]`) flows from step to step:

1. Before execution, steps declare `inputs` (context keys to consume) and `outputs` (context keys to produce)
2. Each step receives the context values matching its `inputs` as keyword arguments
3. The step's return value is assigned to its `outputs` keys in context
4. If `outputs` has one key, the entire return value is assigned; if multiple keys, the return value is destructured

```python
ctx = {"raw_data": [...]}
# Step "extract" has inputs=["raw_data"], outputs=["extracted_df"]
# Calls extract_handler(raw_data=[...])
# Sets ctx["extracted_df"] = <return value>
```

### Step Retry

Steps with `retry > 0` use exponential backoff with jitter:

```python
async def execute_with_retry(step: PipelineStep, ctx: dict) -> Any:
    last_exception = None
    for attempt in range(step.retry + 1):
        try:
            return await asyncio.wait_for(step.func(**ctx), timeout=step.timeout)
        except Exception as e:
            last_exception = e
            if attempt < step.retry:
                delay = step.retry_delay * (2 ** attempt) * random.uniform(0.5, 1.5)
                logger.warning("step %s retry %d/%d after %.1fs", step.name, attempt + 1, step.retry, delay)
                await asyncio.sleep(delay)
    raise last_exception
```

### Timeout Enforcement

Each step is wrapped in `asyncio.wait_for()` with the step's `timeout` value. Timeouts produce a `PipelineRunResult` with `status="failed"` and `error="timeout"`.

### Results

Execution returns a list of `PipelineRunResult` objects:

```python
@dataclass
class PipelineRunResult:
    step_name: str
    status: str           # "completed" | "cached" | "failed"
    start_time: datetime
    end_time: datetime | None = None
    duration_ms: float = 0.0
    error: str | None = None
    output: Any = None
```

A per-pipeline summary is computed by `PipelineExecution`:

```json
{
  "pipeline_name": "energy_infrastructure_ingest",
  "start_time": "2026-07-06T10:00:00Z",
  "end_time": "2026-07-06T10:00:45Z",
  "duration_ms": 45200.0,
  "total_steps": 5,
  "completed": 4,
  "cached": 0,
  "failed": 1,
  "steps": [
    {"step": "download", "status": "completed", "duration_ms": 12300.0},
    {"step": "extract",  "status": "completed", "duration_ms": 3400.0},
    {"step": "validate", "status": "failed",    "duration_ms": 500.0, "error": "high_missing_rate: 0.25"},
    {"step": "normalize","status": "completed", "duration_ms": 2100.0},
    {"step": "store",    "status": "completed", "duration_ms": 8900.0}
  ]
}
```

## Pipeline Execution Manager

The `PipelineExecution` singleton manages registered pipelines and execution history:

```python
class PipelineExecution:
    def register(self, pipeline: PipelineDAG) -> None: ...
    def get(self, name: str) -> PipelineDAG | None: ...
    def list_pipelines(self) -> list[dict]: ...
    async def run(self, name: str, context: dict | None = None,
                  step_filter: list[str] | None = None) -> dict: ...
    def get_history(self, pipeline_name: str | None = None,
                    limit: int = 50) -> list[dict]: ...
```

## Pipeline Caching

The `PipelineCache` class provides two-tier caching (memory + disk) for pipeline step results:

```python
class PipelineCache:
    def exists(self, step_name: str, params: dict | None = None,
               input_hash: str | None = None) -> bool: ...
    def get(self, step_name: str, params: dict | None = None,
            input_hash: str | None = None) -> Any: ...
    def set(self, step_name: str, data: Any, params: dict | None = None,
            input_hash: str | None = None) -> None: ...
    def invalidate(self, step_name: str | None = None) -> None: ...
```

Cache keys are SHA-256 hashes of `step_name::params_json::input_hash`. Cached data is stored as Parquet on disk. Steps with `cache_key` set are checked against the cache before execution.

## Pipeline Export and Replay

`PipelineExporter` serializes pipelines to YAML/JSON and enables replay:

```python
# Export
PipelineExporter.export_yaml(pipeline, "pipelines/energy_ingest.yaml")

# Replay from previous results
PipelineExporter.replay(pipeline, previous_results)
```

## Scheduling

Pipelines can be scheduled via cron expressions, managed through `ml.training_schedules`:

```yaml
schedules:
  - pipeline: energy_infrastructure_ingest
    cron: "0 6 * * *"           # Daily at 06:00 UTC
    config:
      connector_type: energy_service
      full_refresh: false
  - pipeline: gnews_fetch
    cron: "0 */4 * * *"         # Every 4 hours
    config:
      max_articles: 500
      language: en
```

Schedule management is available via:

- `GET /api/v1/ml/schedules` — List all active schedules
- `POST /api/v1/ml/schedules` — Create a new schedule
- `PUT /api/v1/ml/schedules/{uuid}` — Update schedule
- `DELETE /api/v1/ml/schedules/{uuid}` — Deactivate schedule

## Error Handling

### Per-Step Error Isolation

Each step failure is isolated — downstream steps depending on the failed step's outputs are skipped, but parallel branches continue execution.

### Error Logging

All errors are recorded in `ml.ingestion_errors` with structured context:

```json
{
  "pipeline_name": "gnews_fetch",
  "pipeline_version": 1,
  "error_type": "RateLimitError",
  "error_code": "RATE_LIMIT_EXCEEDED",
  "error_message": "API rate limit exceeded, retry after 60s",
  "source_record": {},
  "retry_count": 3,
  "is_resolved": false
}
```

### Partial Completion

If a pipeline has 5 steps and step 3 fails, steps 1-2 results are preserved, steps 3-5 are logged as failed, and the pipeline returns a partial completion summary.

## Example Pipeline Definition (YAML)

```yaml
name: energy_infrastructure_ingest
version: 1
description: Daily ingestion of energy infrastructure catalog from Energy Service

steps:
  - name: download
    type: download
    handler: connectors.energy_service.download
    outputs: [raw_data]
    config:
      connector_type: energy_service
      tables: [ports, pipelines, refineries, oil_fields]
      batch_size: 1000
    retry: 3
    retry_delay: 2.0
    timeout: 600

  - name: extract
    type: extract
    handler: pipelines.handlers.extract_energy_data
    inputs: [raw_data]
    outputs: [extracted_df]
    dependencies: [download]
    config:
      drop_columns: [uuid, slug, created_at, updated_at]
      rename_columns:
        production_bpd: production_barrels_per_day

  - name: validate
    type: validate
    handler: pipelines.handlers.validate_energy_data
    inputs: [extracted_df]
    outputs: [validation_results]
    dependencies: [extract]
    config:
      checks: [missing_values, duplicates, outliers]
      thresholds:
        missing_rate: 0.10
        duplicate_rate: 0.05

  - name: normalize
    type: normalize
    handler: pipelines.handlers.normalize_energy_data
    inputs: [extracted_df]
    outputs: [normalized_df]
    dependencies: [validate]
    config:
      rules: [normalize_dates, map_operational_status, convert_units]

  - name: profile
    type: profile
    handler: pipelines.handlers.profile_dataset
    inputs: [normalized_df]
    outputs: [profile_results]
    dependencies: [normalize]

  - name: version
    type: version
    handler: pipelines.handlers.version_dataset
    inputs: [normalized_df, profile_results]
    outputs: [version_info]
    dependencies: [profile]
    config:
      dataset_name: energy_infrastructure
      target_column: criticality_score
      splits:
        train: 0.7
        validation: 0.1
        test: 0.2

  - name: store
    type: store
    handler: pipelines.handlers.store_dataset
    inputs: [normalized_df, version_info]
    outputs: [store_path]
    dependencies: [version]
    config:
      format: parquet
      compression: zstd
```

## Future Datasets

The ingestion pipeline is designed to accommodate the following data sources as new connector implementations:

| Dataset | Source | Connector Type | Update Frequency | Domain |
|---------|--------|---------------|-----------------|--------|
| GDELT | GDELT 2.0 API | `gdelt` | Every 15 min | Global events |
| ACLED | ACLED API | `acled` | Daily | Conflict events |
| ICEWS | ICEWS API | `icews` | Daily | Political events |
| AIS | AIS streaming | `ais` | Real-time | Maritime |
| EIA | EIA API | `eia` | Weekly | Energy statistics |
| FRED | FRED API | `fred` | Monthly | Economic data |
| WHO | WHO API | `who` | Weekly | Health data |
| UNODC | UNODC API | `unodc` | Annual | Crime statistics |
| IMF | IMF API | `imf` | Quarterly | Financial data |
| World Bank | World Bank API | `world_bank` | Annual | Development data |
| Energy Service | Internal API | `energy_service` | On demand | Infrastructure |
| PostgreSQL | Internal DB | `postgres` | On demand | Internal data |
| Elasticsearch | Internal ES | `elasticsearch` | On demand | Search indices |
| S3 | S3 Buckets | `s3` | On demand | File storage |
| Kafka | Event streams | `kafka` | Real-time | Event streams |

## Integration with Data Connector Framework

The ingestion pipeline and connector framework integrate at the `download` step:

1. Pipeline step `download` receives a connector type name from its config
2. `ConnectorRegistry.get(connector_type)` returns the connector class
3. The connector is configured, connected, and schema discovery runs
4. `connector.fetch()` returns an async iterator of data pages
5. Each page enters the pipeline's `extract` → `validate` → ... flow
6. After all pages, `connector.checkpoint()` persists the sync state
7. `connector.disconnect()` releases resources

This decoupling means adding a new data source requires only implementing the `BaseConnector` interface and registering it — no pipeline changes needed.
