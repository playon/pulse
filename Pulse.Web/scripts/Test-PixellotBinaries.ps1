#Requires -Version 5.1
<#
.SYNOPSIS
    Can Pixellot's programs start? Checks their DLLs and Windows' loader errors.
.DESCRIPTION
    Bear Grass (NC), 2026-10-15: VPU.exe had died at launch on every start
    for a week with "The code execution cannot proceed because libcef.dll was
    not found", and Pulse read PASS. The dialog keeps a 2.8 MB VPU.exe
    process alive, so Get-Services sees it as Running. Two ways to see it:

    1. Static imports. Read the import table of each Pixellot exe in
       C:\Pixellot\Bin and resolve every DLL the way the Windows loader
       does: KnownDLLs, the exe's folder, System32, System, Windows, then
       PATH (machine + user + this process). DLLs that resolve under
       C:\Pixellot are scanned in turn, because a DLL that is present but
       missing its own dependency fails the same way. Delay-load imports
       are skipped (they don't stop the program from starting), and so are
       API-set names (api-ms-*, ext-ms-*), which have no file on disk.

    2. "Application Popup" event 26 in the System log. Windows logs one
       every time a program raises a loader error dialog, with the dialog
       text. A popup at the same second the running VPU.exe was created
       means that copy is stuck on the dialog right now.

    On a healthy 5.37.3 unit, Bin\libcef.dll is a copy of
    C:\Pixellot\dependencies\cef-127.3.5\resources\libcef.dll, put there by
    Pixellot's Dependencies installer. Bear Grass had only cef-78.3.9, so
    the cef* folders are reported as evidence.

    Outputs JSON to stdout.
#>
[CmdletBinding()]
param(
    [int]$DaysBack = 7,
    # Test seam: point at a copy of Bin to prove the scan fires.
    [string]$BinDir = 'C:\Pixellot\Bin'
)

$ErrorActionPreference = 'Stop'

$PIX_ROOT = 'C:\Pixellot'
$PIX_BIN  = $BinDir
$EXES     = @('VPU.exe', 'Agent.exe', 'Coordinator.exe')
$MAX_PARSES = 200
# Seconds and a UTC offset: Python's strptime %z reads it on every version.
$TS = 'yyyy-MM-ddTHH:mm:sszzz'
$INV = [Globalization.CultureInfo]::InvariantCulture

# -- PE import table -------------------------------------------------------
# Returns the static import DLL names, or $null when the file is not a PE we
# can read. Seeks instead of reading the whole file: libcef.dll is 212 MB.
function Get-PeImports([string]$path) {
    $fs = $null
    try {
        $fs = [System.IO.File]::Open($path, 'Open', 'Read', 'ReadWrite')
        $br = New-Object System.IO.BinaryReader($fs)
        if ($fs.Length -lt 0x40) { return $null }
        $null = $fs.Seek(0x3C, 'Begin')
        $peOff = $br.ReadInt32()
        if ($peOff -le 0 -or $peOff -gt ($fs.Length - 24)) { return $null }
        $null = $fs.Seek($peOff, 'Begin')
        if ($br.ReadUInt32() -ne 0x00004550) { return $null }   # 'PE\0\0'
        $null = $br.ReadUInt16()                                # Machine
        $numSections = $br.ReadUInt16()
        $null = $fs.Seek(12, 'Current')
        $optSize = $br.ReadUInt16()
        $null = $br.ReadUInt16()                                # Characteristics
        $optStart = $fs.Position
        $magic = $br.ReadUInt16()
        if ($magic -eq 0x20B) { $ddStart = $optStart + 112 }
        elseif ($magic -eq 0x10B) { $ddStart = $optStart + 96 }
        else { return $null }
        $null = $fs.Seek($ddStart + 8, 'Begin')                 # directory 1 = imports
        $impRva = $br.ReadUInt32()
        $null = $br.ReadUInt32()

        $sections = New-Object 'System.Collections.Generic.List[object]'
        $null = $fs.Seek($optStart + $optSize, 'Begin')
        for ($i = 0; $i -lt $numSections; $i++) {
            $null = $fs.Seek(8, 'Current')
            $vsize = $br.ReadUInt32()
            $va    = $br.ReadUInt32()
            $rsize = $br.ReadUInt32()
            $rptr  = $br.ReadUInt32()
            $null = $fs.Seek(16, 'Current')
            $sections.Add([pscustomobject]@{ va = [int64]$va; size = [int64][math]::Max($vsize, $rsize); ptr = [int64]$rptr })
        }
        $toOff = {
            param([int64]$rva)
            foreach ($s in $sections) {
                if ($rva -ge $s.va -and $rva -lt ($s.va + $s.size)) { return $s.ptr + ($rva - $s.va) }
            }
            return -1
        }

        $names = New-Object 'System.Collections.Generic.List[string]'
        if ($impRva -eq 0) { return ,$names }                   # imports nothing
        $descOff = & $toOff $impRva
        if ($descOff -lt 0) { return $null }
        for ($d = 0; $d -lt 1024; $d++) {
            $null = $fs.Seek($descOff + (20 * $d), 'Begin')
            $null = $br.ReadUInt32(); $null = $br.ReadUInt32(); $null = $br.ReadUInt32()
            $nameRva = $br.ReadUInt32()
            $firstThunk = $br.ReadUInt32()
            if ($nameRva -eq 0 -and $firstThunk -eq 0) { break }
            $nOff = & $toOff $nameRva
            if ($nOff -lt 0) { continue }
            $null = $fs.Seek($nOff, 'Begin')
            $sb = New-Object System.Text.StringBuilder
            for ($c = 0; $c -lt 260; $c++) {
                $b = $br.ReadByte()
                if ($b -eq 0) { break }
                $null = $sb.Append([char]$b)
            }
            if ($sb.Length -gt 0) { $names.Add($sb.ToString()) }
        }
        return ,$names
    }
    catch { return $null }
    finally { if ($fs) { $fs.Dispose() } }
}

try {
    # -- Loader search list ------------------------------------------------
    $winDir = $env:windir
    $sys32 = Join-Path $winDir 'System32'
    # A 32-bit host sees SysWOW64 as System32; Pixellot's exes are 64-bit.
    if ([Environment]::Is64BitOperatingSystem -and -not [Environment]::Is64BitProcess) {
        $sys32 = Join-Path $winDir 'Sysnative'
    }
    $pathDirs = New-Object 'System.Collections.Generic.List[string]'
    foreach ($p in @(
            [Environment]::GetEnvironmentVariable('Path', 'Machine'),
            [Environment]::GetEnvironmentVariable('Path', 'User'),
            $env:Path)) {
        if (-not $p) { continue }
        foreach ($d in ($p -split ';')) {
            $d = [Environment]::ExpandEnvironmentVariables($d.Trim().Trim('"'))
            if ($d -and -not $pathDirs.Contains($d)) { $pathDirs.Add($d) }
        }
    }
    $searchDirs = @($PIX_BIN, $sys32, (Join-Path $winDir 'System'), $winDir) + $pathDirs.ToArray()

    $knownDlls = @{}
    try {
        $kd = Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\KnownDLLs' -ErrorAction Stop
        foreach ($prop in $kd.PSObject.Properties) {
            if ($prop.Value -is [string] -and $prop.Value -like '*.dll') { $knownDlls[$prop.Value.ToLower()] = $true }
        }
    } catch { }

    # The VC 2005/2008 runtimes load from WinSxS by manifest, not the search path.
    $sxsDirs = @()
    try { $sxsDirs = @([System.IO.Directory]::GetDirectories((Join-Path $winDir 'WinSxS'), '*vc*crt*')) } catch { }

    $resolveCache = @{}
    function Resolve-Dll([string]$name) {
        $key = $name.ToLower()
        if ($resolveCache.ContainsKey($key)) { return $resolveCache[$key] }
        $hit = $null
        if ($knownDlls.ContainsKey($key)) { $hit = 'knowndll' }
        if (-not $hit) {
            foreach ($d in $searchDirs) {
                $cand = Join-Path $d $name
                if ([System.IO.File]::Exists($cand)) { $hit = $cand; break }
            }
        }
        if (-not $hit) {
            foreach ($d in $sxsDirs) {
                if ([System.IO.File]::Exists((Join-Path $d $name))) { $hit = 'winsxs'; break }
            }
        }
        $resolveCache[$key] = $hit
        return $hit
    }

    # -- Scan each exe, and the Pixellot DLLs it pulls in ------------------
    $exeResults = New-Object 'System.Collections.Generic.List[object]'
    $parses = 0
    $truncated = $false
    foreach ($exe in $EXES) {
        $exePath = Join-Path $PIX_BIN $exe
        if (-not [System.IO.File]::Exists($exePath)) {
            $exeResults.Add([pscustomobject]@{ name = $exe; present = $false; readable = $false; scanned = 0; missing = @() })
            continue
        }
        $missing = New-Object 'System.Collections.Generic.List[object]'
        $seen = @{}
        $queue = New-Object 'System.Collections.Generic.Queue[string]'
        $queue.Enqueue($exePath)
        $seen[$exePath.ToLower()] = $true
        $readable = $true
        $scanned = 0
        while ($queue.Count -gt 0) {
            if ($parses -ge $MAX_PARSES) { $truncated = $true; break }
            $file = $queue.Dequeue()
            $imports = Get-PeImports $file
            $parses++
            if ($null -eq $imports) {
                if ($file -eq $exePath) { $readable = $false }
                continue
            }
            $scanned++
            foreach ($imp in $imports) {
                $low = $imp.ToLower()
                if ($low.StartsWith('api-ms-') -or $low.StartsWith('ext-ms-')) { continue }
                $where = Resolve-Dll $imp
                if (-not $where) {
                    $missing.Add([pscustomobject]@{ dll = $imp; neededBy = [System.IO.Path]::GetFileName($file) })
                    continue
                }
                if (($where.ToLower().StartsWith($PIX_ROOT.ToLower()) -or $where.ToLower().StartsWith($PIX_BIN.ToLower())) -and -not $seen.ContainsKey($where.ToLower())) {
                    $seen[$where.ToLower()] = $true
                    $queue.Enqueue($where)
                }
            }
        }
        $exeResults.Add([pscustomobject]@{
            name     = $exe
            present  = $true
            readable = $readable
            scanned  = $scanned
            missing  = $missing.ToArray()
        })
    }

    # -- Loader error dialogs (Application Popup 26) -----------------------
    $popupGroups = New-Object 'System.Collections.Generic.List[object]'
    $popupIndex = @{}
    $popupsRead = $true
    $events = @()
    try {
        $events = @(Get-WinEvent -FilterHashtable @{
                LogName = 'System'; ProviderName = 'Application Popup'; Id = 26
                StartTime = (Get-Date).AddDays(-$DaysBack)
            } -MaxEvents 1000 -ErrorAction Stop)
    }
    catch {
        # "No events were found" is a clean empty answer, anything else is not.
        if ($_.Exception.Message -notmatch 'No events were found') { $popupsRead = $false }
    }
    $vpuPopupTimes = New-Object 'System.Collections.Generic.List[datetime]'
    foreach ($ev in $events) {
        $msg = [string]$ev.Message
        if ($msg -notmatch 'Application popup:\s*(?<exe>[^\s]+\.exe)\s*-\s*(?<title>[^:]*):\s*(?<text>.*)$') { continue }
        $exeName = $Matches['exe']
        if (-not [System.IO.File]::Exists((Join-Path $PIX_BIN $exeName))) { continue }
        $text = $Matches['text'].Trim()
        $dll = $null
        if ($text -match '(?<dll>[^\s]+\.dll) was not found') { $dll = $Matches['dll'] }
        $key = ($exeName + '|' + $text).ToLower()
        if (-not $popupIndex.ContainsKey($key)) {
            $g = [pscustomobject]@{
                exe = $exeName; title = $Matches['title'].Trim(); text = $text; dll = $dll
                n = 0; first = $ev.TimeCreated; last = $ev.TimeCreated
            }
            $popupIndex[$key] = $g
            $popupGroups.Add($g)
        }
        $g = $popupIndex[$key]
        $g.n = $g.n + 1
        if ($ev.TimeCreated -lt $g.first) { $g.first = $ev.TimeCreated }
        if ($ev.TimeCreated -gt $g.last) { $g.last = $ev.TimeCreated }
        if ($exeName -ieq 'VPU.exe') { $vpuPopupTimes.Add($ev.TimeCreated) }
    }
    $popupsOut = @(foreach ($g in $popupGroups) {
        [pscustomobject]@{
            exe = $g.exe; title = $g.title; text = $g.text; dll = $g.dll; count = $g.n
            first = $g.first.ToString($TS, $INV); last = $g.last.ToString($TS, $INV)
        }
    })

    # -- Is the running VPU.exe the one showing the dialog? ----------------
    $vpuProcs = @(Get-CimInstance Win32_Process -Filter "Name='VPU.exe'" -ErrorAction SilentlyContinue)
    $procOut = @(foreach ($p in $vpuProcs) {
        $created = $p.CreationDate
        $stuck = $false
        if ($created) {
            foreach ($t in $vpuPopupTimes) {
                if ([math]::Abs(($t - $created).TotalSeconds) -le 30) { $stuck = $true; break }
            }
        }
        [pscustomobject]@{
            pid        = [int]$p.ProcessId
            created    = if ($created) { $created.ToString($TS, $INV) } else { $null }
            workingSetMB = if ($p.WorkingSetSize) { [math]::Round($p.WorkingSetSize / 1MB, 1) } else { $null }
            stuckOnLoaderError = $stuck
        }
    })

    $cefDirs = @()
    $depDir = Join-Path $PIX_ROOT 'dependencies'
    if (Test-Path -LiteralPath $depDir) {
        $cefDirs = @(Get-ChildItem -LiteralPath $depDir -Directory -Filter 'cef*' -ErrorAction SilentlyContinue |
            Sort-Object Name | ForEach-Object { $_.Name })
    }

    [pscustomobject]@{
        now           = (Get-Date).ToString($TS, $INV)
        exes          = $exeResults.ToArray()
        truncated     = $truncated
        popupsRead    = $popupsRead
        popupDays     = $DaysBack
        popups        = $popupsOut
        vpuProcesses  = $procOut
        binHasLibcef  = [System.IO.File]::Exists((Join-Path $PIX_BIN 'libcef.dll'))
        cefPackages   = $cefDirs
    } | ConvertTo-Json -Depth 5 -Compress
}
catch {
    [ordered]@{
        error   = $true
        message = $_.Exception.Message
        script  = 'Test-PixellotBinaries.ps1'
    } | ConvertTo-Json -Compress
}
