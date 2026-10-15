#Requires -Version 5.1
<#
.SYNOPSIS
    Collects system identity information for VPU diagnostics.
.DESCRIPTION
    Gathers computer system, BIOS, OS, timezone, and Pixellot-specific
    registry/file data. Outputs a single JSON object to stdout.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

try {
    # Batch CIM queries
    $cs   = Get-CimInstance Win32_ComputerSystem
    $bios = Get-CimInstance Win32_BIOS
    $enc  = Get-CimInstance Win32_SystemEnclosure
    $os   = Get-CimInstance Win32_OperatingSystem
    $tz   = Get-CimInstance Win32_TimeZone

    # Calculate uptime. TimeSpan.Days, not [int]TotalDays -- the [int] cast
    # ROUNDS (0.66 days -> 1), so a VPU up 16 hours displayed "1d 16h".
    $lastBoot = $os.LastBootUpTime
    $uptime   = (Get-Date) - $lastBoot
    $uptimeStr = '{0}d {1}h {2}m' -f $uptime.Days, $uptime.Hours, $uptime.Minutes

    # Pixellot registry
    $pixReg = $null
    $pixVersion = $null
    $pixImageVersion = $null
    $hasPixellotRegistry = $false
    try {
        $regPath = 'HKLM:\SOFTWARE\Pixellot'
        if (Test-Path $regPath) {
            $hasPixellotRegistry = $true
            $pixVersion = (Get-ItemProperty -Path $regPath -Name 'Version' -ErrorAction SilentlyContinue).Version
            $pixImageVersion = (Get-ItemProperty -Path $regPath -Name 'ImageVersion' -ErrorAction SilentlyContinue).ImageVersion
        }
    }
    catch { }

    # VPU friendly name from the latest Pixellot agent log
    # Uses findstr (native, encoding-safe) then regex to extract the name.
    # We try several log filename patterns since Pixellot has renamed these
    # across firmware versions (agent_vpu2_*, agent_vpu_*, agent_*).
    $logDir = 'C:\Pixellot\Data\Log'
    $vpuName = $null
    try {
        if (Test-Path $logDir) {
            # Newest first, back up to a week: Pixellot starts a new log at
            # midnight, and the new one has no BROADCAST_NAME line until the
            # agent logs it again (a unit that hasn't streamed can go days).
            # Reading only the newest log sent nameless check-ins after
            # midnight (6493, 2026-10-15).
            $logPatterns = @('agent_vpu2_*.log', 'agent_vpu_*.log', 'agent_*.log')
            $agentLogs = $null
            foreach ($pattern in $logPatterns) {
                $agentLogs = @(Get-ChildItem -Path $logDir -Filter $pattern -ErrorAction SilentlyContinue |
                    Sort-Object LastWriteTime -Descending | Select-Object -First 7)
                if ($agentLogs.Count -gt 0) { break }
            }
            foreach ($log in $agentLogs) {
                $lines = & findstr /C:"BROADCAST_NAME" $log.FullName 2>$null
                if ($lines) {
                    # Take the last matching line
                    $last = if ($lines -is [array]) { $lines[-1] } else { $lines }
                    if ($last -match 'result:\s*(.+)$') {
                        $vpuName = $Matches[1].Trim()
                        break
                    }
                }
            }
        }
    }
    catch { }

    # Pixellot Cloud venueId from the latest Coordinator log
    # Same findstr-based approach as vpuName for encoding safety --
    # Select-String can silently miss matches on UTF-16-encoded logs.
    # Pattern from Canopy's systemDataCollector.ps1:
    #   "got for key /GENERAL/VenueID result: <ID>"
    # This id is the lookup key for Pixellot Cloud's /api/v3/venues/{id}
    # endpoint, so the API integration can self-identify without a
    # MAC-matching dance.
    $venueId = $null
    try {
        if (Test-Path $logDir) {
            # Newest first, back up to a week (same midnight rollover as above).
            $coordLogs = @(Get-ChildItem -Path $logDir -Filter 'coordinator*.log' -ErrorAction SilentlyContinue |
                Sort-Object LastWriteTime -Descending | Select-Object -First 7)
            if ($coordLogs.Count -eq 0) {
                $coordLogs = @(Get-ChildItem -Path $logDir -Filter '*Coordinator*.log' -ErrorAction SilentlyContinue |
                    Sort-Object LastWriteTime -Descending | Select-Object -First 7)
            }
            foreach ($log in $coordLogs) {
                $lines = & findstr /C:"/GENERAL/VenueID" $log.FullName 2>$null
                if ($lines) {
                    $last = if ($lines -is [array]) { $lines[-1] } else { $lines }
                    if ($last -match 'result:\s*(\S+)') {
                        $venueId = $Matches[1].Trim()
                        break
                    }
                }
            }
        }
    }
    catch { }

    # Detect non-VPU host
    $hasPixellotLogs = Test-Path 'D:\Pixellot\PixellotAgent\logs\*'
    $hasCPixellot    = Test-Path 'C:\Pixellot'
    $isNonVpuHost    = (-not $hasPixellotRegistry) -and (-not $hasPixellotLogs) -and (-not $hasCPixellot)

    $result = [ordered]@{
        computerSystem = [ordered]@{
            name          = $cs.Name
            manufacturer  = $cs.Manufacturer
            model         = $cs.Model
            domain        = $cs.Domain
            partOfDomain  = $cs.PartOfDomain
        }
        bios = [ordered]@{
            smbiosVersion = $bios.SMBIOSBIOSVersion
            releaseDate   = if ($bios.ReleaseDate) { $bios.ReleaseDate.ToString('o') } else { $null }
            serialNumber  = $bios.SerialNumber
        }
        assetTag = ($enc | Select-Object -First 1).SMBIOSAssetTag
        operatingSystem = [ordered]@{
            caption              = $os.Caption
            version              = $os.Version
            buildNumber          = $os.BuildNumber
            osArchitecture       = $os.OSArchitecture
            installDate          = if ($os.InstallDate) { $os.InstallDate.ToString('o') } else { $null }
            lastBootUpTime       = if ($lastBoot) { $lastBoot.ToString('o') } else { $null }
            totalVisibleMemoryKB = $os.TotalVisibleMemorySize
            freePhysicalMemoryKB = $os.FreePhysicalMemory
        }
        timezone = $tz.Caption
        timezoneId = $tz.StandardName  # Stable identifier -- e.g. "Eastern Standard Time" -- used for US-only validation
        locale     = $(try { (Get-WinSystemLocale).Name } catch { try { (Get-Culture).Name } catch { $null } })
        uptime = [ordered]@{
            totalSeconds = [math]::Round($uptime.TotalSeconds, 0)
            formatted    = $uptimeStr
        }
        pixellot = [ordered]@{
            version      = $pixVersion
            imageVersion = $pixImageVersion
            vpuName      = $vpuName
            venueId      = $venueId
        }
        isNonVpuHost = $isNonVpuHost
    }

    $result | ConvertTo-Json -Depth 5 -Compress
}
catch {
    [ordered]@{
        error   = $true
        message = $_.Exception.Message
        script  = 'Get-SystemIdentity.ps1'
    } | ConvertTo-Json -Compress
}
