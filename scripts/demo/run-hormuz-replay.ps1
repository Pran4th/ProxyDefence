param(
    [ValidateSet("abqaiq-2019", "russia-sanctions-2022", "red-sea-2024")]
    [string]$Case = "abqaiq-2019",
    [int]$MaxTicks = 30,
    [string]$EnergyUrl = "http://127.0.0.1:8006"
)

$ErrorActionPreference = "Stop"

try {
    $health = Invoke-RestMethod "$EnergyUrl/health" -TimeoutSec 10
    if ($health.status -notin @("healthy", "ok")) { throw "Energy service health is $($health.status)." }
} catch {
    throw "Energy service is not ready at $EnergyUrl. Start infrastructure and services first. $($_.Exception.Message)"
}

$result = Invoke-RestMethod "$EnergyUrl/api/v1/intelligence/command/replays/$Case/run" `
    -Method Post -ContentType "application/json" -Body (@{ max_ticks = $MaxTicks } | ConvertTo-Json) -TimeoutSec 180

$result | ConvertTo-Json -Depth 12
Write-Host "`nReplay complete: $($result.case_key)" -ForegroundColor Green
Write-Host "Evidence bundle: $($result.response.evidence_bundle.uuid)" -ForegroundColor Green
Write-Host "Pipeline latency: $($result.measured_results.pipeline_latency_seconds)s" -ForegroundColor Green
