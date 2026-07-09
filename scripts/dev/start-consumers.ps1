#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Start all 3 Kafka consumers (ml-platform, embedding, database) in separate windows.
  Each consumer writes to its own log file.
#>

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Path (Split-Path -Path $PSScriptRoot -Parent) -Parent
$logDir = Join-Path $repoRoot "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

$consumers = @(
    @{Name="ml-platform-consumer"; Dir="services/ml-platform";       File="consumer/article_enrichment.py"; LogFile="ml-platform-consumer.log"}
    @{Name="db-consumer";          Dir="services/database-service";  File="consumer.py";     LogFile="db-consumer.log"}
    @{Name="embedding-consumer";   Dir="services/embedding-service"; File="consumer.py";     LogFile="embedding-consumer.log"}
)

Write-Host "`n=== Starting Kafka Consumers ===" -ForegroundColor Cyan

foreach ($c in $consumers) {
    $svcDir = Join-Path $repoRoot $c.Dir
    $venvPython = Join-Path $svcDir ".venv/Scripts/python.exe"
    $consumerScript = Join-Path $svcDir $c.File
    $logFile = Join-Path $logDir $c.LogFile

    if (-not (Test-Path $venvPython)) {
        Write-Host "  $($c.Name): skipped (.venv not found)" -ForegroundColor Yellow
        continue
    }
    if (-not (Test-Path $consumerScript)) {
        Write-Host "  $($c.Name): skipped ($($c.File) not found)" -ForegroundColor Yellow
        continue
    }

    $cmd = @"
`$ErrorActionPreference = 'Stop'
. '$repoRoot\scripts\dev\common\load-env.ps1' -RepoRoot '$repoRoot'
`$env:PYTHONPATH = '$repoRoot'
`$env:ENVIRONMENT = 'development'
Set-Location '$svcDir'
& '$venvPython' '$consumerScript' *>&1 | Tee-Object -FilePath '$logFile' -Append
"@
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $cmd -WindowStyle Normal
    Write-Host "  $($c.Name): started" -ForegroundColor Green
    Start-Sleep -Milliseconds 500
}

Write-Host "`nAll consumers launched." -ForegroundColor Green
