#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Database reset utility for ProxyDefence.
  Drops and recreates database schemas from the canonical SQL files.
.PARAMETER All
  Reset ALL schemas (public, energy, ml).
.PARAMETER Public
  Reset only the public schema tables.
.PARAMETER Energy
  Reset only the energy schema.
.PARAMETER Ml
  Reset only the ml schema.
.PARAMETER Force
  Skip confirmation prompt.
#>

param(
    [switch]$All,
    [switch]$Public,
    [switch]$Energy,
    [switch]$Ml,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\dev\common\colors.ps1"
. "$PSScriptRoot\dev\common\paths.ps1"
. "$PSScriptRoot\dev\common\load-env.ps1" -RepoRoot $Script:RepoRoot

$sqlDir = Join-Path $Script:RepoRoot "infra\sql"

# ─── Determine targets ───
$targets = @{}
if ($All -or (-not $Public -and -not $Energy -and -not $Ml)) {
    $targets["public"] = $true
    $targets["energy"] = $true
    $targets["ml"]     = $true
}
if ($Public)  { $targets["public"] = $true }
if ($Energy)  { $targets["energy"] = $true }
if ($Ml)      { $targets["ml"]     = $true }

if ($targets.Count -eq 0) {
    Write-Fail "No target specified. Use -All, -Public, -Energy, -Ml, or any combination."
    exit 1
}

# ─── Validate SQL files exist ───
$sqlFiles = @{
    "public" = Join-Path $sqlDir "init.sql"
    "energy" = Join-Path $sqlDir "energy_schema.sql"
    "ml"     = Join-Path $sqlDir "ml_schema.sql"
}
foreach ($kv in $targets.GetEnumerator()) {
    if (-not (Test-Path $sqlFiles[$kv.Key])) {
        Write-Fail "SQL file not found: $($sqlFiles[$kv.Key])"
        exit 1
    }
}

# ─── PostgreSQL connection ───
$pgHost = if ($env:POSTGRES_HOST) { $env:POSTGRES_HOST } else { "127.0.0.1" }
$pgPort = 5432
$pgDb   = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "defenseintel" }
$pgUser = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "admin" }
$pgPass = if ($env:POSTGRES_PASSWORD) { $env:POSTGRES_PASSWORD } else { "change-me" }

$env:PGPASSWORD = $pgPass
$psqlArgs = @("-h", $pgHost, "-p", "$pgPort", "-U", $pgUser, "-d", $pgDb, "-v", "ON_ERROR_STOP=1", "-q")

function Invoke-Psql {
    param([string]$Sql)
    try {
        $result = & "psql" @psqlArgs -t -c $Sql 2>&1
        if ($LASTEXITCODE -ne 0) { throw "psql exited with code $LASTEXITCODE" }
        return $result
    } catch {
        if ($_.Exception.Message -like "*not recognized*" -or $_.Exception.Message -like "*not found*") {
            throw "psql not found in PATH. Install PostgreSQL client tools or add psql to your PATH."
        }
        throw $_
    }
}

function Invoke-PsqlFromFile {
    param([string]$FilePath)
    try {
        & "psql" @psqlArgs -f $FilePath 2>&1
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

# ─── Verify connectivity ───
try {
    $v = Invoke-Psql -Sql "SELECT version();"
    Write-Ok "Connected to PostgreSQL: $($v.Trim())"
} catch {
    Write-Fail "Cannot connect to PostgreSQL on ${pgHost}:${pgPort}: $_"
    exit 1
}

# ─── Confirmation prompt ───
Write-Host "`n==============================================" -ForegroundColor $Script:CRed
Write-Host "  WARNING: Database Reset Utility" -ForegroundColor $Script:CRed
Write-Host "==============================================" -ForegroundColor $Script:CRed
Write-Host "  Target: $($targets.Keys -join ', ')" -ForegroundColor $Script:CYellow
Write-Host "  Host:   $pgHost:$pgPort" -ForegroundColor $Script:CYellow
Write-Host "  DB:     $pgDb" -ForegroundColor $Script:CYellow

if (-not $Force) {
    $confirm = Read-Host "`nThis will DROP all data in the selected schemas. Continue? (y/N) "
    if ($confirm -ne "y") {
        Write-Warn "Reset cancelled."
        exit 0
    }
}

Write-Step "Database Reset Starting"

# ─── Reset public schema ───
$publicOk = $true
if ($targets["public"]) {
    Write-Step "Resetting public schema"
    $dropSql = @"
DO \$\$
DECLARE r RECORD;
BEGIN
    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename != 'spatial_ref_sys')
    LOOP
        EXECUTE 'DROP TABLE IF EXISTS public.' || quote_ident(r.tablename) || ' CASCADE';
    END LOOP;
END \$\$;
"@
    try {
        Invoke-Psql -Sql ($dropSql -replace "`r?`n", " ")
        Write-Ok "Dropped all public tables"

        $publicOk = Invoke-PsqlFromFile -FilePath $sqlFiles["public"]
        if ($publicOk) {
            Write-Ok "Public schema recreated from init.sql"
        } else {
            Write-Fail "Failed to recreate public schema from init.sql"
        }
    } catch {
        Write-Fail "Error resetting public schema: $_"
        $publicOk = $false
    }
}

# ─── Reset energy schema ───
$energyOk = $true
if ($targets["energy"]) {
    Write-Step "Resetting energy schema"
    try {
        Invoke-Psql -Sql "DROP SCHEMA IF EXISTS energy CASCADE;"
        Write-Ok "Dropped energy schema"

        $energyOk = Invoke-PsqlFromFile -FilePath $sqlFiles["energy"]
        if ($energyOk) {
            Write-Ok "Energy schema recreated from energy_schema.sql"
        } else {
            Write-Fail "Failed to recreate energy schema from energy_schema.sql"
        }
    } catch {
        Write-Fail "Error resetting energy schema: $_"
        $energyOk = $false
    }
}

# ─── Reset ml schema ───
$mlOk = $true
if ($targets["ml"]) {
    Write-Step "Resetting ml schema"
    try {
        Invoke-Psql -Sql "DROP SCHEMA IF EXISTS ml CASCADE;"
        Write-Ok "Dropped ml schema"

        $mlOk = Invoke-PsqlFromFile -FilePath $sqlFiles["ml"]
        if ($mlOk) {
            Write-Ok "ML schema recreated from ml_schema.sql"
        } else {
            Write-Fail "Failed to recreate ml schema from ml_schema.sql"
        }
    } catch {
        Write-Fail "Error resetting ml schema: $_"
        $mlOk = $false
    }
}

# ─── Final report ───
Write-Step "Reset Results"
$allOk = $true
if ($targets["public"]) {
    if ($publicOk) { Write-Ok "Public schema: OK" } else { Write-Fail "Public schema: FAILED"; $allOk = $false }
}
if ($targets["energy"]) {
    if ($energyOk) { Write-Ok "Energy schema: OK" } else { Write-Fail "Energy schema: FAILED"; $allOk = $false }
}
if ($targets["ml"]) {
    if ($mlOk) { Write-Ok "ML schema:     OK" } else { Write-Fail "ML schema:     FAILED"; $allOk = $false }
}

if ($allOk) {
    Write-Ok "Database reset completed successfully"
} else {
    Write-Fail "Some schemas failed to reset — check errors above"
    exit 1
}
