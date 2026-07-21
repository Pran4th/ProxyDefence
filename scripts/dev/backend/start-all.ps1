$repoRoot = Split-Path -Path (Split-Path -Path (Split-Path -Path $PSScriptRoot -Parent) -Parent) -Parent

Write-Host "Starting all backend services in separate windows..." -ForegroundColor Cyan

$services = @(
    @{Name="Ingest";        Script="start-ingest.ps1"},
    @{Name="Embedding";     Script="start-embedding.ps1"},
    @{Name="Database";      Script="start-database.ps1"},
    @{Name="Energy";        Script="start-energy.ps1"},
    @{Name="ML Platform";   Script="start-ml-platform.ps1"}
)

foreach ($svc in $services) {
    $scriptPath = Join-Path $PSScriptRoot $svc.Script
    Start-Process powershell -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $scriptPath -WindowStyle Hidden
    Write-Host "  $($svc.Name): started" -ForegroundColor Green
    Start-Sleep -Milliseconds 500
}

Write-Host ""
Write-Host "Modular API (depends on postgres/elastic):" -ForegroundColor Yellow
$modScript = Join-Path $PSScriptRoot "start-modular-api.ps1"
Start-Process powershell -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $modScript -WindowStyle Hidden
Write-Host "  Modular API: started" -ForegroundColor Green

Write-Host ""
Write-Host "Background consumers:" -ForegroundColor Yellow
$conScript = Join-Path $PSScriptRoot "start-consumers.ps1"
Start-Process powershell -ArgumentList "-NoExit", "-File", $conScript -WindowStyle Normal
Write-Host "  Consumers: started" -ForegroundColor Green
