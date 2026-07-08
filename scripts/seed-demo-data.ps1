#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Seeds the database with realistic demo data from tests/sample_data/.
  Idempotent — safe to re-run.
#>

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\dev\common\colors.ps1"
. "$PSScriptRoot\dev\common\paths.ps1"
. "$PSScriptRoot\dev\common\load-env.ps1" -RepoRoot $Script:RepoRoot

$sampleDir = Join-Path $Script:RepoRoot "tests\sample_data"

# ─── Validate sample data ───
$required = @("articles.json", "entities.json", "events.json", "users.json")
foreach ($f in $required) {
    $path = Join-Path $sampleDir $f
    if (-not (Test-Path $path)) {
        Write-Fail "Sample data not found: $path"
        exit 1
    }
}

# ─── Load sample data ───
Write-Step "Loading sample data"
$articles   = Get-Content (Join-Path $sampleDir "articles.json")   | ConvertFrom-Json
$entities   = Get-Content (Join-Path $sampleDir "entities.json")   | ConvertFrom-Json
$events     = Get-Content (Join-Path $sampleDir "events.json")     | ConvertFrom-Json
$users      = Get-Content (Join-Path $sampleDir "users.json")      | ConvertFrom-Json

Write-Info "Loaded $($articles.Count) articles, $($entities.Count) entities, $($events.Count) events, $($users.Count) users"

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
    $result = $null
    try {
        $result = & "psql" @psqlArgs -t -c $Sql 2>&1
        if ($LASTEXITCODE -ne 0) { throw "psql exited with code $LASTEXITCODE" }
    } catch {
        if ($_.Exception.Message -like "*not recognized*" -or $_.Exception.Message -like "*not found*") {
            Write-Warn "psql not found in PATH — attempting Npgsql fallback"
            return Invoke-PsqlNpgsql -Sql $Sql
        }
        throw $_
    }
    return $result
}

function Invoke-PsqlNpgsql {
    param([string]$Sql)
    try {
        Add-Type -Path "C:\Program Files\PostgreSQL\*\Npgsql.dll" -ErrorAction SilentlyContinue
    } catch {}
    $connStr = "Server=$pgHost;Port=$pgPort;Database=$pgDb;User Id=$pgUser;Password=$pgPass;"
    $conn = New-Object Npgsql.NpgsqlConnection($connStr)
    $conn.Open()
    $cmd = $conn.CreateCommand()
    $cmd.CommandText = $Sql
    $reader = $cmd.ExecuteReader()
    $results = @()
    while ($reader.Read()) { $results += $reader[0] }
    $reader.Close()
    $conn.Close()
    if ($results.Count -eq 0) { return $null }
    return $results -join "`n"
}

# ─── Verify connectivity ───
Write-Step "Verifying database connectivity"
try {
    $version = Invoke-Psql -Sql "SELECT version();"
    Write-Ok "Connected to PostgreSQL: $($version.Trim())"
} catch {
    Write-Fail "Could not connect to PostgreSQL: $_"
    exit 1
}

# ─── Helper: escape for SQL string literals ───
function Escape-Sql { param([string]$S) return "'" + $S.Replace("'", "''") + "'" }
function Escape-Null { param([string]$S) if ([string]::IsNullOrEmpty($S)) { return "NULL" } return Escape-Sql $S }

# ─── Seed users ───
Write-Step "Seeding users"
$userCount = 0
foreach ($u in $users) {
    $sql = @"
INSERT INTO users (email, username, password_hash, role)
SELECT $(Escape-Sql $u.email), $(Escape-Sql $u.username), $(Escape-Sql "seed-$($u.password)"), $(Escape-Sql $u.role)
WHERE NOT EXISTS (SELECT 1 FROM users WHERE email = $(Escape-Sql $u.email));
"@
    try {
        $r = Invoke-Psql -Sql $sql
        if ($LASTEXITCODE -eq 0) { $userCount++ }
    } catch { Write-Warn "User $($u.email) already exists or skipped" }
}
Write-Ok "Seeded $userCount users (idempotent)"

# ─── Seed articles ───
Write-Step "Seeding articles"
$articleIdMap = @{}
$articleCount = 0
foreach ($a in $articles) {
    $dedupeKey = "seed-article-$($a.id)"
    $title   = Escape-Null $a.title
    $content = Escape-Null $a.content
    $source  = Escape-Null $a.source
    $url     = Escape-Null $a.url
    $pubAt   = Escape-Null $a.published_at
    $sentiment = Escape-Null $a.sentiment
    $topic   = Escape-Null $a.topic
    $riskLvl = Escape-Null $a.risk_level
    $conf    = if ($a.confidence) { $a.confidence } else { 0.0 }
    $threat  = if ($a.threat_score) { $a.threat_score } else { 0.0 }

    $sql = @"
INSERT INTO processed_articles (article_id, title, content, source, url, published_at, ml_processed, confidence, sentiment, topic, threat_score, risk_level, dedupe_key)
SELECT $($a.id), $title, $content, $source, $url, $pubAt::timestamp, true, $conf, $sentiment, $topic, $threat, $riskLvl, $(Escape-Sql $dedupeKey)
WHERE NOT EXISTS (SELECT 1 FROM processed_articles WHERE dedupe_key = $(Escape-Sql $dedupeKey));
"@
    try {
        Invoke-Psql -Sql $sql
        $articleCount++
        $articleIdMap[$a.id] = $a.id
    } catch { Write-Warn "Article $($a.id) already exists or skipped" }
}
Write-Ok "Seeded $articleCount articles"

# ─── Seed extracted entities ───
Write-Step "Seeding extracted entities"
$entityCount = 0
foreach ($a in $articles) {
    if (-not $a.entities) { continue }
    foreach ($e in $a.entities) {
        $articleId = $a.id
        $text  = Escape-Sql $e.text
        $type  = Escape-Null $e.type
        $conf  = if ($e.confidence) { $e.confidence } else { 0.0 }
        $sql = @"
INSERT INTO extracted_entities (article_id, entity_text, entity_type, confidence)
SELECT $articleId, $text, $type, $conf
WHERE NOT EXISTS (
    SELECT 1 FROM extracted_entities WHERE article_id = $articleId AND entity_text = $text
);
"@
        try { Invoke-Psql -Sql $sql; $entityCount++ } catch {}
    }
}

# ─── Also seed standalone entities ───
foreach ($e in $entities) {
    $text = Escape-Sql $e.entity_text
    $type = Escape-Null $e.entity_type
    $conf = if ($e.confidence) { $e.confidence } else { 0.0 }
    $sql = @"
INSERT INTO extracted_entities (article_id, entity_text, entity_type, confidence)
SELECT 1, $text, $type, $conf
WHERE NOT EXISTS (SELECT 1 FROM extracted_entities WHERE entity_text = $text AND article_id = 1);
"@
    try { Invoke-Psql -Sql $sql; $entityCount++ } catch {}
}
Write-Ok "Seeded $entityCount extracted entities"

# ─── Seed relationships ───
Write-Step "Seeding entity relationships"
$relCount = 0
$relationshipData = @(
    @{ Source = "Iran";  Target = "Israel";     ArticleId = 1; Type = "conflict";  Confidence = 0.92 }
    @{ Source = "North Korea"; Target = "Japan"; ArticleId = 2; Type = "military_aggression"; Confidence = 0.88 }
    @{ Source = "China"; Target = "Russia";     ArticleId = 3; Type = "alliance";  Confidence = 0.85 }
    @{ Source = "Houthi"; Target = "Saudi Arabia"; ArticleId = 5; Type = "attack"; Confidence = 0.81 }
)
foreach ($r in $relationshipData) {
    $sql = @"
INSERT INTO relationships (article_id, source_entity, target_entity, relationship_type, confidence)
SELECT $($r.ArticleId), $(Escape-Sql $r.Source), $(Escape-Sql $r.Target), $(Escape-Sql $r.Type), $($r.Confidence)
WHERE NOT EXISTS (
    SELECT 1 FROM relationships
    WHERE article_id = $($r.ArticleId) AND source_entity = $(Escape-Sql $r.Source) AND target_entity = $(Escape-Sql $r.Target)
);
"@
    try { Invoke-Psql -Sql $sql; $relCount++ } catch {}
}
Write-Ok "Seeded $relCount relationships"

# ─── Seed events ───
Write-Step "Seeding events"
$eventCount = 0
foreach ($ev in $events) {
    $title = Escape-Sql $ev.title
    $desc  = Escape-Null $ev.description
    $eType = Escape-Null $ev.event_type
    $severity = Escape-Null $ev.severity
    $status   = Escape-Null $ev.status
    $start    = Escape-Null $ev.start_date
    $conf     = if ($ev.confidence) { $ev.confidence } else { 0.0 }

    $sql = @"
INSERT INTO events (title, summary, topic, risk_score, risk_level, confidence, first_seen, last_seen, article_count, cluster_key)
SELECT $title, $desc, $eType,
    CASE $severity
        WHEN 'critical' THEN 9.0 WHEN 'high' THEN 7.0 WHEN 'medium' THEN 5.0 ELSE 3.0
    END,
    $severity, $conf, $start::timestamp, NOW(), 1, $(Escape-Sql "seed-event-$($ev.id)")
WHERE NOT EXISTS (SELECT 1 FROM events WHERE cluster_key = $(Escape-Sql "seed-event-$($ev.id)"));
"@
    try { Invoke-Psql -Sql $sql; $eventCount++ } catch {}
}
Write-Ok "Seeded $eventCount events"

# ─── Link events to articles ───
Write-Step "Linking events to articles"
$linkCount = 0
foreach ($ev in $events) {
    if (-not $ev.related_articles) { continue }
    foreach ($aid in $ev.related_articles) {
        $sql = @"
INSERT INTO event_articles (event_id, article_id, similarity_score)
SELECT e.id, $aid, 1.0
FROM events e
WHERE e.cluster_key = $(Escape-Sql "seed-event-$($ev.id)")
  AND NOT EXISTS (SELECT 1 FROM event_articles WHERE event_id = e.id AND article_id = $aid);
"@
        try { Invoke-Psql -Sql $sql; $linkCount++ } catch {}
    }
}
Write-Ok "Linked $linkCount event-article pairs"

# ─── Seed watchlists ───
Write-Step "Seeding watchlists"
$watchlistSql = @"
INSERT INTO watchlists (name, description, owner_id)
SELECT 'High Priority Entities', 'Monitored threat actors and state-level entities', id
FROM users WHERE username = 'admin'
  AND NOT EXISTS (SELECT 1 FROM watchlists WHERE name = 'High Priority Entities');
"@
try { Invoke-Psql -Sql $watchlistSql } catch {}

$watchlistEntities = @("Iran", "North Korea", "Houthi", "Hezbollah", "ISIS", "Russia", "China")
$wlEntCount = 0
foreach ($ent in $watchlistEntities) {
    $sql = @"
INSERT INTO watchlist_entities (watchlist_id, entity_text)
SELECT id, $(Escape-Sql $ent) FROM watchlists WHERE name = 'High Priority Entities'
  AND NOT EXISTS (
      SELECT 1 FROM watchlist_entities we
      JOIN watchlists w ON w.id = we.watchlist_id
      WHERE w.name = 'High Priority Entities' AND we.entity_text = $(Escape-Sql $ent)
  );
"@
    try { Invoke-Psql -Sql $sql; $wlEntCount++ } catch {}
}
Write-Ok "Seeded $wlEntCount watchlist entities"

# ─── Final report ───
Write-Step "Seed Summary"
Write-Ok "Articles:        $articleCount"
Write-Ok "Extracted entities: $entityCount"
Write-Ok "Relationships:   $relCount"
Write-Ok "Events:          $eventCount"
Write-Ok "Event-article links: $linkCount"
Write-Ok "Users:           $userCount"
Write-Ok "Watchlist entities: $wlEntCount"
Write-Info "All inserts are idempotent — safe to re-run."
