#Requires -Version 5.1
# Bench test (not shipped): does ScoreConnect III survive a WebSocket client
# that goes away without the close handshake? 1.4.1.1 died on exactly that
# (vpu-home 2026-09-29: .NET 1026 WebSocketException "remote party closed the
# WebSocket connection without completing the close handshake", System 7034).
# Sportzcast 1.4.2.2: "Fix SCIII crash on stale WebSocket disconnects".
#
# Each round opens ws://127.0.0.1:5000/ (what SC III's own pages use), lets
# SC III push to it, drops it without a close frame, then waits for SC III's
# next push to the dead client. A crash shows as a new service PID plus a
# System 7034/7031 event. ASCII only.
# The 2026-09-29 stack trace (vpu-6493, 1.4.1.1) puts the crash in SC III's
# own server: WebSocketsMiddleWare.SendToAllInsteadOfId writing to a client
# whose response had completed (ObjectDisposedException in Kestrel's
# HttpUpgradeStream), on a thread-pool task nothing catches. A single
# dropped client is removed cleanly (all four single rounds survive on
# 1.4.1.1), so the crash is a race: a client dropping while SC III is
# pushing to it. -Storm drops many clients at random moments to hit it.
param([int]$WaitSec = 25, [switch]$Storm, [int]$Batches = 20, [int]$PerBatch = 25)

$ErrorActionPreference = 'Stop'
$t0 = Get-Date

function Get-Sc3Pid { (Get-CimInstance Win32_Service -Filter "Name='ScoreConnectIII'").ProcessId }

function Open-RawWs {
    $c = New-Object Net.Sockets.TcpClient
    $c.Connect('127.0.0.1', 5000)
    $s = $c.GetStream()
    $key = [Convert]::ToBase64String((1..16 | ForEach-Object { [byte](Get-Random -Max 256) }))
    $req = "GET / HTTP/1.1`r`nHost: 127.0.0.1:5000`r`nUpgrade: websocket`r`nConnection: Upgrade`r`nSec-WebSocket-Key: $key`r`nSec-WebSocket-Version: 13`r`n`r`n"
    $b = [Text.Encoding]::ASCII.GetBytes($req)
    $s.Write($b, 0, $b.Length)
    $buf = New-Object byte[] 4096
    $s.ReadTimeout = 5000
    $n = $s.Read($buf, 0, $buf.Length)
    $head = [Text.Encoding]::ASCII.GetString($buf, 0, $n).Split("`r")[0]
    return @{ client = $c; stream = $s; status = $head }
}

$rounds = @(
    @{ name = 'ClientWebSocket.Abort (no close frame, socket torn down)'; kind = 'abort' },
    @{ name = 'ClientWebSocket.Dispose without CloseAsync'; kind = 'dispose' },
    @{ name = 'raw socket, RST (linger 0)'; kind = 'rst' },
    @{ name = 'raw socket, TCP FIN with no WebSocket close frame'; kind = 'fin' }
)

$out = New-Object System.Collections.Generic.List[string]
$startPid = Get-Sc3Pid
if ($Storm) {
    $out.Add("storm: SC III pid $startPid, version " + ((Get-Item 'C:\Program Files (x86)\Sportzcast LLC\ScoreConnectIII\ScoreConnectIII.exe').VersionInfo.FileVersion -replace '\.', '-'))
    $dropped = 0
    $crashedAt = $null
    for ($b = 1; $b -le $Batches; $b++) {
        $socks = New-Object System.Collections.Generic.List[object]
        for ($i = 0; $i -lt $PerBatch; $i++) {
            try {
                $ws = New-Object Net.WebSockets.ClientWebSocket
                $null = $ws.ConnectAsync([Uri]'ws://127.0.0.1:5000/', [Threading.CancellationToken]::None).Wait(3000)
                $socks.Add($ws)
            } catch {}
        }
        foreach ($ws in $socks) {
            Start-Sleep -Milliseconds (Get-Random -Minimum 0 -Maximum 120)
            try { if ((Get-Random -Maximum 2) -eq 0) { $ws.Abort() } else { $ws.Dispose() } } catch {}
            $dropped++
        }
        Start-Sleep -Seconds 2
        if ((Get-Sc3Pid) -ne $startPid) { $crashedAt = $b; break }
    }
    Start-Sleep -Seconds 8
    $endPid = Get-Sc3Pid
    if ($crashedAt) { $out.Add("CRASHED in batch $crashedAt after $dropped dropped clients (pid $startPid -> $endPid)") }
    else { $out.Add("survived $dropped dropped clients in $Batches batches (pid still $endPid)") }
    $ev = Get-WinEvent -FilterHashtable @{ LogName = 'System'; Id = 7031, 7034; StartTime = $t0 } -ErrorAction SilentlyContinue | Where-Object { $_.Message -like '*ScoreConnect*' }
    $out.Add('System 7031/7034 for SC III during test: ' + @($ev).Count)
    $net = Get-WinEvent -FilterHashtable @{ LogName = 'Application'; Id = 1026; StartTime = $t0 } -ErrorAction SilentlyContinue | Where-Object { $_.Message -like '*ScoreConnect*' }
    foreach ($e in @($net)) { $m = ($e.Message -replace '\s+', ' '); $out.Add('.NET 1026: ' + $m.Substring(0, [Math]::Min(400, $m.Length))) }
    $alive = $false
    try { $alive = ((Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 'http://127.0.0.1:5000/api/configuration/get-status').StatusCode -eq 200) } catch {}
    $out.Add('SC III answering at the end: ' + $alive)
    $out -join "`n"
    exit 0
}
$out.Add("start: SC III pid $startPid, version " + ((Get-Item 'C:\Program Files (x86)\Sportzcast LLC\ScoreConnectIII\ScoreConnectIII.exe').VersionInfo.FileVersion -replace '\.', '-'))

foreach ($r in $rounds) {
    $before = Get-Sc3Pid
    $note = ''
    try {
        if ($r.kind -eq 'abort' -or $r.kind -eq 'dispose') {
            $ws = New-Object Net.WebSockets.ClientWebSocket
            $null = $ws.ConnectAsync([Uri]'ws://127.0.0.1:5000/', [Threading.CancellationToken]::None).Wait(5000)
            $note = 'state ' + $ws.State
            Start-Sleep -Seconds 3   # let SC III push at least once
            if ($r.kind -eq 'abort') { $ws.Abort() } else { $ws.Dispose() }
        } else {
            $w = Open-RawWs
            $note = $w.status
            Start-Sleep -Seconds 3
            if ($r.kind -eq 'rst') { $w.client.Client.LingerState = New-Object Net.Sockets.LingerOption($true, 0) }
            $w.client.Close()
        }
    } catch {
        $note = 'client error: ' + $_.Exception.Message
    }
    Start-Sleep -Seconds $WaitSec
    $after = Get-Sc3Pid
    $alive = $false
    try { $alive = ((Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 'http://127.0.0.1:5000/api/configuration/get-status').StatusCode -eq 200) } catch {}
    $verdict = if ($after -ne $before) { 'CRASHED (pid ' + $before + ' -> ' + $after + ')' } elseif (-not $alive) { 'NOT ANSWERING' } else { 'survived' }
    $out.Add(('{0}: {1} [{2}]' -f $r.name, $verdict, $note))
}

$ev = Get-WinEvent -FilterHashtable @{ LogName = 'System'; Id = 7031, 7034; StartTime = $t0 } -ErrorAction SilentlyContinue |
    Where-Object { $_.Message -like '*ScoreConnect*' }
$out.Add('System 7031/7034 for SC III during test: ' + @($ev).Count)
$net = Get-WinEvent -FilterHashtable @{ LogName = 'Application'; Id = 1026; StartTime = $t0 } -ErrorAction SilentlyContinue |
    Where-Object { $_.Message -like '*ScoreConnect*' }
foreach ($e in @($net)) {
    $m = ($e.Message -replace '\s+', ' ')
    $out.Add('.NET 1026: ' + $m.Substring(0, [Math]::Min(260, $m.Length)))
}
$out.Add("end: SC III pid " + (Get-Sc3Pid))
$out -join "`n"
