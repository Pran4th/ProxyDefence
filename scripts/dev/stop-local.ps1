#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Gracefully stop all local development services.
  Kills service processes, consumers, frontend, then stops Docker infrastructure.
.PARAMETER SkipInfra
  Don't stop docker compose (leave PG, Kafka, ES running).
#>
param([switch]$SkipInfra)

$ErrorActionPreference = "Continue"
$repoRoot = Split-Path -Path (Split-Path -Path $PSScriptRoot -Parent) -Parent
$logDir = Join-Path $repoRoot "logs"
$pidFile = Join-Path $logDir "local-pids.json"
$C = "Cyan"; $G = "Green"; $Y = "Yellow"; $R = "Red"

function Write-Step { param([string]$M) Write-Host "`n=== $M ===" -ForegroundColor $C }
function Write-Ok   { param([string]$M) Write-Host "  OK  $M" -ForegroundColor $G }
function Write-Warn { param([string]$M) Write-Host "  WARN $M" -ForegroundColor $Y }

# --- 1. Kill tracked processes from PID file ---
Write-Step "Stopping Tracked Processes"
if (Test-Path $pidFile) {
    $pids = Get-Content $pidFile | ConvertFrom-Json
    $pids.PSObject.Properties | ForEach-Object {
        $entry = $_.Value
        $procId = $entry.ProcessId
        $name = $entry.Name
        try {
            $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
            if ($proc) {
                $proc.CloseMainWindow() | Out-Null
                Start-Sleep -Milliseconds 200
                if (-not $proc.HasExited) { $proc.Kill() }
                Write-Ok "$name (PID $procId) stopped"
            }
        } catch { Write-Warn "$name (PID $procId): already exited" }
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
} else {
    Write-Warn "No PID file found at $pidFile"
}

# --- 2. Kill stray uvicorn / python-consumer / npm processes ---
Write-Step "Cleaning Up Stray Processes"
$killPatterns = @(
    @{Filter="uvicorn";            Label="uvicorn (API services)"}
)

foreach ($kp in $killPatterns) {
    $procs = Get-Process -Name $kp.Filter -ErrorAction SilentlyContinue
    foreach ($p in $procs) {
        try { $p.Kill(); Write-Ok "$($kp.Label) (PID $($p.Id))" } catch {}
    }
}

# Kill python processes running consumer.py
$pythonProcs = Get-Process -Name "python" -ErrorAction SilentlyContinue
foreach ($p in $pythonProcs) {
    try {
        $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($p.Id)").CommandLine
        if ($cmdLine -match "consumer\.py") {
            $p.Kill()
            Write-Ok "consumer.py process (PID $($p.Id))"
        }
    } catch {}
}

# Kill node/vite (frontend)
$viteProcs = Get-Process -Name "node" -ErrorAction SilentlyContinue
foreach ($p in $viteProcs) {
    try {
        $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($p.Id)").CommandLine
        if ($cmdLine -match "vite") {
            $p.Kill()
            Write-Ok "frontend/vite (PID $($p.Id))"
        }
    } catch {}
}

# Kill extra PowerShell windows launched for services (detect by window title)
$powershellProcs = Get-Process -Name "powershell" -ErrorAction SilentlyContinue
foreach ($p in $powershellProcs) {
    try {
        $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($p.Id)").CommandLine
        if ($cmdLine -match "start-ingest|start-ml|start-database|start-embedding|start-energy|start-ml-platform|start-modular|start-consumer|consumer\.py") {
            $p.Kill()
            Write-Ok "service window (PID $($p.Id))"
        }
    } catch {}
}

# --- 3. Stop infrastructure ---
if (-not $SkipInfra) {
    Write-Step "Stopping Infrastructure (Docker)"
    Set-Location $repoRoot
    docker compose down
    if ($LASTEXITCODE -eq 0) { Write-Ok "docker compose down" } else { Write-Warn "docker compose down had issues" }
} else {
    Write-Step "Skipping Infrastructure (--SkipInfra)"
}

Write-Step "Local Development Environment Stopped"
Write-Host "  All services stopped." -ForegroundColor $G
Write-Host "  Use .\scripts\dev\start-local.ps1 to start again." -ForegroundColor $Y
