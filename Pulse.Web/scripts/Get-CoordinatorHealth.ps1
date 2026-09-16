#Requires -Version 5.1
<#
.SYNOPSIS
    Diagnoses the Pixellot Coordinator websocket-bind failure and the
    KeepAgentUp watchdog task that causes it.
.DESCRIPTION
    Coordinator serves its websocket on the HTTP.SYS strong-wildcard prefix
    http://+:9001/. Registering that prefix needs either an elevated token or a
    URL ACL reservation. Fleet VPUs have NO reservation for it (verified), so the
    elevated token is the only thing that makes the bind work, and it comes from
    the KeepAgentUp scheduled task running at RunLevel=Highest.

    Start keepagentup.exe without elevation and Coordinator fails every launch:

        WebSocketServer.cs(218) Start exception encountered while starting
        websocket server : Access is denied
           at System.Net.HttpListener.AddAllPrefixes()
        Program.cs(307) Initializer Could not setup communication with the servers!

    Agent stays up, so the unit looks half-alive; the gRPC servers bind fine
    because gRPC does not go through HTTP.SYS. Reproduced on demand on a real
    VPU on 5.37.1 (2026-09-16): 9 failed binds, 0 successes, cleared instantly by
    running the task instead of the exe. Pixellot ticket: "Fatal Coordinator
    Errors - PXLS2_6179 Apex (NC) Gym" (3 units, no upstream fix).

    Two field-truth guardrails baked in:

    1. A point-in-time process check CANNOT see the restart cycle - during the
       loop Coordinator is absent about as often as it is present, so one sample
       reports a healthy "Running" mid-cycle. We sample PIDs twice and compare.
    2. Port 9001's listener is ALWAYS owned by PID 4 (the HTTP.SYS kernel
       driver), healthy or not, so listener ownership is not a usable signal.
       Only the bind result in the log is.

    LOCAL collector: scheduled task, process table, registry, log files. No
    network calls, no state mutated.

    Outputs JSON to stdout.
.PARAMETER SampleSeconds
    Gap between the two PID samples used to detect a restart cycle. Default 6.
.PARAMETER HoursBack
    Hours of Coordinator log history to count bind results over. Default 6.
#>
[CmdletBinding()]
param(
    [int]$SampleSeconds = 6,
    [int]$HoursBack = 6
)

$ErrorActionPreference = 'Stop'

$logDir        = 'C:\Pixellot\Data\Log'
$coordExe      = 'C:\Pixellot\bin\Coordinator.exe'
$keepAgentExe  = 'C:\Pixellot\bin\KeepAgentUp.exe'
$wsPort        = 9001
$wsPrefix      = 'http://+:9001/'
$taskName      = 'KeepAgentUp'

# Log signatures. Line numbers are part of the signature - the failing catch
# block (218) and the success path (206) are in the same Start() method, so the
# pair tells you which branch ran.
$sigBindFail   = 'WebSocketServer.cs(218)'
$sigBindOk     = 'Server listening'
$sigFatalComms = 'Could not setup communication with the servers!'

function Get-ProcSnapshot {
    # Names are matched exactly so look-alikes (leaf_agent.exe) cannot match,
    # the same guard Get-Services.ps1 uses.
    $snap = @{}
    foreach ($n in @('KeepAgentUp', 'Agent', 'Coordinator')) {
        $p = @(Get-Process -Name $n -ErrorAction SilentlyContinue)
        if ($p.Count -gt 0) { $snap[$n] = $p[0].Id } else { $snap[$n] = $null }
    }
    return $snap
}

function Get-ProcOwner {
    param([string]$ExeName)
    # Scoped by -Filter: enumerating every process and calling GetOwner() on
    # each is slow enough to time out a remote shell on fleet hardware.
    try {
        $wmi = @(Get-WmiObject -Class Win32_Process -Filter "Name='$ExeName'" -ErrorAction SilentlyContinue)
        if ($wmi.Count -eq 0) { return $null }
        $owner = $wmi[0].GetOwner()
        if ($owner -and $owner.User) {
            if ($owner.Domain) { return ($owner.Domain + '\' + $owner.User) }
            return [string]$owner.User
        }
    } catch { }
    return $null
}

function Get-WatchdogTask {
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
    try {
        $t = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        if ($t) {
            $info.present  = $true
            $info.source   = 'Get-ScheduledTask'
            $info.state    = [string]$t.State
            $info.runAs    = [string]$t.Principal.UserId
            $info.runLevel = [string]$t.Principal.RunLevel
            # RunLevel Highest is the elevated token Coordinator inherits.
            $info.elevated = ($info.runLevel -eq 'Highest')
            $act = @($t.Actions)
            if ($act.Count -gt 0) { $info.action = [string]$act[0].Execute }
            foreach ($trg in @($t.Triggers)) {
                if ($trg.Repetition -and $trg.Repetition.Interval) {
                    # ISO-8601 duration, e.g. PT1M. A healthy box self-heals
                    # within one interval, so "the process is missing" only
                    # matters alongside a broken task.
                    $iso = [string]$trg.Repetition.Interval
                    $m = [regex]::Match($iso, 'PT(?:(\d+)H)?(?:(\d+)M)?')
                    if ($m.Success) {
                        $mins = 0
                        if ($m.Groups[1].Value) { $mins += ([int]$m.Groups[1].Value) * 60 }
                        if ($m.Groups[2].Value) { $mins += [int]$m.Groups[2].Value }
                        if ($mins -gt 0) { $info.repeatIntervalMinutes = $mins }
                    }
                    break
                }
            }
            return $info
        }
    } catch { }

    # Fallback for images where the ScheduledTasks module is unavailable.
    try {
        $raw = & schtasks.exe /query /tn $taskName /fo LIST /v 2>$null
        if ($LASTEXITCODE -eq 0 -and $raw) {
            $info.present = $true
            $info.source  = 'schtasks'
            foreach ($line in $raw) {
                if ($line -match '^\s*Status:\s*(.+?)\s*$')        { $info.state = $Matches[1] }
                if ($line -match '^\s*Run As User:\s*(.+?)\s*$')   { $info.runAs = $Matches[1] }
                if ($line -match '^\s*Task To Run:\s*(.+?)\s*$')   { $info.action = $Matches[1] }
            }
            # schtasks /v does not print RunLevel, so elevation stays unknown
            # rather than being guessed.
        }
    } catch { }
    return $info
}

function Get-LogSignatureHits {
    param([string]$Path, [string]$Literal, [datetime]$Since)
    # findstr is native and encoding-tolerant - the same reason
    # Search-PixellotLogs.ps1 and Get-SystemIdentity.ps1 use it on these files,
    # which can be multi-megabyte. It does the whole-file scan; PowerShell only
    # parses the handful of matches.
    #
    # Two traps, both found on a real VPU (demo mode hides both):
    #  1. Coordinator's exception text spans several lines, so findstr emits a
    #     BLANK element after each match. Counting raw output double-counts
    #     every hit (9 failures read as 18). Empty lines must be dropped.
    #  2. The log file is named per day but spans restarts, so a unit that was
    #     repaired hours ago still carries the morning's failures. Without a
    #     time window the card stays red all day after a successful fix.
    $out = New-Object System.Collections.ArrayList
    try {
        $raw = @(& findstr.exe /c:$Literal $Path 2>$null)
    } catch {
        return $out
    }
    foreach ($line in $raw) {
        $text = [string]$line
        if ([string]::IsNullOrWhiteSpace($text)) { continue }
        $m = [regex]::Match($text, '\|\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})')
        if ($m.Success) {
            $stamp = [datetime]::MinValue
            if ([datetime]::TryParse($m.Groups[1].Value, [ref]$stamp)) {
                if ($stamp -lt $Since) { continue }
            }
            $null = $out.Add([pscustomobject]@{ time = $m.Groups[1].Value; line = $text.Trim() })
        } else {
            # No parsable timestamp - keep it rather than silently dropping
            # evidence, but it cannot be windowed.
            $null = $out.Add([pscustomobject]@{ time = $null; line = $text.Trim() })
        }
    }
    return $out
}

try {
    if (-not (Test-Path -LiteralPath $coordExe)) {
        [ordered]@{
            verdict = 'not-installed'
            message = "Coordinator.exe not found at $coordExe. Pixellot may not be installed."
            findings = @()
        } | ConvertTo-Json -Depth 6 -Compress
        return
    }

    # --- two PID samples, because one cannot see a restart cycle -------------
    $sampleA = Get-ProcSnapshot
    Start-Sleep -Seconds $SampleSeconds
    $sampleB = Get-ProcSnapshot

    $procs = New-Object System.Collections.ArrayList
    foreach ($n in @('KeepAgentUp', 'Agent', 'Coordinator')) {
        $a = $sampleA[$n]
        $b = $sampleB[$n]
        # Changed PID, or appeared/vanished between samples, means it is being
        # restarted under us.
        $cycling = ($a -ne $b)
        $null = $procs.Add([pscustomobject]@{
            name    = $n
            pidFirst = $a
            pidSecond = $b
            running = ($null -ne $b)
            cycling = $cycling
            owner   = (Get-ProcOwner -ExeName ($n + '.exe'))
        })
    }

    # --- websocket bind evidence from the newest Coordinator log ------------
    $ws = [ordered]@{
        port            = $wsPort
        prefix          = $wsPrefix
        listening       = $false
        bindOk          = 0
        bindFailed      = 0
        fatalNoComms    = 0
        lastError       = $null
        lastErrorTime   = $null
        firstErrorTime  = $null
        lastBindOkTime  = $null
        logFile         = $null
        urlAclPresent   = $false
        urlAclDetail    = $null
    }

    $listen = @(Get-NetTCPConnection -State Listen -LocalPort $wsPort -ErrorAction SilentlyContinue)
    # Present means HTTP.SYS holds the reservation; it is owned by PID 4 either
    # way, so we record only presence, never the owner.
    $ws.listening = ($listen.Count -gt 0)

    if (Test-Path -LiteralPath $logDir) {
        $cutoff = (Get-Date).AddHours(-$HoursBack)
        $coordLog = Get-ChildItem -Path $logDir -Filter 'Coordinator_vpu_*.log' -File -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($coordLog) {
            $ws.logFile = $coordLog.Name
            $failHits = Get-LogSignatureHits -Path $coordLog.FullName -Literal $sigBindFail -Since $cutoff
            $okHits   = Get-LogSignatureHits -Path $coordLog.FullName -Literal $sigBindOk -Since $cutoff
            $comHits  = Get-LogSignatureHits -Path $coordLog.FullName -Literal $sigFatalComms -Since $cutoff

            $ws.bindFailed   = @($failHits).Count
            $ws.bindOk       = @($okHits).Count
            $ws.fatalNoComms = @($comHits).Count

            if ($ws.bindFailed -gt 0) {
                $last = @($failHits)[-1]
                $line = [string]$last.line
                if ($line.Length -gt 300) { $line = $line.Substring(0, 300) }
                $ws.lastError     = $line
                $ws.lastErrorTime = $last.time
                $first = @($failHits)[0]
                $ws.firstErrorTime = $first.time
            }
            if ($ws.bindOk -gt 0) {
                $ws.lastBindOkTime = [string](@($okHits)[-1]).time
            }
        }
    }

    # --- why the token could be wrong ---------------------------------------
    $task = Get-WatchdogTask

    $uacEnabled = $null
    try {
        $uac = Get-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System' -Name 'EnableLUA' -ErrorAction SilentlyContinue
        if ($uac) { $uacEnabled = ([int]$uac.EnableLUA -eq 1) }
    } catch { }

    try {
        $acl = @(& netsh.exe http show urlacl url=$wsPrefix 2>$null)
        $aclText = ($acl -join ' ')
        if ($aclText -match 'Reserved URL') {
            $ws.urlAclPresent = $true
            $ws.urlAclDetail  = ($aclText -replace '\s+', ' ').Trim()
            if ($ws.urlAclDetail.Length -gt 300) { $ws.urlAclDetail = $ws.urlAclDetail.Substring(0, 300) }
        }
    } catch { }

    # --- verdict + findings -------------------------------------------------
    $findings = New-Object System.Collections.ArrayList
    $coordProc = $procs | Where-Object { $_.name -eq 'Coordinator' }
    $verdict = 'ok'

    $bindDenied = ($ws.bindFailed -gt 0 -and $ws.fatalNoComms -gt 0 -and -not $ws.listening)

    if ($bindDenied) {
        $verdict = 'websocket-denied'
        $remedy = 'Start the watchdog TASK, not the executable: schtasks /run /tn KeepAgentUp'
        if (-not $task.present) {
            $remedy = 'The KeepAgentUp task is missing - recreate it with RunLevel Highest, or reboot.'
        }
        $null = $findings.Add([pscustomobject]@{
            severity = 'critical'
            title    = 'Coordinator cannot bind its websocket - the VPU will not come online'
            detail   = ("Coordinator failed to register " + $wsPrefix + " (" + $ws.bindFailed + " failed starts, " + $ws.fatalNoComms + " fatals) and port " + $wsPort + " is not held. This is an access-denied on the HTTP.SYS prefix, which means the process is running without an elevated token. It is not a network fault and not a version fault.")
            remedy   = $remedy
        })
    }
    elseif ($coordProc -and $coordProc.cycling) {
        $verdict = 'cycling'
        $null = $findings.Add([pscustomobject]@{
            severity = 'critical'
            title    = 'Coordinator is restarting in a loop'
            detail   = ("Coordinator's PID changed between two samples " + $SampleSeconds + "s apart (" + $coordProc.pidFirst + " then " + $coordProc.pidSecond + "), so it is being restarted rather than running. A single status check would have reported it healthy.")
            remedy   = 'Check the Coordinator log for the failing startup step before restarting anything.'
        })
    }
    elseif ($coordProc -and -not $coordProc.running) {
        $verdict = 'coordinator-down'
        $null = $findings.Add([pscustomobject]@{
            severity = 'critical'
            title    = 'Coordinator is not running'
            detail   = 'Coordinator was absent from both process samples, so the VPU cannot talk to the cloud.'
            remedy   = 'Start the watchdog task: schtasks /run /tn KeepAgentUp'
        })
    }

    # The watchdog task is the root cause behind all of the above, so it is
    # reported whether or not Coordinator is currently broken.
    if (-not $task.present) {
        if ($verdict -eq 'ok') { $verdict = 'watchdog-task-missing' }
        $null = $findings.Add([pscustomobject]@{
            severity = 'critical'
            title    = 'The KeepAgentUp watchdog task is missing'
            detail   = 'Nothing will restart agent or Coordinator if they stop, and a hand-started watchdog runs without elevation, which breaks Coordinator.'
            remedy   = 'Recreate the scheduled task with RunLevel Highest (a Pixellot reinstall restores it).'
        })
    }
    elseif ($task.state -eq 'Disabled') {
        if ($verdict -eq 'ok') { $verdict = 'watchdog-task-disabled' }
        $null = $findings.Add([pscustomobject]@{
            severity = 'critical'
            title    = 'The KeepAgentUp watchdog task is disabled'
            detail   = 'With the task disabled nothing restarts agent or Coordinator, and starting the watchdog by hand gives Coordinator a non-elevated token that breaks its websocket bind.'
            remedy   = 'Re-enable it: schtasks /change /tn KeepAgentUp /enable'
        })
    }
    elseif ($task.elevated -eq $false) {
        if ($verdict -eq 'ok') { $verdict = 'watchdog-task-not-elevated' }
        $null = $findings.Add([pscustomobject]@{
            severity = 'critical'
            title    = 'The KeepAgentUp watchdog task is not set to run elevated'
            detail   = ("The task runs at RunLevel " + $task.runLevel + " instead of Highest, so agent and Coordinator inherit a non-elevated token and Coordinator cannot register " + $wsPrefix + ". This is the configuration that produces the access-denied websocket failure.")
            remedy   = 'Set the task to run with highest privileges, then run it again.'
        })
    }

    [ordered]@{
        verdict       = $verdict
        watchdogTask  = $task
        processes     = @($procs)
        websocket     = $ws
        uacEnabled    = $uacEnabled
        sampleSeconds = $SampleSeconds
        hoursBack     = $HoursBack
        findings      = @($findings)
        # Deliberately not collected: the token elevation of the RUNNING
        # Coordinator process. There is no reliable PS 5.1 way to read another
        # process's integrity level, so the task's RunLevel is reported as the
        # actionable proxy instead of guessing.
        notes         = 'Port 9001 is always owned by PID 4 (HTTP.SYS); listener ownership is not a health signal.'
    } | ConvertTo-Json -Depth 6 -Compress
}
catch {
    [ordered]@{
        verdict = 'error'
        message = $_.Exception.Message
        script  = 'Get-CoordinatorHealth.ps1'
        findings = @()
    } | ConvertTo-Json -Depth 6 -Compress
}
