#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Single-command launcher for the complete ProxyDefence local dev environment.
.DESCRIPTION
  Inspects the environment, cleans up old processes, starts Docker infra,
  launches all 6 API services (separate windows), 3 Kafka consumers, and
  the Vite frontend.  Stops on the FIRST failure and prints diagnostic info.
.PARAMETER SkipInfra
  Skip docker compose up (PG / Kafka / ES already running).
.PARAMETER SkipFrontend
  Skip the Vite dev server.
.PARAMETER SkipCleanup
  Skip killing old ProxyDefence processes and port checks.
.PARAMETER Force
  Answer Yes to all prompts (non-interactive).
#>
param(
    [switch]$SkipInfra,
    [switch]$SkipFrontend,
    [switch]$SkipCleanup,
    [switch]$Force
)

$ErrorActionPreference = "Continue"
$startTime = Get-Date

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
$Script:repoRoot = Split-Path -Path (Split-Path -Path $PSScriptRoot -Parent) -Parent
$Script:logDir   = Join-Path $Script:repoRoot "logs"
$Script:pidFile  = Join-Path $Script:logDir "local-pids.json"
$Script:pids     = @{}

if (-not (Test-Path $Script:logDir)) {
    New-Item -ItemType Directory -Path $Script:logDir -Force | Out-Null
}

# ---------------------------------------------------------------------------
# Colour helpers  (long names to avoid shadowing any PS automatic variables)
# ---------------------------------------------------------------------------
$script:cyanColor    = "Cyan"
$script:greenColor   = "Green"
$script:yellowColor  = "Yellow"
$script:redColor     = "Red"

function Write-Step  { param([string]$M) Write-Host "`n=== $M ===" -ForegroundColor $script:cyanColor }
function Write-Ok    { param([string]$M) Write-Host "  OK  $M" -ForegroundColor $script:greenColor }
function Write-Warn  { param([string]$M) Write-Host "  WARN $M" -ForegroundColor $script:yellowColor }
function Write-Fail  { param([string]$M) Write-Host "  FAIL $M" -ForegroundColor $script:redColor }

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

function Test-CommandAvailable {
    param([string]$Command)
    $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    $null = Get-Command $Command -ErrorAction SilentlyContinue
    $ok = $?
    $ErrorActionPreference = $old
    return $ok
}

function Test-PortFree {
    param([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    return (-not $conn)
}

function Get-ProcessOnPort {
    param([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    if ($conn) {
        $pidsOnPort = @($conn | ForEach-Object { $_.OwningProcess } | Select-Object -Unique)
        foreach ($procId in $pidsOnPort) {
            $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
            if ($proc) { return $proc }
        }
    }
    return $null
}

function Wait-ForPort {
    param([int]$Port, [string]$Label = "port $Port", [int]$TimeoutSec = 30)
    Write-Host "  Waiting for $Label ($Port)..." -NoNewline
    $elapsed = 0
    while ($elapsed -lt $TimeoutSec) {
        if (-not (Test-PortFree $Port)) {
            Write-Host " OK" -ForegroundColor $script:greenColor
            return $true
        }
        Start-Sleep -Seconds 1; $elapsed++
    }
    Write-Host " TIMEOUT after ${TimeoutSec}s" -ForegroundColor $script:redColor
    return $false
}

function Wait-ForUrl {

    param(
        [string]$Url,
        [string]$Label,
        [int]$TimeoutSec = 60
    )

    Write-Host "  Waiting for $Label ($Url)..." -NoNewline

    $sw = [Diagnostics.Stopwatch]::StartNew()

    while($sw.Elapsed.TotalSeconds -lt $TimeoutSec){

        try{

            Invoke-WebRequest `
                -Uri $Url `
                -UseBasicParsing `
                -TimeoutSec 5 `
                -ErrorAction Stop | Out-Null

            Write-Host " OK" -ForegroundColor Green
            return $true
        }

        catch{

            if($_.Exception.Response){

                $resp = $_.Exception.Response

                if($resp -is [System.Net.HttpWebResponse]){

                    switch([int]$resp.StatusCode){

                        200 {
                            Write-Host " OK (200)" -ForegroundColor Green
                            return $true
                        }

                        401 {
                            Write-Host " OK (401 Auth Required)" -ForegroundColor Green
                            return $true
                        }

                        403 {
                            Write-Host " OK (403 Forbidden)" -ForegroundColor Green
                            return $true
                        }
                    }
                }
            }

            Start-Sleep 1
        }

    }

    Write-Host " TIMEOUT" -ForegroundColor Red
    return $false
}

function Wait-ForProcess {
    param([string]$Name, [int]$ProcessId, [int]$TimeoutSec = 10)
    Write-Host "  Waiting for process $Name (PID $ProcessId)..." -NoNewline
    $elapsed = 0
    while ($elapsed -lt $TimeoutSec) {
        $p = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
        if ($p -and (-not $p.HasExited)) {
            Write-Host " alive" -ForegroundColor $script:greenColor
            return $true
        }
        Start-Sleep -Seconds 1; $elapsed++
    }
    Write-Host " not found or exited" -ForegroundColor $script:redColor
    return $false
}

function Track-Process {
    param([string]$Name, [int]$ProcessId)
    $Script:pids[$Name] = @{Name=$Name; ProcessId=$ProcessId; StartedAt=(Get-Date -Format "HH:mm:ss")}
    $Script:pids | ConvertTo-Json | Set-Content $Script:pidFile
}

function Stop-ProxyDefenceProcesses {
    Write-Step "Cleaning Up Old ProxyDefence Processes"

    # uvicorn
    $uvicorn = Get-Process -Name "uvicorn" -ErrorAction SilentlyContinue
    foreach ($p in $uvicorn) {
        try {
            $p.Kill()
            Write-Ok "Killed uvicorn (PID $($p.Id))"
        } catch { Write-Warn "Could not kill uvicorn (PID $($p.Id)): $_" }
    }

    # python running consumer.py
    $python = Get-Process -Name "python" -ErrorAction SilentlyContinue
    foreach ($p in $python) {
        $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($p.Id)" -ErrorAction SilentlyContinue).CommandLine
        if ($cmdLine -match "consumer\.py") {
            try { $p.Kill(); Write-Ok "Killed consumer.py (PID $($p.Id))" } catch {}
        }
    }

    # node running vite
    $node = Get-Process -Name "node" -ErrorAction SilentlyContinue
    foreach ($p in $node) {
        $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($p.Id)" -ErrorAction SilentlyContinue).CommandLine
        if ($cmdLine -match "vite") {
            try { $p.Kill(); Write-Ok "Killed vite (PID $($p.Id))" } catch {}
        }
    }

    # npm (frontend dev server)
    $npm = Get-Process -Name "npm" -ErrorAction SilentlyContinue
    foreach ($p in $npm) {
        try { $p.Kill(); Write-Ok "Killed npm (PID $($p.Id))" } catch {}
    }

    # Child powershell windows running backend scripts
    $pwsh = Get-Process -Name "powershell" -ErrorAction SilentlyContinue
    foreach ($p in $pwsh) {
        $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($p.Id)" -ErrorAction SilentlyContinue).CommandLine
        if ($cmdLine -match "start-ingest|start-ml|start-database|start-embedding|start-energy|start-ml-platform|start-modular|consumer\.py|load-env.*PYTHONPATH") {
            try { $p.Kill(); Write-Ok "Killed launcher window (PID $($p.Id))" } catch {}
        }
    }

    # Remove stale PID file
    if (Test-Path $Script:pidFile) {
        Remove-Item $Script:pidFile -Force -ErrorAction SilentlyContinue
        Write-Ok "Removed stale PID file"
    }
}

function Check-PortOrPrompt {
    param([int]$Port, [string]$ServiceName, [switch]$ForceConfirm)
    if (Test-PortFree $Port) { return $true }
    $proc = Get-ProcessOnPort $Port
    if (-not $proc) {
        Write-Warn "Port $Port is in use (unknown process), but continuing"
        return $true
    }
    $procName = $proc.Name
    $procId = $proc.Id
    # Check if it's a ProxyDefence process we should auto-kill
    $proxyDefenceNames = @("uvicorn", "python", "node", "npm", "powershell")
    if ($procName -in $proxyDefenceNames) {
        # Could be ours - kill and retry
        try {
            $proc.Kill()
            Write-Ok "Freed port $Port (killed $procName PID $procId)"
            Start-Sleep -Seconds 2
            if (Test-PortFree $Port) { return $true }
        } catch {
            Write-Warn "Could not kill process on port $Port"
        }
    }
    # Not a ProxyDefence process (or kill failed) -- prompt
    Write-Warn "Port $Port is occupied by: $procName (PID $procId)"
    if ($ForceConfirm) {
        Write-Warn "  --Force set, continuing anyway (service may fail)"
        return $true
    }
    Write-Host "  Continue anyway? (Y/N): " -NoNewline -ForegroundColor $script:yellowColor
    $response = Read-Host
    if ($response -eq "Y" -or $response -eq "y") { return $true }
    Write-Fail "User aborted due to port conflict on port $Port ($ServiceName)"
    exit 1
}

function Inspect-Log {
    param([string]$LogPath, [string]$ServiceName)
    if (-not (Test-Path $LogPath)) { return }

    $lines = Get-Content $LogPath -Tail 100
    if (-not $lines) { return }

    Write-Host "`n  --- Last 100 lines of $ServiceName log ---" -ForegroundColor $script:yellowColor
    foreach ($line in $lines) { Write-Host "  | $line" }

    # Classify failure
    $fullText = $lines -join "`n"
    $classifications = @()
    if ($fullText -match "ModuleNotFoundError|ImportError") {
        $classifications += "Missing Python dependency"
    }
    if ($fullText -match "OperationalError|Connection refused|connection refused|could not connect to server") {
        $classifications += "Database connection failed"
    }
    if ($fullText -match "NoBrokersAvailable|Failed to connect to broker|KafkaTimeoutError") {
        $classifications += "Kafka unavailable"
    }
    if ($fullText -match "Address already in use|AddressInUseError") {
        $classifications += "Port already in use"
    }
    if ($fullText -match "Permission denied|Access denied") {
        $classifications += "Permission denied"
    }
    if ($fullText -match "No such file or directory|FileNotFoundError") {
        $classifications += "File not found"
    }
    if ($fullText -match "SyntaxError") {
        $classifications += "Python syntax error"
    }
    if ($fullText -match "pkg_resources|VersionConflict|DistributionNotFound") {
        $classifications += "Dependency conflict"
    }
    if ($fullText -match "KeyError|ValueError|TypeError") {
        $classifications += "Python runtime error"
    }
    if ($fullText -match "\.env|environment variable") {
        $classifications += "Missing environment variable or .env"
    }
    if ($fullText -match "Timeout") {
        $classifications += "Operation timed out"
    }

    if ($classifications.Count -gt 0) {
        Write-Host "  --- Failure classification ---" -ForegroundColor $script:yellowColor
        foreach ($c in $classifications) { Write-Host "  * $c" -ForegroundColor $script:redColor }
    } else {
        Write-Host "  (unable to classify failure -- see log above)" -ForegroundColor $script:yellowColor
    }
}

function Stop-On-Failure {
    param([string]$Stage, [string]$Reason, [string]$Suggestion = "", [string]$LogPath = "", [string]$ServiceName = "")
    Write-Host "" -NoNewline
    Write-Fail "Stage: $Stage"
    Write-Fail "Reason: $Reason"
    if ($Suggestion) {
        Write-Host "  Suggested fix: $Suggestion" -ForegroundColor $script:yellowColor
    }
    if ($LogPath -and (Test-Path $LogPath)) {
        $logContent = Get-Content $LogPath -Tail 50
        if ($logContent) {
            Write-Host "`n  --- Last 100 lines from log ---" -ForegroundColor $script:yellowColor
            foreach ($line in $logContent) { Write-Host "  | $line" }
        }
    }
    Write-Host "`n  Startup failed after $([math]::Round(((Get-Date) - $startTime).TotalSeconds, 1))s" -ForegroundColor $script:redColor
    exit 1
}

# ---------------------------------------------------------------------------
# Service definitions
# ---------------------------------------------------------------------------

$Script:svcList = @(
    @{Name="modular-api";       Dir="services/modular-api";       Port=8000; Script="start-modular-api.ps1";  App="backend.api.app:app"}
    @{Name="ingest-service";    Dir="services/ingest-service";    Port=8001; Script="start-ingest.ps1";       App="app:app"}
    @{Name="database-service";  Dir="services/database-service";  Port=8003; Script="start-database.ps1";     App="app:app"}
    @{Name="embedding-service"; Dir="services/embedding-service"; Port=8005; Script="start-embedding.ps1";    App="app:app"}
    @{Name="energy-service";    Dir="services/energy-service";    Port=8006; Script="start-energy.ps1";       App="app:app"}
    @{Name="ml-platform";       Dir="services/ml-platform";       Port=8007; Script="start-ml-platform.ps1";  App="app:app"}
)

$Script:consumers = @(
    @{Name="ml-platform-consumer"; Dir="services/ml-platform";       File="consumer/article_enrichment.py"; LogFile="ml-platform-consumer.log"}
    @{Name="db-consumer";          Dir="services/database-service";  File="consumer.py";     LogFile="db-consumer.log"}
    @{Name="embedding-consumer";   Dir="services/embedding-service"; File="consumer.py";     LogFile="embedding-consumer.log"}
)

$Script:allPorts = @(5434, 8000, 8001, 8003, 8005, 8006, 8007, 8080, 8081, 5173, 4173, 9092, 9200)
$Script:infraPorts = @{PostgreSQL=5434; Kafka=9092; Elasticsearch=9200}
$Script:envFile = Join-Path $Script:repoRoot ".env"

# ===========================================================================
# PHASE 0: Pre-flight Check
# ===========================================================================
Write-Step "Pre-flight Environment Check"

# -- PowerShell version --
if ($PSVersionTable.PSVersion.Major -lt 5) {
    Stop-On-Failure -Stage "Pre-flight" -Reason "PowerShell 5+ is required (current: $($PSVersionTable.PSVersion))" `
        -Suggestion "Install Windows Management Framework 5.1 or PowerShell 7"
}
Write-Ok "PowerShell $($PSVersionTable.PSVersion)"

# -- Python --
if (-not (Test-CommandAvailable "python")) {
    Stop-On-Failure -Stage "Pre-flight" -Reason "Python not found on PATH" `
        -Suggestion "Install Python 3.10+ and ensure it is on your PATH"
}
$pyVer = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Stop-On-Failure -Stage "Pre-flight" -Reason "Python is not working: $pyVer"
}
$verMatch = [regex]::Match($pyVer, '(\d+)\.(\d+)')
$pyMajor = [int]$verMatch.Groups[1].Value
$pyMinor = [int]$verMatch.Groups[2].Value
if ($pyMajor -lt 3 -or ($pyMajor -eq 3 -and $pyMinor -lt 10)) {
    Stop-On-Failure -Stage "Pre-flight" -Reason "Python 3.10+ required (found: $pyVer)" `
        -Suggestion "Install Python 3.10+ from https://www.python.org/downloads/"
}
Write-Ok "Python $pyVer"

# -- Node --
if (-not (Test-CommandAvailable "node")) {
    Stop-On-Failure -Stage "Pre-flight" -Reason "Node.js not found on PATH" `
        -Suggestion "Install Node.js 18+ from https://nodejs.org/"
}
$nodeVer = node --version
Write-Ok "Node $nodeVer"

# -- npm --
if (-not (Test-CommandAvailable "npm")) {
    Stop-On-Failure -Stage "Pre-flight" -Reason "npm not found on PATH" `
        -Suggestion "npm is included with Node.js -- check your installation"
}
$npmVer = npm --version
Write-Ok "npm $npmVer"

# -- Docker CLI --
$dockerCli = $false
$null = docker --version 2>$null
if ($LASTEXITCODE -eq 0) { $dockerCli = $true }
if (-not $dockerCli) {
    if (-not $SkipInfra) {
        Stop-On-Failure -Stage "Pre-flight" -Reason "Docker CLI not found (required for infrastructure)" `
            -Suggestion "Install Docker Desktop from https://www.docker.com/products/docker-desktop/"
    } else {
        Write-Warn "Docker CLI not found (infrastructure will not be managed)"
    }
} else {
    $dockerVer = docker --version 2>$null
    Write-Ok "$dockerVer"

    # -- Docker Compose (v2 plugin or v1 binary) --
    $Script:dockerComposeCmd = "docker compose"
    $null = docker compose version 2>$null
    if ($LASTEXITCODE -ne 0) {
        $null = docker-compose --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            $Script:dockerComposeCmd = "docker-compose"
            $dcVer = docker-compose --version 2>$null
            Write-Ok "$dcVer (legacy v1)"
        } elseif (-not $SkipInfra) {
            Stop-On-Failure -Stage "Pre-flight" -Reason "Docker Compose not found (tried v2 plugin and v1 binary)" `
                -Suggestion "Docker Compose is included with Docker Desktop 4.0+"
        }
    } else {
        $dcVer = docker compose version 2>$null
        Write-Ok "$dcVer"
    }

    # -- Docker daemon --
    $null = docker ps 2>$null
    if ($LASTEXITCODE -ne 0 -and (-not $SkipInfra)) {
        Stop-On-Failure -Stage "Pre-flight" -Reason "Docker daemon is not running" `
            -Suggestion "Start Docker Desktop from the Start Menu or system tray and wait for it to show 'Engine running'"
    }
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "Docker daemon is running"
    }
}

# -- Repository root --
if (-not (Test-Path $Script:repoRoot)) {
    Stop-On-Failure -Stage "Pre-flight" -Reason "Repository root not found at $Script:repoRoot"
}
# Verify key directories exist
$requiredDirs = @(
    "services/modular-api",
    "services/ingest-service",
    "services/database-service",
    "services/embedding-service",
    "services/energy-service",
    "services/ml-platform",
    "services/frontend",
    "scripts/dev"
)
foreach ($dir in $requiredDirs) {
    $fullPath = Join-Path $Script:repoRoot $dir
    if (-not (Test-Path $fullPath)) {
        Stop-On-Failure -Stage "Pre-flight" -Reason "Required directory not found: $dir" `
            -Suggestion "Are you running from the correct repository root?"
    }
}
Write-Ok "Repository root: $Script:repoRoot"

# -- .env file --
if (-not (Test-Path $Script:envFile)) {
    $envExample = Join-Path $Script:repoRoot ".env.example"
    if (Test-Path $envExample) {
        Write-Warn ".env not found, but .env.example exists"
        if ($Force) {
            Copy-Item $envExample $Script:envFile
            Write-Ok "Created .env from .env.example"
        } else {
            Write-Host "  Create .env from .env.example? (Y/N): " -NoNewline -ForegroundColor $script:yellowColor
            $resp = Read-Host
            if ($resp -eq "Y" -or $resp -eq "y") {
                Copy-Item $envExample $Script:envFile
                Write-Ok "Created .env from .env.example"
                Write-Warn "Edit .env with your credentials before continuing"
                Write-Host "  Press Enter to continue..." -ForegroundColor $script:yellowColor
                Read-Host
            } else {
                Stop-On-Failure -Stage "Pre-flight" -Reason ".env file is required" `
                    -Suggestion "Copy .env.example to .env and fill in your credentials"
            }
        }
    } else {
        Stop-On-Failure -Stage "Pre-flight" -Reason ".env file not found at $Script:envFile" `
            -Suggestion "Create a .env file based on the project template"
    }
} else {
    Write-Ok ".env found"
}

# -- Virtual environments --
$allVenvsOk = $true
foreach ($svc in $Script:svcList) {
    $venvPath = Join-Path (Join-Path $Script:repoRoot $svc.Dir) ".venv"
    $pythonExe = Join-Path $venvPath "Scripts/python.exe"
    if (-not (Test-Path $pythonExe)) {
        Write-Warn "$($svc.Name): virtual environment not found at $venvPath"
        $allVenvsOk = $false
    }
}
if (-not $allVenvsOk) {
    if ($Force) {
        Write-Warn "Missing virtual environments -- run scripts/dev/setup/setup.ps1 first (continuing with --Force)"
    } else {
        Stop-On-Failure -Stage "Pre-flight" -Reason "Some virtual environments are missing" `
            -Suggestion "Run 'scripts/dev/setup/setup.ps1' from PowerShell to create all venvs"
    }
} else {
    Write-Ok "All virtual environments found"
}

# -- Logs directory --
if (-not (Test-Path $Script:logDir)) {
    New-Item -ItemType Directory -Path $Script:logDir -Force | Out-Null
    Write-Ok "Created logs directory"
} else {
    Write-Ok "Logs directory exists"
}

# ===========================================================================
# PHASE 1: Process Cleanup
# ===========================================================================
if (-not $SkipCleanup) {
    Stop-ProxyDefenceProcesses

    # Check all ports
    Write-Step "Checking Port Availability"
    foreach ($port in $Script:allPorts) {
        if (-not (Check-PortOrPrompt -Port $port -ServiceName "infra/service" -ForceConfirm:$Force)) {
            Stop-On-Failure -Stage "Port Check" -Reason "Port $port is unavailable"
        }
    }
    Write-Ok "All ports are free"
} else {
    Write-Step "Skipping Cleanup (--SkipCleanup)"
}

# ===========================================================================
# PHASE 2: Infrastructure (Docker)
# ===========================================================================
if (-not $SkipInfra) {
    Write-Step "Starting Infrastructure (Docker)"

    Set-Location $Script:repoRoot

    if ($Script:dockerComposeCmd -eq "docker-compose") {
        docker-compose up -d 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor $script:greenColor }
    } else {
        docker compose up -d 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor $script:greenColor }
    }
    if ($LASTEXITCODE -ne 0) {
        Stop-On-Failure -Stage "Infrastructure" -Reason "docker compose up failed with exit code $LASTEXITCODE" `
            -Suggestion "Check Docker Desktop is running and try again"
    }
    Write-Ok "docker compose up -d"

    # Wait for PostgreSQL
    if (-not (Wait-ForPort -Port $Script:infraPorts.PostgreSQL -Label "PostgreSQL" -TimeoutSec 90)) {
        Stop-On-Failure -Stage "Infrastructure" -Reason "PostgreSQL did not start within 90 seconds" `
            -Suggestion "Check 'docker logs postgres-db' for errors"
    }

    # Wait for Kafka (needs ZK to start first)
    if (-not (Wait-ForPort -Port $Script:infraPorts.Kafka -Label "Kafka" -TimeoutSec 90)) {
        Stop-On-Failure -Stage "Infrastructure" -Reason "Kafka did not start within 90 seconds" `
            -Suggestion "Check 'docker logs kafka' for errors"
    }

    # Wait for Elasticsearch (accepts HTTP 200 or 401)
    if (-not (Wait-ForPort -Port $Script:infraPorts.Elasticsearch -Label "Elasticsearch" -TimeoutSec 120)) {
        Stop-On-Failure -Stage "Infrastructure" -Reason "Elasticsearch did not start within 120 seconds" `
            -Suggestion "Check 'docker logs elasticsearch' for errors"
    }
    Write-Host "  Verifying Elasticsearch HTTP..." -NoNewline
    if (-not (Wait-ForUrl -Url "http://localhost:9200/" -Label "Elasticsearch HTTP" -TimeoutSec 30)) {
        Stop-On-Failure -Stage "Infrastructure" -Reason "Elasticsearch HTTP endpoint not reachable" `
            -Suggestion "Check 'docker logs elasticsearch' for errors"
    }

    Write-Step "Infrastructure Status"
    Write-Ok "PostgreSQL is ready (port 5434)"
    Write-Ok "Kafka is ready (port 9092)"
    Write-Ok "Elasticsearch is ready (port 9200)"
} else {
    Write-Step "Skipping Infrastructure (--SkipInfra)"
    Write-Host "  Assuming PostgreSQL, Kafka, and Elasticsearch are already running" -ForegroundColor $script:yellowColor
}

# ===========================================================================
# PHASE 3: Environment Setup
# ===========================================================================
Write-Step "Setting Up Environment"

$loadEnvScript = "$Script:repoRoot\scripts\dev\common\load-env.ps1"
if (-not (Test-Path $loadEnvScript)) {
    Stop-On-Failure -Stage "Environment Setup" -Reason "load-env.ps1 not found at $loadEnvScript"
}
. $loadEnvScript -RepoRoot $Script:repoRoot
$env:PYTHONPATH = $Script:repoRoot
$env:ENVIRONMENT = "development"
$env:ENERGY_LOAD_SEED = "1"

Write-Ok "Environment variables loaded"
Write-Ok "PYTHONPATH = $Script:repoRoot"

# ===========================================================================
# PHASE 4: API Services
# ===========================================================================
Write-Step "Starting API Services"

function Start-ServiceWindow {
    param([string]$Name, [string]$Script, [int]$Port, [string]$App)

    $svcEntry = $Script:svcList | Where-Object { $_.Name -eq $Name } | Select-Object -First 1
    $svcDir = Join-Path $Script:repoRoot $svcEntry.Dir
    $venvPython = Join-Path $svcDir ".venv/Scripts/python.exe"
    $logFile = Join-Path $Script:logDir "$Name.log"
    $backendScript = Join-Path $Script:repoRoot "scripts/dev/backend/$Script"

    if (-not (Test-Path $venvPython)) {
        Stop-On-Failure -Stage "Start $Name" -Reason "Virtual environment not found at $venvPython" `
            -Suggestion "Run scripts/dev/setup/setup.ps1 to create all virtual environments"
    }
    if (-not (Test-Path $backendScript)) {
        Stop-On-Failure -Stage "Start $Name" -Reason "Backend script not found at $backendScript"
    }

    # Diagnostics before launch
    Write-Host "  [diagnostics] Service dir: $svcDir" -ForegroundColor $script:cyanColor
    Write-Host "  [diagnostics] Python: $venvPython" -ForegroundColor $script:cyanColor
    Write-Host "  [diagnostics] Script: $backendScript" -ForegroundColor $script:cyanColor
    Write-Host "  [diagnostics] PYTHONPATH: $($Script:repoRoot)" -ForegroundColor $script:cyanColor

    # Set correct working directory and verify
    Set-Location $svcDir
    Write-Host "  [diagnostics] Working directory: $(Get-Location)" -ForegroundColor $script:cyanColor

    # Build command for child PowerShell window
    # NOTE: no *>&1 | Tee-Object here — PS 5.1 stream redirection breaks
    #       when piping output from a called .ps1 script.  The script's
    #       output goes directly to the child PS window (visible), and
    #       the try/catch below captures any terminating errors to the
    #       log file for automated debugging.
    $repoRootPath = $Script:repoRoot
    $cmd = @"
`$ErrorActionPreference = 'Stop'
`$repoRoot = '$repoRootPath'
. '$repoRootPath\scripts\dev\common\load-env.ps1' -RepoRoot `$repoRoot
`$env:PYTHONPATH = '$repoRootPath'
`$env:ENVIRONMENT = 'development'
Set-Location '$svcDir'
try {
    & '$backendScript'
} catch {
    `$_ | Out-File -FilePath '$logFile' -Append
    throw
}
"@

    Write-Host "  Launching $Name (port $Port)..." -ForegroundColor $script:cyanColor
    $proc = Start-Process powershell -ArgumentList "-NoExit", "-Command", $cmd -WindowStyle Normal -PassThru
    if (-not $proc -or $proc.HasExited) {
        Stop-On-Failure -Stage "Start $Name" -Reason "Failed to start PowerShell process" `
            -Suggestion "Check that PowerShell is installed correctly" -LogPath $logFile -ServiceName $Name
    }

    Track-Process -Name $Name -ProcessId $proc.Id
    Write-Ok "$Name launched (PID $($proc.Id))"

    # Wait for process to stay alive
    if (-not (Wait-ForProcess -Name $Name -ProcessId $proc.Id -TimeoutSec 5)) {
        $exitCode = $proc.ExitCode
        Stop-On-Failure -Stage "Start $Name" -Reason "Process exited immediately (exit code: $exitCode)" `
            -LogPath $logFile -ServiceName $Name
    }

    # Wait for port
    if (-not (Wait-ForPort -Port $Port -Label $Name -TimeoutSec 45)) {
        Stop-On-Failure -Stage "Start $Name" -Reason "Port $Port did not open within 45 seconds" `
            -LogPath $logFile -ServiceName $Name
    }

    # Verify python.exe is running (not just the PS window)
    try {
        $pyInfo = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction Stop
        $ourPy = $pyInfo | Where-Object { $_.CommandLine -match ":$Port " -or $_.CommandLine -match "--port $Port" } | Select-Object -First 1
        if ($ourPy) {
            Write-Ok "$Name python.exe verified (PID $($ourPy.ProcessId))"
        }
    } catch {
        # CIM query not available (e.g. non-Windows) — skip gracefully
    }

    # Wait for health endpoint
    if ($Name -eq "database-service") {
        $healthUrl = "http://localhost:$Port/health"
    } else {
        $healthUrl = "http://localhost:$Port/"
    }
    if (-not (Wait-ForUrl -Url $healthUrl -Label $Name -TimeoutSec 30)) {
        Stop-On-Failure -Stage "Start $Name" -Reason "Health endpoint not reachable at $healthUrl" `
            -LogPath $logFile -ServiceName $Name
    }

    Write-Ok "$Name is healthy"
}

# Start services sequentially (modular-api last since it depends on PG/ES)
$servicesToStart = $Script:svcList | Where-Object { $_.Name -ne "modular-api" }
foreach ($svc in $servicesToStart) {
    Start-ServiceWindow -Name $svc.Name -Script $svc.Script -Port $svc.Port -App $svc.App
}

# modular-api depends on PG, so it starts last
$modSvc = $Script:svcList | Where-Object { $_.Name -eq "modular-api" } | Select-Object -First 1
Start-ServiceWindow -Name $modSvc.Name -Script $modSvc.Script -Port $modSvc.Port -App $modSvc.App

Write-Step "API Services Status"
Write-Ok "All 6 API services are running and healthy"

# ===========================================================================
# PHASE 5: Kafka Consumers
# ===========================================================================
Write-Step "Starting Kafka Consumers"

foreach ($c in $Script:consumers) {
    $svcDir = Join-Path $Script:repoRoot $c.Dir
    $venvPython = Join-Path $svcDir ".venv/Scripts/python.exe"
    $consumerScript = Join-Path $svcDir $c.File
    $logFile = Join-Path $Script:logDir $c.LogFile

    if (-not (Test-Path $venvPython)) {
        Write-Warn "$($c.Name): .venv not found, skipping"
        continue
    }
    if (-not (Test-Path $consumerScript)) {
        Write-Warn "$($c.Name): $($c.File) not found, skipping"
        continue
    }

    $env:PYTHONPATH = $Script:repoRoot
    $env:ENVIRONMENT = "development"
    $outLog = $logFile
    $errLog = "$logFile.stderr"

    Write-Host "  Launching $($c.Name)..." -ForegroundColor $script:cyanColor
    $proc = Start-Process -FilePath $venvPython -ArgumentList $consumerScript `
        -WorkingDirectory $svcDir `
        -RedirectStandardOutput $outLog -RedirectStandardError $errLog `
        -PassThru -WindowStyle Normal
    if (-not $proc -or $proc.HasExited) {
        Stop-On-Failure -Stage "Start $($c.Name)" -Reason "Failed to start consumer process" `
            -LogPath $logFile -ServiceName $c.Name
    }

    Track-Process -Name $c.Name -ProcessId $proc.Id
    Write-Ok "$($c.Name) launched (PID $($proc.Id))"

    # Give consumer a moment to start and check if it stays alive
    Start-Sleep -Seconds 2
    $alive = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
    if (-not $alive -or $alive.HasExited) {
        $errContent = ""
        if (Test-Path $errLog) { $errContent = Get-Content $errLog -Tail 20 | Out-String }
        Stop-On-Failure -Stage "Start $($c.Name)" -Reason "Consumer exited shortly after launch`n$errContent" `
            -LogPath $logFile -ServiceName $c.Name
    }

    Write-Ok "$($c.Name) is running"
}

Write-Step "Kafka Consumers Status"
Write-Ok "All consumers are running"

# ===========================================================================
# PHASE 6: Frontend (Vite)
# ===========================================================================
if (-not $SkipFrontend) {
    Write-Step "Starting Frontend"

    $frontendDir = Join-Path $Script:repoRoot "services/frontend"
    $frontendLogFile = Join-Path $Script:logDir "frontend.log"

    if (-not (Test-Path $frontendDir)) {
        Stop-On-Failure -Stage "Start Frontend" -Reason "Frontend directory not found at $frontendDir" `
            -Suggestion "Ensure the frontend code exists at services/frontend"
    }

    # Install dependencies only if required
    $nodeModules = Join-Path $frontendDir "node_modules"
    if (-not (Test-Path $nodeModules)) {
        Write-Host "  Installing frontend dependencies (npm install)..." -ForegroundColor $script:yellowColor
        Push-Location $frontendDir
        npm install 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor $script:greenColor }
        if ($LASTEXITCODE -ne 0) {
            Pop-Location
            Stop-On-Failure -Stage "Start Frontend" -Reason "npm install failed" `
                -Suggestion "Check package.json and network connectivity"
        }
        Pop-Location
        Write-Ok "Frontend dependencies installed"
    } else {
        Write-Ok "Frontend dependencies already installed"
    }

    # Launch Vite
    $cmd = @"
`$ErrorActionPreference = 'Stop'
Set-Location '$frontendDir'
npm run dev *>&1 | Tee-Object -FilePath '$frontendLogFile' -Append
"@

    Write-Host "  Launching Vite dev server..." -ForegroundColor $script:cyanColor
    $proc = Start-Process powershell -ArgumentList "-NoExit", "-Command", $cmd -WindowStyle Normal -PassThru
    if (-not $proc -or $proc.HasExited) {
        Stop-On-Failure -Stage "Start Frontend" -Reason "Failed to start Vite process" `
            -LogPath $frontendLogFile -ServiceName "Frontend"
    }

    Track-Process -Name "frontend" -ProcessId $proc.Id
    Write-Ok "Frontend launched (PID $($proc.Id))"

    # Wait for Vite to start and detect the actual port
    Write-Host "  Detecting Vite port..." -NoNewline
    $vitePort = $null
    $viteTimeout = 30
    $elapsed = 0
    while ($elapsed -lt $viteTimeout) {
        Start-Sleep -Seconds 1
        $elapsed++
        if (Test-Path $frontendLogFile) {
            $logContent = Get-Content $frontendLogFile -Tail 50
            # Try multiple patterns for different Vite versions
            $patterns = @("Local:\s+http://localhost:(\d+)", "http://localhost:(\d+)")
            foreach ($pat in $patterns) {
                $match = $logContent | Select-String $pat | Select-Object -First 1
                if ($match) {
                    $vitePort = [int]$match.Matches[0].Groups[1].Value
                    break
                }
            }
            # Fallback: check common ports by probing
            if (-not $vitePort) {
                foreach ($p in @(8080,5173, 4173)) {
                    $conn = Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue | Where-Object { $_.State -eq "Listen" }
                    if ($conn) { $vitePort = $p; break }
                }
            }
            if ($vitePort) { break }
        }
    }

    if ($vitePort) {
        Write-Host " OK (port $vitePort)" -ForegroundColor $script:greenColor
        $Script:frontendPort = $vitePort
    } else {
        Write-Warn " Could not detect Vite port automatically"
        $Script:frontendPort = 8080 # best guess
    }
} else {
    Write-Step "Skipping Frontend (--SkipFrontend)"
    $Script:frontendPort = $null
}

# ===========================================================================
# PHASE 7: Summary
# ===========================================================================
$elapsed = [math]::Round(((Get-Date) - $startTime).TotalSeconds, 1)

Write-Step "Local Development Environment - Summary"
Write-Host "  Elapsed time: $elapsed seconds" -ForegroundColor $script:cyanColor
Write-Host ""

Write-Host "  Infrastructure" -ForegroundColor $script:cyanColor
Write-Host "    PostgreSQL:     localhost:5434" -ForegroundColor $script:greenColor
Write-Host "    Kafka:          localhost:9092" -ForegroundColor $script:greenColor
Write-Host "    Elasticsearch:  localhost:9200" -ForegroundColor $script:greenColor
Write-Host ""

Write-Host "  API Services" -ForegroundColor $script:cyanColor
foreach ($svc in $Script:svcList) {
    Write-Host "    $($svc.Name): http://localhost:$($svc.Port)" -ForegroundColor $script:greenColor
}
Write-Host ""

Write-Host "  Frontend" -ForegroundColor $script:cyanColor
if ($Script:frontendPort) {
    Write-Host "    http://localhost:$($Script:frontendPort)" -ForegroundColor $script:greenColor
} else {
    Write-Host "    (not started)" -ForegroundColor $script:yellowColor
}
Write-Host ""

Write-Host "  Consumers" -ForegroundColor $script:cyanColor
foreach ($c in $Script:consumers) {
    $entry = $Script:pids[$c.Name]
    if ($entry) {
        Write-Host "    $($c.Name) (PID $($entry.ProcessId))" -ForegroundColor $script:greenColor
    } else {
        Write-Host "    $($c.Name) (not tracked)" -ForegroundColor $script:yellowColor
    }
}
Write-Host ""

Write-Host "  Running PIDs" -ForegroundColor $script:cyanColor
$Script:pids.Keys | Sort-Object | ForEach-Object {
    $entry = $Script:pids[$_]
    Write-Host "    $_ : PID $($entry.ProcessId)" -ForegroundColor $script:greenColor
}
Write-Host ""

Write-Host "  Log directory: $Script:logDir" -ForegroundColor $script:cyanColor
Write-Host "  PID file:      $Script:pidFile" -ForegroundColor $script:cyanColor
Write-Host ""

Write-Host "  Commands" -ForegroundColor $script:cyanColor
Write-Host "    Stop all:     .\scripts\dev\stop-local.ps1" -ForegroundColor $script:yellowColor
Write-Host "    Status:       .\scripts\dev\status.ps1" -ForegroundColor $script:yellowColor
Write-Host "    Logs:         .\scripts\dev\logs.ps1 -Follow" -ForegroundColor $script:yellowColor

Write-Host ""
Write-Ok "Startup complete in $elapsed seconds"
