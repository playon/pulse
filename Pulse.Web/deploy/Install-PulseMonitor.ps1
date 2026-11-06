#Requires -Version 5.1
<#
.SYNOPSIS
    Install, check or remove the Pulse fleet monitor scheduled task.

.DESCRIPTION
    Registers "Pulse Fleet Monitor": every 5 minutes, as SYSTEM, at
    below-normal priority, Task Scheduler runs

        <InstallDir>\app\python\python.exe <InstallDir>\app\monitor_once.py

    Each run is one tick. Most ticks make one tasklist call and exit. A due tick
    runs a readiness pass and sends a check-in to the Pulse check-in Worker.
    Passes wait while vpu.exe is running (an event is live). See
    app\monitor_once.py for the full resource budget.

    The task holds no port and needs no download (no nssm), so an interactive
    Pulse launch on the same unit is unaffected. It runs whatever Pulse build
    the launcher last installed in <InstallDir>: if a later launch installs a
    build without app\monitor_once.py, the task fails quietly until a build
    with it is installed again, and the unit stops checking in.

    If Register-ScheduledTask fails (some units have a broken CIM task
    provider: "Invalid class", 0x80041010), the same XML is registered with
    schtasks.exe instead, and the output says so. -Uninstall and -RunNow fall
    back to schtasks.exe the same way. Show-Status and the "already current"
    check only read, and reads work on those units, so they are left on the
    ScheduledTask cmdlets.

    Needs an elevated shell (registering a SYSTEM task needs admin).

    ASCII ONLY (CLAUDE.md PowerShell 5.1 rules). Unwanted returns go to $null.

.PARAMETER InstallDir
    Pulse install root. Default C:\Pulse (what the launchers use).

.PARAMETER Runner
    Register the task to run the fleet agent's runner (PV-49) instead of the
    monitor directly:

        <InstallDir>\runtime\python\python.exe <InstallDir>\agent_runner.py

    The runner runs the monitor from one of two slots under
    <InstallDir>\slots and moves the unit between agent builds as fleet
    control says. fleet_enroll.py (Pulse Settings, Fleet Monitoring) sets the
    folder up and passes this.

.PARAMETER Uninstall
    Remove the task. The state, queue, cache and log files are left in place
    unless -Purge is given too.

.PARAMETER Purge
    With -Uninstall: also delete the monitor's state, queue, cache and log
    files, leaving no trace of it on the unit.

.PARAMETER Force
    Register the task again even if the same definition is already installed.

.PARAMETER Status
    Report whether the task is installed, when it last ran and its result.

.PARAMETER RunNow
    After installing, start one tick immediately.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File C:\Pulse\deploy\Install-PulseMonitor.ps1 -RunNow
#>
[CmdletBinding()]
param(
    [string]$InstallDir = 'C:\Pulse',
    [switch]$Uninstall,
    [switch]$Status,
    [switch]$RunNow,
    [switch]$Purge,
    [switch]$Force,
    [switch]$Runner
)

$ErrorActionPreference = 'Stop'
$TaskName = 'Pulse Fleet Monitor'
# Bump when the task definition below changes. An install that finds this
# version already registered, enabled and pointing at the same files does
# nothing: Canopy Leaf's rollout reinstalled itself on units that already had
# it, batch after batch, and nobody could tell which units had it
# (#leaf-deploy-coordination, 2023-05). Which units run the monitor is read
# from the check-in data, not from installs.
$TaskVersion = '3'
$MonitorFiles = @('pulse-monitor-state.json', 'pulse-monitor-state.json.tmp',
                  'pulse-monitor-checkin-queue.json', 'pulse-monitor-checkin-queue.json.tmp',
                  'pulse-monitor-posts.json', 'pulse-monitor-posts.json.tmp',
                  'pulse-monitor-cache.json', 'pulse-monitor-cache.json.tmp',
                  'pulse-monitor.log', 'pulse-monitor.log.1',
                  'pulse-monitor-ticks.log', 'pulse-monitor-ticks.log.1',
                  'pulse-monitor-event.json', 'pulse-monitor-event.json.tmp',
                  'agent-slots.json', 'agent-slots.json.tmp', 'agent-update.json', 'agent-update.json.tmp',
                  'agent-tick.running', 'agent-download.tmp', 'agent-runner.log', 'agent-runner.log.1')

function Info($msg) { Write-Host "  $msg" }
function Warn($msg) { Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Fail($msg) { Write-Host "  [ERROR] $msg" -ForegroundColor Red; exit 1 }

# schtasks.exe fallback. Some units have a CIM/WMI Task Scheduler provider that
# can read tasks but not write them: Register-ScheduledTask dies with "Invalid
# class" (0x80041010) while schtasks.exe, which talks to the Task Scheduler
# service directly, works. Returns Code and Text. Native stderr is read with
# 'Continue' because 5.1 turns it into a terminating error under 'Stop'.
function Invoke-Schtasks([string[]]$SchArgs) {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $text = (& schtasks.exe @SchArgs 2>&1 | Out-String).Trim()
        return [pscustomobject]@{ Code = $LASTEXITCODE; Text = $text }
    } catch {
        return [pscustomobject]@{ Code = -1; Text = [string]$_.Exception.Message }
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Remove-MonitorTask {
    try {
        $null = Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        return $true
    } catch {
        Warn "Unregister-ScheduledTask failed ($($_.Exception.Message.Trim())); trying schtasks.exe."
        $r = Invoke-Schtasks @('/Delete', '/TN', $TaskName, '/F')
        if ($r.Code -ne 0) { Fail "Could not remove $TaskName. schtasks.exe: $($r.Text)" }
        return $true
    }
}

function Start-MonitorTask {
    try {
        $null = Start-ScheduledTask -TaskName $TaskName
    } catch {
        Warn "Start-ScheduledTask failed ($($_.Exception.Message.Trim())); trying schtasks.exe."
        $r = Invoke-Schtasks @('/Run', '/TN', $TaskName)
        if ($r.Code -ne 0) { Fail "Could not start $TaskName. schtasks.exe: $($r.Text)" }
    }
}

function Show-Status {
    $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $t) { Info "$TaskName is not installed."; return }
    $i = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction SilentlyContinue
    Info "$TaskName : $($t.State)"
    # 1999-11-30 is Task Scheduler's "never run".
    if ($i -and $i.LastRunTime -and $i.LastRunTime.Year -gt 2000) {
        Info ("Last run: " + $i.LastRunTime.ToString('yyyy-MM-dd HH:mm:ss') + "  result: 0x" + ('{0:X}' -f [int64]$i.LastTaskResult))
    } else {
        Info "Last run: never"
    }
    if ($i -and $i.NextRunTime) { Info ("Next run: " + $i.NextRunTime.ToString('yyyy-MM-dd HH:mm:ss')) }
    $statePath = Join-Path $InstallDir 'pulse-monitor-state.json'
    if (Test-Path -LiteralPath $statePath) {
        try {
            $st = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
            Info ("Verdict: " + $st.status + "  updated " + $st.updatedAt)
        } catch {}
    }
    Info ("Log: " + (Join-Path $InstallDir 'pulse-monitor.log'))
}

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$elevated = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if ($Status) { Show-Status; exit 0 }

if (-not $elevated) {
    Fail "Not elevated. Re-run this from an elevated (Run as administrator) shell."
}

if ($Uninstall) {
    $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($t) {
        $null = Remove-MonitorTask
        Info "Removed $TaskName."
    } else {
        Info "$TaskName was not installed."
    }
    if ($Purge) {
        $removed = 0
        foreach ($f in $MonitorFiles) {
            $p = Join-Path $InstallDir $f
            if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Force; $removed++ }
        }
        Info "Deleted $removed monitor file(s) from $InstallDir."
    }
    exit 0
}

if ($Runner) {
    $pyExe   = Join-Path $InstallDir 'runtime\python\python.exe'
    $tick    = Join-Path $InstallDir 'agent_runner.py'
    $workDir = $InstallDir
} else {
    $pyExe   = Join-Path $InstallDir 'app\python\python.exe'
    $tick    = Join-Path $InstallDir 'app\monitor_once.py'
    $workDir = Join-Path $InstallDir 'app'
}
if (-not (Test-Path -LiteralPath $pyExe)) { Fail "Embedded Python not found at $pyExe. Launch Pulse once so it sets up its runtime." }
if (-not (Test-Path -LiteralPath $tick))  { Fail "$tick not found. This Pulse build has no fleet monitor; install one that does." }

# XML text: escape the paths for element content.
$pyXml   = [Security.SecurityElement]::Escape($pyExe)
$argXml  = [Security.SecurityElement]::Escape('"' + $tick + '"')
$dirXml  = [Security.SecurityElement]::Escape($workDir)

# Task Scheduler 1.2 schema.
#   Repetition PT5M with no Duration = every 5 minutes, indefinitely.
#   IgnoreNew: a slow pass is never joined by a second copy.
#   PT5M ExecutionTimeLimit: a hung pass is killed, never left running.
#   Priority 7: below normal (the tick also lowers itself and its PowerShell children).
$xml = @"
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Author>Pulse</Author>
    <Version>$TaskVersion</Version>
    <Description>Pulse fleet monitor. Every 5 minutes checks whether this VPU is ready to stream and reports to the Pulse check-in service. Waits while an event is live. Remove with Install-PulseMonitor.ps1 -Uninstall.</Description>
  </RegistrationInfo>
  <Triggers>
    <TimeTrigger>
      <Enabled>true</Enabled>
      <StartBoundary>2026-01-01T00:00:00</StartBoundary>
      <Repetition>
        <Interval>PT5M</Interval>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
    </TimeTrigger>
    <BootTrigger>
      <Enabled>true</Enabled>
      <Delay>PT3M</Delay>
    </BootTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>S-1-5-18</UserId>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <ExecutionTimeLimit>PT5M</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>$pyXml</Command>
      <Arguments>$argXml</Arguments>
      <WorkingDirectory>$dirXml</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing -and -not $Force) {
    $sameVersion = ($existing.Version -eq $TaskVersion)
    $action = @($existing.Actions)[0]
    $sameFiles = $action -and ($action.Execute -eq $pyExe) -and ($action.Arguments -eq ('"' + $tick + '"'))
    if ($sameVersion -and $sameFiles -and $existing.State -ne 'Disabled') {
        Info "$TaskName is already installed and current (definition $TaskVersion). Nothing to do."
        if ($RunNow) {
            Start-MonitorTask
            Info "Started one tick now."
        }
        Show-Status
        exit 0
    }
}

$regError = $null
$viaSchtasks = $false
try {
    $null = Register-ScheduledTask -TaskName $TaskName -Xml $xml -Force
} catch {
    $regError = $_.Exception.Message.Trim()
}
if ($regError) {
    # Same XML, registered through schtasks.exe. It wants UTF-16 on disk.
    Warn "Register-ScheduledTask failed: $regError"
    $tmp = Join-Path ([IO.Path]::GetTempPath()) ('pulse-monitor-task-' + [guid]::NewGuid().ToString('N') + '.xml')
    try {
        Set-Content -LiteralPath $tmp -Value $xml -Encoding Unicode
        $r = Invoke-Schtasks @('/Create', '/TN', $TaskName, '/XML', $tmp, '/F')
    } finally {
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
    }
    if ($r.Code -ne 0) {
        Fail "Could not register $TaskName. Register-ScheduledTask: $regError | schtasks.exe (exit $($r.Code)): $($r.Text)"
    }
    $viaSchtasks = $true
}
$t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $t -and $viaSchtasks) {
    # The CIM read can be as sick as the CIM write. Ask the service directly.
    $q = Invoke-Schtasks @('/Query', '/TN', $TaskName)
    if ($q.Code -ne 0) { Fail "The task did not register. schtasks.exe /Query: $($q.Text)" }
} elseif (-not $t -or $t.State -eq 'Disabled') {
    Fail "The task did not register as enabled."
}
Info "Installed $TaskName (every 5 minutes, as SYSTEM, below-normal priority)."
if ($viaSchtasks) {
    Info "Registered via schtasks.exe because Register-ScheduledTask failed ($regError)."
}

if ($RunNow) {
    Start-MonitorTask
    Info "Started one tick now. Check the log in a minute or two."
}
Show-Status
