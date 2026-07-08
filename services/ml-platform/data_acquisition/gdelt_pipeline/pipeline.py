from __future__ import annotations

import shutil
import time
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from data_acquisition.config import DataAcquisitionConfig, get_config
from data_acquisition.gdelt_pipeline.master_file_reader import (
    MasterFileReader,
    MasterFileEntry,
    MasterFileResult,
)
from data_acquisition.gdelt_pipeline.filter import GDELTFilter, FilterConfig
from data_acquisition.gdelt_pipeline.downloader import GDELTDownloader, GDELTDownloadResult
from data_acquisition.gdelt_pipeline.parser import GDELTParser, GDELTParserResult
from data_acquisition.gdelt_pipeline.registration import GDELTRegistration, GDELTRegistrationResult, GDELTRegistrationBatch
from data_acquisition.gdelt_pipeline.validation import GDELTValidator, GDELTValidationResult
from data_acquisition.lake import DataLake, DataLakeConfig


@dataclass
class PipelineStageResult:
    stage: str
    status: str
    duration_seconds: float
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class PipelineResult:
    version: str
    start_date: str | None
    end_date: str | None
    stages: list[PipelineStageResult]
    overall_status: str
    total_duration_seconds: float
    error: str | None = None


class GDELTPipeline:
    def __init__(
        self,
        config: DataAcquisitionConfig | None = None,
    ) -> None:
        self._config = config or get_config()
        self._data_lake = DataLake(DataLakeConfig(base_dir=self._config.base_dir))
        self._reader = MasterFileReader(config=self._config, data_lake=self._data_lake)
        self._filter = GDELTFilter()
        self._downloader = GDELTDownloader(config=self._config, data_lake=self._data_lake)
        self._parser = GDELTParser()
        self._registration = GDELTRegistration()
        self._validator = GDELTValidator()

    async def run(
        self,
        version: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        dataset_types: list[str] | None = None,
        max_downloads: int | None = None,
        max_parse_records: int | None = None,
    ) -> PipelineResult:
        overall_start = time.monotonic()
        stages: list[PipelineStageResult] = []

        if version is None:
            today = date.today()
            version = today.strftime("%Y%m%d")

        if dataset_types is None:
            dataset_types = ["export.CSV.zip", "mentions.CSV.zip", "gkg.csv.zip"]

        # Stage 1: Discover
        s1_start = time.monotonic()
        try:
            master_result: MasterFileResult = await self._reader.fetch()
            if master_result.error:
                stages.append(PipelineStageResult(
                    stage="discover", status="failed",
                    duration_seconds=time.monotonic() - s1_start,
                    error=master_result.error,
                ))
                return PipelineResult(
                    version=version, start_date=start_date, end_date=end_date,
                    stages=stages, overall_status="failed",
                    total_duration_seconds=time.monotonic() - overall_start,
                    error=master_result.error,
                )

            stages.append(PipelineStageResult(
                stage="discover", status="completed",
                duration_seconds=time.monotonic() - s1_start,
                data={
                    "total_discovered": master_result.total_discovered,
                    "by_type": master_result.by_type,
                    "earliest": master_result.earliest,
                    "latest": master_result.latest,
                },
            ))
        except Exception as e:
            stages.append(PipelineStageResult(
                stage="discover", status="failed",
                duration_seconds=time.monotonic() - s1_start,
                error=str(e),
            ))
            return PipelineResult(
                version=version, start_date=start_date, end_date=end_date,
                stages=stages, overall_status="failed",
                total_duration_seconds=time.monotonic() - overall_start,
                error=str(e),
            )

        # Stage 2: Filter
        s2_start = time.monotonic()
        try:
            filter_config = FilterConfig(
                start_date=start_date,
                end_date=end_date,
                dataset_types=dataset_types,
            )
            filtered = self._filter.filter(master_result.entries, filter_config)

            if max_downloads and len(filtered) > max_downloads:
                filtered = filtered[:max_downloads]

            grouped = self._filter.group_by_type(filtered)
            stages.append(PipelineStageResult(
                stage="filter", status="completed",
                duration_seconds=time.monotonic() - s2_start,
                data={
                    "total_filtered": len(filtered),
                    "by_type": {k: len(v) for k, v in grouped.items()},
                    "filter_config": {
                        "start_date": start_date,
                        "end_date": end_date,
                        "dataset_types": dataset_types,
                    },
                },
            ))
        except Exception as e:
            stages.append(PipelineStageResult(
                stage="filter", status="failed",
                duration_seconds=time.monotonic() - s2_start,
                error=str(e),
            ))
            return PipelineResult(
                version=version, start_date=start_date, end_date=end_date,
                stages=stages, overall_status="failed",
                total_duration_seconds=time.monotonic() - overall_start,
                error=str(e),
            )

        if not filtered:
            stages.append(PipelineStageResult(
                stage="filter", status="completed",
                duration_seconds=time.monotonic() - s2_start,
                data={"total_filtered": 0, "note": "No matching files found"}
            ))
            return PipelineResult(
                version=version, start_date=start_date, end_date=end_date,
                stages=stages, overall_status="completed",
                total_duration_seconds=time.monotonic() - overall_start,
            )

        # Stage 3: Download
        s3_start = time.monotonic()
        try:
            download_results: list[GDELTDownloadResult] = await self._downloader.download_batch(
                entries=filtered,
                version=version,
            )
            completed_dl = sum(1 for r in download_results if r.status == "completed")
            failed_dl = sum(1 for r in download_results if r.status == "failed")
            stages.append(PipelineStageResult(
                stage="download", status="completed" if failed_dl == 0 else "partial",
                duration_seconds=time.monotonic() - s3_start,
                data={
                    "total": len(download_results),
                    "completed": completed_dl,
                    "failed": failed_dl,
                    "total_bytes": sum(r.total_size_bytes for r in download_results),
                    "results": [
                        {"url": r.url, "status": r.status, "error": r.error}
                        for r in download_results
                    ],
                },
            ))
        except Exception as e:
            stages.append(PipelineStageResult(
                stage="download", status="failed",
                duration_seconds=time.monotonic() - s3_start,
                error=str(e),
            ))
            return PipelineResult(
                version=version, start_date=start_date, end_date=end_date,
                stages=stages, overall_status="failed",
                total_duration_seconds=time.monotonic() - overall_start,
                error=str(e),
            )

        # Stage 4: Decompress + Parse
        s4_start = time.monotonic()
        try:
            extracted_files: list[Path] = []
            for dr in download_results:
                if dr.status == "completed":
                    for fp in dr.files:
                        if "".join(fp.suffixes).lower().endswith(".zip"):
                            extract_dir = fp.parent / "_extracted"
                            extract_dir.mkdir(parents=True, exist_ok=True)
                            with zipfile.ZipFile(fp, "r") as zf:
                                zf.extractall(extract_dir)
                            for child in extract_dir.iterdir():
                                if child.is_file():
                                    extracted_files.append(child)
                        else:
                            extracted_files.append(fp)

            files_by_type: dict[str, list[Path]] = {}
            for fp in extracted_files:
                ext = self._ext_to_ds_type("".join(fp.suffixes))
                if ext in ("events", "mentions", "gkg"):
                    files_by_type.setdefault(ext, []).append(fp)

            parse_results: list[GDELTParserResult] = []
            for ds_type, file_list in files_by_type.items():
                for fp in file_list:
                    pr = await self._parser.parse_file(
                        input_path=fp,
                        dataset_type=ds_type,
                        version=version,
                        max_records=max_parse_records,
                    )
                    parse_results.append(pr)

            total_parsed = sum(r.records_parsed for r in parse_results)
            total_failed = sum(r.records_failed for r in parse_results)
            stages.append(PipelineStageResult(
                stage="parse", status="completed",
                duration_seconds=time.monotonic() - s4_start,
                data={
                    "total_files": len(parse_results),
                    "records_parsed": total_parsed,
                    "records_failed": total_failed,
                    "canonical_valid": sum(r.canonical_valid for r in parse_results),
                    "canonical_invalid": sum(r.canonical_invalid for r in parse_results),
                    "results": [
                        {"source": r.source, "records": r.records_parsed, "failed": r.records_failed}
                        for r in parse_results
                    ],
                },
            ))
        except Exception as e:
            stages.append(PipelineStageResult(
                stage="parse", status="failed",
                duration_seconds=time.monotonic() - s4_start,
                error=str(e),
            ))
            return PipelineResult(
                version=version, start_date=start_date, end_date=end_date,
                stages=stages, overall_status="failed",
                total_duration_seconds=time.monotonic() - overall_start,
                error=str(e),
            )

        # Stage 5: Register
        s5_start = time.monotonic()
        try:
            reg_batch: GDELTRegistrationBatch = await self._registration.register_batch(
                parser_results=parse_results,
                version=version,
            )
            stages.append(PipelineStageResult(
                stage="register", status="completed" if reg_batch.total_failed == 0 else "partial",
                duration_seconds=time.monotonic() - s5_start,
                data={
                    "total": reg_batch.total_registered + reg_batch.total_failed,
                    "registered": reg_batch.total_registered,
                    "failed": reg_batch.total_failed,
                    "results": {
                        k: {
                            "status": r.status,
                            "dataset_name": r.dataset_name,
                            "records_parsed": r.records_parsed,
                            "records_failed": r.records_failed,
                            "error": r.error,
                        }
                        for k, r in reg_batch.results.items()
                    },
                },
            ))
        except Exception as e:
            stages.append(PipelineStageResult(
                stage="register", status="failed",
                duration_seconds=time.monotonic() - s5_start,
                error=str(e),
            ))
            return PipelineResult(
                version=version, start_date=start_date, end_date=end_date,
                stages=stages, overall_status="failed",
                total_duration_seconds=time.monotonic() - overall_start,
                error=str(e),
            )

        total_duration = time.monotonic() - overall_start
        failure_count = sum(1 for s in stages if s.status == "failed")
        overall_status = "completed" if failure_count == 0 else "partial"

        return PipelineResult(
            version=version,
            start_date=start_date,
            end_date=end_date,
            stages=stages,
            overall_status=overall_status,
            total_duration_seconds=total_duration,
        )

    def _ext_to_ds_type(self, suffixes: str) -> str:
        if "export" in suffixes or "events" in suffixes:
            return "events"
        if "mentions" in suffixes:
            return "mentions"
        if "gkg" in suffixes:
            return "gkg"
        return "other"

    def _ext_to_type(self, path: str) -> str:
        pl = path.lower()
        if "export" in pl or "events" in pl:
            return "events"
        if "mentions" in pl:
            return "mentions"
        if "gkg" in pl:
            return "gkg"
        return "other"
