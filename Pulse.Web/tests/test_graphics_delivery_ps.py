"""PV-84: run the real log collector and its finding, without Windows APIs.

PowerShell 7 on macOS/Linux exercises parsing, live/zip reads and JSON shape;
this is not a substitute for a Windows PowerShell 5.1 fleet smoke check.
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
import main

PWSH = shutil.which("pwsh") or shutil.which("powershell")
SCRIPT = ROOT / "scripts" / "Get-GraphicsDelivery.ps1"


def log_line(at, module, function, message):
    return f"Info\t| {at:%Y-%m-%d %H:%M:%S}.000 |{module}\t|source.cs(1)\t|{function}\t|{message}\n"


@unittest.skipUnless(PWSH, "PowerShell isn't installed")
class VpuLifecycleCollector(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.logs = Path(self.tmp.name)
        self.at = datetime.now().astimezone().replace(microsecond=0) - timedelta(minutes=10)
        self.agent_name = f"agent_vpu_{self.at:%Y%m%d}_000000.log"
        self.vpu_name = f"VPU_vpu_{self.at:%Y%m%d}_000000.log"
        self.agent = (
            log_line(self.at - timedelta(seconds=15), "vpu_Manager", "KillAllNamedProcesses", "Found 1 instances of vpu")
            + log_line(self.at, "vpu_Manager", "ForceCloseApplication", "Application has exited")
            + log_line(self.at, "PostProcess_Manager", "ForceCloseApplication", "Application has exited")
            + log_line(self.at, "vpu_Manager", "KillAllNamedProcesses", "looking for vpu process to see if needed to be killed")
        )
        self.vpu = log_line(self.at - timedelta(minutes=30), "MAIN", "main", "START NEW LOG SESSION >>> VPU.exe - Version: test")
        (self.logs / self.agent_name).write_text(self.agent, encoding="ascii")
        (self.logs / self.vpu_name).write_text(self.vpu, encoding="ascii")

    def collect(self, *extra):
        run = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File", str(SCRIPT),
                              "-LogDir", str(self.logs), "-ConfigDir", str(self.logs), *extra],
                             text=True, capture_output=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(run.stdout)
        self.assertNotIn("error", result, result)
        return result

    def test_real_collector_to_dashboard_smoke(self):
        context = self.collect()
        self.assertTrue(context["lifecycleReadComplete"])
        self.assertEqual([p["kind"] for p in context["vpuLifecycle"]].count("teardown"), 2)
        self.assertEqual([p["kind"] for p in context["vpuLifecycle"]].count("start"), 1)
        popup_at = self.at + timedelta(seconds=4)
        b = {"now": (self.at + timedelta(minutes=10)).isoformat(), "exes": [],
             "vpuProcesses": [], "popups": [{"exe": "CEFWorker.exe", "title": "Application Error",
             "text": "The application was unable to start correctly (0xc0000142).",
             "count": 1, "first": popup_at.isoformat(), "last": popup_at.isoformat(),
             "times": [popup_at.isoformat()]}]}
        dash = main._build_dashboard({}, {}, {"services": []}, {}, binaries=b, graphics_delivery=context)
        findings = [f for f in dash["findings"] if f["code"].startswith("pixellot-")]
        self.assertEqual([f["code"] for f in findings], ["pixellot-shutdown-popup"])
        self.assertEqual(findings[0]["severity"], "info")
        self.assertIn("0xc0000142", " ".join(findings[0]["details"]))
        self.assertNotEqual(dash["readiness"]["status"], "FAIL")
        # A fresh VPU launch changes the same popup back into a blocker.
        with (self.logs / self.vpu_name).open("a", encoding="ascii") as fh:
            fh.write(log_line(self.at + timedelta(seconds=2), "MAIN", "main", "START NEW LOG SESSION >>> VPU.exe - Version: test"))
        finding = main._binary_findings(b, self.collect())[0]
        self.assertEqual(finding["code"], "pixellot-start-error")

    def test_archived_logs_keep_lifecycle_and_deduplicate_live_copy(self):
        archive = self.logs / "archive"
        archive.mkdir()
        with ZipFile(archive / "log_test.zip", "w") as z:
            z.writestr(self.agent_name, self.agent)
            z.writestr(self.vpu_name, self.vpu)
        live = self.collect()["vpuLifecycle"]
        (self.logs / self.agent_name).unlink()
        (self.logs / self.vpu_name).unlink()
        self.assertEqual(self.collect()["vpuLifecycle"], live)

    def test_exhausted_budget_is_not_complete_shutdown_context(self):
        self.assertFalse(self.collect("-BudgetSeconds", "-1")["lifecycleReadComplete"])


if __name__ == "__main__":
    unittest.main()
