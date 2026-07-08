#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Port-checking utilities for local development scripts.
#>

function Test-PortFree {
    <#
    .SYNOPSIS
      Returns $true if nothing is listening on the given TCP port.
    #>
    param([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    return (-not $conn)
}

function Find-ProcessOnPort {
    <#
    .SYNOPSIS
      Returns the process (if any) listening on a port.
    #>
    param([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    if ($conn) {
        try { return Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue } catch {}
    }
    return $null
}

function Wait-Port {
    <#
    .SYNOPSIS
      Blocks until a port is open (someone is listening) or timeout.
      Returns $true if port opened, $false on timeout.
    #>
    param(
        [int]$Port,
        [string]$Label = "port $Port",
        [int]$TimeoutSec = 30
    )
    $elapsed = 0
    while ($elapsed -lt $TimeoutSec) {
        if (-not (Test-PortFree $Port)) { return $true }
        Start-Sleep -Seconds 1
        $elapsed++
    }
    return $false
}

function Wait-Url {
    <#
    .SYNOPSIS
      Blocks until an HTTP URL returns 200 or timeout.
      Returns $true if OK, $false on timeout.
    #>
    param(
        [string]$Url,
        [string]$Label = $Url,
        [int]$TimeoutSec = 30
    )
    $elapsed = 0
    while ($elapsed -lt $TimeoutSec) {
        try {
            $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($r.StatusCode -eq 200 -or $r.StatusCode -eq 401) { return $true }
        } catch {}
        Start-Sleep -Seconds 1
        $elapsed++
    }
    return $false
}
