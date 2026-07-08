from typing import Any

from fastapi import APIRouter, HTTPException

from models import ResearchImportRequest, ResearchImportResponse
from deployment.research_exporter import ResearchExporter, export_config_schema
from deployment.platform_importer import PlatformImporter

router = APIRouter(prefix="/api/v1/ml/deployment", tags=["ML Deployment"])


@router.get("/schemas/export-config")
async def get_export_schema() -> dict:
    return export_config_schema()


@router.get("/exports")
async def list_exports() -> list[dict]:
    exporter = ResearchExporter()
    return exporter.list_exports()


@router.post("/import")
async def import_research_model(body: ResearchImportRequest) -> ResearchImportResponse:
    importer = PlatformImporter()
    try:
        result = await importer.import_export(
            export_path=body.export_path,
            model_name=body.model_name,
            stage=body.stage,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")

    return ResearchImportResponse(**result)


@router.get("/import/health")
async def import_health():
    return {"status": "healthy", "service": "Research Deployment Pipeline"}


@router.get("/health")
async def deployment_health():
    return {"status": "healthy", "service": "ML Deployment Pipeline"}
