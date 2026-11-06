"""POST /api/gpu-driver/repair only reinstalls a working driver on an explicit yes.

A working driver is replaced only when the Hardware tab sends {"reinstall": true}
after the technician confirms the warning. Anything else - an empty body, a
truthy string, a number - must leave Repair-GpuDriver.ps1 on its default, which
refuses a healthy card.
"""

import asyncio
import os
import sys
import unittest
from unittest import mock

_WEB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_APP_DIR = os.path.join(_WEB, "app")
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import main  # noqa: E402  (before any asyncio.run: it creates an asyncio.Lock at import)


class _Req:
    def __init__(self, body=None, bad_json=False):
        self._body, self._bad = body, bad_json

    async def json(self):
        if self._bad:
            raise ValueError("no body")
        return self._body


def _args_sent(req):
    seen = {}

    async def fake_run_ps(script, args=None, **kw):
        seen["script"], seen["args"] = script, args
        return {"status": "x"}

    with mock.patch.object(main, "run_ps", fake_run_ps):
        asyncio.run(main.api_gpu_driver_repair(req))
    assert seen["script"] == "Repair-GpuDriver.ps1"
    return seen["args"]


class ReinstallFlag(unittest.TestCase):
    def test_explicit_true_asks_for_a_reinstall(self):
        self.assertEqual(_args_sent(_Req({"reinstall": True})), {"Reinstall": 1})

    def test_the_plain_repair_click_does_not(self):
        self.assertIsNone(_args_sent(_Req({})))

    def test_no_body_does_not(self):
        self.assertIsNone(_args_sent(_Req(bad_json=True)))

    def test_truthy_but_not_true_does_not(self):
        for v in ("true", "yes", 1, "false", [True], {"x": 1}):
            self.assertIsNone(_args_sent(_Req({"reinstall": v})), repr(v))

    def test_a_non_object_body_does_not(self):
        self.assertIsNone(_args_sent(_Req([True])))


if __name__ == "__main__":
    unittest.main()
