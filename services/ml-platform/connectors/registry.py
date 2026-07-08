"""Connector registry — maintains mapping of connector_type -> class."""

from typing import Any

from connectors.base import BaseConnector, ConnectorConfig


DEFAULT_CONFIGS: dict[str, dict[str, Any]] = {
    "rest_api": {
        "base_url": "",
        "headers": {},
        "auth_type": "none",
        "pagination_type": "page_number",
        "page_size_param": "page_size",
        "page_param": "page",
        "data_path": "",
        "timeout": 30,
    },
    "csv": {
        "file_path_or_pattern": "",
        "delimiter": ",",
        "encoding": "utf-8",
        "compression": None,
        "has_header": True,
        "chunk_size": 10000,
    },
    "excel": {
        "file_path": "",
        "sheet_name": None,
        "skip_rows": 0,
        "header_row": 0,
    },
    "json": {
        "file_path": "",
        "root_path": "",
        "lines_format": False,
    },
    "parquet": {
        "file_path_or_pattern": "",
        "columns": None,
    },
    "geojson": {
        "file_path": "",
        "feature_path": "features",
    },
    "sql": {
        "connection_string": "",
        "query": "",
        "query_file": None,
        "parameters": None,
    },
    "postgresql": {
        "host": "localhost",
        "port": 5432,
        "dbname": "",
        "user": "",
        "password": "",
        "schema": "public",
        "table_or_query": "",
    },
    "elasticsearch": {
        "hosts": ["http://localhost:9200"],
        "index": "",
        "query_body": {"query": {"match_all": {}}},
        "scroll_size": 1000,
        "api_key": None,
    },
    "kafka": {
        "bootstrap_servers": ["localhost:9092"],
        "topic": "",
        "group_id": None,
        "value_deserializer": "json",
        "auto_offset_reset": "earliest",
    },
    "s3": {
        "endpoint_url": None,
        "region": "us-east-1",
        "bucket": "",
        "prefix": "",
        "access_key": None,
        "secret_key": None,
    },
    "ftp": {
        "host": "",
        "port": 21,
        "username": "anonymous",
        "password": "",
        "remote_path": "/",
        "file_pattern": "*",
        "passive_mode": True,
    },
    "http_archive": {
        "url": "",
        "headers": {},
        "auth": None,
        "decompression": "auto",
    },
    "zip": {
        "file_path": "",
        "entry_pattern": "*",
        "password": None,
    },
    "tar": {
        "file_path": "",
        "entry_pattern": "*",
        "compression": "none",
    },
    "gzip": {
        "file_path": "",
        "encoding": "utf-8",
    },
}


class ConnectorRegistry:
    """Registry of connector types to connector classes."""

    def __init__(self):
        self._registry: dict[str, type[BaseConnector]] = {}

    def register(self, connector_type: str, connector_class: type[BaseConnector]) -> None:
        if connector_type in self._registry:
            from backend.shared.logging_config import get_logger
            get_logger(__name__).warning("Overwriting existing connector type: %s", connector_type)
        self._registry[connector_type] = connector_class

    def get(self, connector_type: str) -> type[BaseConnector]:
        if connector_type not in self._registry:
            raise KeyError(f"No connector registered for type '{connector_type}'. Available: {self.list_types()}")
        return self._registry[connector_type]

    def create(self, config: ConnectorConfig) -> BaseConnector:
        cls = self.get(config.connector_type)
        return cls(config)

    def list_types(self) -> list[str]:
        return list(self._registry.keys())

    def get_default_config(self, connector_type: str) -> dict[str, Any]:
        if connector_type not in DEFAULT_CONFIGS:
            raise KeyError(f"No default config for connector type '{connector_type}'")
        from copy import deepcopy
        return deepcopy(DEFAULT_CONFIGS[connector_type])


connector_registry = ConnectorRegistry()
