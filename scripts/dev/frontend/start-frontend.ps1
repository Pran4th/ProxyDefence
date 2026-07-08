$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Path (Split-Path -Path (Split-Path -Path $PSScriptRoot -Parent) -Parent) -Parent
$frontendDir = Join-Path $repoRoot "services/frontend"

if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
    Set-Location $frontendDir
    npm install
}

Set-Location $frontendDir
Write-Host "Starting frontend (Vite dev server)..." -ForegroundColor Cyan
npm run dev
