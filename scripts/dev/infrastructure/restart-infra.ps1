$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Path (Split-Path -Path (Split-Path -Path $PSScriptRoot -Parent) -Parent) -Parent
Set-Location $repoRoot
Write-Host "Restarting infrastructure..." -ForegroundColor Cyan
docker compose down
docker compose up -d
Write-Host "Infrastructure restarted." -ForegroundColor Green
