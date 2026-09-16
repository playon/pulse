#Requires -Version 5.1
<#
.SYNOPSIS
    Restarts the Pixellot Agent and Coordinator by running the KeepAgentUp
    scheduled task.
.DESCRIPTION
    Per Pixellot Troubleshooting Tips PDF #13, keepagentup.exe is the documented
    "fast remedy before escalating" when agent or coordinator is down.

    It must be started THROUGH ITS SCHEDULED TASK, not by launching the exe.
    The task runs at RunLevel=Highest, and that elevated token is what lets
    Coordinator register its websocket prefix http://+:9001/ - a strong
    wildcard that HTTP.SYS refuses without elevation, since fleet VPUs carry no
    URL ACL for it. Launch the exe from a non-elevated context and agent comes
    up while Coordinator dies every launch with "Access is denied" at
    HttpListener.AddAllPrefixes(), leaving the VPU offline in the cloud but
    looking half-alive. Reproduced on a real 5.37.1 VPU 2026-09-16; Pixellot
    ticket "Fatal Coordinator Errors - PXLS2_6179 Apex (NC) Gym".

    So this script asks the scheduler to start the watchdog and only falls back
    to the executable when no task exists - and refuses even that if Pulse
    itself is not elevated, rather than causing the fault it is meant to fix.

    Two honesty guarantees the previous version did not make:

    1. A resident watchdog makes a second launch exit 0 immediately without
       restarting anything ("KeekAgentUp Exit as another ... process is
       running", Pixellot's typo). That is only good news if agent AND
       coordinator are actually up - so both are checked, before and after.
       Watchdog resident while something it supervises is down is a FAILURE
       with a remedy, not a reassuring note.
    2. Process state is sampled TWICE. A component being restarted in a loop
       shows as "Running" in any single check, which is exactly how the
       Coordinator fault hid in the field.

    ACTION collector: mutates state (starts processes). Outputs JSON to stdout.
#>
[CmdletBinding()]
param(
    [int]$SampleSeconds = 5
)

$ErrorActionPreference = 'Stop'

$keepAgentPath = 'C:\pixellot\bin\keepagentup.exe'
$taskName      = 'KeepAgentUp'

# Agent/coordinator may be installed as Windows services, or run as bare
# processes under the keepagentup watchdog (common on fleet VPUs, where no
# service exists at all). Check both so status doesn't read 'NotFound' on a
# perfectly healthy box.
function Get-PixellotComponentState {
    param([string]$Name)
    $svc = Get-Service -Name $Name -ErrorAction SilentlyContinue
    if ($svc) {
        return [pscustomobject]@{
            status  = "$($svc.Status) (service)"
            procId  = $null
            running = ($svc.Status -eq 'Running')
        }
    }
    $proc = @(Get-Process -Name $Name -ErrorAction SilentlyContinue)
    if ($proc.Count -gt 0) {
        return [pscustomobject]@{
            status  = "Running (process, PID $($proc[0].Id))"
            procId  = $proc[0].Id
            running = $true
        }
    }
    return [pscustomobject]@{
        status  = 'Not running (no service or process)'
        procId  = $null
        running = $false
    }
}

function Get-StackState {
    # Sampled twice by the caller; one sample cannot see a restart loop.
    return [pscustomobject]@{
        agent       = Get-PixellotComponentState -Name 'agent'
        coordinator = Get-PixellotComponentState -Name 'coordinator'
    }
}

function Test-IsElevated {
    try {
        $id = [Security.Principal.WindowsIdentity]::GetCurrent()
        $pr = New-Object Security.Principal.WindowsPrincipal($id)
        return [bool]$pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } catch {
        return $false
    }
}

function Get-WatchdogTaskState {
    $info = [ordered]@{ present = $false; state = $null; runLevel = $null; elevated = $null }
    try {
        $t = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        if ($t) {
            $info.present  = $true
            $info.state    = [string]$t.State
            $info.runLevel = [string]$t.Principal.RunLevel
            $info.elevated = ($info.runLevel -eq 'Highest')
        }
    } catch { }
    return $info
}

try {
    $task       = Get-WatchdogTaskState
    $isElevated = Test-IsElevated
    $before     = Get-StackState

    $method           = $null
    $exitCode         = $null
    $stdoutText       = ''
    $stderrText       = ''
    $watchdogResident = $false
    $blocked          = $false
    $remedy           = $null

    if ($task.present -and $task.state -ne 'Disabled') {
        # Preferred path. The scheduler supplies the elevated token, so this
        # works even when Pulse itself is not elevated.
        $method = 'task'
        $out = & schtasks.exe /run /tn $taskName 2>&1
        $exitCode = $LASTEXITCODE
        $stdoutText = (@($out) -join "`r`n").Trim()
    }
    elseif (-not (Test-Path -LiteralPath $keepAgentPath)) {
        [ordered]@{
            success = $false
            verdict = 'not-installed'
            message = "keepagentup.exe not found at $keepAgentPath and no $taskName task exists. Verify Pixellot is installed."
            path    = $keepAgentPath
        } | ConvertTo-Json -Depth 5 -Compress
        return
    }
    elseif (-not $isElevated) {
        # Refusing is the correct outcome: launching the exe from here would
        # hand Coordinator a non-elevated token and cause the access-denied
        # websocket failure this button exists to clear.
        $blocked = $true
        $method  = 'refused'
        $remedy  = if ($task.state -eq 'Disabled') {
            "Re-enable the watchdog task, then retry: schtasks /change /tn $taskName /enable"
        } else {
            'Restart Pulse as administrator, or run the watchdog task from an elevated prompt.'
        }
    }
    else {
        # Last resort: no usable task, but we are elevated, so the exe
        # inherits an elevated token and Coordinator can still bind.
        $method = 'exe'
        $tmpOut = [System.IO.Path]::GetTempFileName()
        $tmpErr = [System.IO.Path]::GetTempFileName()
        try {
            $proc = Start-Process -FilePath $keepAgentPath `
                -NoNewWindow `
                -PassThru `
                -RedirectStandardOutput $tmpOut `
                -RedirectStandardError $tmpErr `
                -Wait
            $exitCode   = $proc.ExitCode
            $stdoutText = (Get-Content -LiteralPath $tmpOut -Raw -ErrorAction SilentlyContinue) -as [string]
            $stderrText = (Get-Content -LiteralPath $tmpErr -Raw -ErrorAction SilentlyContinue) -as [string]
        }
        finally {
            Remove-Item -LiteralPath $tmpOut -ErrorAction SilentlyContinue
            Remove-Item -LiteralPath $tmpErr -ErrorAction SilentlyContinue
        }
        # keepagentup exits 0 immediately when the resident watchdog instance
        # is already running - nothing was restarted in that case.
        $watchdogResident = ($stdoutText -match '(?i)exit\s+as\s+another\s+.*process\s+is\s+running')
    }

    # Give the watchdog time to bring the stack up, then sample twice so a
    # restart loop cannot masquerade as healthy.
    if (-not $blocked) { Start-Sleep -Seconds 6 }
    $afterA = Get-StackState
    if (-not $blocked) { Start-Sleep -Seconds $SampleSeconds }
    $afterB = Get-StackState

    $agentCycling = ($afterA.agent.procId -ne $afterB.agent.procId)
    $coordCycling = ($afterA.coordinator.procId -ne $afterB.coordinator.procId)
    $agentUp      = $afterB.agent.running
    $coordUp      = $afterB.coordinator.running

    # Pixellot's logger throws a cosmetic AccessViolationException from
    # closeLog() as keepagentup exits. It is not the restart failing, so it is
    # flagged rather than shown as an error.
    $stderrBenign = $false
    if ($stderrText -and $stderrText -match 'AccessViolationException' -and $stderrText -match 'closeLog') {
        $stderrBenign = $true
    }

    # Nothing was actually restarted if both were already up and neither PID
    # moved. Claiming a restart that did not happen is the same dishonesty as
    # the old "watchdog already running" note, just inverted - and the task
    # path never emits the resident marker, so the PIDs are the only reliable
    # evidence. (schtasks reports "is currently running" in that case too.)
    $nothingChanged = $before.agent.running -and $before.coordinator.running -and
        ($before.agent.procId -eq $afterB.agent.procId) -and
        ($before.coordinator.procId -eq $afterB.coordinator.procId)

    $verdict = 'restarted'
    $success = $true
    $message = 'The Agent and Coordinator were restarted and both are running.'

    if ($blocked) {
        $verdict = 'refused-not-elevated'
        $success = $false
        $message = 'Pulse is not running as administrator and there is no usable watchdog task, so it did not start the watchdog. Starting it without administrator rights breaks the Coordinator instead of fixing it.'
    }
    elseif ($agentCycling -or $coordCycling) {
        $verdict = 'cycling'
        $success = $false
        $parts = New-Object System.Collections.ArrayList
        if ($agentCycling) { $null = $parts.Add('Agent') }
        if ($coordCycling) { $null = $parts.Add('Coordinator') }
        $message = ((($parts -join ' and ')) + ' is restarting in a loop rather than staying up. A single status check would have reported it as running.')
        $remedy  = 'Open Service Status and read the Coordinator check, which names the failing startup step.'
    }
    elseif (-not $agentUp -or -not $coordUp) {
        $success = $false
        $down = New-Object System.Collections.ArrayList
        if (-not $agentUp) { $null = $down.Add('Agent') }
        if (-not $coordUp) { $null = $down.Add('Coordinator') }
        $downText = ($down -join ' and ')
        if ($watchdogResident) {
            # The case the old script called a harmless no-op.
            $verdict = 'watchdog-resident-but-down'
            $message = ('The watchdog was already running so nothing was restarted, but ' + $downText + ' is still down. A resident watchdog that is not keeping its processes up is itself the problem.')
            $remedy  = ('Stop the running watchdog and start it through its task instead: schtasks /end /tn ' + $taskName + ' then schtasks /run /tn ' + $taskName)
        } else {
            $verdict = 'still-down'
            $message = ($downText + ' did not come up after the watchdog was started.')
            if (-not $coordUp) {
                $remedy = 'Open Service Status and read the Coordinator check - if it reports an access-denied websocket bind, the watchdog is running without administrator rights.'
            } else {
                $remedy = 'Check the Pixellot logs for the failing startup step.'
            }
        }
    }
    elseif ($watchdogResident -or $nothingChanged) {
        $verdict = 'already-healthy'
        $message = 'The watchdog was already running, so nothing needed restarting. The Agent and Coordinator are both up.'
    }

    if (-not $task.present) {
        $message = $message + ' Note: the KeepAgentUp scheduled task is missing, so nothing will restart these processes automatically.'
        if (-not $remedy) { $remedy = 'Recreate the KeepAgentUp task with RunLevel Highest (a Pixellot reinstall restores it).' }
    }
    elseif ($task.state -eq 'Disabled') {
        $message = $message + ' Note: the KeepAgentUp scheduled task is disabled, so nothing will restart these processes automatically.'
        if (-not $remedy) { $remedy = ('Re-enable it: schtasks /change /tn ' + $taskName + ' /enable') }
    }

    [ordered]@{
        success            = $success
        verdict            = $verdict
        method             = $method
        watchdogTask       = $task
        pulseElevated      = $isElevated
        watchdogResident   = $watchdogResident
        exitCode           = $exitCode
        path               = $keepAgentPath
        stdout             = if ($stdoutText) { $stdoutText.Trim() } else { '' }
        stderr             = if ($stderrText) { $stderrText.Trim() } else { '' }
        stderrBenign       = $stderrBenign
        agentStatus        = $afterB.agent.status
        coordinatorStatus  = $afterB.coordinator.status
        agentStatusBefore  = $before.agent.status
        coordinatorStatusBefore = $before.coordinator.status
        agentPidBefore     = $before.agent.procId
        agentPidAfter      = $afterB.agent.procId
        coordinatorCycling = $coordCycling
        agentCycling       = $agentCycling
        sampleSeconds      = $SampleSeconds
        message            = $message
        remedy             = $remedy
    } | ConvertTo-Json -Depth 5 -Compress
}
catch {
    [ordered]@{
        success = $false
        verdict = 'error'
        message = $_.Exception.Message
        script  = 'Restart-PixellotAgent.ps1'
    } | ConvertTo-Json -Depth 5 -Compress
}
