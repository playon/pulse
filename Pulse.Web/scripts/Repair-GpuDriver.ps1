#Requires -Version 5.1
<#
.SYNOPSIS
    Installs Pixellot's approved NVIDIA graphics driver when the card has no
    driver or shows an error. Action script: changes system state.
.DESCRIPTION
    Pulse form of the field one-liner:
        Invoke-WebRequest <536.67 installer> -OutFile C:\pixellot\downloadedversion\...
        Start-Process <installer> -ArgumentList "-s -clean -noreboot"

    Differences from the one-liner, each deliberate:
      - Does nothing unless Get-GpuDriverState says the card needs it, so a
        click on a healthy live VPU cannot reinstall its working driver.
      - not-detected: runs a PnP rescan (Device Manager's "Scan for hardware changes") first. If
        Windows still lists no NVIDIA card, stops BEFORE downloading ~1 GB:
        a driver cannot fix a card Windows cannot see.
      - Verifies the Authenticode signature is valid and NVIDIA's before
        running anything it downloaded. An already-downloaded copy is reused
        only if it passes the same check.
      - Downloads to a .download name and renames when complete, so an
        interrupted download is never mistaken for the installer.
      - Judges success by re-reading the card's state, not by the installer's
        exit code alone.

    Runs elevated (Pulse's launcher self-elevates); refuses with 'no-admin'
    otherwise. The display may go blank for a few seconds while the driver
    swaps. -noreboot is kept: the tech chooses when to restart.

    Emits one JSON object on stdout. Nothing else may print to stdout.
.PARAMETER DriverUrl
    Installer URL. Default is Pixellot's approved 536.67 build.
.PARAMETER DownloadDir
    Where the installer is saved. Default matches the field procedure.
#>
[CmdletBinding()]
param(
    [string]$DriverUrl    = 'https://software.pixellot.tv/apps/Drivers/536.67-desktop-win10-win11-64bit-international-nsd-dch-whql.exe',
    [string]$DownloadDir  = 'C:\pixellot\downloadedversion'
)

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'
. (Join-Path $PSScriptRoot '_GpuDriverCommon.ps1')

$t0            = Get-Date
$installerName = [System.IO.Path]::GetFileName(([Uri]$DriverUrl).AbsolutePath)
$installerPath = Join-Path $DownloadDir $installerName
$partialPath   = "$installerPath.download"
$minFreeBytes  = 4GB
$installWaitMs = 20 * 60 * 1000
$steps         = New-Object System.Collections.ArrayList

function Add-Step([string]$name, [bool]$ok, [string]$detail) {
    [void]$steps.Add([pscustomobject]@{ step = $name; ok = $ok; detail = $detail })
}

function Emit([string]$status, [string]$message, $before, $after, $exitCode) {
    [pscustomobject]@{
        status      = $status
        message     = $message
        stateBefore = $before
        stateAfter  = $after
        exitCode    = $exitCode
        installer   = $installerName
        steps       = $steps.ToArray()
        durationSec = [int]((Get-Date) - $t0).TotalSeconds
    } | ConvertTo-Json -Depth 5 -Compress
}

function Test-NvidiaSigned([string]$path) {
    $sig = Get-AuthenticodeSignature -LiteralPath $path
    $signer = $null
    if ($sig.SignerCertificate) { $signer = $sig.SignerCertificate.Subject }
    $ok = ($sig.Status -eq 'Valid') -and ($signer -match 'O=NVIDIA Corporation')
    return [pscustomobject]@{ ok = $ok; status = [string]$sig.Status; signer = $signer }
}

try {
    if (-not (Test-IsAdmin)) {
        Emit 'no-admin' 'Pulse is not running as administrator, so it cannot install a driver. Close Pulse and start it again, choosing Yes at the Windows prompt.' $null $null $null
        return
    }
    if ([Environment]::OSVersion.Version.Build -lt 10240) {
        Emit 'unsupported-os' 'This driver installer is for Windows 10 and 11. This VPU runs an older Windows, so Pulse will not install it.' $null $null $null
        return
    }

    # One run at a time: the page can be reloaded mid-install, and a second
    # installer on top of the first would corrupt both.
    $installerProc = @(Get-Process -ErrorAction SilentlyContinue |
        Where-Object { $_.ProcessName -eq [System.IO.Path]::GetFileNameWithoutExtension($installerName) })
    $otherRuns = @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'Repair-GpuDriver\.ps1' -and $_.ProcessId -ne $PID })
    if ($installerProc.Count -gt 0 -or $otherRuns.Count -gt 0) {
        Emit 'already-running' 'A graphics driver install is already running on this VPU. Wait for it to finish, then check again.' $null $null $null
        return
    }

    $before = Get-GpuDriverState
    Add-Step 'check card' $true $before.reason
    $state = $before

    if ($state.state -eq 'not-detected') {
        try {
            $scan = Invoke-HardwareRescan
            Add-Step 'rescan for hardware' $scan.ok "Windows hardware rescan returned code $($scan.code) (0 = success)"
        } catch {
            Add-Step 'rescan for hardware' $false "Could not run the rescan: $($_.Exception.Message)"
        }
        Start-Sleep -Seconds 8
        $state = Get-GpuDriverState
        Add-Step 'check card again' $true $state.reason
    }

    # A card that is merely turned off needs turning on, not a reinstall.
    if ($state.state -eq 'disabled') {
        foreach ($dev in @($state.devices | Where-Object { $_.state -eq 'disabled' })) {
            try {
                Enable-PnpDevice -InstanceId $dev.deviceId -Confirm:$false -ErrorAction Stop
                Add-Step 'turn the card on' $true $dev.name
            } catch {
                Add-Step 'turn the card on' $false "$($dev.name): $($_.Exception.Message)"
            }
        }
        Start-Sleep -Seconds 5
        $state = Get-GpuDriverState
        Add-Step 'check card again' $true $state.reason
        if ($state.state -eq 'ok') {
            Emit 'enabled' 'The graphics card was turned off and is now on, with its driver. Nothing was downloaded. Restart the VPU before the next event.' $before.state $state.state $null
            return
        }
        if ($state.state -eq 'disabled') {
            Emit 'enable-failed' 'The graphics card is turned off and Pulse could not turn it on. A driver reinstall will not fix that, so nothing was installed. In Device Manager right-click the card and choose Enable device. If that fails, check the BIOS.' $before.state $state.state $null
            return
        }
    }

    switch ($state.state) {
        'not-detected' {
            Emit 'not-detected' 'Windows still does not see an NVIDIA graphics card, so a driver cannot fix this. Nothing was downloaded. Check that the card is seated and its power cable is connected, then check the BIOS shows it. If it is, the card or its slot may be faulty.' $before.state $state.state $null
            return
        }
        'ok' {
            if ($before.state -eq 'not-detected') {
                Emit 'rescan-fixed' 'The rescan found the card and it has its driver. Restart the VPU before the next event.' $before.state $state.state $null
            } else {
                Emit 'not-needed' 'The graphics card already has its driver and shows no error, so nothing was changed.' $before.state $state.state $null
            }
            return
        }
        'reboot-needed' {
            Emit 'reboot-needed' 'The graphics card is only waiting for a restart. Restart the VPU; no driver install is needed.' $before.state $state.state $null
            return
        }
    }

    # -- Disk space: the download plus what the installer unpacks ----------
    if (-not (Test-Path -LiteralPath $DownloadDir)) {
        New-Item -ItemType Directory -Path $DownloadDir -Force | Out-Null
    }
    $drive = New-Object System.IO.DriveInfo([System.IO.Path]::GetPathRoot($DownloadDir))
    $freeGb = [math]::Round($drive.AvailableFreeSpace / 1GB, 1)
    if ($drive.AvailableFreeSpace -lt $minFreeBytes) {
        Add-Step 'check disk space' $false "$freeGb GB free on $($drive.Name)"
        Emit 'low-disk' "There is only $freeGb GB free on $($drive.Name). The driver needs about 4 GB to download and unpack. Free some space and try again." $before.state $state.state $null
        return
    }
    Add-Step 'check disk space' $true "$freeGb GB free on $($drive.Name)"

    # -- Download (reuse a complete, correctly signed copy) ----------------
    $haveGood = $false
    if (Test-Path -LiteralPath $installerPath) {
        $existing = Test-NvidiaSigned $installerPath
        if ($existing.ok) {
            $haveGood = $true
            Add-Step 'use existing download' $true $installerPath
        } else {
            Remove-Item -LiteralPath $installerPath -Force -ErrorAction SilentlyContinue
            Add-Step 'discard existing download' $true "signature $($existing.status)"
        }
    }
    if (-not $haveGood) {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]'Tls,Tls11,Tls12'
        try {
            if (Test-Path -LiteralPath $partialPath) { Remove-Item -LiteralPath $partialPath -Force }
            Invoke-WebRequest -Uri $DriverUrl -OutFile $partialPath -UseBasicParsing
            Move-Item -LiteralPath $partialPath -Destination $installerPath -Force
            $mb = [int]((Get-Item -LiteralPath $installerPath).Length / 1MB)
            Add-Step 'download driver' $true "$mb MB from $DriverUrl"
        } catch {
            Remove-Item -LiteralPath $partialPath -Force -ErrorAction SilentlyContinue
            Add-Step 'download driver' $false $_.Exception.Message
            Emit 'download-failed' "The driver could not be downloaded: $($_.Exception.Message) Check that this VPU can reach software.pixellot.tv on port 443 and that a venue firewall is not blocking it." $before.state $state.state $null
            return
        }
    }

    # -- Never run an unsigned or foreign installer ------------------------
    $sig = Test-NvidiaSigned $installerPath
    if (-not $sig.ok) {
        Remove-Item -LiteralPath $installerPath -Force -ErrorAction SilentlyContinue
        Add-Step 'verify signature' $false "status $($sig.status); signer $($sig.signer)"
        Emit 'bad-signature' "The downloaded file is not a valid NVIDIA-signed installer (signature: $($sig.status)), so it was deleted and not run. A venue firewall that rewrites downloads can cause this." $before.state $state.state $null
        return
    }
    Add-Step 'verify signature' $true $sig.signer

    # -- Install -----------------------------------------------------------
    $proc = Start-Process -FilePath $installerPath -ArgumentList '-s -clean -noreboot' -PassThru -ErrorAction Stop
    $null = $proc.Handle
    if (-not $proc.WaitForExit($installWaitMs)) {
        Add-Step 'run installer' $false 'still running after 20 minutes'
        Emit 'install-timeout' 'The driver installer was still running after 20 minutes. It was left running. Wait, then check the graphics card again before trying anything else.' $before.state $state.state $null
        return
    }
    $exitCode = $proc.ExitCode
    Add-Step 'run installer' $true "exit code $exitCode"

    # Windows re-enumerates the card a little after the installer exits.
    $final = Get-GpuDriverState
    $waited = 0
    while ($final.state -in @('no-driver', 'driver-error') -and $waited -lt 120) {
        Start-Sleep -Seconds 10
        $waited += 10
        $final = Get-GpuDriverState
    }
    Add-Step 'check card after install' ($final.state -in @('ok', 'reboot-needed')) $final.reason

    switch ($final.state) {
        'ok' {
            Emit 'installed' 'The NVIDIA driver is installed and the card shows no error. Restart the VPU before the next event so Pixellot starts cleanly with it.' $before.state $final.state $exitCode
        }
        'reboot-needed' {
            Emit 'installed-reboot' 'The NVIDIA driver is installed. Restart the VPU to finish; the card works after the restart.' $before.state $final.state $exitCode
        }
        default {
            Emit 'install-failed' "The installer finished (exit code $exitCode) but the card still is not working: $($final.reason)" $before.state $final.state $exitCode
        }
    }
}
catch {
    [pscustomobject]@{
        error   = $true
        message = $_.Exception.Message
        script  = 'Repair-GpuDriver.ps1'
        steps   = $steps.ToArray()
    } | ConvertTo-Json -Depth 5 -Compress
}
