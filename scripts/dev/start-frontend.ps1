#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Start the Vite dev server for the frontend.
  Writes logs to logs/frontend.log.
#>

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Path (Split-Path -Path $PSScriptRoot -Parent) -Parent
$frontendDir = Join-Path $repoRoot "services/frontend"
$logDir = Join-Path $repoRoot "logs"
$logFile = Join-Path $logDir "frontend.log"

if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
    Set-Location $frontendDir
    npm install
}

Write-Host "Starting frontend (Vite dev server)..." -ForegroundColor Cyan
Write-Host "  Logs: $logFile" -ForegroundColor Gray
Write-Host "  URL:  http://localhost:8080" -ForegroundColor Green

$cmd = @"
Set-Location '$frontendDir'
npm run dev *>&1 | Tee-Object -FilePath '$logFile' -Append
"@

Start-Process powershell -ArgumentList "-NoExit", "-Command", $cmd -WindowStyle Normal
