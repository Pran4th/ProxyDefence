$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Path (Split-Path -Path (Split-Path -Path $PSScriptRoot -Parent) -Parent) -Parent
Set-Location $repoRoot

Write-Host "Starting infrastructure services..." -ForegroundColor Cyan
docker compose up -d

if ($LASTEXITCODE -eq 0) {
    Write-Host "Infrastructure started." -ForegroundColor Green
    Write-Host "  PostgreSQL: localhost:5434"
    Write-Host "  Kafka:      localhost:9092"
    Write-Host "  Elasticsearch: localhost:9200"
} else {
    Write-Host "Failed to start infrastructure." -ForegroundColor Red
    exit 1
}
