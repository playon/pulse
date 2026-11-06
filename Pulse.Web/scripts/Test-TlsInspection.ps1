#Requires -Version 5.1
<#
.SYNOPSIS
    Detects SSL/TLS interception (firewall certificate substitution) on the
    HTTPS services Pixellot depends on.
.DESCRIPTION
    Completes a real TLS handshake to each service while accepting ANY
    certificate, captures the certificate the far end actually presented, then
    validates that certificate against the VPU's own trust store. A cert that
    doesn't chain to a trusted root means a middlebox (a school firewall doing
    SSL deep-packet inspection) is substituting its own certificate -- the
    failure mode where video streams fine but Singular graphics never load,
    because the graphics data channel correctly rejects the firewall's cert.
    Field-proven signature: Kent School District 2026-07 -- the district's DPI
    bypass covered only *.app.singular.live, so datastream.singular.live got a
    "KSD-FW1-DPI" cert and overlays died at every school in the district.
    Plain reachability tests can't see this (TCP/443 connects fine), which is
    why this check exists alongside Test-NetworkPorts. Outputs JSON to stdout.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

# Web-filter / proxy vendors, matched against the block page's redirect
# target, Server header and body. Naming the box is the whole point: "your
# Linewize filter is blocking pixellot.tv" gets a district's IT team into the
# right console, where "something on the network refused the connection" gets
# a shrug. Ordered most-specific first; the list is data, add to it freely.
$FilterVendorPatterns = @(
    @{ pattern = 'linewize|familyzone|family-zone';        name = 'Linewize / Family Zone' }
    @{ pattern = 'zscaler';                                name = 'Zscaler' }
    @{ pattern = 'iboss';                                  name = 'iboss' }
    @{ pattern = 'securly';                                name = 'Securly' }
    @{ pattern = 'lightspeedsystems|lightspeed';           name = 'Lightspeed Systems' }
    @{ pattern = 'goguardian';                             name = 'GoGuardian' }
    @{ pattern = 'contentkeeper';                          name = 'ContentKeeper' }
    # "Web Filter Violation" is the FortiGate replacement page's <title>; the
    # FortiGuard wording sits far down a page of inline CSS (Armstrong IL).
    @{ pattern = 'fortiguard|fortinet|fortigate|web filter violation'; name = 'FortiGuard (Fortinet)' }
    @{ pattern = 'paloaltonetworks';                       name = 'Palo Alto Networks' }
    @{ pattern = 'umbrella|opendns';                       name = 'Cisco Umbrella (OpenDNS)' }
    @{ pattern = 'meraki';                                 name = 'Cisco Meraki' }
    @{ pattern = 'sonicwall';                              name = 'SonicWall' }
    @{ pattern = 'smoothwall';                             name = 'Smoothwall' }
    @{ pattern = 'barracuda';                              name = 'Barracuda' }
    @{ pattern = 'netsweeper';                             name = 'Netsweeper' }
    @{ pattern = 'forcepoint|websense';                    name = 'Forcepoint (Websense)' }
    @{ pattern = 'blocksi';                                name = 'Blocksi' }
    @{ pattern = 'deledao';                                name = 'Deledao' }
    @{ pattern = 'sophos';                                 name = 'Sophos' }
    @{ pattern = 'watchguard';                             name = 'WatchGuard' }
    @{ pattern = 'trellix|mcafee';                         name = 'Trellix (McAfee)' }
    @{ pattern = 'dnsfilter';                              name = 'DNSFilter' }
    @{ pattern = 'cleanbrowsing';                          name = 'CleanBrowsing' }
)

function Get-FilterBlockSignal {
    <#
    .SYNOPSIS
        Asks a filtered domain over plain HTTP and reports the block page it
        gets back: which host serves it, the full block URL, and which vendor
        it belongs to.
    .DESCRIPTION
        Runs for hosts whose TLS handshake was reset, truncated or dropped.
        The filter that killed 443 normally answers port 80 with a redirect
        (or a 200/403 body) advertising itself, which is what a tech sees browsing
        to the domain from the same LAN. Everything here is best-effort: a
        silent filter simply yields nulls and the caller falls back to
        "a filtering device on the venue network".
    #>
    param([string]$Domain)

    $signal = [ordered]@{ blockPageHost = $null; blockPageUrl = $null; filterVendor = $null; httpStatus = $null }
    $resp = $null
    $reader = $null

    try {
        $req = [System.Net.WebRequest]::Create("http://$Domain/")
        $req.Method = 'GET'
        $req.AllowAutoRedirect = $false   # the redirect target IS the evidence
        $req.Timeout = 2500
        $req.ReadWriteTimeout = 2500
        $req.UserAgent = 'Pulse-Diagnostics'

        try { $resp = $req.GetResponse() }
        catch [System.Net.WebException] {
            # A filter answering 403 Forbidden still hands back a readable
            # response object - that body is exactly the block page.
            if ($_.Exception.Response) { $resp = $_.Exception.Response } else { throw }
        }

        try { $signal.httpStatus = [int]$resp.StatusCode } catch { }
        $location = [string]$resp.Headers['Location']
        $server   = [string]$resp.Headers['Server']

        # Read a slice of the body - enough for a vendor marker, small enough
        # that a hung connection can't stall the sweep.
        $body = ''
        $stream = $resp.GetResponseStream()
        if ($stream) {
            $reader = New-Object System.IO.StreamReader($stream)
            # ReadBlock, not Read: one Read returns only the first chunk that
            # arrived, which on a FortiGate block page is all CSS. The 2.5s
            # ReadWriteTimeout still bounds a hung connection.
            $buffer = New-Object char[] 65536
            $read = $reader.ReadBlock($buffer, 0, 65536)
            if ($read -gt 0) { $body = -join $buffer[0..($read - 1)] }
        }

        # Where the block page lives. A redirect to a DIFFERENT host is the
        # cleanest signal; otherwise the responding host may still be the
        # filter answering in place of the real server.
        $blockHost = $null
        if ($location) {
            try { $blockHost = ([uri]$location).Host } catch { $blockHost = $null }
            if ($blockHost -and ($blockHost -eq $Domain -or $blockHost.EndsWith(".$Domain"))) {
                $blockHost = $null   # ordinary http->https redirect, not a block
            }
            if ($blockHost) {
                $signal.blockPageHost = $blockHost
                $signal.blockPageUrl  = $location
            }
        }

        $haystack = (("$location $server $body $blockHost")).ToLower()
        foreach ($v in $FilterVendorPatterns) {
            if ($haystack -match $v.pattern) { $signal.filterVendor = $v.name; break }
        }
    }
    catch {
        # Port 80 blocked too, DNS dead, or a filter that just drops - no
        # signal to report, and never a reason to fail the whole check.
    }
    finally {
        if ($reader) { $reader.Close() }
        if ($resp) { $resp.Close() }
    }

    return $signal
}

function Add-U16 {
    # Cast before shifting: a [byte] left shift loses its high byte on PS 5.1.
    param($List, [int]$Value)
    $null = $List.Add([byte](($Value -shr 8) -band 0xFF))
    $null = $List.Add([byte]($Value -band 0xFF))
}

function New-ClientHello {
    # A TLS 1.2 hello with SNI, so the reply can be read without SslStream.
    param([string]$Sni)

    $nameBytes = [System.Text.Encoding]::ASCII.GetBytes($Sni)
    $sniData = New-Object System.Collections.Generic.List[byte]
    Add-U16 $sniData ($nameBytes.Length + 3)
    $null = $sniData.Add(0)
    Add-U16 $sniData $nameBytes.Length
    $null = $sniData.AddRange($nameBytes)

    $grpData = New-Object System.Collections.Generic.List[byte]
    Add-U16 $grpData 6
    Add-U16 $grpData 29; Add-U16 $grpData 23; Add-U16 $grpData 24
    $pfData = New-Object System.Collections.Generic.List[byte]
    $null = $pfData.Add(1); $null = $pfData.Add(0)
    $sigData = New-Object System.Collections.Generic.List[byte]
    $sigPairs = @(0x0403, 0x0503, 0x0401, 0x0501, 0x0804, 0x0805, 0x0201)
    Add-U16 $sigData ($sigPairs.Count * 2)
    foreach ($pair in $sigPairs) { Add-U16 $sigData $pair }

    $ext = New-Object System.Collections.Generic.List[byte]
    foreach ($e in @(@{ t = 0x0000; d = $sniData }, @{ t = 0x000A; d = $grpData },
                     @{ t = 0x000B; d = $pfData }, @{ t = 0x000D; d = $sigData })) {
        Add-U16 $ext $e.t
        Add-U16 $ext $e.d.Count
        $null = $ext.AddRange($e.d)
    }

    $body = New-Object System.Collections.Generic.List[byte]
    $null = $body.Add(3); $null = $body.Add(3)
    $rand = New-Object byte[] 32
    (New-Object Random).NextBytes($rand)
    $null = $body.AddRange($rand)
    $null = $body.Add(0)
    $suites = @(0xC02F, 0xC030, 0xC02B, 0xC02C, 0x009C, 0x009D, 0x002F, 0x0035)
    Add-U16 $body ($suites.Count * 2)
    foreach ($suite in $suites) { Add-U16 $body $suite }
    $null = $body.Add(1); $null = $body.Add(0)
    Add-U16 $body $ext.Count
    $null = $body.AddRange($ext)

    $hs = New-Object System.Collections.Generic.List[byte]
    $null = $hs.Add(1)
    $null = $hs.Add([byte](([int]$body.Count -shr 16) -band 0xFF))
    $null = $hs.Add([byte](([int]$body.Count -shr 8) -band 0xFF))
    $null = $hs.Add([byte]([int]$body.Count -band 0xFF))
    $null = $hs.AddRange($body)
    $rec = New-Object System.Collections.Generic.List[byte]
    $null = $rec.Add(0x16); $null = $rec.Add(3); $null = $rec.Add(1)
    Add-U16 $rec $hs.Count
    $null = $rec.AddRange($hs)
    return $rec.ToArray()
}

function Read-TlsFlight {
    # Parse complete messages even when a TLS record or message spans TCP reads.
    # A Certificate header alone is not a complete server flight. Field: Hoover
    # FortiGate, 2026-09-03: 1,448 of 13,829 reply bytes reached the VPU.
    param([byte[]]$Bytes)
    $out = [ordered]@{ rawBytes = $Bytes.Length; messages = ''; complete = $false; handshake = $false; alert = $false }
    $names = @{ 2 = 'ServerHello'; 11 = 'Certificate'; 12 = 'ServerKeyExchange'; 13 = 'CertificateRequest'; 14 = 'ServerHelloDone' }
    $hs = New-Object System.Collections.Generic.List[byte]
    $pos = 0
    while ($pos + 5 -le $Bytes.Length) {
        $recLen = ([int]$Bytes[$pos + 3] -shl 8) -bor [int]$Bytes[$pos + 4]
        if ($Bytes[$pos + 1] -ne 3) { break }
        if ($Bytes[$pos] -eq 0x15) { $out.alert = $true }
        if ($Bytes[$pos] -eq 0x16) {
            $out.handshake = $true
            $available = [math]::Min($recLen, $Bytes.Length - $pos - 5)
            for ($i = 0; $i -lt $available; $i++) { $null = $hs.Add($Bytes[$pos + 5 + $i]) }
        }
        $pos += 5 + $recLen
    }
    $hsBytes = $hs.ToArray()
    $seen = New-Object System.Collections.Generic.List[string]
    $pos = 0
    while ($pos + 4 -le $hsBytes.Length) {
        $len = ([int]$hsBytes[$pos + 1] -shl 16) -bor ([int]$hsBytes[$pos + 2] -shl 8) -bor [int]$hsBytes[$pos + 3]
        if ($pos + 4 + $len -gt $hsBytes.Length) { break }
        $name = $names[[int]$hsBytes[$pos]]
        if (-not $name) { $name = "type $($hsBytes[$pos])" }
        $null = $seen.Add($name)
        $pos += 4 + $len
    }
    $out.messages = $seen -join ', '
    $out.complete = $seen -contains 'ServerHelloDone'
    return $out
}

function Test-RawFlight {
    # SslStream reports the same timeout for no reply and for a partial reply.
    # Read raw bytes to distinguish them; a failed re-connect is inconclusive.
    param([string]$Domain, [int]$TimeoutMs = 4000)
    $out = [ordered]@{ rawBytes = $null; messages = ''; complete = $false; handshake = $false; alert = $false }
    $tcp = $null
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $connect = $tcp.BeginConnect($Domain, 443, $null, $null)
        if (-not ($connect.AsyncWaitHandle.WaitOne($TimeoutMs, $false) -and $tcp.Connected)) { return $out }
        $tcp.EndConnect($connect)
        $hello = [byte[]](New-ClientHello -Sni $Domain)
        $stream = $tcp.GetStream()
        $stream.WriteTimeout = $TimeoutMs
        $stream.Write($hello, 0, $hello.Length)
        $stream.Flush()
        $all = New-Object System.Collections.Generic.List[byte]
        $buf = New-Object byte[] 8192
        try {
            while ($sw.ElapsedMilliseconds -lt $TimeoutMs) {
                $stream.ReadTimeout = [math]::Max(1, $TimeoutMs - [int]$sw.ElapsedMilliseconds)
                $n = $stream.Read($buf, 0, $buf.Length)
                if ($n -le 0) { break }
                for ($i = 0; $i -lt $n; $i++) { $null = $all.Add($buf[$i]) }
                if ($all.Count -gt 60000) { break }
            }
        }
        catch { }
        $out = Read-TlsFlight -Bytes $all.ToArray()
    }
    catch { }
    finally {
        $sw.Stop()
        if ($tcp) { $tcp.Close() }
    }
    return $out
}

try {
    # Known-HTTPS endpoints only. prod-echo.pixellot.tv:443 is intentionally
    # absent -- it's a Zixi tunnel, not TLS, and would false-fail the handshake.
    # The full singular.live family is listed host-by-host because DPI bypass
    # lists are scoped by pattern; at Kent, *.app.singular.live was exempt while
    # datastream/api/apex were still decrypted -- only per-host checks catch a
    # partial bypass. www.python.org is the Pulse installer's own download
    # source (its SEC_E_UNTRUSTED_ROOT failure is the same root cause).
    $targets = @(
        @{ domain = 'singular.live';            purpose = 'Singular graphics (apex)' }
        @{ domain = 'app.singular.live';        purpose = 'Singular graphics app' }
        @{ domain = 'api.singular.live';        purpose = 'Singular graphics API' }
        @{ domain = 'datastream.singular.live'; purpose = 'Singular graphics data feed' }
        @{ domain = 'service.singular.live';    purpose = 'Singular overlay service' }
        @{ domain = 'pixellot.tv';              purpose = 'Pixellot cloud' }
        @{ domain = 'software.pixellot.tv';     purpose = 'Pixellot software updates' }
        @{ domain = 'nfhsnetwork.com';          purpose = 'NFHS Network' }
        @{ domain = 'secure.logmein.com';       purpose = 'Remote support (LogMeIn)' }
        @{ domain = 'www.python.org';           purpose = 'Pulse installer download' }
    )

    $results = foreach ($t in $targets) {
        $status = 'blocked'; $detail = $null; $failureKind = $null
        $blockPageHost = $null; $blockPageUrl = $null; $filterVendor = $null
        $issuer = $null; $issuerCn = $null; $issuerOrg = $null; $subjectCn = $null
        $trusted = $null; $chainErrors = $null; $notAfter = $null
        $tcp = $null; $ssl = $null
        $sw = [System.Diagnostics.Stopwatch]::StartNew()

        try {
            $tcp = New-Object System.Net.Sockets.TcpClient
            $connect = $tcp.BeginConnect($t.domain, 443, $null, $null)
            $waited = $connect.AsyncWaitHandle.WaitOne(4000, $false)
            if (-not ($waited -and $tcp.Connected)) {
                $detail = 'TCP connect to 443 timed out or was refused'
            }
            else {
                $tcp.EndConnect($connect)

                # Accept every certificate during the handshake -- validation is
                # done explicitly below, so an intercepted (untrusted) cert is
                # CAPTURED and reported instead of just aborting the handshake.
                # Clone in the callback: SslStream may dispose its copy after.
                # The delegate cast is REQUIRED: Windows PowerShell 5.1 can
                # fail the implicit scriptblock->delegate conversion inside
                # New-Object (field-found on the first Kent-network run of the
                # installer twin, Test-InstallTls.ps1 -- keep both in sync).
                $script:PresentedCert = $null
                $cb = [System.Net.Security.RemoteCertificateValidationCallback] {
                    param($sender, $cert, $chain, $errors)
                    if ($cert) {
                        $script:PresentedCert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($cert)
                    }
                    return $true
                }
                $ssl = New-Object System.Net.Security.SslStream($tcp.GetStream(), $false, $cb)
                $ssl.ReadTimeout = 6000
                $ssl.WriteTimeout = 6000
                try {
                    # The explicit protocol list is REQUIRED on Windows
                    # PowerShell 5.1: its .NET Framework host resolves the
                    # parameterless overload to the legacy default (SSL3/TLS
                    # 1.0) -- NOT the OS schannel defaults; that's .NET Core
                    # behavior. Modern endpoints reject a TLS 1.0 hello, so
                    # 8 of 11 targets false-failed with
                    # SEC_E_UNSUPPORTED_FUNCTION on a real VPU (2026-07-16).
                    # Tls13 is deliberately absent: the enum flag needs .NET
                    # 4.8+ and requesting it on schannel builds without TLS
                    # 1.3 support can itself fail the handshake; every target
                    # negotiates 1.2. Keep in sync with Test-InstallTls.ps1.
                    $protocols = [System.Security.Authentication.SslProtocols]'Tls, Tls11, Tls12'
                    $ssl.AuthenticateAsClient($t.domain, $null, $protocols, $false)
                }
                catch {
                    # Even with an accept-all callback the handshake can die
                    # (RST mid-handshake, protocol downgrade tampering) -- the
                    # same SSPI/schannel failures Kent showed on the decrypted
                    # singular.live hosts. Classified below only if no cert was
                    # captured; with a cert in hand we can still judge trust.
                    $inner = $_.Exception
                    while ($inner.InnerException) { $inner = $inner.InnerException }
                    $detail = $inner.Message
                    $status = 'handshake-fail'
                    $failureKind = 'protocol'
                    # A TCP reset the instant the ClientHello lands is the
                    # signature of a category/SNI web filter, NOT of SSL
                    # decryption: the filter reads the hostname from the
                    # unencrypted SNI field, decides the domain sits in a
                    # blocked category, and kills the connection. No
                    # certificate is ever substituted, so the interception
                    # check below can never fire and the whole event used to
                    # land in a vague "possible SSL inspection" warning.
                    # Field: Linewize at an Ohio venue 2026-08-19 - eight
                    # Pixellot-critical hosts reset, while a browser on the
                    # same LAN got a "Content Blocked" page (rule "Additional
                    # Blocked Categories", tag "pixellot") served under a
                    # VALID public certificate. Split it out so the verdict
                    # can name the filter instead of hedging about
                    # inspection - the two problems have different fixes.
                    $isReset = $false
                    if ($inner -is [System.Net.Sockets.SocketException]) {
                        # 10054 WSAECONNRESET / 10053 WSAECONNABORTED
                        if ($inner.NativeErrorCode -eq 10054 -or $inner.NativeErrorCode -eq 10053) { $isReset = $true }
                    }
                    if (-not $isReset -and $inner.Message -match 'forcibly closed|connection was reset|connection was aborted') {
                        $isReset = $true
                    }
                    if ($isReset) { $status = 'filtered'; $failureKind = 'reset' }
                }

                # Belt-and-suspenders for PS 5.1: if the callback didn't
                # capture, the stream itself still holds the cert after an
                # accepted handshake.
                if (-not $script:PresentedCert -and $ssl.IsAuthenticated -and $ssl.RemoteCertificate) {
                    $script:PresentedCert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($ssl.RemoteCertificate)
                }

                if ($script:PresentedCert) {
                    $cert2 = $script:PresentedCert
                    $issuer = $cert2.Issuer
                    # Trim: real interceptor CNs carry trailing whitespace
                    # (Zscaler ships "Zscaler Intermediate Root CA (zscalerone.net) (t) ")
                    # which doubles up spaces when we interpolate the org after it.
                    # Cast first so a null CN doesn't blow up the method call on 5.1.
                    $issuerCn = ([string]$cert2.GetNameInfo([System.Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $true)).Trim()
                    $subjectCn = ([string]$cert2.GetNameInfo([System.Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $false)).Trim()
                    if ($cert2.Issuer -match '(?:^|,\s*)O=("[^"]*"|[^,]+)') {
                        $issuerOrg = $Matches[1].Trim('"')
                    }
                    $notAfter = $cert2.NotAfter.ToString('yyyy-MM-dd')

                    # Validate against the VPU's trust store. Revocation is
                    # skipped: it needs its own outbound lookups (often blocked
                    # on these same networks) and isn't the signal -- chain
                    # trust is.
                    $x509chain = New-Object System.Security.Cryptography.X509Certificates.X509Chain
                    $x509chain.ChainPolicy.RevocationMode = [System.Security.Cryptography.X509Certificates.X509RevocationMode]::NoCheck
                    $built = $x509chain.Build($cert2)
                    $statuses = @($x509chain.ChainStatus | ForEach-Object { $_.Status.ToString() })
                    $chainErrors = $statuses -join ', '
                    $x509chain.Reset()

                    # ANY time-related chain status is NOT interception: a
                    # wrong VPU clock (or a genuinely expired cert) fails the
                    # date check, and an expired cert also drags in
                    # PartialChain -- its expired issuer can't be resolved -- so
                    # requiring time-ONLY would misread it as interception
                    # (verified against expired.badssl.com). DPI certs are
                    # minted on the fly with fresh validity, so a genuinely
                    # intercepted connection never shows NotTimeValid. Keep it
                    # a distinct status so techs chase the clock, not the
                    # firewall.
                    $timeInvolved = [bool]($statuses | Where-Object { $_ -in @('NotTimeValid', 'NotTimeNested') })

                    if ($built) { $status = 'pass'; $trusted = $true }
                    elseif ($timeInvolved) { $status = 'cert-time'; $trusted = $false }
                    else {
                        # UntrustedRoot / PartialChain: the presented chain
                        # doesn't reach a trusted root -- certificate
                        # substitution by an inspecting middlebox.
                        $status = 'intercepted'; $trusted = $false
                    }
                }
            }
        }
        catch {
            # DNS failure or socket-level error before the handshake.
            $status = 'blocked'
            $detail = $_.Exception.Message
        }
        finally {
            if ($ssl) { $ssl.Dispose() }
            if ($tcp) { $tcp.Close() }
        }

        $sw.Stop()

        [ordered]@{
            domain      = $t.domain
            purpose     = $t.purpose
            status      = $status
            failureKind = $failureKind
            trusted     = $trusted
            issuer      = $issuer
            issuerCn    = $issuerCn
            issuerOrg   = $issuerOrg
            subjectCn   = $subjectCn
            chainErrors = $chainErrors
            notAfter    = $notAfter
            latencyMs   = [math]::Round($sw.Elapsed.TotalMilliseconds, 1)
            detail      = $detail
            rawBytes    = $null
            serverMessages = $null
            blockPageHost = $blockPageHost
            blockPageUrl  = $blockPageUrl
            filterVendor  = $filterVendor
        }
    }

    # ---- Did the server's reply get cut off mid-flight? -----------------
    # A reset already names itself 'filtered'. Re-probe at most three silent
    # failures, with a 4s raw-flight budget per host.
    $silentRows = @($results | Where-Object { $_.status -eq 'handshake-fail' })
    $rawProbed = 0
    foreach ($row in $silentRows) {
        if ($rawProbed -ge 3) { break }
        $rawProbed++
        $flight = Test-RawFlight -Domain $row.domain
        $row.rawBytes = $flight.rawBytes
        $row.serverMessages = $flight.messages
        if ($flight.handshake -and -not $flight.complete -and -not $flight.alert) {
            $row.status = 'truncated'
            $row.failureKind = 'truncated'
            $row.detail = "Part of the server's reply arrived ($($flight.rawBytes) bytes), then the rest was dropped. A firewall or web filter is cutting off the handshake."
        }
        elseif ($null -ne $flight.rawBytes -and $flight.rawBytes -eq 0) {
            $row.failureKind = 'dropped'
            $row.detail = 'The TCP connection opened, but no TLS reply arrived. A firewall or web filter may be dropping the handshake.'
        }
    }

    # ---- Identify the filter behind the block --------------------------
    # A silent drop or truncated flight can be the same filter as a reset.
    # Port 80 is deliberate - that filter often answers plain HTTP with its
    # own block page, which is where the vendor name lives. Sample three hosts.
    $filteredRows = @($results | Where-Object {
        $_.status -eq 'filtered' -or $_.status -eq 'truncated' -or
        ($_.status -eq 'handshake-fail' -and $_.failureKind -eq 'dropped')
    })
    $probed = 0
    foreach ($row in $filteredRows) {
        if ($probed -ge 3) { break }
        $probed++
        $signal = Get-FilterBlockSignal -Domain $row.domain
        $row.blockPageHost = $signal.blockPageHost
        $row.blockPageUrl  = $signal.blockPageUrl
        $row.filterVendor  = $signal.filterVendor
    }

    # ---- A block page served over HTTPS is a category block ------------
    # Some filters block a category by answering the handshake with a cert
    # they mint themselves, only so the browser can show the block page. That
    # reads as 'intercepted', but nothing is being decrypted and the fix is a
    # category exception, not an SSL-decryption exemption. Field: Armstrong IL
    # 2026-09-28 - the FortiGate served a 2-day cert for secure.logmein.com
    # (FortiGuard category "Remote Access", 403 block page on port 80) while
    # every other host carried a genuine public cert. Tell them apart the same
    # way as above: plain HTTP to the host returns the vendor's block page (a
    # 4xx, or a redirect to another host), where a decrypting-but-allowing
    # middlebox passes port 80 through to the real site.
    $interceptedRows = @($results | Where-Object { $_.status -eq 'intercepted' })
    $probedIntercepted = 0
    foreach ($row in $interceptedRows) {
        if ($probedIntercepted -ge 3) { break }
        $probedIntercepted++
        $signal = Get-FilterBlockSignal -Domain $row.domain
        # The vendor can come from the block page itself or from the cert the
        # middlebox minted for this host (issuer O=Fortinet at Armstrong).
        if (-not $signal.filterVendor) {
            $issuerText = ("$($row.issuer) $($row.issuerOrg)").ToLower()
            foreach ($v in $FilterVendorPatterns) {
                if ($issuerText -match $v.pattern) { $signal.filterVendor = $v.name; break }
            }
        }
        $isBlockPage = $signal.filterVendor -and ($signal.blockPageHost -or ($signal.httpStatus -ge 400))
        if ($isBlockPage) {
            $row.status        = 'filtered'
            $row.failureKind   = 'block-page'
            $row.blockPageHost = $signal.blockPageHost
            $row.blockPageUrl  = $signal.blockPageUrl
            $row.filterVendor  = $signal.filterVendor
        }
    }

    # Distinct vendor identities, same role as interceptorIssuers: give the
    # venue's IT team an unambiguous pointer to the box holding the policy.
    $filterVendors = @(
        $results | Where-Object { $_.filterVendor } | ForEach-Object { $_.filterVendor } | Select-Object -Unique
    )

    # Who is intercepting -- the distinct issuer identities on substituted
    # certs (e.g. "KSD-FW1-DPI (Kent School District)"). Naming the device
    # gives the district's IT team an unambiguous pointer to their own box.
    $interceptors = @(
        $results | Where-Object { $_.status -eq 'intercepted' } | ForEach-Object {
            if ($_.issuerOrg -and $_.issuerCn -ne $_.issuerOrg) { "$($_.issuerCn) ($($_.issuerOrg))" }
            elseif ($_.issuerCn) { $_.issuerCn }
            else { $_.issuer }
        } | Where-Object { $_ } | Select-Object -Unique
    )

    [ordered]@{
        results            = @($results)
        interceptorIssuers = $interceptors
        filterVendors      = $filterVendors
    } | ConvertTo-Json -Depth 5 -Compress
}
catch {
    [ordered]@{
        error   = $true
        message = $_.Exception.Message
        script  = 'Test-TlsInspection.ps1'
    } | ConvertTo-Json -Compress
}
