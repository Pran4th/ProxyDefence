"""Database connectors: generic SQL, PostgreSQL, Elasticsearch."""

import asyncio
import os
import time
from typing import Any, AsyncIterator

from connectors.base import BaseConnector, ConnectorConfig, ConnectorFetchConfig, ConnectorValidationResult, exponential_backoff
from connectors.errors import (
    ConnectorConnectionError,
    ConnectorSchemaDiscoveryError,
    ConnectorFetchError,
    ConnectorCheckpointError,
)
from connectors.registry import connector_registry


class SQLConnector(BaseConnector):
    """Generic SQL connector — uses connection string and raw queries."""

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        cfg = config.config
        self.connection_string = cfg.get("connection_string", "")
        self.query = cfg.get("query", "")
        self.query_file = cfg.get("query_file")
        self.parameters = cfg.get("parameters")
        self._resolved_query = ""
        self._row_count = 0

    async def connect(self) -> None:
        self.logger.info("Connecting to SQL database (simulated)")
        if not self.connection_string:
            raise ConnectorConnectionError("connection_string is required")
        self._resolved_query = self._resolve_query()
        self._is_connected = True
        self.logger.info("SQL connector connected")

    async def disconnect(self) -> None:
        self._is_connected = False
        self._resolved_query = ""

    def _resolve_query(self) -> str:
        if self.query:
            return self.query
        if self.query_file and os.path.exists(self.query_file):
            with open(self.query_file) as f:
                return f.read()
        return "SELECT * FROM simulated_table"

    async def discover_schema(self) -> dict:
        self._raise_if_not_connected()
        try:
            columns = ["id", "name", "value", "category", "created_at"]
            dtypes = {
                "id": "int64",
                "name": "object",
                "value": "float64",
                "category": "object",
                "created_at": "datetime64[ns]",
            }
            return {
                "columns": columns,
                "dtypes": dtypes,
                "sample_count": 5,
                "row_estimate": 10000,
                "query": self._resolved_query[:200],
            }
        except Exception as exc:
            raise ConnectorSchemaDiscoveryError(f"SQL schema discovery failed: {exc}") from exc

    async def fetch(self, config: ConnectorFetchConfig) -> AsyncIterator[dict]:
        self._raise_if_not_connected()
        max_records = config.max_records or float("inf")
        start_position = config.start_position
        offset = int(start_position) if start_position and start_position.isdigit() else 0
        total = offset
        batch_size = config.batch_size

        while total - offset < max_records:
            await asyncio.sleep(0)
            remaining = min(batch_size, max_records - (total - offset))
            if remaining <= 0:
                break
            for i in range(remaining):
                row_id = total + 1
                yield {
                    "id": row_id,
                    "name": f"sql_row_{row_id}",
                    "value": round(row_id * 0.33, 2),
                    "category": f"cat_{(row_id - 1) % 20}",
                    "created_at": "2025-06-01T00:00:00",
                }
                total += 1
            self._checkpoint_data.update({
                "last_id": total,
                "offset": total,
                "timestamp": time.time(),
            })
            if remaining < batch_size:
                break
        self._checkpoint_data["total_fetched"] = total - offset

    async def validate(self) -> ConnectorValidationResult:
        result = await super().validate()
        if not self.connection_string:
            result.is_valid = False
            result.errors.append("connection_string is required")
        if not self.query and not self.query_file:
            result.warnings.append("No query or query_file specified")
        return result


class PostgreSQLConnector(BaseConnector):
    """PostgreSQL connector — server-side cursor, incremental sync, schema introspection."""

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        cfg = config.config
        self.host = cfg.get("host", "localhost")
        self.port = cfg.get("port", 5432)
        self.dbname = cfg.get("dbname", "")
        self.user = cfg.get("user", "")
        self.password = cfg.get("password", "")
        self.schema = cfg.get("schema", "public")
        self.table_or_query = cfg.get("table_or_query", "")
        self._table_name = ""
        self._pk_column = "id"
        self._row_count = 0
        self._max_pk = 0

    async def connect(self) -> None:
        self.logger.info("Connecting to PostgreSQL %s:%s/%s (simulated)", self.host, self.port, self.dbname)
        if not self.dbname:
            raise ConnectorConnectionError("dbname is required")
        self._is_connected = True
        self._table_name = self.table_or_query.split(";")[0].strip().split()[0] if self.table_or_query else "unknown"
        self.logger.info("PostgreSQL connector connected, target: %s.%s", self.schema, self._table_name)

    async def disconnect(self) -> None:
        self._is_connected = False

    async def discover_schema(self) -> dict:
        self._raise_if_not_connected()
        try:
            columns = [
                {"name": "id", "data_type": "integer", "is_nullable": "NO", "is_pk": True},
                {"name": "name", "data_type": "varchar(255)", "is_nullable": "YES", "is_pk": False},
                {"name": "value", "data_type": "double precision", "is_nullable": "YES", "is_pk": False},
                {"name": "category", "data_type": "varchar(100)", "is_nullable": "YES", "is_pk": False},
                {"name": "status", "data_type": "boolean", "is_nullable": "YES", "is_pk": False},
                {"name": "created_at", "data_type": "timestamp with time zone", "is_nullable": "YES", "is_pk": False},
                {"name": "updated_at", "data_type": "timestamp with time zone", "is_nullable": "YES", "is_pk": False},
            ]
            dtypes = {
                "id": "int64",
                "name": "object",
                "value": "float64",
                "category": "object",
                "status": "bool",
                "created_at": "datetime64[ns, UTC]",
                "updated_at": "datetime64[ns, UTC]",
            }
            return {
                "columns": [c["name"] for c in columns],
                "dtypes": dtypes,
                "sample_count": 5,
                "row_estimate": 50000,
                "column_details": columns,
                "schema": self.schema,
                "table": self._table_name,
                "pk_column": self._pk_column,
            }
        except Exception as exc:
            raise ConnectorSchemaDiscoveryError(f"PostgreSQL schema discovery failed: {exc}") from exc

    async def fetch(self, config: ConnectorFetchConfig) -> AsyncIterator[dict]:
        self._raise_if_not_connected()
        max_records = config.max_records or float("inf")
        start_from = 0
        if config.start_position:
            try:
                start_from = int(config.start_position)
            except ValueError:
                pass
        pk = start_from
        total = 0
        batch_size = config.batch_size

        while total < max_records:
            await asyncio.sleep(0)
            remaining = min(batch_size, max_records - total)
            if remaining <= 0:
                break
            for i in range(remaining):
                pk += 1
                total += 1
                yield {
                    "id": pk,
                    "name": f"pg_row_{pk}",
                    "value": round(pk * 0.1, 2),
                    "category": f"cat_{pk % 15}",
                    "status": pk % 2 == 0,
                    "created_at": "2025-06-01T00:00:00+00:00",
                    "updated_at": "2025-06-15T00:00:00+00:00",
                }
            self._max_pk = pk
            self._checkpoint_data.update({
                f"max_{self._pk_column}": pk,
                "row_count": total,
                "timestamp": time.time(),
            })
            if remaining < batch_size:
                break
        self._checkpoint_data["total_fetched"] = total

    async def validate(self) -> ConnectorValidationResult:
        result = await super().validate()
        if not self.dbname:
            result.is_valid = False
            result.errors.append("dbname is required")
        if not self.table_or_query:
            result.is_valid = False
            result.errors.append("table_or_query is required")
        return result


class ElasticsearchConnector(BaseConnector):
    """Elasticsearch connector — scroll/pit-based pagination, mapping discovery."""

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        cfg = config.config
        self.hosts = cfg.get("hosts", ["http://localhost:9200"])
        self.index = cfg.get("index", "")
        self.query_body = cfg.get("query_body", {"query": {"match_all": {}}})
        self.scroll_size = cfg.get("scroll_size", 1000)
        self.api_key = cfg.get("api_key")
        self._scroll_id: str | None = None
        self._pit_id: str | None = None
        self._total_hits = 0
        self._fetched = 0

    async def connect(self) -> None:
        self.logger.info("Connecting to Elasticsearch %s (simulated)", self.hosts[0] if self.hosts else "N/A")
        if not self.index:
            raise ConnectorConnectionError("index is required")
        self._is_connected = True
        self.logger.info("Elasticsearch connector connected to index: %s", self.index)

    async def disconnect(self) -> None:
        self._is_connected = False
        self._scroll_id = None
        self._pit_id = None

    async def discover_schema(self) -> dict:
        self._raise_if_not_connected()
        try:
            mapping = {
                "id": {"type": "integer"},
                "name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "value": {"type": "float"},
                "category": {"type": "keyword"},
                "status": {"type": "boolean"},
                "created_at": {"type": "date"},
                "location": {"type": "geo_point"},
            }
            columns = list(mapping.keys())
            es_to_dtype = {
                "integer": "int64",
                "text": "object",
                "keyword": "object",
                "float": "float64",
                "boolean": "bool",
                "date": "datetime64[ns]",
                "geo_point": "object",
            }
            dtypes = {}
            for col, props in mapping.items():
                dtypes[col] = es_to_dtype.get(props["type"], "object")
            return {
                "columns": columns,
                "dtypes": dtypes,
                "sample_count": 5,
                "row_estimate": 100000,
                "index": self.index,
                "mapping": mapping,
            }
        except Exception as exc:
            raise ConnectorSchemaDiscoveryError(f"Elasticsearch schema discovery failed: {exc}") from exc

    async def fetch(self, config: ConnectorFetchConfig) -> AsyncIterator[dict]:
        self._raise_if_not_connected()
        max_records = config.max_records or float("inf")
        self._fetched = 0
        self._scroll_id = None
        self._total_hits = 100000
        scroll_size = config.batch_size or self.scroll_size

        while self._fetched < min(max_records, self._total_hits):
            await asyncio.sleep(0)
            remaining = min(scroll_size, max_records - self._fetched, self._total_hits - self._fetched)
            if remaining <= 0:
                break
            if self._rate_limiter:
                await self._rate_limiter.acquire()
            for i in range(remaining):
                self._fetched += 1
                yield {
                    "_id": f"doc_{self._fetched}",
                    "_index": self.index,
                    "_score": round(1.0 - (self._fetched * 0.00001), 4),
                    "_source": {
                        "id": self._fetched,
                        "name": f"es_doc_{self._fetched}",
                        "value": round(self._fetched * 0.05, 2),
                        "category": f"cat_{self._fetched % 25}",
                        "status": self._fetched % 3 != 0,
                        "created_at": "2025-06-01T00:00:00",
                        "location": {"lat": 31.0 + self._fetched * 0.001, "lon": 34.0 + self._fetched * 0.001},
                    },
                }
            self._scroll_id = f"simulated_scroll_{self._fetched}"
            self._checkpoint_data.update({
                "scroll_id": self._scroll_id,
                "fetched": self._fetched,
                "total_hits": self._total_hits,
                "timestamp": time.time(),
            })
            if remaining < scroll_size:
                break
        self._checkpoint_data["total_fetched"] = self._fetched

    async def validate(self) -> ConnectorValidationResult:
        result = await super().validate()
        if not self.index:
            result.is_valid = False
            result.errors.append("index is required")
        if self.hosts:
            result.metadata["hosts"] = self.hosts
        return result


connector_registry.register("sql", SQLConnector)
connector_registry.register("postgresql", PostgreSQLConnector)
connector_registry.register("elasticsearch", ElasticsearchConnector)
