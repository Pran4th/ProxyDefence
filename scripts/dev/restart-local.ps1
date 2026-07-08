#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Restart the local development environment (stop + start).
.PARAMETER SkipFrontend
  Pass through to start-local.ps1.
#>
param([switch]$SkipFrontend)

$ErrorActionPreference = "Continue"
$repoRoot = Split-Path -Path (Split-Path -Path $PSScriptRoot -Parent) -Parent

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Restarting Local Development Environment" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Stop everything (leave infra running to save time)
& "$PSScriptRoot\stop-local.ps1" -SkipInfra

Write-Host "`nWaiting 3 seconds before restart..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Start everything
if ($SkipFrontend) {
    & "$PSScriptRoot\start-local.ps1" -SkipInfra -SkipFrontend
} else {
    & "$PSScriptRoot\start-local.ps1" -SkipInfra
}

Write-Host "`nRestart complete." -ForegroundColor Green
