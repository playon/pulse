#Requires -Version 5.1
<#
.SYNOPSIS
    Resolves Pixellot domains via the configured DNS server AND via Google DNS
    (8.8.8.8) so a misconfigured school resolver can be detected.
.DESCRIPTION
    Per Pixellot Troubleshooting Tips PDF #10, the standard DNS triage is to
    compare `nslookup www.pixellot.tv` (system resolver) with
    `nslookup www.pixellot.tv 8.8.8.8`. If Google resolves but the system
    doesn't, the school's internal DNS is blocking Pixellot infrastructure.

    For each test host the script returns:
        {
          host: <fqdn>,
          system:  { resolvedTo, status, resolutionMs, error },
          google:  { resolvedTo, status, resolutionMs, error },
          discrepancy: 'system-blocked' | 'google-blocked' | 'mismatch' | null
        }
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

# Hosts that must resolve consistently across resolvers. Includes the
# specific "www" hosts called out in the PDF plus the apex domains we
# already test elsewhere.
$testHosts = @(
    'www.pixellot.tv',
    'pixellot.tv',
    'software.pixellot.tv',
    'nfhsnetwork.com'
)

# One lookup, as a scriptblock so each runs in its own runspace (see below).
$resolveOnce = {
    param(
        [string]$Name,
        [string]$Server = $null   # null = use the system resolver
    )
    $out = [ordered]@{
        resolvedTo   = $null
        status       = 'fail'
        resolutionMs = $null
        error        = $null
    }
    try {
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $params = @{
            Name        = $Name
            Type        = 'A'
            DnsOnly     = $true
            ErrorAction = 'Stop'
        }
        if ($Server) { $params.Server = $Server }
        $dns = Resolve-DnsName @params
        $sw.Stop()
        $out.resolutionMs = [math]::Round($sw.Elapsed.TotalMilliseconds, 1)

        $ipRecord = $dns | Where-Object { $_.QueryType -eq 'A' } | Select-Object -First 1
        if ($ipRecord) {
            $out.resolvedTo = $ipRecord.IPAddress
            $out.status = 'pass'
        }
        else {
            $any = $dns | Select-Object -First 1
            if ($any) {
                if ($any.IPAddress) { $out.resolvedTo = $any.IPAddress; $out.status = 'pass' }
                elseif ($any.NameHost) { $out.resolvedTo = $any.NameHost; $out.status = 'pass' }
            }
        }
    }
    catch {
        if ($sw -and $sw.IsRunning) { $sw.Stop() }
        if ($sw) { $out.resolutionMs = [math]::Round($sw.Elapsed.TotalMilliseconds, 1) }
        $out.error = $_.Exception.Message
    }
    return $out
}

try {
    # Collect raw resolution results only. The discrepancy classification
    # (system-blocked / redirect / benign) lives in the Python backend
    # (_classify_dns_row) so the rule is in one tested place -- telling a real
    # DNS redirect from benign CDN/GeoDNS load balancing needs public-vs-
    # private IP reasoning that doesn't belong in the collector.
    # $host is a PowerShell automatic variable -- use a different name.
    #
    # All lookups run at once. They used to run one after another, and a
    # resolver that drops packets (a venue blocking 8.8.8.8 is common) made each
    # one wait out Windows' DNS retry timeouts: four blocked lookups back to
    # back ran past the 30 s collector timeout and held the whole first-launch
    # sweep. In parallel the worst case is one wait, and $deadline caps it.
    $deadline = [DateTime]::UtcNow.AddSeconds(15)
    $pool = [runspacefactory]::CreateRunspacePool(1, 8)
    $pool.Open()
    $jobs = foreach ($testHost in $testHosts) {
        foreach ($server in @($null, '8.8.8.8')) {
            $ps = [powershell]::Create()
            $ps.RunspacePool = $pool
            [void]$ps.AddScript($resolveOnce.ToString()).AddArgument($testHost).AddArgument($server)
            [pscustomobject]@{ Host = $testHost; Google = [bool]$server; Ps = $ps; Handle = $ps.BeginInvoke() }
        }
    }
    function Get-JobResult($job) {
        $left = [int][Math]::Max(0, ($deadline - [DateTime]::UtcNow).TotalMilliseconds)
        if ($job.Handle.AsyncWaitHandle.WaitOne($left)) {
            $r = $job.Ps.EndInvoke($job.Handle)
            if ($r -and $r.Count -gt 0) { return $r[0] }
        }
        return [ordered]@{ resolvedTo = $null; status = 'fail'; resolutionMs = $null; error = 'lookup did not finish in 15 seconds' }
    }
    $results = foreach ($testHost in $testHosts) {
        $sys = $jobs | Where-Object { $_.Host -eq $testHost -and -not $_.Google } | Select-Object -First 1
        $goog = $jobs | Where-Object { $_.Host -eq $testHost -and $_.Google } | Select-Object -First 1
        [ordered]@{
            host   = $testHost
            system = Get-JobResult $sys
            google = Get-JobResult $goog
        }
    }

    [ordered]@{
        googleServer = '8.8.8.8'
        results      = @($results)
    } | ConvertTo-Json -Depth 5 -Compress
}
catch {
    [ordered]@{
        error   = $true
        message = $_.Exception.Message
        script  = 'Test-DnsResolution.ps1'
    } | ConvertTo-Json -Compress
}
