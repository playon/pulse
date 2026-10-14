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

    The setting lives on the service registration, and Sportzcast's installer
    deletes and re-creates the service (vpu-6493 2026-10-05: installing 1.4.2.2
    logged System 7045 and left no FailureActions). So this also registers a
    scheduled task, "Pulse ScoreConnect Guard", that puts the setting back
    without Pulse running:
      - System 7045 for ServiceName ScoreConnectIII (installed or updated),
        after 30s;
      - at boot, after 2 minutes;
      - System 7034 for ScoreConnectIII, after 10s. Windows logs 7034 only
        when a crashed service had NO restart action (with one it logs 7031),
        so this fires exactly when Windows itself will not restart it.
    Each run reapplies the restart actions and starts the service (a start
    on a running service is a harmless error, 1056). The task runs Windows'
    own sc.exe through cmd.exe, so it does not depend on Pulse's files.

    Measured on vpu-6493 2026-10-05 (task history on), silent reinstall of
    1.4.2.2: 7045 at +17s, the guard ran at +29s and the restart actions were
    back that second; without the guard they stayed off (the installer never
    restores them). One 7045 started the task twice, 20s apart (the two event
    triggers' delays): Task Scheduler matches an event against all of a
    task's event triggers. The second run changes nothing.

    ASCII ONLY (CLAUDE.md PowerShell 5.1 rules). Unwanted returns go to $null.
#>
[CmdletBinding()]
param(
    [string]$ServiceName = 'ScoreConnectIII'
)

$ErrorActionPreference = 'Stop'

$out = [ordered]@{
    success        = $false
    configured     = $false
    guardInstalled = $false
    guardError     = $null
    message        = $null
}

$GuardTaskName = 'Pulse ScoreConnect Guard'
# Task Scheduler 1.2 schema. Subscription and Arguments are XML text, so the
# event queries' angle brackets and cmd's & are escaped.
$GuardTaskXml = @'
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Author>Pulse</Author>
    <Description>Keeps ScoreConnect III's crash auto-restart on. Sportzcast's installer re-creates the service without it; this puts it back after an install, at boot, and starts ScoreConnect III after a crash Windows did not restart.</Description>
  </RegistrationInfo>
  <Triggers>
    <EventTrigger>
      <Enabled>true</Enabled>
      <Delay>PT30S</Delay>
      <Subscription>&lt;QueryList&gt;&lt;Query Id="0" Path="System"&gt;&lt;Select Path="System"&gt;*[System[Provider[@Name='Service Control Manager'] and (EventID=7045)]] and *[EventData[Data[@Name='ServiceName']='ScoreConnectIII']]&lt;/Select&gt;&lt;/Query&gt;&lt;/QueryList&gt;</Subscription>
    </EventTrigger>
    <BootTrigger>
      <Enabled>true</Enabled>
      <Delay>PT2M</Delay>
    </BootTrigger>
    <EventTrigger>
      <Enabled>true</Enabled>
      <Delay>PT10S</Delay>
      <Subscription>&lt;QueryList&gt;&lt;Query Id="0" Path="System"&gt;&lt;Select Path="System"&gt;*[System[Provider[@Name='Service Control Manager'] and (EventID=7034)]] and *[EventData[Data[@Name='param1']='ScoreConnectIII']]&lt;/Select&gt;&lt;/Query&gt;&lt;/QueryList&gt;</Subscription>
    </EventTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>S-1-5-18</UserId>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>Queue</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <ExecutionTimeLimit>PT2M</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>cmd.exe</Command>
      <Arguments>/c sc.exe failure ScoreConnectIII reset= 86400 actions= restart/5000/restart/5000/restart/30000 &amp; sc.exe start ScoreConnectIII</Arguments>
    </Exec>
  </Actions>
</Task>
'@

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

    # The guard task. Registered every run (Force replaces an older copy),
    # then read back: three enabled triggers or it does not count.
    try {
        $null = Register-ScheduledTask -TaskName $GuardTaskName -Xml $GuardTaskXml -Force
        $t = Get-ScheduledTask -TaskName $GuardTaskName -ErrorAction Stop
        $on = @($t.Triggers | Where-Object { $_.Enabled })
        $out.guardInstalled = ($t.State -ne 'Disabled' -and $on.Count -eq 3)
        if (-not $out.guardInstalled) { $out.guardError = "The task registered but reads back as " + $t.State + " with " + $on.Count + " of 3 triggers on." }
    } catch {
        $out.guardError = $_.Exception.Message
    }

    $out.success = $out.configured
    if ($out.configured -and $out.guardInstalled) {
        $out.message = "Crash auto-restart is on: Windows restarts ScoreConnect III 5 seconds after a crash, and it stays on after ScoreConnect updates."
    } elseif ($out.configured) {
        $out.message = "Crash auto-restart is on, but a ScoreConnect update will turn it off again: the keep-on task could not be set up (" + $out.guardError + ")."
    } else {
        $out.message = "sc.exe reported success, but no restart action reads back from the registry."
    }
}
catch {
    $out.message = "Could not turn on crash auto-restart: $($_.Exception.Message)"
}

$out | ConvertTo-Json -Compress
