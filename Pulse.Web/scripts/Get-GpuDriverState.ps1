#Requires -Version 5.1
<#
.SYNOPSIS
    Reports whether the NVIDIA graphics card is present, has its driver, and
    is free of Device Manager errors. Read-only.
.DESCRIPTION
    Feeds the Graphics driver card on Pulse's Hardware page, which offers
    Repair-GpuDriver.ps1 when the state is not 'ok'.

    state:
      ok             NVIDIA card present, NVIDIA driver bound, no error
      no-driver      card present, no NVIDIA driver (Device Manager code 28,
                     or only Windows' Basic Display driver)
      driver-error   card present, Device Manager shows another error code
      disabled       card present but turned off (code 22)
      reboot-needed  card present, code 14 (restart pending)
      not-detected   no NVIDIA display device on the PCI bus at all; a driver
                     cannot fix this (seating, power, BIOS)

    approvedDriver is the version Pulse would install for the first card that
    needs it (null = a card Pixellot has not approved a driver for, so Pulse
    offers no install). Outputs one JSON object on stdout.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_GpuDriverCommon.ps1')

try {
    $s = Get-GpuDriverState
    $target = @($s.devices | Where-Object { $_.state -ne 'ok' })[0]
    if (-not $target) { $target = @($s.devices)[0] }
    $ad = $null
    if ($target) { $ad = Get-ApprovedDriver $target.deviceId }
    $approvedVersion = $null
    $approvedCard    = $null
    $pciId           = $null
    if ($ad) { $pciId = $ad.pciId; $approvedVersion = $ad.version; $approvedCard = $ad.card }

    [pscustomobject]@{
        state          = $s.state
        reason         = $s.reason
        devices        = $s.devices
        pciId          = $pciId
        approvedDriver = $approvedVersion
        approvedCard   = $approvedCard
        isAdmin        = (Test-IsAdmin)
        osBuild        = [Environment]::OSVersion.Version.Build
        checkedAt      = (Get-Date).ToString('o')
    } | ConvertTo-Json -Depth 5 -Compress
}
catch {
    [pscustomobject]@{
        error   = $true
        message = $_.Exception.Message
        script  = 'Get-GpuDriverState.ps1'
    } | ConvertTo-Json -Compress
}
