#Requires -Version 5.1
<#
.SYNOPSIS
    Which sports and the scoreboard (OCR/PiP) camera are calibrated, read from
    the Pixellot configuration folders only.
.DESCRIPTION
    The cheap half of Get-PixellotConfig.ps1's calibration block, for the
    fleet monitor's telemetry (PV-57). Get-PixellotConfig.ps1 also probes every
    camera over CGI, which the unattended monitor must not pay for. This reads
    two folders and a handful of file times, all local, no network.

    Calibration is recorded by file and folder presence (confirmed on a VPU
    2026-06-15):
      * C:\Pixellot\Data\Configuration\multisportcalibration\<sport>\
        one folder per calibrated sport; the folder's write time is roughly
        when. primary.txt (in the multisportcalibration folder) names the
        primary sport.
      * C:\Pixellot\Data\Configuration\Graphics\pipdesign\
        OCR/scoreboard is calibrated when enhanced_pip.txt AND
        innerobjects.txt both exist; the newer file's time is when.

    This reports what it could READ, not what it could infer. The caller turns
    that into "unknown" (null) versus "read, nothing calibrated":
      configRootReadable  the Configuration folder itself could be listed.
      <section>.exists    the section's folder is there.
      <section>.readable  it was there and could be read.
    A section's folder missing under a readable Configuration folder is a real
    answer (nothing calibrated); a Configuration folder that cannot be read is
    no answer.

    When either section gives no answer the whole result is an error. The
    fleet monitor serves this collector from its 6 h disk cache, which never
    stores an error, so a failed read is retried on the next pass instead of
    sticking for six hours.

    Times are ISO 8601 with the UTC offset, no fractional seconds.

    Always emits one JSON object, even when nothing could be read.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$configRoot = 'C:\Pixellot\Data\Configuration'
$mscPath    = Join-Path $configRoot 'multisportcalibration'
$pipPath    = Join-Path $configRoot 'Graphics\pipdesign'

function Format-Stamp {
    param([datetime]$When)
    return $When.ToString('yyyy-MM-ddTHH:mm:sszzz', [System.Globalization.CultureInfo]::InvariantCulture)
}

$result = $null

try {
    $rootReadable = $false
    try {
        $null = Get-ChildItem -LiteralPath $configRoot -ErrorAction Stop | Select-Object -First 1
        $rootReadable = $true
    }
    catch { }

    # -- Sports: one folder per calibrated sport ---------------------------
    $mscExists   = $false
    $mscReadable = $false
    $sports      = @()
    $primary     = $null
    if (Test-Path -LiteralPath $mscPath -PathType Container) {
        $mscExists = $true
        try {
            $dirs = @(Get-ChildItem -LiteralPath $mscPath -Directory -ErrorAction Stop | Select-Object -First 200)
            foreach ($d in $dirs) {
                $sports += [pscustomobject]@{
                    name = $d.Name
                    at   = Format-Stamp $d.LastWriteTime
                }
            }
            $mscReadable = $true
        }
        catch { }

        if ($mscReadable) {
            $primaryPath = Join-Path $mscPath 'primary.txt'
            if (Test-Path -LiteralPath $primaryPath -PathType Leaf) {
                try {
                    $raw = Get-Content -LiteralPath $primaryPath -Raw -ErrorAction Stop
                    if ($raw) {
                        $first = ($raw -split "[\r\n]+" | Where-Object { $_.Trim() } | Select-Object -First 1)
                        if ($first) { $primary = $first.Trim() }
                    }
                }
                catch { }
            }
        }
    }

    # -- OCR / scoreboard camera: two files in pipdesign -------------------
    $pipExists   = $false
    $pipReadable = $false
    $hasEnhanced = $false
    $hasInner    = $false
    $pipAt       = $null
    if (Test-Path -LiteralPath $pipPath -PathType Container) {
        $pipExists = $true
        try {
            $enhanced = Join-Path $pipPath 'enhanced_pip.txt'
            $inner    = Join-Path $pipPath 'innerobjects.txt'
            $newest   = $null
            if (Test-Path -LiteralPath $enhanced -PathType Leaf) {
                $hasEnhanced = $true
                $newest = (Get-Item -LiteralPath $enhanced -ErrorAction Stop).LastWriteTime
            }
            if (Test-Path -LiteralPath $inner -PathType Leaf) {
                $hasInner = $true
                $t = (Get-Item -LiteralPath $inner -ErrorAction Stop).LastWriteTime
                if ($null -eq $newest -or $t -gt $newest) { $newest = $t }
            }
            if ($null -ne $newest) { $pipAt = Format-Stamp $newest }
            $pipReadable = $true
        }
        catch { }
    }

    $mscAnswered = $mscReadable -or ((-not $mscExists) -and $rootReadable)
    $pipAnswered = $pipReadable -or ((-not $pipExists) -and $rootReadable)
    if (-not ($mscAnswered -and $pipAnswered)) {
        throw 'Calibration folders could not be read'
    }

    $result = [pscustomobject]@{
        configRootReadable = $rootReadable
        multisport = [pscustomobject]@{
            exists   = $mscExists
            readable = $mscReadable
            primary  = $primary
            sports   = $sports
        }
        pip = [pscustomobject]@{
            exists          = $pipExists
            readable        = $pipReadable
            hasEnhancedPip  = $hasEnhanced
            hasInnerObjects = $hasInner
            at              = $pipAt
        }
    }
}
catch {
    $result = [pscustomobject]@{
        error   = $true
        message = $_.Exception.Message
        script  = 'Get-CalibrationStatus.ps1'
    }
}

$result | ConvertTo-Json -Depth 5 -Compress
