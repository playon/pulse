#Requires -Version 5.1
<#
.SYNOPSIS
    Detects NVIDIA GPU architecture for Pixellot version-compatibility checks.
.DESCRIPTION
    Pixellot version vs hardware compatibility (per field guidance):
        Win 8                      -> max Pixellot 2.66.17
        Win 10 + Pascal (10xx)     -> max Pixellot 5.2.x
        Win 10 + Turing or newer   -> any Pixellot version

    Architecture is determined from CUDA compute capability:
        5.x -> Maxwell
        6.x -> Pascal
        7.0/7.2 -> Volta
        7.5 -> Turing
        8.x -> Ampere / Ada Lovelace
        9.0 -> Hopper
       10.x -> Blackwell

    Primary source is `nvidia-smi --query-gpu=name,compute_cap` since it
    yields the compute capability directly. Falls back to parsing the
    Win32_VideoController name with a regex when nvidia-smi isn't on the
    PATH (some support hosts).

    Outputs JSON to stdout.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

function _ArchFromCompute([string]$cap) {
    if (-not $cap) { return 'Unknown' }
    # Capture major.minor as decimals (compute_cap is "8.6" / "7.5" etc.)
    if ($cap -notmatch '^\s*(\d+)\.(\d+)') { return 'Unknown' }
    $major = [int]$Matches[1]
    $minor = [int]$Matches[2]
    if ($major -eq 5) { return 'Maxwell' }
    if ($major -eq 6) { return 'Pascal' }
    if ($major -eq 7 -and ($minor -eq 0 -or $minor -eq 2)) { return 'Volta' }
    if ($major -eq 7 -and $minor -eq 5) { return 'Turing' }
    if ($major -eq 8) { return 'Ampere/Ada' }
    if ($major -eq 9) { return 'Hopper' }
    if ($major -ge 10) { return 'Blackwell' }
    return 'Unknown'
}

# Approximate WMI-name -> architecture map for the nvidia-smi fallback.
# Patterns are tried in declaration order; first hit wins.
function _ArchFromName([string]$name) {
    if (-not $name) { return @{ arch = 'Unknown'; cap = $null } }
    # RTX 50xx -> Blackwell, RTX 40xx -> Ada Lovelace, RTX 30xx -> Ampere
    if ($name -match 'RTX\s*50\d{2}')               { return @{ arch = 'Blackwell';  cap = '10.0' } }
    if ($name -match 'RTX\s*40\d{2}')               { return @{ arch = 'Ampere/Ada'; cap = '8.9'  } }
    if ($name -match 'RTX\s*30\d{2}|A\d{3,4}|A100') { return @{ arch = 'Ampere/Ada'; cap = '8.6'  } }
    # T1000 is a Turing (TU117) workstation card; the name has no RTX/GTX token.
    if ($name -match 'RTX\s*20\d{2}|GTX\s*16\d{2}|T1000|T4|Quadro RTX') { return @{ arch = 'Turing';  cap = '7.5' } }
    if ($name -match 'Titan\s*V|V100|GV100')        { return @{ arch = 'Volta';   cap = '7.0' } }
    if ($name -match 'GTX\s*10\d{2}|P100|P40|P4|Quadro P\d{3,4}') { return @{ arch = 'Pascal';  cap = '6.1' } }
    if ($name -match 'GTX\s*9\d{2}|M40|M60|Quadro M\d{3,4}') { return @{ arch = 'Maxwell'; cap = '5.2' } }
    if ($name -match 'H100|H200|GH200')             { return @{ arch = 'Hopper';  cap = '9.0' } }
    if ($name -match 'B100|B200')                   { return @{ arch = 'Blackwell'; cap = '10.0' } }
    return @{ arch = 'Unknown'; cap = $null }
}

# Architectures sorted oldest -> newest for "max" calculation
$ARCH_RANK = @{
    'Unknown'    = 0
    'Maxwell'    = 1
    'Pascal'     = 2
    'Volta'      = 3
    'Turing'     = 4
    'Ampere/Ada' = 5
    'Hopper'     = 6
    'Blackwell'  = 7
}

try {
    $gpus = New-Object System.Collections.ArrayList
    $nvidiaSmiAvailable = $false
    $smiError = $null

    # -- nvidia-smi primary source ----------------------------
    $smiCmd = Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue
    if ($smiCmd) {
        try {
            $smiOutput = & $smiCmd.Source --query-gpu=name,compute_cap --format=csv,noheader 2>$null
            if ($LASTEXITCODE -eq 0 -and $smiOutput) {
                $nvidiaSmiAvailable = $true
                # nvidia-smi CSV format: "Name, 8.6"
                $lines = if ($smiOutput -is [array]) { $smiOutput } else { @($smiOutput) }
                foreach ($line in $lines) {
                    if ([string]::IsNullOrWhiteSpace($line)) { continue }
                    $parts = $line -split ',', 2
                    if ($parts.Count -ne 2) { continue }
                    $name = $parts[0].Trim()
                    $cap  = $parts[1].Trim()
                    [void]$gpus.Add([ordered]@{
                        name         = $name
                        computeCap   = $cap
                        architecture = (_ArchFromCompute $cap)
                        source       = 'nvidia-smi'
                    })
                }
            } else {
                $smiError = "nvidia-smi exited with code $LASTEXITCODE"
            }
        } catch {
            $smiError = $_.Exception.Message
        }
    }

    # -- WMI fallback (or supplement for Intel iGPU) ----------
    $wmiGpus = Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue
    foreach ($wmi in @($wmiGpus)) {
        $wmiName = $wmi.Name
        if (-not $wmiName) { continue }

        # Skip if nvidia-smi already covered this device
        $alreadyKnown = $false
        foreach ($g in $gpus) {
            if ($g.name -and $wmiName -and $wmiName.Contains($g.name)) { $alreadyKnown = $true; break }
            if ($g.name -and $wmiName -and $g.name.Contains($wmiName)) { $alreadyKnown = $true; break }
        }
        if ($alreadyKnown) { continue }

        # NVIDIA-only -- Intel iGPUs and AMD don't apply to Pixellot encoder constraints
        if ($wmiName -notmatch '(?i)NVIDIA|GeForce|Quadro|Tesla|RTX|GTX') {
            [void]$gpus.Add([ordered]@{
                name         = $wmiName
                computeCap   = $null
                architecture = 'NotNvidia'
                source       = 'wmi'
            })
            continue
        }

        $guess = _ArchFromName $wmiName
        [void]$gpus.Add([ordered]@{
            name         = $wmiName
            computeCap   = $guess.cap
            architecture = $guess.arch
            source       = 'wmi-name-pattern'
        })
    }

    # -- Determine primary NVIDIA architecture (highest rank) --
    $primaryArch = 'None'
    $primaryCap  = $null
    $highestRank = -1
    foreach ($g in $gpus) {
        $arch = $g.architecture
        if ($arch -eq 'NotNvidia' -or $arch -eq 'None') { continue }
        $rank = $ARCH_RANK[$arch]
        if ($null -eq $rank) { $rank = 0 }
        if ($rank -gt $highestRank) {
            $highestRank = $rank
            $primaryArch = $arch
            $primaryCap  = $g.computeCap
        }
    }
    if ($primaryArch -eq 'None') {
        $hasAnyNvidia = ($gpus | Where-Object { $_.architecture -ne 'NotNvidia' -and $_.architecture -ne 'None' }).Count -gt 0
        if (-not $hasAnyNvidia) { $primaryArch = 'None' }
    }

    [ordered]@{
        gpus               = @($gpus)
        primaryArchitecture = $primaryArch
        primaryComputeCap  = $primaryCap
        nvidiaSmiAvailable = $nvidiaSmiAvailable
        nvidiaSmiError     = $smiError
    } | ConvertTo-Json -Depth 5 -Compress
}
catch {
    [ordered]@{
        error   = $true
        message = $_.Exception.Message
        script  = 'Get-GpuInfo.ps1'
    } | ConvertTo-Json -Compress
}
