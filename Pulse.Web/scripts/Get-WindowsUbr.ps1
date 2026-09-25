#Requires -Version 5.1
<#
.SYNOPSIS
    Reads the Windows Update Build Revision (UBR) from the registry.
.DESCRIPTION
    Hidden diagnostic. It has no nav entry and is reached only through the
    About-tab key sequence documented in Pulse.Web/docs/HOW-TO-USE.md.

    The UBR is the part of the OS build that "17763" alone hides. 17763.253
    is the 1809 RTM state Pixellot ships units in (pktmon there cannot
    capture packets); a patched unit reports something like 17763.8880.

    Always emits JSON, even when the value is missing.
#>
[CmdletBinding()]
param()

$result = $null

try {
    $regPath = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
    $props = Get-ItemProperty $regPath -ErrorAction Stop

    $ubr = $props.UBR
    $build = $props.CurrentBuild
    $full = $null
    if ($build -and $null -ne $ubr) { $full = "$build.$ubr" }

    $result = [ordered]@{
        ubr          = $ubr
        currentBuild = $build
        fullBuild    = $full
        registryKey  = $regPath
    }
}
catch {
    $result = [ordered]@{
        error   = $true
        message = $_.Exception.Message
        script  = 'Get-WindowsUbr.ps1'
    }
}

$result | ConvertTo-Json -Depth 3 -Compress
