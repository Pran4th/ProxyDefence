param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Path (Split-Path -Path $PSScriptRoot -Parent) -Parent
Set-Location $repoRoot

Write-Host "=== Development Environment Reset ===" -ForegroundColor Cyan
Write-Host "This will remove all .venv directories." -ForegroundColor Yellow

if (-not $Force) {
    $confirm = Read-Host "Are you sure? (y/N)"
    if ($confirm -ne "y") { Write-Host "Cancelled."; exit 0 }
}

# Stop infra
Write-Host "Stopping infrastructure..." -ForegroundColor Yellow
docker compose down 2>$null

# Clean caches
& "$PSScriptRoot\clean.ps1"

# Remove venvs
Get-ChildItem -Path $repoRoot -Recurse -Directory -Filter ".venv" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Write-Host ".venv directories removed." -ForegroundColor Yellow

Write-Host "Reset complete." -ForegroundColor Green
Write-Host "Run scripts/dev/setup/setup.ps1 to recreate." -ForegroundColor Cyan
