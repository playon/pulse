#Requires -Version 5.1
<#
.SYNOPSIS
    Reads VPU.exe's own log for what the live stream actually did: which
    streaming server it dialed, every failed connection attempt, every
    failover step, and the moment it connected.
.DESCRIPTION
    Test-NetworkPorts.ps1 proves the venue passes UDP 2088 / UDP 443 / TCP
    1935 to Pixellot's echo server (prod-echo.pixellot.tv). The live stream
    goes somewhere else: a broadcaster assigned per event from AWS pools
    (pxltd-<ip>.pixellot.stream). A filter that allows by destination, or a
    dead broadcaster, passes every port test while the stream fails. This is
    the ground truth for that gap. Field origin: Red Lodge (MT), 2026-09-26 -
    readiness read PASS while VPU.exe logged "Failed connecting to
    zixi://34.222.54.117:2088/0_hd_2000 ... return value: -11".

    Line shapes (VPU.exe 5.27-5.37, Windows and gen-3 alike; tab-separated
    "Level | yyyy-MM-dd HH:mm:ss.fff |Module |File(line) |Function |Message"):
      urlToStreamWriter for urls zixi://...:2088/0_hd_2000|zixi://...:443/...|rtmp://...
          the failover chain for a stream, in order. Logged on a fresh start
          AND when VPU.exe restarts mid-event (the "Sucssesfully added stream
          url" line is not repeated on a restart).
      Failed connecting to zixi://<host>:<port>/0_hd_2000, because ... return value: -2
      onStreamDisconnect: <url> failed, move to <url>
          the feeder giving up on one rung (4 attempts, ~60 s) and taking the next
      Created Zixi stream: HD_Writer0_Stream0          connected (Zixi)
      Video Connection rtmp://... Created Successfuly  connected (RTMP)
      START NEW LOG SESSION >>> VPU.exe - Version: x   VPU.exe (re)started
      CloseUnit ... Reason: "stopStreaming event command"   event ended

    Emits the matching lines as ordered events; main.py does the analysis.
    Read-only. Outputs JSON to stdout.
.PARAMETER LogDir
    Pixellot log folder. VPU.exe writes VPU_<host>_<yyyyMMdd>_<HHmmss>.log,
    a new file each time it starts.
.PARAMETER HoursBack
    Ignore files and lines older than this.
.PARAMETER MaxFiles
    Newest N VPU logs inside the window.
.PARAMETER MaxEvents
    Keep the newest N events. A stream that never connects logs ~4 lines a
    minute, so 600 covers the last ~2.5 hours of a dead event.
#>
[CmdletBinding()]
param(
    [string]$LogDir = 'C:\Pixellot\Data\Log',
    [int]$HoursBack = 24,
    [int]$MaxFiles = 3,
    [int]$MaxEvents = 600
)

$ErrorActionPreference = 'Stop'
$inv = [System.Globalization.CultureInfo]::InvariantCulture

# "yyyy-MM-dd HH:mm:ss[.fff]" (VPU.exe local time) -> DateTime (Local kind),
# or $null. Local kind so ToString('zzz') carries the UTC offset.
function Get-LineTime([string]$line) {
    $m = [regex]::Match($line, '(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})(?:\.(\d{1,3}))?')
    if (-not $m.Success) { return $null }
    $ms = '000'
    if ($m.Groups[3].Success) { $ms = $m.Groups[3].Value.PadRight(3, '0') }
    $dt = [datetime]::MinValue
    $ok = [datetime]::TryParseExact(
        ($m.Groups[1].Value + ' ' + $m.Groups[2].Value + '.' + $ms),
        'yyyy-MM-dd HH:mm:ss.fff', $inv,
        [System.Globalization.DateTimeStyles]::AssumeLocal, [ref]$dt)
    if (-not $ok) { return $null }
    return $dt
}

function Format-Time([datetime]$dt) {
    return $dt.ToString('yyyy-MM-ddTHH:mm:ss.fffzzz', $inv)
}

try {
    $now = Get-Date
    $base = [ordered]@{
        logDir    = $LogDir
        hoursBack = $HoursBack
        now       = (Format-Time $now)
    }

    if (-not (Test-Path -LiteralPath $LogDir)) {
        $base.logsFound = $false
        $base.filesScanned = 0
        $base.events = @()
        $base | ConvertTo-Json -Depth 5 -Compress
        return
    }

    $cutoff = $now.AddHours(-$HoursBack)
    # Oldest first, so events come out in time order.
    $files = @(Get-ChildItem -LiteralPath $LogDir -Filter 'VPU_*.log' -File -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -ge $cutoff } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First $MaxFiles |
        Sort-Object LastWriteTime)

    # Literal needles, one pass per file. findstr.exe is native and fast (a
    # full-day VPU log reaches 180+ MB) and reads the file VPU.exe is still
    # writing - the same approach Search-PixellotLogs.ps1 uses on these logs.
    # /I avoids findstr's known miss with several case-sensitive literals of
    # different lengths. Select-String is the fallback off-Windows (local
    # parse testing against field bundles).
    $needles = @(
        'urlToStreamWriter for urls',
        'Failed connecting to',
        'failed, move to',
        'Created Zixi stream',
        'Created Successfuly',
        'START NEW LOG SESSION',
        'CloseUnit'
    )
    $findstr = Get-Command 'findstr.exe' -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1

    $events = New-Object System.Collections.Generic.List[object]
    $lastChain = $null
    $names = New-Object System.Collections.Generic.List[string]

    foreach ($f in $files) {
        $names.Add($f.Name)
        $lines = @()
        if ($findstr) {
            $fsArgs = @('/I') + @($needles | ForEach-Object { '/C:' + $_ }) + @($f.FullName)
            $lines = @(& $findstr.Source $fsArgs 2>$null)
        }
        else {
            $lines = @(Select-String -LiteralPath $f.FullName -SimpleMatch -Pattern $needles |
                ForEach-Object { $_.Line })
        }

        foreach ($line in $lines) {
            if (-not $line) { continue }
            $dt = Get-LineTime $line
            if ($null -eq $dt -or $dt -lt $cutoff) { continue }
            $t = Format-Time $dt
            $ev = $null

            if ($line -match 'START NEW LOG SESSION') {
                $ver = $null
                if ($line -match 'Version: ([0-9.]+)') { $ver = $Matches[1] }
                $ev = [ordered]@{ t = $t; kind = 'session'; version = $ver; file = $f.Name }
            }
            elseif ($line -match 'urlToStreamWriter for urls (\S+)') {
                $list = $Matches[1]
                # Recording writers (local .mkv paths) share this line; only
                # the network chain matters here.
                if ($list -notmatch '(zixi|rtmp)://') { continue }
                $ev = [ordered]@{ t = $t; kind = 'chain'; urls = $list.Split('|') }
                $lastChain = $ev
            }
            elseif ($line -match 'Failed connecting to (\S+?), because') {
                $url = $Matches[1]
                $rv = $null
                if ($line -match 'return value: (-?\d+)') { $rv = [int]$Matches[1] }
                $ev = [ordered]@{ t = $t; kind = 'fail'; url = $url; returnValue = $rv }
            }
            elseif ($line -match 'onStreamDisconnect: (\S+) failed, move to (\S+)') {
                $ev = [ordered]@{ t = $t; kind = 'move'; from = $Matches[1]; to = $Matches[2] }
            }
            elseif ($line -match 'Created Zixi stream: (\S+)') {
                $ev = [ordered]@{ t = $t; kind = 'zixiOk'; name = $Matches[1] }
            }
            elseif ($line -match 'Video Connection (rtmp://\S+) Created Successfuly') {
                $ev = [ordered]@{ t = $t; kind = 'rtmpOk'; url = $Matches[1] }
            }
            elseif ($line -match 'CloseUnit') {
                $reason = $null
                if ($line -match 'Reason: "([^"]*)"') { $reason = $Matches[1] }
                $ev = [ordered]@{ t = $t; kind = 'close'; reason = $reason }
            }

            if ($ev) { $events.Add($ev) }
        }
    }

    $total = $events.Count
    $kept = $events.ToArray()
    if ($total -gt $MaxEvents) {
        $kept = $events.GetRange($total - $MaxEvents, $MaxEvents).ToArray()
    }

    $base.logsFound = [bool]($files.Count -gt 0)
    $base.filesScanned = $files.Count
    $base.files = $names.ToArray()
    $base.eventCount = $total
    $base.truncated = [bool]($total -gt $MaxEvents)
    # The newest chain survives truncation: without it, a long dead stream
    # would lose the one line that names its streaming server.
    $base.lastChain = $lastChain
    $base.events = $kept
    $base | ConvertTo-Json -Depth 5 -Compress
}
catch {
    [ordered]@{
        error   = $true
        message = $_.Exception.Message
        script  = 'Get-VpuStreamLog.ps1'
    } | ConvertTo-Json -Compress
}
