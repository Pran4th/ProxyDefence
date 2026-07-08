#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Start all 7 API services in separate PowerShell windows with log redirection.
  Does NOT start infrastructure or consumers.
#>
param([switch]$NoWait)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Path (Split-Path -Path $PSScriptRoot -Parent) -Parent
$logDir = Join-Path $repoRoot "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

function Start-Svc {
    param([string]$Name, [string]$BackendScript, [int]$Port)
    $scriptPath = Join-Path $PSScriptRoot "backend/$BackendScript"
    $logFile = Join-Path $logDir "$Name.log"
    $title = "$Name [:$Port]"
    $cmd = "& '$scriptPath' *>&1 | Tee-Object -FilePath '$logFile' -Append"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $cmd -WindowStyle Normal
    Write-Host "  $Name [:$Port]: started" -ForegroundColor Green
    Start-Sleep -Milliseconds 500
}

Write-Host "`n=== Starting API Services ===" -ForegroundColor Cyan

# 6 standalone services
Start-Svc "ingest-service"     "start-ingest.ps1"       8001
Start-Svc "ml-service"         "start-ml.ps1"           8002
Start-Svc "database-service"   "start-database.ps1"     8003
Start-Svc "embedding-service"  "start-embedding.ps1"    8005
Start-Svc "energy-service"     "start-energy.ps1"       8006
Start-Svc "ml-platform"        "start-ml-platform.ps1"  8007

Write-Host "  (waiting 5s before modular-api)..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# modular-api (depends on PG + ES)
Start-Svc "modular-api"        "start-modular-api.ps1"  8000

Write-Host ""
Write-Host "All 7 API services launched." -ForegroundColor Green
Write-Host "Status: .\scripts\dev\status.ps1" -ForegroundColor Yellow
Write-Host "Logs:   .\scripts\dev\logs.ps1" -ForegroundColor Yellow
