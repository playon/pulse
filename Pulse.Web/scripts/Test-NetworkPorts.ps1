#Requires -Version 5.1
<#
.SYNOPSIS
    Tests network port connectivity for VPU diagnostics.
.DESCRIPTION
    Tests TCP and UDP connectivity to required service endpoints.
    Outputs a JSON array of test results to stdout.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

try {
    # Port list audited against Canopy connections.csv (the canonical Pixellot
    # port reference). Notes:
    #  - prod-echo.pixellot.tv covers TCP 443 + UDP 123/443/2088 per the CSV;
    #    we hit those specific subdomain entries in addition to the wider
    #    pixellot.tv apex test (some venues filter on FQDN, not IP).
    #  - scorebot.sportzcast.net (TCP 1400-1405) is NOT tested. It was, as
    #    optional rows, until the range was dropped -- see the note in the
    #    port list below.
    # Discover the VPU's configured DNS server so the DNS check tests the
    # resolver the box actually uses -- not a hardcoded public IP like 8.8.8.8,
    # which locked-down venue networks block by design (the VPU resolves names
    # through the venue's internal DNS instead).
    # Test the resolver the ACTIVE UPLINK actually uses -- scope to the interface
    # that holds the default route. Querying every interface and taking the first
    # DNS can grab a stale resolver off a disconnected or secondary adapter (a
    # camera NIC, VPN, etc.); that dead IP then fails the UDP/53 probe and looks
    # like "DNS blocked" while the real resolver is working fine.
    $primaryDns = $null
    try {
        $dnsRows = Get-DnsClientServerAddress -AddressFamily IPv4 -ErrorAction Stop
        $uplinkIdx = (Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue |
            Where-Object { $_.NextHop -and $_.NextHop -ne '0.0.0.0' } |
            Sort-Object RouteMetric | Select-Object -First 1).InterfaceIndex
        $scoped = if ($uplinkIdx) { $dnsRows | Where-Object { $_.InterfaceIndex -eq $uplinkIdx } } else { $dnsRows }
        $primaryDns = $scoped |
            ForEach-Object { $_.ServerAddresses } |
            Where-Object { $_ -and -not $_.StartsWith('127.') -and -not $_.StartsWith('169.254.') } |
            Select-Object -First 1
        # If the uplink interface carried no usable resolver, fall back to any
        # interface's -- keeps the check working on unusual routing setups.
        if (-not $primaryDns -and $uplinkIdx) {
            $primaryDns = $dnsRows |
                ForEach-Object { $_.ServerAddresses } |
                Where-Object { $_ -and -not $_.StartsWith('127.') -and -not $_.StartsWith('169.254.') } |
                Select-Object -First 1
        }
    }
    catch { }

    $portTests = @(
        # Required -- core Pixellot streaming + cloud services
        @{ protocol = 'TCP'; port = 443;  host = 'pixellot.tv';            purpose = 'Pixellot';          optional = $false }
        @{ protocol = 'TCP'; port = 443;  host = 'prod-echo.pixellot.tv';  purpose = 'Pixellot Echo';     optional = $false }
        @{ protocol = 'TCP'; port = 443;  host = 'nfhsnetwork.com';        purpose = 'NFHS Network';      optional = $false }
        @{ protocol = 'TCP'; port = 443;  host = 'service.singular.live';  purpose = 'Singular Overlay';  optional = $false }
        # secure.logmein.com, not the logmein.com apex: the apex now points at
        # GoTo's marketing site (Vercel, 76.76.21.21), so reaching it proves
        # nothing about remote access. secure.logmein.com rides GoTo's real
        # service block (158.120.16.0/20 -- same netblock live VPU LMI sessions
        # use, PTR lmi-www25-10.logmein.com), so this tests what techs depend on.
        @{ protocol = 'TCP'; port = 443;  host = 'secure.logmein.com';     purpose = 'LogMeIn';           optional = $false }
        @{ protocol = 'UDP'; port = 123;  host = 'prod-echo.pixellot.tv';  purpose = 'NTP';               optional = $false }
        # Zixi ingest caveat: live events stream to a broadcaster assigned
        # per-event from AWS pools (observed us-east-2/us-west-2), not to
        # prod-echo (us-east-1). These rows prove the venue firewall allows the
        # PORTS; rules must therefore allow UDP 443/2088 by port, not by
        # destination IP. Streaming failover chain (verified from VPU logs +
        # packet capture, Olympic WA 2026-08-18): Zixi UDP/2088 -> Zixi UDP/443
        # (same protocol, disguise port) -> RTMP TCP/1935 -> nothing. Either
        # UDP rung alone is a fully healthy stream; RTMP is a degraded last
        # resort (~4 min late start, no FEC/ARQ).
        @{ protocol = 'UDP'; port = 443;  host = 'prod-echo.pixellot.tv';  purpose = 'Zixi Backup';       optional = $false }
        @{ protocol = 'UDP'; port = 2088; host = 'prod-echo.pixellot.tv';  purpose = 'Zixi Streaming';    optional = $false }
        # RTMP fallback egress (TCP/1935). No stable Pixellot host listens on
        # 1935 -- prod-echo doesn't (verified 2026-08-18), and the real
        # broadcasters (pxltd-<ip>.pixellot.stream) are provisioned per event
        # and torn down after -- so this probes the most stable public RTMP
        # listener there is. Caveat: proves 1935 egress BY PORT; a
        # destination-aware filter could still block pixellot.stream while
        # allowing this. Revisit if Pixellot ever adds 1935 to prod-echo.
        @{ protocol = 'TCP'; port = 1935; host = 'a.rtmp.youtube.com';     purpose = 'RTMP Fallback';     optional = $false }
        # The Sportzcast Scorebot range (TCP/1400-1405) used to be probed here
        # as six optional rows. Removed: nothing on the VPU requires it, so
        # six tiles that can never fail readiness were six-sevenths of the
        # Optional section and read to a tier-1 agent as more ports to
        # understand. Scoreboard health is covered properly by the
        # ScoreConnect tab, which tests the thing that actually matters (the
        # bot connection and the live feed) rather than egress to a port
        # range. sportzcast.net has since been dropped from the
        # domain-reachability list too, so Pulse no longer probes Sportzcast
        # at all.
    )

    # DNS reachability against the *configured* resolver (prepended so it
    # leads the list). Skipped -- not failed -- when no resolver is configured;
    # a missing/broken resolver still surfaces via the domain-resolution tests.
    if ($primaryDns) {
        $portTests = @(
            @{ protocol = 'UDP'; port = 53; host = $primaryDns; purpose = 'DNS'; optional = $false }
        ) + $portTests
    }

    # Kick off every TCP connect up front, non-blocking, then judge them all
    # against one shared deadline when the loop reaches each row. Probing
    # sequentially made the script's runtime scale with the number of DEAD
    # targets (~3s each): when Sportzcast's six Scorebot/RTMP endpoints went
    # dark in July 2026 the port sweep ballooned to ~20s and froze the splash
    # checklist, which gates on the dashboard. Those six rows are gone now,
    # but the design stands -- any dead target costs the same, and concurrent
    # probes cap the whole TCP set at the single budget below no matter how
    # many die.
    $tcpBudgetMs = 4000

    # Pre-warm the .NET thread pool before racing the connects. Each
    # BeginConnect(hostname, ...) needs a pool thread for its DNS leg, and
    # .NET Framework grows the pool at ~1 thread per 500ms past the default
    # minimum (= CPU count). During Pulse's launch burst several PowerShell
    # collectors saturate the box at once, so on a starved 6-core VPU ~13
    # concurrent probes could spend the entire shared budget just waiting
    # for threads -- every healthy TCP row then reported "blocked" while the
    # network was fine (reproduced on VPU2, 2026-07-23). Raising the minimum
    # makes threads available immediately; it costs nothing when idle.
    $minWorker = 0; $minIo = 0
    $null = [System.Threading.ThreadPool]::GetMinThreads([ref]$minWorker, [ref]$minIo)
    if ($minWorker -lt 16 -or $minIo -lt 16) {
        $null = [System.Threading.ThreadPool]::SetMinThreads(
            [Math]::Max($minWorker, 16), [Math]::Max($minIo, 16))
    }

    function Start-TcpRace([array]$targets) {
        # Kick off a non-blocking connect for every target, keyed host:port.
        $probes = @{}
        foreach ($t in $targets) {
            try {
                $tcp = New-Object System.Net.Sockets.TcpClient
                $probes["$($t.host):$($t.port)"] = @{
                    client = $tcp
                    async  = $tcp.BeginConnect($t.host, $t.port, $null, $null)
                }
            }
            catch {
                # DNS resolution or socket setup failed synchronously -- leave
                # the probe absent; the row is judged 'fail'.
            }
        }
        return $probes
    }

    $tcpProbes = Start-TcpRace ($portTests | Where-Object { $_.protocol -eq 'TCP' })
    $tcpClock = [System.Diagnostics.Stopwatch]::StartNew()

    $results = foreach ($test in $portTests) {
        $status = 'fail'

        if ($test.protocol -eq 'TCP') {
            $probe = $tcpProbes["$($test.host):$($test.port)"]
            if ($probe) {
                try {
                    # Remaining slice of the shared budget -- all connects have
                    # been racing since before the loop, so a probe reached
                    # late waits only for what's left (possibly 0ms).
                    $remainingMs = $tcpBudgetMs - $tcpClock.ElapsedMilliseconds
                    if ($remainingMs -lt 0) { $remainingMs = 0 }
                    $waited = $probe.async.AsyncWaitHandle.WaitOne($remainingMs, $false)
                    if ($waited -and $probe.client.Connected) {
                        $probe.client.EndConnect($probe.async)
                        $status = 'pass'
                    }
                }
                catch {
                    $status = 'fail'
                }
                finally {
                    $probe.client.Close()
                }
            }
        }
        elseif ($test.protocol -eq 'UDP' -and $test.port -eq 123) {
            # NTP/123 egress test -- send a real NTP v3 client request, require a
            # reply. Any reply passes: this row answers "is UDP/123 egress open",
            # and prod-echo answers as an echo service (it returns our own mode-3
            # packet verbatim, wire-verified) -- so requiring a genuine mode-4
            # server reply would false-fail an open port. We still send a real
            # 48-byte NTP request (not arbitrary bytes) so NTP-aware middleboxes
            # treat the probe as NTP. Whether time sync actually WORKS is judged
            # separately by the w32tm status check (Time Sync on the adapter
            # card). A retry defeats transient single-packet loss; capped at
            # two attempts so a blocked port costs ~6s, not ~9s (the script's
            # callers budget 30-45s for the whole port list).
            try {
                $addr = [System.Net.Dns]::GetHostAddresses($test.host) |
                    Where-Object { $_.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork } |
                    Select-Object -First 1
                if ($addr) {
                    $ep = New-Object System.Net.IPEndPoint($addr, 123)
                    # 48-byte NTP packet: byte 0 = 0x1B (LI=0, Version=3, Mode=3 client)
                    $ntpReq = New-Object byte[] 48
                    $ntpReq[0] = 0x1B
                    for ($attempt = 1; ($attempt -le 2) -and ($status -ne 'pass'); $attempt++) {
                        $udp = New-Object System.Net.Sockets.UdpClient
                        $udp.Client.ReceiveTimeout = 3000
                        $udp.Client.SendTimeout = 3000
                        try {
                            $udp.Send($ntpReq, $ntpReq.Length, $ep) | Out-Null
                            $remoteEP = New-Object System.Net.IPEndPoint([System.Net.IPAddress]::Any, 0)
                            $resp = $udp.Receive([ref]$remoteEP)
                            if ($resp.Length -gt 0) { $status = 'pass' }
                        }
                        catch [System.Net.Sockets.SocketException] {
                            # 10054 = ICMP port unreachable -- definitive reject; stop retrying.
                            $sockErr = $_.Exception.ErrorCode
                            if (-not $sockErr -and $_.Exception.InnerException) { $sockErr = $_.Exception.InnerException.ErrorCode }
                            if ($sockErr -eq 10054) { break }
                            # Otherwise a receive timeout -- stay 'fail' and retry.
                        }
                        finally {
                            $udp.Close()
                        }
                    }
                }
            }
            catch {
                $status = 'fail'
            }
        }
        elseif ($test.protocol -eq 'UDP' -and $test.port -eq 53) {
            # Real DNS UDP test -- send a minimal NS-root query and check for response
            try {
                $udp = New-Object System.Net.Sockets.UdpClient
                $udp.Client.ReceiveTimeout = 3000
                $udp.Client.SendTimeout = 3000
                $addr = [System.Net.Dns]::GetHostAddresses($test.host) |
                    Where-Object { $_.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork } |
                    Select-Object -First 1
                if ($addr) {
                    $ep = New-Object System.Net.IPEndPoint($addr, 53)
                    # 17-byte DNS query: ID=0x1234, flags=0x0100 (std query, RD), 1 question
                    # Name: root (.), QTYPE=NS (0x0002), QCLASS=IN (0x0001)
                    $dnsReq = [byte[]](
                        0x12, 0x34, 0x01, 0x00, 0x00, 0x01, 0x00, 0x00,
                        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0x00, 0x01
                    )
                    $udp.Send($dnsReq, $dnsReq.Length, $ep) | Out-Null
                    $remoteEP = New-Object System.Net.IPEndPoint([System.Net.IPAddress]::Any, 0)
                    $resp = $udp.Receive([ref]$remoteEP)
                    # Reply needs to be at least 12 bytes (header) and echo our ID
                    if ($resp.Length -ge 12 -and $resp[0] -eq 0x12 -and $resp[1] -eq 0x34) {
                        $status = 'pass'
                    }
                }
                $udp.Close()
            }
            catch {
                $status = 'fail'
            }
        }
        elseif ($test.protocol -eq 'UDP') {
            # Echo-contract UDP test. The generic UDP targets (prod-echo.pixellot.tv
            # 443/2088) run an echo service -- anything sent comes back verbatim
            # (wire-verified: a 24-byte probe to :2088 echoed back in ~20 ms). So a
            # reply is REQUIRED to pass. The old rule treated a silent timeout as
            # pass ("open|filtered"), which false-passed every silently-dropped
            # port -- the most common school-firewall block mode -- and let a VPU
            # show UDP/2088 green while streaming was actually blocked. Three
            # second attempt defeats transient single-packet loss; capped at two
            # so a silently-blocked port costs ~4s, keeping the whole list inside
            # its callers' 30-45s budgets.
            # NOTE: this branch assumes echo-capable endpoints; a future non-echo
            # UDP target needs its own protocol-aware branch (like 123/53 above).
            try {
                $addr = [System.Net.Dns]::GetHostAddresses($test.host) |
                    Where-Object { $_.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork } |
                    Select-Object -First 1
                if ($addr) {
                    $ep = New-Object System.Net.IPEndPoint($addr, $test.port)
                    $payload = [System.Text.Encoding]::ASCII.GetBytes("testing UDP on port $($test.port)")
                    for ($attempt = 1; ($attempt -le 2) -and ($status -ne 'pass'); $attempt++) {
                        $udp = New-Object System.Net.Sockets.UdpClient
                        $udp.Client.ReceiveTimeout = 2000
                        $udp.Client.SendTimeout = 2000
                        try {
                            $udp.Send($payload, $payload.Length, $ep) | Out-Null
                            $remoteEP = New-Object System.Net.IPEndPoint([System.Net.IPAddress]::Any, 0)
                            $resp = $udp.Receive([ref]$remoteEP)
                            # Any datagram back proves the port is open end-to-end
                            # (the echo service returns our payload verbatim).
                            if ($resp.Length -gt 0) { $status = 'pass' }
                        }
                        catch [System.Net.Sockets.SocketException] {
                            # 10054 = ICMP port unreachable -- definitive reject; stop retrying.
                            $sockErr = $_.Exception.ErrorCode
                            if (-not $sockErr -and $_.Exception.InnerException) { $sockErr = $_.Exception.InnerException.ErrorCode }
                            if ($sockErr -eq 10054) { break }
                            # Otherwise a receive timeout -- stay 'fail' and retry.
                        }
                        finally {
                            $udp.Close()
                        }
                    }
                }
            }
            catch {
                $status = 'fail'
            }
        }

        [ordered]@{
            protocol = $test.protocol
            port     = $test.port
            host     = $test.host
            purpose  = $test.purpose
            optional = $test.optional
            status   = $status
        }
    }

    # Second-chance pass for TCP rows that failed the shared-budget race.
    # The first race can run inside Pulse's own collector burst (launch
    # preload fires many PowerShell processes at once); a starved process
    # can burn the budget without the connects ever being serviced, failing
    # every row at once -- a pattern no real firewall produces. A genuinely
    # blocked port fails this pass too, so it costs one extra budget only
    # when something failed, and truly-dead rows (e.g. the July 2026
    # Sportzcast outage) still can't stall the sweep beyond it.
    $retryRows = @($results | Where-Object { $_.protocol -eq 'TCP' -and $_.status -eq 'fail' })
    if ($retryRows.Count -gt 0) {
        # Brief settle so the retry lands after the worst of the burst.
        Start-Sleep -Milliseconds 1500
        $retryProbes = Start-TcpRace $retryRows
        $retryClock = [System.Diagnostics.Stopwatch]::StartNew()
        foreach ($row in $retryRows) {
            $probe = $retryProbes["$($row.host):$($row.port)"]
            if (-not $probe) { continue }
            try {
                $remainingMs = $tcpBudgetMs - $retryClock.ElapsedMilliseconds
                if ($remainingMs -lt 0) { $remainingMs = 0 }
                $waited = $probe.async.AsyncWaitHandle.WaitOne($remainingMs, $false)
                if ($waited -and $probe.client.Connected) {
                    $probe.client.EndConnect($probe.async)
                    $row.status = 'pass'
                }
            }
            catch { }
            finally {
                $probe.client.Close()
            }
        }
    }

    [ordered]@{
        results = @($results)
    } | ConvertTo-Json -Depth 5 -Compress
}
catch {
    [ordered]@{
        error   = $true
        message = $_.Exception.Message
        script  = 'Test-NetworkPorts.ps1'
    } | ConvertTo-Json -Compress
}
