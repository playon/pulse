#Requires -Version 5.1
<#
.SYNOPSIS
    Runs several Pulse collectors inside ONE PowerShell process.
.DESCRIPTION
    Starting powershell.exe is most of what a collector costs: measured on
    vpu-home, a monitor pass that started one process per collector used
    8 CPU-seconds for 11 collectors. This runner starts once and invokes
    each collector in turn in a shared runspace, so the .NET and PowerShell
    start-up is paid once per batch instead of once per script.

    Used by the unattended monitor only (powershell.py configure_background
    batch=True). The interactive app still runs one process per collector.

    Input: -RequestFile, a UTF-8 JSON array of
        { "id": "...", "script": "Get-X.ps1", "args": { "Name": "value" }, "timeoutSec": 30 }
    Output (stdout, one line): a JSON array of
        { "id": "...", "status": "ok"|"timeout"|"error"|"skipped",
          "ms": 123, "output": "<the script's stdout>", "error": "..." }

    Collectors run one at a time on purpose: the monitor must stay light,
    and wall time is not what it optimizes. A collector that overruns its
    timeout is stopped and the runspace replaced, so nothing it left behind
    reaches the next one. Past -DeadlineSec the remaining collectors are
    skipped rather than started.

    ASCII ONLY (CLAUDE.md PowerShell 5.1 rules). Unwanted returns go to $null.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RequestFile,
    [int]$DeadlineSec = 230
)

$ErrorActionPreference = 'Stop'
$scriptsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$results = New-Object 'System.Collections.Generic.List[object]'
$clock = [Diagnostics.Stopwatch]::StartNew()

function New-CollectorRunspace {
    $iss = [System.Management.Automation.Runspaces.InitialSessionState]::CreateDefault()
    $iss.ExecutionPolicy = [Microsoft.PowerShell.ExecutionPolicy]::Bypass
    $rs = [System.Management.Automation.Runspaces.RunspaceFactory]::CreateRunspace($iss)
    $rs.Open()
    return $rs
}

try {
    # 5.1's ConvertFrom-Json emits a JSON array as ONE object, so @(...) would
    # wrap it into a one-element array (pwsh 7 enumerates it). Copy it out
    # with foreach, which enumerates on both.
    $parsed = Get-Content -LiteralPath $RequestFile -Raw -Encoding UTF8 | ConvertFrom-Json
    $requests = New-Object 'System.Collections.Generic.List[object]'
    foreach ($r in $parsed) { $requests.Add($r) }
} catch {
    $line = [pscustomobject]@{ id = $null; status = 'error'; ms = 0; output = ''; error = 'bad request file: ' + $_.Exception.Message }
    ConvertTo-Json -InputObject @($line) -Depth 3 -Compress
    exit 0
}

$runspace = New-CollectorRunspace

foreach ($req in $requests) {
    $entry = [pscustomobject]@{ id = $req.id; status = 'ok'; ms = 0; output = ''; error = $null }
    if ($clock.Elapsed.TotalSeconds -ge $DeadlineSec) {
        $entry.status = 'skipped'
        $entry.error = 'batch deadline reached before this collector started'
        $results.Add($entry)
        continue
    }

    $path = Join-Path $scriptsDir ([string]$req.script)
    if (-not (Test-Path -LiteralPath $path)) {
        $entry.status = 'error'
        $entry.error = 'Script not found: ' + $req.script
        $results.Add($entry)
        continue
    }

    $timeoutMs = 30000
    if ($req.timeoutSec) { $timeoutMs = [int]$req.timeoutSec * 1000 }
    $t0 = $clock.ElapsedMilliseconds
    $ps = [System.Management.Automation.PowerShell]::Create()
    $ps.Runspace = $runspace
    $null = $ps.AddCommand($path)
    if ($req.args) {
        foreach ($p in $req.args.PSObject.Properties) { $null = $ps.AddParameter($p.Name, $p.Value) }
    }
    # Input must be its own, already-completed collection: an open input
    # collection keeps the script waiting for pipeline input forever (it hung
    # every collector on vpu-home when output doubled as input).
    $noInput = New-Object 'System.Management.Automation.PSDataCollection[psobject]'
    $noInput.Complete()
    $buffer = New-Object 'System.Management.Automation.PSDataCollection[psobject]'
    try {
        $async = $ps.BeginInvoke($noInput, $buffer)
        if ($async.AsyncWaitHandle.WaitOne($timeoutMs)) {
            $null = $ps.EndInvoke($async)
        } else {
            $entry.status = 'timeout'
            $entry.error = 'Timeout after ' + [int]($timeoutMs / 1000) + 's'
            try { $ps.Stop() } catch {}
        }
    } catch {
        $entry.status = 'error'
        $entry.error = $_.Exception.Message
    }

    $lines = New-Object 'System.Collections.Generic.List[string]'
    foreach ($o in $buffer) { if ($null -ne $o) { $lines.Add([string]$o) } }
    $entry.output = [string]::Join("`n", $lines.ToArray())
    if ($entry.status -eq 'ok' -and $ps.Streams.Error.Count -gt 0 -and -not $entry.output) {
        $entry.status = 'error'
        $entry.error = [string]$ps.Streams.Error[0]
    }
    $entry.ms = $clock.ElapsedMilliseconds - $t0
    $ps.Dispose()
    $results.Add($entry)

    if ($entry.status -eq 'timeout') {
        # A stopped pipeline can leave the runspace busy or half-torn; start clean.
        try { $runspace.Dispose() } catch {}
        $runspace = New-CollectorRunspace
    }
}

try { $runspace.Dispose() } catch {}
ConvertTo-Json -InputObject $results.ToArray() -Depth 3 -Compress
