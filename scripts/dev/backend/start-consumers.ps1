$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Path (Split-Path -Path (Split-Path -Path $PSScriptRoot -Parent) -Parent) -Parent

. "$repoRoot\scripts\dev\common\load-env.ps1" -RepoRoot $repoRoot

$consumers = @(
    @{Name="ml-consumer";         Dir="services/ml-service";        File="consumer.py"},
    @{Name="embedding-consumer";  Dir="services/embedding-service"; File="consumer.py"},
    @{Name="db-consumer";         Dir="services/database-service";  File="consumer.py"}
)

foreach ($c in $consumers) {
    $svcDir = Join-Path $repoRoot $c.Dir
    $venvPython = Join-Path $svcDir ".venv/Scripts/python.exe"
    if (-not (Test-Path $venvPython)) {
        Write-Host "WARNING: $($c.Name) skipped (.venv not found)" -ForegroundColor Yellow
        continue
    }
    $consumerScript = Join-Path $svcDir $c.File
    Write-Host "Starting $($c.Name)..." -ForegroundColor Cyan
    $scriptBlock = "`$env:PYTHONPATH = '$repoRoot'; " +
                   "`$env:ENVIRONMENT = 'development'; " +
                   ". '$repoRoot\scripts\dev\common\load-env.ps1' -RepoRoot '$repoRoot'; " +
                   "Set-Location '$svcDir'; " +
                   "& '$venvPython' '$consumerScript'"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $scriptBlock
    Start-Sleep -Milliseconds 300
}

Write-Host "All consumers launched in separate windows." -ForegroundColor Green
