#Requires -Version 5.1
<#
.SYNOPSIS
    Waits for a local port to start accepting connections, then launches a URL.
.DESCRIPTION
    Used by run.bat to open Chrome only after uvicorn has bound to localhost:8765.
    A fixed sleep would race on cold VPUs where Python bootstrap is slow.
#>
[CmdletBinding()]
param(
    [int]$Port = 8765,
    [string]$Url = "http://localhost:8765",
    [int]$TimeoutSec = 30,

    # Suppress the animated wait line. Used by the beta launcher's debug mode,
    # where the server runs in the foreground and is already writing to this
    # same console -- two writers on one line just garble each other.
    [switch]$NoProgress
)

# ---- Console progress ------------------------------------------------------
# run.bat prints "[5/5] Starting Pulse ........... launching" and then hands
# off to this script, which can spend up to $TimeoutSec waiting for uvicorn to
# bind and another ~12s per attempt waiting for a Chrome window to appear. That
# was dead air on a static line -- indistinguishable from a hang, which is what
# makes a tester close the window part-way through a first-run bootstrap. So
# animate the wait in place: a frame plus an mm:ss clock, rewritten over itself.
# Silent when stdout is redirected (nothing to animate into) or -NoProgress.
$script:ShowProgress = -not $NoProgress
try { if ([Console]::IsOutputRedirected) { $script:ShowProgress = $false } } catch { $script:ShowProgress = $false }
$script:SpinFrames = '|/-\'
$script:SpinIndex  = 0
$script:SpinStart  = Get-Date

function Write-WaitLine([string]$text) {
    if (-not $script:ShowProgress) { return }
    $frame = $script:SpinFrames[$script:SpinIndex]
    $script:SpinIndex = ($script:SpinIndex + 1) % 4
    $clock = ((Get-Date) - $script:SpinStart).ToString('mm\:ss')
    Write-Host -NoNewline ([string][char]13 + '       - ' + $text + ' ' + $frame + ' ' + $clock + '   ')
}

function Write-WaitDone([string]$text) {
    if (-not $script:ShowProgress) { return }
    Write-Host ([string][char]13 + '       - ' + $text + '                          ')
}

# Append-only breadcrumb log, separate from pulse-server.log (which the hidden
# server holds open for writing). The browser launch used to be completely
# silent, so a tester reporting "said it's running but no window appeared" left
# us guessing. This records which Chrome we found and whether the launch took,
# so the next report is diagnosable instead of inferred. Never throws.
$LaunchLog = Join-Path $PSScriptRoot '..\pulse-launch.log'
function Write-LaunchLog($msg) {
    try {
        $stamp = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
        Add-Content -Path $LaunchLog -Value "$stamp  $msg" -ErrorAction SilentlyContinue
    } catch { }
}

# Resolve chrome.exe explicitly. Start-Process on a bare URL hands it to the
# DEFAULT browser handler -- and a fresh VPU often has no default browser set,
# so Windows pops a "How do you want to open this?" picker (with IE as the
# first option) instead of opening Pulse. The launcher guarantees Chrome is
# installed, so open it directly; fall back to the default handler only if
# Chrome is genuinely missing.
function Get-ChromePath {
    # Plain string interpolation (not Join-Path): a missing env var must yield
    # a harmless non-existent path, not a binding error.
    $candidates = @(
        (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe' -ErrorAction SilentlyContinue).'(default)'
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe"
        "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe"
        "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
    )
    foreach ($p in $candidates) {
        if ($p -and (Test-Path $p)) { return $p }
    }
    return $null
}

# True once any chrome.exe owns a visible top-level window. Running processes
# alone are NOT proof a window appeared: Chrome's first launch after an update
# or reboot can start its process tree, exit cleanly moments later, and never
# surface a window (observed on VPU2 2026-07-23 - no crash dump, no event-log
# trace). Only the browser process has a MainWindowHandle; child processes
# (GPU, renderers) report 0.
function Test-ChromeWindow {
    foreach ($p in @(Get-Process -Name chrome -ErrorAction SilentlyContinue)) {
        if ($p.MainWindowHandle -ne 0) { return $true }
    }
    return $false
}

# Open Pulse in Chrome. The first launch on a freshly transferred VPU hits a
# COLD Chrome profile: Chrome's first-run path (profile creation + the
# "welcome / set as default" interstitial) swallows the URL and never surfaces
# a window, so the launcher prints "running" and closes with nothing on screen
# -- and the tester has to run it a second time, when the profile is warm. The
# flags below skip that first-run friction and force the URL into a new window;
# --no-first-run + --no-default-browser-check are exactly what a cold profile
# needs to open straight to the page.
#
# Even with those flags, Chrome can still start and silently exit windowless
# (first launch after a background Chrome update). A second launch reliably
# works, so instead of making the tester do it, poll for a VISIBLE window and
# relaunch ourselves until one appears (up to 3 attempts).
function Open-Browser {
    if ($env:PULSE_NO_BROWSER) {
        # A self-update restart sets this: the page that triggered the update is
        # still open and reconnects on its own, so a second tab would be noise.
        Write-LaunchLog "PULSE_NO_BROWSER set - skipping browser launch"
        return
    }

    $chrome = Get-ChromePath
    if (-not $chrome) {
        # No Chrome found -- fall back to the default handler. Can't pass the
        # cold-profile flags here, but this is the rare "Chrome genuinely
        # missing" path; the launcher normally guarantees it's installed.
        Write-LaunchLog "Chrome not found - opening $Url via default handler"
        try { Start-Process $Url } catch { Write-LaunchLog "default-handler launch threw: $_" }
        return
    }

    $chromeArgs = @('--no-first-run', '--no-default-browser-check', '--new-window', $Url)
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        Write-LaunchLog "Launching Chrome (attempt $attempt): $chrome $($chromeArgs -join ' ')"
        try { Start-Process -FilePath $chrome -ArgumentList $chromeArgs } catch { Write-LaunchLog "Chrome launch threw: $_" }

        # If Chrome was already open, Test-ChromeWindow passes on the first
        # poll and we're done: --new-window into a warm instance is reliable.
        $waited = 0
        while ($waited -lt 12) {
            Write-WaitLine 'waiting for the Chrome window'
            Start-Sleep -Seconds 1
            $waited += 1
            if (Test-ChromeWindow) {
                Write-LaunchLog "Chrome window visible after ~${waited}s (attempt $attempt)"
                Write-WaitDone 'Chrome window open'
                return
            }
        }
        Write-LaunchLog "No visible Chrome window after ${waited}s (attempt $attempt)"
    }
    Write-LaunchLog "Giving up: no Chrome window after 3 attempts - open $Url manually"
    Write-WaitDone "no Chrome window appeared - open $Url manually"
}

$elapsed = 0
while ($elapsed -lt $TimeoutSec) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $iar = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne(500)
        if ($ok -and $client.Connected) {
            $client.Close()
            Write-LaunchLog "Port $Port up after ~$elapsed s - opening browser"
            Write-WaitDone 'server up - opening Chrome'
            Open-Browser
            exit 0   # server is up
        }
        $client.Close()
    } catch {
        # Port not open yet -- sleep and retry
    }
    Write-WaitLine 'waiting for the server to start'
    Start-Sleep -Milliseconds 500
    $elapsed += 1
}

# Timed out -- the server never came up. Do NOT open the browser (it would
# just show a connection error); exit non-zero so run.bat surfaces the
# failure and points the user at pulse-server.log.
Write-LaunchLog "Timed out after ${TimeoutSec}s waiting for port $Port"
Write-WaitDone 'the server did not come up'
exit 1
