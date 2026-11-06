#Requires -Version 5.1
<#
.SYNOPSIS
    Installer-time SSL-interception diagnosis for failed bootstrap downloads.
.DESCRIPTION
    Called by run.bat when a first-run download fails (embedded Python from
    www.python.org, the pip zipapp from bootstrap.pypa.io, packages from PyPI).
    Completes a TLS handshake to each host while accepting ANY certificate,
    then validates the certificate actually presented against the machine's
    trust store. A cert that doesn't chain to a trusted root means a firewall
    doing SSL deep-packet inspection is substituting certificates -- the
    SEC_E_UNTRUSTED_ROOT failure the Kent School District install hit -- so
    print a plain-English explanation naming the intercepting device instead
    of leaving the tech with a raw schannel error.

    Runs before Pulse (and its Python) exists, so it must stay dependency-free
    and print human text, not JSON. Pulse's own Test-TlsInspection.ps1 is the
    full runtime equivalent; keep their classification logic in sync.
.PARAMETER TargetHosts
    Comma-separated hostnames that just failed to download.
.NOTES
    Exit codes: 0 = no interception seen (or hosts unreachable), 2 = at least
    one host presented a substituted certificate.
#>
[CmdletBinding()]
param([string]$TargetHosts = 'www.python.org')

$ErrorActionPreference = 'SilentlyContinue'
$intercepted = @()
# Breadcrumb log: this diagnostic must stay silent on the console when the
# network is clean, so when IT fails it fails invisibly -- the log is the only
# way to debug it from the field ("send me %TEMP%\pulse-install-tls.log").
$diag = @("=== Test-InstallTls $(Get-Date -Format s) targets=$TargetHosts ===")

foreach ($h in ($TargetHosts -split ',')) {
    $h = $h.Trim()
    if (-not $h) { continue }
    $tcp = $null; $ssl = $null
    $script:PresentedCert = $null
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $iar = $tcp.BeginConnect($h, 443, $null, $null)
        if (-not ($iar.AsyncWaitHandle.WaitOne(4000, $false) -and $tcp.Connected)) {
            $diag += "$h : TCP connect failed/timed out"
            continue
        }
        $tcp.EndConnect($iar)

        # Accept every certificate during the handshake -- validation happens
        # explicitly below so a substituted cert is captured, not just refused.
        # The cast to RemoteCertificateValidationCallback is REQUIRED: Windows
        # PowerShell 5.1 can fail the implicit scriptblock->delegate conversion
        # inside New-Object (silently, given the error handling here), which is
        # exactly how this check printed nothing on the first Kent-network run.
        $cb = [System.Net.Security.RemoteCertificateValidationCallback] {
            param($sender, $cert, $chain, $errors)
            if ($cert) {
                $script:PresentedCert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($cert)
            }
            return $true
        }
        $ssl = New-Object System.Net.Security.SslStream($tcp.GetStream(), $false, $cb)
        # Explicit protocols are REQUIRED on Windows PowerShell 5.1: its .NET
        # Framework host defaults the parameterless overload to SSL3/TLS 1.0,
        # which modern endpoints reject outright (SEC_E_UNSUPPORTED_FUNCTION
        # on a real VPU), not the OS defaults .NET Core uses. Tls13 is
        # deliberately absent (enum needs .NET 4.8+; requesting it on schannel
        # without TLS 1.3 can fail the handshake). Sync: Test-TlsInspection.ps1.
        $protocols = [System.Security.Authentication.SslProtocols]'Tls, Tls11, Tls12'
        try { $ssl.AuthenticateAsClient($h, $null, $protocols, $false) } catch { }
        # Belt-and-suspenders for PS 5.1: if the callback didn't capture (e.g.
        # its scope didn't stick), the stream itself still holds the cert after
        # an accepted handshake.
        if (-not $script:PresentedCert -and $ssl.IsAuthenticated -and $ssl.RemoteCertificate) {
            $script:PresentedCert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($ssl.RemoteCertificate)
        }
        if (-not $script:PresentedCert) { $diag += "$h : handshake yielded no certificate"; continue }

        $chain = New-Object System.Security.Cryptography.X509Certificates.X509Chain
        $chain.ChainPolicy.RevocationMode = [System.Security.Cryptography.X509Certificates.X509RevocationMode]::NoCheck
        $built = $chain.Build($script:PresentedCert)
        $statuses = @($chain.ChainStatus | ForEach-Object { $_.Status.ToString() })
        $chain.Reset()

        # ANY date-related status means a wrong VPU clock or an expired cert,
        # NOT interception -- don't send the tech after the firewall for those.
        # (An expired cert also drags in PartialChain -- its expired issuer
        # can't be resolved -- so "time-only" would misread it. DPI certs are
        # minted on the fly with fresh validity, so a genuinely intercepted
        # connection never shows NotTimeValid.)
        $timeInvolved = [bool]($statuses | Where-Object { $_ -in @('NotTimeValid', 'NotTimeNested') })

        if (-not $built -and -not $timeInvolved) {
            $issuerCn = $script:PresentedCert.GetNameInfo([System.Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $true)
            $org = $null
            if ($script:PresentedCert.Issuer -match '(?:^|,\s*)O=("[^"]*"|[^,]+)') {
                $org = $Matches[1].Trim('"')
            }
            $who = if ($org -and $org -ne $issuerCn) { "$issuerCn ($org)" } else { $issuerCn }
            $intercepted += [pscustomobject]@{ TargetHost = $h; Who = $who }
        }
        $diag += "$h : built=$built statuses=[$($statuses -join ',')] issuer=$($script:PresentedCert.Issuer)"
    }
    catch {
        $diag += "$h : EXCEPTION $($_.Exception.Message)"
    }
    finally {
        if ($ssl) { $ssl.Dispose() }
        if ($tcp) { $tcp.Close() }
    }
}

$diag += "verdict: intercepted=$($intercepted.Count)"
try { $diag | Out-File -FilePath (Join-Path ([System.IO.Path]::GetTempPath()) 'pulse-install-tls.log') -Append -Encoding utf8 } catch { }

if ($intercepted.Count -gt 0) {
    Write-Output ''
    Write-Output '  ============================================================'
    Write-Output '   THIS NETWORK IS INTERCEPTING SECURE CONNECTIONS'
    Write-Output '  ============================================================'
    foreach ($i in $intercepted) {
        Write-Output ('   ' + $i.TargetHost + ' presented a certificate issued by')
        Write-Output ('   "' + $i.Who + '" instead of a public authority.')
    }
    Write-Output ''
    Write-Output '   The venue firewall is decrypting HTTPS traffic (SSL'
    Write-Output '   inspection), so this download is rejected as untrusted.'
    Write-Output '   This is a network problem, not a Pulse or VPU problem.'
    Write-Output ''
    Write-Output '   Fix: ask the venue IT team to EXEMPT these domains from'
    Write-Output '   SSL decryption (the bypass list - a URL allowlist is NOT'
    Write-Output '   enough):'
    Write-Output ''
    Write-Output '     www.python.org    bootstrap.pypa.io    pypi.org'
    Write-Output '     files.pythonhosted.org    *.pixellot.tv    *.singular.live'
    Write-Output ''
    Write-Output '   Or run this install once from a network without SSL'
    Write-Output '   inspection (a phone hotspot works). After install, the'
    Write-Output '   Pulse Network tab shows this same check with full detail.'
    Write-Output '  ============================================================'
    exit 2
}
exit 0
