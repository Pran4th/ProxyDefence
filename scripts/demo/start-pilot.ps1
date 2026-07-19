param(
    [switch]$SkipVerification
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Path (Split-Path $PSScriptRoot -Parent) -Parent

& "$repoRoot\scripts\dev\infrastructure\start-infra.ps1"
& "$repoRoot\scripts\dev\backend\start-all.ps1"

$frontend = "$repoRoot\scripts\dev\frontend\start-frontend.ps1"
Start-Process powershell -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $frontend -WindowStyle Hidden

if ($SkipVerification) {
    Write-Host "Pilot services launched. Run scripts/demo/verify-pilot-readiness.ps1 when ready." -ForegroundColor Green
    exit 0
}

for ($attempt = 1; $attempt -le 24; $attempt++) {
    try {
        & "$repoRoot\scripts\demo\verify-pilot-readiness.ps1"
        Write-Host "Pilot environment is verified. Open http://127.0.0.1:8080/command to record the demo." -ForegroundColor Green
        exit 0
    } catch {
        if ($attempt -eq 24) { throw }
        Write-Host "Waiting for pilot services ($attempt/24): $($_.Exception.Message)" -ForegroundColor Yellow
        Start-Sleep -Seconds 5
    }
}
