from __future__ import annotations

import asyncio
import csv
import gzip
import hashlib
import json
import tarfile
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiohttp

from backend.shared.logging_config import get_logger
from data_acquisition.config import DataAcquisitionConfig, get_config
from data_acquisition.lake import DataLake, DataLakeConfig

logger = get_logger(__name__)


@dataclass
class DownloadConfig:
    source: str
    version: str
    url: str | None = None
    output_dir: str | None = None
    max_retries: int = 3
    retry_delay: float = 5.0
    chunk_size: int = 8192
    verify_checksum: bool = True
    expected_checksum: str | None = None
    decompress: bool = True
    preserve_archive: bool = False
    timeout: int = 300
    headers: dict = field(default_factory=dict)


@dataclass
class DownloadResult:
    source: str
    version: str
    status: str
    files: list[Path]
    total_size_bytes: int
    checksum: str
    download_duration_seconds: float
    retries: int
    error: str | None = None


class DownloadManager:
    def __init__(
        self,
        config: DataAcquisitionConfig | None = None,
        data_lake: DataLake | None = None,
    ) -> None:
        self._config = config or get_config()
        self._data_lake = data_lake or DataLake(
            DataLakeConfig(base_dir=self._config.base_dir)
        )
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def download(self, config: DownloadConfig) -> DownloadResult:
        start_time = time.monotonic()
        retries = 0
        result_files: list[Path] = []
        total_bytes = 0
        checksum = ""
        error: str | None = None
        status = "completed"

        if not config.url:
            return DownloadResult(
                source=config.source,
                version=config.version,
                status="failed",
                files=[],
                total_size_bytes=0,
                checksum="",
                download_duration_seconds=0.0,
                retries=0,
                error="No URL specified",
            )

        version_dir = await self._data_lake.create_version_dir(
            config.source, config.version
        )
        output_path = version_dir / self._filename_from_url(config.url)
        session = await self._get_session()

        last_exception: Exception | None = None
        while retries <= config.max_retries:
            try:
                initial_offset = output_path.stat().st_size if output_path.exists() else 0
                total_bytes = await self.download_with_resume(
                    url=config.url,
                    output_path=output_path,
                    headers=config.headers,
                    chunk_size=config.chunk_size,
                    initial_offset=initial_offset,
                    timeout=config.timeout,
                )
                last_exception = None
                break
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as e:
                last_exception = e
                retries += 1
                if retries <= config.max_retries:
                    wait = config.retry_delay * (2 ** (retries - 1))
                    logger.warning(
                        "download failed, retrying",
                        url=config.url,
                        attempt=retries,
                        max_retries=config.max_retries,
                        wait=wait,
                        error=str(e),
                    )
                    await asyncio.sleep(wait)
                else:
                    error = str(e)
                    status = "failed"

        if last_exception and not error:
            error = str(last_exception)
            status = "failed"

        if status != "failed" and output_path.exists():
            checksum = await self.compute_checksum(output_path)

            if config.verify_checksum and config.expected_checksum:
                valid = await self.verify_checksum(
                    output_path, config.expected_checksum
                )
                if not valid:
                    logger.error(
                        "checksum mismatch",
                        url=config.url,
                        expected=config.expected_checksum,
                        actual=checksum,
                    )
                    status = "partial"

            if config.decompress:
                try:
                    extracted = await self.decompress(
                        output_path, version_dir, config.preserve_archive
                    )
                    result_files.extend(extracted)
                    if not config.preserve_archive:
                        output_path.unlink(missing_ok=True)
                except (tarfile.TarError, zipfile.BadZipFile, gzip.BadGzipFile, ValueError) as e:
                    logger.error("decompression failed", path=str(output_path), error=str(e))
                    result_files.append(output_path)
            else:
                result_files.append(output_path)

            total_bytes = sum(
                f.stat().st_size for f in result_files if f.exists()
            )
        elif output_path.exists():
            total_bytes = output_path.stat().st_size
            result_files.append(output_path)
            checksum = await self.compute_checksum(output_path)

        if total_bytes == 0 and status != "failed":
            status = "skipped"

        elapsed = time.monotonic() - start_time

        result = DownloadResult(
            source=config.source,
            version=config.version,
            status=status,
            files=result_files,
            total_size_bytes=total_bytes,
            checksum=checksum,
            download_duration_seconds=elapsed,
            retries=retries,
            error=error,
        )

        await self._write_metadata(version_dir, config, result)
        return result

    async def download_with_resume(
        self,
        url: str,
        output_path: Path,
        headers: dict | None = None,
        chunk_size: int = 8192,
        initial_offset: int = 0,
        timeout: int = 300,
    ) -> int:
        session = await self._get_session()
        request_headers = dict(headers or {})

        if initial_offset > 0:
            supports = await self.check_resume_support(url)
            if supports:
                request_headers["Range"] = f"bytes={initial_offset}-"
            else:
                initial_offset = 0
                logger.info("server does not support resume, downloading from start", url=url)

        mode = "ab" if initial_offset > 0 else "wb"
        total_downloaded = initial_offset

        async with session.get(
            url, headers=request_headers, timeout=aiohttp.ClientTimeout(total=timeout)
        ) as resp:
            resp.raise_for_status()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, mode) as f:
                async for chunk in resp.content.iter_chunked(chunk_size):
                    f.write(chunk)
                    total_downloaded += len(chunk)

        return total_downloaded

    async def verify_checksum(
        self, file_path: Path, expected: str, algorithm: str = "sha256"
    ) -> bool:
        actual = await self.compute_checksum(file_path, algorithm)
        return actual.lower() == expected.lower()

    async def compute_checksum(
        self, file_path: Path, algorithm: str = "sha256"
    ) -> str:
        h = hashlib.new(algorithm)
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    async def decompress(
        self, file_path: Path, output_dir: Path, preserve: bool = False
    ) -> list[Path]:
        suffix = "".join(file_path.suffixes).lower()

        if suffix.endswith(".zip") or suffix == ".zip":
            return await self.extract_archive(file_path, output_dir, preserve)

        if suffix.endswith(".tar.gz") or suffix.endswith(".tgz"):
            return await self._extract_tar(file_path, output_dir, "gz", preserve)
        if suffix.endswith(".tar.bz2"):
            return await self._extract_tar(file_path, output_dir, "bz2", preserve)
        if suffix.endswith(".tar"):
            return await self._extract_tar(file_path, output_dir, "", preserve)

        if suffix.endswith(".gz"):
            return await self._decompress_gzip(file_path, output_dir, preserve)
        if suffix.endswith(".bz2"):
            return await self._decompress_bz2(file_path, output_dir, preserve)

        logger.info("no decompression needed for file", path=str(file_path))
        return [file_path]

    async def extract_archive(
        self, archive_path: Path, output_dir: Path, preserve: bool = False
    ) -> list[Path]:
        suffix = "".join(archive_path.suffixes).lower()

        if suffix.endswith(".zip") or suffix == ".zip":
            return await self._extract_zip(archive_path, output_dir, preserve)
        if suffix.endswith(".tar.gz") or suffix.endswith(".tgz"):
            return await self._extract_tar(archive_path, output_dir, "gz", preserve)
        if suffix.endswith(".tar.bz2"):
            return await self._extract_tar(archive_path, output_dir, "bz2", preserve)
        if suffix.endswith(".tar"):
            return await self._extract_tar(archive_path, output_dir, "", preserve)

        raise ValueError(f"Unsupported archive format: {suffix}")

    async def _extract_zip(
        self, zip_path: Path, output_dir: Path, preserve: bool
    ) -> list[Path]:
        extracted: list[Path] = []
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(output_dir)
            for name in zf.namelist():
                target = output_dir / name
                if target.is_file():
                    extracted.append(target)
        if not preserve:
            zip_path.unlink(missing_ok=True)
        logger.info("extracted zip archive", path=str(zip_path), files=len(extracted))
        return extracted

    async def _extract_tar(
        self, tar_path: Path, output_dir: Path, compression: str, preserve: bool
    ) -> list[Path]:
        mode = f"r:{compression}" if compression else "r"
        extracted: list[Path] = []
        with tarfile.open(tar_path, mode) as tf:
            tf.extractall(output_dir)
            for member in tf.getmembers():
                if member.isfile():
                    extracted.append(output_dir / member.name)
        if not preserve:
            tar_path.unlink(missing_ok=True)
        logger.info("extracted tar archive", path=str(tar_path), files=len(extracted))
        return extracted

    async def _decompress_gzip(
        self, gz_path: Path, output_dir: Path, preserve: bool
    ) -> list[Path]:
        output_path = output_dir / gz_path.stem
        with gzip.open(gz_path, "rb") as gz:
            data = gz.read()
        with open(output_path, "wb") as f:
            f.write(data)
        if not preserve:
            gz_path.unlink(missing_ok=True)
        logger.info("decompressed gzip", path=str(gz_path), output=str(output_path))
        return [output_path]

    async def _decompress_bz2(
        self, bz2_path: Path, output_dir: Path, preserve: bool
    ) -> list[Path]:
        import bz2
        output_path = output_dir / bz2_path.stem
        with bz2.open(bz2_path, "rb") as bz:
            data = bz.read()
        with open(output_path, "wb") as f:
            f.write(data)
        if not preserve:
            bz2_path.unlink(missing_ok=True)
        logger.info("decompressed bz2", path=str(bz2_path), output=str(output_path))
        return [output_path]

    async def get_remote_file_size(
        self, url: str, headers: dict | None = None
    ) -> int:
        session = await self._get_session()
        async with session.head(url, headers=headers) as resp:
            resp.raise_for_status()
            length = resp.headers.get("Content-Length")
            if length is None:
                raise ValueError("Content-Length header not present in HEAD response")
            return int(length)

    async def check_resume_support(self, url: str) -> bool:
        session = await self._get_session()
        async with session.head(url) as resp:
            accept_ranges = resp.headers.get("Accept-Ranges", "")
            return accept_ranges.lower() == "bytes"

    async def list_local_versions(self, source: str) -> list[dict]:
        return await self._data_lake.list_versions(source)

    async def clean_old_versions(self, source: str, keep_last: int = 3) -> None:
        versions = await self._data_lake.list_versions(source)
        versions.sort(key=lambda v: v["version"], reverse=True)
        to_remove = versions[keep_last:]
        for v in to_remove:
            p = Path(v["path"])
            if p.exists():
                for f in p.rglob("*"):
                    if f.is_file():
                        f.unlink()
                for d in sorted(p.rglob("*"), key=lambda x: len(str(x)), reverse=True):
                    if d.is_dir():
                        try:
                            d.rmdir()
                        except OSError:
                            pass
                try:
                    p.rmdir()
                except OSError:
                    pass
                logger.info(
                    "removed old version",
                    source=source,
                    version=v["version"],
                )

    async def get_download_history(self, source: str) -> list[dict]:
        history: list[dict] = []
        history_path = self._data_lake.raw_dir / source / "_download_history.json"
        if history_path.exists():
            with open(history_path) as f:
                history = json.load(f)
        return history

    async def _write_metadata(
        self, version_dir: Path, config: DownloadConfig, result: DownloadResult
    ) -> None:
        meta = {
            "source": config.source,
            "version": config.version,
            "url": config.url,
            "downloaded_at": datetime.utcnow().isoformat(),
            "status": result.status,
            "total_size_bytes": result.total_size_bytes,
            "checksum": result.checksum,
            "download_duration_seconds": result.download_duration_seconds,
            "retries": result.retries,
            "error": result.error,
            "files": [str(f) for f in result.files],
        }
        meta_path = version_dir / "_metadata.json"
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

        history_path = self._data_lake.raw_dir / config.source / "_download_history.json"
        history_path.parent.mkdir(parents=True, exist_ok=True)
        history: list[dict] = []
        if history_path.exists():
            with open(history_path) as f:
                history = json.load(f)
        history.append({
            "version": config.version,
            "url": config.url,
            "status": result.status,
            "downloaded_at": meta["downloaded_at"],
            "total_size_bytes": result.total_size_bytes,
            "checksum": result.checksum,
        })
        with open(history_path, "w") as f:
            json.dump(history, f, indent=2)

    def _filename_from_url(self, url: str) -> str:
        parsed = urlparse(url)
        path = parsed.path
        name = path.rstrip("/").split("/")[-1] if path else "download"
        return name or "download"

    async def __aenter__(self) -> DownloadManager:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
