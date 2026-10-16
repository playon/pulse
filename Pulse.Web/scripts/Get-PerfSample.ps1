#Requires -Version 5.1
<#
.SYNOPSIS
    Samples CPU and memory over a few seconds and returns the averages.
.DESCRIPTION
    The Stream Readiness Engine needs SUSTAINED CPU/memory, not a one-instant
    snapshot -- a momentary spike at the moment of a dashboard fetch must not
    move the PASS/WARN/FAIL verdict. Get-Counter samples the processor and
    available-memory counters once per second for a short window and we average
    the cooked values.

    CPU  : \Processor(_Total)\% Processor Time  (averaged across samples)
    Memory: physical used% derived from \Memory\Available MBytes vs the host's
            total physical RAM (matches the dashboard's physical-memory view,
            not commit charge).

    Post-event VOD: after a game Pixellot cuts and uploads the recording with
    ffmpeg.exe and PostProcess.exe, which can hold the CPU near 100% for a
    while (Perry, 2026-10-15: ffmpeg 86%, PostProcess 8%). That is expected
    work, not a fault, so the same window measures those processes' share of
    the whole host's CPU (their CPU time across the window / (window x logical
    cores)). The readiness engine subtracts it before judging F17, unless
    VPU.exe is running: then a game is live and the load is a real risk.

    Outputs JSON to stdout: { cpuAvgPercent, memAvgPercent, sampleCount,
    windowSeconds, postProcess: { processes, cpuPercent, vpuRunning } }. postProcess.cpuPercent
    is null when the processes' CPU time can't be read. Errors fail soft with
    an {error:true} envelope -- the readiness engine then falls back to the
    single Get-Performance snapshot.
#>
[CmdletBinding()]
param(
    [int]$Samples = 3,        # number of 1-second samples to average
    [int]$IntervalSeconds = 1
)

$ErrorActionPreference = 'Stop'

# Pixellot's post-event VOD tools (process names, no .exe).
$PostProcessNames = @('ffmpeg', 'PostProcess')

# Processor seconds per PID, or $null for a process whose CPU time is unreadable.
function Get-PostProcessCpu {
    $out = @{}
    foreach ($p in @(Get-Process -Name $PostProcessNames -ErrorAction SilentlyContinue)) {
        $sec = $null
        try { $sec = $p.TotalProcessorTime.TotalSeconds } catch { }
        $out[$p.Id] = [ordered]@{ name = "$($p.ProcessName).exe"; cpu = $sec }
    }
    $out
}

try {
    $totalPhysMB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1MB)

    $before = Get-PostProcessCpu
    $clock = [System.Diagnostics.Stopwatch]::StartNew()
    $counter = Get-Counter -Counter '\Processor(_Total)\% Processor Time', '\Memory\Available MBytes' `
        -SampleInterval $IntervalSeconds -MaxSamples $Samples -ErrorAction Stop
    $elapsed = $clock.Elapsed.TotalSeconds
    $after = Get-PostProcessCpu

    $cpuVals = @()
    $memVals = @()
    foreach ($set in $counter) {
        foreach ($s in $set.CounterSamples) {
            if ($s.Path -like '*% processor time*') {
                $cpuVals += [double]$s.CookedValue
            }
            elseif ($s.Path -like '*available mbytes*') {
                if ($totalPhysMB -gt 0) {
                    $usedPct = (($totalPhysMB - [double]$s.CookedValue) / $totalPhysMB) * 100
                    $memVals += $usedPct
                }
            }
        }
    }

    $cpuAvg = if ($cpuVals.Count) { [math]::Round((($cpuVals | Measure-Object -Average).Average), 1) } else { $null }
    $memAvg = if ($memVals.Count) { [math]::Round((($memVals | Measure-Object -Average).Average), 1) } else { $null }

    # A process that started inside the window spent all its CPU time in it;
    # one that exited is gone from $after and counts nothing.
    $names = @()
    $postSec = 0.0
    $readable = $true
    foreach ($id in $after.Keys) {
        $a = $after[$id]
        if ($names -notcontains $a.name) { $names += $a.name }
        if ($null -eq $a.cpu) { $readable = $false; continue }
        $b = if ($before.ContainsKey($id)) { $before[$id].cpu } else { 0.0 }
        if ($null -eq $b) { $readable = $false; continue }
        $postSec += [math]::Max(0.0, $a.cpu - $b)
    }
    $cores = [Environment]::ProcessorCount
    $postPct = if ($readable -and $elapsed -gt 0 -and $cores -gt 0) {
        [math]::Round([math]::Min(100.0, $postSec / ($elapsed * $cores) * 100), 1)
    } else { $null }

    [ordered]@{
        cpuAvgPercent = $cpuAvg
        memAvgPercent = $memAvg
        sampleCount   = $cpuVals.Count
        windowSeconds = $Samples * $IntervalSeconds
        postProcess   = [ordered]@{
            processes  = @($names | Sort-Object)
            cpuPercent = if ($names.Count) { $postPct } else { 0.0 }
            vpuRunning = [bool](Get-Process -Name VPU -ErrorAction SilentlyContinue)
        }
    } | ConvertTo-Json -Compress
}
catch {
    [ordered]@{
        error   = $true
        message = $_.Exception.Message
        script  = 'Get-PerfSample.ps1'
    } | ConvertTo-Json -Compress
}
