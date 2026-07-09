#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Resolved service paths, port mappings, and log paths.
  Dot-source this from any dev script:
    . "$PSScriptRoot\..\common\paths.ps1"
#>

$Script:RepoRoot = Split-Path -Path (Split-Path -Path (Split-Path -Path $PSScriptRoot -Parent) -Parent) -Parent
$Script:LogDir   = Join-Path $Script:RepoRoot "logs"

# --- Service directories ---
$Script:ServiceDirs = @{
    "ingest-service"     = Join-Path $Script:RepoRoot "services/ingest-service"
    "database-service"   = Join-Path $Script:RepoRoot "services/database-service"
    "embedding-service"  = Join-Path $Script:RepoRoot "services/embedding-service"
    "energy-service"     = Join-Path $Script:RepoRoot "services/energy-service"
    "ml-platform"        = Join-Path $Script:RepoRoot "services/ml-platform"
    "modular-api"        = Join-Path $Script:RepoRoot "services/modular-api"
    "frontend"           = Join-Path $Script:RepoRoot "services/frontend"
}

# --- Port mappings ---
$Script:ServicePorts = @{
    "modular-api"      = 8000
    "ingest-service"   = 8001
    "database-service" = 8003
    "embedding-service"= 8005
    "energy-service"   = 8006
    "ml-platform"      = 8007
    "frontend"         = 8080
}

# --- Infrastructure ports ---
$Script:InfraPorts = @{
    "postgresql" = 5432
    "kafka"      = 9092
    "elasticsearch" = 9200
}

# --- Health endpoint URLs ---
$Script:HealthUrls = @{
    "modular-api"       = "http://localhost:8000/"
    "ingest-service"    = "http://localhost:8001/"
    "database-service"  = "http://localhost:8003/health"
    "embedding-service" = "http://localhost:8005/"
    "energy-service"    = "http://localhost:8006/"
    "ml-platform"       = "http://localhost:8007/"
    "frontend"          = "http://localhost:8080/"
}

# --- Helper: resolve .venv python ---
function Get-VenvPython {
    param([string]$ServiceName)
    $dir = $Script:ServiceDirs[$ServiceName]
    if (-not $dir) { return $null }
    $py = Join-Path $dir ".venv/Scripts/python.exe"
    if (Test-Path $py) { return $py }
    return $null
}

# --- Helper: log file path ---
function Get-LogPath {
    param([string]$ServiceName)
    return Join-Path $Script:LogDir "$ServiceName.log"
}
