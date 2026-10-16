#!/usr/bin/env python3
"""Run every Pulse read-only collector on the test VPU over SSH and grade the output.

Mirrors how the app itself runs collectors (powershell.py):
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File <script> [-Arg value]
with the same args and timeouts main.py uses, then applies the same tolerant
JSON extraction. The point: catch scripts that pass under pwsh/macOS demo mode
but break on the fleet image's real Windows PowerShell 5.1.

Usage:
    python3 tools/vpu-smoke/sweep.py --outdir /path/to/results [--host vpu-test]
    python3 tools/vpu-smoke/sweep.py --only Get-AudioDevices.ps1,Get-GpuInfo.ps1

Raw stdout/stderr land as files under --outdir and are NOT printed. The
console summary (safe for chat) shows per-script status, duration, size and a
redacted error head. Inspect payloads with redact.py, never by cat-ing raw files.

Exit code: number of scripts that did not come back "ok" (capped at 99).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from redact import redact  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_SCRIPTS_DIR = REPO / "Pulse.Web" / "scripts"
REMOTE_ROOT = "C:/PulseSmoke"
REMOTE_SCRIPTS = r"C:\PulseSmoke\scripts"

SSH_OPTS = [
    "-o", "ControlMaster=auto",
    "-o", "ControlPath=~/.ssh/cm-%r@%h-%p",
    "-o", "ControlPersist=600",
    "-o", "ConnectTimeout=15",
]

# (script, args, app_timeout_seconds) — mirrored from main.py's run_ps calls.
# Read-only collectors only. Deliberately excluded:
#   Test-CameraVideo.ps1     needs live camera IPs (run manually if cameras exist)
#   Start-NetworkCapture.ps1 starts a packet capture (manual)
#   Set-*/Restart-*/Reboot-*/Install-*/Invoke-RepairTool.ps1  actions (B7, manual)
#   Wait-AndLaunch.ps1       launcher helper, not a collector
#   _AudioInterop.ps1        dot-sourced library
MANIFEST: list[tuple[str, dict, int]] = [
    ("Get-SystemIdentity.ps1", {}, 30),
    ("Get-Hardware.ps1", {}, 30),
    ("Get-Performance.ps1", {}, 30),
    ("Get-PerfSample.ps1", {}, 15),
    ("Get-NetworkConfig.ps1", {}, 15),
    ("Get-NicAdapters.ps1", {}, 30),
    ("Get-Services.ps1", {}, 30),
    ("Get-DiskHealth.ps1", {}, 15),
    ("Get-EventLogs.ps1", {"HoursBack": 48, "Level": "all"}, 30),
    ("Get-RebootHistory.ps1", {"HoursBack": 168}, 30),
    ("Search-PixellotLogs.ps1", {"HoursBack": 24}, 30),
    ("Get-ScoreConnectStatus.ps1", {"BaseUrl": "http://localhost:5000"}, 20),
    ("Get-ScoreConnectLive.ps1", {"BaseUrl": "http://localhost:5000"}, 15),
    ("Get-ScoreLinkStatus.ps1", {}, 15),
    ("Get-Sc3InstallStatus.ps1", {}, 10),
    ("Get-PixellotConfig.ps1", {}, 20),
    ("Get-CalibrationStatus.ps1", {}, 15),
    ("Get-PixellotDependencies.ps1", {}, 10),
    ("Test-PixellotInstallState.ps1", {}, 15),
    ("Get-InstalledSoftware.ps1", {}, 30),
    ("Test-NetworkDomains.ps1", {}, 20),
    ("Test-NetworkPorts.ps1", {}, 45),
    ("Test-NtpDrift.ps1", {}, 15),
    ("Get-NtpPeers.ps1", {}, 15),
    ("Test-LocalNetwork.ps1", {}, 20),
    ("Test-DnsResolution.ps1", {}, 30),
    ("Get-NetworkHealth.ps1", {}, 10),
    ("Test-Traceroute.ps1", {"Target": "pixellot.tv", "MaxHops": 20}, 60),
    ("Get-GpuInfo.ps1", {}, 15),
    ("Get-WifiAdapters.ps1", {}, 10),
    ("Test-TlsInspection.ps1", {}, 60),
    ("Get-CameraExpectations.ps1", {}, 10),
    ("Get-S1Cameras.ps1", {}, 15),
    ("Get-AudioDevices.ps1", {}, 15),
    ("Get-UsersAndDomains.ps1", {}, 20),
    ("Get-Peripherals.ps1", {}, 15),
]

# SSH connection + remote PowerShell startup overhead on top of the app timeout.
SSH_OVERHEAD = 40


def extract_json(text: str):
    """Same tolerant extraction as app/powershell.py:_extract_json."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        pass
    for line in reversed(text.splitlines()):
        candidate = line.strip()
        if candidate[:1] in ("{", "["):
            try:
                return json.loads(candidate, strict=False)
            except json.JSONDecodeError:
                continue
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1], strict=False)
        except json.JSONDecodeError:
            pass
    return None


def ssh(host: str, command: str, timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["ssh", *SSH_OPTS, host, command],
        capture_output=True, timeout=timeout,
    )


def deploy(host: str, scripts_dir: pathlib.Path) -> None:
    print(f"deploying {scripts_dir} -> {host}:{REMOTE_ROOT} ...", flush=True)
    ssh(host, f"Remove-Item -Recurse -Force '{REMOTE_SCRIPTS}' -ErrorAction SilentlyContinue; "
              f"New-Item -ItemType Directory -Force '{REMOTE_ROOT}\\scripts' | Out-Null", 60)
    subprocess.run(
        ["scp", *SSH_OPTS, "-q", "-r", f"{scripts_dir}/.", f"{host}:{REMOTE_ROOT}/scripts/"],
        check=True, timeout=120,
    )
    count = ssh(host, f"(Get-ChildItem '{REMOTE_SCRIPTS}' -Filter *.ps1).Count", 30)
    print(f"deployed; remote script count = {count.stdout.decode().strip()}", flush=True)


def run_one(host: str, script: str, args: dict, app_timeout: int, outdir: pathlib.Path) -> dict:
    cmd = (f"powershell.exe -NoProfile -ExecutionPolicy Bypass "
           f"-File {REMOTE_SCRIPTS}\\{script}")
    for key, value in args.items():
        cmd += f" -{key} {value}"

    t0 = time.monotonic()
    try:
        proc = ssh(host, cmd, app_timeout + SSH_OVERHEAD)
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        proc = exc
        timed_out = True
    ms = (time.monotonic() - t0) * 1000

    stdout = (proc.stdout or b"").decode("utf-8", errors="replace").strip()
    stderr = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
    rc = None if timed_out else proc.returncode

    stem = script.replace(".ps1", "")
    (outdir / f"{stem}.stdout.txt").write_text(stdout, encoding="utf-8")
    if stderr:
        (outdir / f"{stem}.stderr.txt").write_text(stderr, encoding="utf-8")

    parsed = extract_json(stdout)
    if timed_out:
        status, detail = "timeout", f"client timeout after {app_timeout + SSH_OVERHEAD}s"
    elif rc == 255 and not stdout:
        status, detail = "ssh-error", stderr[:160]
    elif not stdout:
        status, detail = "empty", f"exit={rc}; stderr: {stderr[:160]}" if stderr else f"exit={rc}, no stderr"
    elif parsed is None:
        status, detail = "unparseable", stdout[:160].replace("\n", " ")
    elif isinstance(parsed, dict) and parsed.get("error"):
        status, detail = "script-error", str(parsed.get("message", ""))[:160]
    elif stdout[:1] not in ("{", "["):
        status, detail = "ok-noisy", "JSON recovered from noisy stdout"
    else:
        status = "ok"
        detail = stderr[:120] if stderr else ""

    meta = {
        "script": script, "args": args, "status": status, "detail": detail,
        "exit": rc, "durationMs": round(ms), "stdoutBytes": len(stdout),
        "stderrBytes": len(stderr), "appTimeout": app_timeout,
    }
    (outdir / f"{stem}.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="vpu-test")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--only", help="comma-separated script names (skip the rest)")
    ap.add_argument("--no-deploy", action="store_true", help="reuse scripts already on the VPU")
    ap.add_argument("--scripts-dir", default=str(DEFAULT_SCRIPTS_DIR),
                    help="local scripts dir to deploy (e.g. a git-archive snapshot of origin/dev)")
    args = ap.parse_args()

    outdir = pathlib.Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    manifest = MANIFEST
    if args.only:
        wanted = {s.strip() for s in args.only.split(",")}
        manifest = [m for m in MANIFEST if m[0] in wanted]
        missing = wanted - {m[0] for m in manifest}
        if missing:
            print(f"not in manifest: {', '.join(sorted(missing))}", file=sys.stderr)

    if not args.no_deploy:
        deploy(args.host, pathlib.Path(args.scripts_dir))

    results = []
    width = max(len(m[0]) for m in manifest)
    for script, script_args, app_timeout in manifest:
        meta = run_one(args.host, script, script_args, app_timeout, outdir)
        results.append(meta)
        detail = redact(meta["detail"]) if meta["detail"] else ""
        print(f"{script:<{width}}  {meta['status']:<12} {meta['durationMs']:>7}ms "
              f"{meta['stdoutBytes']:>8}B  {detail}", flush=True)

    (outdir / "summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    bad = [r for r in results if r["status"] not in ("ok", "ok-noisy")]
    noisy = [r for r in results if r["status"] == "ok-noisy"]
    print(f"\n{len(results)} run, {len(results) - len(bad)} ok "
          f"({len(noisy)} noisy), {len(bad)} failing")
    if bad:
        print("failing: " + ", ".join(r["script"] for r in bad))
    return min(len(bad), 99)


if __name__ == "__main__":
    sys.exit(main())
