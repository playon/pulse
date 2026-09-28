#Requires -Version 5.1
<#
.SYNOPSIS
    Reads the Pixellot logs from recent events to say, per event, whether the
    graphics (scorebug) ever reached the broadcast.
.DESCRIPTION
    Pulse's other graphics coverage is network reachability to singular.live,
    so a unit can air a whole game with no scorebug and pass every check.
    This collector reads the on-box evidence instead. Field cases behind it:
    Tanque Verde AZ (2026-09-14), Thomas MacLaren CO (2026-09-23), Merrol
    Hyde (2026-08-17), Armstrong IL (2026-09-28), all 5.37.x.

    1. GraphicsManager_*.log - GraphicsManager hands the graphics client URL
       to VPU.exe over localhost gRPC (sendGrpcMsgToVpu):
         Successfully sent graphics client URL to VPU eventId=<id> url=...
         Failed to send graphics client to VPU attempt=N error=rpc error:
             code = DeadlineExceeded ... eventId=<id> ... url=...
       The bug is proven by ABSENCE: sustained failures and zero successes
       for an event (MacLaren 127/127 failed across two restarts; healthy
       control 413 successes). One DeadlineExceeded per event is normal (CEF
       takes ~6s against a 5s deadline) and Unavailable / connection refused
       on 61011 is GraphicsManager retrying before VPU.exe is up. The whole
       path is localhost, so no venue firewall can cause it.
    2. VPU_*.log - "VPUScoreboardImpl::SendGraphicsInfo ... eventid=<id>" is
       VPU.exe receiving that URL. Zero on every broken bundle, 414 on the
       healthy control. Per-event cross-check.
    3. agent_*.log - the agent disables graphics for an event when no
       scoreboard engine is selected (Merrol Hyde):
         enableGraphics is False as agentSetup/GENERAL/GraphicsEnabled is
             True scoreboardType is NONE_SELECTED ...
       repeating every ~15s. "enableGraphics is false as it is test event" is
       the daily test and is not counted.
    4. Scoreboard data never arriving (sportzcastdatareceiver):
         No scoreboard data is being received
         Problem detected: No valid scoreboard data
       Counted for context only.

    Pixellot zips each day's logs into archive\ around 03:00: GraphicsManager
    goes to log_vpu_*_others.zip, VPU and agent logs to log_vpu_*.zip, and an
    entry can land a day or two late. Live files and zip entries are merged
    by name (largest copy wins), newest first, inside a time budget.
    Benign and NOT reported: "Failed to read score provider backup file ...
    scoreProvider.txt" (every healthy boot) and "Recieved graphics engine
    type from CG: []" (healthy control too).

    Read-only. Outputs JSON to stdout. Timestamps: GraphicsManager logs UTC
    ("...z"), VPU and agent logs local time; both are emitted as logged.
#>
[CmdletBinding()]
param(
    [string]$LogDir = 'C:\Pixellot\Data\Log',
    [string]$ConfigDir = 'C:\Pixellot\Data\Configuration',
    [int]$DaysBack = 7,
    [int]$BudgetSeconds = 25,
    [int]$MaxEvents = 20
)

$ErrorActionPreference = 'Stop'

# Read a whole log without locking out the writer.
function Read-SharedText([string]$path, [long]$maxBytes) {
    $fs = New-Object System.IO.FileStream($path, [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read, [System.IO.FileShare]'ReadWrite, Delete')
    try {
        if ($fs.Length -gt $maxBytes) { $null = $fs.Seek(-$maxBytes, [System.IO.SeekOrigin]::End) }
        $sr = New-Object System.IO.StreamReader($fs)
        try { return $sr.ReadToEnd() } finally { $sr.Dispose() }
    } finally { $fs.Dispose() }
}

function Read-ZipEntryText([string]$zipPath, [string]$entryName) {
    $zip = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
    try {
        $entry = $zip.GetEntry($entryName)
        if ($null -eq $entry) { return '' }
        $sr = New-Object System.IO.StreamReader($entry.Open())
        try { return $sr.ReadToEnd() } finally { $sr.Dispose() }
    } finally { $zip.Dispose() }
}

# yyyyMMdd from names like GraphicsManager_vpu2_20260925_000057.log
function Get-NameDate([string]$name) {
    if ($name -match '_(\d{8})_\d{6}\.log$') {
        $d = [datetime]::MinValue
        if ([datetime]::TryParseExact($Matches[1], 'yyyyMMdd', $null,
                [System.Globalization.DateTimeStyles]::None, [ref]$d)) { return $d }
    }
    return $null
}

function Get-CfgValue([string]$path, [string]$key) {
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    foreach ($line in @(Get-Content -LiteralPath $path -ErrorAction SilentlyContinue)) {
        # "Key, type, value    //comment". Strip a comment only after
        # whitespace: graphics.cfg stores URLs as http:////host.
        if ($line -match ('^\s*' + [regex]::Escape($key) + '\s*,\s*\w+\s*,\s*(.*)$')) {
            $v = ($Matches[1] -replace '\s+//.*$', '').Trim()
            return $v
        }
    }
    return $null
}

try {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $config = [pscustomobject]@{
        graphicEngineType  = Get-CfgValue (Join-Path $ConfigDir 'agentsetup.cfg') 'GraphicEngineType'
        graphicsEnabled    = Get-CfgValue (Join-Path $ConfigDir 'agentsetup.cfg') 'GraphicsEnabled'
        graphicsModeOnInit = Get-CfgValue (Join-Path $ConfigDir 'graphics.cfg') 'GRAPHICS_MODE_ON_INIT'
    }

    if (-not (Test-Path -LiteralPath $LogDir)) {
        [pscustomobject]@{
            logsFound = $false; logDir = $LogDir; daysBack = $DaysBack; config = $config
        } | ConvertTo-Json -Compress -Depth 5
        return
    }

    $zipOk = $true
    try { Add-Type -AssemblyName System.IO.Compression.FileSystem } catch { $zipOk = $false }

    $cutoff = (Get-Date).Date.AddDays(-$DaysBack)
    $maxLiveBytes = 64MB
    $maxEntryBytes = 200MB

    # Candidate sources by entry name; the largest copy of a name wins.
    $cands = @{}
    function Add-Cand($kind, $name, $length, $zipPath) {
        $d = Get-NameDate $name
        if ($null -eq $d -or $d -lt $cutoff) { return }
        if ($length -gt $maxEntryBytes) { return }
        $prev = $cands[$name]
        if ($null -eq $prev -or $length -gt $prev.length) {
            $cands[$name] = [pscustomobject]@{
                kind = $kind; name = $name; length = [long]$length; zip = $zipPath; date = $d
            }
        }
    }
    function Get-Kind([string]$name) {
        if ($name -like 'GraphicsManager_*') { return 'gm' }
        if ($name -like 'VPU_*') { return 'vpu' }
        if ($name -like 'agent_*') { return 'agent' }
        return $null
    }

    foreach ($f in @(Get-ChildItem -LiteralPath $LogDir -File -ErrorAction SilentlyContinue)) {
        $k = Get-Kind $f.Name
        if ($k) { Add-Cand $k $f.Name $f.Length $null }
    }
    $archive = Join-Path $LogDir 'archive'
    if ($zipOk -and (Test-Path -LiteralPath $archive)) {
        $zipCutoff = $cutoff.AddDays(-1)
        foreach ($z in @(Get-ChildItem -LiteralPath $archive -Filter 'log_*.zip' -File -ErrorAction SilentlyContinue)) {
            if ($z.LastWriteTime -lt $zipCutoff) { continue }
            try {
                $zip = [System.IO.Compression.ZipFile]::OpenRead($z.FullName)
                try {
                    foreach ($e in $zip.Entries) {
                        $k = Get-Kind $e.Name
                        if ($k) { Add-Cand $k $e.Name $e.Length $z.FullName }
                    }
                } finally { $zip.Dispose() }
            } catch { }
        }
    }

    # Newest first: if the budget runs out, the oldest days are what's lost.
    # The per-event verdicts need GraphicsManager logs; read those before the
    # (much larger) VPU and agent logs.
    $order = @{ gm = 0; vpu = 1; agent = 2 }
    $sources = @($cands.Values | Sort-Object @{ Expression = { $order[$_.kind] } }, @{ Expression = { $_.date }; Descending = $true })

    $events = @{}
    function Get-Event([string]$id) {
        $ev = $events[$id]
        if ($null -eq $ev) {
            $ev = [pscustomobject]@{
                eventId = $id; firstSeen = $null; lastSeen = $null; delivered = 0
                deadlineFails = 0; unavailableFails = 0; otherFails = 0
                maxAttempt = 0; vpuReceived = 0
            }
            $events[$id] = $ev
        }
        return $ev
    }
    function Touch($ev, $ts) {
        if (-not $ts) { return }
        if (-not $ev.firstSeen -or $ts -lt $ev.firstSeen) { $ev.firstSeen = $ts }
        if (-not $ev.lastSeen -or $ts -gt $ev.lastSeen) { $ev.lastSeen = $ts }
    }

    # Ordinal substring search finds the few interesting lines; the regexes
    # only ever run on those. A line-anchored regex over a 15 MB agent log
    # blew the whole budget on VPU2.
    function Find-Lines([string]$text, [string]$needle) {
        $out = New-Object 'System.Collections.Generic.List[string]'
        $i = 0
        while ($i -lt $text.Length) {
            $i = $text.IndexOf($needle, $i, [System.StringComparison]::Ordinal)
            if ($i -lt 0) { break }
            $st = $text.LastIndexOf([char]10, $i) + 1
            $en = $text.IndexOf([char]10, $i)
            if ($en -lt 0) { $en = $text.Length }
            $out.Add($text.Substring($st, $en - $st))
            $i = $en
        }
        # Unrolled on purpose: callers pipe the lines.
        return $out.ToArray()
    }

    $tsRx = '(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})'
    $idRx = '(?:.*?[Ee]vent[Ii][Dd]=([0-9a-fA-F]{8,}))?'
    $rxOk = New-Object regex ($tsRx + '.*?Successfully sent graphics client URL to VPU' + $idRx)
    $rxFail = New-Object regex ($tsRx + '.*?Failed to send graphics client to VPU attempt=(\d+).*?code = (\w+)' + $idRx)
    $rxVpu = New-Object regex ('SendGraphicsInfo.*?[Ee]vent[Ii][Dd]=([0-9a-fA-F]{8,})')
    $rxNone = New-Object regex ($tsRx + '.*?enableGraphics is False as .*?scoreboardType is NONE_SELECTED'), 'IgnoreCase'
    $rxSet = New-Object regex ($tsRx + '.*?Got Comm\w* SetScoreboardType (\w+)')
    $rxNoData = New-Object regex ($tsRx + '.*?(No scoreboard data is being received|Problem detected: No valid scoreboard data)')

    $scanned = @{ gm = 0; vpu = 0; agent = 0 }
    $truncated = $false
    $noneLines = 0; $noneFirst = $null; $noneLast = $null
    $setLast = $null; $setValue = $null
    $noDataLines = 0; $invalidDataLines = 0; $noDataLast = $null
    $readErrors = 0

    foreach ($src in $sources) {
        if ($sw.Elapsed.TotalSeconds -gt $BudgetSeconds) { $truncated = $true; break }
        $text = ''
        try {
            if ($src.zip) { $text = Read-ZipEntryText $src.zip $src.name }
            else { $text = Read-SharedText (Join-Path $LogDir $src.name) $maxLiveBytes }
        } catch { $readErrors++; continue }
        $scanned[$src.kind]++

        if ($src.kind -eq 'gm') {
            $gl = @(Find-Lines $text 'graphics client')
            foreach ($m in @($gl | ForEach-Object { $rxOk.Match($_) } | Where-Object { $_.Success })) {
                $id = $m.Groups[2].Value; if (-not $id) { $id = 'unknown' }
                $ev = Get-Event $id.ToLower()
                $ev.delivered++
                Touch $ev $m.Groups[1].Value
            }
            foreach ($m in @($gl | ForEach-Object { $rxFail.Match($_) } | Where-Object { $_.Success })) {
                $id = $m.Groups[4].Value; if (-not $id) { $id = 'unknown' }
                $ev = Get-Event $id.ToLower()
                $code = $m.Groups[3].Value
                if ($code -eq 'DeadlineExceeded') { $ev.deadlineFails++ }
                elseif ($code -eq 'Unavailable') { $ev.unavailableFails++ }
                else { $ev.otherFails++ }
                $att = 0
                if ([int]::TryParse($m.Groups[2].Value, [ref]$att) -and $att -gt $ev.maxAttempt) { $ev.maxAttempt = $att }
                Touch $ev $m.Groups[1].Value
            }
            $dl = @(Find-Lines $text 'No scoreboard data is being received') + @(Find-Lines $text 'No valid scoreboard data')
            foreach ($m in @($dl | ForEach-Object { $rxNoData.Match($_) } | Where-Object { $_.Success })) {
                if ($m.Groups[2].Value -like 'Problem detected*') { $invalidDataLines++ } else { $noDataLines++ }
                $t = $m.Groups[1].Value
                if (-not $noDataLast -or $t -gt $noDataLast) { $noDataLast = $t }
            }
        }
        elseif ($src.kind -eq 'vpu') {
            foreach ($m in @(@(Find-Lines $text 'SendGraphicsInfo') | ForEach-Object { $rxVpu.Match($_) } | Where-Object { $_.Success })) {
                $ev = $events[$m.Groups[1].Value.ToLower()]
                # Only events GraphicsManager knows about; a VPU-only id
                # has no hand-off to judge.
                if ($null -ne $ev) { $ev.vpuReceived++ }
            }
        }
        else {
            foreach ($m in @(@(Find-Lines $text 'NONE_SELECTED') | ForEach-Object { $rxNone.Match($_) } | Where-Object { $_.Success })) {
                $noneLines++
                $t = $m.Groups[1].Value
                if (-not $noneFirst -or $t -lt $noneFirst) { $noneFirst = $t }
                if (-not $noneLast -or $t -gt $noneLast) { $noneLast = $t }
            }
            foreach ($m in @(@(Find-Lines $text 'SetScoreboardType') | ForEach-Object { $rxSet.Match($_) } | Where-Object { $_.Success })) {
                $t = $m.Groups[1].Value
                if (-not $setLast -or $t -gt $setLast) { $setLast = $t; $setValue = $m.Groups[2].Value }
            }
        }
        $text = $null
    }

    $evList = @($events.Values | Sort-Object @{ Expression = { $_.lastSeen }; Descending = $true } | Select-Object -First $MaxEvents)

    [pscustomobject]@{
        logsFound        = [bool]($sources.Count -gt 0)
        logDir           = $LogDir
        daysBack         = $DaysBack
        zipSupport       = $zipOk
        truncated        = $truncated
        readErrors       = $readErrors
        elapsedMs        = [int]$sw.ElapsedMilliseconds
        filesScanned     = [pscustomobject]@{ graphicsManager = $scanned['gm']; vpu = $scanned['vpu']; agent = $scanned['agent'] }
        config           = $config
        events           = $evList
        engineDisabled   = [pscustomobject]@{
            lines = $noneLines; first = $noneFirst; last = $noneLast
            lastSetScoreboardType = $setValue; lastSetAt = $setLast
        }
        scoreboardData   = [pscustomobject]@{
            noDataLines = $noDataLines; invalidDataLines = $invalidDataLines; last = $noDataLast
        }
    } | ConvertTo-Json -Compress -Depth 5
}
catch {
    [pscustomobject]@{
        error   = $true
        message = $_.Exception.Message
        script  = 'Get-GraphicsDelivery.ps1'
    } | ConvertTo-Json -Compress
}
