from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from data_acquisition.manifest import ManifestGenerator
from data_acquisition.registration import DatasetRegistrationPipeline, DatasetRegistrationResult


@dataclass
class GDELTRegistrationResult:
    dataset_name: str
    version: str
    status: str
    records_parsed: int
    records_failed: int
    registration: DatasetRegistrationResult | None = None
    manifest_path: Path | None = None
    error: str | None = None


@dataclass
class GDELTRegistrationBatch:
    results: dict[str, GDELTRegistrationResult]
    total_registered: int
    total_failed: int


class GDELTRegistration:
    def __init__(self) -> None:
        self._pipeline = DatasetRegistrationPipeline()
        self._manifest_gen = ManifestGenerator()

    async def register_parsed_dataset(
        self,
        dataset_type: str,
        version: str,
        csv_path: Path,
    ) -> GDELTRegistrationResult:
        dataset_name = f"gdelt-{dataset_type}-{version}"

        try:
            result = await self._pipeline.register_dataset(
                dataset_name=dataset_name,
                source=dataset_type,
                version=version,
                processed_path=csv_path,
            )

            return GDELTRegistrationResult(
                dataset_name=dataset_name,
                version=version,
                status=result.status,
                records_parsed=0,
                records_failed=0,
                registration=result,
                manifest_path=result.manifest_path if result.status == "registered" else None,
                error=result.error,
            )

        except Exception as e:
            return GDELTRegistrationResult(
                dataset_name=dataset_name,
                version=version,
                status="failed",
                records_parsed=0,
                records_failed=0,
                error=str(e),
            )

    async def register_batch(
        self,
        parser_results: list,
        version: str,
    ) -> GDELTRegistrationBatch:
        results: dict[str, GDELTRegistrationResult] = {}
        total_registered = 0
        total_failed = 0

        for pr in parser_results:
            ds_type = self._infer_ds_type(pr.source)
            reg_result = await self.register_parsed_dataset(
                dataset_type=ds_type,
                version=version,
                csv_path=pr.output_path,
            )
            reg_result.records_parsed = pr.records_parsed
            reg_result.records_failed = pr.records_failed

            results[ds_type] = reg_result
            if reg_result.status == "registered":
                total_registered += 1
            else:
                total_failed += 1

        return GDELTRegistrationBatch(
            results=results,
            total_registered=total_registered,
            total_failed=total_failed,
        )

    def _infer_ds_type(self, source: str) -> str:
        if "events" in source:
            return "events"
        if "mention" in source:
            return "mentions"
        if "gkg" in source:
            return "gkg"
        return source
