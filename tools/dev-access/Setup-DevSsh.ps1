<#
.SYNOPSIS
  One-time hardened SSH setup for a TEST VPU, reachable only over Tailscale.

  What it does:
    1. Installs Tailscale (winget, or tells you where to get the MSI)
    2. Installs OpenSSH Server (Win32-OpenSSH MSI; Windows capability as fallback)
    3. Installs your public key (admin accounts use administrators_authorized_keys)
    4. Hardens sshd_config: pubkey-only, no passwords, single allowed user
    5. Sets PowerShell as the SSH default shell
    6. Replaces the default any-address firewall rule with one scoped to the
       Tailscale CGNAT range (100.64.0.0/10) -- port 22 is closed to the venue LAN
       and the internet

  Run as Administrator on the VPU. Safe to re-run.

.EXAMPLE
  .\Setup-DevSsh.ps1 -PublicKey "ssh-ed25519 AAAA... ian.moore vpu-test"
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$PublicKey,

    # Account SSH logins are limited to. Defaults to whoever runs the script.
    [string]$AllowUser = $env:USERNAME
)

$ErrorActionPreference = 'Stop'

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { throw 'Run this from an elevated (Administrator) PowerShell.' }

if ($PublicKey -notmatch '^(ssh-ed25519|ssh-rsa|ecdsa-sha2-\S+)\s+\S+') {
    throw "That doesn't look like an SSH public key. Pass the full contents of your .pub file."
}

# --- 1. Tailscale --------------------------------------------------------
if (-not (Get-Command tailscale -ErrorAction SilentlyContinue)) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host '[1/6] Installing Tailscale...'
        winget install --id Tailscale.Tailscale --accept-source-agreements --accept-package-agreements
        $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
    } else {
        Write-Warning 'winget not available (common on LTSC). Install Tailscale manually from https://tailscale.com/download/windows then re-run this script.'
        exit 1
    }
} else {
    Write-Host '[1/6] Tailscale already installed.'
}

# --- 2. OpenSSH Server ----------------------------------------------------
# Primary path is Microsoft's Win32-OpenSSH MSI from GitHub, hash-pinned.
# The Windows capability (Add-WindowsCapability) downloads through Windows
# Update, which the fleet image's GPO breaks: it fails with 0x80072ee6, or
# crawls for many minutes. It stays as a fallback for when GitHub is blocked.
$msiUrl    = 'https://github.com/PowerShell/Win32-OpenSSH/releases/download/10.0.0.0p2-Preview/OpenSSH-Win64-v10.0.0.0.msi'
$msiSha256 = 'DDEC9C53864280759CF9F74791CEFD387100E3946AA849A1C138A4ED1B96B7D9'

if (Get-Service sshd -ErrorAction SilentlyContinue) {
    Write-Host '[2/6] OpenSSH Server already installed.'
} else {
    Write-Host '[2/6] Installing OpenSSH Server (Win32-OpenSSH MSI)...'
    $msi = Join-Path $env:TEMP 'OpenSSH-Win64.msi'
    $msiOk = $false
    try {
        # PS 5.1 / .NET Framework defaults to TLS 1.0; GitHub needs 1.2.
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $ProgressPreference = 'SilentlyContinue'   # the 5.1 progress bar slows downloads badly
        Invoke-WebRequest -Uri $msiUrl -OutFile $msi -UseBasicParsing
        $hash = (Get-FileHash -Path $msi -Algorithm SHA256).Hash
        if ($hash -ne $msiSha256) { throw "MSI hash mismatch: got $hash" }
        $p = Start-Process msiexec.exe -ArgumentList "/i `"$msi`" /qn ADDLOCAL=Server" -Wait -PassThru
        if ($p.ExitCode -ne 0 -and $p.ExitCode -ne 3010) { throw "msiexec exited $($p.ExitCode)" }
        $msiOk = $true
    } catch {
        Write-Warning "MSI install failed ($($_.Exception.Message)). Falling back to the Windows capability..."
    }
    if (-not $msiOk) {
        $cap = Get-WindowsCapability -Online -Name 'OpenSSH.Server*' | Select-Object -First 1
        $null = Add-WindowsCapability -Online -Name $cap.Name
    }
}
Set-Service sshd -StartupType Automatic
Start-Service sshd -ErrorAction SilentlyContinue   # first start generates default config/host keys

# The MSI installs under Program Files, the capability under System32.
$sshdExe = ((Get-CimInstance Win32_Service -Filter "Name='sshd'").PathName).Trim('"')

# --- 3. Authorized key ----------------------------------------------------
# Members of the Administrators group authenticate against this shared file,
# and sshd requires it to be locked down to SYSTEM + Administrators only.
Write-Host "[3/6] Installing public key for '$AllowUser'..."
$keyFile = Join-Path $env:ProgramData 'ssh\administrators_authorized_keys'
Set-Content -Path $keyFile -Value $PublicKey -Encoding ascii
icacls $keyFile /inheritance:r /grant 'SYSTEM:F' /grant 'BUILTIN\Administrators:F' | Out-Null

# --- 4. Harden sshd_config -------------------------------------------------
Write-Host '[4/6] Hardening sshd_config (pubkey-only, single user)...'
$confFile = Join-Path $env:ProgramData 'ssh\sshd_config'
$directives = [ordered]@{
    'PasswordAuthentication'       = 'no'
    'KbdInteractiveAuthentication' = 'no'
    'PubkeyAuthentication'         = 'yes'
    'AllowUsers'                   = $AllowUser
}
$names = ($directives.Keys | ForEach-Object { [regex]::Escape($_) }) -join '|'
# Strip existing (or commented) copies of our directives, then PREPEND ours.
# Prepending keeps them in the global section, above the default
# "Match Group administrators" block -- appending would land inside it.
$conf = Get-Content $confFile | Where-Object { $_ -notmatch "^\s*#?\s*($names)\b" }
$header = $directives.GetEnumerator() | ForEach-Object { "$($_.Key) $($_.Value)" }
Set-Content -Path $confFile -Value (@($header) + @('') + @($conf)) -Encoding ascii

# Validate before restarting so a bad config can't lock us out of the service.
& $sshdExe -t
if ($LASTEXITCODE -ne 0) { throw 'sshd_config failed validation; not restarting sshd.' }

# --- 5. Default shell = PowerShell -----------------------------------------
Write-Host '[5/6] Setting PowerShell as the SSH default shell...'
New-Item -Path 'HKLM:\SOFTWARE\OpenSSH' -Force | Out-Null
Set-ItemProperty -Path 'HKLM:\SOFTWARE\OpenSSH' -Name 'DefaultShell' `
    -Value "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"

# --- 6. Firewall: tailnet only ---------------------------------------------
Write-Host '[6/6] Scoping firewall to the tailnet (removing any-address rules)...'
# Remove every inbound allow on TCP 22, whatever named it (the capability
# and the MSI each add their own any-address rule), then add ours.
Get-NetFirewallPortFilter -Protocol TCP -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalPort -eq '22' } |
    Get-NetFirewallRule -ErrorAction SilentlyContinue |
    Where-Object { $_.Direction -eq 'Inbound' -and $_.Action -eq 'Allow' } |
    Remove-NetFirewallRule
New-NetFirewallRule -DisplayName 'Pulse dev SSH (tailnet only)' -Direction Inbound `
    -Protocol TCP -LocalPort 22 -RemoteAddress '100.64.0.0/10' -Action Allow | Out-Null

Restart-Service sshd

# --- Done -------------------------------------------------------------------
Write-Host ''
Write-Host "Done. SSH is key-only, restricted to '$AllowUser', reachable only via Tailscale." -ForegroundColor Green
$status = & tailscale status 2>&1
if ($LASTEXITCODE -ne 0 -or "$status" -match 'Logged out|Stopped') {
    Write-Host 'Tailscale is not logged in yet. Run:  tailscale up' -ForegroundColor Yellow
    Write-Host 'Then get this box''s address with:   tailscale ip -4'
} else {
    $ip = & tailscale ip -4 2>$null | Select-Object -First 1
    Write-Host "Tailscale IPv4: $ip  (use this as HostName in ~/.ssh/config on the Mac)"
}
