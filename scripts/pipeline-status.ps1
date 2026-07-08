#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Real-time pipeline health dashboard for ProxyDefence.
  Probes all 7 microservices, 3 infra components, and Kafka consumer lag.
#>

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\dev\common\colors.ps1"
. "$PSScriptRoot\dev\common\paths.ps1"
. "$PSScriptRoot\dev\common\load-env.ps1" -RepoRoot $Script:RepoRoot

$kafkaBootstrap = if ($env:KAFKA_BOOTSTRAP_SERVERS) { $env:KAFKA_BOOTSTRAP_SERVERS } else { "127.0.0.1:9092" }

# ─── Header ───
Write-Host "`n==============================================" -ForegroundColor $Script:CCyan
Write-Host "  ProxyDefence — Pipeline Health Dashboard" -ForegroundColor $Script:CCyan
Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor $Script:CCyan
Write-Host "==============================================" -ForegroundColor $Script:CCyan

# ─── Check HTTP service ───
function Check-HttpService {
    param([string]$Name, [string]$Url, [int]$Port, [string]$HealthField = "status")

    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $status = "down"; $uptime = "-"; $detail = ""

    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 4 -ErrorAction Stop
        $sw.Stop()
        $ms = $sw.ElapsedMilliseconds

        try {
            $body = $r.Content | ConvertFrom-Json
            $rawStatus = $body.$HealthField
            if (-not $rawStatus) { $rawStatus = $body.status }
            if (-not $rawStatus) { $rawStatus = "running" }

            $uptime = if ($body.uptime) { $body.uptime } else { "-" }

            if ($rawStatus -in @("healthy", "alive", "ok", "running", "up", $true)) {
                $status = "up"
            } elseif ($rawStatus -in @("degraded", "warning")) {
                $status = "degraded"
            } else {
                $status = "down"
                $detail = " ($rawStatus)"
            }
        } catch {
            $status = "up"
            $detail = ""
        }
    } catch {
        $sw.Stop()
        $ms = $sw.ElapsedMilliseconds
        $status = "down"
    }

    $icon = switch ($status) {
        "up"       { "●" }
        "degraded" { "◐" }
        "down"     { "○" }
    }
    $color = switch ($status) {
        "up"       { $Script:CGreen }
        "degraded" { $Script:CYellow }
        "down"     { $Script:CRed }
    }

    Write-Host ("  {0,-22} {1,-2} port {2,-5} " -f $Name, $icon, $Port) -NoNewline
    $msStr = if ($status -eq "down") { "-" } else { "${ms}ms" }
    Write-Host ("{0,-8} " -f $msStr) -NoNewline
    Write-Host "$status$detail" -ForegroundColor $color
    if ($uptime -and $uptime -ne "-") {
        Write-Host ("  {0,-22} {1,-2}         uptime: {2}" -f "", "", $uptime) -ForegroundColor $Script:CGray
    }

    return @{ Status = $status; LatencyMs = $ms; Uptime = $uptime }
}

# ─── Check TCP port ───
function Check-TcpPort {
    param([string]$Name, [int]$Port)

    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $conn = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
        $sw.Stop()
        $ms = $sw.ElapsedMilliseconds

        if ($conn -and $conn.State -eq "Listen") {
            Write-Host ("  {0,-22} ● port {1,-5} {2}ms   up" -f $Name, $Port, $ms) -ForegroundColor $Script:CGreen
            return @{ Status = "up"; LatencyMs = $ms }
        }
        Write-Host ("  {0,-22} ○ port {1,-5} {2}ms   down" -f $Name, $Port, $ms) -ForegroundColor $Script:CRed
        return @{ Status = "down"; LatencyMs = $ms }
    } catch {
        $sw.Stop()
        Write-Host ("  {0,-22} ○ port {1,-5} {2}ms   down" -f $Name, $Port, $sw.ElapsedMilliseconds) -ForegroundColor $Script:CRed
        return @{ Status = "down"; LatencyMs = $sw.ElapsedMilliseconds }
    }
}

# ─── Check Kafka consumer lag via modular-api ───
function Check-KafkaLag {
    Write-Step "Kafka Consumer Lag"
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8000/health/kafka" -UseBasicParsing -TimeoutSec 4 -ErrorAction SilentlyContinue
        $body = $r.Content | ConvertFrom-Json
        if ($body.topics -or $body.lag -or $body.consumers) {
            Write-Ok "Kafka consumer lag data available"
            if ($body.topics) {
                $body.topics | Get-Member -MemberType NoteProperty | ForEach-Object {
                    $t = $_.Name
                    $info = $body.topics.$t
                    Write-Host ("    {0,-22} partitions: {1}, lag: {2}" -f $t, $info.partitions, $info.lag) -ForegroundColor $Script:CGray
                }
            }
            if ($body.lag) {
                Write-Host ("    Total lag: {0}" -f $body.lag) -ForegroundColor $Script:CYellow
            }
            return $true
        }
        Write-Info "No Kafka consumer lag data at /health/kafka"
        return $false
    } catch {
        Write-Warn "modular-api /health/kafka not available"
        return $false
    }
}

# ─── Services health ───
Write-Step "Microservices"
$serviceResults = @{}
$serviceResults["modular-api"]      = Check-HttpService -Name "modular-api"       -Url "http://localhost:8000/"       -Port 8000
$serviceResults["ingest-service"]   = Check-HttpService -Name "ingest-service"    -Url "http://localhost:8001/"       -Port 8001
$serviceResults["ml-service"]       = Check-HttpService -Name "ml-service"        -Url "http://localhost:8002/"       -Port 8002
$serviceResults["database-service"] = Check-HttpService -Name "database-service"  -Url "http://localhost:8003/health"  -Port 8003
$serviceResults["embedding-service"]= Check-HttpService -Name "embedding-service" -Url "http://localhost:8005/"       -Port 8005
$serviceResults["energy-service"]   = Check-HttpService -Name "energy-service"    -Url "http://localhost:8006/"       -Port 8006
$serviceResults["ml-platform"]      = Check-HttpService -Name "ml-platform"       -Url "http://localhost:8007/"       -Port 8007

# ─── Infrastructure ───
Write-Step "Infrastructure"
$infraResults = @{}
$infraResults["postgresql"]    = Check-TcpPort -Name "PostgreSQL"     -Port 5432
$infraResults["kafka"]        = Check-TcpPort -Name "Kafka"          -Port 9092
$infraResults["elasticsearch"]= Check-TcpPort -Name "Elasticsearch"  -Port 9200

# ─── Kafka consumer lag ───
Check-KafkaLag

# ─── Summary Table ───
Write-Step "Summary"
Write-Host ("  {0,-22} {1,-6} {2,-8} {3,-10}" -f "Component", "Port", "Status", "Latency") -ForegroundColor $Script:CCyan
Write-Host ("  {0,-22} {1,-6} {2,-8} {3,-10}" -f ("-" * 22), ("-" * 6), ("-" * 8), ("-" * 10)) -ForegroundColor $Script:CGray

$allResults = $serviceResults + $infraResults
$upCount = 0; $degradedCount = 0; $downCount = 0
foreach ($kv in $allResults.GetEnumerator()) {
    $s = $kv.Value.Status
    $icon = switch ($s) {
        "up"       { "●" ; $upCount++ }
        "degraded" { "◐" ; $degradedCount++ }
        "down"     { "○" ; $downCount++ }
    }
    $color = switch ($s) {
        "up"       { $Script:CGreen }
        "degraded" { $Script:CYellow }
        "down"     { $Script:CRed }
    }
    $latencyStr = if ($kv.Value.LatencyMs -and $s -ne "down") { "$($kv.Value.LatencyMs)ms" } else { "-" }
    Write-Host ("  {0,-22} port {1,-3} {2,-8} {3,-10}" -f $kv.Key, $kv.Key.Port, $icon, $latencyStr) -ForegroundColor $color
}

Write-Host ""
Write-Host ("  Total: {0} up, {1} degraded, {2} down (of {3})" -f $upCount, $degradedCount, $downCount, $allResults.Count) -ForegroundColor $Script:CCyan

if ($downCount -gt 0) { exit 1 }
