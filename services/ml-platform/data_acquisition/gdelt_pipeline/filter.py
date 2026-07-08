from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from data_acquisition.gdelt_pipeline.master_file_reader import MasterFileEntry


@dataclass
class FilterConfig:
    start_date: str | None = None
    end_date: str | None = None
    dataset_types: list[str] | None = field(
        default_factory=lambda: ["export.CSV.zip", "mentions.CSV.zip", "gkg.csv.zip"]
    )


class GDELTFilter:
    @staticmethod
    def _normalize_ds_type(ext: str) -> str:
        mapping = {
            "export.CSV.zip": "events",
            "mentions.CSV.zip": "mentions",
            "gkg.csv.zip": "gkg",
        }
        return mapping.get(ext, ext)

    def filter(
        self,
        entries: list[MasterFileEntry],
        config: FilterConfig,
    ) -> list[MasterFileEntry]:
        results: list[MasterFileEntry] = []

        start_date_str: str | None = None
        end_date_str: str | None = None

        if config.start_date:
            try:
                d = date.fromisoformat(config.start_date)
                start_date_str = d.strftime("%Y%m%d")
            except ValueError:
                start_date_str = config.start_date.replace("-", "")

        if config.end_date:
            try:
                d = date.fromisoformat(config.end_date)
                end_date_str = d.strftime("%Y%m%d")
            except ValueError:
                end_date_str = config.end_date.replace("-", "")

        for entry in entries:
            if config.dataset_types is not None:
                if entry.dataset_type not in config.dataset_types:
                    continue

            if start_date_str is not None and entry.date_str < start_date_str:
                continue
            if end_date_str is not None and entry.date_str > end_date_str:
                continue

            results.append(entry)

        return results

    def group_by_type(
        self, entries: list[MasterFileEntry]
    ) -> dict[str, list[MasterFileEntry]]:
        grouped: dict[str, list[MasterFileEntry]] = {}
        for entry in entries:
            key = entry.dataset_type
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(entry)
        return grouped
