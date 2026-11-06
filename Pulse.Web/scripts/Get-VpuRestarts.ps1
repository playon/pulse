#Requires -Version 5.1
<#
.SYNOPSIS
    Reads the Pixellot VPU log for VPU.exe sessions in the recent window so
    Pulse can tell a crash-looping VPU.exe from a healthy one.
.DESCRIPTION
    A crash-looping VPU.exe still shows as "Running" in a process snapshot:
    the agent restarts it every 15-60 seconds, so there is almost always a
    fresh copy alive. The VPU log is the only place the loop is visible -
    every start writes "START NEW LOG SESSION", a clean exit writes
    "Goodbye!!!", and a crash writes a Fatal line or nothing at all.

    Field origin: Tecumseh (MI), 2026-09-28. NVIDIA driver 446.14 made every
    VPU.exe die on its first frame (cudaErrorInvalidPtx); 21 starts in 2.5
    hours, Head Setup never loaded, Pulse said Game-ready.

    Only marker lines are read (findstr, or Select-String off Windows), and
    only from VPU_*.log files written inside the window. Classification of
    WHY the sessions died happens in main.py (_vpu_restart_findings), so this
    script just reports per-session facts.

    Timestamps in the log are VPU local time; ages are computed here against
    the local clock so the backend never has to guess a time zone.
    Outputs JSON to stdout.
.PARAMETER WindowMinutes
    How far back to report sessions. Default 120.
.PARAMETER AsOf
    Evaluate as if the local time were this value (yyyy-MM-dd HH:mm:ss).
    For replaying a captured log off-box; skips the live process check.
#>
[CmdletBinding()]
param(
    [string]$LogDir = 'C:\Pixellot\Data\Log',
    [int]$WindowMinutes = 120,
    [int]$MaxSessions = 60,
    [string]$AsOf = ''
)

$ErrorActionPreference = 'Stop'

$inv = [System.Globalization.CultureInfo]::InvariantCulture
$needleFile = $null

function _Ts([string]$line) {
    # "2026-09-28 08:17:10" or "2026-09-28 08:17:10.643"; some Pixellot
    # tools space-pad the hour ("2026-09-25  0:10:00").
    if ($line -match '(\d{4}-\d{2}-\d{2}) +(\d{1,2}):(\d{2}):(\d{2})') {
        $s = '{0} {1}:{2}:{3}' -f $Matches[1], ([int]$Matches[2]).ToString('00'), $Matches[3], $Matches[4]
        $d = [datetime]::MinValue
        if ([datetime]::TryParseExact($s, 'yyyy-MM-dd HH:mm:ss', $inv,
                [System.Globalization.DateTimeStyles]::None, [ref]$d)) { return $d }
    }
    return $null
}

try {
    $now = Get-Date
    $replay = $false
    if ($AsOf) {
        $now = [datetime]::ParseExact($AsOf, 'yyyy-MM-dd HH:mm:ss', $inv)
        $replay = $true
    }
    $cutoff = $now.AddMinutes(-$WindowMinutes)

    # Live process: VPU.exe is not always running (the agent closes it
    # outside events), so absence alone is not a fault.
    $vpuRunning = $false
    $vpuStartedMinutesAgo = $null
    if (-not $replay) {
        $proc = Get-Process -Name 'VPU' -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($proc) {
            $vpuRunning = $true
            try { $vpuStartedMinutesAgo = [math]::Round(($now - $proc.StartTime).TotalMinutes, 1) } catch { }
        }
    }

    if (-not (Test-Path -LiteralPath $LogDir)) {
        [ordered]@{
            logsFound            = $false
            logDir               = $LogDir
            windowMinutes        = $WindowMinutes
            vpuRunning           = $vpuRunning
            vpuStartedMinutesAgo = $vpuStartedMinutesAgo
            sessions             = @()
        } | ConvertTo-Json -Compress
        return
    }

    # A file last written before the window can't hold a session that
    # started inside it. When replaying, take every file - the capture's
    # mtimes are the copy time, not the log time.
    $allLogs = @(Get-ChildItem -LiteralPath $LogDir -Filter 'VPU_*.log' -File)
    $files = @($allLogs | Where-Object { $replay -or $_.LastWriteTime -ge $cutoff } | Sort-Object Name)

    $needles = @(
        'START NEW LOG SESSION', 'END LOG SESSION', 'Goodbye!!!',
        'Installed NVIDIA driver', 'Received first frame',
        'CloseUnit Command from Agent', 'Fatal',
        'no new debayer thread entries', 'Found camera data path problem',
        'Camera reset happened'
    )

    # Pre-filter with findstr: a VPU day log reaches 250+ MB during events
    # and Select-String takes 30 s+ on one that size; findstr takes about a
    # second. Needles go in a /G: file (no argument quoting to get wrong),
    # and /I is required - case-sensitive findstr with several literal
    # strings of different lengths silently misses matches. The exact-case
    # checks below do the real classification.
    $findstr = Get-Command findstr.exe -ErrorAction SilentlyContinue
    if ($findstr) {
        $needleFile = [System.IO.Path]::GetTempFileName()
        [System.IO.File]::WriteAllLines($needleFile, [string[]]$needles)
    }

    $all = New-Object System.Collections.Generic.List[object]
    $cur = $null
    foreach ($f in $files) {
        if ($findstr) {
            $lines = @(& $findstr.Source /I /L "/G:$needleFile" $f.FullName 2>$null)
            if ($LASTEXITCODE -gt 1) { throw "Unable to read VPU log: $($f.FullName) (findstr exit $LASTEXITCODE)" }
        } else {
            $lines = @(Select-String -LiteralPath $f.FullName -SimpleMatch -Pattern $needles | ForEach-Object { $_.Line })
        }
        foreach ($line in $lines) {
            if ($null -eq $line) { continue }
            if ($line.Contains('START NEW LOG SESSION')) {
                if ($cur) { $cur.ended = $true }
                $v = $null
                if ($line -match 'Version: ([\w.\-]+)') { $v = $Matches[1] }
                $cur = @{
                    startTime  = (_Ts $line)
                    version    = $v
                    driver     = $null
                    firstFrame = $false
                    goodbye    = $false
                    ended      = $false
                    fatal      = $null
                    fatalCount = 0
                    closeReason = $null
                    tags       = New-Object System.Collections.Generic.List[string]
                }
                $null = $all.Add($cur)
                continue
            }
            if (-not $cur) { continue }
            if ($line.Contains('END LOG SESSION')) { $cur.ended = $true }
            elseif ($line.Contains('Goodbye!!!')) { $cur.goodbye = $true }
            elseif ($line.Contains('Installed NVIDIA driver')) {
                $cur.driver = ($line -split ':')[-1].Trim()
            }
            elseif ($line.Contains('Received first frame')) { $cur.firstFrame = $true }
            elseif ($line.Contains('CloseUnit Command from Agent')) {
                if ($line -match 'Reason: "?([^"]+)') { $cur.closeReason = $Matches[1].Trim() }
            }
            elseif ($line.StartsWith('Fatal')) {
                $cur.fatalCount++
                if (-not $cur.fatal) {
                    $msg = $line
                    if ($msg.Length -gt 400) { $msg = $msg.Substring(0, 400) }
                    $cur.fatal = $msg.Trim()
                }
            }
            elseif ($line.Contains('no new debayer thread entries')) {
                if (-not $cur.tags.Contains('debayer-stall')) { $null = $cur.tags.Add('debayer-stall') }
            }
            elseif ($line.Contains('Found camera data path problem')) {
                if (-not $cur.tags.Contains('camera-datapath')) { $null = $cur.tags.Add('camera-datapath') }
            }
            elseif ($line.Contains('Camera reset happened')) {
                if (-not $cur.tags.Contains('camera-reset')) { $null = $cur.tags.Add('camera-reset') }
            }
        }
    }

    # The newest session is still open only if VPU.exe is running now;
    # otherwise it died without writing an end marker.
    if ($cur -and -not $cur.ended -and -not $vpuRunning -and -not $replay) { $cur.ended = $true }

    $inWindow = New-Object System.Collections.Generic.List[object]
    foreach ($s in $all) {
        if ($null -eq $s.startTime -or $s.startTime -lt $cutoff -or $s.startTime -gt $now) { continue }
        $null = $inWindow.Add([pscustomobject]@{
            start             = $s.startTime.ToString('yyyy-MM-ddTHH:mm:ss')
            startedMinutesAgo = [math]::Round(($now - $s.startTime).TotalMinutes, 1)
            version           = $s.version
            driver            = $s.driver
            firstFrame        = $s.firstFrame
            goodbye           = $s.goodbye
            ended             = $s.ended
            fatal             = $s.fatal
            fatalCount        = $s.fatalCount
            closeReason       = $s.closeReason
            tags              = $s.tags.ToArray()
        })
    }
    $total = $inWindow.Count
    $out = $inWindow.ToArray()
    if ($out.Count -gt $MaxSessions) { $out = $out[($out.Count - $MaxSessions)..($out.Count - 1)] }

    [ordered]@{
        logsFound            = [bool]($allLogs.Count -gt 0)
        logDir               = $LogDir
        filesScanned         = $files.Count
        windowMinutes        = $WindowMinutes
        vpuRunning           = $vpuRunning
        vpuStartedMinutesAgo = $vpuStartedMinutesAgo
        sessionsInWindow     = $total
        sessions             = @($out)
    } | ConvertTo-Json -Depth 5 -Compress
}
catch {
    [ordered]@{
        error   = $true
        message = $_.Exception.Message
        script  = 'Get-VpuRestarts.ps1'
    } | ConvertTo-Json -Compress
}
finally {
    if ($needleFile) { Remove-Item -LiteralPath $needleFile -ErrorAction SilentlyContinue }
}
