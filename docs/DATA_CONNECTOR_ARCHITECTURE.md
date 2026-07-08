# Data Connector Architecture

## Overview

The Data Connector Framework provides a pluggable, extensible architecture for connecting to 15+ data source types. Each connector encapsulates the logic for authentication, schema discovery, pagination, rate limiting, incremental sync, and error handling behind a unified interface. The framework is designed for the ML Platform's ingestion pipeline, enabling data engineers to add new sources without modifying core ingestion logic.

The framework follows a **composite pattern**: a `ConnectorRegistry` manages the lifecycle of all registered connector implementations, which are instantiated and invoked by the `IngestionEngine`.

## Architecture

```
                         ┌─────────────────────────────────┐
                         │         ConnectorRegistry        │
                         │  (singleton, thread-safe)        │
                         └──────────┬──────────────────────┘
                                    │ register / get / list
                                    │
           ┌────────────────────────┼────────────────────────┐
           │                        │                        │
           ▼                        ▼                        ▼
  ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
  │  GNewsConnector   │   │   ACLEDConnector  │   │   ICEWSConnector  │   ...
  └──────────────────┘   └──────────────────┘   └──────────────────┘
           │                        │                        │
           └────────────────────────┼────────────────────────┘
                                    │
                                    ▼
                         ┌─────────────────────────────────┐
                         │        IngestionEngine           │
                         │  - pipeline execution            │
                         │  - context propagation           │
                         │  - step orchestration            │
                         │  - checkpoint management         │
                         └─────────────────────────────────┘
                                    │
                                    ▼
                         ┌─────────────────────────────────┐
                         │     DatasetBuilder / Catalog     │
                         └─────────────────────────────────┘
```

## Connector Lifecycle

Every connector follows a stateful lifecycle managed by the framework:

```
  ┌──────────┐    register     ┌───────────┐   configure   ┌───────────┐
  │   New     │ ──────────────▶ │  Defined  │ ─────────────▶│ Configured │
  └──────────┘                 └───────────┘               └───────────┘
                                                                 │
                                                          connect │
                                                                 ▼
                                                         ┌───────────┐
                                                         │ Connected  │
                                                         └───────────┘
                                                              │
                                                     discover │
                                                      schema  │
                                                              ▼
                                                         ┌───────────┐
                                                         │ Schema    │
                                                         │ Discovered│
                                                         └───────────┘
                                                              │
                                                        fetch │
                                                              ▼
                                                         ┌───────────┐     checkpoint  ┌───────────┐
                                                         │  Fetched  │ ──────────────▶ │Checkpoint │
                                                         └───────────┘                └───────────┘
                                                              │
                                                    disconnect│
                                                              ▼
                                                         ┌───────────┐
                                                         │Disconnected│
                                                         └───────────┘
```

| Phase | Description |
|-------|-------------|
| **Register** | Connector class is registered in `ConnectorRegistry` with a unique `connector_type` key. Schema validation runs on registration. |
| **Configure** | Runtime configuration is applied: endpoint URLs, auth credentials, rate limits, pagination strategy, retry policy. Configuration is validated against the connector's config schema. |
| **Connect** | Authentication handshake is performed. Session or client is established (e.g., OAuth2 token acquisition, API key header injection). |
| **Discover Schema** | The connector introspects the remote API or database to discover available endpoints, fields, data types, and relationships. Results are persisted to `ml.connector_schemas`. |
| **Fetch** | Data is retrieved using the configured pagination strategy. Each page is validated, normalized, and passed to the ingestion pipeline. |
| **Checkpoint** | After each successful fetch cycle, a checkpoint is persisted recording the cursor, timestamp, or sequence number for incremental sync. |
| **Disconnect** | Resources are released: connections closed, sessions terminated, rate limiter state flushed. |

## Base Connector Interface

```python
class BaseConnector(ABC):
    connector_type: str           # unique identifier
    config_schema: dict           # JSON schema for configuration

    @abstractmethod
    async def configure(self, config: dict) -> None: ...
    @abstractmethod
    async def connect(self) -> bool: ...
    @abstractmethod
    async def discover_schema(self) -> list[dict]: ...
    @abstractmethod
    async def fetch(self, context: IngestionContext) -> AsyncIterator[dict]: ...
    @abstractmethod
    async def checkpoint(self, context: IngestionContext) -> None: ...
    @abstractmethod
    async def disconnect(self) -> None: ...
```

## Connector Registry

The `ConnectorRegistry` is the central registry managing all connector implementations.

```python
class ConnectorRegistry:
    def __init__(self):
        self._registry: dict[str, type[BaseConnector]] = {}

    def register(self, connector_class: type[BaseConnector]) -> None:
        self._registry[connector_class.connector_type] = connector_class

    def get(self, connector_type: str) -> type[BaseConnector]:
        if connector_type not in self._registry:
            raise KeyError(f"No connector registered: {connector_type}")
        return self._registry[connector_type]

    def list_types(self) -> list[str]:
        return list(self._registry.keys())

    def list_supported_sources(self) -> list[dict]:
        return [
            {"type": ct, "schema": cls.config_schema}
            for ct, cls in self._registry.items()
        ]
```

Database tables `ml.connector_definitions` and `ml.connector_schemas` provide persistence for the registry state.

## Connector Types

| Connector Type | Source | Data Domain | Auth Method | Pagination |
|---------------|--------|-------------|-------------|------------|
| `gnews` | GNews API | News articles | API key | page_number |
| `acled` | ACLED API | Conflict events | API key | page_number |
| `icews` | ICEWS API | Political events | API key | cursor |
| `eia` | EIA API | Energy statistics | API key | offset |
| `fred` | FRED API | Economic data | API key | offset |
| `ais` | AIS streaming | Maritime traffic | Bearer | cursor |
| `gdelt` | GDELT API | Global news events | None | next_url |
| `who` | WHO API | Health data | API key | offset |
| `unodc` | UNODC API | Crime statistics | API key | offset |
| `imf` | IMF API | Financial data | API key | offset |
| `world_bank` | World Bank API | Development data | None | page_number |
| `energy_service` | Energy Service | Infrastructure catalog | Bearer | offset |
| `postgres` | PostgreSQL | Internal tables | Basic | cursor |
| `elasticsearch` | Elasticsearch | Search indices | Basic | cursor |
| `s3` | S3 Buckets | File storage | Bearer | next_url |
| `kafka` | Kafka Streams | Event streams | None (VPC) | cursor |
| `csv_upload` | User uploads | Batch files | None | offset |

## Authentication Patterns

The framework supports four authentication strategies, configurable per connector instance.

### Basic Auth

```python
class BasicAuth:
    def __init__(self, username: str, password: str):
        self._token = base64.b64encode(f"{username}:{password}".encode()).decode()

    def apply(self, headers: dict) -> dict:
        headers["Authorization"] = f"Basic {self._token}"
        return headers
```

### Bearer Token

```python
class BearerAuth:
    def __init__(self, token: str):
        self._token = token

    def apply(self, headers: dict) -> dict:
        headers["Authorization"] = f"Bearer {self._token}"
        return headers
```

### API Key

```python
class ApiKeyAuth:
    def __init__(self, key: str, param_name: str = "apiKey", in_header: bool = True):
        self._key = key
        self._param_name = param_name
        self._in_header = in_header

    def apply(self, headers: dict, params: dict) -> tuple[dict, dict]:
        if self._in_header:
            headers[self._param_name] = self._key
        else:
            params[self._param_name] = self._key
        return headers, params
```

### OAuth2

```python
class OAuth2Auth:
    def __init__(self, client_id: str, client_secret: str, token_url: str,
                 scopes: list[str] | None = None):
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url
        self._scopes = scopes or []
        self._token: str | None = None
        self._expires_at: float = 0

    async def authenticate(self) -> str:
        if self._token and time.time() < self._expires_at - 60:
            return self._token
        # OAuth2 client credentials grant flow
        resp = await httpx.AsyncClient().post(
            self._token_url,
            data={"grant_type": "client_credentials", "scope": " ".join(self._scopes)},
            auth=(self._client_id, self._client_secret),
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._expires_at = time.time() + data.get("expires_in", 3600)
        return self._token
```

## Pagination Strategies

### Page Number

Simple page-based pagination where the client requests `?page=N`.

```yaml
pagination:
  strategy: page_number
  param_name: page
  page_size_param: page_size
  page_size: 100
  max_pages: 1000
```

### Cursor

Cursor-based pagination using an opaque token from the API response.

```yaml
pagination:
  strategy: cursor
  cursor_param: after
  cursor_path: "$.meta.next_cursor"
  page_size_param: limit
  page_size: 100
```

### Offset

Offset-based pagination (`?offset=N&limit=M`).

```yaml
pagination:
  strategy: offset
  offset_param: offset
  limit_param: limit
  page_size: 500
  max_offset: 10000
```

### Next URL

The API returns a full URL for the next page in its response body.

```yaml
pagination:
  strategy: next_url
  next_url_path: "$.meta.next_page_url"
```

## Rate Limiting (Token Bucket Algorithm)

Every connector is configured with a token bucket rate limiter operating at the per-connector-instance level.

```python
class TokenBucket:
    def __init__(self, capacity: int, refill_rate: float, refill_interval: float = 1.0):
        self._capacity = capacity
        self._tokens = float(capacity)
        self._refill_rate = refill_rate
        self._refill_interval = refill_interval
        self._last_refill = time.monotonic()

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self._last_refill
        added = elapsed * self._refill_rate
        self._tokens = min(self._capacity, self._tokens + added)
        self._last_refill = now

    async def acquire(self, tokens: int = 1) -> float:
        while True:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return 0.0
            wait = (tokens - self._tokens) / self._refill_rate
            await asyncio.sleep(wait)
```

**Algorithm behavior**:
- **Capacity**: maximum burst size (e.g., 100 requests)
- **Refill rate**: tokens added per second (e.g., 10 tokens/sec = 10 requests/sec sustained)
- **Acquire**: blocks until `tokens` are available, returns the wait time
- Used before every API call to enforce the configured rate limit

Example configuration:

```yaml
rate_limit:
  strategy: token_bucket
  capacity: 100
  refill_rate: 10.0
  refill_interval: 1.0
```

## Retry with Exponential Backoff + Jitter

The framework implements retry with full jitter exponential backoff as described in the AWS architecture blog.

```python
class RetryPolicy:
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0,
                 max_delay: float = 120.0, jitter: bool = True):
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._jitter = jitter

    def get_delay(self, attempt: int) -> float:
        delay = min(self._base_delay * (2 ** attempt), self._max_delay)
        if self._jitter:
            delay = random.uniform(0, delay)
        return delay

    async def execute(self, func, *args, **kwargs):
        last_exception = None
        for attempt in range(self._max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except (httpx.TimeoutException, httpx.HTTPStatusError,
                    ConnectionError) as e:
                last_exception = e
                if attempt < self._max_retries:
                    delay = self.get_delay(attempt)
                    logger.warning("retry %d/%d after %.2fs: %s",
                                   attempt + 1, self._max_retries, delay, e)
                    await asyncio.sleep(delay)
        raise last_exception
```

**Retryable errors**: `5xx` status codes, `408 Request Timeout`, `429 Too Many Requests`, connection errors, DNS failures, SSL errors.

**Non-retryable errors**: `4xx` (except 408/429), authentication failures, invalid requests.

## Incremental Sync via Checkpointing

Each connector maintains checkpoints in `ml.connector_checkpoints` for resumable incremental ingestion.

```python
class CheckpointManager:
    def __init__(self, connector_name: str, connector_version: int = 1):
        self._connector_name = connector_name
        self._connector_version = connector_version

    async def save(self, key: str, value: str, checkpoint_type: str = "cursor",
                   snapshot: dict | None = None) -> None:
        pool = await get_pool()
        await pool.execute(
            """
            INSERT INTO ml.connector_checkpoints
                (connector_name, connector_version, checkpoint_key,
                 checkpoint_value, checkpoint_type, snapshot)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (connector_name, connector_version, checkpoint_key)
            DO UPDATE SET checkpoint_value = $4, snapshot = $6,
                          updated_at = NOW()
            """,
            self._connector_name, self._connector_version,
            key, value, checkpoint_type, json.dumps(snapshot or {}),
        )

    async def load(self, key: str) -> dict | None:
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT * FROM ml.connector_checkpoints "
            "WHERE connector_name = $1 AND connector_version = $2 AND checkpoint_key = $3",
            self._connector_name, self._connector_version, key,
        )
        return dict(row) if row else None
```

**Checkpoint types**: `cursor` (opaque token), `timestamp` (ISO 8601 datetime), `sequence` (monotonic integer), `offset` (page offset).

## Schema Discovery

On first connect (or on demand), each connector discovers its schema and persists it to `ml.connector_schemas`.

```python
class SchemaDiscoverer:
    @staticmethod
    async def discover_and_register(connector_name: str, connector: BaseConnector) -> list[dict]:
        schemas = await connector.discover_schema()
        pool = await get_pool()
        registered = []
        for schema in schemas:
            row = await pool.fetchrow(
                """
                INSERT INTO ml.connector_schemas
                    (connector_name, schema_name, schema_type, fields_json,
                     required_fields, nullable_fields, primary_key_fields,
                     validation_rules, description)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (connector_name, schema_name)
                DO UPDATE SET fields_json = $4, validation_rules = $8,
                              updated_at = NOW()
                RETURNING *
                """,
                connector_name,
                schema["name"],
                schema["type"],
                json.dumps(schema.get("fields", [])),
                json.dumps(schema.get("required", [])),
                json.dumps(schema.get("nullable", [])),
                json.dumps(schema.get("primary_key", [])),
                json.dumps(schema.get("validation_rules", {})),
                schema.get("description"),
            )
            registered.append(dict(row))
        return registered
```

## Error Handling Hierarchy

```
ConnectorError
├── AuthenticationError        # Invalid/expired credentials
│   ├── TokenExpiredError
│   ├── InvalidCredentialsError
│   └── InsufficientPermissionsError
├── ConnectionError            # Network-level failures
│   ├── TimeoutError
│   ├── DNSResolutionError
│   └── ConnectionRefusedError
├── RateLimitError             # Rate limit exceeded
│   └── QuotaExceededError
├── SchemaError                # Schema-related issues
│   ├── SchemaMismatchError
│   └── RequiredFieldMissingError
├── DataError                  # Data-level failures
│   ├── ValidationError
│   ├── TransformationError
│   └── SerializationError
├── PaginationError            # Pagination failures
│   └── MaxPagesExceededError
└── CheckpointError            # Checkpoint persistence failures
```

Each error carries structured metadata for observability:

```python
@dataclass
class ConnectorError(Exception):
    connector_type: str
    error_code: str
    message: str
    details: dict = field(default_factory=dict)
    retryable: bool = False
    cause: Exception | None = None
```

## Integration with Ingestion Pipeline

The connector framework integrates with the `IngestionPipeline` through the `IngestionEngine`:

1. Pipeline step `download` calls `connector.fetch()` with pagination
2. Each page of data is passed through `extract` and `validate` steps
3. Checkpoints are updated after successful page processing
4. `IngestionContext` carries connector state between steps
5. Pipeline failure triggers connector-level retry via `RetryPolicy`

Future connectors for GDELT, ACLED, ICEWS, AIS, EIA, FRED, and WHO will follow the same lifecycle and interface contract defined above.
