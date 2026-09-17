@echo off
setlocal EnableDelayedExpansion
title Pulse  -  updating (dev)

:: -- Run as Administrator -------------------------------------------------
::   Pulse's checks read HKLM, query WMI/CIM, and inspect Windows services
::   and the Pixellot install -- all most reliable with admin rights.
::   Self-elevate via UAC so the launcher, the hidden server, and every
::   PowerShell probe it spawns run at full capability. The /elevated
::   sentinel breaks any relaunch loop; if UAC is declined we continue with
::   limited diagnostics rather than failing outright.
if /I "%~1"=="/elevated" ( shift & goto :gotadmin )
net session >nul 2>&1
if %errorlevel% EQU 0 goto :gotadmin
echo   Requesting administrator access ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Start-Process -FilePath '%~f0' -ArgumentList '/elevated %*' -Verb RunAs -ErrorAction Stop } catch { exit 1 }"
if not errorlevel 1 exit /b
echo   Administrator access declined - continuing with limited diagnostics.
:gotadmin

:: ════════════════════════════════════════════════════════════════
::  Pulse updater / launcher  (DEV channel)
::
::  - Installs to C:\Pulse
::  - Pulls the LATEST COMMIT on the dev branch directly (commit zip), so
::    dev always tracks tip-of-branch — no dependency on a tagged release.
::    Pass a branch name as the first arg to test any other branch instead.
::  - If offline or the download fails, launches the already-installed copy
::  - Hands off to run.bat, which starts the server hidden and closes
::    this window
:: ════════════════════════════════════════════════════════════════

:: -- Config ---------------------------------------------------------------
set "BRANCH=dev"
if not "%~1"=="" set "BRANCH=%~1"

set "INSTALL_DIR=C:\Pulse"
set "REPO=playon/pulse"
set "ZIPFILE=%TEMP%\pulse-dl.zip"
set "EXTRACT=%TEMP%\pulse-extract"
:: Repo copy of THIS launcher (on whichever branch we're tracking) -- used to
:: repair %INSTALL_DIR%\Pulse.bat if the runtime self-copy ever fails (see :shortcut).
set "LAUNCHER_URL=https://raw.githubusercontent.com/playon/pulse/%BRANCH%/runners/run_pulse_dev.bat"

echo.
echo  .-----------------------------------------------------.
echo  ^|                                                     ^|
echo  ^| __________ ____ ___.____       ____________________ ^|
echo  ^| \______   \    ^|   \    ^|     /   _____/\_   _____/ ^|
echo  ^|  ^|     ___/    ^|   /    ^|     \_____  \  ^|    __)_  ^|
echo  ^|  ^|    ^|   ^|    ^|  /^|    ^|___  /        \ ^|        \ ^|
echo  ^|  ^|____^|   ^|______/ ^|_______ \/_______  //_______  / ^|
echo  ^|                        [ DEV ]                      ^|
echo  '-----------------------------------------------------'
echo                    VPU Diagnostics
echo.
if /I "%BRANCH%"=="dev" ( echo   Channel : dev ) else ( echo   Channel : dev ^(%BRANCH%^) )
echo   Install : %INSTALL_DIR%
echo.

:: -- Chrome (install if missing) ------------------------------------------
:: The download and the silent install are the two longest unattended steps
:: in the launcher (minutes on a slow venue link) and both used to sit on one
:: static "installing" line, so a tech had no way to tell them from a hang.
:: Both now animate -- see :spin at the end of this file.
reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe" >nul 2>&1
if %errorlevel% EQU 0 (
    echo   Chrome ......................... ok
    goto :chrome_done
)
call :dl_spin "  Chrome ......................... downloading" "https://dl.google.com/chrome/install/latest/chrome_installer.exe" "%TEMP%\chrome_installer.exe" "-"
if errorlevel 1 (
    echo   Chrome ......................... download failed - continuing
    goto :chrome_done
)
set "SPIN_LABEL=  Chrome ......................... installing"
set "SPIN_DONE=  Chrome ......................... installed"
set "SPIN_PSCMD=$null=Start-Process -FilePath ($env:TEMP+'\chrome_installer.exe') -ArgumentList '/silent','/install' -Wait"
call :spin
del "%TEMP%\chrome_installer.exe" 2>nul
:chrome_done

:: -- Offline fast-path ----------------------------------------------------
:: If Pulse is already installed and we can't reach GitHub, skip the update
:: entirely and launch the installed copy. A tech on a downed venue network
:: should get Pulse immediately, not after a download timeout.
if exist "%INSTALL_DIR%\run.bat" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $c = New-Object Net.Sockets.TcpClient; $iar = $c.BeginConnect('github.com',443,$null,$null); if ($iar.AsyncWaitHandle.WaitOne(3000) -and $c.Connected) { $c.Close(); exit 0 } else { exit 1 } } catch { exit 1 }"
    if errorlevel 1 (
        echo   Network ........................ offline - using installed build
        goto :shortcut
    )
)
echo   Network ........................ online

:: -- Resolve latest commit SHA (cache-bust download) ----------------------
set "COMMIT_SHA="
set "RESOLVE_OUT=%TEMP%\pulse-resolve.txt"
set "SPIN_LABEL=  Update ......................... checking %BRANCH% for a newer build"
set "SPIN_DONE=-"
set "SPIN_OUT=%RESOLVE_OUT%"
set "SPIN_PSCMD=try{[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;(Invoke-RestMethod -Uri 'https://api.github.com/repos/%REPO%/commits/%BRANCH%' -TimeoutSec 10).sha}catch{''}"
call :spin
if exist "%RESOLVE_OUT%" set /p COMMIT_SHA=<"%RESOLVE_OUT%"
del "%RESOLVE_OUT%" 2>nul

:: Lookup failure isn't fatal (the branch-zip URL below still works without a
:: SHA) but say so -- api.github.com being blocked is a real field failure.
if not defined COMMIT_SHA echo   Update ......................... commit lookup failed ^(api.github.com unreachable?^) - trying branch zip

:: Already up to date? Skip the download entirely. Don't re-stream a build
:: that's already installed — just go straight to launch.
if defined COMMIT_SHA if exist "%INSTALL_DIR%\VERSION" (
    set "SHORT_SHA=!COMMIT_SHA:~0,7!"
    set "INSTALLED_VER="
    set /p INSTALLED_VER=<"%INSTALL_DIR%\VERSION"
    if "!INSTALLED_VER!"=="%BRANCH%-!SHORT_SHA!" (
        echo   Update ......................... already up to date ^(!INSTALLED_VER!^)
        goto :shortcut
    )
)

if defined COMMIT_SHA (
    set "ASSET_URL=https://github.com/%REPO%/archive/!COMMIT_SHA!.zip"
) else (
    set "ASSET_URL=https://github.com/%REPO%/archive/refs/heads/%BRANCH%.zip"
)

:: -- Download -------------------------------------------------------------
:: curl is primary (clean progress bar), but the Windows-bundled curl+schannel
:: can fail the GitHub archive CDN redirect with SEC_E_WRONG_PRINCIPAL.
:: If curl yields no usable zip (failed or absent), fall back to PowerShell,
:: whose .NET stack uses the Windows cert store and follows the redirect cleanly.
echo   Update ......................... downloading %BRANCH%
if exist "%ZIPFILE%" del "%ZIPFILE%" 2>nul
where curl.exe >nul 2>&1 && curl.exe -L --progress-bar -o "%ZIPFILE%" "!ASSET_URL!"

set "DL_OK="
if exist "%ZIPFILE%" for %%A in ("%ZIPFILE%") do if %%~zA GEQ 1000 set "DL_OK=1"
if not defined DL_OK (
    if exist "%ZIPFILE%" del "%ZIPFILE%" 2>nul
    call :dl_spin "  Update ......................... retrying via PowerShell" "!ASSET_URL!" "%ZIPFILE%" "  Update ......................... downloaded"
)

if not exist "%ZIPFILE%" goto :dl_failed
for %%A in ("%ZIPFILE%") do if %%~zA LSS 1000 goto :dl_failed
goto :dl_ok

:dl_failed
if exist "%ZIPFILE%" del "%ZIPFILE%"
if exist "%INSTALL_DIR%\run.bat" (
    echo   Update ......................... failed - using installed build
    goto :shortcut
)
echo.
echo   [ERROR] Download failed and no installed build to fall back on.
call :netdiag
goto :fatal

:dl_ok
if exist "%EXTRACT%" rd /s /q "%EXTRACT%"
:: Import-Module explicitly: Expand-Archive lives in a module, and the spinner
:: runs it in a fresh runspace rather than relying on command auto-discovery.
set "SPIN_LABEL=  Update ......................... extracting"
set "SPIN_DONE=  Update ......................... extracted"
set "SPIN_PSCMD=Import-Module Microsoft.PowerShell.Archive -ErrorAction SilentlyContinue;Expand-Archive -Path '%ZIPFILE%' -DestinationPath '%EXTRACT%' -Force"
call :spin
del "%ZIPFILE%"

:: Find the Pulse.Web folder inside the extracted archive.
set "SRC="
if exist "%EXTRACT%\run.bat" set "SRC=%EXTRACT%"
if not defined SRC for /d %%d in ("%EXTRACT%\*") do if exist "%%d\run.bat" set "SRC=%%d"
if not defined SRC for /d %%d in ("%EXTRACT%\*") do if exist "%%d\Pulse.Web\run.bat" set "SRC=%%d\Pulse.Web"

if not defined SRC (
    echo   [ERROR] Downloaded archive did not contain Pulse.Web.
    if exist "%EXTRACT%" rd /s /q "%EXTRACT%"
    goto :fatal
)

if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%" 2>nul
if not exist "%INSTALL_DIR%" (
    echo   [ERROR] Could not create %INSTALL_DIR%.
    echo           Run this launcher as Administrator.
    if exist "%EXTRACT%" rd /s /q "%EXTRACT%"
    goto :fatal
)
:: /s /e copies subdirs incl. the app\python\ runtime and settings,
:: which are preserved across updates (xcopy only overwrites shipped files).
:: Copying the unpacked build (including the ~50 MB embedded Python runtime)
:: over a cold disk takes long enough to look stalled, so it animates too.
:: SRC goes through the environment: it can contain spaces, and quoting it
:: through the spinner's single-quoted command string cannot.
set "SPIN_SRC=%SRC%"
set "SPIN_LABEL=  Update ......................... installing to %INSTALL_DIR%"
set "SPIN_DONE=  Update ......................... installed to %INSTALL_DIR%"
set "SPIN_PSCMD=$log=$env:TEMP+'\pulse-copy.log';& ($env:SystemRoot+'\System32\xcopy.exe') ($env:SPIN_SRC+'\*') '%INSTALL_DIR%\' /s /e /y /q *> $log;if($LASTEXITCODE -ge 4){throw 'file copy failed with code '+$LASTEXITCODE+' - see '+$log}"
call :spin
if exist "%EXTRACT%" rd /s /q "%EXTRACT%"

:: Stamp the installed version.
set "SHORT_SHA=unknown"
if defined COMMIT_SHA set "SHORT_SHA=!COMMIT_SHA:~0,7!"
echo %BRANCH%-!SHORT_SHA!> "%INSTALL_DIR%\VERSION"
echo   Version ........................ %BRANCH%-!SHORT_SHA!

:shortcut
:: -- Self-copy + Start Menu shortcut --------------------------------------
:: Stealth footprint: no desktop icon. Findable via Start Menu — press Win,
:: type "pulse", hit Enter. Also auto-removes any existing Desktop\Pulse.lnk
:: from older launcher builds so existing installs migrate on next launch.
:: Copy this launcher into the install dir so the shortcut has a stable
:: target. Guard against copying onto itself (when launched FROM the
:: shortcut, %~f0 already IS the install copy).
::
:: If that copy is ever missing, the shortcut points at nothing and the Start
:: Menu entry dies ("Missing Shortcut - Windows is searching for Pulse.bat").
:: So: self-copy; if it didn't land, fetch the launcher from the repo; and only
:: (re)create the shortcut AFTER confirming the target exists -- never orphan it.
if /I not "%~f0"=="%INSTALL_DIR%\Pulse.bat" copy /y "%~f0" "%INSTALL_DIR%\Pulse.bat" >nul
if not exist "%INSTALL_DIR%\Pulse.bat" (
    echo   Launcher self-copy ............. failed - fetching from repo
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue';[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; try{ Invoke-WebRequest -UseBasicParsing -Uri '%LAUNCHER_URL%' -OutFile '%INSTALL_DIR%\Pulse.bat' }catch{}" 2>nul
)
:: Record the channel so the in-app "Check for update" knows which release line to track
>"%INSTALL_DIR%\CHANNEL" echo dev

set "ICON=%INSTALL_DIR%\app\static\img\pulse.ico"
if not exist "%ICON%" set "ICON=%INSTALL_DIR%\Pulse.bat"
:: Only (re)create the shortcut once its target is confirmed present -- never
:: orphan it. (goto, not an if/else block: keeps the powershell line below in
:: top-level parse context so its quoted parens and ^ continuation are safe.)
if not exist "%INSTALL_DIR%\Pulse.bat" goto :no_shortcut
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$old=[Environment]::GetFolderPath('DesktopDirectory')+'\Pulse.lnk'; if (Test-Path $old) { Remove-Item $old -Force -ErrorAction SilentlyContinue }; $d=[Environment]::GetFolderPath('Programs'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut(\"$d\Pulse.lnk\"); $s.TargetPath='%INSTALL_DIR%\Pulse.bat'; $s.WorkingDirectory='%INSTALL_DIR%'; $s.IconLocation='%ICON%'; $s.Description='Pulse - VPU Diagnostics'; $s.Save()" 2>nul
echo   Start Menu shortcut ............ ready
goto :after_shortcut
:no_shortcut
echo   Start Menu shortcut ............ SKIPPED - launcher copy unavailable
:after_shortcut

:: -- Hand off to the runtime launcher -------------------------------------
echo.
if not exist "%INSTALL_DIR%\run.bat" (
    echo   [ERROR] %INSTALL_DIR%\run.bat not found — install incomplete.
    goto :fatal
)
cd /d "%INSTALL_DIR%"
call run.bat
:: run.bat starts the hidden server and closes this window on success,
:: or pauses on its own error. Nothing left to do here.
endlocal
exit /b 0

:: -- Update-phase error handler -------------------------------------------
:fatal
echo.
echo  ============================================
echo    PULSE UPDATE FAILED — see messages above.
echo    Press any key to close.
echo  ============================================
pause >nul
endlocal
exit /b 1

:: -- Network diagnostics ---------------------------------------------------
:: Runs when no build could be downloaded AND none is installed, so the tech
:: (or the venue's IT) can see exactly which GitHub hostname this network
:: blocks. School/venue web filters commonly allow github.com but block
:: *.githubusercontent.com -- that shows up here as an OK first line with
:: FAIL lines underneath. Results also land in %TEMP%\pulse-launcher-diag.txt
:: so support can ask for the file.
:netdiag
set "DIAG_LOG=%TEMP%\pulse-launcher-diag.txt"
> "%DIAG_LOG%" echo Pulse launcher network diagnostics - %DATE% %TIME% - channel dev - branch %BRANCH%
echo.
echo   -- Network check: every host Pulse downloads from ----------------
call :probe github.com
call :probe api.github.com
call :probe codeload.github.com
call :probe objects.githubusercontent.com
call :probe release-assets.githubusercontent.com
call :probe raw.githubusercontent.com
echo   -------------------------------------------------------------------
findstr /l /c:"[FAIL]" "%DIAG_LOG%" >nul 2>&1
if errorlevel 1 goto :diag_allok
findstr /l /c:"[ OK ] github.com " "%DIAG_LOG%" >nul 2>&1
if errorlevel 1 goto :diag_list
echo   github.com works but other GitHub hosts are blocked. This is
echo   typical of a school/venue web filter, and it is why the download
echo   fails even though github.com opens fine in a browser.
:diag_list
echo   Ask the site's network admin to allow HTTPS - TCP 443 - to:
echo     api.github.com                        - finds the latest release
echo     github.com                            - starts the download
echo     objects.githubusercontent.com         - release file storage
echo     release-assets.githubusercontent.com  - release file storage
echo     codeload.github.com                   - source zip fallback
echo     raw.githubusercontent.com             - launcher updates
goto :diag_certs
:diag_allok
echo   All GitHub hosts are reachable from this machine, so the failure
echo   above may be transient - run this launcher again. If it keeps
echo   failing, send the report file below to the Pulse team.
:diag_certs
findstr /l /c:"CERT WARNING" "%DIAG_LOG%" >nul 2>&1
if not errorlevel 1 (
    echo.
    echo   A CERT WARNING above means this network intercepts HTTPS
    echo   ^(SSL inspection^). Downloads will keep failing until IT exempts
    echo   the hosts listed above from inspection.
)
echo.
echo   Report saved to: %DIAG_LOG%
goto :eof

:: One host: DNS, then TCP 443, then a real TLS handshake with the protocol
:: list pinned to Tls/Tls11/Tls12 (the .NET Framework default on this image
:: negotiates SSL3/TLS1.0 and false-fails modern hosts). Reports the
:: certificate issuer so an SSL-inspection appliance is visible at a glance.
:: PS 5.1: the validation callback MUST be cast to its delegate type
:: explicitly -- implicit conversion inside New-Object fails silently.
:probe
powershell -NoProfile -ExecutionPolicy Bypass -Command "$h='%~1';$line='';try{$null=[Net.Dns]::GetHostAddresses($h)}catch{$line=('  [FAIL] {0,-38} DNS lookup failed - {1}' -f $h,$_.Exception.Message.Trim())};if(-not $line){$c=New-Object Net.Sockets.TcpClient;$c.ReceiveTimeout=10000;$c.SendTimeout=10000;$iar=$c.BeginConnect($h,443,$null,$null);if(-not ($iar.AsyncWaitHandle.WaitOne(5000) -and $c.Connected)){$line=('  [FAIL] {0,-38} DNS ok but no connection on port 443' -f $h)}else{try{$script:pe='None';$cb=[Net.Security.RemoteCertificateValidationCallback]{param($s,$cert,$chain,$e) $script:pe=$e; $true};$ss=New-Object Net.Security.SslStream($c.GetStream(),$false,$cb);$ss.AuthenticateAsClient($h,$null,[Security.Authentication.SslProtocols]'Tls,Tls11,Tls12',$false);$cert2=New-Object Security.Cryptography.X509Certificates.X509Certificate2 $ss.RemoteCertificate;$iss=(($cert2.Issuer -split ',')[0]) -replace 'CN=','';$warn='';if($script:pe.ToString() -ne 'None'){$warn=' ** CERT WARNING: '+$script:pe};$line=('  [ OK ] {0,-38} cert issuer: {1}{2}' -f $h,$iss,$warn)}catch{$line=('  [FAIL] {0,-38} TLS handshake failed - {1}' -f $h,$_.Exception.Message.Trim())};$c.Close()}};Write-Output $line;Add-Content -LiteralPath '%DIAG_LOG%' -Value $line"
goto :eof

:: -- Live progress for long steps -----------------------------------------
:: Long steps (Chrome install, pip, extract, copy) used to print one static
:: line and then sit silent for minutes. A tech can't tell a slow install
:: from a hung one, and the usual reaction is to kill the window mid-install.
:: :spin runs the work in a background PowerShell runspace and animates the
:: SAME line (frame + mm:ss clock) until it finishes, so the window always
:: shows the step is still moving.
::
::   set "SPIN_LABEL=  Thing ......................... doing"  (exact text)
::   set "SPIN_DONE=  Thing ......................... done"    ('-' erases it)
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
powershell -NoProfile -ExecutionPolicy Bypass -Command "$CR=[string][char]13;$lbl=$env:SPIN_LABEL;$ps=[powershell]::Create();$null=$ps.AddScript('Set-Location -LiteralPath $env:SPIN_CWD; '+$env:SPIN_PSCMD);$h=$ps.BeginInvoke();$fr='|/-\';$i=0;$t0=Get-Date;$tty=$true;try{if([Console]::IsOutputRedirected){$tty=$false}}catch{$tty=$false};if(-not $tty){Write-Host $lbl};while(-not $h.IsCompleted){if($tty){Write-Host -NoNewline ($CR+$lbl+' '+$fr[$i]+' '+((Get-Date)-$t0).ToString('mm\:ss')+'  ');$i=($i+1) -band 3};Start-Sleep -Milliseconds 200};$rc=0;$msg='';$out=$null;try{$out=$ps.EndInvoke($h)}catch{$rc=1;$e=$_.Exception;if($e.InnerException){$e=$e.InnerException};$msg=$e.Message};if($ps.Streams.Error.Count -gt 0){$rc=1;if(-not $msg){$msg=[string]$ps.Streams.Error[0]}};$ps.Dispose();$ts=(Get-Date)-$t0;$fin=$env:SPIN_DONE;if(-not $fin){$fin=$lbl};if($rc -ne 0){$fin=$lbl+'  FAILED'};if($fin -eq '-'){if($tty){Write-Host -NoNewline ($CR+(' '*($lbl.Length+16))+$CR)}}else{if($ts.TotalSeconds -ge 5){$fin=$fin+'  ('+$ts.ToString('mm\:ss')+')'};if($tty){Write-Host ($CR+$fin+'                ')}else{Write-Host $fin}};if($env:SPIN_OUT){$out|Out-File -FilePath $env:SPIN_OUT -Encoding ascii};if($rc -ne 0 -and $msg){Write-Host ('       '+$msg)};exit $rc"
set "SPIN_RC=%errorlevel%"
set "SPIN_PSCMD="
set "SPIN_DONE="
set "SPIN_OUT="
exit /b %SPIN_RC%

:: -- Download one URL with the spinner ------------------------------------
:: Used only on the PowerShell fallback path; curl prints its own progress
:: bar and doesn't need this.
::   %1 = label   %2 = url   %3 = output file   %4 = done label
:dl_spin
set "SPIN_LABEL=%~1"
set "SPIN_DONE=%~4"
set "SPIN_PSCMD=$ProgressPreference='SilentlyContinue';[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;Invoke-WebRequest -UseBasicParsing -Uri '%~2' -OutFile '%~3'"
call :spin
exit /b %errorlevel%
