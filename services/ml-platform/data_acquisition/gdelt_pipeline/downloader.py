from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiohttp

from data_acquisition.config import DataAcquisitionConfig, get_config
from data_acquisition.download_manager import DownloadManager, DownloadConfig
from data_acquisition.gdelt_pipeline.master_file_reader import MasterFileEntry
from data_acquisition.lake import DataLake, DataLakeConfig


@dataclass
class GDELTDownloadResult:
    source: str
    version: str
    status: str
    files: list[Path]
    total_size_bytes: int
    checksum: str
    download_duration_seconds: float
    retries: int
    error: str | None = None
    url: str = ""


class GDELTDownloader:
    def __init__(
        self,
        config: DataAcquisitionConfig | None = None,
        data_lake: DataLake | None = None,
    ) -> None:
        self._config = config or get_config()
        self._data_lake = data_lake or DataLake(
            DataLakeConfig(base_dir=self._config.base_dir)
        )

    async def download_batch(
        self,
        entries: list[MasterFileEntry],
        version: str,
        max_concurrent: int = 3,
    ) -> list[GDELTDownloadResult]:
        sem = asyncio.Semaphore(max_concurrent)
        tasks = [self._download_one(entry, version, sem) for entry in entries]
        results = await asyncio.gather(*tasks)
        return list(results)

    async def _download_one(
        self,
        entry: MasterFileEntry,
        version: str,
        sem: asyncio.Semaphore,
    ) -> GDELTDownloadResult:
        async with sem:
            start = time.monotonic()

            ds_type = self._ds_type_map(entry.dataset_type)
            output_dir = self._data_lake.raw_dir / "gdelt" / ds_type / version
            output_dir.mkdir(parents=True, exist_ok=True)

            filename = entry.url.rstrip("/").split("/")[-1]
            output_path = output_dir / filename

            retries = 0
            status = "completed"
            error: str | None = None
            total_bytes = 0
            checksum = ""

            while retries <= self._config.max_retries:
                try:
                    total_bytes = await self._download_with_resume(
                        url=entry.url,
                        output_path=output_path,
                        expected_md5=entry.md5,
                        timeout=300,
                    )
                    checksum = await self._compute_md5(output_path)
                    valid = checksum == entry.md5
                    if not valid:
                        raise ValueError(
                            f"MD5 mismatch: expected {entry.md5}, got {checksum}"
                        )
                    error = None
                    break
                except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError) as e:
                    error = str(e)
                    retries += 1
                    if retries <= self._config.max_retries:
                        wait = self._config.retry_delay * (2 ** (retries - 1))
                        await asyncio.sleep(wait)
                    else:
                        status = "failed"

            if status != "failed" and output_path.exists():
                checksum = await self._compute_md5(output_path)
                total_bytes = output_path.stat().st_size
                if checksum != entry.md5:
                    error = f"MD5 mismatch after download: expected {entry.md5}, got {checksum}"
                    status = "failed"

            elapsed = time.monotonic() - start

            files = [output_path] if output_path.exists() else []

            return GDELTDownloadResult(
                source=f"gdelt-{ds_type}",
                version=version,
                status=status,
                files=files,
                total_size_bytes=total_bytes,
                checksum=checksum,
                download_duration_seconds=elapsed,
                retries=retries,
                error=error,
                url=entry.url,
            )

    async def _download_with_resume(
        self,
        url: str,
        output_path: Path,
        expected_md5: str | None = None,
        timeout: int = 300,
    ) -> int:
        async with aiohttp.ClientSession() as session:
            # Check if file already fully downloaded
            async with session.head(url) as head_resp:
                head_resp.raise_for_status()
                server_size_str = head_resp.headers.get("Content-Length", "0")
                server_size = int(server_size_str) if server_size_str.isdigit() else 0

            if output_path.exists():
                local_size = output_path.stat().st_size
                if server_size > 0 and local_size >= server_size:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    return local_size
                initial_offset = local_size
            else:
                initial_offset = 0

            headers = {}
            mode = "ab" if initial_offset > 0 else "wb"
            if initial_offset > 0:
                accept_ranges = head_resp.headers.get("Accept-Ranges", "")
                if accept_ranges.lower() == "bytes" and initial_offset < server_size:
                    headers["Range"] = f"bytes={initial_offset}-"
                else:
                    output_path.unlink(missing_ok=True)
                    initial_offset = 0
                    mode = "wb"

            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status == 416:
                    output_path.unlink(missing_ok=True)
                    initial_offset = 0
                    mode = "wb"
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as retry_resp:
                        retry_resp.raise_for_status()
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        total = 0
                        with open(output_path, "wb") as f:
                            async for chunk in retry_resp.content.iter_chunked(8192):
                                f.write(chunk)
                                total += len(chunk)
                        return total
                else:
                    resp.raise_for_status()
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    total = initial_offset
                    with open(output_path, mode) as f:
                        async for chunk in resp.content.iter_chunked(8192):
                            f.write(chunk)
                            total += len(chunk)
                    return total

    async def _compute_md5(self, file_path: Path) -> str:
        h = hashlib.md5()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    def _ds_type_map(self, ext: str) -> str:
        mapping = {
            "export.CSV.zip": "events",
            "mentions.CSV.zip": "mentions",
            "gkg.csv.zip": "gkg",
        }
        return mapping.get(ext, "other")
