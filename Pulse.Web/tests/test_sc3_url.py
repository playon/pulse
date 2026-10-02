"""SC III's base URL reads "localhost" as 127.0.0.1.

Measured on VPU2 2026-09-29: a fresh process's first request to localhost:5000
took 12-40s and 127.0.0.1:5000 ~80ms, so the ScoreConnect collector (2s
timeout, new PowerShell process per run) called a healthy SC III down.
"""

import os
import re
import sys
import unittest

_WEB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_APP_DIR = os.path.join(_WEB, "app")
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import main  # noqa: E402


class Sc3BaseUrl(unittest.TestCase):
    def test_default_is_loopback_ip(self):
        self.assertEqual(main.sc3_base_url({}), "http://127.0.0.1:5000")
        self.assertEqual(main.SC3_DEFAULT_URL, "http://127.0.0.1:5000")

    def test_saved_localhost_is_rewritten(self):
        # Every settings file written before this change holds this value.
        self.assertEqual(main.sc3_base_url({"scoreConnectUrl": "http://localhost:5000"}), "http://127.0.0.1:5000")
        self.assertEqual(main.sc3_base_url({"scoreConnectUrl": "http://LOCALHOST:5000/"}), "http://127.0.0.1:5000")
        self.assertEqual(main.sc3_base_url({"scoreConnectUrl": "http://localhost"}), "http://127.0.0.1")

    def test_other_hosts_are_left_alone(self):
        for u in ("http://192.168.1.20:5000", "http://localhost.example:5000", "http://127.0.0.1:5001"):
            self.assertEqual(main.sc3_base_url({"scoreConnectUrl": u}), u)

    def test_no_sc3_call_site_reads_the_setting_raw(self):
        with open(os.path.join(_APP_DIR, "main.py"), encoding="utf-8") as f:
            src = f.read()
        raw = [m.start() for m in re.finditer(r'get\("scoreConnectUrl"', src)]
        # Only sc3_base_url itself reads the setting.
        self.assertEqual(len(raw), 1, "read SC III's URL through sc3_base_url()")

    def test_collectors_default_to_loopback_ip(self):
        for name in ("Get-ScoreConnectStatus.ps1", "Get-ScoreConnectLive.ps1", "Install-ScoreConnectIII.ps1"):
            with open(os.path.join(_WEB, "scripts", name), encoding="utf-8") as f:
                self.assertNotRegex(f.read(), r"'http://localhost:5000", name)


if __name__ == "__main__":
    unittest.main()
