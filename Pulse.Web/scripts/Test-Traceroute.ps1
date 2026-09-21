#Requires -Version 5.1
<#
.SYNOPSIS
    Runs a traceroute to a target host for VPU network path diagnostics.
.DESCRIPTION
    Uses ICMP echo with incrementing TTL to trace the path to a target.
    Each hop reports IP, optional hostname, and round-trip time.
    Outputs JSON to stdout.
#>
[CmdletBinding()]
param(
    [string]$Target = 'pixellot.tv',
    [int]$MaxHops = 20,
    [int]$TimeoutMs = 2000
)

$ErrorActionPreference = 'Stop'

try {
    # Resolve target to IPv4 first
    $targetIp = $null
    try {
        $resolved = [System.Net.Dns]::GetHostAddresses($Target) |
            Where-Object { $_.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork } |
            Select-Object -First 1
        if ($resolved) { $targetIp = $resolved.ToString() }
    }
    catch { }

    if (-not $targetIp) {
        [ordered]@{
            error   = $true
            message = "Could not resolve target: $Target"
            script  = 'Test-Traceroute.ps1'
        } | ConvertTo-Json -Compress
        return
    }

    $pinger  = New-Object System.Net.NetworkInformation.Ping
    $options = New-Object System.Net.NetworkInformation.PingOptions
    $options.DontFragment = $true
    $buffer  = [byte[]]::new(32)

    $hops    = @()
    $reached = $false

    for ($ttl = 1; $ttl -le $MaxHops; $ttl++) {
        $options.Ttl = $ttl
        $ip       = $null
        $hostname = $null
        $rttMs    = $null
        $hopStatus = 'timeout'

        try {
            # Ping.RoundtripTime is only populated when Status is Success. On a
            # TtlExpired reply -- which is every intermediate hop -- .NET leaves
            # it at 0, so reading it straight off the reply reported "0 ms" for
            # the whole path and hid exactly the latency spike a traceroute is
            # run to find. Time the call ourselves instead.
            $sw = [System.Diagnostics.Stopwatch]::StartNew()
            $reply = $pinger.Send($targetIp, $TimeoutMs, $buffer, $options)
            $sw.Stop()

            if ($reply.Status -eq [System.Net.NetworkInformation.IPStatus]::TtlExpired -or
                $reply.Status -eq [System.Net.NetworkInformation.IPStatus]::Success) {
                $ip     = $reply.Address.ToString()
                # Trust the stack's own figure when it gave us one; otherwise
                # use the measured elapsed time, floored at 1ms so a sub-1ms
                # LAN hop does not render as the "0 ms" this bug produced.
                if ($reply.Status -eq [System.Net.NetworkInformation.IPStatus]::Success -and $reply.RoundtripTime -gt 0) {
                    $rttMs = [int]$reply.RoundtripTime
                }
                else {
                    $rttMs = [math]::Max(1, [int][math]::Round($sw.Elapsed.TotalMilliseconds))
                }
                $hopStatus = if ($reply.Status -eq [System.Net.NetworkInformation.IPStatus]::Success) { 'reached' } else { 'transit' }

                # Quick reverse DNS -- 500ms async timeout so it doesn't stall
                try {
                    $ar = [System.Net.Dns]::BeginGetHostEntry($ip, $null, $null)
                    if ($ar.AsyncWaitHandle.WaitOne(500)) {
                        $entry = [System.Net.Dns]::EndGetHostEntry($ar)
                        if ($entry.HostName -and $entry.HostName -ne $ip) {
                            $hostname = $entry.HostName
                        }
                    }
                }
                catch { }
            }
            elseif ($reply.Status -eq [System.Net.NetworkInformation.IPStatus]::TimedOut) {
                $hopStatus = 'timeout'
            }
            else {
                $hopStatus = $reply.Status.ToString()
            }
        }
        catch {
            $hopStatus = 'error'
        }

        $hops += [ordered]@{
            hop      = $ttl
            ip       = $ip
            hostname = $hostname
            rttMs    = $rttMs
            status   = $hopStatus
        }

        if ($hopStatus -eq 'reached') {
            $reached = $true
            break
        }
    }

    $pinger.Dispose()

    [ordered]@{
        target   = $Target
        targetIp = $targetIp
        reached  = $reached
        hops     = @($hops)
        hopCount = $hops.Count
    } | ConvertTo-Json -Depth 5 -Compress
}
catch {
    [ordered]@{
        error   = $true
        message = $_.Exception.Message
        script  = 'Test-Traceroute.ps1'
    } | ConvertTo-Json -Compress
}
