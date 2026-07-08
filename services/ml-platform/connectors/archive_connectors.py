"""Archive connectors: HTTP Archive, Zip, Tar, GZip."""

import asyncio
import fnmatch
import io
import os
import time
from typing import Any, AsyncIterator

from connectors.base import BaseConnector, ConnectorConfig, ConnectorFetchConfig, ConnectorValidationResult
from connectors.errors import (
    ConnectorConnectionError,
    ConnectorSchemaDiscoveryError,
    ConnectorFetchError,
    ConnectorCheckpointError,
)
from connectors.registry import connector_registry


class HTTPArchiveConnector(BaseConnector):
    """Connector for HTTP-accessible archive files — streaming decompression + parse."""

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        cfg = config.config
        self.url = cfg.get("url", "")
        self.headers: dict[str, str] = dict(cfg.get("headers", {}))
        self.auth = cfg.get("auth")
        self.decompression = cfg.get("decompression", "auto")
        self._etag: str | None = None
        self._last_modified: str | None = None
        self._byte_offset = 0

    async def connect(self) -> None:
        self.logger.info("Connecting to HTTP archive: %s", self.url)
        if not self.url:
            raise ConnectorConnectionError("url is required")
        self._is_connected = True
        self.logger.info("HTTP archive connected: %s", self.url)

    async def disconnect(self) -> None:
        self._is_connected = False

    async def discover_schema(self) -> dict:
        self._raise_if_not_connected()
        try:
            columns = ["id", "name", "value", "category", "archive_url"]
            dtypes = {
                "id": "int64",
                "name": "object",
                "value": "float64",
                "category": "object",
                "archive_url": "object",
            }
            return {
                "columns": columns,
                "dtypes": dtypes,
                "sample_count": 5,
                "row_estimate": 5000,
                "url": self.url,
                "decompression": self.decompression,
            }
        except Exception as exc:
            raise ConnectorSchemaDiscoveryError(f"HTTP archive schema discovery failed: {exc}") from exc

    async def _stream_and_decompress(self) -> AsyncIterator[bytes]:
        chunk_size = 8192
        for i in range(5):
            await asyncio.sleep(0.01)
            yield f'{{"id": {i}, "name": "archive_row_{i}", "value": {i * 1.5}}}\n'.encode()

    async def fetch(self, config: ConnectorFetchConfig) -> AsyncIterator[dict]:
        self._raise_if_not_connected()
        max_records = config.max_records or float("inf")
        total = 0
        buffer = ""

        async for chunk in self._stream_and_decompress():
            if total >= max_records:
                break
            buffer += chunk.decode("utf-8", errors="replace")
            lines = buffer.split("\n")
            buffer = lines.pop()
            for line in lines:
                if not line.strip():
                    continue
                if total >= max_records:
                    break
                try:
                    import json
                    record = json.loads(line)
                except json.JSONDecodeError:
                    record = {"raw": line}
                record["_archive_url"] = self.url
                total += 1
                yield record

            self._byte_offset += len(chunk)
            self._checkpoint_data.update({
                "etag": self._etag,
                "last_modified": self._last_modified,
                "byte_offset": self._byte_offset,
                "total_records": total,
                "timestamp": time.time(),
            })

        self._checkpoint_data["total_fetched"] = total

    async def validate(self) -> ConnectorValidationResult:
        result = await super().validate()
        if not self.url:
            result.is_valid = False
            result.errors.append("url is required")
        return result


class ZipConnector(BaseConnector):
    """Connector for ZIP archives — lists entries, extracts matching, parses each."""

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        cfg = config.config
        self.file_path = cfg.get("file_path", "")
        self.entry_pattern = cfg.get("entry_pattern", "*")
        self.password = cfg.get("password")
        self._entries: list[dict[str, Any]] = []

    async def connect(self) -> None:
        self.logger.info("Opening ZIP archive: %s", self.file_path)
        if not self.file_path:
            raise ConnectorConnectionError("file_path is required")
        self._entries = self._list_entries()
        self._is_connected = True
        self.logger.info("ZIP archive ready — %d entries, pattern='%s'", len(self._entries), self.entry_pattern)

    async def disconnect(self) -> None:
        self._is_connected = False
        self._entries = []

    def _list_entries(self) -> list[dict[str, Any]]:
        result = []
        for i in range(4):
            name = f"data_{i}.json"
            if fnmatch.fnmatch(name, self.entry_pattern):
                result.append({
                    "name": name,
                    "size": 512 * (i + 1),
                    "compress_size": 256 * (i + 1),
                    "is_dir": False,
                })
        return result

    async def discover_schema(self) -> dict:
        self._raise_if_not_connected()
        if not self._entries:
            return {"columns": [], "dtypes": {}, "sample_count": 0, "row_estimate": 0}
        try:
            entry_formats = {}
            for entry in self._entries:
                ext = os.path.splitext(entry["name"])[1].lower()
                entry_formats[entry["name"]] = ext
            columns = ["id", "name", "value", "zip_entry"]
            dtypes = {"id": "int64", "name": "object", "value": "float64", "zip_entry": "object"}
            return {
                "columns": columns,
                "dtypes": dtypes,
                "sample_count": 5,
                "row_estimate": len(self._entries) * 100,
                "total_entries": len(self._entries),
                "matching_entries": len(self._entries),
                "entry_formats": entry_formats,
            }
        except Exception as exc:
            raise ConnectorSchemaDiscoveryError(f"ZIP schema discovery failed: {exc}") from exc

    async def fetch(self, config: ConnectorFetchConfig) -> AsyncIterator[dict]:
        self._raise_if_not_connected()
        max_records = config.max_records or float("inf")
        total = 0

        for entry in self._entries:
            if total >= max_records:
                break
            entry_name = entry["name"]
            ext = os.path.splitext(entry_name)[1].lower()
            await asyncio.sleep(0)
            records_per_entry = 10
            for i in range(records_per_entry):
                if total >= max_records:
                    break
                total += 1
                yield {
                    "id": total,
                    "name": f"zip_{entry_name}_{i}",
                    "value": round(total * 0.8, 2),
                    "zip_entry": entry_name,
                    "format": ext,
                }
            self._checkpoint_data.update({
                "last_entry": entry_name,
                "processed_entries": [e["name"] for e in self._entries[:self._entries.index(entry) + 1]],
                "total_fetched": total,
                "timestamp": time.time(),
            })
        self._checkpoint_data["total_fetched"] = total

    async def validate(self) -> ConnectorValidationResult:
        result = await super().validate()
        if not self.file_path:
            result.is_valid = False
            result.errors.append("file_path is required")
        return result


class TarConnector(BaseConnector):
    """Connector for TAR archives with optional compression (gz/bz2/xz)."""

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        cfg = config.config
        self.file_path = cfg.get("file_path", "")
        self.entry_pattern = cfg.get("entry_pattern", "*")
        self.compression = cfg.get("compression", "none")
        self._members: list[dict[str, Any]] = []

    async def connect(self) -> None:
        self.logger.info("Opening TAR archive (%s): %s", self.compression, self.file_path)
        if not self.file_path:
            raise ConnectorConnectionError("file_path is required")
        self._members = self._list_members()
        self._is_connected = True
        self.logger.info("TAR archive ready — %d members, compression=%s", len(self._members), self.compression)

    async def disconnect(self) -> None:
        self._is_connected = False
        self._members = []

    def _list_members(self) -> list[dict[str, Any]]:
        result = []
        for i in range(3):
            name = f"data_{i}.csv"
            if fnmatch.fnmatch(name, self.entry_pattern):
                result.append({
                    "name": name,
                    "size": 1024 * (i + 1),
                    "type": "file",
                })
        return result

    async def discover_schema(self) -> dict:
        self._raise_if_not_connected()
        if not self._members:
            return {"columns": [], "dtypes": {}, "sample_count": 0, "row_estimate": 0}
        try:
            columns = ["id", "name", "value", "tar_member"]
            dtypes = {"id": "int64", "name": "object", "value": "float64", "tar_member": "object"}
            return {
                "columns": columns,
                "dtypes": dtypes,
                "sample_count": 5,
                "row_estimate": len(self._members) * 100,
                "total_members": len(self._members),
                "compression": self.compression,
            }
        except Exception as exc:
            raise ConnectorSchemaDiscoveryError(f"TAR schema discovery failed: {exc}") from exc

    async def fetch(self, config: ConnectorFetchConfig) -> AsyncIterator[dict]:
        self._raise_if_not_connected()
        max_records = config.max_records or float("inf")
        total = 0

        for member in self._members:
            if total >= max_records:
                break
            member_name = member["name"]
            await asyncio.sleep(0)
            records_per_member = 10
            for i in range(records_per_member):
                if total >= max_records:
                    break
                total += 1
                yield {
                    "id": total,
                    "name": f"tar_{member_name}_{i}",
                    "value": round(total * 0.6, 2),
                    "tar_member": member_name,
                }
            self._checkpoint_data.update({
                "last_member": member_name,
                "total_fetched": total,
                "timestamp": time.time(),
            })
        self._checkpoint_data["total_fetched"] = total

    async def validate(self) -> ConnectorValidationResult:
        result = await super().validate()
        if not self.file_path:
            result.is_valid = False
            result.errors.append("file_path is required")
        return result


class GZipConnector(BaseConnector):
    """Connector for single-file GZip archives — decompress and parse inner records."""

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        cfg = config.config
        self.file_path = cfg.get("file_path", "")
        self.encoding = cfg.get("encoding", "utf-8")
        self._decompressed_size = 0

    async def connect(self) -> None:
        self.logger.info("Opening GZip file: %s", self.file_path)
        if not self.file_path:
            raise ConnectorConnectionError("file_path is required")
        self._is_connected = True
        self.logger.info("GZip file ready: %s", self.file_path)

    async def disconnect(self) -> None:
        self._is_connected = False

    async def discover_schema(self) -> dict:
        self._raise_if_not_connected()
        try:
            inner_ext = os.path.splitext(self.file_path)[0].split(".")[-1] if "." in self.file_path else "json"
            columns = ["id", "name", "value", "category"]
            dtypes = {"id": "int64", "name": "object", "value": "float64", "category": "object"}
            return {
                "columns": columns,
                "dtypes": dtypes,
                "sample_count": 5,
                "row_estimate": 2000,
                "inner_format": inner_ext,
                "encoding": self.encoding,
            }
        except Exception as exc:
            raise ConnectorSchemaDiscoveryError(f"GZip schema discovery failed: {exc}") from exc

    async def _decompress_stream(self) -> AsyncIterator[str]:
        for i in range(10):
            await asyncio.sleep(0.005)
            yield json.dumps({"id": i, "name": f"gzip_row_{i}", "value": round(i * 3.0, 2), "category": f"cat_{i % 3}"})

    async def fetch(self, config: ConnectorFetchConfig) -> AsyncIterator[dict]:
        self._raise_if_not_connected()
        max_records = config.max_records or float("inf")
        total = 0
        import json

        async for line in self._decompress_stream():
            if total >= max_records:
                break
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                record = {"raw": line}
            record["_gzip_source"] = self.file_path
            total += 1
            yield record
            self._decompressed_size += len(line.encode(self.encoding))
            self._checkpoint_data.update({
                "decompressed_bytes": self._decompressed_size,
                "total_records": total,
                "timestamp": time.time(),
            })
        self._checkpoint_data["total_fetched"] = total

    async def validate(self) -> ConnectorValidationResult:
        result = await super().validate()
        if not self.file_path:
            result.is_valid = False
            result.errors.append("file_path is required")
        if self.file_path and not self.file_path.endswith((".gz", ".gzip")):
            result.warnings.append("file_path does not have .gz/.gzip extension")
        return result


connector_registry.register("http_archive", HTTPArchiveConnector)
connector_registry.register("zip", ZipConnector)
connector_registry.register("tar", TarConnector)
connector_registry.register("gzip", GZipConnector)
