#Requires -Version 5.1
<#
.SYNOPSIS
    Reads Pixellot configuration from the registry and calibration folders.
.DESCRIPTION
    Gathers all Pixellot registry values and the calibration status
    recorded on disk. Outputs JSON to stdout.
    Pixellot stopped using cameras.cfg around agent 2.3 (Logan, 2026-10-12).
    It is deliberately not read: current units can have no file or a stale one.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

try {
    # Registry values
    $registryConfig = [ordered]@{}
    $regPath = 'HKLM:\SOFTWARE\Pixellot'

    try {
        if (Test-Path $regPath) {
            $regItem = Get-Item -Path $regPath -ErrorAction Stop
            foreach ($valueName in $regItem.GetValueNames()) {
                if ($valueName -ne '') {
                    $registryConfig[$valueName] = $regItem.GetValue($valueName)
                }
            }
        }
    }
    catch { }

    # Calibration status -- recorded by FILE/FOLDER PRESENCE, not a registry
    # flag (confirmed on a VPU 2026-06-15):
    #   * Main camera multisport view:
    #       C:\Pixellot\Data\Configuration\multisportcalibration\<sport>\
    #       one subfolder per sport == calibrated for that sport; folder
    #       mtime ~= when. primary.txt names the default sport.
    #   * OCR / scoreboard:
    #       C:\Pixellot\Data\Configuration\Graphics\pipdesign\
    #       calibrated when enhanced_pip.txt AND innerobjects.txt both exist.
    $calibration = [ordered]@{
        multisport = [ordered]@{ calibrated = $false; sports = @(); primary = $null }
        ocr        = [ordered]@{ calibrated = $false; lastCalibrated = $null; hasEnhancedPip = $false; hasInnerObjects = $false }
    }

    $mscPath = 'C:\Pixellot\Data\Configuration\multisportcalibration'
    if (Test-Path $mscPath) {
        try {
            $sports = @()
            foreach ($f in (Get-ChildItem -LiteralPath $mscPath -Directory -ErrorAction SilentlyContinue)) {
                $sports += [ordered]@{
                    name           = $f.Name
                    lastCalibrated = $f.LastWriteTime.ToString('o')
                }
            }
            $calibration.multisport.sports     = @($sports)
            $calibration.multisport.calibrated = ($sports.Count -gt 0)

            $primaryPath = Join-Path $mscPath 'primary.txt'
            if (Test-Path $primaryPath) {
                $primaryRaw = Get-Content -LiteralPath $primaryPath -Raw -ErrorAction SilentlyContinue
                if ($primaryRaw) { $calibration.multisport.primary = $primaryRaw.Trim() }
            }
        }
        catch { }
    }

    $pipPath = 'C:\Pixellot\Data\Configuration\Graphics\pipdesign'
    if (Test-Path $pipPath) {
        try {
            $enhanced    = Join-Path $pipPath 'enhanced_pip.txt'
            $inner       = Join-Path $pipPath 'innerobjects.txt'
            $hasEnhanced = Test-Path $enhanced
            $hasInner    = Test-Path $inner
            $calibration.ocr.hasEnhancedPip  = $hasEnhanced
            $calibration.ocr.hasInnerObjects = $hasInner
            $calibration.ocr.calibrated      = ($hasEnhanced -and $hasInner)

            $times = @()
            if ($hasInner)    { $times += (Get-Item -LiteralPath $inner).LastWriteTime }
            if ($hasEnhanced) { $times += (Get-Item -LiteralPath $enhanced).LastWriteTime }
            if ($times.Count -gt 0) {
                $calibration.ocr.lastCalibrated = ($times | Sort-Object -Descending | Select-Object -First 1).ToString('o')
            }
        }
        catch { }
    }

    [ordered]@{
        registryConfig  = $registryConfig
        calibration     = $calibration
    } | ConvertTo-Json -Depth 6 -Compress
}
catch {
    [ordered]@{
        error   = $true
        message = $_.Exception.Message
        script  = 'Get-PixellotConfig.ps1'
    } | ConvertTo-Json -Compress
}
