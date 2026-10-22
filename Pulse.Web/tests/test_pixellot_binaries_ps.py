"""Test-PixellotBinaries.ps1's user-PATH expansion, run in PowerShell.

As SYSTEM (the fleet monitor) the collector reads each logged-in user's Path
from the registry, unexpanded, and expands it with that user's variables:
expanded as SYSTEM, %USERPROFILE% would be SYSTEM's profile (De La Salle CA,
2026-10-16: 22 DLLs read as missing). ConvertTo-UserPathDirs does the
expansion and is pure, so this runs it in pwsh on any OS. The registry read
around it needs Windows and isn't tested here. Skipped without pwsh (CI's
ubuntu runner has it).
"""

import json
import os
import re
import shutil
import subprocess
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "scripts", "Test-PixellotBinaries.ps1")
PWSH = shutil.which("pwsh") or shutil.which("powershell")


def _function(name):
    with open(SCRIPT, encoding="ascii") as fh:
        text = fh.read()
    m = re.search(r"^function " + re.escape(name) + r"\b.*?^}\n", text, re.S | re.M)
    if not m:
        raise AssertionError(f"{name} not found in {SCRIPT}")
    return m.group(0)


@unittest.skipUnless(PWSH, "PowerShell isn't installed")
class UserPathDirs(unittest.TestCase):
    def run_ps(self, raw, vars_):
        code = _function("ConvertTo-UserPathDirs") + (
            "$vars = @{}\n"
            + "".join(f"$vars['{k}'] = '{v}'\n" for k, v in vars_.items())
            + f"$r = ConvertTo-UserPathDirs '{raw}' $vars\n"
            + "ConvertTo-Json -InputObject @($r) -Compress\n")
        out = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-Command", code],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def test_expands_with_the_users_own_variables(self):
        dirs = self.run_ps(r"%USERPROFILE%\AppData\Local\Pixellot;C:\Pixellot\dependencies\opencv\bin",
                           {"USERPROFILE": r"C:\Users\pixellot"})
        self.assertEqual(dirs, [r"C:\Users\pixellot\AppData\Local\Pixellot",
                                r"C:\Pixellot\dependencies\opencv\bin"])

    def test_variable_names_ignore_case_and_unknown_ones_stay(self):
        dirs = self.run_ps(r"%LocalAppData%\x;%NOT_A_VAR_PV49%\y",
                           {"LOCALAPPDATA": r"C:\Users\p\AppData\Local"})
        self.assertEqual(dirs, [r"C:\Users\p\AppData\Local\x", r"%NOT_A_VAR_PV49%\y"])

    def test_blanks_quotes_and_repeats(self):
        dirs = self.run_ps(r';"C:\a" ; C:\a;;C:\b;', {})
        self.assertEqual(dirs, [r"C:\a", r"C:\b"])

    def test_nothing(self):
        self.assertEqual(self.run_ps("", {}), [])


@unittest.skipUnless(PWSH, "PowerShell isn't installed")
class PopupOccurrences(unittest.TestCase):
    def test_group_preserves_each_occurrence_and_title(self):
        import tempfile
        with open(SCRIPT, encoding="ascii") as fh:
            source = fh.read()
        block = source.split("    # -- Loader error dialogs", 1)[1].split("\n", 1)[1].split(
            "    # -- Is the running VPU.exe", 1)[0]
        # Run the real grouping block; only Windows' event source is replaced.
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("CEFWorker.exe", "VPU.exe"):
                open(os.path.join(tmp, name), "wb").close()
            escaped = tmp.replace("'", "''")
            code = f"$PIX_BIN = '{escaped}'; $DaysBack = 7\n" + (
                "$TS = 'yyyy-MM-ddTHH:mm:sszzz'; $INV = [Globalization.CultureInfo]::InvariantCulture\n"
                "function Get-WinEvent {\n"
                "foreach ($second in @(4, 8)) { [pscustomobject]@{\n"
                "Message = 'Application popup: CEFWorker.exe - Application Error: The application was unable to start correctly (0xc0000142).';\n"
                "TimeCreated = (Get-Date).Date.AddHours(11).AddSeconds($second) } }\n"
                "[pscustomobject]@{ Message = 'Application popup: VPU.exe - System Error: libcef.dll was not found'; TimeCreated = (Get-Date) }\n"
                "}\n") + block + "\nConvertTo-Json -InputObject $popupsOut -Depth 5 -Compress\n"
            run = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-Command", code],
                                 capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stderr)
        popups = json.loads(run.stdout)
        cef = next(p for p in popups if p["exe"] == "CEFWorker.exe")
        self.assertEqual(cef["count"], 2)
        self.assertEqual(len(cef["times"]), 2)
        self.assertNotEqual(cef["times"][0], cef["times"][1])
        self.assertEqual(cef["title"], "Application Error")
        vpu = next(p for p in popups if p["exe"] == "VPU.exe")
        self.assertEqual(vpu["title"], "System Error")
        self.assertEqual(vpu["dll"], "libcef.dll")


if __name__ == "__main__":
    unittest.main()
