@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title Pulse  -  starting up

:: ================================================================
::  Pulse runtime launcher
::  Bootstraps embedded Python (first run), then starts the server in
::  a hidden, detached process and opens the browser. This window
::  shows setup progress, then closes itself once Pulse is running -
::  the server has no console window for anyone to click into.
:: ================================================================

set "PYVER=3.12.8"
set "PYDIR=%~dp0app\python"
set "PYEXE=%PYDIR%\python.exe"
set "PYZIP=python-%PYVER%-embed-amd64.zip"
set "PYURL=https://www.python.org/ftp/python/%PYVER%/%PYZIP%"
set "PIPURL=https://bootstrap.pypa.io/get-pip.py"
set "PORT=8765"
set "URL=http://localhost:%PORT%"

where curl.exe >nul 2>&1 && (set "HAS_CURL=1") || (set "HAS_CURL=")

:: -- What the tech sees ---------------------------------------------------
:: Continues the launcher's list under "Starting Pulse": one line per step,
:: status in the same column (labels padded to match run_pulse.bat), quiet
:: housekeeping, and every failure ends in the :fatal banner with the cause
:: (FAIL_WHY) and the next step (FAIL_DO). Wait-AndLaunch.ps1 prints the
:: Server and Browser lines in the same layout.
set "L_PY=    Python runtime ...... "
set "L_DEPS=    Dependencies ........ "
set "L_PREV=    Previous Pulse ...... "
set "FAIL_WHY=Something went wrong while starting Pulse."
set "FAIL_DO="
set "PY_DONE=installed"

echo   Starting Pulse

:: -- Python runtime ---------------------------------------------
:: python.exe alone doesn't prove a usable runtime: a first run interrupted
:: after extraction leaves the exe without pip, updates never replace
:: app\python, and every later launch died at step 2 "No module named pip".
:: Repair it in place instead of skipping.
if exist "%PYEXE%" (
    "%PYEXE%" -m pip --version >nul 2>&1
    if not errorlevel 1 (
        echo !L_PY!ready
        goto :deps
    )
    echo !L_PY!repairing - pip is missing
    set "PY_DONE=repaired"
    goto :pyrepair
)

echo !L_PY!first run - setting up Python %PYVER%, about 2 minutes
if not exist "%PYDIR%" mkdir "%PYDIR%"

if defined HAS_CURL (
    curl.exe -L --progress-bar -o "%PYDIR%\%PYZIP%" "%PYURL%"
) else (
    call :dl_spin "%L_PY%downloading Python %PYVER%" "%PYURL%" "%PYDIR%\%PYZIP%" "-" "-"
)
set "FAIL_WHY=Python could not be downloaded."
set "FAIL_DO=Check this VPU's internet connection, then run Pulse again."
if not exist "%PYDIR%\%PYZIP%" (
    echo !L_PY!download failed
    call :tlscheck "www.python.org"
    goto :fatal
)
for %%A in ("%PYDIR%\%PYZIP%") do if %%~zA LSS 5000 (
    echo !L_PY!download did not finish
    del "%PYDIR%\%PYZIP%"
    call :tlscheck "www.python.org"
    goto :fatal
)

set "SPIN_LABEL=%L_PY%unpacking Python"
set "SPIN_DONE=-"
set "SPIN_PSCMD=Add-Type -Assembly System.IO.Compression.FileSystem;[System.IO.Compression.ZipFile]::ExtractToDirectory('%PYDIR%\%PYZIP%','%PYDIR%')"
call :spin
if not exist "%PYEXE%" (
    echo !L_PY!could not unpack Python
    set "FAIL_WHY=Python could not be unpacked."
    set "FAIL_DO=Run Pulse again."
    goto :fatal
)
del "%PYDIR%\%PYZIP%"

:pyrepair
set "FAIL_WHY=The Python runtime on this VPU is damaged."
set "FAIL_DO=Delete the folder !PYDIR! and run Pulse again."
"%PYEXE%" --version >nul 2>&1
if errorlevel 1 (
    echo !L_PY!damaged - Python will not run
    goto :fatal
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$f = Get-ChildItem '%PYDIR%' -Filter '*._pth' | Select-Object -First 1; if (-not $f) { exit 1 }; (Get-Content $f.FullName) -replace '#import site','import site' | Set-Content $f.FullName"
if errorlevel 1 (
    echo !L_PY!damaged - its settings file is missing
    goto :fatal
)

if defined HAS_CURL (
    curl.exe -L --silent -o "%PYDIR%\get-pip.py" "%PIPURL%"
) else (
    call :dl_spin "%L_PY%downloading pip" "%PIPURL%" "%PYDIR%\get-pip.py" "-" "-"
)
if not exist "%PYDIR%\get-pip.py" (
    echo !L_PY!could not download pip
    set "FAIL_WHY=pip, Python's installer, could not be downloaded."
    set "FAIL_DO=Check this VPU's internet connection, then run Pulse again."
    call :tlscheck "bootstrap.pypa.io"
    goto :fatal
)
set "SPIN_LABEL=%L_PY%installing pip"
set "SPIN_DONE=-"
set "SPIN_PSCMD=$log=$env:TEMP+'\pulse-bootstrap.log';& '%PYEXE%' '%PYDIR%\get-pip.py' --no-warn-script-location --quiet *> $log;if($LASTEXITCODE -ne 0){throw 'get-pip exited '+$LASTEXITCODE+' - see '+$log}"
call :spin
if errorlevel 1 (
    set "FAIL_WHY=pip, Python's installer, could not be set up."
    set "FAIL_DO=Run Pulse again. If it fails again, send %TEMP%\pulse-bootstrap.log to the Pulse team."
    goto :fatal
)
del "%PYDIR%\get-pip.py"
echo !L_PY!!PY_DONE!

:deps
:: -- Make app/ importable --------------------------------------
powershell -NoProfile -ExecutionPolicy Bypass -Command "$f = Get-ChildItem '%PYDIR%' -Filter '*._pth' | Select-Object -First 1; if ($f) { $c = Get-Content $f.FullName; if ($c -notcontains '..') { Add-Content $f.FullName '..' } }"

:: -- Dependencies ---------------------------------------------
:: Best-effort pip self-update first, so installed runtimes pick up pip
:: security patches after bootstrap. Failures there are ignored and the
:: timeout is short -- an offline VPU must still launch on its current pip.
:: Both runs share one spinner: on a cold VPU this is the longest step in the
:: launcher (every wheel downloaded and built), and it used to sit on a single
:: static "checking" line for minutes with nothing to show it was alive.
:: pip output goes to the log so it can't fight the spinner for the line; the
:: verbose retry below is what a tech reads when it actually fails.
set "SPIN_LABEL=%L_DEPS%checking"
set "SPIN_DONE=%L_DEPS%ready"
set "SPIN_PSCMD=$log=$env:TEMP+'\pulse-pip.log';& '%PYEXE%' -m pip install --upgrade pip --quiet --no-warn-script-location --timeout 5 --retries 1 *> $log;& '%PYEXE%' -m pip install -r app\requirements.txt --quiet --no-warn-script-location *>> $log;if($LASTEXITCODE -ne 0){throw 'pip exited '+$LASTEXITCODE+' - see '+$log}"
call :spin
if not errorlevel 1 goto :deps_ok
echo !L_DEPS!retrying, with pip's own output shown below
"%PYEXE%" -m pip install -r app\requirements.txt --no-warn-script-location
if errorlevel 1 (
    echo !L_DEPS!FAILED
    set "FAIL_WHY=Pulse's Python packages could not be installed."
    set "FAIL_DO=Check this VPU's internet connection, then run Pulse again."
    call :tlscheck "pypi.org,files.pythonhosted.org"
    goto :fatal
)
echo !L_DEPS!ready
:deps_ok

:: -- Sanity check (silent when fine) ---------------------------
if not exist "app\main.py" (
    set "FAIL_WHY=Pulse's files are incomplete: app\main.py is missing from %CD%."
    set "FAIL_DO=Run the Pulse launcher again to reinstall them."
    goto :fatal
)

:: -- Free the port (silent unless a previous Pulse was running) -
set "KILLED="
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":%PORT% " ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
    set "KILLED=1"
)
if defined KILLED echo !L_PREV!closed - it was still running

:: -- Start the hidden server + open the browser ----------------
:: Wait-AndLaunch.ps1 prints the Server and Browser steps.
if not exist "%~dp0pulse-launch.vbs" (
    set "FAIL_WHY=Pulse's files are incomplete: pulse-launch.vbs is missing."
    set "FAIL_DO=Run the Pulse launcher again to reinstall them."
    goto :fatal
)
wscript "%~dp0pulse-launch.vbs"

:: Wait until the server is actually accepting connections, then open
:: the browser. Returns 0 once the port is up, 1 on timeout.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Wait-AndLaunch.ps1" -Port %PORT% -Url "%URL%" -TimeoutSec 40
if errorlevel 1 (
    set "FAIL_WHY=The Pulse server did not start within 40 seconds."
    set "FAIL_DO=Run Pulse again. If it fails again, send %~dp0pulse-server.log to the Pulse team."
    goto :fatal
)

echo.
echo   Pulse is running at %URL%
echo   This window will close in a few seconds.
:: Brief pause so the success message is readable, then exit cleanly.
:: The server keeps running hidden; the caller closes this window.
ping -n 3 127.0.0.1 >nul

:: Launch-complete marker. The app watches this to learn the launcher has
:: finished, so it can replace the frozen Pulse.bat self-copy without
:: rewriting a .bat that cmd is still reading (see _refresh_installed_launcher
:: in app/main.py -- that mistake garbles the launch). Written last: all that
:: is left after this is the caller's own exit.
>"%~dp0pulse-launch-done" echo %DATE% %TIME%
endlocal
exit /b 0

:: -- SSL-interception diagnosis on download failure -----------
:: A failed bootstrap download on a school network is often not connectivity
:: but a firewall doing SSL inspection substituting certificates (the
:: SEC_E_UNTRUSTED_ROOT the Kent School District install died on). Probe the
:: host that just failed; if its cert doesn't chain to a trusted root, the
:: helper prints a plain-English explanation + fix for the venue's IT team.
:: Silent no-op when the network is fine or the helper is missing.
:tlscheck
if exist "%~dp0scripts\Test-InstallTls.ps1" powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Test-InstallTls.ps1" -TargetHosts "%~1"
exit /b 0

:: -- Error handler --------------------------------------------
:fatal
echo.
echo   ------------------------------------------------------------
echo   PULSE DID NOT START
echo   !FAIL_WHY!
if defined FAIL_DO echo   !FAIL_DO!
echo   Press any key to close this window.
echo   ------------------------------------------------------------
pause >nul
endlocal
exit /b 1

:: -- Live progress for long steps -----------------------------------------
:: Long steps (Chrome install, pip, extract, copy) used to print one static
:: line and then sit silent for minutes. A tech can't tell a slow install
:: from a hung one, and the usual reaction is to kill the window mid-install.
:: :spin runs the work in a background PowerShell runspace and animates the
:: SAME line (frame + mm:ss clock) until it finishes, so the window always
:: shows the step is still moving.
::
::   set "SPIN_LABEL=%L_THING%doing"   (exact text)
::   set "SPIN_DONE=%L_THING%done"     ('-' erases it)
::   set "SPIN_FAIL=-"                 (optional - a failure erases it too)
::   set "SPIN_PSCMD=<PowerShell; throw to fail>"
::   set "SPIN_OUT=<file>"  (optional - captures the script's output)
::   call :spin
::   if errorlevel 1 ( ... )
::
:: SPIN_PSCMD runs in %CD% and may use single quotes only -- cmd eats embedded
:: double quotes, and '!' is eaten by delayed expansion. Send native-command
:: output to a log (*> $log) or it fights the spinner for the line. Animation
:: is skipped (one line in, one line out) when stdout is redirected.
:spin
set "SPIN_CWD=%CD%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$CR=[string][char]13;$lbl=$env:SPIN_LABEL;$ps=[powershell]::Create();$null=$ps.AddScript('Set-Location -LiteralPath $env:SPIN_CWD; '+$env:SPIN_PSCMD);$h=$ps.BeginInvoke();$fr='|/-\';$i=0;$t0=Get-Date;$tty=$true;try{if([Console]::IsOutputRedirected){$tty=$false}}catch{$tty=$false};if(-not $tty){Write-Host $lbl};while(-not $h.IsCompleted){if($tty){Write-Host -NoNewline ($CR+$lbl+' '+$fr[$i]+' '+((Get-Date)-$t0).ToString('mm\:ss')+'  ');$i=($i+1) -band 3};Start-Sleep -Milliseconds 200};$rc=0;$msg='';$out=$null;try{$out=$ps.EndInvoke($h)}catch{$rc=1;$e=$_.Exception;if($e.InnerException){$e=$e.InnerException};$msg=$e.Message};if($ps.Streams.Error.Count -gt 0){$rc=1;if(-not $msg){$msg=[string]$ps.Streams.Error[0]}};$ps.Dispose();$ts=(Get-Date)-$t0;$fin=$env:SPIN_DONE;if(-not $fin){$fin=$lbl};$quiet=($rc -ne 0 -and $env:SPIN_FAIL -eq '-');if($rc -ne 0){if($quiet){$fin='-'}else{$fin=$lbl+'  FAILED'}};if($fin -eq '-'){if($tty){Write-Host -NoNewline ($CR+(' '*($lbl.Length+16))+$CR)}}else{if($ts.TotalSeconds -ge 5){$fin=$fin+'  ('+$ts.ToString('mm\:ss')+')'};if($tty){Write-Host ($CR+$fin+'                ')}else{Write-Host $fin}};if($env:SPIN_OUT){$out|Out-File -FilePath $env:SPIN_OUT -Encoding ascii};if($rc -ne 0 -and $msg -and -not $quiet){Write-Host ('      '+$msg)};exit $rc"
set "SPIN_RC=%errorlevel%"
set "SPIN_PSCMD="
set "SPIN_DONE="
set "SPIN_OUT="
set "SPIN_FAIL="
exit /b %SPIN_RC%

:: -- Download one URL with the spinner ------------------------------------
:: Used only on the PowerShell fallback path; curl prints its own progress
:: bar and doesn't need this.
::   %1 = label   %2 = url   %3 = output file   %4 = done label
::   %5 = '-' to erase the line on failure (the caller reports the outcome)
:dl_spin
set "SPIN_LABEL=%~1"
set "SPIN_DONE=%~4"
set "SPIN_FAIL=%~5"
set "SPIN_PSCMD=$ProgressPreference='SilentlyContinue';[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;Invoke-WebRequest -UseBasicParsing -Uri '%~2' -OutFile '%~3'"
call :spin
exit /b %errorlevel%
