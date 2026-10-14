#Requires -Version 5.1
<#
.SYNOPSIS
    Decides whether an NVIDIA GPU on a Windows VPU is genuinely faulty, or
    whether the Pixellot HwDetector failure ("gpu type is: N/A" /
    "failed to use the QSV or NVENC decoder or CUDA") has a software cause.
.DESCRIPTION
    Works bottom-up through the layers that must all hold for NVENC/CUDA:
        1. Fleet-correlation facts (driver, OS build, BIOS, recent updates)
        2. Is the GPU on the PCI bus at all?
        3. PnP / driver state and problem codes
        4. nvidia-smi / NVML health, thermals, encoder contention
        5. Event log history (nvlddmkm TDR, WHEA PCIe, PnP)
        6. Functional NVENC + CUDA decode test - the actual proof
    Prints a report and writes a JSON summary so results from several
    units can be compared to find the common factor.
.PARAMETER OutDir
    Where to write the JSON + log. Defaults to the current directory.
.PARAMETER SkipFunctionalTest
    Skip the ffmpeg encode/decode test (it briefly loads the GPU).
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\Get-GpuTriage.ps1
.NOTES
    Windows PowerShell 5.1 compatible. Pure ASCII. Run as Administrator for
    the full event-log and PnP picture.
    Exit codes: 0 NOT_HARDWARE  1 SOFTWARE_FAULT  2 HARDWARE_SUSPECT  3 INCONCLUSIVE
#>
[CmdletBinding()]
param(
    [string]$OutDir = '.',
    [switch]$SkipFunctionalTest
)

$ErrorActionPreference = 'Continue'
$VERSION = '1.0'

$hwEvidence = New-Object System.Collections.ArrayList
$swEvidence = New-Object System.Collections.ArrayList
$notes      = New-Object System.Collections.ArrayList

function Add-Hw   { param([string]$m) $null = $hwEvidence.Add($m) }
function Add-Sw   { param([string]$m) $null = $swEvidence.Add($m) }
function Add-Note { param([string]$m) $null = $notes.Add($m) }
function Write-Section { param([string]$t) Write-Host ''; Write-Host ("=== " + $t + " ===") }

$hostName = $env:COMPUTERNAME
$stamp    = Get-Date -Format 'yyyyMMdd-HHmmss'
if (-not (Test-Path $OutDir)) { $null = New-Item -ItemType Directory -Path $OutDir -Force }
$jsonPath = Join-Path $OutDir ("gpu-triage-$hostName-$stamp.json")
$logPath  = Join-Path $OutDir ("gpu-triage-$hostName-$stamp.log")
try { Start-Transcript -Path $logPath -Force | Out-Null } catch { }

$isAdmin = $false
try {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $pr = New-Object Security.Principal.WindowsPrincipal($id)
    $isAdmin = $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
} catch { }

Write-Host ("NVIDIA GPU triage v" + $VERSION)
Write-Host ("host: $hostName   date: " + (Get-Date -Format 'o') + "   admin: $isAdmin")
if (-not $isAdmin) { Write-Host 'WARNING: not elevated - event log and PnP property checks will be degraded.' }

# ==========================================================================
Write-Section '1. HOST / FLEET CORRELATION FACTS'
# Compare these fields across every unit that failed. If eight units share a
# driver version, an OS build, or an update date, the GPUs are not the
# common factor and the RMAs are being sent for a software regression.
# ==========================================================================
$os = $null; $cs = $null; $bios = $null
try { $os   = Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue } catch { }
try { $cs   = Get-CimInstance Win32_ComputerSystem  -ErrorAction SilentlyContinue } catch { }
try { $bios = Get-CimInstance Win32_BIOS            -ErrorAction SilentlyContinue } catch { }

$osBuild = ''
try { $osBuild = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion' -ErrorAction SilentlyContinue).BuildLabEx } catch { }
$uptimeStr = ''
if ($os -and $os.LastBootUpTime) {
    $up = (Get-Date) - $os.LastBootUpTime
    $uptimeStr = '{0}d {1}h {2}m' -f $up.Days, $up.Hours, $up.Minutes
}
Write-Host ('model       : ' + $(if ($cs) { $cs.Manufacturer + ' ' + $cs.Model } else { 'unknown' }))
Write-Host ('os          : ' + $(if ($os) { $os.Caption + ' ' + $os.Version } else { 'unknown' }))
Write-Host ('build lab   : ' + $osBuild)
Write-Host ('bios        : ' + $(if ($bios) { $bios.SMBIOSBIOSVersion + ' (' + $bios.ReleaseDate + ')' } else { 'unknown' }))
Write-Host ('uptime      : ' + $uptimeStr)

Write-Host '-- last 6 installed hotfixes (correlate with failure onset) --'
try {
    Get-HotFix -ErrorAction SilentlyContinue |
        Sort-Object InstalledOn -Descending |
        Select-Object -First 6 HotFixID, Description, InstalledOn |
        Format-Table -AutoSize | Out-String | Write-Host
} catch { Write-Host '  (hotfix query failed)' }

# ==========================================================================
Write-Section '2. IS THE GPU ON THE PCI BUS AT ALL?'
# "gpu type is: N/A, intelGpu: UHD Graphics 770" means the detector saw the
# Intel iGPU and nothing else. Establish first whether a 10DE device is even
# enumerated - an absent card is a seating/BIOS/build question, not silicon.
# ==========================================================================
$nvPnp = @()
$allPnp = @()
$enumOk = $false   # did the PCI enumeration actually work at all?
try {
    $allPnp = @(Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue |
                Where-Object { $_.PNPDeviceID -and $_.PNPDeviceID.StartsWith('PCI\') })
    $nvPnp = @($allPnp | Where-Object { $_.PNPDeviceID -match 'VEN_10DE' })
} catch { }
# A WMI repository that cannot enumerate ANY PCI device has not proved the GPU
# is missing - it has proved WMI is broken. On the 2019-era fleet image that is
# a real failure mode, and mistaking it for an absent card causes a wrong RMA.
if ($allPnp.Count -gt 0) { $enumOk = $true }

$pciPresent = ($nvPnp.Count -gt 0)
$devIdStr = ''
if ($pciPresent) {
    foreach ($d in $nvPnp) {
        Write-Host ('  ' + $d.Name + '  [' + $d.PNPDeviceID + ']  status=' + $d.Status + ' cmErr=' + $d.ConfigManagerErrorCode)
    }
    $m = [regex]::Match($nvPnp[0].PNPDeviceID, 'VEN_10DE&DEV_([0-9A-Fa-f]{4})')
    if ($m.Success) { $devIdStr = '10DE:' + $m.Groups[1].Value.ToUpper() }
    Add-Note ('NVIDIA PCI device present: ' + $devIdStr)
} elseif ($enumOk) {
    Write-Host ('  NO NVIDIA (VEN_10DE) DEVICE FOUND ON THE PCI BUS (' + $allPnp.Count + ' other PCI devices enumerated fine).')
    Add-Hw 'No NVIDIA device enumerated on the PCI bus - card absent, unseated, disabled in BIOS, or dead'
    Add-Note 'Confirm the chassis actually contains a discrete GPU, and that BIOS primary display / Above 4G Decoding were not changed'
} else {
    Write-Host '  PCI enumeration returned NOTHING - not even non-NVIDIA devices.'
    Add-Note 'WMI/PnP enumerated zero PCI devices - the inspection failed, so this run cannot say whether a GPU is fitted. Check the WMI repository (winmgmt /verifyrepository) and re-run.'
}

Write-Host '-- all display adapters (Win32_VideoController) --'
$videoControllers = @()
try {
    $videoControllers = @(Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue)
    foreach ($v in $videoControllers) {
        Write-Host ('  ' + $v.Name + '  drv=' + $v.DriverVersion + '  date=' + $v.DriverDate + '  status=' + $v.Status + '  cmErr=' + $v.ConfigManagerErrorCode)
    }
} catch { }
if ($videoControllers.Count -gt 0) { $enumOk = $true }
$nvVideo = @($videoControllers | Where-Object { $_.Name -match '(?i)NVIDIA|Quadro|RTX|GeForce|Tesla|^T\d{3,4}' })
if ($nvVideo.Count -eq 0 -and $pciPresent) {
    Add-Sw 'GPU is on the PCI bus but Windows exposes no NVIDIA display adapter - the display driver is not installed or not loading'
}

# Ghost entries: a device Windows has seen before but cannot see now is the
# signature of a card that dropped out, as opposed to one never fitted.
try {
    $ghosts = @(Get-PnpDevice -ErrorAction SilentlyContinue |
                Where-Object { $_.InstanceId -match 'VEN_10DE' -and $_.Status -ne 'OK' })
    if ($ghosts.Count -gt 0) {
        Write-Host '-- non-OK / previously-seen NVIDIA PnP entries --'
        foreach ($g in $ghosts) { Write-Host ('  ' + $g.Status + '  ' + $g.FriendlyName + '  ' + $g.InstanceId) }
        if (-not $pciPresent) {
            Add-Hw 'Windows has a record of an NVIDIA device that is no longer present - the card dropped off the bus'
        }
    }
} catch { }

# ==========================================================================
Write-Section '3. PNP / DRIVER STATE'
# Problem codes separate "driver refused to load" from "device reports a
# fault". Code 43 is deliberately ambiguous and is NOT by itself an RMA.
# ==========================================================================
$cmErrText = @{
    0='OK'; 1='Not configured correctly'; 3='Driver corrupted or out of memory';
    10='Device cannot start'; 12='Cannot find enough free resources';
    14='Requires a restart'; 18='Reinstall the drivers'; 19='Registry corrupt';
    21='Windows is removing the device'; 22='Device is disabled';
    24='Device not present / not working'; 28='Drivers not installed';
    31='Device not working properly (driver failed to load)';
    43='Windows stopped this device because it reported problems';
    45='Not currently connected to the computer'
}
foreach ($d in $nvPnp) {
    $code = $d.ConfigManagerErrorCode
    if ($null -eq $code) {
        # Do NOT let a null code fall through to [int]$null = 0 = "OK".
        Write-Host ('  ' + $d.Name + ' -> no ConfigManagerErrorCode reported')
        Add-Note 'PnP reported no ConfigManagerErrorCode for the NVIDIA device - state unknown from this source'
        continue
    }
    $txt = $cmErrText[[int]$code]
    if (-not $txt) { $txt = 'code ' + $code }
    Write-Host ('  ' + $d.Name + ' -> ' + $code + ' : ' + $txt)
    switch ([int]$code) {
        0  { Add-Note 'PnP reports the NVIDIA device as working (code 0)' }
        22 { Add-Sw 'NVIDIA device is DISABLED in Device Manager - enable it; not a hardware fault' }
        28 { Add-Sw 'No driver installed for the NVIDIA device (code 28) - install the driver; not a hardware fault' }
        31 { Add-Sw 'Driver failed to load (code 31) - clean-install the NVIDIA driver before considering an RMA' }
        43 { Add-Note 'Code 43 - ambiguous by design. Clean driver reinstall AND a reseat must both be tried before RMA' }
        10 { Add-Note 'Code 10 (cannot start) - driver or device; reseat plus clean driver reinstall before RMA' }
        12 { Add-Sw 'Resource conflict (code 12) - check BIOS Above 4G Decoding / Resizable BAR' }
        45 { Add-Hw 'Device reported as not connected (code 45)' }
        default { Add-Note ('PnP problem code ' + $code + ' on the NVIDIA device: ' + $txt) }
    }
}

# PCIe link state. A card that enumerates but trained narrow or slow is a
# seating/riser/slot problem, and a reseat fixes it far more often than an RMA.
Write-Host '-- PCIe link state --'
foreach ($d in $nvPnp) {
    try {
        $props = Get-PnpDeviceProperty -InstanceId $d.PNPDeviceID -ErrorAction SilentlyContinue |
                 Where-Object { $_.KeyName -match 'LinkWidth|LinkSpeed|LocationInfo|CurrentSpeedAndMode' }
        if (-not $props) { Write-Host '  (link properties not exposed by this driver/OS)'; continue }
        $curW = $null; $maxW = $null
        foreach ($pr in $props) {
            Write-Host ('  ' + $pr.KeyName + ' = ' + $pr.Data)
            if ($pr.KeyName -match 'CurrentLinkWidth') { $curW = $pr.Data }
            if ($pr.KeyName -match 'MaxLinkWidth')     { $maxW = $pr.Data }
        }
        if ($null -ne $curW -and $null -ne $maxW -and [int]$curW -gt 0 -and [int]$curW -lt [int]$maxW) {
            Add-Hw ('PCIe link trained DEGRADED: x' + $curW + ' of x' + $maxW + ' capable - reseat the card/riser before RMA')
        }
    } catch {
        Write-Host '  (link property query failed)'
    }
}

Write-Host '-- signed driver package --'
try {
    $drv = @(Get-CimInstance Win32_PnPSignedDriver -ErrorAction SilentlyContinue |
             Where-Object { $_.DeviceName -match '(?i)NVIDIA|Quadro|RTX|GeForce' })
    foreach ($d in $drv) {
        Write-Host ('  ' + $d.DeviceName + '  ver=' + $d.DriverVersion + '  date=' + $d.DriverDate + '  inf=' + $d.InfName + '  provider=' + $d.DriverProviderName)
        if ($d.DriverProviderName -and $d.DriverProviderName -match '(?i)Microsoft') {
            Add-Sw 'A Microsoft-supplied (Windows Update) display driver is bound instead of the NVIDIA package - NVENC/CUDA will not work; reinstall the NVIDIA driver'
        }
    }
    if ($drv.Count -eq 0) { Write-Host '  (no NVIDIA driver package registered)' }
} catch { }

Write-Host '-- nvlddmkm kernel driver file --'
# Modern drivers (incl. fleet 536.67) load nvlddmkm.sys from the DriverStore
# package folder, NOT System32\drivers - a healthy 3667 unit has no copy there.
# Verified on Mountain View WY 2026-08-27. So check BOTH locations.
$sysRoot = $env:SystemRoot
if (-not $sysRoot) { $sysRoot = 'C:\Windows' }
$nvKernels = @()
$legacy = Join-Path $sysRoot 'System32\drivers\nvlddmkm.sys'
if (Test-Path $legacy) { $nvKernels += Get-Item $legacy }
$storeRoot = Join-Path $sysRoot 'System32\DriverStore\FileRepository'
try {
    $nvKernels += @(Get-ChildItem -Path $storeRoot -Directory -Filter 'nv_disp*' -ErrorAction SilentlyContinue |
        ForEach-Object { Get-ChildItem -Path $_.FullName -Filter 'nvlddmkm.sys' -Recurse -ErrorAction SilentlyContinue })
} catch { }
if ($nvKernels.Count -gt 0) {
    foreach ($f in $nvKernels) {
        Write-Host ('  ' + $f.FullName)
        Write-Host ('    ver=' + $f.VersionInfo.FileVersion + '  written=' + $f.LastWriteTime)
    }
} else {
    Write-Host '  nvlddmkm.sys NOT present in System32\drivers or any DriverStore nv_disp* package'
    Add-Sw 'nvlddmkm.sys absent from System32\drivers AND the DriverStore - no NVIDIA kernel driver on this machine'
}

# ==========================================================================
Write-Section '4. NVIDIA-SMI / NVML'
# ==========================================================================
$smiOk = $false
$smiPath = $null
$driverVersion = ''
$gpuName = ''
$progFiles = ${env:ProgramFiles}
if (-not $progFiles) { $progFiles = 'C:\Program Files' }
$candidates = @(
    (Join-Path $sysRoot 'System32\nvidia-smi.exe'),
    (Join-Path $progFiles 'NVIDIA Corporation\NVSMI\nvidia-smi.exe')
)
foreach ($c in $candidates) { if ($c -and (Test-Path $c)) { $smiPath = $c; break } }
if (-not $smiPath) {
    $cmd = Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue
    if ($cmd) { $smiPath = $cmd.Source }
}

if ($smiPath) {
    Write-Host ('  using ' + $smiPath)
    $smiOut = & $smiPath 2>&1 | Out-String
    Write-Host $smiOut
    if ($LASTEXITCODE -eq 0) {
        $smiOk = $true
        $q = & $smiPath --query-gpu=name,serial,uuid,vbios_version,driver_version,temperature.gpu,power.draw,utilization.gpu,memory.total,encoder.stats.sessionCount --format=csv,noheader 2>&1 | Out-String
        Write-Host ('  query: ' + $q.Trim())
        $parts = $q.Trim() -split ','
        if ($parts.Count -ge 5) {
            $gpuName = $parts[0].Trim()
            $driverVersion = $parts[4].Trim()
        }
        if ($parts.Count -ge 10) {
            $sessions = ($parts[9].Trim() -replace '[^0-9]', '')
            if ($sessions -and [int]$sessions -gt 0) {
                Add-Note ('NVENC sessions already open (' + $sessions + ') - HwDetector can fail on encoder contention while the card is healthy')
            }
        }
        # Thermal and slowdown state
        $qdetail = & $smiPath -q 2>&1 | Out-String
        $throttleActive = ($qdetail -match '(?i)HW Thermal Slowdown\s*:\s*Active') -or ($qdetail -match '(?i)HW Power Brake Slowdown\s*:\s*Active')
        if ($throttleActive) { Add-Hw 'Hardware thermal or power-brake slowdown is ACTIVE - cooling or power delivery fault' }
        $tempM = [regex]::Match($qdetail, '(?i)GPU Current Temp\s*:\s*(\d+)')
        if ($tempM.Success) {
            $temp = [int]$tempM.Groups[1].Value
            Write-Host ('  GPU temp: ' + $temp + ' C')
            if ($temp -ge 90) { Add-Hw ('GPU running at ' + $temp + ' C under light load - cooling fault') }
        }
        $replayM = [regex]::Match($qdetail, '(?i)Replay Counter\s*:\s*(\d+)')
        if ($replayM.Success) {
            $replay = [int]$replayM.Groups[1].Value
            Write-Host ('  PCIe replay counter: ' + $replay)
            if ($replay -gt 100) { Add-Hw ('High PCIe replay counter (' + $replay + ') - marginal physical link, reseat the card') }
        }
        Write-Host '-- processes holding the GPU --'
        & $smiPath --query-compute-apps=pid,process_name,used_memory --format=csv 2>&1 | Out-String | Write-Host
    } else {
        # NVML error strings each map to a distinct, mostly non-hardware cause.
        if ($smiOut -match '(?i)Driver/library version mismatch') {
            Add-Sw 'NVML driver/library version mismatch - driver updated without a reboot. Reboot and retest; do not RMA.'
        }
        if ($smiOut -match '(?i)has failed because it couldn|NVIDIA-SMI has failed') {
            Add-Sw 'nvidia-smi cannot communicate with the driver - driver not loaded or not installed'
        }
        if ($smiOut -match '(?i)No devices were found') {
            Add-Note 'nvidia-smi ran but found no devices - correlate with the PCI section above'
        }
        if ($smiOut -match '(?i)GPU is lost|Unable to determine the device handle') {
            Add-Hw 'NVML reports the GPU handle is lost - the device stopped responding (hard fault signature)'
        }
    }
} else {
    Write-Host '  nvidia-smi.exe not found'
    Add-Sw 'nvidia-smi.exe not present - the NVIDIA driver package is incomplete; the GPU cannot be judged in this state'
}

# ==========================================================================
Write-Section '5. EVENT LOG HISTORY (last 21 days)'
# TDR resets, WHEA PCIe errors and PnP surprise-removals are the Windows
# equivalents of the Linux Xid / AER evidence.
# ==========================================================================
$since = (Get-Date).AddDays(-21)
function Get-Ev {
    param([string]$LogName, [string[]]$Providers)
    try {
        return @(Get-WinEvent -FilterHashtable @{ LogName = $LogName; ProviderName = $Providers; StartTime = $since } -MaxEvents 40 -ErrorAction Stop)
    } catch { return @() }
}

$nvEvents   = Get-Ev -LogName 'System' -Providers @('nvlddmkm', 'Display', 'nvsvc')
$wheaEvents = Get-Ev -LogName 'System' -Providers @('Microsoft-Windows-WHEA-Logger')
$pnpEvents  = Get-Ev -LogName 'System' -Providers @('Microsoft-Windows-Kernel-PnP')

Write-Host ('  nvlddmkm/Display events: ' + $nvEvents.Count)
foreach ($e in ($nvEvents | Select-Object -First 8)) {
    Write-Host ('   [' + $e.TimeCreated + '] id=' + $e.Id + ' ' + (($e.Message -split "`n")[0]))
}
$tdr = @($nvEvents | Where-Object { $_.Message -match '(?i)stopped responding and has successfully recovered|Display driver nvlddmkm' })
if ($tdr.Count -ge 5) {
    Add-Hw ('Repeated display-driver resets (TDR): ' + $tdr.Count + ' in 21 days - persistent GPU instability')
} elseif ($tdr.Count -gt 0) {
    Add-Note ('Display-driver reset (TDR) events present: ' + $tdr.Count + ' in 21 days - driver or load related, not proof of dead silicon')
}

Write-Host ('  WHEA events: ' + $wheaEvents.Count)
foreach ($e in ($wheaEvents | Select-Object -First 6)) {
    Write-Host ('   [' + $e.TimeCreated + '] id=' + $e.Id + ' ' + (($e.Message -split "`n")[0]))
}
$wheaUncorrected = @($wheaEvents | Where-Object { $_.Id -eq 18 -or $_.Message -match '(?i)uncorrectable|fatal' })
if ($wheaUncorrected.Count -gt 0) {
    Add-Hw ('WHEA uncorrectable/fatal hardware errors logged (' + $wheaUncorrected.Count + ') - genuine hardware evidence')
} elseif ($wheaEvents.Count -gt 0) {
    Add-Note ('WHEA corrected errors present (' + $wheaEvents.Count + ') - watch, but corrected errors alone are not an RMA')
}

$surprise = @($pnpEvents | Where-Object { $_.Message -match '(?i)VEN_10DE' })
if ($surprise.Count -gt 0) {
    Write-Host ('  Kernel-PnP events referencing the NVIDIA device: ' + $surprise.Count)
    foreach ($e in ($surprise | Select-Object -First 4)) {
        Write-Host ('   [' + $e.TimeCreated + '] id=' + $e.Id + ' ' + (($e.Message -split "`n")[0]))
    }
    Add-Hw 'Kernel-PnP logged the NVIDIA device disappearing/reappearing - the card is dropping off the bus'
}

# ==========================================================================
Write-Section '6. FUNCTIONAL NVENC / CUDA TEST - THE ACTUAL PROOF'
# If the card encodes and decodes here, it can do the exact job HwDetector
# claims it cannot, and the unit must not be RMA'd.
# ==========================================================================
$nvencTest = 'skipped'
$nvdecTest = 'skipped'
if (-not $SkipFunctionalTest -and $smiOk) {
    $ffmpeg = $null
    # Path confirmed from the Pulse collectors - Pixellot ships ffmpeg here.
    $ffCandidates = @(
        'C:\Pixellot\Bin\ffmpeg\ffmpeg.exe',
        'C:\Pixellot\Bin\ffmpeg.exe',
        'C:\ffmpeg\bin\ffmpeg.exe'
    )
    foreach ($c in $ffCandidates) { if (Test-Path $c) { $ffmpeg = $c; break } }
    if (-not $ffmpeg) {
        $cmd = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
        if ($cmd) { $ffmpeg = $cmd.Source }
    }
    if (-not $ffmpeg) {
        # Last resort: any ffmpeg shipped under the Pixellot tree.
        try {
            $found = Get-ChildItem -Path 'C:\Pixellot' -Filter 'ffmpeg.exe' -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($found) { $ffmpeg = $found.FullName }
        } catch { }
    }

    if ($ffmpeg) {
        Write-Host ('  using ffmpeg: ' + $ffmpeg)
        $tmp = Join-Path $env:TEMP ('gputriage-' + $stamp + '.mp4')
        $encOut = & $ffmpeg -hide_banner -loglevel error -y -f lavfi -i testsrc2=size=1280x720:rate=30 -frames:v 60 -c:v h264_nvenc $tmp 2>&1 | Out-String
        if ((Test-Path $tmp) -and ((Get-Item $tmp).Length -gt 0)) {
            $nvencTest = 'PASS'
            Write-Host '  NVENC: PASS'
            Add-Note 'FUNCTIONAL: NVENC encoded successfully on this GPU'
            $decOut = & $ffmpeg -hide_banner -loglevel error -hwaccel cuda -hwaccel_output_format cuda -i $tmp -f null - 2>&1 | Out-String
            if ($LASTEXITCODE -eq 0) {
                $nvdecTest = 'PASS'
                Write-Host '  NVDEC/CUDA: PASS'
                Add-Note 'FUNCTIONAL: CUDA/NVDEC decode succeeded on this GPU'
            } else {
                $nvdecTest = 'FAIL'
                Write-Host ('  NVDEC/CUDA: FAIL - ' + $decOut.Trim())
            }
        } else {
            $nvencTest = 'FAIL'
            Write-Host ('  NVENC: FAIL - ' + $encOut.Trim())
        }
        if (Test-Path $tmp) { Remove-Item $tmp -Force -ErrorAction SilentlyContinue }
    } else {
        Write-Host '  ffmpeg.exe not found - functional test skipped'
        Add-Note 'ffmpeg not found; the decisive encode/decode test did not run'
    }
} else {
    Write-Host '  (skipped)'
}

# ==========================================================================
Write-Section '7. PIXELLOT HWDETECTOR LOG EVIDENCE'
# The date of the FIRST occurrence is the number that matters. If it lines up
# with a driver or Windows update rather than with anything physical, that is
# the argument against the hardware-fault explanation.
# ==========================================================================
$logDir = 'C:\Pixellot\Data\Log'
$firstSeen = ''
$hitCount  = 0
if (Test-Path $logDir) {
    try {
        $logs = @(Get-ChildItem -Path $logDir -Filter '*.log' -File -ErrorAction SilentlyContinue |
                  Sort-Object LastWriteTime -Descending | Select-Object -First 25)
        Write-Host ('  scanning ' + $logs.Count + ' log files in ' + $logDir)
        $hits = New-Object System.Collections.ArrayList
        foreach ($lf in $logs) {
            $found = @(Select-String -Path $lf.FullName -SimpleMatch -ErrorAction SilentlyContinue -Pattern @(
                'HwDetector', 'NVENC', 'gpu type is', 'CUDA', 'QSV'))
            foreach ($h in $found) {
                if ($h.Line -match '(?i)fail|error|N/A') { $null = $hits.Add($h) }
            }
        }
        $hitCount = $hits.Count
        Write-Host ('  matching failure lines: ' + $hitCount)
        foreach ($h in ($hits | Select-Object -First 6)) {
            Write-Host ('   ' + $h.Filename + ': ' + $h.Line.Trim())
        }
        if ($hitCount -gt 0) {
            # Oldest touched log carrying the error bounds when this began.
            $oldest = $logs | Where-Object { $_.Name -in ($hits | ForEach-Object { $_.Filename }) } |
                      Sort-Object LastWriteTime | Select-Object -First 1
            if ($oldest) {
                $firstSeen = $oldest.LastWriteTime.ToString('o')
                Write-Host ('  earliest log carrying the error: ' + $oldest.Name + ' (' + $oldest.LastWriteTime + ')')
                Add-Note ('HwDetector failure present in logs back to at least ' + $oldest.LastWriteTime + ' - compare against driver/update dates in section 1')
            }
        }
    } catch {
        Write-Host '  (log scan failed)'
    }
} else {
    Write-Host ('  ' + $logDir + ' not present')
}

# ==========================================================================
Write-Section '8. INTEL QSV PATH (the other half of the HwDetector message)'
# ==========================================================================
$intelGpu = @($videoControllers | Where-Object { $_.Name -match '(?i)Intel' })
foreach ($i in $intelGpu) {
    Write-Host ('  ' + $i.Name + '  drv=' + $i.DriverVersion + '  cmErr=' + $i.ConfigManagerErrorCode)
}
if ($intelGpu.Count -gt 0 -and -not $pciPresent) {
    Add-Note 'Only the Intel iGPU is present - this matches the "gpu type is: N/A, intelGpu: ..." message exactly'
}

# ==========================================================================
Write-Section 'VERDICT'
# ==========================================================================
$verdict = 'INCONCLUSIVE'
$rc = 3
if (-not $enumOk -and $hwEvidence.Count -eq 0) {
    # Nothing could be inspected; no conclusion is honest.
    $verdict = 'INCONCLUSIVE'; $rc = 3
} elseif ($hwEvidence.Count -gt 0) {
    $verdict = 'HARDWARE_SUSPECT'; $rc = 2
} elseif ($nvencTest -eq 'PASS' -and ($nvdecTest -eq 'PASS' -or $nvdecTest -eq 'skipped')) {
    $verdict = 'NOT_HARDWARE'; $rc = 0
} elseif ($swEvidence.Count -gt 0) {
    $verdict = 'SOFTWARE_FAULT'; $rc = 1
}

Write-Host $verdict
Write-Host ''
if ($hwEvidence.Count -gt 0) {
    Write-Host 'Hardware evidence:'
    foreach ($e in $hwEvidence) { Write-Host ('  [HW] ' + $e) }
    Write-Host ''
}
if ($swEvidence.Count -gt 0) {
    Write-Host 'Software/config evidence:'
    foreach ($e in $swEvidence) { Write-Host ('  [SW] ' + $e) }
    Write-Host ''
}
if ($notes.Count -gt 0) {
    Write-Host 'Notes:'
    foreach ($e in $notes) { Write-Host ('  [--] ' + $e) }
    Write-Host ''
}
switch ($verdict) {
    'NOT_HARDWARE'     { Write-Host 'The GPU encoded and decoded on demand. DO NOT RMA. The HwDetector failure is software, timing, or encoder contention.' }
    'SOFTWARE_FAULT'   { Write-Host 'The GPU is present but the driver stack is broken. Fix in place; DO NOT RMA until it is repaired and retested.' }
    'HARDWARE_SUSPECT' { Write-Host 'Physical-layer evidence found. Reseat the card and retest FIRST - reseating clears most of these. RMA only if it survives a reseat.' }
    'INCONCLUSIVE'     { Write-Host 'No decisive evidence either way. Re-run elevated, with ffmpeg available, right after reproducing the failure.' }
}

# --- JSON summary ----------------------------------------------------------
$summary = [ordered]@{
    schema           = 'gpu-triage/1'
    host             = $hostName
    timestamp        = (Get-Date -Format 'o')
    platform         = 'windows'
    model            = $(if ($cs) { $cs.Manufacturer + ' ' + $cs.Model } else { '' })
    os               = $(if ($os) { $os.Caption + ' ' + $os.Version } else { '' })
    buildLab         = $osBuild
    bios             = $(if ($bios) { [string]$bios.SMBIOSBIOSVersion } else { '' })
    gpuName          = $gpuName
    pciPresent       = $pciPresent
    pciId            = $devIdStr
    driverVersion    = $driverVersion
    enumerationOk    = $enumOk
    nvidiaSmiOk      = $smiOk
    nvencTest        = $nvencTest
    nvdecTest        = $nvdecTest
    hwDetectorLogHits   = $hitCount
    hwDetectorFirstSeen = $firstSeen
    tdrCount         = $tdr.Count
    wheaCount        = $wheaEvents.Count
    verdict          = $verdict
    hardwareEvidence = @($hwEvidence)
    softwareEvidence = @($swEvidence)
    notes            = @($notes)
}
$summary | ConvertTo-Json -Depth 6 | Out-File -FilePath $jsonPath -Encoding ASCII

Write-Host ''
Write-Host ('JSON summary : ' + $jsonPath)
Write-Host ('Full log     : ' + $logPath)
try { Stop-Transcript | Out-Null } catch { }
exit $rc
