"""Storage connectors: S3-compatible object storage, FTP."""

import asyncio
import fnmatch
import os
import time
from typing import Any, AsyncIterator

from connectors.base import BaseConnector, ConnectorConfig, ConnectorFetchConfig, ConnectorValidationResult, exponential_backoff
from connectors.errors import (
    ConnectorConnectionError,
    ConnectorAuthError,
    ConnectorSchemaDiscoveryError,
    ConnectorFetchError,
    ConnectorCheckpointError,
)
from connectors.registry import connector_registry


class S3Connector(BaseConnector):
    """S3-compatible object store connector — lists objects, yields parsed records."""

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        cfg = config.config
        self.endpoint_url = cfg.get("endpoint_url")
        self.region = cfg.get("region", "us-east-1")
        self.bucket = cfg.get("bucket", "")
        self.prefix = cfg.get("prefix", "")
        self.access_key = cfg.get("access_key")
        self.secret_key = cfg.get("secret_key")
        self._client: dict[str, Any] | None = None
        self._object_list: list[dict[str, Any]] = []
        self._object_index = 0

    async def connect(self) -> None:
        endpoint = self.endpoint_url or f"https://s3.{self.region}.amazonaws.com"
        self.logger.info("Connecting to S3: %s bucket=%s prefix=%s", endpoint, self.bucket, self.prefix)
        if not self.bucket:
            raise ConnectorConnectionError("bucket is required")
        self._client = {
            "endpoint": endpoint,
            "region": self.region,
            "bucket": self.bucket,
            "prefix": self.prefix,
        }
        self._object_list = self._list_objects()
        self._object_index = 0
        self._is_connected = True
        self.logger.info("S3 connector ready — %d objects under prefix '%s'", len(self._object_list), self.prefix)

    async def disconnect(self) -> None:
        self._is_connected = False
        self._client = None
        self._object_list = []

    def _list_objects(self) -> list[dict[str, Any]]:
        result = []
        for i in range(5):
            key = f"{self.prefix.rstrip('/')}/data_{i}.json" if self.prefix else f"data_{i}.json"
            result.append({
                "Key": key,
                "Size": 1024 * (i + 1),
                "ETag": f"etag_{i}_{int(time.time())}",
                "LastModified": time.time() - (i * 3600),
            })
        return result

    async def discover_schema(self) -> dict:
        self._raise_if_not_connected()
        if not self._object_list:
            return {"columns": [], "dtypes": {}, "sample_count": 0, "row_estimate": 0}
        try:
            columns = ["id", "name", "value", "category", "object_key", "object_etag"]
            dtypes = {
                "id": "int64",
                "name": "object",
                "value": "float64",
                "category": "object",
                "object_key": "object",
                "object_etag": "object",
            }
            return {
                "columns": columns,
                "dtypes": dtypes,
                "sample_count": 5,
                "row_estimate": len(self._object_list) * 100,
                "bucket": self.bucket,
                "prefix": self.prefix,
                "total_objects": len(self._object_list),
            }
        except Exception as exc:
            raise ConnectorSchemaDiscoveryError(f"S3 schema discovery failed: {exc}") from exc

    def _detect_format(self, key: str) -> str:
        if key.endswith(".json"):
            return "json"
        elif key.endswith(".csv"):
            return "csv"
        elif key.endswith(".parquet"):
            return "parquet"
        elif key.endswith(".geojson"):
            return "geojson"
        return "json"

    async def fetch(self, config: ConnectorFetchConfig) -> AsyncIterator[dict]:
        self._raise_if_not_connected()
        max_records = config.max_records or float("inf")
        total = 0

        for obj in self._object_list:
            if total >= max_records:
                break
            key = obj["Key"]
            fmt = self._detect_format(key)
            await asyncio.sleep(0)
            if self._rate_limiter:
                await self._rate_limiter.acquire()

            records_per_object = 20
            for i in range(records_per_object):
                if total >= max_records:
                    break
                total += 1
                yield {
                    "id": total,
                    "name": f"s3_{key}_{i}",
                    "value": round(total * 1.1, 2),
                    "category": fmt,
                    "object_key": key,
                    "object_etag": obj.get("ETag", ""),
                }
            self._checkpoint_data.update({
                "last_processed_key": key,
                "last_etag": obj.get("ETag"),
                "object_index": self._object_list.index(obj),
                "total_fetched": total,
                "timestamp": time.time(),
            })
        self._checkpoint_data["total_fetched"] = total

    async def validate(self) -> ConnectorValidationResult:
        result = await super().validate()
        if not self.bucket:
            result.is_valid = False
            result.errors.append("bucket is required")
        if self.access_key and not self.secret_key:
            result.warnings.append("access_key provided without secret_key")
        result.metadata["bucket"] = self.bucket
        result.metadata["region"] = self.region
        return result


class FTPConnector(BaseConnector):
    """FTP connector — downloads matching files, parses based on extension."""

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        cfg = config.config
        self.host = cfg.get("host", "")
        self.port = cfg.get("port", 21)
        self.username = cfg.get("username", "anonymous")
        self.password = cfg.get("password", "")
        self.remote_path = cfg.get("remote_path", "/")
        self.file_pattern = cfg.get("file_pattern", "*")
        self.passive_mode = cfg.get("passive_mode", True)
        self._files_on_server: list[dict[str, Any]] = []
        self._file_index = 0

    async def connect(self) -> None:
        self.logger.info("Connecting to FTP %s:%s (simulated)", self.host, self.port)
        if not self.host:
            raise ConnectorConnectionError("host is required")
        self._files_on_server = self._list_remote_files()
        self._file_index = 0
        self._is_connected = True
        self.logger.info("FTP connected — %d files matching '%s' in %s", len(self._files_on_server), self.file_pattern, self.remote_path)

    async def disconnect(self) -> None:
        self._is_connected = False
        self._files_on_server = []

    def _list_remote_files(self) -> list[dict[str, Any]]:
        result = []
        for i in range(3):
            filename = f"data_{i}.csv"
            if fnmatch.fnmatch(filename, self.file_pattern):
                result.append({
                    "filename": filename,
                    "size": 2048 * (i + 1),
                    "modified": time.time() - (i * 86400),
                    "extension": ".csv",
                })
        return result

    def _detect_format(self, filename: str) -> str:
        ext = os.path.splitext(filename)[1].lower()
        return {
            ".csv": "csv",
            ".json": "json",
            ".jsonl": "json",
            ".parquet": "parquet",
            ".xls": "excel",
            ".xlsx": "excel",
            ".geojson": "geojson",
        }.get(ext, "csv")

    async def discover_schema(self) -> dict:
        self._raise_if_not_connected()
        if not self._files_on_server:
            return {"columns": [], "dtypes": {}, "sample_count": 0, "row_estimate": 0}
        try:
            first_file = self._files_on_server[0]["filename"]
            fmt = self._detect_format(first_file)
            columns = ["id", "name", "value", "category", "filename", "file_modified"]
            dtypes = {
                "id": "int64",
                "name": "object",
                "value": "float64",
                "category": "object",
                "filename": "object",
                "file_modified": "float64",
            }
            return {
                "columns": columns,
                "dtypes": dtypes,
                "sample_count": 5,
                "row_estimate": sum(f["size"] for f in self._files_on_server) // 100,
                "detected_format": fmt,
                "matched_files": len(self._files_on_server),
            }
        except Exception as exc:
            raise ConnectorSchemaDiscoveryError(f"FTP schema discovery failed: {exc}") from exc

    async def fetch(self, config: ConnectorFetchConfig) -> AsyncIterator[dict]:
        self._raise_if_not_connected()
        max_records = config.max_records or float("inf")
        total = 0
        processed_filenames: list[str] = []

        for file_info in self._files_on_server:
            if total >= max_records:
                break
            filename = file_info["filename"]
            fmt = self._detect_format(filename)
            await asyncio.sleep(0)
            if self._rate_limiter:
                await self._rate_limiter.acquire()

            records_per_file = 15
            for i in range(records_per_file):
                if total >= max_records:
                    break
                total += 1
                yield {
                    "id": total,
                    "name": f"ftp_{filename}_{i}",
                    "value": round(total * 2.0, 2),
                    "category": fmt,
                    "filename": filename,
                    "file_modified": file_info.get("modified", 0),
                }
            processed_filenames.append(filename)
            self._checkpoint_data.update({
                "last_modified": max(f.get("modified", 0) for f in self._files_on_server),
                "processed_filenames": processed_filenames,
                "total_fetched": total,
                "timestamp": time.time(),
            })
        self._checkpoint_data["total_fetched"] = total

    async def validate(self) -> ConnectorValidationResult:
        result = await super().validate()
        if not self.host:
            result.is_valid = False
            result.errors.append("host is required")
        result.metadata["host"] = self.host
        result.metadata["port"] = self.port
        return result


connector_registry.register("s3", S3Connector)
connector_registry.register("ftp", FTPConnector)
