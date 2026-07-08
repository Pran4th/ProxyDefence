from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from data_acquisition.gdelt_pipeline.master_file_reader import MasterFileEntry
from data_acquisition.parser.base import ParseConfig, ParserResult
from data_acquisition.parser.sources.gdelt import (
    GDELTEventParser,
    GDELTMentionParser,
    GKGParser,
)


@dataclass
class GDELTParserResult:
    source: str
    version: str
    records_parsed: int
    records_failed: int
    output_path: Path
    schema_discovered: dict
    columns: list[str]
    row_count: int
    duration_seconds: float
    errors: list[dict] = field(default_factory=list)
    canonical_valid: int = 0
    canonical_invalid: int = 0


class GDELTParser:
    def __init__(self) -> None:
        self._event_parser = GDELTEventParser()
        self._mention_parser = GDELTMentionParser()
        self._gkg_parser = GKGParser()

    async def parse_file(
        self,
        input_path: Path,
        dataset_type: str,
        version: str,
        output_base_dir: Path | None = None,
        max_records: int | None = None,
    ) -> GDELTParserResult:
        if dataset_type == "events":
            parser = self._event_parser
            source_name = "gdelt-events"
        elif dataset_type == "mentions":
            parser = self._mention_parser
            source_name = "gdelt-mentions"
        elif dataset_type == "gkg":
            parser = self._gkg_parser
            source_name = "gdelt-gkg"
        else:
            raise ValueError(f"Unknown dataset_type: {dataset_type}")

        ds_dir = _ds_dir_map(dataset_type)
        if output_base_dir is None:
            from data_acquisition.config import get_config
            from data_acquisition.lake import DataLake, DataLakeConfig
            cfg = get_config()
            lake = DataLake(DataLakeConfig(base_dir=cfg.base_dir))
            output_base_dir = lake.processed_dir / "gdelt" / ds_dir / version

        output_base_dir.mkdir(parents=True, exist_ok=True)
        stem = input_path.stem.replace(".CSV", "").replace(".csv", "")
        output_csv = output_base_dir / f"{stem}.csv"

        parse_config = ParseConfig(
            source=source_name,
            version=version,
            input_path=input_path,
            output_path=output_csv,
            max_records=max_records,
        )

        result = await parser.parse(parse_config)

        canonical_errors = await self._validate_canonical(output_csv)

        return GDELTParserResult(
            source=source_name,
            version=version,
            records_parsed=result.records_parsed,
            records_failed=result.records_failed,
            output_path=output_csv,
            schema_discovered=result.schema_discovered,
            columns=result.columns,
            row_count=result.row_count,
            duration_seconds=result.duration_seconds,
            errors=result.errors,
            canonical_valid=result.records_parsed - len(canonical_errors),
            canonical_invalid=len(canonical_errors),
        )

    async def parse_batch(
        self,
        files_by_type: dict[str, list[Path]],
        version: str,
        max_records: int | None = None,
    ) -> list[GDELTParserResult]:
        results: list[GDELTParserResult] = []
        for ds_type, file_list in files_by_type.items():
            for fpath in file_list:
                result = await self.parse_file(
                    input_path=fpath,
                    dataset_type=ds_type,
                    version=version,
                    max_records=max_records,
                )
                results.append(result)
        return results

    async def _validate_canonical(self, csv_path: Path) -> list[dict]:
        import csv

        from data_acquisition.canonical import CanonicalRecord

        errors: list[dict] = []
        if not csv_path.exists():
            return errors

        required = {"entity_type", "entity_id", "timestamp", "source"}
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row_idx, row in enumerate(reader):
                missing = required - set(row.keys())
                if missing:
                    errors.append({"row": row_idx, "error": f"missing fields: {missing}"})
                    continue
                try:
                    record = CanonicalRecord(**row)
                    record.validate()
                except Exception as e:
                    errors.append({"row": row_idx, "error": str(e)})

        return errors


def _ds_dir_map(dataset_type: str) -> str:
    mapping = {"events": "events", "mentions": "mentions", "gkg": "gkg"}
    return mapping.get(dataset_type, dataset_type)
