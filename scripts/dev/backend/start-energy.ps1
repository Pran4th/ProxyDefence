$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Path (Split-Path -Path (Split-Path -Path $PSScriptRoot -Parent) -Parent) -Parent
$svcDir = Join-Path $repoRoot "services/energy-service"
$venvPython = Join-Path $svcDir ".venv/Scripts/python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "ERROR: .venv not found at $venvPython. Run scripts/dev/setup/setup.ps1 first." -ForegroundColor Red
    exit 1
}

$loadEnv = Join-Path $repoRoot "scripts\dev\common\load-env.ps1"
. $loadEnv -RepoRoot $repoRoot

Set-Location $svcDir
$env:PYTHONPATH = $repoRoot
$env:ENVIRONMENT = "development"
& $venvPython -m uvicorn app:app --host 0.0.0.0 --port 8006 --reload
