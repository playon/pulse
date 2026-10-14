#Requires -Version 5.1
<#
.SYNOPSIS
    Kicks off a ScoreConnect III installation that runs hidden in the
    background, driven from the Pulse UI.
.DESCRIPTION
    Adapted from Logan's Install-SC3-1.0.bat (PlayOn internal).

    The Canopy install script is nearly non-interactive: its only console
    read is a 'pause' reminding the tech to copy down the scoreboard code
    before SC1/SC2 are removed. Pulse now shows that reminder (with the
    live bot number) in its own confirm dialog BEFORE calling this script,
    so the elevated child:

      1. Writes initial status to C:\ProgramData\Pulse\sc3-install-status.json
      2. Spawns an ELEVATED PowerShell child (the UAC prompt shows so the
         tech can consent - Pulse itself runs non-elevated, so this one
         window cannot be removed).
      3. The child downloads the Canopy script, strips the console-only
         'pause' / 'cls' lines, and runs the result in a HIDDEN window with
         stdout captured. The Pulse modal polls status and shows the
         installer's own output lines as live progress.

    SAFETY NET: before running hidden, the child scans the sanitized script
    for any remaining interactive reads (a future Canopy revision could add
    a Read-Host). If any are found it falls back to the old VISIBLE window
    so the tech can answer prompts there - never a hidden hang. The hidden
    run also passes -NonInteractive, so a missed prompt errors out instead
    of waiting forever on input nobody can type.

    Status is driven by REAL events (download done, installer running with
    its latest output line, installer exited, SC III reachable on :5000) -
    never a fabricated timer. The child heartbeats the status file every few
    seconds while the installer runs so a legitimately long install is not
    mistaken for a stall.

    ASCII ONLY. Windows PowerShell 5.1 parses a BOM-less .ps1 using the system
    ANSI code page (CP-1252 on US VPUs), which corrupts non-ASCII glyphs (the
    ellipsis, em/en dashes) at parse time - that is the "background?" mojibake.
    Keep every string literal and comment to plain ASCII.
.PARAMETER Mode
    'Install' (default) is the normal flow. 'Reinstall' first stops the
    ScoreConnectIII service and deletes the whole 'Sportzcast LLC' program
    folder (under Program Files (x86), and Program Files on a 64-bit
    layout), then runs the same installer. The installer script is
    downloaded BEFORE anything is deleted, so a failed download leaves the
    existing install untouched. C:\ProgramData\Sportzcast LLC (settings
    and logs) is deliberately NOT touched.
.PARAMETER ScriptUrl
    Override the Canopy install script URL (for testing).
#>
[CmdletBinding()]
param(
    [string]$ScriptUrl = 'https://canopy-public-packages.nfhsnetwork.com/SC3/Current/installScript3_current.ps1',
    [ValidateSet('Install', 'Reinstall')]
    [string]$Mode = 'Install'
)

$ErrorActionPreference = 'Stop'

# Paths
$statusDir  = 'C:\ProgramData\Pulse'
$statusPath = Join-Path $statusDir 'sc3-install-status.json'
$logPath    = Join-Path $statusDir 'sc3-install.log'
$tempDir    = 'C:\scoreconnecttemp'

# Status writer (a mirror of this also runs inside the elevated child).
function Write-Status {
    param(
        [string]$Stage,
        [int]$Percent,
        [string]$Message,
        [string]$ErrorMsg = $null
    )
    if (-not (Test-Path $statusDir)) {
        New-Item -ItemType Directory -Path $statusDir -Force | Out-Null
    }
    [ordered]@{
        stage     = $Stage
        percent   = $Percent
        message   = $Message
        error     = $ErrorMsg
        updatedAt = (Get-Date).ToString('o')
    } | ConvertTo-Json -Compress | Set-Content -Path $statusPath -Encoding UTF8
}

try {
    # Initial status - the bar sits here until the tech consents to UAC.
    $startMsg = 'Approve the Windows administrator prompt to begin installing ScoreConnect III.'
    if ($Mode -eq 'Reinstall') { $startMsg = 'Approve the Windows administrator prompt to begin reinstalling ScoreConnect III.' }
    Write-Status -Stage 'starting' -Percent 5 -Message $startMsg

    if (-not (Test-Path $tempDir)) {
        New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    }
    $elevatedScript = Join-Path $tempDir 'pulse-sc3-elevated.ps1'

    # The elevated child body. It runs (hidden) as Administrator after the UAC
    # prompt, then runs the sanitized Canopy installer hidden with output
    # captured. In the here-string, `$ defers a variable to the child;
    # $statusDir / $statusPath / $logPath / $tempDir / $ScriptUrl interpolate
    # now, from this parent. (Confirmed correct - do not "fix" the escaping.)
    $elevatedBody = @"
`$ErrorActionPreference = 'Stop'
`$statusDir  = '$statusDir'
`$statusPath = '$statusPath'
`$logPath    = '$logPath'
`$tempDir    = '$tempDir'
`$scriptUrl  = '$ScriptUrl'
`$mode       = '$Mode'
`$scriptFile = Join-Path `$tempDir 'installScript3_current.ps1'
`$runFile    = Join-Path `$tempDir 'installScript3_headless.ps1'
`$outLog     = Join-Path `$tempDir 'sc3-installer-out.log'
`$errLog     = Join-Path `$tempDir 'sc3-installer-err.log'

function Write-Status {
    param([string]`$Stage, [int]`$Percent, [string]`$Message, [string]`$ErrorMsg = `$null)
    if (-not (Test-Path `$statusDir)) { New-Item -ItemType Directory -Path `$statusDir -Force | Out-Null }
    [ordered]@{
        stage     = `$Stage
        percent   = `$Percent
        message   = `$Message
        error     = `$ErrorMsg
        updatedAt = (Get-Date).ToString('o')
    } | ConvertTo-Json -Compress | Set-Content -Path `$statusPath -Encoding UTF8
}

function Write-Log {
    param([string]`$Line)
    "`$(Get-Date -Format 'HH:mm:ss')  `$Line" | Add-Content -Path `$logPath -Encoding UTF8
}

try {
    # Reset the log immediately so any later failure is never silent.
    '' | Set-Content -Path `$logPath -Encoding UTF8

    Write-Status -Stage 'downloading' -Percent 20 -Message 'Downloading the ScoreConnect III installer from Canopy.'
    Write-Log "Downloading from `$scriptUrl"

    `$curlPath = (Get-Command curl.exe -ErrorAction SilentlyContinue).Source
    if (`$curlPath) {
        & `$curlPath -sSL --fail -o `$scriptFile `$scriptUrl --connect-timeout 15 --max-time 60 2>`$null
        if (`$LASTEXITCODE -ne 0) { throw "Download failed (curl exit `$LASTEXITCODE). Verify *.nfhsnetwork.com is reachable from this VPU." }
    } else {
        Invoke-WebRequest -Uri `$scriptUrl -OutFile `$scriptFile -UseBasicParsing -TimeoutSec 60
    }
    if (-not (Test-Path `$scriptFile)) { throw 'Installer script did not download.' }
    Write-Log "Downloaded `$((Get-Item `$scriptFile).Length) bytes"

    # Reinstall only: wipe the Sportzcast LLC program folder, then fall through
    # to the normal installer. Done AFTER the download so a failed download
    # never leaves the VPU with no ScoreConnect III at all. Paths are fixed
    # literals, never built from input. ProgramData (settings, logs) is kept.
    if (`$mode -eq 'Reinstall') {
        Write-Status -Stage 'removing' -Percent 40 -Message 'Stopping ScoreConnect III and deleting its program folder.'
        `$svcName = 'ScoreConnectIII'
        `$svc = Get-Service -Name `$svcName -ErrorAction SilentlyContinue
        if (`$svc -and `$svc.Status -ne 'Stopped') {
            Write-Log 'Stopping ScoreConnectIII service'
            try { Stop-Service -Name `$svcName -Force -ErrorAction Stop; `$svc.WaitForStatus('Stopped', [TimeSpan]::FromSeconds(20)) } catch { Write-Log "Stop-Service: `$(`$_.Exception.Message)" }
        }
        # Anything still running out of the folder holds files open.
        Write-Status -Stage 'removing' -Percent 42 -Message 'Stopping ScoreConnect III and deleting its program folder.'
        `$null = Get-Process -Name 'ScoreConnectIII*', 'ScoreConnect', 'ScoreConnectII' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
        # Drop the stale service entry so the installer registers it fresh
        # against the new folder instead of inheriting one pointing at a
        # path that no longer exists.
        if (`$svc) {
            `$null = sc.exe delete `$svcName
            Write-Log "sc.exe delete `$svcName exited `$LASTEXITCODE"
        }
        foreach (`$dir in @('C:\Program Files (x86)\Sportzcast LLC', 'C:\Program Files\Sportzcast LLC')) {
            if (-not (Test-Path -LiteralPath `$dir)) { continue }
            Write-Log "Deleting `$dir"
            for (`$n = 1; `$n -le 5 -and (Test-Path -LiteralPath `$dir); `$n++) {
                try { Remove-Item -LiteralPath `$dir -Recurse -Force -ErrorAction Stop }
                catch { Write-Log "Delete attempt `$n failed: `$(`$_.Exception.Message)"; Write-Status -Stage 'removing' -Percent 45 -Message "A file is still in use - retrying (attempt `$n of 5)."; Start-Sleep -Seconds 3 }
            }
            if (Test-Path -LiteralPath `$dir) { throw "Could not delete `$dir - a file in it is still in use. Close anything using ScoreConnect and click Retry." }
            Write-Log "Deleted `$dir"
        }
    }

    # Sanitize for a hidden run: strip the console-only statements. 'pause'
    # reads CONIN`$ (which no redirected pipe satisfies - that is why the old
    # design needed a visible window) and 'cls' clears a screen nobody sees.
    # Line-anchored so nothing inside a string literal is touched. The \r? is
    # load-bearing: the Canopy file is CRLF and a bare `$ anchor will not match
    # before \r, silently leaving every pause/cls in place.
    `$rawScript = Get-Content -Path `$scriptFile -Raw
    `$sanitized = `$rawScript -replace '(?im)^[ \t]*pause[ \t]*\r?`$', 'Write-Host ''[Pulse] pause skipped (headless install)'''
    `$sanitized = `$sanitized -replace '(?im)^[ \t]*(cls|Clear-Host)[ \t]*\r?`$', ''
    Set-Content -Path `$runFile -Value `$sanitized -Encoding UTF8

    # Safety net: if anything interactive survived sanitizing (a future Canopy
    # revision), run VISIBLE like the old design so the tech can answer it.
    `$headless = -not (`$sanitized -match '(?im)^[ \t]*pause\b|Read-Host|\.ReadKey\(|\`$host\.ui')
    Write-Log "Sanitized installer script; headless=`$headless"

    if (`$headless) {
        Write-Status -Stage 'installing' -Percent 50 -Message 'Installing ScoreConnect III in the background.'
        '' | Set-Content -Path `$outLog -Encoding UTF8
        '' | Set-Content -Path `$errLog -Encoding UTF8
        # -NonInteractive: if a prompt slips past the scan, it errors instead
        # of hanging forever on input nobody can type into a hidden window.
        `$p = Start-Process powershell.exe -ArgumentList '-ExecutionPolicy','Bypass','-NoProfile','-NonInteractive','-File',`$runFile -WorkingDirectory `$tempDir -WindowStyle Hidden -RedirectStandardOutput `$outLog -RedirectStandardError `$errLog -PassThru
    } else {
        Write-Status -Stage 'installing' -Percent 50 -Message 'Follow the prompts in the ScoreConnect III installer window. It will finish automatically.'
        `$p = Start-Process powershell.exe -ArgumentList '-ExecutionPolicy','Bypass','-NoProfile','-File',`$scriptFile -WorkingDirectory `$tempDir -PassThru
    }
    if (-not `$p) { throw 'Could not launch the installer.' }

    # Milestone -> percent map, matched against the installer's own output.
    # Later entries win so percent only moves forward. Fallback stays at 50.
    `$milestones = @(
        @{ Pattern = 'Downloading installer'; Percent = 55 },
        @{ Pattern = 'uninstall SC1';         Percent = 62 },
        @{ Pattern = 'SC2';                   Percent = 68 },
        @{ Pattern = 'install now';           Percent = 78 }
    )

    # Heartbeat the status file while the installer runs. In headless mode,
    # surface the installer's latest output line so the Pulse modal shows
    # real progress, not a frozen bar.
    `$installStart = Get-Date
    `$lastPct = 50
    while (-not `$p.HasExited) {
        if (((Get-Date) - `$installStart).TotalSeconds -gt 900) {
            if (`$headless) {
                Write-Log 'Installer exceeded 15 minutes - stopping the hidden process'
                try { Stop-Process -Id `$p.Id -Force -ErrorAction SilentlyContinue } catch {}
                throw 'The installer did not finish within 15 minutes and was stopped. Click Retry to start over.'
            }
            Write-Log 'Installer exceeded 15 minutes - abandoning wait'
            throw 'The installer did not finish within 15 minutes. Complete it in the installer window, then click Refresh.'
        }
        `$msg = 'Installing ScoreConnect III in the background.'
        if (-not `$headless) {
            `$msg = 'Follow the prompts in the ScoreConnect III installer window. It will finish automatically.'
        } else {
            try {
                `$outLines = @(Get-Content -Path `$outLog -ErrorAction SilentlyContinue | Where-Object { `$_ -and `$_.Trim() })
                if (`$outLines.Count -gt 0) {
                    `$lastLine = `$outLines[`$outLines.Count - 1].Trim()
                    if (`$lastLine.Length -gt 140) { `$lastLine = `$lastLine.Substring(0, 140) }
                    `$msg = "Installer: `$lastLine"
                    `$joined = `$outLines -join "``n"
                    foreach (`$m in `$milestones) {
                        if (`$joined -match `$m.Pattern -and `$m.Percent -gt `$lastPct) { `$lastPct = `$m.Percent }
                    }
                }
            } catch {}
        }
        Write-Status -Stage 'installing' -Percent `$lastPct -Message `$msg
        Start-Sleep -Seconds 3
    }
    Write-Log "Installer exited (exit `$(`$p.ExitCode))"

    # Preserve the installer's own output in the Pulse log for diagnostics.
    if (`$headless) {
        try {
            `$outTail = @(Get-Content -Path `$outLog -Tail 40 -ErrorAction SilentlyContinue | Where-Object { `$_ -and `$_.Trim() })
            foreach (`$line in `$outTail) { Write-Log "installer: `$(`$line.Trim())" }
            `$errTail = @(Get-Content -Path `$errLog -Tail 20 -ErrorAction SilentlyContinue | Where-Object { `$_ -and `$_.Trim() })
            foreach (`$line in `$errTail) { Write-Log "installer-err: `$(`$line.Trim())" }
        } catch {}
    }

    # Verify against the REAL signal: SC III answering on :5000.
    Write-Status -Stage 'verifying' -Percent 85 -Message 'Verifying ScoreConnect III is running.'
    `$ok = `$false
    `$verifyStart = Get-Date
    while (((Get-Date) - `$verifyStart).TotalSeconds -lt 60) {
        try {
            `$r = Invoke-WebRequest -Uri 'http://127.0.0.1:5000/api/configuration/get-status' -UseBasicParsing -TimeoutSec 3
            if (`$r.StatusCode -eq 200) { `$ok = `$true; break }
        } catch {}
        Start-Sleep -Seconds 2
    }

    # Sportzcast's installer configures NO service recovery, so SC3's known
    # process-killing crash (unhandled WebSocket exception in
    # SendToAllInsteadOfId, present in every version) leaves the scoreboard
    # down until a human notices. Configure SCM to auto-restart the service:
    # 5s after the first two crashes, 30s after the third, counter resets
    # daily. Args are unquoted on purpose - PowerShell strips quotes from
    # sc.exe args (the actions= "" empty-string form fails from PS), but
    # these plain tokens pass through clean. Validated on VPU2 2026-09-01:
    # a force-killed process was back serving :5000 in under 12 seconds.
    try {
        `$svc = Get-Service -Name 'ScoreConnectIII' -ErrorAction SilentlyContinue
        if (`$svc) {
            `$null = sc.exe failure ScoreConnectIII reset= 86400 actions= restart/5000/restart/5000/restart/30000
            if (`$LASTEXITCODE -eq 0) {
                Write-Log 'Service recovery configured: auto-restart on crash (5s/5s/30s, counter resets daily)'
            } else {
                Write-Log "sc.exe failure exited `$LASTEXITCODE - service recovery NOT configured"
            }
        } else {
            Write-Log 'ScoreConnectIII service not registered - skipped recovery config'
        }
    } catch { Write-Log "Service recovery config failed: `$(`$_.Exception.Message)" }

    if (`$ok) {
        Write-Status -Stage 'complete' -Percent 100 -Message 'ScoreConnect III is installed and running.'
        Write-Log 'SC III reachable on :5000 - install complete'
    } else {
        Write-Status -Stage 'complete' -Percent 100 -Message 'Installer finished. ScoreConnect III may need a moment or a reboot to start.'
        Write-Log 'Install finished but SC III not responding on :5000 yet'
    }

    try { Remove-Item -Path `$scriptFile -Force -ErrorAction SilentlyContinue } catch {}
    try { Remove-Item -Path `$runFile -Force -ErrorAction SilentlyContinue } catch {}
}
catch {
    `$err = `$_.Exception.Message
    Write-Log "FAILED: `$err"
    Write-Status -Stage 'failed' -Percent 0 -Message 'Installation failed.' -ErrorMsg `$err
}
"@

    Set-Content -Path $elevatedScript -Value $elevatedBody -Encoding UTF8

    # Spawn the elevated child. -Verb RunAs triggers the UAC prompt the tech
    # approves. The child runs hidden and (normally) keeps the installer hidden
    # too. -PassThru lets us confirm it actually launched, so we never write an
    # optimistic "running" status for a child that never ran.
    $child = $null
    try {
        $child = Start-Process -FilePath 'powershell.exe' `
            -ArgumentList "-ExecutionPolicy Bypass -NoProfile -WindowStyle Hidden -File `"$elevatedScript`"" `
            -WindowStyle Hidden `
            -Verb RunAs `
            -PassThru `
            -ErrorAction Stop
    }
    catch {
        Write-Status -Stage 'failed' -Percent 0 -Message 'Administrator permission was declined. Click Retry and approve the Windows prompt.' -ErrorMsg $_.Exception.Message
        @{ ok = $false; error = $_.Exception.Message } | ConvertTo-Json -Depth 5
        return
    }

    if (-not $child) {
        Write-Status -Stage 'failed' -Percent 0 -Message 'Could not launch the elevated installer.' -ErrorMsg 'Start-Process returned no process handle.'
        @{ ok = $false; error = 'Start-Process returned no process handle.' } | ConvertTo-Json -Depth 5
        return
    }

    # The child is live and now owns the status file. Do NOT overwrite it here -
    # the previous design's unconditional 5% write is exactly what froze the bar.
    @{
        ok        = $true
        message   = 'Install started. Poll /api/scoreconnect/install-sc3/status for progress.'
        statusUrl = '/api/scoreconnect/install-sc3/status'
    } | ConvertTo-Json -Depth 5
}
catch {
    Write-Status -Stage 'failed' -Percent 0 -Message 'Failed to launch the installer.' -ErrorMsg $_.Exception.Message
    @{
        ok    = $false
        error = $_.Exception.Message
    } | ConvertTo-Json -Depth 5
}
