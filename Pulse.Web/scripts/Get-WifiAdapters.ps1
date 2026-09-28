#Requires -Version 5.1
<#
.SYNOPSIS
    Detects whether the VPU is reaching the internet over Wi-Fi.
.DESCRIPTION
    Pixellot VPUs are wired-only by design. The condition worth flagging is
    not "a Wi-Fi adapter exists" -- Windows always has Wi-Fi Direct / hosted-
    network *virtual* adapters that show as connected -- but "Wi-Fi is the
    VPU's actual internet uplink." That is true only when a real Wi-Fi NIC
    carries the default route (0.0.0.0/0) AND no wired adapter does.

    Returns every Wi-Fi-class adapter with isVirtual / hasDefaultRoute flags,
    plus a top-level `uplinkIsWifi` the dashboard gates its warning on.

    Adapted from Canopy's reportWifiConnection.ps1 -- the Banyan POST envelope
    is replaced with stdout JSON for run_ps consumption.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

function Test-IsWifi {
    param($Adapter)
    return ($Adapter.PhysicalMediaType -eq 'Native 802.11' -or
            $Adapter.InterfaceDescription -like '*Wi-Fi*'   -or
            $Adapter.InterfaceDescription -like '*Wireless*' -or
            $Adapter.InterfaceDescription -like '*WLAN*')
}

function Test-IsVirtualWifi {
    param($Adapter)
    # Wi-Fi Direct / Miracast / Microsoft Hosted Network adapters are P2P
    # plumbing, never the real uplink. Match by description and the adapter's
    # Virtual flag when the OS exposes it.
    if ($Adapter.InterfaceDescription -match 'Direct|Virtual') { return $true }
    try { if ($Adapter.Virtual -eq $true) { return $true } } catch { }
    return $false
}

try {
    # -- Which interfaces carry an active default route? ----------
    # Membership here means the interface is currently providing a path to
    # the internet (a real gateway next-hop, not APIPA).
    $defaultRouteIdx = @()
    try {
        $defaultRouteIdx = @(
            Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue |
                Where-Object { $_.NextHop -and $_.NextHop -ne '0.0.0.0' -and -not $_.NextHop.StartsWith('169.254.') } |
                Select-Object -ExpandProperty ifIndex -Unique
        )
    }
    catch { }

    $allAdapters = @(Get-NetAdapter -ErrorAction SilentlyContinue)

    # -- Which interface does Windows actually send internet traffic on? --
    # Holding a default route is not enough: a cable in the motherboard port
    # can hold one (static config, or a dead jack's DHCP) while Windows routes
    # everything over Wi-Fi on a better metric. Field: Armstrong IL
    # 2026-09-28 - on Wi-Fi with a cable in the main port, and this check
    # stayed quiet because "a wired adapter has a default route". Ask the
    # route table directly; fall back to the lowest route + interface metric.
    $uplinkIdx = $null
    $uplinkSource = $null
    try {
        $uplinkIdx = @(Find-NetRoute -RemoteIPAddress '8.8.8.8' -ErrorAction Stop |
            Where-Object { $_.InterfaceIndex } | Select-Object -ExpandProperty InterfaceIndex)[0]
        if ($uplinkIdx) { $uplinkSource = 'route-lookup' }
    }
    catch { }
    if (-not $uplinkIdx) {
        try {
            $ifMetric = @{}
            foreach ($i in @(Get-NetIPInterface -AddressFamily IPv4 -ErrorAction SilentlyContinue)) { $ifMetric[[int]$i.ifIndex] = [int]$i.InterfaceMetric }
            $best = $null; $bestMetric = [int]::MaxValue
            foreach ($r in @(Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue)) {
                if (-not $r.NextHop -or $r.NextHop -eq '0.0.0.0' -or $r.NextHop.StartsWith('169.254.')) { continue }
                $m = [int]$r.RouteMetric + [int]$ifMetric[[int]$r.ifIndex]
                if ($m -lt $bestMetric) { $bestMetric = $m; $best = $r.ifIndex }
            }
            if ($best) { $uplinkIdx = $best; $uplinkSource = 'lowest-metric' }
        }
        catch { }
    }

    # Does a wired adapter hold a default route? Only the fallback when the
    # route lookup above fails. The rows go to the Wi-Fi finding, so it can
    # say a cable IS connected but unused (Armstrong: I219-LM up with a
    # 192.168.10.x gateway on metric 256 while Wi-Fi carried the internet).
    $ethernetHasDefaultRoute = $false
    $wiredRoutes = New-Object 'System.Collections.Generic.List[object]'
    $routeRows = @(Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue)
    foreach ($a in $allAdapters) {
        if ($a.Status -eq 'Up' -and -not (Test-IsWifi $a) -and ($defaultRouteIdx -contains $a.ifIndex)) {
            $ethernetHasDefaultRoute = $true
            $hop = @($routeRows | Where-Object { $_.ifIndex -eq $a.ifIndex } | Select-Object -ExpandProperty NextHop)[0]
            $wiredRoutes.Add([pscustomobject]@{
                ifIndex = $a.ifIndex; name = $a.Name
                interfaceDescription = $a.InterfaceDescription; nextHop = $hop
            })
        }
    }

    # -- Enumerate Wi-Fi-class adapters ---------------------------
    $adapters = @()
    foreach ($a in ($allAdapters | Where-Object { Test-IsWifi $_ })) {
        $isUp = ($a.Status -eq 'Up')
        $detail = [ordered]@{
            name                 = $a.Name
            interfaceAlias       = $a.InterfaceAlias
            interfaceDescription = $a.InterfaceDescription
            macAddress           = $a.MacAddress
            linkSpeed            = $a.LinkSpeed
            status               = $a.Status.ToString()
            isUp                 = $isUp
            isVirtual            = [bool](Test-IsVirtualWifi $a)
            hasDefaultRoute      = [bool]($defaultRouteIdx -contains $a.ifIndex)
            ifIndex              = $a.ifIndex
            isUplink             = [bool]($uplinkIdx -and $a.ifIndex -eq $uplinkIdx)
            connected            = $false
            ssid                 = $null
            networkCategory      = $null
            ipv4Connectivity     = $null
            ipv6Connectivity     = $null
        }

        if ($isUp) {
            # $profile is a PowerShell automatic variable (profile script path);
            # use $connProfile to avoid shadowing it.
            try {
                $connProfile = Get-NetConnectionProfile -InterfaceAlias $a.Name -ErrorAction Stop
                if ($connProfile) {
                    $detail.connected        = $true
                    $detail.ssid             = $connProfile.Name
                    $detail.networkCategory  = "$($connProfile.NetworkCategory)"
                    $detail.ipv4Connectivity = "$($connProfile.IPv4Connectivity)"
                    $detail.ipv6Connectivity = "$($connProfile.IPv6Connectivity)"
                }
            }
            catch { }  # Up but not on a profile -- leave connected=false
        }

        $adapters += $detail
    }

    # -- Is Wi-Fi the VPU's actual internet uplink? ---------------
    # A real (non-virtual) Wi-Fi NIC carries the default route, and no wired
    # adapter does. This is the only case worth a warning.
    $uplinkIsWifi = $false
    if ($uplinkIdx) {
        foreach ($d in $adapters) {
            if ($d.isUplink -and $d.isUp -and -not $d.isVirtual) { $uplinkIsWifi = $true; break }
        }
    }
    elseif (-not $ethernetHasDefaultRoute) {
        foreach ($d in $adapters) {
            if ($d.isUp -and -not $d.isVirtual -and $d.hasDefaultRoute) {
                $uplinkIsWifi = $true
                break
            }
        }
    }

    $activeCount = @($adapters | Where-Object { $_.isUp -and -not $_.isVirtual }).Count

    [ordered]@{
        adapters                = @($adapters)
        anyActive               = ($activeCount -gt 0)
        activeCount             = $activeCount
        ethernetHasDefaultRoute = [bool]$ethernetHasDefaultRoute
        wiredDefaultRoutes      = $wiredRoutes.ToArray()
        uplinkIsWifi            = [bool]$uplinkIsWifi
        uplinkIfIndex           = $uplinkIdx
        uplinkSource            = $uplinkSource
    } | ConvertTo-Json -Depth 5 -Compress
}
catch {
    [ordered]@{
        error   = $true
        message = $_.Exception.Message
        script  = 'Get-WifiAdapters.ps1'
    } | ConvertTo-Json -Compress
}
