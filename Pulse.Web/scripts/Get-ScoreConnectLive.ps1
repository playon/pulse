#Requires -Version 5.1
<#
.SYNOPSIS
    Lightweight live poll of ScoreConnect III scoreboard data.
.DESCRIPTION
    Companion to Get-ScoreConnectStatus.ps1, built for high-frequency polling
    (every 1-2s) to drive a live-updating scoreboard in the Pulse UI.

    Hits ONLY SC III's get-status endpoint and returns the raw scoreboard
    data string plus data-flow status. It deliberately does NOT:
      - touch SC II (port 1400)
      - enumerate USB / run WMI queries
      - hit config / bot / scorelink endpoints

    SC III is a stateless REST service designed for concurrent clients --
    polling get-status does NOT interfere with the live data stream that
    Pixellot's agent relies on. Each request is independent: a single
    HTTP GET to localhost:5000, connect -> respond -> close.
.PARAMETER BaseUrl
    SC III base URL. Defaults to http://127.0.0.1:5000.
#>
[CmdletBinding()]
param([string]$BaseUrl = 'http://127.0.0.1:5000')

$ErrorActionPreference = 'Stop'
$BaseUrl = $BaseUrl.TrimEnd('/')
# 'localhost' can take 12-40s to resolve in a fresh process (VPU2,
# 2026-09-29); 127.0.0.1 answers at once. SC III listens on IPv4 and IPv6.
$BaseUrl = $BaseUrl -replace '^(https?://)localhost(?=[:/]|$)', '${1}127.0.0.1'

$result = @{
    reachable  = $false
    rawData    = $null
    dataStatus = $null
    ts         = (Get-Date).ToString('o')
    error      = $null
}

try {
    $resp = Invoke-WebRequest -Uri "$BaseUrl/api/configuration/get-status" `
        -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
    $result.reachable = $true

    try {
        $data = $resp.Content | ConvertFrom-Json

        # Raw scoreboard data string (Daktronics RTD etc.)
        if ($data.PSObject.Properties['data']) {
            $raw = "$($data.data)".Trim()
            if ($raw -ne '') { $result.rawData = $raw }
        }

        # Data-flow status ("Data is present..." / "No Scoreboard data...")
        if ($data.PSObject.Properties['scoreBoardData'] -and $data.scoreBoardData) {
            $result.dataStatus = $data.scoreBoardData.description
        }
    } catch {}
}
catch {
    $result.error = $_.Exception.Message
}

$result | ConvertTo-Json -Depth 5
