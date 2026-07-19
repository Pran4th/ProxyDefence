param(
    [string]$EnergyUrl = "http://127.0.0.1:8006",
    [string]$ModularApiUrl = "http://127.0.0.1:8000",
    [string]$FrontendUrl = "http://127.0.0.1:8080",
    [ValidateSet("abqaiq-2019", "russia-sanctions-2022", "red-sea-2024")]
    [string]$Case = "abqaiq-2019"
)

$ErrorActionPreference = "Stop"

function Test-ServiceHealth([string]$Name, [string]$Url) {
    $response = Invoke-WebRequest -UseBasicParsing "$Url/health" -TimeoutSec 15
    if ($response.StatusCode -ne 200) {
        throw "$Name readiness check returned HTTP $($response.StatusCode)."
    }

    $health = $response.Content | ConvertFrom-Json
    if ($health.status -ne "healthy") {
        $dependencies = if ($health.dependencies) { $health.dependencies | ConvertTo-Json -Compress } else { "{}" }
        throw "$Name is reachable but unhealthy: $dependencies"
    }
    Write-Host "PASS $Name /health" -ForegroundColor Green
}

function Test-Frontend([string]$Url) {
    $response = Invoke-WebRequest -UseBasicParsing "$Url/command" -TimeoutSec 15
    if ($response.StatusCode -ne 200) {
        throw "Frontend readiness check returned HTTP $($response.StatusCode)."
    }
    Write-Host "PASS frontend /command" -ForegroundColor Green
}

function Invoke-JsonPost([string]$Url, [hashtable]$Body, [hashtable]$Headers = @{}) {
    Invoke-RestMethod -Method Post -Uri $Url -ContentType "application/json" -Headers $Headers -Body ($Body | ConvertTo-Json -Depth 8) -TimeoutSec 180
}

foreach ($service in @(
    @{ Name = "modular-api"; Url = $ModularApiUrl },
    @{ Name = "ingest-service"; Url = "http://127.0.0.1:8001" },
    @{ Name = "database-service"; Url = "http://127.0.0.1:8003" },
    @{ Name = "embedding-service"; Url = "http://127.0.0.1:8005" },
    @{ Name = "energy-service"; Url = $EnergyUrl },
    @{ Name = "ml-platform"; Url = "http://127.0.0.1:8007" }
)) {
    Test-ServiceHealth $service.Name $service.Url
}
Test-Frontend $FrontendUrl

foreach ($path in @("/health", "/api/v1/intelligence/sources/status", "/api/v1/intelligence/command/replays")) {
    $response = Invoke-WebRequest -UseBasicParsing "$EnergyUrl$path" -TimeoutSec 15
    if ($response.StatusCode -ne 200) { throw "Energy readiness check failed: $path returned $($response.StatusCode)" }
    Write-Host "PASS energy-service $path" -ForegroundColor Green
}

# Dedicated non-production verifier identity. Registration is idempotent through login fallback.
$credentials = @{ email = "pilot-readiness@proxydefence-test.io"; username = "pilot-readiness"; password = "PilotReadiness-2026" }
try { $auth = Invoke-JsonPost "$ModularApiUrl/auth/register" $credentials } catch { $auth = Invoke-JsonPost "$ModularApiUrl/auth/login" @{ email = $credentials.email; password = $credentials.password } }
if (-not $auth.access_token) { throw "Could not obtain validation access token from modular-api." }
$headers = @{ Authorization = "Bearer $($auth.access_token)" }

$expectedScenario = @{
    "abqaiq-2019" = "Strait of Hormuz Partial Closure"
    "russia-sanctions-2022" = "Russian Export Ban"
    "red-sea-2024" = "Red Sea Shipping Disruption"
}[$Case]

$replay = Invoke-JsonPost "$ModularApiUrl/api/v1/intelligence/command/replays/$Case/run" @{ max_ticks = 1 } $headers
$response = $replay.response
if ($response.scenario.name -ne $expectedScenario) { throw "Wrong scenario selected: $($response.scenario.name)" }
if (-not $response.evidence_bundle.uuid) { throw "Replay did not create an evidence bundle." }
if ($response.evidence_bundle.mode -notin @("live", "cached", "replay", "fallback")) { throw "Invalid evidence mode: $($response.evidence_bundle.mode)" }
if ($response.procurement_run.recommended_volume_bpd -gt $response.twin_run.aggregate_impacts.max_supply_gap_bpd) { throw "Procurement recommendation exceeds modelled supply gap." }

$bundle = Invoke-RestMethod -Uri "$ModularApiUrl/api/v1/intelligence/command/evidence/$($response.evidence_bundle.uuid)" -Headers $headers -TimeoutSec 30
if (-not $bundle.uuid -or -not $bundle.approvals) { throw "Evidence bundle is not persistently retrievable with approval history." }

Write-Host "PASS gateway replay $Case -> $($response.scenario.name)" -ForegroundColor Green
Write-Host "PASS evidence bundle $($response.evidence_bundle.uuid) [$($response.evidence_bundle.mode)]" -ForegroundColor Green
Write-Host "PASS telemetry $($response.telemetry.uuid), pipeline $($response.telemetry.pipeline_latency_seconds)s" -ForegroundColor Green
