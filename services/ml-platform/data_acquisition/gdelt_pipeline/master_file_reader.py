from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiohttp

from data_acquisition.config import DataAcquisitionConfig, get_config
from data_acquisition.lake import DataLake, DataLakeConfig

MASTER_FILE_URL = "http://data.gdeltproject.org/gdeltv2/masterfilelist.txt"
MASTER_FILE_LINE_RE = re.compile(
    r"^\s*(\d+)\s+(\S+)\s+(https?://\S+\.(export\.CSV\.zip|mentions\.CSV\.zip|gkg\.csv\.zip))\s*$"
)


URL_DATE_RE = re.compile(r"/(\d{8})\d*\.(export\.CSV\.zip|mentions\.CSV\.zip|gkg\.csv\.zip)$")


@dataclass
class MasterFileEntry:
    record_number: int
    url: str
    md5: str
    date_str: str = ""
    size: int = 0
    dataset_type: str = ""


@dataclass
class MasterFileResult:
    entries: list[MasterFileEntry]
    total_discovered: int
    by_type: dict[str, int]
    earliest: str | None
    latest: str | None
    download_duration_seconds: float
    error: str | None = None


class MasterFileReader:
    def __init__(
        self,
        config: DataAcquisitionConfig | None = None,
        data_lake: DataLake | None = None,
    ) -> None:
        self._config = config or get_config()
        self._data_lake = data_lake or DataLake(
            DataLakeConfig(base_dir=self._config.base_dir)
        )

    async def fetch(self, url: str = MASTER_FILE_URL) -> MasterFileResult:
        import time
        start = time.monotonic()
        entries: list[MasterFileEntry] = []
        by_type: dict[str, int] = {}
        earliest: int | None = None
        latest: int | None = None
        error: str | None = None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                    resp.raise_for_status()
                    text = await resp.text()

            lines = text.strip().splitlines()
            for line in lines:
                line = line.strip()
                match = MASTER_FILE_LINE_RE.match(line)
                if not match:
                    continue

                rec_num = int(match.group(1))
                md5_val = match.group(2)
                url_val = match.group(3)
                ext = match.group(4)

                date_match = URL_DATE_RE.search(url_val)
                date_str = date_match.group(1) if date_match else ""

                entry = MasterFileEntry(
                    record_number=rec_num,
                    url=url_val,
                    md5=md5_val.lower(),
                    date_str=date_str,
                    size=0,
                    dataset_type=ext,
                )
                entries.append(entry)
                by_type[ext] = by_type.get(ext, 0) + 1

                if date_str:
                    if earliest is None or date_str < earliest:
                        earliest = date_str
                    if latest is None or date_str > latest:
                        latest = date_str

        except aiohttp.ClientError as e:
            error = f"Failed to fetch master file list: {e}"
        except Exception as e:
            error = f"Unexpected error: {e}"

        elapsed = time.monotonic() - start

        return MasterFileResult(
            entries=entries,
            total_discovered=len(entries),
            by_type=by_type,
            earliest=earliest,
            latest=latest,
            download_duration_seconds=elapsed,
            error=error,
        )

    @staticmethod
    def format_date(date_str: str) -> str:
        if len(date_str) == 8 and date_str.isdigit():
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        return date_str

    def save_master_file(self, content: str, version: str) -> Path:
        self._data_lake.raw_dir.mkdir(parents=True, exist_ok=True)
        gdelt_dir = self._data_lake.raw_dir / "gdelt"
        gdelt_dir.mkdir(exist_ok=True)
        meta_dir = gdelt_dir / "_meta"
        meta_dir.mkdir(exist_ok=True)
        path = meta_dir / f"masterfile_{version}.txt"
        path.write_text(content, encoding="utf-8")
        return path
