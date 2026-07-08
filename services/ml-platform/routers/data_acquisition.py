from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from db import get_pool
from data_acquisition.download_manager import DownloadManager, DownloadConfig
from data_acquisition.registration import DatasetRegistrationPipeline
from data_acquisition.registration_flow import RegistrationFlow
from data_acquisition.source_registry import SourceRegistry, DATASET_REGISTRY
from data_acquisition.lake import DataLake
from data_acquisition.research_integration import DatasetResolver
from data_acquisition.parser.sources import (
    GDELTEventParser, GDELTMentionParser, GKGParser, GCAMParser,
    EIAParser, FREDParser, OPECParser,
    AISParser, PortCongestionParser, WorldPortIndexParser,
    CommodityPriceParser, CommodityFuturesParser,
    OFACParser, UNSanctionsParser,
    WorldBankParser, UNComtradeParser, KaggleParser,
)
from data_acquisition.parser.base import ParseConfig

router = APIRouter(prefix="/api/v1/ml/acquisition", tags=["ML Data Acquisition"])

_PARSER_MAP: dict[str, type] = {
    "GDELTEventParser": GDELTEventParser,
    "GDELTMentionParser": GDELTMentionParser,
    "GKGParser": GKGParser,
    "GCAMParser": GCAMParser,
    "EIAParser": EIAParser,
    "FREDParser": FREDParser,
    "OPECParser": OPECParser,
    "AISParser": AISParser,
    "PortCongestionParser": PortCongestionParser,
    "WorldPortIndexParser": WorldPortIndexParser,
    "CommodityPriceParser": CommodityPriceParser,
    "CommodityFuturesParser": CommodityFuturesParser,
    "OFACParser": OFACParser,
    "UNSanctionsParser": UNSanctionsParser,
    "WorldBankParser": WorldBankParser,
    "UNComtradeParser": UNComtradeParser,
    "KaggleParser": KaggleParser,
}


class DownloadRequest(BaseModel):
    source: str
    version: str | None = None
    force: bool = False
    dry_run: bool = False


class ParseRequest(BaseModel):
    source: str
    input_path: str
    version: str | None = None
    output_dir: str | None = None


class RegisterRequest(BaseModel):
    dataset_name: str
    source: str
    version: str
    path: str


class BuildRequest(BaseModel):
    dataset_name: str
    builder_name: str | None = None
    version: str | None = None


class ValidateRequest(BaseModel):
    dataset_name: str
    version: str | None = None


@router.post("/download")
async def download_dataset(body: DownloadRequest) -> dict[str, Any]:
    pool = await get_pool()
    try:
        mgr = DownloadManager()
        config = DownloadConfig(
            source=body.source,
            version=body.version or "latest",
            url=None,
        )
        if body.dry_run:
            return {"status": "dry_run", "result": {"source": body.source, "version": body.version or "latest"}}
        result = await mgr.download(config)
        await mgr.close()
        return {"status": result.status, "result": {
            "source": result.source,
            "version": result.version,
            "files": [str(f) for f in result.files],
            "total_size_bytes": result.total_size_bytes,
            "checksum": result.checksum,
            "download_duration_seconds": result.download_duration_seconds,
            "retries": result.retries,
            "error": result.error,
        }}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/parse")
async def parse_data(body: ParseRequest) -> dict[str, Any]:
    try:
        registry = SourceRegistry()
        for sd in DATASET_REGISTRY:
            registry.register(sd)
        source_def = registry.get(body.source)
        if not source_def:
            raise HTTPException(status_code=404, detail=f"Source '{body.source}' not registered")
        parser_cls = _PARSER_MAP.get(source_def.default_parser)
        if not parser_cls:
            raise HTTPException(status_code=422, detail=f"No parser found for source: {body.source}")
        parser = parser_cls()
        input_path = Path(body.input_path)
        if not input_path.exists():
            raise HTTPException(status_code=422, detail=f"Input path does not exist: {body.input_path}")
        output_dir = Path(body.output_dir) if body.output_dir else input_path.parent
        version = body.version or source_def.version
        config = ParseConfig(
            source=body.source,
            version=version,
            input_path=input_path,
            output_path=output_dir,
        )
        result = await parser.parse(config)
        return {"status": "completed", "result": {
            "source": result.source,
            "version": result.version,
            "records_parsed": result.records_parsed,
            "records_failed": result.records_failed,
            "output_path": str(result.output_path),
            "columns": result.columns,
            "row_count": result.row_count,
            "duration_seconds": result.duration_seconds,
            "errors": result.errors,
        }}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/register")
async def register_dataset(body: RegisterRequest) -> dict[str, Any]:
    try:
        pipeline = DatasetRegistrationPipeline()
        path = Path(body.path)
        if not path.exists():
            raise HTTPException(status_code=422, detail=f"Path does not exist: {body.path}")
        result = await pipeline.register_dataset(
            dataset_name=body.dataset_name,
            source=body.source,
            version=body.version,
            processed_path=path,
        )
        return {"status": result.status, "result": {
            "dataset_name": result.dataset_name,
            "version": result.version,
            "status": result.status,
            "catalog_entry": result.catalog_entry,
            "statistics": result.statistics,
            "preview_rows": result.preview_rows,
            "manifest_path": str(result.manifest_path),
            "registration_id": result.registration_id,
            "error": result.error,
        }}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/build")
async def build_dataset(body: BuildRequest) -> dict[str, Any]:
    try:
        flow = RegistrationFlow()
        version = body.version or "1"
        result = await flow.process_registered_to_builder(
            dataset_name=body.dataset_name,
            version=version,
            builder_name=body.builder_name,
        )
        return {"status": "completed", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sources")
async def list_sources(
    category: str | None = Query(None),
    active_only: bool = Query(True),
) -> dict[str, Any]:
    try:
        registry = SourceRegistry()
        for sd in DATASET_REGISTRY:
            registry.register(sd)
        sources = registry.list_sources(category=category, active_only=active_only)
        return {"sources": [
            {
                "name": s.name,
                "display_name": s.display_name,
                "description": s.description,
                "category": s.category,
                "update_frequency": s.update_frequency,
                "connector_type": s.connector_type,
                "default_parser": s.default_parser,
                "version": s.version,
                "license": s.license,
                "tags": s.tags,
                "is_active": s.is_active,
            }
            for s in sources
        ], "count": len(sources)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sources/{name}")
async def get_source_details(name: str) -> dict[str, Any]:
    try:
        registry = SourceRegistry()
        for sd in DATASET_REGISTRY:
            registry.register(sd)
        source = registry.get(name)
        if not source:
            raise HTTPException(status_code=404, detail=f"Source '{name}' not found")
        return {
            "name": source.name,
            "display_name": source.display_name,
            "description": source.description,
            "category": source.category,
            "update_frequency": source.update_frequency,
            "connector_type": source.connector_type,
            "default_parser": source.default_parser,
            "url_template": source.url_template,
            "expected_schema": source.expected_schema,
            "version": source.version,
            "license": source.license,
            "citation": source.citation,
            "tags": source.tags,
            "is_active": source.is_active,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/datasets")
async def list_datasets(
    source: str | None = Query(None),
    status: str | None = Query(None),
) -> dict[str, Any]:
    try:
        flow = RegistrationFlow()
        datasets = await flow.list_registered_datasets(source=source)
        if status:
            datasets = [d for d in datasets if d.get("dataset_type") == status]
        return {"datasets": datasets, "total": len(datasets)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/datasets/{name}")
async def get_dataset_details(
    name: str,
    version: str | None = Query(None),
) -> dict[str, Any]:
    try:
        lake = DataLake()
        flow = RegistrationFlow()
        entry = await flow.get_registration_status(name)
        if not entry.get("registered"):
            raise HTTPException(status_code=404, detail=f"Dataset '{name}' not found")
        versions = await lake.list_versions(name)
        manifest = {}
        schema = {}
        statistics = {}
        if version:
            proc_path = await lake.get_processed_path(name, version)
            manifest_path = proc_path / "dataset.yaml"
            if manifest_path.exists():
                from data_acquisition.manifest import ManifestGenerator
                gen = ManifestGenerator()
                manifest_obj = await gen.load_manifest(manifest_path)
                manifest = {
                    "dataset_name": manifest_obj.dataset_name,
                    "version": manifest_obj.version,
                    "file_count": manifest_obj.file_count,
                    "total_size_bytes": manifest_obj.total_size_bytes,
                    "row_count": manifest_obj.row_count,
                    "column_count": manifest_obj.column_count,
                }
        return {
            "name": name,
            "entry": entry,
            "manifest": manifest,
            "schema": schema,
            "statistics": statistics,
            "versions": versions,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/datasets/{name}/statistics")
async def get_dataset_statistics(
    name: str,
    version: str | None = Query(None),
) -> dict[str, Any]:
    try:
        pipeline = DatasetRegistrationPipeline()
        lake = DataLake()
        v = version or "1"
        proc_path = await lake.get_processed_path(name, v)
        file_path = proc_path / "data.parquet" if proc_path.exists() else proc_path
        if not file_path.exists() or (file_path.is_dir() and not list(file_path.glob("*.parquet"))):
            raise HTTPException(status_code=404, detail=f"Dataset '{name}' version '{v}' not found on disk")
        if file_path.is_dir():
            parquet_files = list(file_path.glob("*.parquet"))
            file_path = parquet_files[0] if parquet_files else file_path
        stats = await pipeline.compute_statistics(file_path)
        return {"statistics": stats}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/datasets/{name}/preview")
async def get_dataset_preview(
    name: str,
    version: str | None = Query(None),
    n_rows: int = Query(100, ge=1, le=10000),
) -> dict[str, Any]:
    try:
        pipeline = DatasetRegistrationPipeline()
        lake = DataLake()
        v = version or "1"
        proc_path = await lake.get_processed_path(name, v)
        file_path = proc_path / "data.parquet" if proc_path.exists() else proc_path
        if not file_path.exists() or (file_path.is_dir() and not list(file_path.glob("*.parquet"))):
            raise HTTPException(status_code=404, detail=f"Dataset '{name}' version '{v}' not found on disk")
        if file_path.is_dir():
            parquet_files = list(file_path.glob("*.parquet"))
            file_path = parquet_files[0] if parquet_files else file_path
        preview = await pipeline.generate_preview(file_path, n_rows=n_rows)
        schema = await pipeline.generate_schema(file_path)
        return {"preview": preview, "schema": schema}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/datasets/validate")
async def validate_dataset(body: ValidateRequest) -> dict[str, Any]:
    try:
        pipeline = DatasetRegistrationPipeline()
        lake = DataLake()
        v = body.version or "1"
        proc_path = await lake.get_processed_path(body.dataset_name, v)
        file_path = proc_path / "data.parquet" if proc_path.exists() else proc_path
        if not file_path.exists() or (file_path.is_dir() and not list(file_path.glob("*.parquet"))):
            raise HTTPException(status_code=404, detail=f"Dataset '{body.dataset_name}' version '{v}' not found on disk")
        if file_path.is_dir():
            parquet_files = list(file_path.glob("*.parquet"))
            file_path = parquet_files[0] if parquet_files else file_path

        validations = []
        passed = 0
        failed = 0

        try:
            schema = await pipeline.generate_schema(file_path)
            validations.append({"check": "schema_inference", "passed": True, "detail": f"Inferred {len(schema)} columns"})
            passed += 1
        except Exception as e:
            validations.append({"check": "schema_inference", "passed": False, "detail": str(e)})
            failed += 1

        try:
            stats = await pipeline.compute_statistics(file_path)
            validations.append({"check": "statistics", "passed": True, "detail": f"{stats['row_count']} rows, {stats['column_count']} columns"})
            passed += 1
        except Exception as e:
            validations.append({"check": "statistics", "passed": False, "detail": str(e)})
            failed += 1

        try:
            integrity_ok = await pipeline.verify_integrity(file_path, "")
            validations.append({"check": "integrity", "passed": True, "detail": "File readable and valid"})
            passed += 1
        except Exception as e:
            validations.append({"check": "integrity", "passed": False, "detail": str(e)})
            failed += 1

        return {"validations": validations, "passed": passed, "failed": failed}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lake/stats")
async def get_lake_statistics() -> dict[str, Any]:
    try:
        lake = DataLake()
        stats = await lake.get_lake_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resolve/{dataset_spec}")
async def resolve_dataset(dataset_spec: str) -> dict[str, Any]:
    try:
        resolver = DatasetResolver()
        result = await resolver.resolve_dataset(dataset_spec)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def acquisition_health() -> dict[str, str]:
    return {"status": "healthy", "service": "Data Acquisition"}
