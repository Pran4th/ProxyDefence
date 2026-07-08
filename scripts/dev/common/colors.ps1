#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Shared ANSI / console colour utilities for dev scripts.
#>

$Script:CCyan   = "Cyan"
$Script:CGreen  = "Green"
$Script:CYellow = "Yellow"
$Script:CRed    = "Red"
$Script:CGray   = "Gray"
$Script:CMagenta = "Magenta"

function Write-Step  { param([string]$M) Write-Host "`n=== $M ===" -ForegroundColor $Script:CCyan }
function Write-Ok    { param([string]$M) Write-Host "  OK  $M" -ForegroundColor $Script:CGreen }
function Write-Warn  { param([string]$M) Write-Host "  WARN $M" -ForegroundColor $Script:CYellow }
function Write-Fail  { param([string]$M) Write-Host "  FAIL $M" -ForegroundColor $Script:CRed }
function Write-Info  { param([string]$M) Write-Host "  $M" -ForegroundColor $Script:CGray }

function Write-ServiceStatus {
    param([string]$Name, [string]$Status)
    $icon = switch ($Status) {
        "up"  { "●" }
        "down" { "○" }
        "degraded" { "◐" }
        default { "?" }
    }
    $color = switch ($Status) {
        "up"  { $Script:CGreen }
        "down" { $Script:CRed }
        "degraded" { $Script:CYellow }
        default { $Script:CGray }
    }
    Write-Host "  $Name " -NoNewline
    Write-Host "$icon $Status" -ForegroundColor $color
}
