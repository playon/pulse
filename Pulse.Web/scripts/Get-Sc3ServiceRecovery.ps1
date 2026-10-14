#Requires -Version 5.1
<#
.SYNOPSIS
    Reports whether ScoreConnect III is configured to restart itself after a
    crash, plus recent crash / auto-recovery evidence from the event log.
.DESCRIPTION
    SC III has a process-killing unhandled WebSocket exception
    (WebSocketsMiddleWare.SendToAllInsteadOfId) present in every version seen
    in the field. Sportzcast's installer configures NO service recovery, so a
    crash leaves the scoreboard dead until a human notices - the service just
    sits Stopped. Pulse-driven installs now apply SCM restart actions
    (Install-ScoreConnectIII.ps1), and this collector reports whether a given
    VPU actually has them, so a tech can confirm the unit is protected.

    Recovery config is read from the REGISTRY, not `sc.exe qfailure`. The
    sc.exe output is localized and its labels shift between Windows builds;
    the registry blob is the same bytes everywhere. Layout of
    HKLM:\SYSTEM\CurrentControlSet\Services\<name>\FailureActions
    (SERVICE_FAILURE_ACTIONS as persisted):

        0x00  DWORD  dwResetPeriod (seconds)
        0x04  DWORD  offset to lpRebootMsg (0 = none)
        0x08  DWORD  offset to lpCommand   (0 = none)
        0x0C  DWORD  cActions
        0x10  DWORD  offset to the actions array (normally 0x14)
        0x14  array of SC_ACTION { DWORD Type; DWORD Delay(ms) }

    SC_ACTION types: 0 None, 1 Restart, 2 Reboot, 3 Run command.
    A missing FailureActions value is the Sportzcast default: no recovery.

    Event evidence (last 7 days, System log):
      7034 - service terminated unexpectedly, NO corrective action taken
      7031 - service terminated unexpectedly, corrective action taken (restart)
    A unit with the fix logs 7031; an unprotected one logs 7034.

    ASCII ONLY (see CLAUDE.md PowerShell 5.1 rules). No COM, no hashtable
    Sort/Group, unwanted returns assigned to $null.
.PARAMETER ServiceName
    Override the service to inspect (for testing).
.PARAMETER DaysBack
    How far back to count crashes / auto-restarts. Default 7.
#>
[CmdletBinding()]
param(
    [string]$ServiceName = 'ScoreConnectIII',
    [int]$DaysBack = 7
)

$ErrorActionPreference = 'Stop'

$out = [ordered]@{
    serviceName          = $ServiceName
    installed            = $false
    status               = $null
    startType            = $null
    recoveryConfigured   = $false
    resetPeriodSec       = $null
    actions              = @()
    actionSummary        = $null
    crashCount           = 0
    autoRecoveredCount   = 0
    lastCrash            = $null
    lastAutoRestart      = $null
    daysBack             = $DaysBack
    guardPresent         = $false
    guardEnabled         = $false
    guardLastRun         = $null
    guardLastResult      = $null
    error                = $null
}

try {
    $svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if (-not $svc) {
        # Not installed is a legitimate answer, not an error: a legacy SC I/II
        # box has no SC III service at all.
        $out.error = $null
        $out | ConvertTo-Json -Depth 5
        exit 0
    }

    $out.installed = $true
    $out.status    = "$($svc.Status)"

    # StartType is not on ServiceController in 5.1's older builds - read the
    # CIM instance, which also gives the authoritative start mode string.
    try {
        $cim = Get-CimInstance -ClassName Win32_Service -Filter "Name='$ServiceName'" -ErrorAction SilentlyContinue
        if ($cim) { $out.startType = $cim.StartMode }
    } catch {}

    # -- Recovery configuration (registry) --------------------------------
    $svcKey = "HKLM:\SYSTEM\CurrentControlSet\Services\$ServiceName"
    $blob = $null
    try {
        $prop = Get-ItemProperty -Path $svcKey -Name 'FailureActions' -ErrorAction SilentlyContinue
        if ($prop) { $blob = $prop.FailureActions }
    } catch {}

    if ($blob -and $blob.Length -ge 20) {
        $bytes = [byte[]]$blob
        $out.resetPeriodSec = [int][BitConverter]::ToUInt32($bytes, 0)
        $count       = [int][BitConverter]::ToUInt32($bytes, 12)
        $actionsAt   = [int][BitConverter]::ToUInt32($bytes, 16)
        if ($actionsAt -lt 20) { $actionsAt = 20 }

        $typeNames = @{ 0 = 'None'; 1 = 'Restart'; 2 = 'Reboot'; 3 = 'Run command' }
        # Emit pscustomobject, never hashtables - 5.1 cannot resolve hashtable
        # keys as properties downstream (CLAUDE.md rule 4).
        $parsed = New-Object 'System.Collections.Generic.List[object]'
        for ($i = 0; $i -lt $count; $i++) {
            $at = $actionsAt + ($i * 8)
            if (($at + 8) -gt $bytes.Length) { break }
            $t = [int][BitConverter]::ToUInt32($bytes, $at)
            $d = [int][BitConverter]::ToUInt32($bytes, $at + 4)
            $name = $typeNames[$t]
            if (-not $name) { $name = "Unknown ($t)" }
            $parsed.Add([pscustomobject]@{ type = $name; delayMs = $d })
        }
        # ToArray() so ConvertTo-Json emits a plain array, and so a single
        # action does not collapse to a bare object.
        $out.actions = $parsed.ToArray()
        $restarts = @($parsed | Where-Object { $_.type -eq 'Restart' })
        $out.recoveryConfigured = ($restarts.Count -gt 0)

        if ($out.recoveryConfigured) {
            $delays = @($restarts | ForEach-Object {
                if ($_.delayMs -ge 1000) { "$([int]($_.delayMs / 1000))s" } else { "$($_.delayMs)ms" }
            })
            $out.actionSummary = 'Restart after ' + ($delays -join ', ')
        } else {
            $out.actionSummary = 'No restart action configured'
        }
    } else {
        $out.actionSummary = 'No recovery actions configured'
    }

    # -- The keep-on task (Set-Sc3ServiceRecovery.ps1) ----------------------
    # Sportzcast's installer re-creates the service without restart actions;
    # "Pulse ScoreConnect Guard" puts them back on its own.
    try {
        $gt = Get-ScheduledTask -TaskName 'Pulse ScoreConnect Guard' -ErrorAction SilentlyContinue
        if ($gt) {
            $out.guardPresent = $true
            $out.guardEnabled = ($gt.State -ne 'Disabled' -and @($gt.Triggers | Where-Object { $_.Enabled }).Count -eq 3)
            $gi = Get-ScheduledTaskInfo -TaskName 'Pulse ScoreConnect Guard' -ErrorAction SilentlyContinue
            # 1999-11-30 is Task Scheduler's "never run".
            if ($gi -and $gi.LastRunTime -and $gi.LastRunTime.Year -gt 2000) {
                $out.guardLastRun = $gi.LastRunTime.ToString('o')
                $out.guardLastResult = [int64]$gi.LastTaskResult
            }
        }
    } catch {}

    # -- Crash / recovery evidence from the System log --------------------
    # 7034 = terminated, nothing done. 7031 = terminated, SCM restarted it.
    try {
        $since = (Get-Date).AddDays(-[Math]::Abs($DaysBack))
        $evts = @(Get-WinEvent -FilterHashtable @{
            LogName   = 'System'
            Id        = 7031, 7034
            StartTime = $since
        } -ErrorAction SilentlyContinue | Where-Object { $_.Message -match [regex]::Escape($ServiceName) })

        foreach ($e in $evts) {
            $stamp = $e.TimeCreated.ToString('o')
            if ($e.Id -eq 7031) {
                $out.autoRecoveredCount++
                if (-not $out.lastAutoRestart -or $stamp -gt $out.lastAutoRestart) { $out.lastAutoRestart = $stamp }
            } else {
                if (-not $out.lastCrash -or $stamp -gt $out.lastCrash) { $out.lastCrash = $stamp }
            }
        }
        # Every 7031/7034 is a crash; 7031 additionally means it was recovered.
        $out.crashCount = $evts.Count
        # A 7031's own timestamp is also the crash time - surface the most
        # recent crash whichever way it ended.
        if ($out.lastAutoRestart -and (-not $out.lastCrash -or $out.lastAutoRestart -gt $out.lastCrash)) {
            $out.lastCrash = $out.lastAutoRestart
        }
    } catch {}

    $out | ConvertTo-Json -Depth 5
}
catch {
    $out.error = $_.Exception.Message
    $out | ConvertTo-Json -Depth 5
}
