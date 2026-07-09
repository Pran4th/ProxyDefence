param(
    [switch]$Force
)

$ErrorActionPreference = "Continue"
$repoRoot = Split-Path -Path (Split-Path -Path (Split-Path -Path $PSScriptRoot -Parent) -Parent) -Parent
Set-Location $repoRoot

Write-Host "=== ProxyDefence Development Setup ===" -ForegroundColor Cyan

# --- Verify Python ---
try {
    $pyVer = python --version 2>&1
    Write-Host "Python: $pyVer" -ForegroundColor Green
    $verMatch = [regex]::Match($pyVer, '(\d+)\.(\d+)')
    if ([int]$verMatch.Groups[1].Value -lt 3 -or ([int]$verMatch.Groups[1].Value -eq 3 -and [int]$verMatch.Groups[2].Value -lt 10)) {
        Write-Host "ERROR: Python 3.10+ required" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "ERROR: Python not found" -ForegroundColor Red
    exit 1
}

# --- Verify Docker ---
$dockerOk = $false
try {
    $null = docker --version 2>$null
    if ($LASTEXITCODE -eq 0) { $dockerOk = $true }
}
catch {}
if ($dockerOk) {
    Write-Host "Docker: running" -ForegroundColor Green
} else {
    Write-Host "WARNING: Docker not detected. Start Docker Desktop first." -ForegroundColor Yellow
}

# --- Verify .env ---
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host ".env: created from .env.example" -ForegroundColor Yellow
        Write-Host "  >> Edit .env with your credentials <<" -ForegroundColor Yellow
    } else {
        Write-Host "WARNING: No .env or .env.example found" -ForegroundColor Yellow
    }
} else {
    Write-Host ".env: found" -ForegroundColor Green
}

$services = @(
    @{Name="ingest-service";    Dir="services/ingest-service";    Req="requirements.txt"},
    @{Name="embedding-service"; Dir="services/embedding-service"; Req="requirements.txt"},
    @{Name="database-service";  Dir="services/database-service";  Req="requirements.txt"},
    @{Name="energy-service";    Dir="services/energy-service";    Req="requirements.txt"},
    @{Name="ml-platform";       Dir="services/ml-platform";       Req="requirements.txt"},
    @{Name="modular-api";       Dir="services/modular-api";       Req="requirements.txt"}
)

# --- Shared dev dependencies -----------------------------------------------
$sharedDevReqs = @(
    "pytest",
    "pytest-cov",
    "pytest-asyncio",
    "pytest-timeout",
    "ruff",
    "pyright"
)

$allOk = $true
foreach ($svc in $services) {
    $svcDir = Join-Path $repoRoot $svc.Dir
    $venvDir = Join-Path $svcDir ".venv"
    $reqFile = Join-Path $svcDir $svc.Req

    Write-Host "`n--- $($svc.Name) ---" -ForegroundColor Cyan

    if (-not (Test-Path $reqFile)) {
        Write-Host "  SKIP: requirements.txt not found" -ForegroundColor Yellow
        continue
    }

    if ((Test-Path $venvDir) -and -not $Force) {
        Write-Host "  .venv: exists (use -Force to recreate)" -ForegroundColor Green
    } else {
        if (Test-Path $venvDir) { Remove-Item -Recurse -Force $venvDir }
        Write-Host "  Creating .venv..." -ForegroundColor Yellow
        python -m venv $venvDir
        if ($LASTEXITCODE -ne 0) { Write-Host "  FAILED" -ForegroundColor Red; $allOk = $false; continue }
        Write-Host "  .venv: created" -ForegroundColor Green
    }

    $pip = Join-Path $venvDir "Scripts\pip.exe"
    if (-not (Test-Path $pip)) {
        Write-Host "  FAILED: pip not found in .venv" -ForegroundColor Red
        $allOk = $false
        continue
    }

    Write-Host "  Installing dependencies..." -ForegroundColor Yellow
    & $pip install --quiet -r $reqFile
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  FAILED: pip install" -ForegroundColor Red
        $allOk = $false
    } else {
        Write-Host "  Dependencies: installed" -ForegroundColor Green
    }
}

# --- spaCy model for ml-platform ---
Write-Host "`n--- spaCy Model (ml-platform) ---" -ForegroundColor Cyan
$mlPip = Join-Path $repoRoot "services/ml-platform/.venv/Scripts/pip.exe"
if (Test-Path $mlPip) {
    $spacyCheck = & (Join-Path $repoRoot "services/ml-platform/.venv/Scripts/python.exe") -c "import spacy; spacy.load('en_core_web_sm')" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Downloading en_core_web_sm..." -ForegroundColor Yellow
        & $mlPip install --quiet "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl" 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  spaCy model: downloaded" -ForegroundColor Green
        } else {
            Write-Host "  WARNING: spaCy model download failed" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  spaCy model: found" -ForegroundColor Green
    }
}

# --- Install shared dev dependencies (pytest, ruff, etc.) ----------------
Write-Host "`n--- Shared Dev Dependencies ---" -ForegroundColor Cyan
$anyPip = $null
foreach ($svc in $services) {
    $svcPip = Join-Path $repoRoot $svc.Dir ".venv/Scripts/pip.exe"
    if (Test-Path $svcPip) { $anyPip = $svcPip; break }
}
if ($anyPip -and (Test-Path $anyPip)) {
    Write-Host "  Installing shared dev dependencies..." -ForegroundColor Yellow
    & $anyPip install --quiet $sharedDevReqs
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Shared dev dependencies: installed" -ForegroundColor Green
    } else {
        Write-Host "  WARNING: Some dev dependencies failed" -ForegroundColor Yellow
    }
} else {
    Write-Host "  WARNING: No working pip found, skipping dev dependencies" -ForegroundColor Yellow
}

# --- Install pre-commit hooks (if pre-commit is available) ---------------
Write-Host "`n--- Pre-commit Hooks ---" -ForegroundColor Cyan
$hookPip = $anyPip
if ($hookPip -and (Test-Path $hookPip)) {
    & $hookPip install --quiet pre-commit 2>$null
    if ($LASTEXITCODE -eq 0) {
        $preCommit = Join-Path (Split-Path $hookPip -Parent) "pre-commit.exe"
        if (-not (Test-Path $preCommit)) { $preCommit = Join-Path (Split-Path $hookPip -Parent) "pre-commit" }
        if (Test-Path $preCommit) {
            & $preCommit install 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  Pre-commit hooks: installed" -ForegroundColor Green
            } else {
                Write-Host "  WARNING: Pre-commit install failed" -ForegroundColor Yellow
            }
        } else {
            Write-Host "  WARNING: pre-commit binary not found" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  WARNING: pre-commit install failed" -ForegroundColor Yellow
    }
} else {
    Write-Host "  WARNING: No pip found, skipping pre-commit" -ForegroundColor Yellow
}

# --- Report ---
Write-Host "`n=== Setup Complete ===" -ForegroundColor Cyan
if ($allOk) {
    Write-Host "All services configured successfully." -ForegroundColor Green
} else {
    Write-Host "Some services had errors. Check output above." -ForegroundColor Yellow
}

Write-Host "`nNext steps:"
Write-Host "  1. Edit .env with your credentials"
Write-Host "  2. Run: scripts/dev/infrastructure/start-infra.ps1"
Write-Host "  3. Run: scripts/dev/backend/start-all.ps1"
Write-Host "  4. Run: scripts/dev/frontend/start-frontend.ps1"
