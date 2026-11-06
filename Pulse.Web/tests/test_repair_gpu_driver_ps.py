"""Repair-GpuDriver.ps1's status file, run in PowerShell.

Pulse runs the repair detached and learns everything from the status file the
script writes (gpu_job.py reads it). This runs the script's own Set-Stage /
Write-RunStatus / Emit functions in pwsh and checks the file carries the
fields gpu_job relies on, ends at stage 'done' with the result, and that
stdout still gets exactly one JSON line (the noisy-stdout rule). Skipped
without pwsh (CI's ubuntu runner has it).
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "scripts", "Repair-GpuDriver.ps1")
PWSH = shutil.which("pwsh") or shutil.which("powershell")


def _function(name):
    with open(SCRIPT, encoding="ascii") as fh:
        text = fh.read()
    m = re.search(r"^function " + re.escape(name) + r"\b.*?^}\r?\n", text, re.S | re.M)
    if not m:
        raise AssertionError(f"{name} not found in {SCRIPT}")
    return m.group(0)


@unittest.skipUnless(PWSH, "PowerShell isn't installed")
class StatusFile(unittest.TestCase):
    def run_ps(self, body, status_path):
        prelude = (
            f"$StatusPath = '{status_path}'\n$RunId = 'run42'\n$Kind = 'install'\n$Reinstall = 0\n"
            "$t0 = Get-Date\n$script:startedEpoch = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()\n"
            "$installerName = 'x.exe'\n$steps = New-Object System.Collections.ArrayList\n"
            "$script:runStage = 'checking'\n$script:runMessage = ''\n"
            "$script:bytesDone = $null\n$script:bytesTotal = $null\n"
            "$stagesSeen = New-Object System.Collections.ArrayList\n"
        )
        code = prelude + "".join(_function(n) for n in ("Add-Step", "Write-RunStatus", "Set-Stage", "Emit")) + body
        out = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-Command", code],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout

    def test_stage_then_result(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sub", "gpu-driver-status.json")
            self.run_ps("Set-Stage 'checking' 'Checking.'\n", path)
            with open(path, encoding="utf-8-sig") as fh:
                rec = json.load(fh)
            self.assertEqual(rec["stage"], "checking")
            self.assertEqual(rec["runId"], "run42")
            self.assertEqual(rec["stagesSeen"], ["checking"])
            self.assertIsInstance(rec["pid"], int)
            self.assertIsInstance(rec["updatedEpoch"], int)
            self.assertIsNone(rec["result"])

            out = self.run_ps(
                "Set-Stage 'checking' 'Checking.'\nSet-Stage 'checking' 'Again.'\n"
                "Set-Stage 'downloading' 'Downloading.'\n"
                "$script:bytesDone = 10; $script:bytesTotal = 100; Write-RunStatus $null\n"
                "Add-Step 'download driver' $true '1 MB'\n"
                "Emit 'installed' 'Done.' 'no-driver' 'ok' 0\n", path)
            lines = [l for l in out.splitlines() if l.strip()]
            self.assertEqual(len(lines), 1, out)
            self.assertEqual(json.loads(lines[0])["status"], "installed")
            with open(path, encoding="utf-8-sig") as fh:
                rec = json.load(fh)
            self.assertEqual(rec["stage"], "done")
            self.assertEqual(rec["stagesSeen"], ["checking", "downloading"])
            self.assertEqual(rec["result"]["status"], "installed")
            self.assertEqual(rec["result"]["steps"][0]["step"], "download driver")
            self.assertEqual((rec["bytesDone"], rec["bytesTotal"]), (10, 100))
            self.assertFalse(os.path.exists(path + ".tmp"))

    def test_no_status_path_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            out = self.run_ps("$StatusPath = ''\nSet-Stage 'checking' 'x'\nEmit 'not-needed' 'ok' 'ok' 'ok' $null\n",
                              os.path.join(d, "unused.json"))
            self.assertEqual(os.listdir(d), [])
            self.assertEqual(json.loads(out.strip())["status"], "not-needed")


if __name__ == "__main__":
    unittest.main()
