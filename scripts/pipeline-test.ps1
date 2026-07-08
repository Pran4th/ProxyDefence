#!/usr/bin/env pwsh
<#
.SYNOPSIS
  End-to-end pipeline validation for ProxyDefence.
  Tests ingest, Kafka, ML, DB, embedding, and API stages.
.PARAMETER PipelineType
  Pipeline stage to test: inject, kafka, ml, db, embedding, api, full (default).
.PARAMETER TimeoutSec
  Timeout in seconds per HTTP check (default: 10).
#>

param(
    [ValidateSet("inject", "kafka", "ml", "db", "embedding", "api", "full")]
    [string]$PipelineType = "full",
    [int]$TimeoutSec = 10
)

$ErrorActionPreference = "Stop"

# ─── Dot-source common modules ───
. "$PSScriptRoot\dev\common\colors.ps1"
. "$PSScriptRoot\dev\common\paths.ps1"
. "$PSScriptRoot\dev\common\load-env.ps1" -RepoRoot $Script:RepoRoot

$kafkaBootstrap = if ($env:KAFKA_BOOTSTRAP_SERVERS) { $env:KAFKA_BOOTSTRAP_SERVERS } else { "127.0.0.1:9092" }

# ─── Duration tracking ───
$script:timings = @{}
function Add-Duration { param([string]$Stage, [double]$Seconds) $script:timings[$Stage] = $Seconds }

# ─── HTTP helper ───
function Invoke-HealthCheck {
    param([string]$Url, [int]$Timeout = $TimeoutSec)
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $Timeout -ErrorAction Stop
        $sw.Stop()
        return $true, $r.StatusCode, $sw.Elapsed.TotalSeconds, ($r.Content | ConvertFrom-Json)
    } catch {
        $sw.Stop()
        return $false, $null, $sw.Elapsed.TotalSeconds, $null
    }
}

# ─── Stage: inject ───
function Test-InjectStage {
    Write-Step "Pipeline Stage: Inject (ingest-service)"
    $url = "http://localhost:8001/fetch-real-news"
    $ok, $code, $secs, $body = Invoke-HealthCheck -Url $url -Timeout 30
    Add-Duration "inject" $secs
    if ($ok -and $code -eq 200) {
        $fetched = if ($body -and $body.articles_fetched) { $body.articles_fetched } else { "unknown" }
        Write-Ok "ingest-service returned $code in $($secs.ToString('F2'))s (articles_fetched: $fetched)"
        return $true
    }
    Write-Fail "ingest-service POST /fetch-real-news failed (HTTP $code, ${secs}s)"
    return $false
}

# ─── Stage: kafka ───
function Test-KafkaStage {
    Write-Step "Pipeline Stage: Kafka"

    $pythonCode = @"
from confluent_kafka import Consumer, KafkaException
import json, sys
try:
    c = Consumer({'bootstrap.servers': '$kafkaBootstrap', 'group.id': 'pipeline-test', 'session.timeout.ms': 5000})
    md = c.list_topics(timeout=5)
    c.close()
    wanted = ['raw_articles', 'processed_articles']
    result = {}
    for t in wanted:
        if t in md.topics:
            result[t] = len(md.topics[t].partitions)
        else:
            result[t] = 0
    print(json.dumps(result))
except Exception as e:
    print(json.dumps({'error': str(e)}))
    sys.exit(1)
"@

    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $output = & python -c $pythonCode 2>&1
        $sw.Stop()
        $parsed = $output | Out-String | ConvertFrom-Json
        Add-Duration "kafka" $sw.Elapsed.TotalSeconds

        if ($parsed.error) {
            Write-Fail "Kafka: $($parsed.error)"
            return $false
        }
        $rawMsg = ""
        $procMsg = ""
        $rawCount = if ($parsed.raw_articles) { $parsed.raw_articles } else { 0 }
        $procCount = if ($parsed.processed_articles) { $parsed.processed_articles } else { 0 }

        if ($parsed.raw_articles -gt 0) {
            $rawMsg = "raw_articles (${rawCount} partitions)"
        } else {
            $rawMsg = "raw_articles NOT FOUND"
        }
        if ($parsed.processed_articles -gt 0) {
            $procMsg = "processed_articles (${procCount} partitions)"
        } else {
            $procMsg = "processed_articles NOT FOUND"
        }

        if ($parsed.raw_articles -gt 0 -and $parsed.processed_articles -gt 0) {
            Write-Ok "Kafka topics OK — $rawMsg, $procMsg ($($sw.Elapsed.TotalSeconds.ToString('F2'))s)"
            return $true
        }
        Write-Warn "Kafka topics missing — $rawMsg, $procMsg"
        return $false
    } catch {
        $sw.Stop()
        Add-Duration "kafka" $sw.Elapsed.TotalSeconds
        Write-Warn "confluent_kafka not available or error; falling back to port check"
        $tcpOk = $false
        try {
            $tcp = Get-NetTCPConnection -LocalPort 9092 -ErrorAction SilentlyContinue
            $tcpOk = ($tcp -and $tcp.State -eq "Listen")
        } catch {}
        if ($tcpOk) {
            Write-Ok "Kafka port 9092 is listening ($($sw.Elapsed.TotalSeconds.ToString('F2'))s)"
            return $true
        }
        Write-Fail "Kafka port 9092 not reachable"
        return $false
    }
}

# ─── Stage: ml ───
function Test-MlStage {
    Write-Step "Pipeline Stage: ML (ml-service)"
    $ok, $code, $secs, $body = Invoke-HealthCheck -Url "http://localhost:8002/"
    Add-Duration "ml" $secs
    if ($ok) {
        $status = if ($body -and $body.status) { $body.status } else { "unknown" }
        Write-Ok "ml-service health: $status ($($secs.ToString('F2'))s)"
        return $true
    }
    Write-Fail "ml-service not reachable (${secs}s)"
    return $false
}

# ─── Stage: db ───
function Test-DbStage {
    Write-Step "Pipeline Stage: Database (database-service)"
    $ok, $code, $secs, $body = Invoke-HealthCheck -Url "http://localhost:8003/health"
    Add-Duration "db" $secs
    if ($ok -and $body) {
        $pg = if ($body.database) { $body.database } else { "unknown" }
        $es = if ($body.elasticsearch) { $body.elasticsearch } else { "unknown" }
        $pgOk = $pg -eq "healthy" -or $pg -eq "connected" -or $pg -eq $true
        $esOk = $es -eq "healthy" -or $es -eq "connected" -or $es -eq $true
        if ($pgOk -and $esOk) {
            Write-Ok "PostgreSQL: ${pg}, Elasticsearch: ${es} ($($secs.ToString('F2'))s)"
        } else {
            Write-Warn "PostgreSQL: ${pg}, Elasticsearch: ${es} ($($secs.ToString('F2'))s)"
        }
        return ($pgOk -and $esOk)
    }
    Write-Fail "database-service not reachable (${secs}s)"
    return $false
}

# ─── Stage: embedding ───
function Test-EmbeddingStage {
    Write-Step "Pipeline Stage: Embedding"
    $ok, $code, $secs, $body = Invoke-HealthCheck -Url "http://localhost:8005/"
    Add-Duration "embedding" $secs
    if ($ok) {
        Write-Ok "embedding-service health OK ($($secs.ToString('F2'))s)"
        return $true
    }
    Write-Fail "embedding-service not reachable (${secs}s)"
    return $false
}

# ─── Stage: api ───
function Test-ApiStage {
    Write-Step "Pipeline Stage: API (modular-api)"
    $ok, $code, $secs, $body = Invoke-HealthCheck -Url "http://localhost:8000/"
    Add-Duration "api" $secs
    if ($ok) {
        Write-Ok "modular-api health OK ($($secs.ToString('F2'))s)"

        $artOk, $artCode, $artSecs, $artBody = Invoke-HealthCheck -Url "http://localhost:8000/api/articles?limit=5"
        if ($artOk -and $artBody) {
            $count = if ($artBody.total -or $artBody.count) { $artBody.total ?? $artBody.count } else { ($artBody | Measure-Object).Count }
            Write-Ok "Articles endpoint: $count articles available ($($artSecs.ToString('F2'))s)"
        } else {
            Write-Warn "Articles endpoint not reachable or empty"
        }
        return $true
    }
    Write-Fail "modular-api not reachable (${secs}s)"
    return $false
}

# ─── Main ───
Write-Host "`n==============================================" -ForegroundColor $Script:CCyan
Write-Host "  ProxyDefence — Pipeline Validation Toolkit" -ForegroundColor $Script:CCyan
Write-Host "  Mode: $PipelineType" -ForegroundColor $Script:CCyan
Write-Host "==============================================" -ForegroundColor $Script:CCyan

$overall = [System.Diagnostics.Stopwatch]::StartNew()
$results = @{}

switch ($PipelineType) {
    "inject"    { $results["inject"]    = Test-InjectStage }
    "kafka"     { $results["kafka"]     = Test-KafkaStage }
    "ml"        { $results["ml"]        = Test-MlStage }
    "db"        { $results["db"]        = Test-DbStage }
    "embedding" { $results["embedding"] = Test-EmbeddingStage }
    "api"       { $results["api"]       = Test-ApiStage }
    "full" {
        $results["inject"]    = Test-InjectStage
        $results["kafka"]     = Test-KafkaStage
        $results["ml"]        = Test-MlStage
        $results["db"]        = Test-DbStage
        $results["embedding"] = Test-EmbeddingStage
        $results["api"]       = Test-ApiStage
    }
}

$overall.Stop()
$totalSec = $overall.Elapsed.TotalSeconds

# ─── Summary ───
Write-Step "Pipeline Results"
$pass = 0; $fail = 0
foreach ($kv in $results.GetEnumerator()) {
    $icon = if ($kv.Value) { "PASS" } else { "FAIL" }
    $color = if ($kv.Value) { $Script:CGreen } else { $Script:CRed }
    $dur = if ($script:timings[$kv.Key]) { $script:timings[$kv.Key].ToString('F2') + "s" } else { "-" }
    Write-Host "  [$icon] $($kv.Key.PadRight(12)) ${dur}" -ForegroundColor $color
    if ($kv.Value) { $pass++ } else { $fail++ }
}

Write-Host "`n  Total elapsed: $($totalSec.ToString('F2'))s" -ForegroundColor $Script:CCyan
$overallOk = ($fail -eq 0)
if ($overallOk) {
    Write-Ok "All pipeline stages passed"
} else {
    Write-Fail "${fail} stage(s) failed out of $($results.Count)"
}

if (-not $overallOk) { exit 1 }
