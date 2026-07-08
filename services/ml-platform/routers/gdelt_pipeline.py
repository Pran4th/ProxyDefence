from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from data_acquisition.gdelt_pipeline.master_file_reader import MasterFileReader
from data_acquisition.gdelt_pipeline.filter import GDELTFilter, FilterConfig
from data_acquisition.gdelt_pipeline.downloader import GDELTDownloader
from data_acquisition.gdelt_pipeline.parser import GDELTParser
from data_acquisition.gdelt_pipeline.registration import GDELTRegistration
from data_acquisition.gdelt_pipeline.validation import GDELTValidator
from data_acquisition.gdelt_pipeline.pipeline import GDELTPipeline
from data_acquisition.gdelt_pipeline.report import ReportGenerator

router = APIRouter(prefix="/api/v1/ml/gdelt", tags=["ML GDELT Pipeline"])


class GDELTDiscoverRequest(BaseModel):
    pass


class GDELTDownloadRequest(BaseModel):
    start_date: str = "2024-01-01"
    end_date: str | None = None
    version: str | None = None


class GDELTParseRequest(BaseModel):
    start_date: str = "2024-01-01"
    version: str | None = None


class GDELTRegisterRequest(BaseModel):
    start_date: str = "2024-01-01"
    version: str | None = None


class GDELTValidateRequest(BaseModel):
    start_date: str = "2024-01-01"
    version: str | None = None


@router.post("/discover")
async def gdelt_discover() -> dict[str, Any]:
    try:
        reader = MasterFileReader()
        result = await reader.fetch()
        if result.error:
            raise HTTPException(status_code=502, detail=result.error)
        return {
            "status": "completed",
            "total_discovered": result.total_discovered,
            "by_type": result.by_type,
            "earliest": result.earliest,
            "latest": result.latest,
            "duration_seconds": result.download_duration_seconds,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/download")
async def gdelt_download(body: GDELTDownloadRequest) -> dict[str, Any]:
    try:
        reader = MasterFileReader()
        master_result = await reader.fetch()
        if master_result.error:
            raise HTTPException(status_code=502, detail=f"discovery failed: {master_result.error}")

        filter_config = FilterConfig(
            start_date=body.start_date,
            end_date=body.end_date,
        )
        filtered = GDELTFilter().filter(master_result.entries, filter_config)
        if not filtered:
            return {
                "status": "completed",
                "note": "No matching files found for date range",
                "filtered_count": 0,
            }

        version = body.version or body.start_date.replace("-", "")
        downloader = GDELTDownloader()
        results = await downloader.download_batch(filtered, version=version)

        return {
            "status": "completed",
            "total_entries": len(filtered),
            "completed": sum(1 for r in results if r.status == "completed"),
            "failed": sum(1 for r in results if r.status == "failed"),
            "total_bytes": sum(r.total_size_bytes for r in results),
            "version": version,
            "results": [
                {
                    "source": r.source,
                    "url": r.url,
                    "status": r.status,
                    "size_bytes": r.total_size_bytes,
                    "duration_seconds": r.download_duration_seconds,
                    "error": r.error,
                    "files": [str(f) for f in r.files],
                }
                for r in results
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/parse")
async def gdelt_parse(body: GDELTParseRequest) -> dict[str, Any]:
    import zipfile
    try:
        version = body.version or body.start_date.replace("-", "")
        parser = GDELTParser()

        files_by_type: dict[str, list[Path]] = {"events": [], "mentions": [], "gkg": []}
        for ds_type in ("events", "mentions", "gkg"):
            base = Path(f"datasets/raw/gdelt/{ds_type}/{version}")
            if base.exists():
                for zf in base.glob("*.zip"):
                    extract_dir = base / "extracted"
                    extract_dir.mkdir(parents=True, exist_ok=True)
                    with zipfile.ZipFile(zf, "r") as z:
                        z.extractall(extract_dir)
                    for csv_file in extract_dir.glob("*.csv"):
                        files_by_type[ds_type].append(csv_file)

        parse_results = []
        for ds_type, file_list in files_by_type.items():
            for fp in file_list:
                pr = await parser.parse_file(
                    input_path=fp,
                    dataset_type=ds_type,
                    version=version,
                )
                parse_results.append(pr)

        return {
            "status": "completed",
            "total_files": len(parse_results),
            "total_records_parsed": sum(r.records_parsed for r in parse_results),
            "total_records_failed": sum(r.records_failed for r in parse_results),
            "version": version,
            "results": [
                {
                    "source": r.source,
                    "records_parsed": r.records_parsed,
                    "records_failed": r.records_failed,
                    "output_path": str(r.output_path),
                    "duration_seconds": r.duration_seconds,
                }
                for r in parse_results
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/register")
async def gdelt_register(body: GDELTRegisterRequest) -> dict[str, Any]:
    try:
        version = body.version or body.start_date.replace("-", "")
        reg = GDELTRegistration()
        results: dict[str, Any] = {}

        for ds_type in ("events", "mentions", "gkg"):
            csv_dir = Path(f"datasets/processed/gdelt/{ds_type}/{version}")
            if csv_dir.exists():
                csv_files = list(csv_dir.glob("*.csv"))
                for csv_path in csv_files:
                    result = await reg.register_parsed_dataset(
                        dataset_type=ds_type,
                        version=version,
                        csv_path=csv_path,
                    )
                    results[ds_type] = {
                        "dataset_name": result.dataset_name,
                        "status": result.status,
                        "registration_id": getattr(result.registration, "registration_id", "") if result.registration else "",
                        "records_parsed": result.records_parsed,
                        "records_failed": result.records_failed,
                        "error": result.error,
                    }

        return {
            "status": "completed",
            "version": version,
            "results": results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate")
async def gdelt_validate(body: GDELTValidateRequest) -> dict[str, Any]:
    import zipfile
    try:
        version = body.version or body.start_date.replace("-", "")
        validator = GDELTValidator()
        validation_results: dict[str, Any] = {}

        for ds_type in ("events", "mentions", "gkg"):
            zip_dir = Path(f"datasets/raw/gdelt/{ds_type}/{version}")
            csv_dir = Path(f"datasets/processed/gdelt/{ds_type}/{version}")
            checks: list[dict] = []

            if zip_dir.exists():
                for zf in zip_dir.glob("*.zip"):
                    vresult = validator.full_validation(
                        dataset_type=ds_type,
                        version=version,
                        zip_path=zf,
                    )
                    for c in vresult.checks:
                        checks.append({
                            "name": c.name,
                            "passed": c.passed,
                            "detail": c.detail,
                        })

            if csv_dir.exists():
                for csv_path in csv_dir.glob("*.csv"):
                    vresult_csv = validator.full_validation(
                        dataset_type=ds_type,
                        version=version,
                        csv_path=csv_path,
                    )
                    for c in vresult_csv.checks:
                        checks.append({
                            "name": c.name,
                            "passed": c.passed,
                            "detail": c.detail,
                        })

            validation_results[ds_type] = {
                "checks": checks,
                "all_passed": all(c["passed"] for c in checks),
                "total_checks": len(checks),
                "passed": sum(1 for c in checks if c["passed"]),
                "failed": sum(1 for c in checks if not c["passed"]),
            }

        return {
            "status": "completed",
            "version": version,
            "results": validation_results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def gdelt_status() -> dict[str, Any]:
    try:
        status_info: dict[str, Any] = {
            "gdelt_sources": {
                "events": {"registered": True, "parser": "GDELTEventParser"},
                "mentions": {"registered": True, "parser": "GDELTMentionParser"},
                "gkg": {"registered": True, "parser": "GKGParser"},
            },
            "master_file_url": "http://data.gdeltproject.org/gdeltv2/masterfilelist.txt",
        }

        for ds_type in ("events", "mentions", "gkg"):
            raw_dir = Path(f"datasets/raw/gdelt/{ds_type}")
            proc_dir = Path(f"datasets/processed/gdelt/{ds_type}")
            versions_raw = sorted([d.name for d in raw_dir.iterdir() if d.is_dir()]) if raw_dir.exists() else []
            versions_proc = sorted([d.name for d in proc_dir.iterdir() if d.is_dir()]) if proc_dir.exists() else []
            status_info["gdelt_sources"][ds_type]["raw_versions"] = versions_raw
            status_info["gdelt_sources"][ds_type]["processed_versions"] = versions_proc

        return status_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
