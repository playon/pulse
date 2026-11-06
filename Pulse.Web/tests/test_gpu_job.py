"""gpu_job: the graphics driver repair as a detached job with a status file.

The run must survive the browser and Pulse, so its state lives in a file the
script writes. These tests pin what Pulse concludes from that file: live,
stalled (alive but silent), died (process gone with no result), or done; that
a second start is refused while a run may still be going; and that only a
finished run can be acknowledged.
"""

import json
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

_WEB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_APP_DIR = os.path.join(_WEB, "app")
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import gpu_job  # noqa: E402


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for p in (mock.patch.dict(os.environ, {"ProgramData": self.tmp.name}),
                  mock.patch.object(gpu_job, "DEMO", False)):
            p.start()
            self.addCleanup(p.stop)
        self.alive = set()
        p = mock.patch.object(gpu_job, "_pid_alive", lambda pid: pid in self.alive)
        p.start()
        self.addCleanup(p.stop)
        gpu_job._last_spawn.clear()

    def write(self, **kw):
        now = int(time.time())
        rec = {"runId": "r1", "kind": "install", "pid": 4242, "stage": "downloading",
               "startedEpoch": now - 60, "updatedEpoch": now, "result": None}
        rec.update(kw)
        os.makedirs(os.path.dirname(gpu_job.status_path()), exist_ok=True)
        with open(gpu_job.status_path(), "w", encoding="utf-8") as fh:
            json.dump(rec, fh)
        return rec


class Status(_Base):
    def test_no_file_is_idle(self):
        s = gpu_job.status()
        self.assertEqual(s["stage"], "idle")
        self.assertFalse(s["live"])

    def test_alive_and_fresh_is_live(self):
        self.alive.add(4242)
        self.write()
        s = gpu_job.status()
        self.assertTrue(s["live"])
        self.assertFalse(s["stale"] or s["died"] or s["finished"])

    def test_alive_but_silent_is_stale_not_live(self):
        self.alive.add(4242)
        self.write(updatedEpoch=int(time.time()) - gpu_job.STALE_SECS - 5)
        s = gpu_job.status()
        self.assertTrue(s["stale"])
        self.assertFalse(s["live"])
        self.assertFalse(s["finished"])

    def test_process_gone_without_a_result_died(self):
        self.write(stage="installing")
        s = gpu_job.status()
        self.assertTrue(s["died"])
        self.assertTrue(s["finished"])
        self.assertFalse(s["live"])

    def test_done_is_finished_whatever_the_pid(self):
        self.write(stage="done", result={"status": "installed"})
        s = gpu_job.status()
        self.assertTrue(s["finished"])
        self.assertFalse(s["died"])

    def test_no_pid_yet_gets_a_grace_period(self):
        self.write(stage="starting", pid=None)
        self.assertFalse(gpu_job.status()["died"])
        self.write(stage="starting", pid=None,
                   updatedEpoch=int(time.time()) - gpu_job.FIRST_WRITE_GRACE_SECS - 5)
        self.assertTrue(gpu_job.status()["died"])

    def test_spawned_pid_covers_the_gap_before_the_first_write(self):
        self.alive.add(777)
        gpu_job._last_spawn["r1"] = 777
        self.write(stage="starting", pid=None)
        self.assertTrue(gpu_job.status()["live"])

    def test_unreadable_file_is_transient_unknown(self):
        os.makedirs(os.path.dirname(gpu_job.status_path()), exist_ok=True)
        with open(gpu_job.status_path(), "w") as fh:
            fh.write("{not json")
        s = gpu_job.status()
        self.assertEqual(s["stage"], "unknown")
        self.assertTrue(s["transient"])

    def test_a_bom_from_powershell_is_tolerated(self):
        os.makedirs(os.path.dirname(gpu_job.status_path()), exist_ok=True)
        with open(gpu_job.status_path(), "w", encoding="utf-8-sig") as fh:
            json.dump({"runId": "r1", "stage": "done", "updatedEpoch": int(time.time())}, fh)
        self.assertTrue(gpu_job.status()["finished"])


class Start(_Base):
    def test_refused_while_a_run_is_live(self):
        self.alive.add(4242)
        self.write()
        with mock.patch.object(gpu_job.subprocess, "Popen") as popen:
            r = gpu_job.start("install", False)
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "already-running")
        popen.assert_not_called()

    def test_refused_while_a_run_is_stale_but_recent(self):
        self.alive.add(4242)
        self.write(updatedEpoch=int(time.time()) - gpu_job.STALE_SECS - 5)
        with mock.patch.object(gpu_job.subprocess, "Popen") as popen:
            self.assertEqual(gpu_job.start("install", False)["status"], "already-running")
        popen.assert_not_called()

    def test_allowed_after_a_run_died(self):
        self.write(stage="installing")  # pid 4242 not alive
        proc = mock.Mock(pid=9001)
        with mock.patch.object(gpu_job.subprocess, "Popen", return_value=proc):
            self.assertTrue(gpu_job.start("install", False)["ok"])

    def test_spawns_detached_with_status_args_and_writes_starting(self):
        proc = mock.Mock(pid=9001)
        with mock.patch.object(gpu_job.subprocess, "Popen", return_value=proc) as popen:
            r = gpu_job.start("reinstall", True)
        self.assertTrue(r["ok"])
        cmd = popen.call_args[0][0]
        self.assertIn("Repair-GpuDriver.ps1", os.path.basename(cmd[cmd.index("-File") + 1]))
        self.assertEqual(cmd[cmd.index("-StatusPath") + 1], gpu_job.status_path())
        self.assertEqual(cmd[cmd.index("-RunId") + 1], r["runId"])
        self.assertEqual(cmd[cmd.index("-Kind") + 1], "reinstall")
        self.assertEqual(cmd[cmd.index("-Reinstall") + 1], "1")
        flags = popen.call_args[1]["creationflags"]
        self.assertTrue(flags & 0x00000200, "needs its own process group")
        self.assertTrue(flags & 0x08000000, "no console window")
        with open(gpu_job.status_path(), encoding="utf-8") as fh:
            rec = json.load(fh)
        self.assertEqual((rec["runId"], rec["stage"]), (r["runId"], "starting"))
        self.assertEqual(gpu_job._last_spawn[r["runId"]], 9001)

    def test_no_reinstall_flag_unless_asked(self):
        with mock.patch.object(gpu_job.subprocess, "Popen", return_value=mock.Mock(pid=1)) as popen:
            gpu_job.start("install", False)
        self.assertNotIn("-Reinstall", popen.call_args[0][0])

    def test_unknown_kind_is_normalised(self):
        with mock.patch.object(gpu_job.subprocess, "Popen", return_value=mock.Mock(pid=1)) as popen:
            gpu_job.start("rm -rf", False)
        cmd = popen.call_args[0][0]
        self.assertEqual(cmd[cmd.index("-Kind") + 1], "install")

    def test_retries_without_breakaway_when_the_job_forbids_it(self):
        calls = []

        def popen(cmd, **kw):
            calls.append(kw["creationflags"])
            if kw["creationflags"] & 0x01000000:
                raise PermissionError("Access is denied")
            return mock.Mock(pid=5)
        with mock.patch.object(gpu_job.subprocess, "Popen", popen):
            self.assertTrue(gpu_job.start("install", False)["ok"])
        self.assertEqual(len(calls), 2)
        self.assertFalse(calls[1] & 0x01000000)

    def test_spawn_failure_is_recorded_as_a_finished_error(self):
        with mock.patch.object(gpu_job.subprocess, "Popen", side_effect=OSError("no powershell")):
            r = gpu_job.start("install", False)
        self.assertFalse(r["ok"])
        s = gpu_job.status()
        self.assertTrue(s["finished"])
        self.assertTrue(s["result"]["error"])
        self.assertIn("no powershell", s["result"]["message"])


class Ack(_Base):
    def test_only_a_finished_run_with_the_same_id(self):
        self.alive.add(4242)
        self.write()
        self.assertFalse(gpu_job.ack("r1")["ok"])            # still running
        self.write(stage="done", result={"status": "installed"})
        self.assertFalse(gpu_job.ack("other")["ok"])         # not the latest run
        self.assertTrue(gpu_job.ack("r1")["ok"])
        self.assertTrue(gpu_job.status()["acknowledged"])

    def test_a_died_run_can_be_acknowledged(self):
        self.write(stage="installing")
        self.assertTrue(gpu_job.ack("r1")["ok"])


class InstallLive(_Base):
    def test_holds_pulse_up_while_live_or_recently_stale(self):
        self.assertFalse(gpu_job.install_live())
        self.alive.add(4242)
        self.write()
        self.assertTrue(gpu_job.install_live())
        self.write(updatedEpoch=int(time.time()) - gpu_job.STALE_SECS - 5)
        self.assertTrue(gpu_job.install_live())
        self.write(updatedEpoch=int(time.time()) - gpu_job.ABANDONED_SECS - 5)
        self.assertFalse(gpu_job.install_live())
        self.write(stage="done")
        self.assertFalse(gpu_job.install_live())


class Demo(unittest.TestCase):
    def test_runs_through_to_the_demo_result(self):
        with mock.patch.object(gpu_job, "DEMO", True), mock.patch.dict(os.environ, {"PULSE_DEMO_GPU": "no-driver"}):
            import demo_data
            demo_data._gpu_demo_fixed["done"] = False
            t = [1000.0]
            with mock.patch.object(gpu_job.time, "time", lambda: t[0]):
                r = gpu_job.start("install", False)
                self.assertTrue(r["ok"])
                self.assertEqual(gpu_job.start("install", False)["status"], "already-running")
                t[0] += 9
                s = gpu_job.status()
                self.assertEqual(s["stage"], "downloading")
                self.assertGreater(s["bytesDone"], 0)
                t[0] += 60
                s = gpu_job.status()
                self.assertTrue(s["finished"])
                self.assertEqual(s["result"]["status"], "installed")
                self.assertTrue(gpu_job.ack(r["runId"])["ok"])
                self.assertTrue(gpu_job.status()["acknowledged"])
            demo_data._gpu_demo_fixed["done"] = False
            gpu_job._demo["run"] = None


if __name__ == "__main__":
    unittest.main()
