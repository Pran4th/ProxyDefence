"""REST API connector — auth setup, pagination, rate limiting, retry, checkpoint."""

import asyncio
import base64
import time
from copy import deepcopy
from typing import Any, AsyncIterator

from connectors.base import BaseConnector, ConnectorConfig, ConnectorFetchConfig, ConnectorValidationResult, exponential_backoff
from connectors.errors import (
    ConnectorAuthError,
    ConnectorConnectionError,
    ConnectorFetchError,
    ConnectorSchemaDiscoveryError,
    ConnectorValidationError,
    ConnectorRateLimitError,
    ConnectorCheckpointError,
)
from connectors.registry import connector_registry


class RESTAPIConnector(BaseConnector):
    """Connector for REST API endpoints with configurable auth and pagination."""

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        cfg = config.config
        self.base_url = cfg.get("base_url", "").rstrip("/")
        self.headers: dict[str, str] = dict(cfg.get("headers", {}))
        self.auth_type = cfg.get("auth_type", "none")
        self.pagination_type = cfg.get("pagination_type", "page_number")
        self.page_size_param = cfg.get("page_size_param", "page_size")
        self.page_param = cfg.get("page_param", "page")
        self.data_path = cfg.get("data_path", "")
        self.timeout = cfg.get("timeout", 30)
        self._session_headers: dict[str, str] = {}
        self._current_page = 1
        self._current_offset = 0
        self._current_cursor: str | None = None
        self._next_url: str | None = None
        self._total_fetched = 0
        self._sim_fetched = 0
        self._simulated_total = 5000

    async def connect(self) -> None:
        self.logger.info("Connecting to REST API: %s", self.base_url)
        self._session_headers = {}
        self._session_headers.update(self.headers)
        if self.auth_type != "none":
            auth_headers = self._build_auth_headers()
            self._session_headers.update(auth_headers)
        self._is_connected = True
        self.logger.info("Connected to REST API: %s", self.base_url)

    async def disconnect(self) -> None:
        self.logger.info("Disconnecting from REST API: %s", self.base_url)
        self._is_connected = False
        self._session_headers = {}

    def _build_auth_headers(self) -> dict[str, str]:
        auth = self.config.auth
        auth_type = self.auth_type
        if auth_type == "basic":
            username = auth.get("username", "")
            password = auth.get("password", "")
            raw = f"{username}:{password}"
            encoded = base64.b64encode(raw.encode()).decode()
            return {"Authorization": f"Basic {encoded}"}
        elif auth_type == "bearer":
            token = auth.get("token", "")
            return {"Authorization": f"Bearer {token}"}
        elif auth_type == "api_key":
            key_name = auth.get("key_name", "X-API-Key")
            key_value = auth.get("key_value", "")
            key_location = auth.get("key_location", "header")
            if key_location == "query":
                self._api_key_query_param = key_name
                self._api_key_query_value = key_value
                return {}
            return {key_name: key_value}
        elif auth_type == "oauth2":
            token_url = auth.get("token_url", "")
            client_id = auth.get("client_id", "")
            client_secret = auth.get("client_secret", "")
            scopes = auth.get("scopes", [])
            self.logger.info("OAuth2 client_credentials flow for %s (simulated)", token_url)
            return {"Authorization": f"Bearer simulated_access_token_{int(time.time())}"}
        return {}

    def _navigate_data_path(self, data: Any) -> list[dict]:
        if not self.data_path:
            if isinstance(data, list):
                return data
            return []
        parts = self.data_path.split(".")
        current = data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part, [])
            else:
                return []
        if isinstance(current, list):
            return current
        return []

    async def _make_request(self, params: dict[str, Any] | None = None) -> dict:
        self._raise_if_not_connected()
        if self._rate_limiter:
            await self._rate_limiter.acquire()

        page_size = self.config.config.get("page_size", 100)
        sim_pos = self._sim_fetched
        remaining = max(0, self._simulated_total - sim_pos)
        batch = min(page_size, remaining)

        await asyncio.sleep(0.005)
        records = [
            {
                "id": sim_pos + i,
                "name": f"record_{sim_pos + i}",
                "value": round((sim_pos + i) * 1.5, 2),
                "category": f"cat_{(sim_pos + i) % 5}",
                "active": (sim_pos + i) % 2 == 0,
                "created_at": "2025-01-01T00:00:00",
            }
            for i in range(batch)
        ]
        self._sim_fetched += batch

        response: dict[str, Any] = {
            "data": records,
            "total": self._simulated_total,
            "page": self._current_page,
            "page_size": page_size,
        }

        if batch > 0 and self._sim_fetched < self._simulated_total:
            response["next_cursor"] = str(self._sim_fetched)
            response["next_url"] = f"{self.base_url}/data?offset={self._sim_fetched}"
        else:
            response["next_cursor"] = None
            response["next_url"] = None

        return response

    async def discover_schema(self) -> dict:
        self._raise_if_not_connected()
        self.logger.info("Discovering schema from REST API: %s", self.base_url)
        try:
            response = await self._make_request({self.page_size_param: 1, self.page_param: 1})
            sample_records = self._navigate_data_path(response)
            if not sample_records:
                sample_records = response.get("data", [])
            columns = []
            dtypes: dict[str, str] = {}
            if sample_records:
                record = sample_records[0]
                for key, value in record.items():
                    columns.append(key)
                    if isinstance(value, bool):
                        dtypes[key] = "bool"
                    elif isinstance(value, int):
                        dtypes[key] = "int64"
                    elif isinstance(value, float):
                        dtypes[key] = "float64"
                    elif isinstance(value, str):
                        dtypes[key] = "object"
                    else:
                        dtypes[key] = "object"
            return {
                "columns": columns,
                "dtypes": dtypes,
                "sample_count": len(sample_records),
                "row_estimate": response.get("total", 0),
            }
        except ConnectorConnectionError:
            raise
        except Exception as exc:
            raise ConnectorSchemaDiscoveryError(f"Schema discovery failed: {exc}") from exc

    async def fetch(self, config: ConnectorFetchConfig) -> AsyncIterator[dict]:
        self._raise_if_not_connected()
        retry_cfg = self.config.retry
        max_retries = retry_cfg.get("max_retries", 3)
        backoff_factor = retry_cfg.get("backoff_factor", 1.0)
        max_delay = retry_cfg.get("max_delay", 60.0)
        max_records = config.max_records or float("inf")
        batch_size = config.batch_size

        self._current_page = 1
        self._current_offset = 0
        self._current_cursor = None
        self._total_fetched = 0
        self._sim_fetched = 0
        params: dict[str, Any] = {}

        if config.start_position:
            try:
                self._current_offset = int(config.start_position)
                self._current_page = int(config.start_position)
            except ValueError:
                self._current_cursor = config.start_position

        while self._total_fetched < max_records:
            page_params = self._get_next_page_params(self._current_page == 1)
            if page_params is None:
                break
            params.update(page_params)
            if batch_size:
                params[self.page_size_param] = batch_size

            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    response = await self._make_request(params)
                    break
                except (ConnectorRateLimitError, ConnectorConnectionError) as exc:
                    last_error = exc
                    if attempt < max_retries:
                        delay = exponential_backoff(attempt, backoff_factor, max_delay)
                        self.logger.warning("Retry %d/%d after %0.2fs: %s", attempt + 1, max_retries, delay, exc)
                        await asyncio.sleep(delay)
                    else:
                        raise ConnectorFetchError(f"Fetch failed after {max_retries} retries: {exc}") from exc
                except Exception as exc:
                    raise ConnectorFetchError(f"Unexpected fetch error: {exc}") from exc
            else:
                if last_error:
                    raise ConnectorFetchError(f"Fetch failed: {last_error}") from last_error

            records = self._navigate_data_path(response)
            if not records:
                records = response.get("data", [])

            for record in records:
                if self._total_fetched >= max_records:
                    break
                self._total_fetched += 1
                yield record

            self._update_checkpoint()

            if not records or len(records) < batch_size:
                break

    def _get_next_page_params(self, is_first: bool) -> dict[str, Any] | None:
        pt = self.pagination_type
        if pt == "page_number":
            if is_first:
                self._current_page = 1
            else:
                self._current_page += 1
            return {self.page_param: self._current_page}
        elif pt == "cursor":
            if is_first:
                self._current_cursor = None
            if self._current_cursor is None and not is_first:
                return None
            result = {}
            if self._current_cursor:
                result["cursor"] = self._current_cursor
            return result
        elif pt == "offset":
            if is_first:
                self._current_offset = 0
            else:
                self._current_offset += self.config.config.get("page_size", 100)
            return {"offset": self._current_offset}
        elif pt == "next_url":
            if is_first:
                self._next_url = None
            if self._next_url is None and not is_first:
                return None
            if self._next_url:
                return {"_next_url": self._next_url}
            return {}
        return {}

    def _update_checkpoint(self):
        self._checkpoint_data = {
            "page": self._current_page,
            "offset": self._current_offset,
            "cursor": self._current_cursor,
            "total_fetched": self._total_fetched,
            "timestamp": time.time(),
        }

    async def validate(self) -> ConnectorValidationResult:
        result = await super().validate()
        if not self.base_url:
            result.is_valid = False
            result.errors.append("base_url is required")
        return result


connector_registry.register("rest_api", RESTAPIConnector)
