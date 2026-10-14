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

    Needs an elevated shell (registering a SYSTEM task needs admin).

    ASCII ONLY (CLAUDE.md PowerShell 5.1 rules). Unwanted returns go to $null.

.PARAMETER InstallDir
    Pulse install root. Default C:\Pulse (what the launchers use).

.PARAMETER Uninstall
    Remove the task. The state, queue, cache and log files are left in place.

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
    [switch]$RunNow
)

$ErrorActionPreference = 'Stop'
$TaskName = 'Pulse Fleet Monitor'

function Info($msg) { Write-Host "  $msg" }
function Fail($msg) { Write-Host "  [ERROR] $msg" -ForegroundColor Red; exit 1 }

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
        $null = Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Info "Removed $TaskName."
    } else {
        Info "$TaskName was not installed."
    }
    exit 0
}

$pyExe = Join-Path $InstallDir 'app\python\python.exe'
$tick  = Join-Path $InstallDir 'app\monitor_once.py'
if (-not (Test-Path -LiteralPath $pyExe)) { Fail "Embedded Python not found at $pyExe. Launch Pulse once so it sets up its runtime." }
if (-not (Test-Path -LiteralPath $tick))  { Fail "$tick not found. This Pulse build has no fleet monitor; install one that does." }

# XML text: escape the paths for element content.
$pyXml   = [Security.SecurityElement]::Escape($pyExe)
$argXml  = [Security.SecurityElement]::Escape('"' + $tick + '"')
$dirXml  = [Security.SecurityElement]::Escape((Join-Path $InstallDir 'app'))

# Task Scheduler 1.2 schema.
#   Repetition PT5M with no Duration = every 5 minutes, indefinitely.
#   IgnoreNew: a slow pass is never joined by a second copy.
#   PT5M ExecutionTimeLimit: a hung pass is killed, never left running.
#   Priority 7: below normal (the tick also lowers itself and its PowerShell children).
$xml = @"
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Author>Pulse</Author>
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

$null = Register-ScheduledTask -TaskName $TaskName -Xml $xml -Force
$t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $t -or $t.State -eq 'Disabled') { Fail "The task did not register as enabled." }
Info "Installed $TaskName (every 5 minutes, as SYSTEM, below-normal priority)."

if ($RunNow) {
    $null = Start-ScheduledTask -TaskName $TaskName
    Info "Started one tick now. Check the log in a minute or two."
}
Show-Status
