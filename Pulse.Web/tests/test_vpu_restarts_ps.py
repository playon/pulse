"""Replay VPU log markers through the real restart collector in pwsh.

This exercises the cross-platform log reader, not Windows findstr or live
process detection. The collector still needs fleet PowerShell 5.1 validation.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

APP = Path(__file__).resolve().parents[1] / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))
import main

SCRIPT = APP.parent / "scripts" / "Get-VpuRestarts.ps1"
PWSH = shutil.which("pwsh") or shutil.which("powershell")


def session(minute, fatal=None, close=None, goodbye=False, end=True,
            driver="446.14", first_frame=True):
    stamp = f"2026-09-28 08:{minute:02d}:00"
    lines = [f"Info | {stamp} | START NEW LOG SESSION Version: 5.37.2",
             f"Info | {stamp} | Installed NVIDIA driver: {driver}"]
    if first_frame:
        lines.append(f"Info | {stamp} | Received first frame")
    if fatal:
        lines.append(f"Fatal | {stamp} | CUDA | file(1) | function | {fatal}")
    if close:
        lines.append(f'Info | {stamp} | CloseUnit Command from Agent Reason: "{close}"')
    if goodbye:
        lines.append(f"Info | {stamp} | Goodbye!!!")
    if end:
        lines.append(f"Info | {stamp} | END LOG SESSION")
    return "\n".join(lines) + "\n"


class VpuRestartsSource(unittest.TestCase):
    def test_collector_is_ascii(self):
        SCRIPT.read_bytes().decode("ascii")


@unittest.skipUnless(PWSH, "PowerShell isn't installed")
class VpuRestartsReplay(unittest.TestCase):
    def collect(self, files, **kwargs):
        with tempfile.TemporaryDirectory(prefix="pulse-restart-log-") as folder:
            for name, text in files.items():
                Path(folder, name).write_text(text, encoding="ascii")
            args = [PWSH, "-NoProfile", "-NonInteractive", "-File", str(SCRIPT),
                    "-LogDir", folder, "-AsOf", "2026-09-28 09:00:00"]
            for key, value in kwargs.items():
                args.extend([f"-{key}", str(value)])
            out = subprocess.run(args, capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        result = json.loads(out.stdout)
        self.assertFalse(result.get("error"), result)
        return result

    def test_tecumseh_logs_reach_readiness(self):
        log = "".join(session(m, fatal="cudaErrorInvalidPtx") for m in (51, 53, 55))
        result = self.collect({"VPU_20260928.log": log})
        self.assertEqual(result["sessionsInWindow"], 3)
        self.assertEqual(result["sessions"][0]["startedMinutesAgo"], 9.0)
        self.assertTrue(all(s["firstFrame"] and s["ended"] for s in result["sessions"]))
        self.assertTrue(all(s["fatalCount"] == 1 for s in result["sessions"]))
        dash = main._build_dashboard({}, {}, {}, {}, vpu_restarts=result)
        found = [f for f in dash["findings"] if f["code"] == "vpu-restart-loop"]
        self.assertEqual(found[0]["cause"], "driver-too-old")
        self.assertEqual(dash["readiness"]["status"], "FAIL")

    def test_new_driver_clean_exit_is_recovered(self):
        log = "".join(session(m, fatal="cudaErrorInvalidPtx") for m in (51, 53, 55))
        log += session(58, driver="536.67", goodbye=True)
        result = self.collect({"VPU_20260928.log": log})
        found = main._vpu_restart_findings(result)
        self.assertEqual(found[0]["code"], "vpu-restarts-recent")
        self.assertEqual(main._compute_readiness(found)["status"], "WARN")

    def test_clean_and_deliberate_exits_do_not_form_a_loop(self):
        log = session(20, goodbye=True)
        log += session(30, close="AgnetGui: restart VPU button was clicked")
        log += session(40, close="Watchdog - As not in event, close App")
        log += session(50, goodbye=True)
        result = self.collect({"VPU_20260928.log": log})
        self.assertEqual(main._vpu_restart_findings(result), [])

    def test_tags_across_files_and_bounded_session_output(self):
        first = session(30, end=False)
        first += "Info | 2026-09-28 08:31:00 | no new debayer thread entries\n"
        first += "Info | 2026-09-28 08:31:01 | Found camera data path problem\n"
        later = "".join(session(m) for m in (40, 50, 55))
        result = self.collect({"VPU_20260928_1.log": first, "VPU_20260928_2.log": later})
        self.assertTrue(result["sessions"][0]["ended"])
        self.assertEqual(result["sessions"][0]["tags"], ["debayer-stall", "camera-datapath"])
        limited = self.collect({"VPU_20260928.log": first + later}, MaxSessions=2)
        self.assertEqual(limited["sessionsInWindow"], 4)
        self.assertEqual(len(limited["sessions"]), 2)
        self.assertEqual(limited["sessions"][0]["startedMinutesAgo"], 10.0)

    def test_empty_log_directory_is_not_a_collector_error(self):
        result = self.collect({})
        self.assertFalse(result["logsFound"])
        self.assertEqual(result["sessions"], [])
        self.assertEqual(main._vpu_restart_findings(result), [])


if __name__ == "__main__":
    unittest.main()
