#Requires -Version 5.1
<#
.SYNOPSIS
    Probes ScoreConnect service for status, configuration, BOT status, and ScoreLink detection.
.DESCRIPTION
    Makes HTTP requests to the ScoreConnect local API to check reachability, retrieve
    configuration, and fetch cloud BOT status. Also enumerates Win32_PnPEntity to detect
    whether a ScoreLink hardware box is connected via USB. Outputs JSON to stdout.

    Configuration fields are normalised to renderer-friendly names (vendor, sport, etc.)
    using the same alias tables as the WPF ScoreConnectService.

    ScoreConnect product versions:
      SC III  -- web-based (localhost:5000), raw RTD data only, no parsed scores.
                This script targets SC III.
      SC II   -- web-based, has parsed scoreboard data (team names, scores, clock).
      SC I    -- standalone .exe, has parsed data but no HTTP API.

    Real SC III get-status shape (v1.4.x):
      { botNumber, scoreBoardData: {id, messageType, description},
        network: {id, messageType, description}, isConnectedToBotServer,
        hasLocalStream, updateInProgress, data, botConfigurationInProgress }

    Known issues:
      - botNumber from get-status and get-bot-number is notoriously stale on
        SC III -- often shows a previous unit's number until a service reset.
        Surfaced as best-effort, not authoritative.
      - Bus-reported device description (DEVPKEY) requires admin access on some
        VPU builds. VID/PID fallback (04D8/00DD) covers ScoreLink detection.
#>
[CmdletBinding()]
param(
    [string]$BaseUrl = 'http://127.0.0.1:5000'
)

$ErrorActionPreference = 'Stop'

# -- Helpers ------------------------------------------------------------------

# Emit an object as compressed JSON with any literal C0 control bytes escaped.
# Windows PowerShell 5.1's ConvertTo-Json (unlike PS 7's) leaves control bytes
# unescaped inside strings -- the raw Daktronics RTD scoreboard string uses
# STX/ETX framing, and findstr scraping a UTF-16 SC I log can yield embedded
# NULs. The server parses our stdout with a strict JSON reader that rejects
# literal control characters, so a single stray byte voids the whole payload
# ("Invalid JSON from Get-ScoreConnectStatus.ps1"). Replacing only literal
# bytes is idempotent: anything ConvertTo-Json already escaped is a two-char
# backslash sequence, not a literal byte, so it's untouched. No-op on PS 7+.
function Out-StatusJson {
    param($Obj, [int]$Depth = 10)
    $json = $Obj | ConvertTo-Json -Depth $Depth -Compress
    [regex]::Replace($json, '[\x00-\x1F]', { param($m) '\u{0:x4}' -f [int][char]$m.Value[0] })
}

function Invoke-SafeGet {
    param([string]$Url, [int]$TimeoutSec = 2)
    try {
        # Pre-check TCP connection with explicit socket timeout.
        # Invoke-WebRequest's -TimeoutSec only covers the response phase;
        # a SYN-blackholed port can hang for 20+ seconds at the TCP layer.
        $uri = [System.Uri]$Url
        $tcp = New-Object System.Net.Sockets.TcpClient
        try {
            $connectTask = $tcp.ConnectAsync($uri.Host, $uri.Port)
            if (-not $connectTask.Wait($TimeoutSec * 1000)) {
                return @{ ok = $false; content = $null }
            }
            if ($connectTask.IsFaulted) {
                return @{ ok = $false; content = $null }
            }
        } finally { $tcp.Dispose() }

        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec -ErrorAction Stop
        if ($r.StatusCode -eq 200) { return @{ ok = $true; content = $r.Content } }
    } catch {}
    return @{ ok = $false; content = $null }
}

# Pick the first non-empty string value from a hashtable by an ordered list of
# candidate keys.  Uses PowerShell's -eq operator which is case-insensitive by
# default (e.g. 'VendorName' -eq 'vendorName' -> True).  Do NOT replace with a
# direct hashtable index ($Map[$k]) -- that would break the case-insensitive
# matching that SC III's inconsistent casing requires.
function Pick-First {
    param([hashtable]$Map, [string[]]$Keys)
    foreach ($k in $Keys) {
        foreach ($mk in $Map.Keys) {
            if ($mk -eq $k) {
                $v = $Map[$mk]
                if ($null -ne $v -and "$v".Trim() -ne '') { return "$v" }
            }
        }
    }
    return $null
}

# Flatten a PSCustomObject (from ConvertFrom-Json) into a case-insensitive hashtable.
# Only scalar values are kept as strings; nested objects/arrays are skipped so
# Pick-First never sees a "System.Management.Automation.PSCustomObject" string.
function To-Map {
    param($Obj)
    $map = @{}
    if ($null -eq $Obj) { return $map }
    foreach ($p in $Obj.PSObject.Properties) {
        if ($null -eq $p.Value) {
            $map[$p.Name] = $null
        } elseif ($p.Value -is [string] -or $p.Value -is [bool] -or $p.Value -is [ValueType]) {
            $map[$p.Name] = "$($p.Value)"
        }
        # Nested PSCustomObject / arrays are intentionally omitted
    }
    return $map
}

# Read DEVPKEY_Device_BusReportedDeviceDesc from the PnP property store.
# Same registry path as the WPF ScoreLinkDetector; value name is empty string (default).
# NOTE: Requires admin/elevated access on some VPU builds. Returns '' on access-denied.
function Get-BusReportedDesc {
    param([string]$PnpDeviceId)
    if (-not $PnpDeviceId) { return '' }
    try {
        $regPath = "HKLM:\SYSTEM\CurrentControlSet\Enum\$PnpDeviceId\Properties\{a45c254e-df1c-4efd-8020-67d146a850e0}\0004"
        $key = Get-Item -LiteralPath $regPath -ErrorAction Stop
        $v = $key.GetValue('')
        if (-not $v) { $v = $key.GetValue('Data') }
        return [string]$v
    } catch { return '' }
}

# Read FileVersion from the ScoreConnect III executable on disk.
# get-status has no version field -- this is the only reliable source.
function Get-ScoreConnectExeVersion {
    $candidates = @(
        'C:\Program Files (x86)\Sportzcast LLC\ScoreConnectIII\ScoreConnectIII.exe',
        'C:\Program Files\Sportzcast LLC\ScoreConnectIII\ScoreConnectIII.exe'
    )
    foreach ($path in $candidates) {
        try {
            if (-not (Test-Path -LiteralPath $path)) { continue }
            $info = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($path)
            $v = $info.ProductVersion
            if (-not $v) { $v = $info.FileVersion }
            if ($v) {
                # Trim git commit hash suffix: "1.4.0.10+bf99cfe..." -> "1.4.0.10"
                $v = $v.Trim()
                $plusIdx = $v.IndexOf('+')
                if ($plusIdx -gt 0) { $v = $v.Substring(0, $plusIdx) }
                return $v
            }
        } catch {}
    }
    return $null
}

# Read FileVersion from an arbitrary exe (used for the SC I executable).
function Get-ExeVersionAt {
    param([string]$Path)
    try {
        if (-not (Test-Path -LiteralPath $Path)) { return $null }
        $info = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($Path)
        $v = $info.ProductVersion; if (-not $v) { $v = $info.FileVersion }
        if ($v) {
            $v = $v.Trim(); $p = $v.IndexOf('+'); if ($p -gt 0) { $v = $v.Substring(0, $p) }
            return $v
        }
    } catch {}
    return $null
}

# -- ScoreConnect service detection --------------------------------------------
# Adapted from Canopy's scoreboardModeSet.ps1. The Windows service names are
# 'scoreconnect' (SC I), 'scoreconnectii' (SC II), 'scoreconnectiii' (SC III).
# Get-Service -Name matches exactly, so 'scoreconnect' won't match the others.
# Returns @{ sc1; sc2; sc3 } booleans for which versions are RUNNING, plus
# 'installed' for which are present at all.
function Get-ScoreConnectServices {
    $running   = [ordered]@{ sc1 = $false; sc2 = $false; sc3 = $false }
    $installed = [ordered]@{ sc1 = $false; sc2 = $false; sc3 = $false }
    try {
        $svcs = Get-Service -Name 'scoreconnect', 'scoreconnectii', 'scoreconnectiii' -ErrorAction SilentlyContinue
        foreach ($s in $svcs) {
            $key = switch ($s.Name.ToLower()) {
                'scoreconnect'    { 'sc1' }
                'scoreconnectii'  { 'sc2' }
                'scoreconnectiii' { 'sc3' }
                default           { $null }
            }
            if ($key) {
                $installed[$key] = $true
                if ($s.Status -eq 'Running') { $running[$key] = $true }
            }
        }
    } catch {}
    return @{ running = $running; installed = $installed }
}

# Best-effort BOT number from SC I logs. The bot id is written as "BOT=<id>".
# Logs may be UTF-16, so use findstr (encoding-safe) per the VPU log-parsing
# guidance rather than Select-String. The bot id is notoriously stale anyway --
# surfaced best-effort.
function Get-ScoreConnectILogBot {
    $logDir = 'C:\Program Files (x86)\Sportzcast LLC\ScoreConnect\Logs'
    if (-not (Test-Path $logDir)) { return $null }
    try {
        $hit = & findstr.exe /S /I /C:"BOT=" "$logDir\*" 2>$null | Select-Object -First 1
        if ($hit -and ($hit -match 'BOT=([^\s,;]+)')) {
            $bot = $Matches[1].Trim()
            if ($bot) { return $bot }
        }
    } catch {}
    return $null
}

# -- SC I probe (file-based) ---------------------------------------------------
# Adapted from Canopy's scoreboardModeSet.ps1. SC I is a legacy standalone
# install with no HTTP API. Configuration lives in:
#   C:\Program Files (x86)\Sportzcast LLC\ScoreConnect\Files\Parms.json
# Schema: parms[0].sbvendor / .sbcode (no sbvendorname like SC II has).
#
# "Out of date" detection: very old SC I builds leave stray .txt files in the
# Files folder instead of a Parms.json -- Canopy treats their presence as an
# out-of-date install that should be upgraded.
#
# Returns an object shaped like the SC II probe (hardware = 'ScoreConnect') so
# the existing renderer surfaces it in the legacy ScoreConnect panel without
# any frontend changes. Zero network/disk impact on a live data stream.
function Probe-ScoreConnectI {
    $result = @{
        reachable    = $false
        baseUrl      = $null
        version      = $null
        hardware     = 'ScoreConnect'
        productName  = 'ScoreConnect (SC I)'
        uid          = $null
        scores       = $null
        teamNames    = $null
        vendor       = $null
        vendorIsCode = $false
        sport        = $null
        botNumber    = $null
        license      = $null
        scoreLink    = $null
        networkIfaces = $null
        outOfDate    = $false
        error        = $null
    }

    $filesDir = 'C:\Program Files (x86)\Sportzcast LLC\ScoreConnect\Files'
    if (-not (Test-Path $filesDir)) { return $result }

    # Out-of-date: stray .txt files in the Files folder (no Parms.json era).
    $strayTxt = Get-ChildItem -Path $filesDir -Filter '*.txt' -File -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($strayTxt) {
        $result.reachable = $true
        $result.outOfDate = $true
        $result.version   = 'Out of date'
        $result.error     = 'ScoreConnect (SC I) software is out of date. Upgrade to SC III.'
        return $result
    }

    $parmsPath = Join-Path $filesDir 'Parms.json'
    if (-not (Test-Path $parmsPath)) { return $result }

    try {
        $json = Get-Content $parmsPath -Raw -ErrorAction Stop | ConvertFrom-Json
        if (-not $json.parms -or @($json.parms).Count -lt 1) {
            $result.reachable = $true
            $result.error = 'Unreadable SC I configuration'
            return $result
        }
        $p = $json.parms[0]
        $result.reachable = $true
        # Prefer a human-readable vendor name when the SC I build provides one
        # (sbvendorname); older builds expose only the numeric sbvendor code.
        # When it's a bare code the renderer labels it "(code)" rather than
        # presenting a meaningless number as a vendor name.
        $vn = $p.sbvendorname
        $vendorIsCode = $false
        if (-not $vn) {
            $vn = $p.sbvendor
            if ($vn -ne $null -and ("$vn" -match '^\d+$')) { $vendorIsCode = $true }
        }
        $result.vendor       = $vn
        $result.vendorIsCode = $vendorIsCode
        $result.sport        = $p.sbcode
        $result.botNumber = Get-ScoreConnectILogBot
        $result.version   = Get-ExeVersionAt 'C:\Program Files (x86)\Sportzcast LLC\ScoreConnect\ScoreConnect.exe'
    }
    catch {
        $result.reachable = $true
        $result.error = 'Unreadable SC I configuration'
    }
    return $result
}

# -- SC II probe (SignalR long-polling) ---------------------------------------
# SC II uses SignalR 2.x on localhost:1400.  No REST API -- all data flows
# through the ScoreConnectHub hub.  We use the long-polling transport so we
# don't need a WebSocket library.
#
# Flow: negotiate -> connect -> start -> send getsettings -> send uidlogin ->
#       send getparms -> poll for broadcasts -> parse and return.
#
# Parsed score data is broadcast as individual topics:
#   status_vscore, status_hscore, status_clock, status_text1/2/3
# Status LEDs: status_scoreboard_led, status_network_led, etc.  (0=off 1=yellow 2=green)

function Probe-ScoreConnectII {
    param([string]$Sc2Base = 'http://localhost:1400')

    # -- ZERO-IMPACT PROBE ----------------------------------------------
    # SC II is single-threaded.  ANY SignalR connection (even short-lived)
    # blocks the server from servicing the real client, freezing live data.
    #
    # Strategy: TCP check (is it running?) + read settings.json from disk.
    # No HTTP requests to SC II at all -- zero impact on the data stream.
    #
    # settings.json contains: version, hardware, UID, team names, vendor,
    # sport, bot#, license, scorelink device, network interfaces.
    # Live scores (clock, vscore, hscore) are NOT available without SignalR.

    $result = @{
        reachable    = $false
        baseUrl      = $Sc2Base
        version      = $null
        hardware     = $null
        uid          = $null
        scores       = $null
        teamNames    = $null
        vendor       = $null
        sport        = $null
        botNumber    = $null
        statusLeds   = $null
        license      = $null
        scoreLink    = $null
        networkIfaces = $null
        error        = $null
        _diag        = $null
    }

    $sw = [System.Diagnostics.Stopwatch]::StartNew()

    try {
        # -- 1. TCP check on port 1400 -- is SC II running? ------------------
        $sc2Uri = [System.Uri]$Sc2Base
        $tcp = New-Object System.Net.Sockets.TcpClient
        try {
            $ct = $tcp.ConnectAsync($sc2Uri.Host, $sc2Uri.Port)
            if (-not $ct.Wait(1500)) { return $result }
            if ($ct.IsFaulted) { return $result }
        } finally { $tcp.Dispose() }

        $result.reachable = $true

        # -- 2. Read settings.json from disk ---------------------------------
        $settingsPath = $null
        $searchPaths = @(
            'C:\Program Files (x86)\Sportzcast\ScoreConnectII\Files\settings.json',
            'C:\Program Files\Sportzcast\ScoreConnectII\Files\settings.json'
        )
        foreach ($p in $searchPaths) {
            if (Test-Path $p) { $settingsPath = $p; break }
        }

        if (-not $settingsPath) {
            # Fallback: search common install roots
            $found = Get-ChildItem 'C:\Program Files*\Sportzcast' -Recurse -Filter 'settings.json' -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($found) { $settingsPath = $found.FullName }
        }

        if ($settingsPath) {
            $json = Get-Content $settingsPath -Raw -ErrorAction Stop | ConvertFrom-Json

            $result.version  = $json.version
            $result.hardware = $json.hardware
            $result.uid      = $json.instance_uid

            # parms array -- first slot has the active config
            $parms = $null
            if ($json.parms -and $json.parms.Count -gt 0) {
                $parms = $json.parms[0]
            }

            if ($parms) {
                $result.teamNames = @{
                    visitor = $parms.visitor_teamname
                    home    = $parms.home_teamname
                }
                $vn = $parms.sbvendorname
                if (-not $vn) { $vn = $parms.sbvendor }
                $result.vendor    = $vn
                $result.sport     = $parms.sbcode
                $result.botNumber = $parms.botnumber
                $result.license   = $parms.licenseexp

                $result.scoreLink = @{
                    description = $parms.scorelink_desc
                    type        = $parms.scorelink_typ
                    address     = $parms.scorelink_address
                    serial      = $parms.usbserial
                }
            }

            # Network interfaces
            if ($json.nics -and $json.nics.Count -gt 0) {
                $result.networkIfaces = @($json.nics | ForEach-Object {
                    @{ name = $_.name; address = $_.address; type = $_.type }
                })
            }

            $result._diag = @{
                mode         = 'file'
                settingsPath = $settingsPath
                elapsedMs    = [int]$sw.ElapsedMilliseconds
            }
        }
        else {
            $result._diag = @{
                mode      = 'tcp-only'
                elapsedMs = [int]$sw.ElapsedMilliseconds
                note      = 'settings.json not found on disk'
            }
        }
    }
    catch {
        $result.error = $_.Exception.Message
    }

    return $result
}

try {
    $BaseUrl = $BaseUrl.TrimEnd('/')
    # 'localhost' can take 12-40s to resolve in a fresh process (VPU2,
    # 2026-09-29); 127.0.0.1 answers at once. SC III listens on IPv4 and IPv6.
    $BaseUrl = $BaseUrl -replace '^(https?://)localhost(?=[:/]|$)', '${1}127.0.0.1'

    # -- 1. Status probe -----------------------------------------------------
    $reachable  = $false
    $statusData = $null
    $errorMsg   = $null
    $version    = $null

    # get-status is the primary endpoint -- it carries BOT status, score data
    # status, network state, and the raw scoreboard data string.
    $sr = Invoke-SafeGet "$BaseUrl/api/configuration/get-status"
    if ($sr.ok) {
        $reachable = $true
        try { $statusData = $sr.content | ConvertFrom-Json } catch {}
    }

    # Fallback: if get-status fails, try get-current-configuration to confirm
    # reachability (root is too broad -- matches any HTTP server).
    if (-not $reachable) {
        $sr2 = Invoke-SafeGet "$BaseUrl/api/configuration/get-current-configuration"
        if ($sr2.ok) { $reachable = $true }
    }

    # NOTE: do NOT set $errorMsg here just because SC III isn't answering on
    # :5000. SC III being absent is an expected state on a legacy box -- this
    # VPU may be running SC I or SC II, which we still detect and report below
    # in the `sc2`/legacy slot. The `reachable` flag already conveys SC III's
    # status; the top-level `error` field is reserved for a genuine probe
    # failure (the catch block). Setting it here made the frontend treat a
    # legacy-only VPU as a fatal "Failed to load data" and discard the SC I/II
    # data we collected.

    # Version: get-status has no version field -- always use exe on disk.
    $version = Get-ScoreConnectExeVersion

    # -- 2. Extract status fields --------------------------------------------
    # Real get-status shape (v1.4.x):
    #   { botNumber: 0,
    #     scoreBoardData: { id, messageType, description },
    #     network: { id, messageType, description },
    #     isConnectedToBotServer: bool,
    #     hasLocalStream: bool,
    #     data: "raw RTD string",
    #     updateInProgress: bool,
    #     botConfigurationInProgress: bool }

    $dataStatus    = $null   # "Data is present..." or "No Scoreboard data..."
    $rawData       = $null   # Raw RTD protocol string from scoreboard
    $networkStatus = $null   # "Internet is detected" etc.
    $hasLocalStream = $null
    $isConnectedToBotServer = $null

    if ($statusData) {
        # scoreBoardData.description -- tells us if data is flowing
        if ($statusData.PSObject.Properties['scoreBoardData'] -and $statusData.scoreBoardData) {
            $dataStatus = $statusData.scoreBoardData.description
        }

        # Raw data string (Daktronics RTD etc.) -- trim whitespace padding
        if ($statusData.PSObject.Properties['data']) {
            $rawStr = "$($statusData.data)".Trim()
            if ($rawStr -ne '') { $rawData = $rawStr }
        }

        # Network status
        if ($statusData.PSObject.Properties['network'] -and $statusData.network) {
            $networkStatus = $statusData.network.description
        }

        # Booleans
        if ($statusData.PSObject.Properties['hasLocalStream']) {
            $hasLocalStream = [bool]$statusData.hasLocalStream
        }
        if ($statusData.PSObject.Properties['isConnectedToBotServer']) {
            $isConnectedToBotServer = [bool]$statusData.isConnectedToBotServer
        }
    }

    # -- 3. Extended configuration --------------------------------------------
    # Try extended first (carries vendor/sport names), fall back to plain
    # (only numeric IDs -- less useful but confirms the config endpoint works).
    $configuration = $null
    if ($reachable) {
        foreach ($cfgPath in @(
            "$BaseUrl/api/configuration/get-current-configuration-extended",
            "$BaseUrl/api/configuration/get-current-configuration"
        )) {
            $cr = Invoke-SafeGet $cfgPath
            if ($cr.ok) {
                try {
                    $rawCfg = $cr.content | ConvertFrom-Json
                    $cfgMap = To-Map $rawCfg

                    # Normalise field names using the same alias tables as WPF
                    # PopulateConfigurationFromJson.
                    $configuration = [ordered]@{
                        vendor                  = Pick-First $cfgMap @('vendorName', 'vendor', 'currentVendor', 'currentSbvendor')
                        sport                   = Pick-First $cfgMap @('vendorSportName', 'sport', 'vendorSport', 'sportName', 'vendorSportCode', 'currentSbCode')
                        vendorConfigurationName = Pick-First $cfgMap @('vendorConfigurationName', 'configurationName')
                        device                  = Pick-First $cfgMap @('device', 'deviceName', 'deviceId')
                        serialPort              = Pick-First $cfgMap @('serialPort', 'port', 'comPort', 'portName')
                        firmware                = Pick-First $cfgMap @('firmware', 'firmwareVersion', 'fwVersion')
                        eventType               = Pick-First $cfgMap @('eventType', 'eventTypeName', 'eventTypeId')
                    }
                    # If normalization found anything, stop trying endpoints
                    $hasAny = $false
                    foreach ($v in $configuration.Values) { if ($v) { $hasAny = $true; break } }
                    if ($hasAny) { break }
                } catch {}
            }
        }
    }

    # -- 4. BOT status --------------------------------------------------------
    # NOTE: The bot number reported by SC III is notoriously stale -- it often
    # shows a previous unit's number and only corrects after a service reset.
    # Do NOT treat it as authoritative.  We still surface it ("best-effort")
    # because _some_ value is better than none for field triage, but the UI
    # should not emphasize it.
    #
    # isConnectedToBotServer from get-status is the most trustworthy boolean
    # for cloud connection state.
    $botStatus = $null
    if ($reachable) {
        $botIsConnected    = $false
        $botScoreConnectId = $null
        $botServerAddress  = $null
        $botLastError      = $null

        # get-status fields (already parsed above)
        if ($null -ne $isConnectedToBotServer) {
            $botIsConnected = $isConnectedToBotServer
        }
        if ($statusData -and $statusData.PSObject.Properties['botNumber']) {
            $bn = [long]$statusData.botNumber
            if ($bn -gt 0) { $botScoreConnectId = "$bn" }
        }

        # Fallback: dedicated get-bot-number endpoint
        if (-not $botScoreConnectId) {
            $br = Invoke-SafeGet "$BaseUrl/api/configuration/get-bot-number"
            if (-not $br.ok) {
                $br = Invoke-SafeGet "$BaseUrl/api/v2/configuration/get-bot-configuration-status"
            }
            if ($br.ok -and $br.content) {
                $trimmed = $br.content.Trim()
                if ($trimmed -match '^\d+$') {
                    $bareNumber = [long]$trimmed
                    if ($bareNumber -gt 0) { $botScoreConnectId = $trimmed }
                    if (-not $botIsConnected -and $bareNumber -gt 0) { $botIsConnected = $true }
                } else {
                    try {
                        $botObj = $trimmed | ConvertFrom-Json
                        $botMap = To-Map $botObj

                        $botNumStr = Pick-First $botMap @('botNumber', 'bot_number')
                        if ($null -ne $botNumStr -and ([long]$botNumStr) -gt 0) {
                            $botScoreConnectId = $botNumStr
                        }
                        if (-not $botIsConnected) {
                            $connStr = Pick-First $botMap @('botOnline', 'isConnected', 'cloudConnection', 'isCloudMode')
                            $botIsConnected = ($connStr -eq 'True' -or $connStr -eq 'true' -or $connStr -eq '1')
                        }
                        if (-not $botScoreConnectId) {
                            $idStr = Pick-First $botMap @('scoreConnectId', 'id')
                            if ($idStr) { $botScoreConnectId = $idStr }
                        }
                        $botServerAddress = Pick-First $botMap @('botServerAddress', 'botAddress', 'botServer')
                        $botLastError     = Pick-First $botMap @('lastErrorMessage', 'lastError', 'errorMessage')
                    } catch {}
                }
            }
        }

        $botStatus = [ordered]@{
            isConnected      = $botIsConnected
            scoreConnectId   = $botScoreConnectId
            botServerAddress = $botServerAddress
            lastErrorMessage = $botLastError
        }
    }

    # -- 5. ScoreLink USB detection -------------------------------------------
    # Detection priority:
    #   1. Bus-reported description (DEVPKEY_Device_BusReportedDeviceDesc) --
    #      requires admin access, may fail with SecurityException.
    #   2. Caption / Description / Name string matching -- secondary.
    #   3. VID/PID matching -- tertiary fallback when bus-reported is access-
    #      denied and generic driver names ("USB Serial Device") don't match.
    #      Known VID/PID pairs for Sportzcast hardware:
    #        VID_04D8 & PID_00DD = Microchip MCP2221 (ScoreLink / ScoreLinkII)
    #
    # Not cached -- runs every poll cycle (~30s).  The WMI USB enumeration is
    # sub-100ms and ScoreLink hardware can be plugged/unplugged between polls.
    $scoreLinkConnected = $false
    $scoreLinkPort      = ''
    $scoreLinkModel     = ''

    $busNeedles = @(
        @{ needle = 'scorelinkii';                model = 'ScoreLinkII' },
        @{ needle = 'scorelink ii';               model = 'ScoreLinkII' },
        @{ needle = 'score link ii';              model = 'ScoreLinkII' },
        @{ needle = 'mcp2221 usb-i2c/uart combo'; model = 'ScoreLink'   },
        @{ needle = 'mcp2221';                    model = 'ScoreLink'   }
    )

    # VID/PID pairs for Sportzcast hardware -- fallback when bus-reported
    # description is access-denied and Caption is generic ("USB Serial Device").
    $vidPidMap = @{
        'VID_04D8&PID_00DD' = 'ScoreLink'
    }

    $comRx = [regex]'\bCOM(\d+)\b'

    # OS-version-aware generic serial-driver description (from Canopy's
    # usbConnectionCheck.ps1). Windows 8 / 8.1 (6.2-6.3) name the inbox
    # USB-serial driver "USB Serial Port"; every other build uses "USB Serial
    # Device". Used as a LAST-RESORT needle (after the specific name + VID/PID
    # strategies) so a ScoreLink whose bus-reported description is access-
    # denied and whose VID/PID didn't enumerate is still recognised by its
    # generic serial driver name.
    $osSerialDesc = 'usb serial device'
    try {
        $osVer = [version]((Get-CimInstance Win32_OperatingSystem -ErrorAction Stop).Version)
        if ($osVer -ge [version]'6.2' -and $osVer -lt [version]'6.4') {
            $osSerialDesc = 'usb serial port'
        }
    } catch {}

    try {
        # USB\ filter -- WPF checks pnpId.StartsWith("USB\\").
        # WQL escaping: 'USB\\%' is a literal backslash + wildcard.
        # Some WMI provider builds reject the escaped backslash, so fall back
        # to a broader query with client-side filtering if the first fails.
        $pnpDevices = $null
        try {
            $pnpDevices = Get-CimInstance -ClassName Win32_PnPEntity `
                -Filter "PNPDeviceID LIKE 'USB\\%'" -ErrorAction Stop
        } catch {
            $allDevices = Get-CimInstance -ClassName Win32_PnPEntity -ErrorAction Stop
            $pnpDevices = $allDevices | Where-Object { $_.PNPDeviceID -like 'USB\*' }
        }

        foreach ($dev in $pnpDevices) {
            $caption     = [string]$dev.Caption
            $name        = [string]$dev.Name
            $description = [string]$dev.Description
            $pnpId       = [string]$dev.PNPDeviceID

            # Must expose a COM port number in Name or Caption
            $pm = $comRx.Match($name)
            if (-not $pm.Success) { $pm = $comRx.Match($caption) }
            if (-not $pm.Success) { continue }
            $portName = 'COM' + $pm.Groups[1].Value

            # Strategy 1: bus-reported + Caption/Description needle matching
            $busDesc = Get-BusReportedDesc $dev.PNPDeviceID
            $busLow  = $busDesc.ToLower()
            $capLow  = $caption.ToLower()
            $drvLow  = $description.ToLower()

            $matched = $null
            foreach ($entry in $busNeedles) {
                if ($busLow.Contains($entry.needle) -or
                    $capLow.Contains($entry.needle) -or
                    $drvLow.Contains($entry.needle)) {
                    $matched = $entry; break
                }
            }

            # Strategy 2: VID/PID fallback -- needed when bus-reported description
            # is access-denied and Caption is generic ("USB Serial Device").
            if ($null -eq $matched) {
                $pnpUpper = $pnpId.ToUpper()
                foreach ($vidpid in $vidPidMap.Keys) {
                    if ($pnpUpper.Contains($vidpid)) {
                        $matched = @{ needle = $vidpid; model = $vidPidMap[$vidpid] }
                        break
                    }
                }
            }

            # Strategy 3 (last resort): OS-aware generic serial-driver name.
            # On a VPU the ScoreLink is the USB-serial adapter, so a COM-port
            # device whose driver description is the OS's generic serial name
            # is treated as a ScoreLink. Heuristic -- could in theory match an
            # unrelated USB-serial adapter, hence it runs only after the
            # specific name and VID/PID strategies fail.
            if ($null -eq $matched -and $drvLow.Contains($osSerialDesc)) {
                $matched = @{ needle = $osSerialDesc; model = 'ScoreLink' }
            }

            if ($null -eq $matched) { continue }

            # ScoreLinkII wins over ScoreLink when both are present
            if ($matched.model -eq 'ScoreLinkII' -or -not $scoreLinkConnected) {
                $scoreLinkConnected = $true
                $scoreLinkPort      = $portName
                $scoreLinkModel     = $matched.model
                if ($matched.model -eq 'ScoreLinkII') { break }
            }
        }
    } catch {}

    $scoreLinkLabel = if (-not $scoreLinkConnected) {
        'ScoreLink not connected'
    } elseif (-not $scoreLinkPort) {
        "$scoreLinkModel device connected"
    } else {
        "$scoreLinkModel device connected ($scoreLinkPort)"
    }

    # -- 6. Legacy ScoreConnect probe (SC II, else SC I) ----------------------
    # Per Canopy's scoreboardModeSet.ps1, determine which versions are running
    # via Get-Service, then read the appropriate config source. SC III is
    # handled above (HTTP); here we cover the legacy installs that previously
    # showed "not detected": SC II (settings.json) and SC I (Parms.json).
    #
    # The running legacy version is normalised into the `sc2` output slot
    # (hardware distinguishes SC I vs SC II) so the existing renderer surfaces
    # it in the legacy ScoreConnect panel without any frontend changes.
    $svc = Get-ScoreConnectServices

    # SC II -- rich file-based probe on port 1400 (settings.json).
    $sc2BaseUri = [System.Uri]$BaseUrl
    $sc2Url     = "http://$($sc2BaseUri.Host):1400"
    $sc2Data    = Probe-ScoreConnectII -Sc2Base $sc2Url

    # SC I -- only when SC II isn't present. Probe if the SC I service is
    # running/installed, or its config exists on disk (covers a stopped
    # service that's still configured).
    $legacyData = $null
    if ($sc2Data.reachable) {
        $legacyData = $sc2Data
    }
    elseif ($svc.installed.sc1 -or (Test-Path 'C:\Program Files (x86)\Sportzcast LLC\ScoreConnect\Files')) {
        $sc1Data = Probe-ScoreConnectI
        if ($sc1Data.reachable) { $legacyData = $sc1Data }
    }

    # -- 7. Output ------------------------------------------------------------
    $result = [ordered]@{
        reachable            = $reachable
        baseUrl              = $BaseUrl
        version              = $version
        dataStatus           = $dataStatus
        rawData              = $rawData
        networkStatus        = $networkStatus
        hasLocalStream       = $hasLocalStream
        configuration        = $configuration
        botStatus            = $botStatus
        scoreLinkConnected   = $scoreLinkConnected
        scoreLinkPort        = $scoreLinkPort
        scoreLinkModel       = $scoreLinkModel
        scoreLinkStatusLabel = $scoreLinkLabel
        services             = $svc.running
        error                = $errorMsg
        sc2                  = $legacyData
    }
    Out-StatusJson $result
}
catch {
    $errResult = [ordered]@{
        reachable            = $false
        baseUrl              = $BaseUrl
        version              = $null
        dataStatus           = $null
        rawData              = $null
        networkStatus        = $null
        hasLocalStream       = $null
        configuration        = $null
        botStatus            = $null
        scoreLinkConnected   = $false
        scoreLinkPort        = ''
        scoreLinkModel       = ''
        scoreLinkStatusLabel = 'ScoreLink not connected'
        error                = $_.Exception.Message
        sc2                  = $null
    }
    Out-StatusJson $errResult
}
