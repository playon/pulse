"""POST /api/gpu-driver/repair only reinstalls a working driver on an explicit yes.

A working driver is replaced only when the Hardware tab sends {"reinstall": true}
after the technician confirms the warning. Anything else - an empty body, a
truthy string, a number - must leave Repair-GpuDriver.ps1 on its default, which
refuses a healthy card. The endpoint hands off to gpu_job.start, which runs the
script detached.
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


def _sent(req):
    seen = {}

    def fake_start(kind, reinstall):
        seen["kind"], seen["reinstall"] = kind, reinstall
        return {"ok": True}

    with mock.patch.object(main.gpu_job, "start", fake_start):
        asyncio.run(main.api_gpu_driver_repair(req))
    return seen


def _args_sent(req):
    """The Reinstall argument the script ends up with: {"Reinstall": 1} or None."""
    return {"Reinstall": 1} if _sent(req)["reinstall"] is True else None


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

    def test_kind_is_passed_through_only_as_a_string(self):
        self.assertEqual(_sent(_Req({"kind": "rescan"}))["kind"], "rescan")
        self.assertEqual(_sent(_Req({"kind": ["rescan"]}))["kind"], "")
        self.assertEqual(_sent(_Req(bad_json=True))["kind"], "")


class StatusAndAck(unittest.TestCase):
    def test_status_reads_the_job(self):
        with mock.patch.object(main.gpu_job, "status", lambda: {"stage": "downloading"}):
            self.assertEqual(asyncio.run(main.api_gpu_driver_repair_status())["stage"], "downloading")

    def test_ack_needs_a_run_id(self):
        called = []
        with mock.patch.object(main.gpu_job, "ack", lambda rid: called.append(rid) or {"ok": True}):
            self.assertFalse(asyncio.run(main.api_gpu_driver_repair_ack(_Req({})))["ok"])
            self.assertFalse(asyncio.run(main.api_gpu_driver_repair_ack(_Req({"runId": 5})))["ok"])
            self.assertTrue(asyncio.run(main.api_gpu_driver_repair_ack(_Req({"runId": "abc"})))["ok"])
        self.assertEqual(called, ["abc"])


if __name__ == "__main__":
    unittest.main()
