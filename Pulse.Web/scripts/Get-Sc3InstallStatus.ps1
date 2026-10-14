#Requires -Version 5.1
<#
.SYNOPSIS
    Reads the current ScoreConnect III install status.
.DESCRIPTION
    Companion to Install-ScoreConnectIII.ps1. The install runs as an
    elevated background process and writes status JSON to a known path.
    This script reads that file and returns the current state.

    Status stages:
      starting       - install just kicked off, awaiting elevation
      downloading    - fetching installer from Canopy CDN
      removing       - reinstall only: deleting the old program folder
      installing     - running the installer
      verifying      - checking SC III is reachable on :5000
      complete       - install finished successfully
      failed         - install errored (see 'error' field)
      idle           - no install has been started

    The 'stale' flag is true when the status file hasn't been updated in
    >30s - useful for detecting hung installs.
#>
[CmdletBinding()]
param()

$statusPath = 'C:\ProgramData\Pulse\sc3-install-status.json'
$logPath    = 'C:\ProgramData\Pulse\sc3-install.log'

if (-not (Test-Path $statusPath)) {
    @{
        stage   = 'idle'
        percent = 0
        message = 'No install in progress'
    } | ConvertTo-Json
    exit 0
}

try {
    $raw = Get-Content -Path $statusPath -Raw -ErrorAction Stop
    $status = $raw | ConvertFrom-Json

    # Compute staleness - if the file hasn't been touched in 30s and we're
    # not in a terminal state, the elevated process is likely hung or the
    # user cancelled the UAC prompt. Parse with invariant culture + round-trip
    # style so a non-US-locale VPU still flips stale (a current-culture parse
    # throws on the ISO 'o' string and would leave a hang spinning forever).
    $stale = $false
    if ($status.updatedAt) {
        try {
            $updated = [DateTime]::Parse(
                $status.updatedAt,
                [Globalization.CultureInfo]::InvariantCulture,
                [Globalization.DateTimeStyles]::RoundtripKind)
            $ageSec = ((Get-Date) - $updated).TotalSeconds
            $terminal = $status.stage -in @('complete', 'failed', 'idle')
            if (-not $terminal -and $ageSec -gt 30) { $stale = $true }
        } catch {}
    }

    # Tail of the install log for diagnostics (last 20 lines).
    $logTail = $null
    if (Test-Path $logPath) {
        try {
            $logTail = Get-Content -Path $logPath -Tail 20 -ErrorAction SilentlyContinue
            if ($logTail) { $logTail = $logTail -join "`n" }
        } catch {}
    }

    $out = [ordered]@{
        stage     = $status.stage
        percent   = [int]$status.percent
        message   = $status.message
        error     = $status.error
        updatedAt = $status.updatedAt
        stale     = $stale
        logTail   = $logTail
    }
    $out | ConvertTo-Json -Depth 5
}
catch {
    @{
        stage   = 'unknown'
        percent = 0
        message = 'Could not read install status'
        error   = $_.Exception.Message
    } | ConvertTo-Json
}
