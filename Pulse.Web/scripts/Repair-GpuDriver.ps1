#Requires -Version 5.1
<#
.SYNOPSIS
    Installs Pixellot's approved NVIDIA graphics driver for this card model
    when the card has no driver or shows an error. Action script: changes system state.
.DESCRIPTION
    Pulse form of the field one-liner:
        Invoke-WebRequest <approved installer> -OutFile C:\pixellot\downloadedversion\...
        Start-Process <installer> -ArgumentList "-s -clean -noreboot"
    The installer is chosen per card by PCI ID and subsystem (see the table in
    _GpuDriverCommon.ps1, each row checked against the package's INF). A card
    not in that table is refused ('unknown-card') before anything is downloaded.

    Differences from the one-liner, each deliberate:
      - Does nothing unless Get-GpuDriverState says the card needs it, so a
        click on a healthy live VPU cannot reinstall its working driver. The one
        exception is -Reinstall 1, which Pulse sends only after the technician
        confirms a warning that a working driver will be replaced.
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

    Pulse runs this DETACHED (gpu_job.py) with -StatusPath, so the install
    outlives a page reload, a browser that crashes while the display driver
    swaps, and Pulse itself closing. Progress then goes to the status file:
    the current stage, download bytes, the steps so far, a heartbeat at least
    every few seconds, and finally the same result object stdout gets.
.PARAMETER DownloadDir
    Where the installer is saved. Default matches the field procedure.
.PARAMETER Reinstall
    1 = install the approved driver even though the card works (a technician
    asked for it and confirmed in Pulse). Default 0: a working card is left alone.
.PARAMETER StatusPath
    Where to write progress JSON (Pulse passes
    C:\ProgramData\Pulse\gpu-driver-status.json). Empty = no status file.
.PARAMETER RunId
    Pulse's id for this run, echoed into the status file.
.PARAMETER Kind
    What the technician clicked (install, reinstall, rescan, enable), echoed
    into the status file so a reopened page shows the right steps.
#>
[CmdletBinding()]
param(
    [string]$DownloadDir  = 'C:\pixellot\downloadedversion',
    [int]$Reinstall = 0,
    [string]$StatusPath = '',
    [string]$RunId = '',
    [string]$Kind = ''
)

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'
. (Join-Path $PSScriptRoot '_GpuDriverCommon.ps1')

$t0            = Get-Date
$script:startedEpoch = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$installerName = $null
$installerPath = $null
$partialPath   = $null
$DriverUrl     = $null
$minFreeBytes  = 4GB
$installWaitMs = 20 * 60 * 1000
$steps         = New-Object System.Collections.ArrayList

$script:runStage   = 'checking'
$script:runMessage = ''
$script:bytesDone  = $null
$script:bytesTotal = $null
$stagesSeen        = New-Object System.Collections.ArrayList

function Add-Step([string]$name, [bool]$ok, [string]$detail) {
    [void]$steps.Add([pscustomobject]@{ step = $name; ok = $ok; detail = $detail })
}

# Writes the status file (no-op without -StatusPath). Called on every stage
# change and as a heartbeat inside every long wait, so Pulse can tell a slow
# install from a dead one. Written to a temp file and swapped in, so a reader
# never sees half a file. Never throws and never prints: a failed status
# write must not stop a driver install halfway.
function Write-RunStatus($result) {
    if (-not $StatusPath) { return }
    $json = $null
    try {
        $dir = Split-Path -Parent $StatusPath
        if ($dir -and -not (Test-Path -LiteralPath $dir)) { $null = New-Item -ItemType Directory -Path $dir -Force }
        $json = [pscustomobject]@{
            runId         = $RunId
            kind          = $Kind
            pid           = $PID
            reinstall     = ($Reinstall -ne 0)
            stage         = $script:runStage
            message       = $script:runMessage
            stagesSeen    = $stagesSeen.ToArray()
            bytesDone     = $script:bytesDone
            bytesTotal    = $script:bytesTotal
            steps         = $steps.ToArray()
            startedEpoch  = $script:startedEpoch
            updatedEpoch  = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
            updatedAt     = (Get-Date).ToUniversalTime().ToString('o')
            result        = $result
        } | ConvertTo-Json -Depth 6 -Compress
        $tmp = "$StatusPath.tmp"
        [IO.File]::WriteAllText($tmp, $json, (New-Object System.Text.UTF8Encoding($false)))
        if (Test-Path -LiteralPath $StatusPath) {
            [IO.File]::Replace($tmp, $StatusPath, [NullString]::Value)
        } else {
            [IO.File]::Move($tmp, $StatusPath)
        }
    } catch {
        # Pulse may be reading the file at this instant; a direct write is
        # second best but still moves the heartbeat on.
        if ($json) { try { [IO.File]::WriteAllText($StatusPath, $json, (New-Object System.Text.UTF8Encoding($false))) } catch { } }
    }
}

function Set-Stage([string]$name, [string]$message) {
    $script:runStage   = $name
    $script:runMessage = $message
    if ($stagesSeen.Count -eq 0 -or $stagesSeen[$stagesSeen.Count - 1] -ne $name) { [void]$stagesSeen.Add($name) }
    Write-RunStatus $null
}

function Emit([string]$status, [string]$message, $before, $after, $exitCode) {
    $o = [pscustomobject]@{
        status      = $status
        message     = $message
        stateBefore = $before
        stateAfter  = $after
        exitCode    = $exitCode
        installer   = $installerName
        steps       = $steps.ToArray()
        durationSec = [int]((Get-Date) - $t0).TotalSeconds
    }
    $script:runStage   = 'done'
    $script:runMessage = $message
    Write-RunStatus $o
    $o | ConvertTo-Json -Depth 5 -Compress
}

# Streams the download to disk in 1 MB chunks so the status file can report
# how far it has got (Invoke-WebRequest blocks silently for the whole ~700 MB).
# ReadWriteTimeout fails a download that stalls instead of hanging for ever.
function Save-WithProgress([string]$url, [string]$dest) {
    $req = [Net.HttpWebRequest]::Create($url)
    $req.Timeout = 60000
    $req.ReadWriteTimeout = 120000
    $resp = $req.GetResponse()
    try {
        $total = [long]$resp.ContentLength
        if ($total -gt 0) { $script:bytesTotal = $total } else { $script:bytesTotal = $null }
        $script:bytesDone = [long]0
        $in  = $resp.GetResponseStream()
        $out = [IO.File]::Create($dest)
        try {
            $buf  = New-Object byte[] (1MB)
            $done = [long]0
            $beat = Get-Date
            while (($n = $in.Read($buf, 0, $buf.Length)) -gt 0) {
                $out.Write($buf, 0, $n)
                $done += $n
                if (((Get-Date) - $beat).TotalSeconds -ge 2) {
                    $script:bytesDone = $done
                    Write-RunStatus $null
                    $beat = Get-Date
                }
            }
            $script:bytesDone = $done
        } finally {
            $out.Close()
            $in.Close()
        }
        if ($total -gt 0 -and $done -ne $total) { throw "The download stopped early ($done of $total bytes)." }
    } finally {
        $resp.Close()
    }
}

function Test-NvidiaSigned([string]$path) {
    $sig = Get-AuthenticodeSignature -LiteralPath $path
    $signer = $null
    if ($sig.SignerCertificate) { $signer = $sig.SignerCertificate.Subject }
    $ok = ($sig.Status -eq 'Valid') -and ($signer -match 'O=NVIDIA Corporation')
    return [pscustomobject]@{ ok = $ok; status = [string]$sig.Status; signer = $signer }
}

try {
    Set-Stage 'checking' 'Checking the graphics card.'
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
        Where-Object { $_.ProcessName -match '^\d+\.\d+-desktop-win10-win11' })
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
        Set-Stage 'rescanning' 'Asking Windows to rescan for the graphics card.'
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
        Set-Stage 'enabling' 'Turning the graphics card on.'
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
        if ($state.state -eq 'ok' -and $Reinstall -eq 0) {
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
                return
            }
            if ($Reinstall -eq 0) {
                Emit 'not-needed' 'The graphics card already has its driver and shows no error, so nothing was changed.' $before.state $state.state $null
                return
            }
            # Reinstall requested on a working card: carry on to the install below.
            Add-Step 'reinstall requested' $true 'the card works; reinstalling the approved driver because the technician asked'
        }
        'reboot-needed' {
            Emit 'reboot-needed' 'The graphics card is only waiting for a restart. Restart the VPU; no driver install is needed.' $before.state $state.state $null
            return
        }
    }

    # -- Choose the approved driver for THIS card; unknown cards fail closed
    Set-Stage 'preparing' 'Choosing the approved driver and checking disk space.'
    $target = @($state.devices | Where-Object { $_.state -in @('no-driver', 'driver-error') })[0]
    if (-not $target -and $Reinstall -ne 0) {
        # Reinstall on request: the card works, the tech wants the approved driver anyway.
        $target = @($state.devices | Where-Object { $_.state -eq 'ok' })[0]
    }
    $approved = $null
    if ($target) { $approved = Get-ApprovedDriver $target.deviceId }
    if (-not $approved -or -not $approved.known) {
        $idText = 'unknown PCI ID'
        if ($approved) { $idText = "PCI ID 10DE:$($approved.pciId)" }
        Add-Step 'choose driver' $false "no approved driver for this card ($idText)"
        Emit 'unknown-card' "Pulse has no approved driver for this graphics card ($idText), so it installed nothing. Install the driver Pixellot support approves for this card by hand, and ask Pixellot to add this card to Pulse." $before.state $state.state $null
        return
    }
    $DriverUrl     = $approved.url
    $installerName = $approved.file
    $installerPath = Join-Path $DownloadDir $installerName
    $partialPath   = "$installerPath.download"
    Add-Step 'choose driver' $true "$($approved.card): driver $($approved.version) (PCI ID 10DE:$($approved.pciId))"

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
    Set-Stage 'downloading' 'Downloading the driver.'
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
            Save-WithProgress $DriverUrl $partialPath
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
    Set-Stage 'verifying' 'Checking the installer is signed by NVIDIA.'
    $sig = Test-NvidiaSigned $installerPath
    if (-not $sig.ok) {
        Remove-Item -LiteralPath $installerPath -Force -ErrorAction SilentlyContinue
        Add-Step 'verify signature' $false "status $($sig.status); signer $($sig.signer)"
        Emit 'bad-signature' "The downloaded file is not a valid NVIDIA-signed installer (signature: $($sig.status)), so it was deleted and not run. A venue firewall that rewrites downloads can cause this." $before.state $state.state $null
        return
    }
    Add-Step 'verify signature' $true $sig.signer

    # -- Install -----------------------------------------------------------
    Set-Stage 'installing' 'Installing the driver. The screen goes black for a few seconds, maybe more than once, while Windows swaps the driver.'
    $proc = Start-Process -FilePath $installerPath -ArgumentList '-s -clean -noreboot' -PassThru -ErrorAction Stop
    $null = $proc.Handle
    $installDeadline = (Get-Date).AddMilliseconds($installWaitMs)
    $installExited = $false
    while ($true) {
        if ($proc.WaitForExit(3000)) { $installExited = $true; break }
        if ((Get-Date) -gt $installDeadline) { break }
        Write-RunStatus $null
    }
    if (-not $installExited) {
        Add-Step 'run installer' $false 'still running after 20 minutes'
        Emit 'install-timeout' 'The driver installer was still running after 20 minutes. It was left running. Wait, then check the graphics card again before trying anything else.' $before.state $state.state $null
        return
    }
    $exitCode = $proc.ExitCode
    Add-Step 'run installer' $true "exit code $exitCode"

    # Windows re-enumerates the card a little after the installer exits.
    Set-Stage 'confirming' 'Checking the card works with the new driver.'
    $final = Get-GpuDriverState
    $waited = 0
    while ($final.state -in @('no-driver', 'driver-error') -and $waited -lt 120) {
        Write-RunStatus $null
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
    $o = [pscustomobject]@{
        error   = $true
        message = $_.Exception.Message
        script  = 'Repair-GpuDriver.ps1'
        steps   = $steps.ToArray()
    }
    $script:runStage   = 'done'
    $script:runMessage = $_.Exception.Message
    Write-RunStatus $o
    $o | ConvertTo-Json -Depth 5 -Compress
}
