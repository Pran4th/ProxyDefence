#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Tail aggregated service logs from the logs/ directory.
.DESCRIPTION
  Displays real-time log output from all services.
  If no service filter is provided, shows all logs merged.
.PARAMETER Service
  Filter to a specific service. Values: ingest, ml, database, embedding, energy, ml-platform, modular-api, frontend, ml-consumer, db-consumer, embedding-consumer.
.PARAMETER Lines
  Number of most recent lines to show per service (default: 10).
.PARAMETER Follow
  Keep watching for new log entries (tail -f equivalent).
.PARAMETER All
  Show all log lines (equivalent to cat).
#>

param(
    [string]$Service,
    [int]$Lines = 10,
    [switch]$Follow,
    [switch]$All
)

$repoRoot = Split-Path -Path (Split-Path -Path $PSScriptRoot -Parent) -Parent
$logDir = Join-Path $repoRoot "logs"
$Cyan = "Cyan"; $Green = "Green"; $Yellow = "Yellow"; $Gray = "Gray"

$logFiles = @{
    "ingest"              = "ingest.log"
    "ml"                  = "ml.log"
    "database"            = "database.log"
    "embedding"           = "embedding.log"
    "energy"              = "energy.log"
    "ml-platform"         = "ml-platform.log"
    "modular-api"         = "modular-api.log"
    "frontend"            = "frontend.log"
    "ml-consumer"         = "ml-consumer.log"
    "db-consumer"         = "db-consumer.log"
    "embedding-consumer"  = "embedding-consumer.log"
}

# --- Validate log directory ---
if (-not (Test-Path $logDir)) {
    Write-Host "ERROR: Log directory not found at $logDir" -ForegroundColor Red
    Write-Host "Start some services first to generate logs." -ForegroundColor Yellow
    exit 1
}

# --- Select files ---
$selectedFiles = @()
if ($Service) {
    $fileKey = $Service.ToLower()
    if (-not $logFiles.ContainsKey($fileKey)) {
        Write-Host "ERROR: Unknown service '$Service'. Options: $($logFiles.Keys -join ', ')" -ForegroundColor Red
        exit 1
    }
    $path = Join-Path $logDir $logFiles[$fileKey]
    if (Test-Path $path) {
        $selectedFiles = @($path)
    } else {
        Write-Host "No log file found for '$Service' at $path" -ForegroundColor Yellow
        exit 0
    }
} else {
    $selectedFiles = Get-ChildItem $logDir -Filter "*.log" | Sort-Object Name | ForEach-Object { $_.FullName }
    if (-not $selectedFiles) {
        Write-Host "No log files found in $logDir" -ForegroundColor Yellow
        exit 0
    }
}

# --- Help text ---
Write-Host "=== ProxyDefence Logs ===" -ForegroundColor $Cyan
if ($Service) {
    Write-Host "  Service: $Service ($($selectedFiles.Count) file)" -ForegroundColor $Gray
} else {
    Write-Host "  Showing all logs ($($selectedFiles.Count) files)" -ForegroundColor $Gray
}
if ($All) {
    Write-Host "  Mode: full output" -ForegroundColor $Gray
} elseif ($Follow) {
    Write-Host "  Mode: follow (Ctrl+C to stop)" -ForegroundColor $Gray
} else {
    Write-Host "  Mode: last $Lines lines per file" -ForegroundColor $Gray
}
Write-Host ""

# --- Display ---
function Show-LogFile {
    param([string]$Path, [string]$Label, [int]$MaxLines = 10)
    $color = @($Cyan, $Green, $Yellow)[(Get-Random -Minimum 0 -Maximum 3)]

    Write-Host "--- $Label ---" -ForegroundColor $color

    if ($All) {
        Get-Content $Path
    } else {
        Get-Content $Path -Tail $MaxLines
    }
    Write-Host ""
}

if ($Follow) {
    $label = if ($Service) { $Service } else { "all services" }

    if ($selectedFiles.Count -eq 1) {
        Write-Host "Following $label ($($selectedFiles[0]))" -ForegroundColor $Cyan
        Write-Host "Ctrl+C to exit`n" -ForegroundColor $Gray
        Get-Content $selectedFiles[0] -Wait
    } else {
        Write-Host "Following $label ($($selectedFiles.Count) files)" -ForegroundColor $Cyan
        Write-Host "Ctrl+C to exit`n" -ForegroundColor $Gray
        foreach ($path in $selectedFiles) {
            $name = [System.IO.Path]::GetFileNameWithoutExtension($path)
            Start-Job -ScriptBlock {
                param($p, $n)
                Get-Content $p -Wait | ForEach-Object { Write-Output "[$n] $_" }
            } -ArgumentList $path, $name | Out-Null
        }
        while ($true) {
            Get-Job | Where-Object { $_.HasMoreData } | ForEach-Object {
                Receive-Job $_
            }
            Start-Sleep -Milliseconds 200
        }
    }
} else {
    foreach ($path in $selectedFiles) {
        $name = [System.IO.Path]::GetFileNameWithoutExtension($path)
        Show-LogFile -Path $path -Label $name -MaxLines $Lines
    }
}
