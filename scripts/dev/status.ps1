#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Check the status of every local development service.
  Probes health endpoints and port listeners.
#>

$ErrorActionPreference = "Continue"
$repoRoot = Split-Path -Path (Split-Path -Path $PSScriptRoot -Parent) -Parent
$C = "Cyan"; $G = "Green"; $Y = "Yellow"; $R = "Red"

function Write-Status {
    param([string]$Name, [string]$Url, [string]$Expected = "healthy")
    Write-Host "  $Name " -NoNewline
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
        $body = $r.Content
        if ($body -match '"status"\s*:\s*"([^"]+)"') {
            $s = $matches[1]
            if ($s -eq $Expected -or $s -eq "alive" -or $s -eq "healthy") {
                Write-Host "● $s" -ForegroundColor $G
            } elseif ($s -eq "degraded") {
                Write-Host "◐ $s" -ForegroundColor $Y
            } else {
                Write-Host "○ $s" -ForegroundColor $R
            }
        } else {
            Write-Host "● running (no status field)" -ForegroundColor $G
        }
    } catch {
        Write-Host "○ down" -ForegroundColor $R
    }
}

function Check-Port {
    param([string]$Name, [int]$Port)
    Write-Host "  $Name " -NoNewline
    $conns = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    if ($conns) {
        $listening = $conns | Where-Object { $_.State -eq "Listen" }
        if ($listening) { Write-Host "● listening (port $Port)" -ForegroundColor $G }
        else { Write-Host "◐ $($conns[0].State) (port $Port)" -ForegroundColor $Y }
    } else {
        Write-Host "○ not listening (port $Port)" -ForegroundColor $R
    }
}

# --- Header ---
Write-Host "`n==========================" -ForegroundColor $C
Write-Host "  ProxyDefence - Status" -ForegroundColor $C
Write-Host "==========================`n" -ForegroundColor $C

# --- Infrastructure ---
Write-Host "Infrastructure" -ForegroundColor $C
Check-Port "PostgreSQL  " 5434
Check-Port "Kafka       " 9092
Check-Port "Elasticsearch" 9200
Write-Host ""

# --- API Services ---
Write-Host "API Services" -ForegroundColor $C
Write-Status "modular-api      " "http://localhost:8000/"
Write-Status "ingest-service   " "http://localhost:8001/"
Write-Status "database-service " "http://localhost:8003/health"
Write-Status "embedding-service" "http://localhost:8005/"
Write-Status "energy-service   " "http://localhost:8006/"
Write-Status "ml-platform      " "http://localhost:8007/"
Write-Host ""

# --- Frontend ---
Write-Host "Frontend" -ForegroundColor $C
Write-Status "Vite dev server  " "http://localhost:8080/"
Write-Host ""

# --- Log files ---
$logDir = Join-Path $repoRoot "logs"
if (Test-Path $logDir) {
    Write-Host "Log Files" -ForegroundColor $C
    $logs = Get-ChildItem $logDir -Filter "*.log" | Sort-Object LastWriteTime -Descending
    if ($logs) {
        foreach ($log in $logs) {
            $lastMod = $log.LastWriteTime.ToString("HH:mm:ss")
            $sizeKB = [math]::Round($log.Length / 1KB, 1)
            Write-Host "  $($log.BaseName) - $lastMod, ${sizeKB}KB" -ForegroundColor $G
        }
    } else {
        Write-Host "  (no log files yet)" -ForegroundColor $Y
    }
}
Write-Host ""
