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
      reboot-needed  card present, code 14 (restart pending)
      not-detected   no NVIDIA display device on the PCI bus at all; a driver
                     cannot fix this (seating, power, BIOS)

    Outputs one JSON object on stdout.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_GpuDriverCommon.ps1')

try {
    $s = Get-GpuDriverState
    [pscustomobject]@{
        state     = $s.state
        reason    = $s.reason
        devices   = $s.devices
        isAdmin   = (Test-IsAdmin)
        osBuild   = [Environment]::OSVersion.Version.Build
        checkedAt = (Get-Date).ToString('o')
    } | ConvertTo-Json -Depth 5 -Compress
}
catch {
    [pscustomobject]@{
        error   = $true
        message = $_.Exception.Message
        script  = 'Get-GpuDriverState.ps1'
    } | ConvertTo-Json -Compress
}
