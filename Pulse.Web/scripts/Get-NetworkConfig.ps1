#Requires -Version 5.1
<#
.SYNOPSIS
    Collects network configuration for VPU diagnostics.
.DESCRIPTION
    Gathers adapter info, IP configuration, internet reachability,
    NTP source, and identifies the uplink adapter. Outputs JSON to stdout.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

try {
    # Net adapters -- enriched with PCI location + media type + admin/link state
    # so role classification (motherboard / camera / Wi-Fi) and the "internet on
    # a camera port" check can run downstream in Python.
    #
    # PCI location resolves the motherboard uplink (onboard LOM = PCI bus 0) from
    # a camera-NIC port (add-in card = bus > 0) even when both use the same Intel
    # chipset. We look it up ONLY for each present adapter via its own PnPDeviceID
    # -- never by scanning Get-PnpDevice -Class Net, which on a VPU enumerates
    # dozens of stale/ghost net devices and was slow enough to time out this whole
    # collector on real hardware. Any failed/expensive lookup degrades to null
    # (role classification falls back to chipset/unknown; internet detection,
    # adapters, IP config, and reachability are all unaffected).
    $adapters = Get-NetAdapter -ErrorAction SilentlyContinue | ForEach-Object {
        $pciBus = $null; $pciDev = $null; $pciFun = $null
        $pdid = $_.PnPDeviceID
        if ($pdid -and $pdid.StartsWith('PCI\')) {
            try {
                $loc = (Get-PnpDeviceProperty -InstanceId $pdid -KeyName 'DEVPKEY_Device_LocationInfo' -ErrorAction Stop).Data
                if ($loc -and ($loc -match 'PCI bus (\d+), device (\d+), function (\d+)')) {
                    $pciBus = [int]$Matches[1]; $pciDev = [int]$Matches[2]; $pciFun = [int]$Matches[3]
                }
            } catch { }
        }

        # Error/discard counters for EVERY wired adapter -- not just the uplink.
        # A multi-NIC VPU has the motherboard port plus the camera card; a bad
        # cable or dirty switch port on a non-uplink wired port was previously
        # invisible here. Wi-Fi/virtual adapters are skipped (no useful counters).
        $rxErr = $null; $txErr = $null
        $rxPErr = $null; $rxDisc = $null; $txPErr = $null; $txDisc = $null
        $fullDuplex = $null
        if ("$($_.PhysicalMediaType)" -match '802\.3') {
            try { $fullDuplex = $_.FullDuplex } catch { }
            try {
                $st = Get-NetAdapterStatistics -Name $_.Name -ErrorAction Stop
                $rxPErr = [int]$st.ReceivedUnicastPacketsWithErrors
                $rxDisc = [int]$st.ReceivedDiscards
                $txPErr = [int]$st.OutboundPacketErrors
                $txDisc = [int]$st.OutboundDiscards
                $rxErr  = $rxPErr + $rxDisc
                $txErr  = $txPErr + $txDisc
            } catch { }
        }

        [ordered]@{
            name                 = $_.Name
            interfaceDescription = $_.InterfaceDescription
            status               = "$($_.Status)"
            adminStatus          = "$($_.AdminStatus)"
            mediaConnectionState = "$($_.MediaConnectionState)"
            physicalMediaType    = "$($_.PhysicalMediaType)"
            macAddress           = $_.MacAddress
            linkSpeed            = $_.LinkSpeed
            interfaceIndex       = $_.InterfaceIndex
            pnpDeviceId          = $pdid
            pciBus               = $pciBus
            pciDevice            = $pciDev
            pciFunction          = $pciFun
            fullDuplex           = $fullDuplex
            rxErrors             = $rxErr
            txErrors             = $txErr
            rxPacketErrors       = $rxPErr
            rxDiscards           = $rxDisc
            txPacketErrors       = $txPErr
            txDiscards           = $txDisc
        }
    }

    # Build lookup tables keyed by InterfaceIndex for DHCP status and prefix length
    $ipIfaceMap = @{}
    Get-NetIPInterface -AddressFamily IPv4 -ErrorAction SilentlyContinue | ForEach-Object {
        $ipIfaceMap[$_.InterfaceIndex] = $_
    }
    $ipAddrMap = @{}
    Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | ForEach-Object {
        if (-not $ipAddrMap.ContainsKey($_.InterfaceIndex)) {
            $ipAddrMap[$_.InterfaceIndex] = $_
        }
    }

    # IP configurations
    $ipConfigs = Get-NetIPConfiguration -ErrorAction SilentlyContinue | ForEach-Object {
        $idx   = $_.InterfaceIndex
        $iface = $ipIfaceMap[$idx]
        $addr  = $ipAddrMap[$idx]
        [ordered]@{
            interfaceAlias     = $_.InterfaceAlias
            interfaceIndex     = $idx
            # @(...) forces an array so a single IP / gateway / DNS server isn't
            # unwrapped to a bare string in JSON -- consumers expect a list.
            ipv4Address        = @(if ($_.IPv4Address) { $_.IPv4Address | ForEach-Object { $_.IPAddress } })
            ipv4DefaultGateway = @(if ($_.IPv4DefaultGateway) { $_.IPv4DefaultGateway | ForEach-Object { $_.NextHop } })
            dnsServers         = @(if ($_.DNSServer) { $_.DNSServer | ForEach-Object { $_.ServerAddresses } | Select-Object -Unique })
            dhcpEnabled        = if ($iface) { $iface.Dhcp -eq 'Enabled' } else { $false }
            prefixLength       = if ($_.IPv4Address) { [int]($_.IPv4Address | Select-Object -First 1).PrefixLength } else { if ($addr) { [int]$addr.PrefixLength } else { $null } }
        }
    }

    # Identify the uplink adapter -- the interface that owns the active default
    # route (lowest-metric 0.0.0.0/0). Taking the first ipConfig that happens to
    # carry a gateway can pick a secondary/disconnected NIC on a multi-homed box
    # (camera NIC, VPN), mislabeling which adapter's link/error stats we report.
    $uplinkAdapter = $null
    $uplinkIdx = (Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue |
        Where-Object { $_.NextHop -and $_.NextHop -ne '0.0.0.0' -and -not $_.NextHop.StartsWith('169.254.') } |
        Sort-Object RouteMetric | Select-Object -First 1).InterfaceIndex

    # Prefer the default-route interface; fall back to the first interface with a
    # usable (non-APIPA) gateway if the route didn't resolve.
    $candidates = @()
    if ($uplinkIdx) { $candidates += $ipConfigs | Where-Object { $_.interfaceIndex -eq $uplinkIdx } }
    $candidates += $ipConfigs
    foreach ($ipc in $candidates) {
        $validGw = $ipc.ipv4DefaultGateway | Where-Object { $_ -and -not $_.StartsWith('169.254.') }
        if ($validGw) {
            $uplinkAdapter = [ordered]@{
                interfaceAlias = $ipc.interfaceAlias
                interfaceIndex = $ipc.interfaceIndex
                gateway        = ($validGw | Select-Object -First 1)
            }
            break
        }
    }

    # Internet reachability -- use .NET Ping with explicit 2s timeout
    # (Test-Connection can hang for 10+ seconds on VPU hardware)
    $internetReachable = $false
    $reachHost = $null
    foreach ($target in @('8.8.8.8', '1.1.1.1')) {
        if ($internetReachable) { break }
        try {
            $pinger = New-Object System.Net.NetworkInformation.Ping
            $reply = $pinger.Send($target, 2000)
            if ($reply.Status -eq [System.Net.NetworkInformation.IPStatus]::Success) {
                $internetReachable = $true
                $reachHost = $target
            }
            $pinger.Dispose()
        }
        catch { }
    }

    # ICMP fallback: managed/venue networks routinely block outbound ping
    # while allowing TCP/443. A failed ping does NOT mean "no internet" -- so
    # if ICMP came back empty, confirm with a TCP connect to a well-known
    # host on 443 before concluding the box is offline.
    if (-not $internetReachable) {
        foreach ($target in @('8.8.8.8', '1.1.1.1', '9.9.9.9')) {
            if ($internetReachable) { break }
            try {
                $tcp = New-Object System.Net.Sockets.TcpClient
                $iar = $tcp.BeginConnect($target, 443, $null, $null)
                if ($iar.AsyncWaitHandle.WaitOne(2000, $false) -and $tcp.Connected) {
                    $internetReachable = $true
                    $reachHost = "${target}:443"
                }
                $tcp.Close()
            }
            catch { }
        }
    }

    # NTP source
    $ntpSource = $null
    try {
        $ntpOutput = & w32tm /query /source 2>&1
        if ($LASTEXITCODE -eq 0 -and $ntpOutput) {
            $ntpSource = ($ntpOutput | Out-String).Trim()
        }
    }
    catch { }

    # Uplink adapter statistics (duplex, error counters) -- only if we found one
    $uplinkStats = $null
    if ($uplinkAdapter) {
        try {
            $uAdapter = Get-NetAdapter -InterfaceIndex $uplinkAdapter.interfaceIndex -ErrorAction Stop
            $uDuplex = $null
            try { $uDuplex = $uAdapter.FullDuplex } catch { }

            $uStats = [ordered]@{
                fullDuplex      = $uDuplex
                rxBytes         = $null; txBytes         = $null
                rxErrors        = 0; txErrors        = 0
                rxPacketErrors  = 0; rxDiscards      = 0
                txPacketErrors  = 0; txDiscards      = 0
            }
            try {
                $s = Get-NetAdapterStatistics -Name $uAdapter.Name -ErrorAction Stop
                $uStats.rxBytes        = $s.ReceivedBytes
                $uStats.txBytes        = $s.SentBytes
                $uStats.rxPacketErrors = $s.ReceivedUnicastPacketsWithErrors
                $uStats.rxDiscards     = $s.ReceivedDiscards
                $uStats.txPacketErrors = $s.OutboundPacketErrors
                $uStats.txDiscards     = $s.OutboundDiscards
                $uStats.rxErrors       = $uStats.rxPacketErrors + $uStats.rxDiscards
                $uStats.txErrors       = $uStats.txPacketErrors + $uStats.txDiscards
            }
            catch { }
            $uplinkStats = $uStats
        }
        catch { }
    }

    # Self-sightings: one of this VPU's own adapter MACs listed in ANOTHER of
    # its interfaces' neighbour (ARP) tables. Windows only learns a neighbour
    # from frames it receives, so this means the two ports share one network.
    # A camera port is a point-to-point link to one camera, so a camera port
    # heard on the motherboard port means its cable is patched into the venue
    # switch (Watertown TN, 2026-11-09: Ports 2-4 linked at 1 Gbps, no camera,
    # all three port MACs in the motherboard port's ARP table). Python decides
    # which sightings matter (roles live there); this just reports them.
    $selfSightings = @()
    try {
        $macOwner = @{}
        foreach ($a in $adapters) {
            $m = ("$($a.macAddress)" -replace '[-:]', '').ToUpper()
            if ($m -and $m -ne '000000000000') { $macOwner[$m] = $a.interfaceIndex }
        }
        Get-NetNeighbor -AddressFamily IPv4 -ErrorAction SilentlyContinue | ForEach-Object {
            $m = ("$($_.LinkLayerAddress)" -replace '[-:]', '').ToUpper()
            if ($selfSightings.Count -lt 32 -and $m -and $macOwner.ContainsKey($m) -and
                $macOwner[$m] -ne $_.InterfaceIndex) {
                $selfSightings += [ordered]@{
                    mac                  = $m
                    ip                   = $_.IPAddress
                    seenOnInterfaceIndex = $_.InterfaceIndex
                    seenOnInterfaceAlias = $_.InterfaceAlias
                    state                = "$($_.State)"
                }
            }
        }
    }
    catch { }

    $result = [ordered]@{
        adapters         = @($adapters)
        ipConfigurations = @($ipConfigs)
        uplinkAdapter    = $uplinkAdapter
        uplinkStats      = $uplinkStats
        internet = [ordered]@{
            reachable = $internetReachable
            testedHost = $reachHost
        }
        ntpSource = $ntpSource
        selfNeighborSightings = @($selfSightings)
    }

    $result | ConvertTo-Json -Depth 5 -Compress
}
catch {
    [ordered]@{
        error   = $true
        message = $_.Exception.Message
        script  = 'Get-NetworkConfig.ps1'
    } | ConvertTo-Json -Compress
}
