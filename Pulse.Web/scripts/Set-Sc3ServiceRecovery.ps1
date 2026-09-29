#Requires -Version 5.1
<#
.SYNOPSIS
    Turns on crash auto-restart for the ScoreConnect III service.
.DESCRIPTION
    SC III dies on an unhandled WebSocket exception in every version seen in
    the field, and Sportzcast's installer configures no service recovery, so
    the service just sits Stopped until someone notices. Pulse-driven installs
    apply recovery (Install-ScoreConnectIII.ps1); this applies the same
    settings to an SC III that Pulse did not install.

    Found on vpu-home 2026-09-29: SC III crashed (.NET 1026, WebSocketException
    "remote party closed the WebSocket connection without completing the close
    handshake", System 7034) with no recovery configured, and stayed down.

    Same actions as the installer: restart after 5s, 5s, then 30s; the failure
    count resets daily. Validated there on VPU2 2026-09-01: a force-killed
    process was back serving :5000 in under 12 seconds.

    Reads the result back from the registry (FailureActions), the same source
    Get-Sc3ServiceRecovery.ps1 reports from, so "configured" is measured.

    ASCII ONLY (CLAUDE.md PowerShell 5.1 rules). Unwanted returns go to $null.
#>
[CmdletBinding()]
param(
    [string]$ServiceName = 'ScoreConnectIII'
)

$ErrorActionPreference = 'Stop'

$out = [ordered]@{
    success    = $false
    configured = $false
    message    = $null
}

try {
    if ($ServiceName -ne 'ScoreConnectIII') {
        $out.message = "Only ScoreConnectIII can be changed here."
        $out | ConvertTo-Json -Compress
        exit 0
    }
    $svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if (-not $svc) {
        $out.message = "ScoreConnect III is not installed on this VPU."
        $out | ConvertTo-Json -Compress
        exit 0
    }

    # Plain tokens pass through PowerShell to sc.exe cleanly (the empty-string
    # actions= "" form does not; see Install-ScoreConnectIII.ps1).
    $scOut = & sc.exe failure $ServiceName reset= 86400 actions= restart/5000/restart/5000/restart/30000 2>&1
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        $out.message = "Windows refused the change (sc.exe exit $code). Pulse may not be running as administrator. " + (($scOut | Out-String).Trim())
        $out | ConvertTo-Json -Compress
        exit 0
    }

    # Read it back: at least one Restart action in the persisted blob.
    $blob = $null
    try {
        $prop = Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\$ServiceName" -Name 'FailureActions' -ErrorAction SilentlyContinue
        if ($prop) { $blob = [byte[]]$prop.FailureActions }
    } catch {}
    $restarts = 0
    if ($blob -and $blob.Length -ge 20) {
        $count = [int][BitConverter]::ToUInt32($blob, 12)
        $at0 = [int][BitConverter]::ToUInt32($blob, 16)
        if ($at0 -lt 20) { $at0 = 20 }
        for ($i = 0; $i -lt $count; $i++) {
            $at = $at0 + ($i * 8)
            if (($at + 8) -gt $blob.Length) { break }
            if ([BitConverter]::ToUInt32($blob, $at) -eq 1) { $restarts++ }
        }
    }
    $out.configured = ($restarts -gt 0)
    $out.success = $out.configured
    if ($out.configured) {
        $out.message = "Crash auto-restart is on: Windows restarts ScoreConnect III 5 seconds after a crash."
    } else {
        $out.message = "sc.exe reported success, but no restart action reads back from the registry."
    }
}
catch {
    $out.message = "Could not turn on crash auto-restart: $($_.Exception.Message)"
}

$out | ConvertTo-Json -Compress
