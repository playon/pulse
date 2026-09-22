#Requires -Version 5.1
<#
.SYNOPSIS
    ADLINK SmartPoE card budget + per-port PoE power draw (LOCAL collector).

.DESCRIPTION
    Ported from the gen-1 PowerShell tool (Modules/CameraConnectivity.psm1 ->
    "PoE Status", plus the AdlinkPoE P/Invoke shim in Modules/UIHelpers.psm1
    and the Get-AdlinkCardInfo NIC gate in Run.ps1, all at 3ca61dc). The
    Pulse.WPF port of the same feature dropped the NIC gate and regressed the
    low-budget threshold to a flat 55 W; both are restored here.

    Three gates, cheapest first, so an unsupported box never loads the driver:

      1. NIC model. Only the Intel I210 / I211 (ADLINK GIE74P) expose PoE
         telemetry. The 82574L (GIE64) and I350 / I354 (GIE74P-AN) do not --
         Register_Card either fails or hangs on those, so we never call it.
      2. SmartPoE.dll presence. It ships with the ADLINK driver bundle, NOT
         with Windows. A supported NIC with no bundle installed reports
         available=false with an actionable reason.
      3. Crash sentinel (see below).

    Crash sentinel: unlike gen-1 (one probe per diagnostic run) this collector
    is polled every ~2s to drive a live card. The native DLL is known to throw
    AccessViolation on some platforms, and an AV is a corrupted-state
    exception that .NET Framework will NOT let us catch -- it takes
    powershell.exe down with it. Left unguarded that becomes a crash loop
    spawning a dying process every 2s. So we increment a TEMP sentinel before
    the first native call and clear it after the reads land; three unfinished
    attempts latch the probe off until Pulse restarts (the launcher clears
    stale sentinels) or the tech clears TEMP.

    PS 5.1 portability (see CLAUDE.md):
      - Pure ASCII only. No em-dashes or smart quotes in this file.
      - The DllImport declarations live in compiled C# (C# 5 / CodeDom safe),
        never as script-level casts.
      - Every unwanted native return value is cast to [void] so it cannot
        land on stdout ahead of the JSON payload.

.OUTPUTS
    Single JSON object on stdout. See $result construction at the bottom.
#>

$ErrorActionPreference = "Stop"

# Port count on the GIE74P PSE controller. Card index is always 0 -- the VPU
# chassis has one PoE NIC.
$PortCount = 4
$CardNum   = 0

# IEEE 802.3at PoE+ per-port ceiling. Reported only so the UI can draw a port's
# draw as a fraction of its headroom -- NOT a budget threshold. Real Pixellot
# CHUs draw 4-7 W, so anything that scales an expectation off this ceiling
# overestimates demand roughly fourfold.
$PoePlusWattsPerPort = 25.5

# Total-budget floor for a healthy card, in watts. Below this the PoE card's
# supplementary Molex power lead is disconnected (or otherwise not delivering),
# so the card falls back to slot power alone and cannot run a full camera set.
#
# 55 W is not a guess -- it's bracketed by two real measurements, and it is the
# same figure Pixellot's own VPU Manager uses, so Pulse and VPU Manager agree
# instead of contradicting each other in front of a tech:
#   - Molex disconnected: VPU Manager reports "20.0 W detected (expected >=55W)".
#   - Molex connected: a production GIE74P read 61-63 W total with two cameras
#     up (2026-08-12).
# A ~40 W gap with the threshold in the middle, so this is robust to the drift
# noted below.
#
# Note on the number this is compared against: total is derived as
# consumed + remaining, and those two are NOT complementary -- across samples 3s
# apart consumed fell 12.0 -> 11.3 W while remaining ALSO fell 51.4 -> 49.6 W.
# So total wobbles by a couple of watts and is not a precise card rating. That
# rules out hanging a TIGHT per-port expectation on it (which is exactly how
# gen-1's D8 change went wrong: it demanded poeOnCount * 25.5 W, i.e. 76.5 W at
# three active ports, which a healthy 63 W card fails). A coarse 55 W floor is
# unaffected by a couple of watts of drift.
$HealthyTotalFloorWatts = 55.0

$SentinelPath  = Join-Path $env:TEMP "PulsePoE-probe.sentinel"
$SentinelLimit = 3

function New-PoeResult {
    param(
        [bool]$Supported,
        [bool]$Available,
        [string]$NicModel   = "",
        [string]$CardLabel  = "",
        [string]$Reason     = "",
        [string]$DllPath    = ""
    )
    [ordered]@{
        supported = $Supported
        available = $Available
        nicModel  = $NicModel
        cardLabel = $CardLabel
        reason    = $Reason
        dllPath   = $DllPath
        budget    = $null
        ports     = @()
    }
}

function Write-PoeJson {
    param($Result)
    $Result | ConvertTo-Json -Depth 5 -Compress
}

# ---------------------------------------------------------------------------
# Gate 1 -- NIC model. Mirrors Get-AdlinkCardInfo from gen-1 Run.ps1 exactly,
# including which families are deliberately unsupported.
# ---------------------------------------------------------------------------
function Get-AdlinkCardInfo {
    $nics = @()
    try {
        $nics = @(Get-NetAdapter -Physical -ErrorAction Stop | Where-Object {
            $_.InterfaceDescription -match 'I210|I211|I350|I354|82574L'
        })
    } catch {
        # Get-NetAdapter unavailable (rare, non-fleet host) -- fall back to WMI.
        try {
            $nics = @(Get-CimInstance Win32_NetworkAdapter -ErrorAction Stop |
                Where-Object { $_.Name -match 'I210|I211|I350|I354|82574L' } |
                ForEach-Object { [pscustomobject]@{ InterfaceDescription = $_.Name } })
        } catch { $nics = @() }
    }

    $desc  = if ($nics.Count -gt 0) { [string]$nics[0].InterfaceDescription } else { "" }
    $count = $nics.Count

    if ($desc -like "*82574L*") {
        [pscustomobject]@{ Model = "82574L"; Label = "ADLINK GIE64 (Intel 82574L x$count)";    Supported = $false }
    } elseif ($desc -like "*I210*") {
        [pscustomobject]@{ Model = "I210";   Label = "ADLINK GIE74P (Intel I210 x$count)";     Supported = $true  }
    } elseif ($desc -like "*I211*") {
        [pscustomobject]@{ Model = "I211";   Label = "ADLINK GIE74P (Intel I211 x$count)";     Supported = $true  }
    } elseif ($desc -like "*I350*") {
        [pscustomobject]@{ Model = "I350";   Label = "ADLINK GIE74P-AN (Intel I350 x$count)";  Supported = $false }
    } elseif ($desc -like "*I354*") {
        [pscustomobject]@{ Model = "I354";   Label = "ADLINK GIE74P-AN (Intel I354 x$count)";  Supported = $false }
    } elseif ($count -gt 0) {
        [pscustomobject]@{ Model = "Unknown"; Label = "Unknown NIC ($desc)";                   Supported = $false }
    } else {
        [pscustomobject]@{ Model = "None";    Label = "No camera card detected";               Supported = $false }
    }
}

$card = Get-AdlinkCardInfo

if (-not $card.Supported) {
    $reason = switch ($card.Model) {
        "82574L" { "Power draw can't be measured on this camera card (ADLINK GIE64, Intel 82574L). The ports still deliver power; Pulse just can't read how much." }
        "I350"   { "Power draw can't be measured on this camera card (ADLINK GIE74P-AN, Intel I350). The ports still deliver power." }
        "I354"   { "Power draw can't be measured on this camera card (ADLINK GIE74P-AN, Intel I354). The ports still deliver power." }
        "None"   { "No camera card was detected (Intel I210 / I211 / I350 / 82574L), so there is no power draw to measure." }
        default  { "PoE power telemetry requires an ADLINK GIE74P card (Intel I210 or I211). This system reports: $($card.Label)" }
    }
    Write-PoeJson (New-PoeResult -Supported $false -Available $false `
        -NicModel $card.Model -CardLabel $card.Label -Reason $reason)
    exit 0
}

# ---------------------------------------------------------------------------
# Gate 2 -- locate SmartPoE.dll. Same search order as gen-1 Run.ps1: known
# install paths, then the ADLINK registry keys, then a bounded recursive walk
# of the ADLINK trees only (never all of Program Files -- that walk took
# seconds on a spinning disk and this collector is polled).
# ---------------------------------------------------------------------------
function Find-SmartPoeDll {
    $candidates = @(
        "C:\Program Files\ADLINK\GIE Series\Library\Dll\x64\SmartPoE.dll"
        (Join-Path $env:SystemRoot "System32\SmartPoE.dll")
        "C:\Program Files\ADLINK\SmartPoE\SmartPoE.dll"
        "C:\Program Files (x86)\ADLINK\SmartPoE\SmartPoE.dll"
        "C:\Program Files\ADLINK\PCIe-GIE7x\SmartPoE.dll"
        "C:\ADLINK\SmartPoE\SmartPoE.dll"
    )
    foreach ($c in $candidates) {
        try { if (Test-Path -LiteralPath $c) { return $c } } catch { }
    }

    foreach ($reg in @(
        "HKLM:\SOFTWARE\ADLINK\SmartPoE"
        "HKLM:\SOFTWARE\WOW6432Node\ADLINK\SmartPoE"
        "HKLM:\SOFTWARE\ADLINK\GigE Tool"
    )) {
        try {
            $install = Get-ItemPropertyValue -Path $reg -Name "InstallDir" -ErrorAction Stop
            if ($install) {
                $c = Join-Path $install "SmartPoE.dll"
                if (Test-Path -LiteralPath $c) { return $c }
            }
        } catch { }
    }

    foreach ($root in @("C:\Program Files\ADLINK", "C:\Program Files (x86)\ADLINK", "C:\ADLINK")) {
        try {
            if (-not (Test-Path -LiteralPath $root)) { continue }
            $found = Get-ChildItem -LiteralPath $root -Recurse -Filter "SmartPoE.dll" `
                        -ErrorAction SilentlyContinue |
                     Where-Object { $_.FullName -notlike "*x86*" } |
                     Select-Object -First 1
            if ($found) { return $found.FullName }
        } catch { }
    }
    return $null
}

$dllPath = Find-SmartPoeDll

if (-not $dllPath) {
    Write-PoeJson (New-PoeResult -Supported $true -Available $false `
        -NicModel $card.Model -CardLabel $card.Label `
        -Reason "This camera card ($($card.Model)) can report power draw, but its ADLINK SmartPoE driver (SmartPoE.dll) is not installed. Install the ADLINK GIE Series driver package to see per-port power.")
    exit 0
}

# ---------------------------------------------------------------------------
# Gate 3 -- crash sentinel. See the header note on AccessViolation.
# ---------------------------------------------------------------------------
$crashCount = 0
try {
    if (Test-Path -LiteralPath $SentinelPath) {
        $raw = Get-Content -LiteralPath $SentinelPath -Raw -ErrorAction Stop
        [void][int]::TryParse($raw.Trim(), [ref]$crashCount)
    }
} catch { $crashCount = 0 }

if ($crashCount -ge $SentinelLimit) {
    Write-PoeJson (New-PoeResult -Supported $true -Available $false `
        -NicModel $card.Model -CardLabel $card.Label -DllPath $dllPath `
        -Reason "The SmartPoE driver crashed the power probe $crashCount times in a row, so live monitoring has been disabled to stop it retrying. Restart Pulse to try again; if it keeps failing, the ADLINK driver bundle likely needs reinstalling.")
    exit 0
}

try {
    Set-Content -LiteralPath $SentinelPath -Value ([string]($crashCount + 1)) -Encoding ASCII -ErrorAction Stop
} catch { }

# ---------------------------------------------------------------------------
# Native shim. Compiled once to a hash-keyed DLL in TEMP -- every poll is a
# fresh powershell.exe and Add-Type -TypeDefinition shells out to csc.exe
# (1-3s), which would make a 2s live poll crawl. Same approach as
# _AudioInterop.ps1; any failure on the cache path falls back to the slow
# in-memory compile so behaviour never changes.
# ---------------------------------------------------------------------------
if (-not ([System.Management.Automation.PSTypeName]'Pulse.AdlinkPoE').Type) {
    $poeSource = @'
using System.Runtime.InteropServices;

namespace Pulse {
    public static class AdlinkPoE {
        // Register_Card takes the card index (0 for the first card) and
        // returns 0 on success, negative on error.
        [DllImport("SmartPoE.dll")]
        public static extern short SmartPoE_Register_Card(ushort wCardNumber);
        [DllImport("SmartPoE.dll")]
        public static extern short SmartPoE_Release_Card(ushort wCardNumber);
        [DllImport("SmartPoE.dll")]
        public static extern short SmartPoE_Get_Temperature(ushort wCardNumber, out double wTemperature);
        [DllImport("SmartPoE.dll")]
        public static extern short SmartPoE_Get_POEConsPowbudget(ushort wCardNumber, out double wPower);
        [DllImport("SmartPoE.dll")]
        public static extern short SmartPoE_Get_POELeftPowbudget(ushort wCardNumber, out double wPower);
        [DllImport("SmartPoE.dll")]
        public static extern short SmartPoE_Get_PSEPortCurrent(ushort wCardNumber, ushort PortNumber, out double wCurrent);
        [DllImport("SmartPoE.dll")]
        public static extern short SmartPoE_Get_PSEPortVoltage(ushort wCardNumber, ushort PortNumber, out double wVoltage);
    }
}
'@

    # The late-bound DllImport resolves "SmartPoE.dll" off PATH, so prepend
    # the directory we actually found it in.
    try {
        $dllDir = [System.IO.Path]::GetDirectoryName($dllPath)
        if ($dllDir -and ($env:PATH -notlike "*$dllDir*")) {
            $env:PATH = "$dllDir;$env:PATH"
        }
    } catch { }

    $poeLoaded = $false
    try {
        $md5       = [System.Security.Cryptography.MD5]::Create()
        $hashBytes = $md5.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($poeSource))
        $hash      = ([System.BitConverter]::ToString($hashBytes) -replace '-', '').Substring(0, 12)
        $cacheDll  = Join-Path $env:TEMP ("PulseAdlinkPoE-" + $hash + ".dll")

        if (-not (Test-Path -LiteralPath $cacheDll)) {
            # Compile to a per-process name then move into place, so two
            # concurrent polls cannot load a half-written DLL.
            $tmpPath = $cacheDll + "." + $PID + ".tmp"
            Add-Type -TypeDefinition $poeSource -OutputAssembly $tmpPath -ErrorAction Stop
            try {
                Move-Item -LiteralPath $tmpPath -Destination $cacheDll -Force -ErrorAction Stop
            } catch {
                Remove-Item -LiteralPath $tmpPath -Force -ErrorAction SilentlyContinue
            }
        }

        if (Test-Path -LiteralPath $cacheDll) {
            Add-Type -Path $cacheDll -ErrorAction Stop
            $poeLoaded = $true
        }
    } catch { $poeLoaded = $false }

    if (-not $poeLoaded) {
        Add-Type -TypeDefinition $poeSource -ErrorAction Stop
    }
}

# ---------------------------------------------------------------------------
# Read the card. Everything below is best-effort: a driver that loads but
# fails a read reports available=false with the exception type rather than
# throwing out of the collector.
# ---------------------------------------------------------------------------
$registered = $false
try {
    $regRet = [Pulse.AdlinkPoE]::SmartPoE_Register_Card([uint16]$CardNum)
    if ($regRet -ne 0) {
        try { Remove-Item -LiteralPath $SentinelPath -Force -ErrorAction SilentlyContinue } catch { }
        Write-PoeJson (New-PoeResult -Supported $true -Available $false `
            -NicModel $card.Model -CardLabel $card.Label -DllPath $dllPath `
            -Reason "The SmartPoE driver is installed but reported no PoE card (Register_Card returned $regRet). The card may be seated badly, or the driver may not match this card revision.")
        exit 0
    }
    $registered = $true

    # Check every native return code rather than discarding it. A getter can
    # return non-zero while still leaving a plausible-looking number in its
    # out-param, so a value whose rc != 0 must be treated as unread, not shown.
    # (Verified all-zero on a healthy production GIE74P, 2026-08-12.)
    $consumed = 0.0
    $remaining = 0.0
    $tempC = 0.0
    $rcCons = [Pulse.AdlinkPoE]::SmartPoE_Get_POEConsPowbudget([uint16]$CardNum, [ref]$consumed)
    $rcLeft = [Pulse.AdlinkPoE]::SmartPoE_Get_POELeftPowbudget([uint16]$CardNum, [ref]$remaining)
    $rcTemp = [Pulse.AdlinkPoE]::SmartPoE_Get_Temperature([uint16]$CardNum, [ref]$tempC)

    if ($rcCons -ne 0 -or $rcLeft -ne 0) {
        try { Remove-Item -LiteralPath $SentinelPath -Force -ErrorAction SilentlyContinue } catch { }
        Write-PoeJson (New-PoeResult -Supported $true -Available $false `
            -NicModel $card.Model -CardLabel $card.Label -DllPath $dllPath `
            -Reason "The PoE card is present but rejected the power-budget read (consumed rc=$rcCons, remaining rc=$rcLeft). The ADLINK driver may not match this card revision.")
        exit 0
    }
    # Temperature is non-essential -- a bad rc there drops the reading without
    # discarding the power figures the tech actually came for.
    if ($rcTemp -ne 0) { $tempC = 0.0 }

    $total = $consumed + $remaining

    # PSE channels are 1-BASED: channel N is chassis Port N, and valid channels
    # are 1..4. Gen-1 read 0..3 and labelled them "P{index+1}"; that is wrong in
    # two ways at once and this collector inherited it until it was measured.
    #
    # Proven by controlled experiment on a GIE74P (VPU2, 2026-08-12): unplugging
    # the camera on chassis Port 1 took channel 1 from 54 V to its 0.187 V float,
    # binding channel N to Port N directly. A sweep of indices 0..5 then showed
    # the real range:
    #     ch0  0.000 V  0.0002 A  <- phantom, out of range
    #     ch1  0.187 V            <- Port 1 (camera just unplugged)
    #     ch2 54.336 V  5.52 W    <- Port 2
    #     ch3  0.187 V            <- Port 3 (empty)
    #     ch4 54.336 V  3.82 W    <- Port 4 (OCR camera)
    #     ch5  0.000 V            <- phantom, out of range
    #
    # Reading 0..3 therefore invented a dead Port 1, shifted every other reading
    # one place, and never read Port 4 at all -- a powered camera there showed as
    # "off". The same 1-based mapping also fits the production card read earlier.
    #
    # WATCH OUT: out-of-range channels return rc=0 with zeroed out-params, so a
    # bad index looks exactly like an unpowered port. There is no error to catch;
    # the only defence is the consumed-vs-sum cross-check below.
    $ports     = @()
    $poeOnCount = 0
    $portSum    = 0.0
    for ($i = 1; $i -le $PortCount; $i++) {
        $voltage = 0.0
        $current = 0.0
        $rcV = [Pulse.AdlinkPoE]::SmartPoE_Get_PSEPortVoltage([uint16]$CardNum, [uint16]$i, [ref]$voltage)
        $rcA = [Pulse.AdlinkPoE]::SmartPoE_Get_PSEPortCurrent([uint16]$CardNum, [uint16]$i, [ref]$current)
        $readOk = ($rcV -eq 0 -and $rcA -eq 0)
        if (-not $readOk) {
            # Do not render a failed read as a confident "0 W / off" -- that
            # looks identical to a genuinely unpowered port.
            $ports += [ordered]@{
                port = $i; voltage = $null; current = $null; watts = $null
                poeOn = $false; state = "Unreadable"; readOk = $false
            }
            continue
        }
        $watts = $voltage * $current
        # >1 V means the PSE has actually powered the pair up. An unpowered port
        # floats rather than sitting at exactly zero -- a production card read
        # 0.187 V on its empty port, which a naive "> 0" test would have called
        # powered.
        $isOn = ($voltage -gt 1.0)
        if ($isOn) { $poeOnCount++ }
        $portSum += $watts
        # Hoisted out of the hashtable literal on purpose: an inline if-else as
        # a hashtable value is a 5.1 parsing hazard even though pwsh 7 accepts
        # it. Same reason the rest of this file keeps values simple.
        $stateStr = "Off"
        if ($isOn) { $stateStr = "Powered" }
        $ports += [ordered]@{
            port    = $i
            voltage = [math]::Round($voltage, 2)
            current = [math]::Round($current, 3)
            watts   = [math]::Round($watts, 1)
            poeOn   = $isOn
            state   = $stateStr
            readOk  = $true
        }
    }

    # Molex / insufficient-power verdict. See $HealthyTotalFloorWatts -- this is
    # the coarse floor VPU Manager uses, bracketed by real measurements at both
    # ends, NOT gen-1's per-port-scaled expectation.
    #
    # Guarded on $total -gt 0 so a card that reports nothing at all falls through
    # to the ordinary "no reading" path rather than being called Molex-out.
    $underPowered = ($total -gt 0) -and ($total -lt $HealthyTotalFloorWatts)

    # Self-check: the per-port readings should account for what the card says it
    # is delivering. This is the guard that would have caught the 0-based channel
    # bug immediately -- with Port 4 unread, the card reported 9.9 W consumed
    # while the ports summed to 5.5 W, and nothing complained.
    #
    # Out-of-range channels return rc=0 with zeroed values, so a wrong index is
    # indistinguishable from an unpowered port at the API level; this arithmetic
    # is the only place it shows up. 3 W of slack covers the card's own rounding
    # and the drift between separately-sampled figures.
    $portSumDelta = [math]::Abs($consumed - $portSum)
    $portSumOk    = ($consumed -le 0) -or ($portSumDelta -le 3.0)

    $result = New-PoeResult -Supported $true -Available $true `
        -NicModel $card.Model -CardLabel $card.Label -DllPath $dllPath
    $result.budget = [ordered]@{
        totalW        = [math]::Round($total, 1)
        consumedW     = [math]::Round($consumed, 1)
        remainingW    = [math]::Round($remaining, 1)
        tempC         = [math]::Round($tempC, 1)
        poeOnCount    = $poeOnCount
        healthyFloorW = $HealthyTotalFloorWatts
        underPowered  = $underPowered
        portMaxW      = $PoePlusWattsPerPort
        portSumW      = [math]::Round($portSum, 1)
        portSumOk     = $portSumOk
    }
    $result.ports = $ports

    # Reads landed -- the driver did not take the process down.
    try { Remove-Item -LiteralPath $SentinelPath -Force -ErrorAction SilentlyContinue } catch { }

    Write-PoeJson $result
} catch {
    $errType = $_.Exception.GetType().Name
    $errMsg  = ($_.Exception.Message -replace "[\r\n]+", " ")
    try { Remove-Item -LiteralPath $SentinelPath -Force -ErrorAction SilentlyContinue } catch { }
    Write-PoeJson (New-PoeResult -Supported $true -Available $false `
        -NicModel $card.Model -CardLabel $card.Label -DllPath $dllPath `
        -Reason "Reading PoE power failed ($errType): $errMsg")
} finally {
    if ($registered) {
        try { [void][Pulse.AdlinkPoE]::SmartPoE_Release_Card([uint16]$CardNum) } catch { }
    }
}
