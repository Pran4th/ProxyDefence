param(
    [string]$Service,
    [switch]$Infra
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Path (Split-Path -Path $PSScriptRoot -Parent) -Parent
Set-Location $repoRoot

$env:PYTHONPATH = $repoRoot
$env:ENVIRONMENT = "test"

if ($Service) {
    $svcDir = Join-Path $repoRoot "services/$Service"
    if (-not (Test-Path $svcDir)) {
        Write-Host "ERROR: Service '$Service' not found" -ForegroundColor Red
        exit 1
    }
    $venvPython = Join-Path $svcDir ".venv/Scripts/python.exe"
    if (Test-Path $venvPython) {
        & $venvPython -m pytest (Join-Path $svcDir "tests") -v
    } else {
        python -m pytest (Join-Path $svcDir "tests") -v
    }
} elseif ($Infra) {
    Write-Host "Running infrastructure tests..." -ForegroundColor Cyan
    python -m pytest tests/ -v
} else {
    Write-Host "Running all tests..." -ForegroundColor Cyan
    python -m pytest tests/ -v 2>&1 | Out-Null
    if (Test-Path "services/ml-platform/tests") {
        Write-Host "`n--- ml-platform tests ---" -ForegroundColor Cyan
        $mlPython = "services/ml-platform/.venv/Scripts/python.exe"
        if (Test-Path $mlPython) {
            & $mlPython -m pytest services/ml-platform/tests -v
        } else {
            python -m pytest services/ml-platform/tests -v
        }
    }
}
