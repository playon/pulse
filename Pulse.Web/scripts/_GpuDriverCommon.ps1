# _GpuDriverCommon.ps1 - dot-sourced by Get-GpuDriverState.ps1 and
# Repair-GpuDriver.ps1. Not a collector: it prints nothing on its own.
#
# ASCII ONLY (Windows PowerShell 5.1 reads a BOM-less .ps1 as CP-1252).
#
# Why this is not Win32_VideoController: a card with no driver is either absent
# from that class or shows up as "Microsoft Basic Display Adapter" with a
# Microsoft vendor, so it cannot tell "no card" from "card, no driver". The PnP
# tree can: every NVIDIA (PCI vendor 10DE) display-class device is listed there
# whether or not a driver is bound, with Device Manager's own error code.

function Test-IsAdmin {
    try {
        $id = [Security.Principal.WindowsIdentity]::GetCurrent()
        $pr = New-Object Security.Principal.WindowsPrincipal($id)
        return [bool]$pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } catch {
        return $false
    }
}

function Get-ProblemText([int]$code) {
    switch ($code) {
        0  { return $null }
        10 { return 'The device could not start.' }
        12 { return 'The device cannot find enough free resources to use.' }
        14 { return 'The device needs a restart before it will work.' }
        22 { return 'The device is disabled in Device Manager.' }
        28 { return 'No driver is installed for the device.' }
        31 { return 'Windows could not load the driver, so the device is not working properly.' }
        39 { return 'Windows could not load the driver (it may be missing or corrupt).' }
        43 { return 'Windows stopped the device because it reported problems.' }
        52 { return 'Windows cannot verify the digital signature of the driver.' }
        default { return "Device Manager error code $code." }
    }
}

# Returns a [pscustomobject]:
#   state   ok | no-driver | driver-error | disabled | reboot-needed | not-detected
#   reason  one plain sentence for the state
#   devices one row per NVIDIA display device the PnP tree lists
# Throws if the PnP query or the driver lookup fails, or if the PnP tree comes
# back with no devices at all: the caller reports that as "could not check",
# never as "no card" or "healthy".
function Get-GpuDriverState {
    $all = @(Get-CimInstance -ClassName Win32_PnPEntity -ErrorAction Stop)
    if ($all.Count -eq 0) { throw 'Windows returned an empty device list, so the graphics card could not be checked.' }
    $pnp = @($all | Where-Object { $_.PNPDeviceID -like 'PCI\VEN_10DE&*' })

    $rows = New-Object System.Collections.ArrayList
    foreach ($d in $pnp) {
        # Display class is 03xx; a device with no driver has no PNPClass yet,
        # so read the class code from its hardware IDs.
        $hwIds = @($d.HardwareID)
        $isDisplay = ($d.PNPClass -eq 'Display') -or (@($hwIds | Where-Object { $_ -match 'CC_03' }).Count -gt 0)
        if (-not $isDisplay) { continue }

        $code = 0
        if ($null -ne $d.ConfigManagerErrorCode) { $code = [int]$d.ConfigManagerErrorCode }

        $provider = $null
        $version  = $null
        $escaped = $d.PNPDeviceID.Replace('\', '\\')
        $drv = Get-CimInstance -ClassName Win32_PnPSignedDriver -Filter "DeviceID='$escaped'" -ErrorAction Stop |
            Select-Object -First 1
        if ($drv) {
            $provider = $drv.DriverProviderName
            $version  = $drv.DriverVersion
        }

        # Healthy only if no Device Manager error AND NVIDIA's own driver is
        # bound. Windows quietly binds its Basic Display driver to a card with
        # no NVIDIA driver; that reports error code 0 but is not a working card.
        $nvidiaDriver = ($provider -match 'NVIDIA') -or ((-not $provider) -and ($d.Name -match 'NVIDIA'))
        $state = 'ok'
        if     ($code -eq 14) { $state = 'reboot-needed' }
        elseif ($code -eq 22) { $state = 'disabled' }
        elseif ($code -eq 28) { $state = 'no-driver' }
        elseif ($code -ne 0)  { $state = 'driver-error' }
        elseif (-not $nvidiaDriver) { $state = 'no-driver' }

        [void]$rows.Add([pscustomobject]@{
            name           = [string]$d.Name
            deviceId       = [string]$d.PNPDeviceID
            state          = $state
            errorCode      = $code
            problem        = (Get-ProblemText $code)
            driverProvider = $provider
            driverVersion  = $version
        })
    }

    $devices = $rows.ToArray()
    if ($devices.Count -eq 0) {
        return [pscustomobject]@{
            state   = 'not-detected'
            reason  = 'Windows does not list any NVIDIA graphics card on the PCI bus.'
            devices = $devices
        }
    }

    # Worst device wins; the order only decides which sentence the tech reads.
    $state = 'ok'
    foreach ($candidate in @('driver-error', 'no-driver', 'disabled', 'reboot-needed')) {
        if (@($devices | Where-Object { $_.state -eq $candidate }).Count -gt 0) { $state = $candidate; break }
    }
    $worst = @($devices | Where-Object { $_.state -eq $state })[0]
    $reason = switch ($state) {
        'ok'            { 'The NVIDIA graphics card has its NVIDIA driver and Windows reports no error.' }
        'no-driver'     { "Windows sees the NVIDIA card ($($worst.name)) but it has no NVIDIA graphics driver." }
        'driver-error'  { "The NVIDIA card ($($worst.name)) shows an error in Device Manager: $($worst.problem) (code $($worst.errorCode))." }
        'disabled'      { "The NVIDIA card ($($worst.name)) is turned off in Device Manager." }
        'reboot-needed' { "The NVIDIA card ($($worst.name)) is waiting for a restart before it will work." }
    }
    return [pscustomobject]@{ state = $state; reason = $reason; devices = $devices }
}

# "Scan for hardware changes", the Device Manager button, as a direct call to
# the Configuration Manager API. Used instead of `pnputil /scan-devices`,
# whose newer switches may be missing on the Win10 1809 fleet image (not
# verified either way). The C# is
# C#5-compatible (Add-Type on 5.1 compiles with the old CodeDom compiler).
# Returns the CONFIGRET code so a failed rescan is reported as failed.
function Invoke-HardwareRescan {
    if (-not ('Pulse.PnpRescan' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace Pulse {
    public static class PnpRescan {
        [DllImport("cfgmgr32.dll", CharSet = CharSet.Unicode)]
        static extern int CM_Locate_DevNodeW(out uint devInst, IntPtr deviceId, uint flags);
        [DllImport("cfgmgr32.dll")]
        static extern int CM_Reenumerate_DevNode(uint devInst, uint flags);
        // CR_SUCCESS is 0. A null device ID locates the root of the device tree;
        // flag 1 is CM_REENUMERATE_SYNCHRONOUS.
        public static int Run() {
            uint root;
            int cr = CM_Locate_DevNodeW(out root, IntPtr.Zero, 0);
            if (cr != 0) { return cr; }
            return CM_Reenumerate_DevNode(root, 1);
        }
    }
}
'@
    }
    $cr = [Pulse.PnpRescan]::Run()
    return [pscustomobject]@{ ok = ($cr -eq 0); code = $cr }
}
