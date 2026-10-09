"""The Find the code endpoints, in the demo simulator.

A console ScoreConnect already reads is only scanned when the tech confirmed
(force); a console that is silent or sends the wrong format is scanned at
once. Calls the endpoint functions directly (no HTTP client needed).

    cd Pulse.Web && .venv/bin/python -m unittest discover -s tests
"""

import asyncio
import os
import sys
import unittest

_APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import main  # noqa: E402


class _Req:
    def __init__(self, body):
        self._body = body

    async def json(self):
        return self._body


class ScanEndpoints(unittest.TestCase):
    def setUp(self):
        self._saved = (main.DEMO_MODE, main._demo_sc3, main._sc3_scan, os.environ.get("PULSE_DEMO_SC"))
        main.DEMO_MODE = True
        main._demo_sc3 = None
        main._sc3_scan = {"state": "idle"}

    def tearDown(self):
        main.DEMO_MODE, main._demo_sc3, main._sc3_scan, env = self._saved
        if env is None:
            os.environ.pop("PULSE_DEMO_SC", None)
        else:
            os.environ["PULSE_DEMO_SC"] = env

    def scenario(self, name):
        os.environ["PULSE_DEMO_SC"] = name
        main._demo_sc3 = None

    def test_plan_reports_what_the_console_is_doing(self):
        for scenario, expected in (("healthy", "reading"), ("wrong-format", "wrong"), ("no-data", "none")):
            self.scenario(scenario)
            out = asyncio.run(main.api_sc3_scan_get(plan=1))
            self.assertEqual(out["console"], expected, scenario)
            self.assertTrue(out["plan"]["sports"], scenario)

    def test_a_console_already_read_is_refused_without_confirmation(self):
        self.scenario("healthy")
        out = asyncio.run(main.api_sc3_scan_start(_Req({"confirm": True, "sport": None})))
        self.assertTrue(out["error"])
        self.assertTrue(out["alreadyReading"])
        self.assertEqual(main._sc3_scan["state"], "idle")

    def test_the_old_confirm_flag_alone_is_not_enough_for_a_read_console(self):
        self.scenario("healthy")
        out = asyncio.run(main.api_sc3_scan_start(_Req({"confirm": True, "force": False})))
        self.assertTrue(out.get("alreadyReading"))

    def test_without_confirm_nothing_is_tried(self):
        self.scenario("wrong-format")
        out = asyncio.run(main.api_sc3_scan_start(_Req({"sport": None})))
        self.assertTrue(out["error"])
        self.assertFalse(out.get("alreadyReading"))
        self.assertEqual(main._sc3_scan["state"], "idle")


if __name__ == "__main__":
    unittest.main()
