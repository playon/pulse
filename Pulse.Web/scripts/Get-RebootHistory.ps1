#Requires -Version 5.1
<#
.SYNOPSIS
    Reboot/shutdown history with cause + a pending-reboot indicator.
.DESCRIPTION
    Answers "why did this VPU reboot, and is one pending?" -- the question
    every "the box restarted on its own" support ticket starts with.

    Two halves, both LOCAL (event log + registry, no network):

    1. history -- recent restarts/shutdowns built from the System log:
         * 1074 (User32)        clean, software-initiated restart/shutdown.
                                Carries process, user, reason code, and the
                                COMMENT -- Pulse's own Reboot-Vpu.ps1 stamps
                                "Reboot requested from Pulse diagnostics", so a
                                Pulse-initiated reboot is positively identified
                                (byPulse) and an empty/other comment is not us.
         * 1076 (User32)        reason recorded after an unexpected shutdown.
         * 6008 (EventLog)      the previous shutdown was UNEXPECTED.
         * 41   (Kernel-Power)  rebooted without a clean shutdown (power loss
                                / hard crash).
       Each entry gets a best-effort `source` (Pulse / Windows Update /
       Planned-external / Unexpected) and keeps the raw fields so a tech can
       judge for themselves.

    2. pending -- is a reboot already queued? The flags Windows sets:
         CBS RebootPending, WindowsUpdate RebootRequired,
         PendingFileRenameOperations, and a pending computer rename. Plus the
         built-in "Device Install Reboot Required" scheduled task's last run --
         a driver install flagging reboot-required is the usual culprit behind
         an "unprovoked" restart shortly after logon.

    Outputs a single JSON object on stdout.
#>
[CmdletBinding()]
param(
    [int]$HoursBack = 168  # 7 days -- reboots are rarer than ordinary events
)

$ErrorActionPreference = 'Stop'

# Pulse's Reboot-Vpu.ps1 always passes this exact /c comment. Matching it is
# how we positively attribute a reboot to Pulse (vs. anything external).
$PulseCommentMark = 'Pulse diagnostics'

function Get-1074Field {
    param([string]$Message, [string]$Pattern)
    if ($Message -match $Pattern) { return $Matches[1].Trim() }
    return ''
}

try {
    $startTime = (Get-Date).AddHours(-$HoursBack)
    $history = @()

    # -- Recent restart/shutdown events ---------------------------
    $events = Get-WinEvent -FilterHashtable @{
        LogName = 'System'; Id = 1074, 1076, 6008, 41; StartTime = $startTime
    } -MaxEvents 60 -ErrorAction SilentlyContinue

    foreach ($e in @($events)) {
        $msg = if ($e.Message) { $e.Message } else { '' }
        $entry = [ordered]@{
            time       = $e.TimeCreated.ToString('o')
            eventId    = $e.Id
            kind       = 'restart'
            category   = 'planned'
            process    = ''
            user       = ''
            reasonCode = ''
            reasonText = ''
            comment    = ''
            byPulse    = $false
            source     = 'Other'
            message    = if ($msg.Length -gt 400) { $msg.Substring(0, 400) } else { $msg }
        }

        switch ($e.Id) {
            1074 {
                # English System log format -- the same text Event Viewer shows.
                $entry.process    = Get-1074Field $msg 'The process (.+?) has initiated the'
                $entry.user       = Get-1074Field $msg 'on behalf of user (\S+)'
                $entry.reasonText = Get-1074Field $msg 'for the following reason: (.+)'
                $entry.reasonCode = Get-1074Field $msg 'Reason Code: (0x[0-9A-Fa-f]+)'
                $entry.comment    = Get-1074Field $msg 'Comment: (.*)'
                $stype = Get-1074Field $msg 'Shutdown Type: (.+)'
                $entry.kind = if ($stype -match 'restart') { 'restart' }
                              elseif ($stype) { 'shutdown' } else { 'restart' }

                if ($entry.comment -and $entry.comment -match $PulseCommentMark) {
                    $entry.byPulse = $true
                    $entry.source  = 'Pulse (Reboot VPU)'
                }
                elseif ($entry.process -match 'MusNotification|wuauclt|UsoClient|MoUsoCoreWorker|TiWorker|TrustedInstaller|WaaSMedic' `
                        -or $entry.reasonText -match 'Windows Update|Operating System: (Recovery|Upgrade)') {
                    $entry.source = 'Windows Update'
                }
                else {
                    # Planned restart we didn't initiate: a scheduled task
                    # (e.g. Device Install Reboot Required), an admin, or a
                    # third-party tool. Empty comment = definitively not Pulse.
                    $entry.source = 'Planned - external'
                }
            }
            1076 {
                $entry.category   = 'unexpected'
                $entry.kind       = 'unexpected'
                $entry.source     = 'Unexpected (reason logged after)'
                $entry.reasonText = Get-1074Field $msg 'reason: (.+)'
                $entry.user       = Get-1074Field $msg 'on behalf of user (\S+)'
            }
            6008 {
                $entry.category = 'unexpected'
                $entry.kind     = 'unexpected'
                $entry.source   = 'Unexpected shutdown (power loss / crash)'
            }
            41 {
                $entry.category = 'unexpected'
                $entry.kind     = 'unexpected'
                $entry.source   = 'Unexpected (kernel-power: no clean shutdown)'
            }
        }
        $history += $entry
    }

    $history = @($history | Sort-Object { $_.time } -Descending)

    # -- Pending-reboot flags -------------------------------------
    $reasons = @()
    try {
        if (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending') {
            $reasons += 'Component servicing (CBS) staged updates'
        }
    } catch { }
    try {
        if (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired') {
            $reasons += 'Windows Update is waiting to finish'
        }
    } catch { }
    try {
        $pfro = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager' `
                    -Name PendingFileRenameOperations -ErrorAction SilentlyContinue).PendingFileRenameOperations
        if ($pfro -and @($pfro).Count -gt 0) { $reasons += 'Files staged to be renamed/replaced on reboot' }
    } catch { }
    try {
        $cn  = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\ComputerName\ComputerName' -Name ComputerName -ErrorAction SilentlyContinue).ComputerName
        $acn = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\ComputerName\ActiveComputerName' -Name ComputerName -ErrorAction SilentlyContinue).ComputerName
        if ($cn -and $acn -and $cn -ne $acn) { $reasons += 'Computer rename pending' }
    } catch { }

    # The built-in PnP task that reboots after a driver/device install flags
    # reboot-required -- the usual cause of an "unprovoked" restart at logon.
    $deviceInstallLastRun = $null
    try {
        $task = Get-ScheduledTask -TaskName 'Device Install Reboot Required' -ErrorAction SilentlyContinue
        if ($task) {
            $info = $task | Get-ScheduledTaskInfo -ErrorAction SilentlyContinue
            if ($info -and $info.LastRunTime) { $deviceInstallLastRun = $info.LastRunTime.ToString('o') }
        }
    } catch { }

    # -- Uptime / last boot ---------------------------------------
    $lastBoot = $null; $uptime = $null
    try {
        $os = Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue
        if ($os -and $os.LastBootUpTime) {
            $lastBoot = $os.LastBootUpTime.ToString('o')
            $span = (Get-Date) - $os.LastBootUpTime
            $uptime = ('{0}d {1}h {2}m' -f [int]$span.TotalDays, $span.Hours, $span.Minutes)
        }
    } catch { }

    # -- BIOS "After Power Loss" (does the VPU turn back on after a power cut?)
    # HP exposes BIOS settings read-only through its inbox InstrumentedBIOS
    # WMI namespace. Other vendors report 'unsupported', never a pass.
    $afterPowerLoss = [ordered]@{ status = 'unsupported'; value = $null; options = @(); manufacturer = $null; model = $null; message = $null }
    try {
        $cs = Get-CimInstance Win32_ComputerSystem -ErrorAction Stop
        $afterPowerLoss.manufacturer = "$($cs.Manufacturer)".Trim()
        $afterPowerLoss.model = "$($cs.Model)".Trim()
        if ($afterPowerLoss.manufacturer -match '^(HP|Hewlett)') {
            $setting = Get-CimInstance -Namespace 'root\HP\InstrumentedBIOS' -ClassName HP_BIOSEnumeration -Filter "Name='After Power Loss'" -ErrorAction Stop | Select-Object -First 1
            if ($setting) {
                $afterPowerLoss.status = 'read'
                $afterPowerLoss.value = "$($setting.CurrentValue)"
                $afterPowerLoss.options = @($setting.PossibleValues | ForEach-Object { "$_" })
            }
        }
    }
    catch {
        $afterPowerLoss.status = 'error'
        $afterPowerLoss.message = $_.Exception.Message
    }

    [ordered]@{
        pending = [ordered]@{
            isPending = ($reasons.Count -gt 0)
            reasons   = @($reasons)
        }
        afterPowerLoss                = $afterPowerLoss
        lastBoot                      = $lastBoot
        uptime                        = $uptime
        deviceInstallRebootTaskLastRun = $deviceInstallLastRun
        count                         = $history.Count
        history                       = $history
    } | ConvertTo-Json -Depth 5 -Compress
}
catch {
    [ordered]@{
        error   = $true
        message = $_.Exception.Message
        script  = 'Get-RebootHistory.ps1'
    } | ConvertTo-Json -Compress
}
