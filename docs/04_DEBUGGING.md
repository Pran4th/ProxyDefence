# Debugging

## VS Code Debugging

### Prerequisites

Install the recommended VS Code extensions (prompted when opening the workspace):
- Python
- Pylance
- Black Formatter
- Ruff
- Docker
- YAML

### Launch Configurations

The workspace includes `.vscode/launch.json` with debug configurations for every service:

| Configuration | Service | Port |
|--------------|---------|------|
| Ingest Service | ingest-service | 8001 |
| ML Service | ml-service | 8002 |
| Embedding Service | embedding-service | 8005 |
| Database Service | database-service | 8003 |
| Energy Service | energy-service | 8006 |
| ML Platform | ml-platform | 8007 |
| Modular API | modular-api | 8000 |

### How to Debug

1. Open the Run and Debug view (Ctrl+Shift+D)
2. Select a service from the dropdown
3. Set breakpoints in your code
4. Press F5 to start debugging
5. The service starts with `--reload` enabled
6. When a breakpoint hits, inspect variables, step through code

### Environment Variables in Debug

All launch configurations set:
- `PYTHONPATH` to the workspace root (for `backend.shared.*` imports)
- `ENVIRONMENT` to `development`
- Service-specific vars (e.g., `ENERGY_LOAD_SEED` for energy-service)

### Just My Code

`justMyCode: true` skips debugging into installed packages.
Set to `false` in `.vscode/launch.json` if you need to step into library code.

## Hot Reload

All services run with `--reload` flag in development.
File changes trigger automatic restarts.

## Logging

Structured logging (structlog) is configured for all services.
Log levels controlled by `LOG_LEVEL` env var (default: INFO).

## Common Issues

### ModuleNotFoundError: No module named 'backend'

PYTHONPATH is not set. Run with the startup script or VS Code launch config.

### RuntimeError: Missing required environment variable

The service needs env vars from `.env`. Ensure `.env` exists and has the required variables.

### Port already in use

Another service or process is using the port. Check with:
```powershell
netstat -ano | findstr :PORT
```

### PostgreSQL connection refused

Infrastructure not running. Start with:
```powershell
scripts/dev/infrastructure/start-infra.ps1
```

### spaCy model not found

Run the setup script to download the model:
```powershell
scripts/dev/setup/setup.ps1
```
