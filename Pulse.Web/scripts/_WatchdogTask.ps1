#Requires -Version 5.1
<#
.SYNOPSIS
    Shared reader for the Pixellot KeepAgentUp scheduled task.
.DESCRIPTION
    Dot-sourced by Get-CoordinatorHealth.ps1 and Restart-PixellotAgent.ps1.

    Reads the task through schtasks.exe, NOT Get-ScheduledTask. The
    ScheduledTasks module goes through CIM, which works for the filtered
    admin token Pulse gets when a tech declines UAC, but answers "Cannot
    connect to CIM server. Access denied" to a more restricted token (a
    Basic User runas on vpu-home, 2026-09-29) - and then reads the task as
    missing. schtasks /query and /run worked under every token tested, so
    this is the one path that cannot misreport the task.

    /xml gives the locale-independent fields (RunLevel, Enabled, action,
    repetition); /fo CSV /v gives the live Status and the run-as account.

    Keep this file pure ASCII (see the note in _AudioInterop.ps1).
#>

function Get-KeepAgentUpTask {
    param([string]$TaskName = 'KeepAgentUp')

    $info = [ordered]@{
        present               = $false
        state                 = $null
        runAs                 = $null
        runLevel              = $null
        elevated              = $null
        repeatIntervalMinutes = $null
        action                = $null
        source                = $null
    }

    $x = $null
    try {
        $raw = @(& schtasks.exe /query /tn $TaskName /xml 2>$null)
        if ($LASTEXITCODE -eq 0 -and $raw.Count -gt 0) {
            # Drop the declaration: it claims UTF-16, but the text is already
            # decoded and [xml] would refuse the mismatch.
            $text = ($raw -join "`n") -replace '^\s*<\?xml[^>]*\?>', ''
            $x = [xml]$text
        }
    } catch { $x = $null }

    if (-not $x -or -not $x.Task) { return $info }

    $info.present = $true
    $info.source  = 'schtasks'

    # Absent RunLevel means LeastPrivilege. Names match Get-ScheduledTask's
    # Highest/Limited so the UI reads the same either way.
    $rl = [string]$x.Task.Principals.Principal.RunLevel
    $info.runLevel = if ($rl -eq 'HighestAvailable') { 'Highest' } else { 'Limited' }
    # Highest is the elevated token Coordinator inherits.
    $info.elevated = ($info.runLevel -eq 'Highest')

    $cmd = $x.Task.Actions.Exec.Command
    if ($cmd) { $info.action = ([string]@($cmd)[0]).Trim() }

    foreach ($trg in @($x.Task.Triggers.ChildNodes)) {
        $iso = $null
        if ($trg.Repetition -and $trg.Repetition.Interval) { $iso = [string]$trg.Repetition.Interval }
        if (-not $iso) { continue }
        # ISO-8601 duration, e.g. PT1M. A healthy box self-heals within one
        # interval, so "the process is missing" only matters alongside a
        # broken task.
        $m = [regex]::Match($iso, 'PT(?:(\d+)H)?(?:(\d+)M)?')
        if ($m.Success) {
            $mins = 0
            if ($m.Groups[1].Value) { $mins += ([int]$m.Groups[1].Value) * 60 }
            if ($m.Groups[2].Value) { $mins += [int]$m.Groups[2].Value }
            if ($mins -gt 0) { $info.repeatIntervalMinutes = $mins }
        }
        break
    }

    try {
        $csv = @(& schtasks.exe /query /tn $TaskName /fo CSV /v 2>$null)
        if ($LASTEXITCODE -eq 0 -and $csv.Count -gt 1) {
            $row = @($csv | ConvertFrom-Csv)[0]
            if ($row) {
                $info.state = [string]$row.Status
                $info.runAs = [string]$row.'Run As User'
            }
        }
    } catch { }

    # Enabled=false is in the XML regardless of locale; the CSV Status column
    # is localized, so the XML wins for Disabled.
    if ([string]$x.Task.Settings.Enabled -eq 'false') { $info.state = 'Disabled' }

    return $info
}
