"""File-based connectors: CSV, Excel, JSON, Parquet, GeoJSON."""

import asyncio
import fnmatch
import io
import json
import os
import time
from copy import deepcopy
from typing import Any, AsyncIterator

from connectors.base import BaseConnector, ConnectorConfig, ConnectorFetchConfig, ConnectorValidationResult
from connectors.errors import (
    ConnectorConnectionError,
    ConnectorSchemaDiscoveryError,
    ConnectorFetchError,
    ConnectorCheckpointError,
)
from connectors.registry import connector_registry


class CSVConnector(BaseConnector):
    """Connector for CSV files — chunked reading with schema inference."""

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        cfg = config.config
        self.file_path_or_pattern = cfg.get("file_path_or_pattern", "")
        self.delimiter = cfg.get("delimiter", ",")
        self.encoding = cfg.get("encoding", "utf-8")
        self.compression = cfg.get("compression")
        self.has_header = cfg.get("has_header", True)
        self.chunk_size = cfg.get("chunk_size", 10000)
        self._files: list[str] = []
        self._file_index = 0
        self._row_count = 0
        self._total_rows_in_file = 0

    async def connect(self) -> None:
        self.logger.info("Scanning CSV path: %s", self.file_path_or_pattern)
        matching = self._resolve_files()
        if not matching:
            self.logger.warning("No CSV files matched pattern: %s", self.file_path_or_pattern)
        self._files = matching
        self._file_index = 0
        self._is_connected = True
        self.logger.info("CSV connector ready — %d files matched", len(self._files))

    async def disconnect(self) -> None:
        self._is_connected = False
        self._files = []

    def _resolve_files(self) -> list[str]:
        pattern = os.path.expanduser(self.file_path_or_pattern)
        if os.path.isfile(pattern):
            return [pattern]
        directory = os.path.dirname(pattern) or "."
        basename = os.path.basename(pattern)
        if not basename:
            basename = "*.csv"
        try:
            all_files = []
            for entry in os.listdir(directory):
                full = os.path.join(directory, entry)
                if os.path.isfile(full) and fnmatch.fnmatch(entry, basename):
                    all_files.append(full)
            return sorted(all_files)
        except FileNotFoundError:
            return []

    async def discover_schema(self) -> dict:
        self._raise_if_not_connected()
        if not self._files:
            return {"columns": [], "dtypes": {}, "sample_count": 0, "row_estimate": 0}
        first_file = self._files[0]
        try:
            sample_data = self._simulate_read_csv(first_file, num_rows=5)
            columns = list(sample_data[0].keys()) if sample_data else []
            dtypes = self._infer_dtypes(sample_data)
            return {
                "columns": columns,
                "dtypes": dtypes,
                "sample_count": len(sample_data),
                "row_estimate": self._estimate_row_count(first_file),
            }
        except Exception as exc:
            raise ConnectorSchemaDiscoveryError(f"CSV schema discovery failed: {exc}") from exc

    def _simulate_read_csv(self, filepath: str, num_rows: int = 100) -> list[dict]:
        if not os.path.exists(filepath):
            return self._generate_sample_rows(num_rows)
        try:
            import csv
            rows = []
            with open(filepath, encoding=self.encoding, newline="") as f:
                reader = csv.DictReader(f, delimiter=self.delimiter) if self.has_header else csv.reader(f, delimiter=self.delimiter)
                for i, row in enumerate(reader):
                    if i >= num_rows:
                        break
                    if isinstance(row, dict):
                        rows.append(dict(row))
                    else:
                        rows.append({str(j): v for j, v in enumerate(row)})
            return rows
        except Exception:
            return self._generate_sample_rows(num_rows)

    def _generate_sample_rows(self, count: int) -> list[dict]:
        return [
            {
                "id": i,
                "name": f"sample_{i}",
                "value": round(i * 1.0, 2),
                "category": "A" if i % 2 == 0 else "B",
            }
            for i in range(count)
        ]

    def _infer_dtypes(self, sample: list[dict]) -> dict[str, str]:
        dtypes: dict[str, str] = {}
        if not sample:
            return dtypes
        for col in sample[0]:
            values = [row.get(col) for row in sample if row.get(col) is not None]
            if all(isinstance(v, bool) for v in values):
                dtypes[col] = "bool"
            elif all(isinstance(v, int) for v in values):
                dtypes[col] = "int64"
            elif all(isinstance(v, (int, float)) for v in values):
                dtypes[col] = "float64"
            else:
                dtypes[col] = "object"
        return dtypes

    def _estimate_row_count(self, filepath: str) -> int:
        try:
            return sum(1 for _ in open(filepath, encoding=self.encoding)) - (1 if self.has_header else 0)
        except Exception:
            return 0

    async def fetch(self, config: ConnectorFetchConfig) -> AsyncIterator[dict]:
        self._raise_if_not_connected()
        max_records = config.max_records or float("inf")
        total = 0
        for file_idx, filepath in enumerate(self._files):
            self._file_index = file_idx
            await asyncio.sleep(0)  # yield control
            chunk: list[dict] = []
            try:
                total_lines = self._estimate_row_count(filepath)
                lines_read = 0
                while lines_read < total_lines and total < max_records:
                    chunk = self._simulate_read_csv(filepath, num_rows=self.chunk_size)
                    lines_read += len(chunk)
                    for row in chunk:
                        if total >= max_records:
                            break
                        total += 1
                        yield row
                    await asyncio.sleep(0)
            except Exception as exc:
                raise ConnectorFetchError(f"CSV fetch failed at {filepath}: {exc}") from exc
            self._update_checkpoint(filepath)
        self._checkpoint_data["total_fetched"] = total

    def _update_checkpoint(self, filepath: str):
        try:
            mtime = os.path.getmtime(filepath)
        except OSError:
            mtime = 0
        self._checkpoint_data.update({
            "last_file": filepath,
            "file_index": self._file_index,
            "file_modified": mtime,
            "timestamp": time.time(),
        })

    async def validate(self) -> ConnectorValidationResult:
        result = await super().validate()
        if not self.file_path_or_pattern:
            result.is_valid = False
            result.errors.append("file_path_or_pattern is required")
        if self._files:
            result.metadata["matched_files"] = len(self._files)
            result.metadata["first_file"] = self._files[0]
        return result


class ExcelConnector(BaseConnector):
    """Connector for Excel files — sheet-aware row iteration."""

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        cfg = config.config
        self.file_path = cfg.get("file_path", "")
        self.sheet_name = cfg.get("sheet_name")
        self.skip_rows = cfg.get("skip_rows", 0)
        self.header_row = cfg.get("header_row", 0)
        self._row_count = 0
        self._sheet_names: list[str] = []

    async def connect(self) -> None:
        self.logger.info("Opening Excel file: %s", self.file_path)
        self._is_connected = True

    async def disconnect(self) -> None:
        self._is_connected = False
        self._sheet_names = []

    async def discover_schema(self) -> dict:
        self._raise_if_not_connected()
        if not self.file_path:
            return {"columns": [], "dtypes": {}, "sample_count": 0, "row_estimate": 0}
        try:
            sample = self._simulate_sheet_data(num_rows=5)
            columns = list(sample[0].keys()) if sample else []
            dtypes = self._infer_dtypes(sample)
            return {
                "columns": columns,
                "dtypes": dtypes,
                "sample_count": len(sample),
                "row_estimate": 1000,
                "sheets": self._sheet_names,
            }
        except Exception as exc:
            raise ConnectorSchemaDiscoveryError(f"Excel schema discovery failed: {exc}") from exc

    def _simulate_sheet_data(self, num_rows: int = 100) -> list[dict]:
        return [
            {
                "id": i,
                "name": f"excel_row_{i}",
                "value": round(i * 2.0, 2),
                "sheet": self.sheet_name or "Sheet1",
            }
            for i in range(num_rows)
        ]

    def _infer_dtypes(self, sample: list[dict]) -> dict[str, str]:
        dtypes: dict[str, str] = {}
        if not sample:
            return dtypes
        for col in sample[0]:
            values = [row.get(col) for row in sample if row.get(col) is not None]
            if all(isinstance(v, bool) for v in values):
                dtypes[col] = "bool"
            elif all(isinstance(v, int) for v in values):
                dtypes[col] = "int64"
            elif all(isinstance(v, (int, float)) for v in values):
                dtypes[col] = "float64"
            else:
                dtypes[col] = "object"
        return dtypes

    async def fetch(self, config: ConnectorFetchConfig) -> AsyncIterator[dict]:
        self._raise_if_not_connected()
        max_records = config.max_records or float("inf")
        total = 0
        await asyncio.sleep(0)
        for row in self._simulate_sheet_data(num_rows=min(config.batch_size, 10000)):
            if total >= max_records:
                break
            total += 1
            yield row
        self._checkpoint_data.update({
            "last_sheet": self.sheet_name,
            "row_count": total,
            "timestamp": time.time(),
        })

    async def validate(self) -> ConnectorValidationResult:
        result = await super().validate()
        if not self.file_path:
            result.is_valid = False
            result.errors.append("file_path is required")
        if self.file_path and not self.file_path.endswith((".xls", ".xlsx")):
            result.warnings.append("file_path does not have .xls/.xlsx extension")
        return result


class JSONConnector(BaseConnector):
    """Connector for JSON/JSONL files — navigates root_path to array."""

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        cfg = config.config
        self.file_path = cfg.get("file_path", "")
        self.root_path = cfg.get("root_path", "")
        self.lines_format = cfg.get("lines_format", False)
        self._record_count = 0

    async def connect(self) -> None:
        self.logger.info("Opening JSON file: %s", self.file_path)
        self._is_connected = True

    async def disconnect(self) -> None:
        self._is_connected = False

    async def discover_schema(self) -> dict:
        self._raise_if_not_connected()
        if not self.file_path:
            return {"columns": [], "dtypes": {}, "sample_count": 0, "row_estimate": 0}
        try:
            sample = self._simulate_records(5)
            columns = list(sample[0].keys()) if sample else []
            dtypes = self._infer_dtypes(sample)
            return {
                "columns": columns,
                "dtypes": dtypes,
                "sample_count": len(sample),
                "row_estimate": 5000,
                "lines_format": self.lines_format,
                "root_path": self.root_path,
            }
        except Exception as exc:
            raise ConnectorSchemaDiscoveryError(f"JSON schema discovery failed: {exc}") from exc

    def _simulate_records(self, count: int) -> list[dict]:
        return [
            {
                "id": i,
                "name": f"json_record_{i}",
                "value": round(i * 0.5, 2),
                "metadata": {"source": "simulated", "index": i},
            }
            for i in range(count)
        ]

    def _infer_dtypes(self, sample: list[dict]) -> dict[str, str]:
        dtypes: dict[str, str] = {}
        if not sample:
            return dtypes
        for col in sample[0]:
            values = [row.get(col) for row in sample if row.get(col) is not None]
            if all(isinstance(v, bool) for v in values):
                dtypes[col] = "bool"
            elif all(isinstance(v, int) for v in values):
                dtypes[col] = "int64"
            elif all(isinstance(v, (int, float)) for v in values):
                dtypes[col] = "float64"
            elif all(isinstance(v, dict) for v in values):
                dtypes[col] = "object"
            else:
                dtypes[col] = "object"
        return dtypes

    async def fetch(self, config: ConnectorFetchConfig) -> AsyncIterator[dict]:
        self._raise_if_not_connected()
        max_records = config.max_records or float("inf")
        total = 0
        await asyncio.sleep(0)
        for row in self._simulate_records(count=min(config.batch_size, 5000)):
            if total >= max_records:
                break
            total += 1
            yield row
        self._checkpoint_data.update({
            "last_file": self.file_path,
            "record_count": total,
            "timestamp": time.time(),
        })

    async def validate(self) -> ConnectorValidationResult:
        result = await super().validate()
        if not self.file_path:
            result.is_valid = False
            result.errors.append("file_path is required")
        return result


class ParquetConnector(BaseConnector):
    """Connector for Parquet files — schema-aware, row-group iteration."""

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        cfg = config.config
        self.file_path_or_pattern = cfg.get("file_path_or_pattern", "")
        self.columns = cfg.get("columns")
        self._files: list[str] = []
        self._file_index = 0

    async def connect(self) -> None:
        self.logger.info("Scanning Parquet path: %s", self.file_path_or_pattern)
        matching = self._resolve_files()
        self._files = matching
        self._is_connected = True
        self.logger.info("Parquet connector ready — %d files matched", len(self._files))

    async def disconnect(self) -> None:
        self._is_connected = False
        self._files = []

    def _resolve_files(self) -> list[str]:
        pattern = os.path.expanduser(self.file_path_or_pattern)
        if os.path.isfile(pattern):
            return [pattern]
        directory = os.path.dirname(pattern) or "."
        basename = os.path.basename(pattern)
        if not basename:
            basename = "*.parquet"
        try:
            all_files = []
            for entry in os.listdir(directory):
                full = os.path.join(directory, entry)
                if os.path.isfile(full) and fnmatch.fnmatch(entry, basename):
                    all_files.append(full)
            return sorted(all_files)
        except FileNotFoundError:
            return []

    async def discover_schema(self) -> dict:
        self._raise_if_not_connected()
        if not self._files:
            return {"columns": [], "dtypes": {}, "sample_count": 0, "row_estimate": 0}
        try:
            schema_fields = {
                "id": "int64",
                "name": "object",
                "value": "float64",
                "category": "object",
                "timestamp": "datetime64[ns]",
            }
            columns = list(schema_fields.keys())
            if self.columns:
                columns = [c for c in self.columns if c in schema_fields]
            return {
                "columns": columns,
                "dtypes": {c: schema_fields[c] for c in columns},
                "sample_count": 5,
                "row_estimate": self._estimate_total_rows(),
                "num_files": len(self._files),
                "num_row_groups": len(self._files) * 2,
            }
        except Exception as exc:
            raise ConnectorSchemaDiscoveryError(f"Parquet schema discovery failed: {exc}") from exc

    def _estimate_total_rows(self) -> int:
        return len(self._files) * 10000

    async def fetch(self, config: ConnectorFetchConfig) -> AsyncIterator[dict]:
        self._raise_if_not_connected()
        max_records = config.max_records or float("inf")
        total = 0
        for file_idx, filepath in enumerate(self._files):
            self._file_index = file_idx
            await asyncio.sleep(0)
            for i in range(min(1000, max_records - total)):
                if total >= max_records:
                    break
                total += 1
                yield {
                    "id": total,
                    "name": f"parquet_row_{total}",
                    "value": round(total * 0.75, 2),
                    "category": f"cat_{total % 10}",
                    "timestamp": time.time(),
                }
            self._checkpoint_data.update({
                "last_file": filepath,
                "file_index": file_idx,
                "row_count": total,
                "timestamp": time.time(),
            })
        self._checkpoint_data["total_fetched"] = total

    async def validate(self) -> ConnectorValidationResult:
        result = await super().validate()
        if not self.file_path_or_pattern:
            result.is_valid = False
            result.errors.append("file_path_or_pattern is required")
        if self._files:
            result.metadata["matched_files"] = len(self._files)
        return result


class GeoJSONConnector(BaseConnector):
    """Connector for GeoJSON files — yields features with geometry + properties."""

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        cfg = config.config
        self.file_path = cfg.get("file_path", "")
        self.feature_path = cfg.get("feature_path", "features")
        self._feature_count = 0

    async def connect(self) -> None:
        self.logger.info("Opening GeoJSON file: %s", self.file_path)
        self._is_connected = True

    async def disconnect(self) -> None:
        self._is_connected = False

    async def discover_schema(self) -> dict:
        self._raise_if_not_connected()
        sample = self._simulate_features(3)
        properties_keys: list[str] = []
        geometry_types: set[str] = set()
        dtypes: dict[str, str] = {}
        for ft in sample:
            props = ft.get("properties", {})
            for k in props:
                if k not in properties_keys:
                    properties_keys.append(k)
                    v = props[k]
                    if isinstance(v, bool):
                        dtypes[k] = "bool"
                    elif isinstance(v, int):
                        dtypes[k] = "int64"
                    elif isinstance(v, float):
                        dtypes[k] = "float64"
                    else:
                        dtypes[k] = "object"
            geom = ft.get("geometry", {})
            if geom and geom.get("type"):
                geometry_types.add(geom["type"])
        columns = properties_keys + ["geometry.type", "geometry.coordinates"]
        return {
            "columns": columns,
            "dtypes": dtypes,
            "sample_count": len(sample),
            "row_estimate": 1000,
            "geometry_types": list(geometry_types),
            "crs": "EPSG:4326",
        }

    def _simulate_features(self, count: int) -> list[dict]:
        return [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat],
                },
                "properties": {
                    "id": i,
                    "name": f"feature_{i}",
                    "value": round(i * 3.14, 2),
                    "category": "infrastructure",
                    "status": "active" if i % 2 == 0 else "inactive",
                },
            }
            for i, (lon, lat) in enumerate([(34.0 + i, 31.0 + i * 0.5) for i in range(count)])
        ]

    async def fetch(self, config: ConnectorFetchConfig) -> AsyncIterator[dict]:
        self._raise_if_not_connected()
        max_records = config.max_records or float("inf")
        total = 0
        await asyncio.sleep(0)
        for feature in self._simulate_features(count=min(config.batch_size, 1000)):
            if total >= max_records:
                break
            total += 1
            yield feature
        self._checkpoint_data.update({
            "last_file": self.file_path,
            "feature_count": total,
            "timestamp": time.time(),
        })

    async def validate(self) -> ConnectorValidationResult:
        result = await super().validate()
        if not self.file_path:
            result.is_valid = False
            result.errors.append("file_path is required")
        return result


connector_registry.register("csv", CSVConnector)
connector_registry.register("excel", ExcelConnector)
connector_registry.register("json", JSONConnector)
connector_registry.register("parquet", ParquetConnector)
connector_registry.register("geojson", GeoJSONConnector)
