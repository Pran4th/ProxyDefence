import gzip
import hashlib
import zipfile
from pathlib import Path
from dataclasses import asdict

import pytest

from data_acquisition.download_manager import DownloadConfig, DownloadResult, DownloadManager
from data_acquisition.config import DataAcquisitionConfig


class TestDownloadConfig:
    def test_default_values(self):
        cfg = DownloadConfig(source="test_src", version="v1")
        assert cfg.source == "test_src"
        assert cfg.version == "v1"
        assert cfg.url is None
        assert cfg.max_retries == 3
        assert cfg.retry_delay == 5.0
        assert cfg.chunk_size == 8192
        assert cfg.verify_checksum is True
        assert cfg.decompress is True
        assert cfg.preserve_archive is False
        assert cfg.timeout == 300
        assert cfg.headers == {}

    def test_full_config(self):
        cfg = DownloadConfig(
            source="eia",
            version="2025-01",
            url="https://api.eia.gov/data.csv",
            max_retries=5,
            decompress=False,
            expected_checksum="abc",
            headers={"Authorization": "Bearer test"},
        )
        assert cfg.expected_checksum == "abc"
        assert cfg.headers == {"Authorization": "Bearer test"}

    def test_output_dir_none_by_default(self):
        cfg = DownloadConfig(source="src", version="1")
        assert cfg.output_dir is None


class TestDownloadResult:
    def test_default_fields(self):
        result = DownloadResult(
            source="src",
            version="1",
            status="completed",
            files=[],
            total_size_bytes=0,
            checksum="",
            download_duration_seconds=0.0,
            retries=0,
        )
        assert result.error is None
        assert result.status == "completed"

    def test_with_error(self):
        result = DownloadResult(
            source="src",
            version="1",
            status="failed",
            files=[],
            total_size_bytes=0,
            checksum="",
            download_duration_seconds=1.5,
            retries=2,
            error="Connection timeout",
        )
        assert result.error == "Connection timeout"

    def test_fields_are_mutable(self):
        result = DownloadResult(
            source="s", version="v", status="partial", files=[],
            total_size_bytes=100, checksum="chk", download_duration_seconds=0.5, retries=1,
        )
        assert result.total_size_bytes == 100

    def test_partial_status(self):
        result = DownloadResult(
            source="s", version="v", status="partial", files=[],
            total_size_bytes=50, checksum="", download_duration_seconds=0.1, retries=0,
        )
        assert result.status == "partial"


class TestDownloadManager:
    @pytest.fixture
    def manager(self, tmp_path):
        cfg = DataAcquisitionConfig(base_dir=str(tmp_path / "daclient"))
        return DownloadManager(config=cfg)

    @pytest.mark.asyncio
    async def test_constructor_defaults(self):
        dm = DownloadManager()
        assert dm._config is not None
        assert dm._data_lake is not None
        await dm.close()

    @pytest.mark.asyncio
    async def test_constructor_custom_config(self, tmp_path):
        cfg = DataAcquisitionConfig(base_dir=str(tmp_path / "custom"))
        dm = DownloadManager(config=cfg)
        assert dm._config.base_dir == str(tmp_path / "custom")
        await dm.close()

    @pytest.mark.asyncio
    async def test_compute_checksum_sha256(self, manager, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        cs = await manager.compute_checksum(f)
        expected = hashlib.sha256(b"hello world").hexdigest()
        assert cs == expected

    @pytest.mark.asyncio
    async def test_compute_checksum_different_algorithm(self, manager, tmp_path):
        f = tmp_path / "test_md5.txt"
        f.write_text("data")
        cs = await manager.compute_checksum(f, algorithm="md5")
        assert len(cs) == 32

    @pytest.mark.asyncio
    async def test_compute_checksum_empty_file(self, manager, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("")
        cs = await manager.compute_checksum(f)
        assert cs == hashlib.sha256(b"").hexdigest()

    @pytest.mark.asyncio
    async def test_verify_checksum_match(self, manager, tmp_path):
        f = tmp_path / "verify_ok.txt"
        f.write_text("verify me")
        expected = hashlib.sha256(b"verify me").hexdigest()
        result = await manager.verify_checksum(f, expected)
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_checksum_mismatch(self, manager, tmp_path):
        f = tmp_path / "verify_bad.txt"
        f.write_text("content")
        result = await manager.verify_checksum(f, "0000000000000000000000000000000000000000000000000000000000000000")
        assert result is False

    @pytest.mark.asyncio
    async def test_verify_checksum_case_insensitive(self, manager, tmp_path):
        f = tmp_path / "case_test.txt"
        f.write_text("test")
        cs = await manager.compute_checksum(f)
        result = await manager.verify_checksum(f, cs.upper())
        assert result is True

    @pytest.mark.asyncio
    async def test_decompress_gzip(self, manager, tmp_path):
        original = b"hello, this is test data\nline2\n"
        gz_path = tmp_path / "data.txt.gz"
        with gzip.open(gz_path, "wb") as gz:
            gz.write(original)

        output_dir = tmp_path / "out"
        output_dir.mkdir()
        files = await manager.decompress(gz_path, output_dir, preserve=False)
        assert len(files) == 1
        decompressed = files[0]
        assert decompressed.read_bytes() == original
        assert not gz_path.exists()

    @pytest.mark.asyncio
    async def test_decompress_gzip_preserve(self, manager, tmp_path):
        gz_path = tmp_path / "keep.txt.gz"
        with gzip.open(gz_path, "wb") as gz:
            gz.write(b"preserve me")
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        files = await manager.decompress(gz_path, output_dir, preserve=True)
        assert len(files) == 1
        assert gz_path.exists()

    @pytest.mark.asyncio
    async def test_extract_archive_zip(self, manager, tmp_path):
        zip_path = tmp_path / "archive.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("file1.txt", "content1")
            zf.writestr("sub/file2.txt", "content2")
        output_dir = tmp_path / "extracted"
        output_dir.mkdir()
        files = await manager.extract_archive(zip_path, output_dir, preserve=False)
        assert len(files) >= 2
        assert (output_dir / "file1.txt").exists()
        assert (output_dir / "sub" / "file2.txt").exists()
        assert not zip_path.exists()

    @pytest.mark.asyncio
    async def test_extract_archive_zip_preserve(self, manager, tmp_path):
        zip_path = tmp_path / "keep.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("data.csv", "a,b\n1,2\n")
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        files = await manager.extract_archive(zip_path, output_dir, preserve=True)
        assert len(files) == 1
        assert zip_path.exists()

    @pytest.mark.asyncio
    async def test_decompress_noop_for_unknown_suffix(self, manager, tmp_path):
        f = tmp_path / "unknown.xyz"
        f.write_text("plain data")
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        files = await manager.decompress(f, output_dir)
        assert files == [f]

    @pytest.mark.asyncio
    async def test_extract_archive_unsupported_raises(self, manager, tmp_path):
        f = tmp_path / "bad.rar"
        f.write_text("fake rar")
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        with pytest.raises(ValueError, match="Unsupported archive format"):
            await manager.extract_archive(f, output_dir)

    @pytest.mark.asyncio
    async def test_download_no_url_fails_immediately(self, manager):
        cfg = DownloadConfig(source="test", version="v1", url=None)
        result = await manager.download(cfg)
        assert result.status == "failed"
        assert result.error == "No URL specified"
        assert result.files == []
        assert result.total_size_bytes == 0

    @pytest.mark.asyncio
    async def test_filename_from_url(self, manager):
        name = manager._filename_from_url("https://example.com/data/file.csv")
        assert name == "file.csv"

    @pytest.mark.asyncio
    async def test_filename_from_url_no_path(self, manager):
        name = manager._filename_from_url("https://example.com")
        assert name == "download"

    @pytest.mark.asyncio
    async def test_filename_from_url_trailing_slash(self, manager):
        name = manager._filename_from_url("https://example.com/data/")
        assert name != ""

    @pytest.mark.asyncio
    async def test_list_local_versions_empty(self, manager, tmp_path):
        versions = await manager.list_local_versions("nonexistent_source")
        assert versions == []

    @pytest.mark.asyncio
    async def test_download_history_empty(self, manager, tmp_path):
        history = await manager.get_download_history("nosource")
        assert history == []

    @pytest.mark.asyncio
    async def test_clean_old_versions_noop_when_fewer(self, manager, tmp_path):
        await manager._data_lake.ensure_directories()
        await manager.clean_old_versions("ghost", keep_last=3)

    @pytest.mark.asyncio
    async def test_decompress_gzip_large_content(self, manager, tmp_path):
        content = b"x" * 100000
        gz_path = tmp_path / "large.txt.gz"
        with gzip.open(gz_path, "wb") as gz:
            gz.write(content)
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        files = await manager.decompress(gz_path, output_dir)
        assert files[0].stat().st_size == 100000

    @pytest.mark.asyncio
    async def test_close_manager(self):
        dm = DownloadManager()
        await dm.close()
        assert dm._session is None or dm._session.closed
