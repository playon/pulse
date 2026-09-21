#Requires -Version 5.1
<#
.SYNOPSIS
    Runs a short network capture using pktmon and returns a summary of findings.
.DESCRIPTION
    Uses Windows built-in pktmon to capture packet headers for a specified duration,
    then analyzes the capture for retransmissions, resets, and connection issues.
    No third-party drivers or installs required. Outputs JSON to stdout.
.NOTES
    Requires Windows 10 1809+ (pktmon is present on the fleet image, build 17763)
    and elevated privileges. Only packet headers are logged -- no payload inspection.

    GROUND TRUTH (measured on a real VPU, Win10 1809 build 17763, PS 5.1):

    'pktmon start' has NO packet-count option on this build. The short form -c
    IS --capture, so passing a number after it fails the whole command with
    exit 87 / "Unknown parameter". Volume is bounded with --file-size instead.

    'pktmon counters' prints a per-component table with comma-grouped numbers
    and no drop column; --json gives the same data structured, which is what we
    read. Every component in a group reports the same packets (Upper/Lower at
    each NDIS edge), so only the physical NIC component -- the one whose Name
    equals the group Name -- is summed. Drop counters appear as Type 'Drops'.

    'pktmon etl2txt' writes tcpdump-style detail lines, NOT the "TCP ... dst:"
    text an earlier version of this script looked for. A packet is two lines:

      [00]0000.0000::<ts> [Microsoft-Windows-PktMon] PktGroupId 5, PktNumber 1,
        Appearance 1, Direction Rx , Type Ethernet , Component 13, Edge 1, ...
      <TAB>AA-..-B6 > 9C-..-D5, ethertype IPv4 (0x0800), length 66:
        52.1.53.61.443 > 192.168.101.120.65077: Flags [S.], seq 1747935550,
        ack 3660231009, win 16060, options [...], length 0

    So: the port is dot-separated (52.1.53.61.443), flags are tcpdump letters
    ([S]=SYN, [S.]=SYN-ACK, [R]=RST, [F.]=FIN-ACK), and the strings "TCP",
    "RST", "SYN", "FIN" and "retransmit" never appear anywhere in the file.
    Each packet is also logged 5-10 times, once per component/edge it crosses,
    tagged Appearance 1..N -- so only Appearance 1 is counted.

    RELIABILITY, also measured. The two data sources are not equally good:

      * 'pktmon counters' was correct on every run. Packet and drop totals
        come from there and can be trusted.

      * The ETL decode is intermittent on this build. Repeated identical
        captures produced ~16000 events, ~170 events, and on one run nothing
        at all. Retransmissions, resets and top talkers all come from the
        decode, so the script reports how many packets it actually inspected
        and refuses to emit a 'pass' finding when that number is zero. A green
        tick over six unmeasured zeros is worse than an empty card.

      * An outbound SYN is never logged here. Across every combination of
        filter count and log size tried, pure '[S]' packets came back as zero
        while '[S.]' and '[F.]' were present, so a SYN count would read 0 on a
        healthy VPU. tcpSyns/tcpFins stay in the payload for tier-2 reading
        but drive no verdict and are not shown as headline stats.
#>
[CmdletBinding()]
param(
    [int]$DurationSec = 30,
    # Upper bound on packets parsed out of the ETL, to keep a busy VPU's
    # capture from turning into a long text scan. Counters are unaffected.
    [int]$MaxPackets = 20000
)

$ErrorActionPreference = 'Stop'

# Clamp duration: 10-60 seconds
$DurationSec = [math]::Max(10, [math]::Min($DurationSec, 60))

# MEASURED, do not "tidy" this number. On build 17763, --file-size 16 starts
# cleanly (exit 0) and reports "No events lost" on stop, but the resulting ETL
# decodes to 2 events -- the trace headers and no packets at all. Verified
# repeatable on a warm driver, so it is the size value and not a cold-start
# artifact. 4, 8 and the 512 MB default all decode correctly; 8 was verified
# both as the first capture after 'pktmon unload' and on a warm driver.
# The log is preallocated, so this costs ~32 MB in TEMP until cleanup.
$LogSizeMb = 8

function Invoke-Pktmon {
    <#
        Runs pktmon and returns @{ Output = <string>; ExitCode = <int> }.

        Native stderr must NOT be merged into the success stream here. With
        $ErrorActionPreference = 'Stop' in force, '& pktmon ... 2>&1' turns any
        stderr chatter into a terminating NativeCommandError -- which is how the
        ETL decode silently reported zero packets even on a good capture.
        pktmon signals real failures through its exit code, so that is what we
        read. Errors are reported, never thrown.
    #>
    param([Parameter(Mandatory = $true)][string[]]$PktmonArgs)

    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out = (& pktmon @PktmonArgs 2>&1 | Out-String)
        return @{ Output = $out; ExitCode = $LASTEXITCODE }
    }
    catch {
        return @{ Output = $_.Exception.Message; ExitCode = -1 }
    }
    finally {
        $ErrorActionPreference = $prev
    }
}

function Get-PktmonNicTotals {
    <#
        Sums the physical NIC component's counters out of 'pktmon counters --json'.
        Returns a hashtable with Packets and Drops. Every other component in a
        group re-reports the same packets, so summing them all inflates the
        totals roughly tenfold.
    #>
    param([string]$Json)

    $totals = @{ Packets = 0; Drops = 0 }
    if (-not $Json) { return $totals }

    $parsed = $null
    try { $parsed = $Json | ConvertFrom-Json }
    catch { return $totals }
    if (-not $parsed) { return $totals }

    foreach ($group in @($parsed)) {
        if (-not $group.Components) { continue }
        foreach ($comp in @($group.Components)) {
            # The physical adapter repeats the group name; the LWF/protocol
            # components below it do not.
            if ($comp.Name -ne $group.Group) { continue }
            foreach ($counter in @($comp.Counters)) {
                $isDrop = ($counter.Type -and $counter.Type -match 'Drop')
                foreach ($dir in @($counter.Inbound, $counter.Outbound)) {
                    if (-not $dir) { continue }
                    $pkts = 0
                    if ($dir.Packets) { $pkts = [int]$dir.Packets }
                    if ($isDrop) { $totals.Drops += $pkts }
                    else { $totals.Packets += $pkts }
                }
            }
        }
    }
    return $totals
}

try {
    # -- Check pktmon availability --------------------------------
    $pktmonPath = Get-Command pktmon -ErrorAction SilentlyContinue
    if (-not $pktmonPath) {
        [ordered]@{
            error = $true
            message = 'pktmon not available. Requires Windows 10 1809 or later.'
            script = 'Start-NetworkCapture.ps1'
        } | ConvertTo-Json -Compress
        return
    }

    # -- Check for admin elevation (pktmon requires it) -----------
    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $isAdmin) {
        [ordered]@{
            error = $true
            message = 'Packet capture requires administrator privileges. Run Pulse as administrator.'
            script = 'Start-NetworkCapture.ps1'
        } | ConvertTo-Json -Compress
        return
    }

    # -- Local addresses, so "the remote end" is unambiguous ------
    $localIps = @{}
    try {
        foreach ($a in (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop)) {
            $localIps[$a.IPAddress] = $true
        }
    }
    catch {
        # Older/locked-down boxes: fall back to direction tags only.
    }

    # -- Clean up any prior state ---------------------------------
    $null = Invoke-Pktmon @('stop')
    $null = Invoke-Pktmon @('filter', 'remove')

    # -- Add filters: streaming ports -----------------------------
    # 'pktmon filter add <name> -t <proto> -p <port>' is correct on 1809.
    $filterSpecs = @(
        @('filter', 'add', 'PulseTCP',  '-t', 'TCP', '-p', '443'),
        @('filter', 'add', 'PulseRTMP', '-t', 'TCP', '-p', '1935'),
        @('filter', 'add', 'PulseHTTP', '-t', 'TCP', '-p', '80'),
        @('filter', 'add', 'PulseZixi', '-t', 'UDP', '-p', '2088')
    )
    foreach ($spec in $filterSpecs) {
        $fr = Invoke-Pktmon $spec
        if ($fr.ExitCode -ne 0) {
            $null = Invoke-Pktmon @('filter', 'remove')
            [ordered]@{
                error = $true
                message = "Failed to add pktmon filter $($spec[2]) (exit $($fr.ExitCode)). $((($fr.Output) -replace '\s+', ' ').Trim())"
                script = 'Start-NetworkCapture.ps1'
            } | ConvertTo-Json -Compress
            return
        }
    }

    # -- Start capture (ETL file, headers only) -------------------
    $etlPath = Join-Path $env:TEMP "pulse_capture.etl"
    $txtPath = Join-Path $env:TEMP "pulse_capture.txt"
    foreach ($stale in @($etlPath, $txtPath)) {
        if (Test-Path $stale) { Remove-Item $stale -Force -ErrorAction SilentlyContinue }
    }

    # No packet-count flag exists on this build; --file-size bounds the volume.
    # pktmon reports parameter errors through its EXIT CODE, not an exception --
    # a bad flag returns 87 and PowerShell sails straight past it. Without this
    # check the script slept for the full duration and then reported a
    # confident all-zero capture.
    $startFailure = $null
    $startRes = Invoke-Pktmon @('start', '--capture', '--pkt-size', '128',
                               '--file-name', $etlPath, '--file-size', "$LogSizeMb")
    if ($startRes.ExitCode -ne 0) {
        $detail = (($startRes.Output) -replace '\s+', ' ').Trim()
        $startFailure = "pktmon start failed (exit $($startRes.ExitCode)). $detail"
    }

    if ($startFailure) {
        $null = Invoke-Pktmon @('filter', 'remove')
        [ordered]@{
            error = $true
            message = $startFailure
            script = 'Start-NetworkCapture.ps1'
        } | ConvertTo-Json -Compress
        return
    }

    # Confirm the driver really is collecting before we sleep for a minute.
    $statusRes = Invoke-Pktmon @('status')
    if ($statusRes.Output -match 'not running') {
        $null = Invoke-Pktmon @('stop')
        $null = Invoke-Pktmon @('filter', 'remove')
        [ordered]@{
            error = $true
            message = 'pktmon accepted the start command but is not collecting. Check that no other capture tool holds the pktmon driver.'
            script = 'Start-NetworkCapture.ps1'
        } | ConvertTo-Json -Compress
        return
    }

    # -- Wait for capture duration --------------------------------
    Start-Sleep -Seconds $DurationSec

    # -- Read counters BEFORE stopping ----------------------------
    # 'pktmon stop' tears the session down; counters have to be read while it
    # is still live.
    $counterRes = Invoke-Pktmon @('counters', '--json')
    $nicTotals = Get-PktmonNicTotals -Json $counterRes.Output

    # -- Stop capture and drop filters ----------------------------
    $null = Invoke-Pktmon @('stop')
    $null = Invoke-Pktmon @('filter', 'remove')

    $totalPackets   = [int]$nicTotals.Packets
    $droppedPackets = [int]$nicTotals.Drops

    # -- Convert ETL to text for per-packet analysis --------------
    $tcpResets      = 0
    $tcpSyns        = 0
    $tcpSynAcks     = 0
    $tcpFins        = 0
    $tcpRetransmits = 0
    $parsedPackets  = 0
    $etl2txtFailed  = $false

    $remoteCounts = @{}
    $seenSegments = @{}

    try {
        $convRes = Invoke-Pktmon @('etl2txt', $etlPath, '-o', $txtPath)
        if ($convRes.ExitCode -ne 0) { $etl2txtFailed = $true }

        if (-not $etl2txtFailed -and (Test-Path $txtPath)) {
            $direction = $null
            $counting  = $false

            # ReadLines streams the file instead of loading a multi-hundred-MB
            # text dump into memory the way Get-Content would.
            foreach ($line in [System.IO.File]::ReadLines($txtPath)) {

                # Metadata line: pick up the direction, and count each physical
                # packet exactly once by only accepting its first appearance.
                if ($line -match 'PktGroupId\s+\d+,\s+PktNumber\s+\d+,\s+Appearance\s+(\d+),\s+Direction\s+(\w+)') {
                    $counting  = ([int]$Matches[1] -eq 1)
                    $direction = $Matches[2]
                    continue
                }

                if (-not $counting) { continue }

                # Detail line: "<src>.<sport> > <dst>.<dport>: Flags [S.], seq N, ... length N"
                if ($line -notmatch '(\d{1,3}(?:\.\d{1,3}){3})\.(\d+)\s+>\s+(\d{1,3}(?:\.\d{1,3}){3})\.(\d+):') {
                    continue
                }
                $srcIp   = $Matches[1]
                $srcPort = $Matches[2]
                $dstIp   = $Matches[3]
                $dstPort = $Matches[4]

                $parsedPackets++
                $counting = $false   # one detail line per packet
                if ($parsedPackets -ge $MaxPackets) { break }

                # tcpdump flag letters, not the words SYN/RST/FIN.
                $flags = ''
                if ($line -match 'Flags\s+\[([^\]]*)\]') { $flags = $Matches[1] }
                $hasAck = $flags.Contains('.')
                if ($flags.Contains('R')) { $tcpResets++ }
                if ($flags.Contains('F')) { $tcpFins++ }
                if ($flags.Contains('S')) {
                    if ($hasAck) { $tcpSynAcks++ } else { $tcpSyns++ }
                }

                # Retransmit heuristic. pktmon marks nothing as a retransmit, so
                # a repeat of the same (flow, seq, length) segment is the signal.
                # Pure ACKs legitimately reuse a seq number, so only segments
                # that carry data or open/close a connection are keyed.
                $payloadLen = -1
                $lenMatches = [regex]::Matches($line, 'length\s+(\d+)')
                if ($lenMatches.Count -gt 0) {
                    $payloadLen = [int]$lenMatches[$lenMatches.Count - 1].Groups[1].Value
                }
                $isInteresting = ($payloadLen -gt 0) -or $flags.Contains('S') -or $flags.Contains('F')
                if ($isInteresting -and $line -match 'seq\s+(\d+)') {
                    $segKey = "$srcIp`:$srcPort>$dstIp`:$dstPort|$($Matches[1])|$payloadLen|$flags"
                    if ($seenSegments.ContainsKey($segKey)) { $tcpRetransmits++ }
                    else { $seenSegments[$segKey] = $true }
                }

                # Remote endpoint: whichever side is not one of ours. Direction
                # is the fallback when Get-NetIPAddress was unavailable.
                $remoteIp   = $null
                $remotePort = $null
                if ($localIps.Count -gt 0) {
                    if ($localIps.ContainsKey($srcIp) -and -not $localIps.ContainsKey($dstIp)) {
                        $remoteIp = $dstIp; $remotePort = $dstPort
                    }
                    elseif ($localIps.ContainsKey($dstIp) -and -not $localIps.ContainsKey($srcIp)) {
                        $remoteIp = $srcIp; $remotePort = $srcPort
                    }
                }
                if (-not $remoteIp) {
                    if ($direction -eq 'Tx') { $remoteIp = $dstIp; $remotePort = $dstPort }
                    else { $remoteIp = $srcIp; $remotePort = $srcPort }
                }

                $remoteKey = "$remoteIp|$remotePort"
                if ($remoteCounts.ContainsKey($remoteKey)) { $remoteCounts[$remoteKey]++ }
                else { $remoteCounts[$remoteKey] = 1 }
            }
        }
        else {
            $etl2txtFailed = $true
        }
    }
    catch {
        $etl2txtFailed = $true
    }

    # The NIC counters see everything; the ETL parse can lag behind on a very
    # busy box. Report the larger of the two so the headline is never below
    # what we actually inspected.
    if ($parsedPackets -gt $totalPackets) { $totalPackets = $parsedPackets }

    # -- Build top talkers list -----------------------------------
    # Rule 4: never Sort-Object a hashtable. Project to pscustomobject first --
    # 5.1 cannot resolve hashtable keys as properties and the sort collapses.
    $talkerRows = @()
    foreach ($key in $remoteCounts.Keys) {
        $parts = $key -split '\|'
        $talkerRows += [pscustomobject]@{
            RemoteAddr = $parts[0]
            RemotePort = [int]$parts[1]
            Packets    = [int]$remoteCounts[$key]
        }
    }

    $topTalkers = @()
    foreach ($row in @($talkerRows | Sort-Object -Property Packets -Descending | Select-Object -First 10)) {
        $hostname = $null
        try {
            $ar = [System.Net.Dns]::BeginGetHostEntry($row.RemoteAddr, $null, $null)
            if ($ar.AsyncWaitHandle.WaitOne(300)) {
                $entry = [System.Net.Dns]::EndGetHostEntry($ar)
                if ($entry.HostName -ne $row.RemoteAddr) { $hostname = $entry.HostName }
            }
        }
        catch { }

        $topTalkers += [ordered]@{
            remoteAddr = $row.RemoteAddr
            remotePort = $row.RemotePort
            remoteHost = $hostname
            packets    = $row.Packets
        }
    }

    # -- Classify findings ----------------------------------------
    $findings = @()

    # A capture that saw nothing is not a clean bill of health. Say so, rather
    # than printing six zeros next to a green tick.
    if ($totalPackets -eq 0) {
        $findings += [ordered]@{
            severity = 'info'
            title    = 'No streaming traffic seen'
            body     = "Nothing crossed ports 443, 1935, 80 or UDP 2088 during the ${DurationSec}s capture. That is expected on an idle VPU -- run this again while an event is streaming to judge the connection."
        }
    }

    # The NIC counters and the ETL are independent sources. When the counters
    # saw traffic but the decode yielded no packets, the flag/reset/talker
    # numbers below are all structurally zero rather than measured -- say that
    # instead of letting the run fall through to "No issues detected".
    $detailMissing = ($totalPackets -gt 0 -and $parsedPackets -eq 0)
    if ($detailMissing) {
        $findings += [ordered]@{
            severity = 'info'
            title    = 'Per-packet detail unavailable'
            body     = "The network counters saw $totalPackets packets, but the capture file could not be decoded, so resets and retransmissions were not measured on this run."
        }
    }

    if ($tcpRetransmits -gt 10) {
        $findings += [ordered]@{
            severity = 'warning'
            title    = "$tcpRetransmits TCP retransmission(s) detected"
            body     = "Retransmissions mean packet loss on the network path. Check for congestion, firewall interference, or a bad cable."
        }
    }
    elseif ($tcpRetransmits -gt 0) {
        $findings += [ordered]@{
            severity = 'info'
            title    = "$tcpRetransmits TCP retransmission(s) detected"
            body     = "Minor retransmissions. These only matter if they are sustained."
        }
    }

    if ($tcpResets -gt 5) {
        $findings += [ordered]@{
            severity = 'warning'
            title    = "$tcpResets TCP reset(s) seen"
            body     = "Connections are being forcefully terminated. Common causes: a content filter resetting blocked domains, a server rejecting connections, or idle connection timeouts."
        }
    }

    if ($droppedPackets -gt 0) {
        $findings += [ordered]@{
            severity = 'critical'
            title    = "$droppedPackets packet(s) dropped by the network stack"
            body     = "Packets were dropped before reaching the application. Look at NIC buffer overflow, the network driver, or a security filter blocking traffic."
        }
    }

    # Only claim a clean result when enough packets were actually inspected. A
    # pass badge over numbers that were never measured is worse than no card.
    #
    # How much gets decoded varies a lot run to run and is NOT proportional to
    # traffic: measured on a real VPU, a quiet 12s run decoded 2367 of 2491
    # packets, while a loaded 15s run decoded 22 of 7905. So a thin sample is
    # reported as what it is -- not enough to judge -- rather than dressed up
    # with a cause this script cannot observe.
    if ($findings.Count -eq 0 -and $parsedPackets -gt 0) {
        $inspectedEnough = ($totalPackets -le 0) -or ($parsedPackets -ge ($totalPackets * 0.5))
        if ($inspectedEnough) {
            $findings += [ordered]@{
                severity = 'pass'
                title    = 'No issues detected'
                body     = "Inspected $parsedPackets packets over ${DurationSec}s with no retransmissions, resets, or drops."
            }
        }
        else {
            $findings += [ordered]@{
                severity = 'info'
                title    = 'Too little detail to judge the connection'
                body     = "The VPU moved $totalPackets packets in ${DurationSec}s but Windows only wrote per-packet detail for $parsedPackets of them. Nothing was wrong in that sample, but it is too small to call the connection healthy. Run the capture again, ideally while an event is streaming."
            }
        }
    }

    # -- Cleanup temp files ---------------------------------------
    foreach ($tmp in @($etlPath, $txtPath)) {
        try { if (Test-Path $tmp) { Remove-Item $tmp -Force } } catch { }
    }

    [ordered]@{
        durationSec     = $DurationSec
        totalPackets    = $totalPackets
        inspectedPackets = $parsedPackets
        droppedPackets  = $droppedPackets
        tcpRetransmits  = $tcpRetransmits
        tcpResets       = $tcpResets
        tcpSyns         = $tcpSyns
        tcpSynAcks      = $tcpSynAcks
        tcpFins         = $tcpFins
        topTalkers      = @($topTalkers)
        findings        = @($findings)
    } | ConvertTo-Json -Depth 5 -Compress
}
catch {
    # Cleanup on error
    try { $null = Invoke-Pktmon @('stop') } catch { }
    try { $null = Invoke-Pktmon @('filter', 'remove') } catch { }

    [ordered]@{
        error   = $true
        message = $_.Exception.Message
        script  = 'Start-NetworkCapture.ps1'
    } | ConvertTo-Json -Compress
}
