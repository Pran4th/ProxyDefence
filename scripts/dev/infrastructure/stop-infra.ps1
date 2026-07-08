$repoRoot = Split-Path -Path (Split-Path -Path (Split-Path -Path $PSScriptRoot -Parent) -Parent) -Parent
Set-Location $repoRoot
Write-Host "Stopping infrastructure services..." -ForegroundColor Cyan
docker compose down
Write-Host "Infrastructure stopped." -ForegroundColor Green
