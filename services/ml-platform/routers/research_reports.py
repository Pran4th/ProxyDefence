from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from config import REPORT_DIR, ARTIFACT_DIR
from research.experiment_runner import ExperimentRunner
from research.model_cards import ModelCardGenerator
from research.notebooks import NotebookRunner, NotebookPipeline
from research.notebooks.runner import DEFAULT_PIPELINE
from research.reports import ReportGenerator, ReportFormat

router = APIRouter(prefix="/api/v1/ml/research/reports", tags=["ML Research Reports"])

_runner = ExperimentRunner()
_report_gen = ReportGenerator()
_card_gen = ModelCardGenerator()
_notebook_runner = NotebookRunner()


@router.post("/generate")
async def generate_report(body: dict) -> dict[str, Any]:
    execution_id = body.get("execution_id")
    if not execution_id:
        raise HTTPException(status_code=422, detail="'execution_id' is required")
    fmt = body.get("format", "md")
    output_dir = body.get("output_dir")
    try:
        status = await _runner.get_status(execution_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    format_map = {
        "md": ReportFormat.MARKDOWN,
        "json": ReportFormat.JSON,
        "html": ReportFormat.HTML,
        "all": None,
    }
    target_format = format_map.get(fmt)
    if target_format is None and fmt != "all":
        raise HTTPException(status_code=422, detail=f"Unsupported format: {fmt}")
    out = output_dir or str(Path(REPORT_DIR) / execution_id)
    paths = {}
    try:
        if fmt == "all":
            paths = await _report_gen.generate_all(status, out)
        else:
            path = await _report_gen.generate(status, target_format, out)
            paths[fmt] = path
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"report_paths": paths, "execution_id": execution_id}


@router.get("/model-card/{model_uuid}")
async def get_model_card(model_uuid: str) -> dict[str, Any]:
    try:
        card = await _card_gen.from_model_version(model_uuid)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {
        "model_name": card.model_name,
        "model_version": card.model_version,
        "model_type": card.model_type,
        "task": card.task,
        "dataset_name": card.dataset_name,
        "dataset_version": card.dataset_version,
        "intended_use": card.intended_use,
        "limitations": card.limitations,
        "ethical_considerations": card.ethical_considerations,
        "evaluation_metrics": card.evaluation_metrics,
        "training_params": card.training_params,
        "training_date": card.training_date,
        "owner": card.owner,
        "model_architecture": card.model_architecture,
        "feature_count": card.feature_count,
        "training_duration_seconds": card.training_duration_seconds,
        "inference_latency_ms": card.inference_latency_ms,
        "model_size_kb": card.model_size_kb,
        "bias_assessment": card.bias_assessment,
        "out_of_scope_usage": card.out_of_scope_usage,
        "dependencies": card.dependencies,
        "license": card.license,
        "references": card.references,
    }


@router.post("/model-card/generate")
async def generate_model_card(body: dict) -> dict[str, Any]:
    model_uuid = body.get("model_uuid")
    if not model_uuid:
        raise HTTPException(status_code=422, detail="'model_uuid' is required")
    output_dir = body.get("output_dir")
    try:
        card = await _card_gen.from_model_version(model_uuid)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    out = output_dir or str(Path(ARTIFACT_DIR) / "model_cards")
    try:
        paths = await _card_gen.save(card, out, formats=["md", "json"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {
        "card": {
            "model_name": card.model_name,
            "model_version": card.model_version,
            "model_type": card.model_type,
            "task": card.task,
            "evaluation_metrics": card.evaluation_metrics,
            "training_params": card.training_params,
        },
        "paths": paths,
    }


@router.get("/notebooks")
async def list_notebooks(directory: str | None = Query(None)) -> dict[str, Any]:
    nb_dir = directory or "./research/notebooks"
    try:
        notebooks = await _notebook_runner.list_notebooks(nb_dir)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"notebooks": notebooks}


@router.post("/notebooks/run")
async def run_notebook_pipeline(body: dict) -> dict[str, Any]:
    pipeline_data = body.get("pipeline")
    parameters = body.get("parameters", {})
    if pipeline_data:
        pipeline = NotebookPipeline(
            name=pipeline_data.get("name", "custom_pipeline"),
            notebooks=pipeline_data.get("notebooks", []),
            config=pipeline_data.get("config", {}),
            parameters=parameters,
        )
    else:
        pipeline = NotebookPipeline(
            name=DEFAULT_PIPELINE.name,
            notebooks=list(DEFAULT_PIPELINE.notebooks),
            config=dict(DEFAULT_PIPELINE.config),
            parameters=parameters,
        )
    try:
        results = await _notebook_runner.run_pipeline(pipeline)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"pipeline_name": pipeline.name, "results": results}


@router.get("/health")
async def reports_health():
    return {"status": "healthy", "service": "Research Reports"}
