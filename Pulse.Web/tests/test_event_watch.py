"""The in-event reader (event_watch.py): files only, stdlib only."""

import os
import sys
import tempfile
import time
import unittest

_APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import event_watch  # noqa: E402

T0 = time.mktime((2026, 10, 14, 20, 10, 0, 0, 0, -1))


def stamp(sec):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(T0 + sec)) + ".123"


def line(sec, msg, level="Info", module="VPU"):
    return f"{level}\t| {stamp(sec)} |{module}\t|VPU.cpp(1)\t|VPU::f\t|{msg}\n"


BENCH_HEADER = ("Year,Month,Day,Hour,Min,Sec,GPUCoreLoad,GPUMemoryLoad,GPUTemperature,CPULoad,"
                "CPU Usage: VPU,RAM Available,GPU Video Engine Load,Camera NIC 1 Speed,Camera NIC 2 Speed\n")


def bench_row(sec, cpu=20, nic1=1000, nic2=1000):
    t = time.localtime(T0 + sec)
    return f"{t.tm_year},{t.tm_mon},{t.tm_mday},{t.tm_hour},{t.tm_min},{t.tm_sec},40,10,50,{cpu},12,25,30,{nic1},{nic2}\n"


class EventWatchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.logs = os.path.join(self.tmp.name, "Log")
        self.events = os.path.join(self.tmp.name, "recordedEvents")
        os.makedirs(self.logs)
        os.makedirs(os.path.join(self.events, "2026-10-14_p_6ad018b2ec5d0313d04118a6"))
        self.vpu = os.path.join(self.logs, "VPU_vpu_20261014_105916.log")
        self.bench = os.path.join(self.logs, "AgentBenchmarks_vpu_20261014_000006.csv")
        with open(self.bench, "w") as fh:
            fh.write(BENCH_HEADER)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, path, text):
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text)

    def tick(self, ev, now, pid="4242"):
        return event_watch.observe(ev, pid, T0 + now, log_dir=self.logs, events_dir=self.events)

    def test_a_stream_that_connects_reads_on_air(self):
        ev = {"startedAt": T0}
        self.write(self.vpu, line(1, "START NEW LOG SESSION >>> VPU.exe - Version: 5.37.2"))
        self.write(self.vpu, line(5, "urlToStreamWriter for urls zixi://a:2088/0_hd|zixi://a:443/0_hd|rtmp://b/live"))
        self.write(self.vpu, line(9, "Created Zixi stream: HD_Writer0_Stream0"))
        self.write(self.bench, bench_row(10) + bench_row(20, cpu=35))
        self.tick(ev, 30)
        self.assertEqual(event_watch.verdict(ev, T0 + 30), "on-air")
        self.assertEqual(ev["eventId"], "6ad018b2ec5d0313d04118a6")
        self.assertEqual(ev["via"], "zixi")
        self.assertEqual(ev["peak"]["cpuMax"], 35)

    def test_failing_for_two_minutes_without_a_connect_is_stream_failing(self):
        ev = {"startedAt": T0}
        for s in range(0, 150, 15):
            self.write(self.vpu, line(s, "Failed connecting to zixi://a:2088/0_hd, because x return value: -11",
                                      level="Error"))
        self.tick(ev, 60)
        self.assertEqual(event_watch.verdict(ev, T0 + 60), "connecting")   # not yet 2 minutes
        self.tick(ev, 160)
        self.assertEqual(event_watch.verdict(ev, T0 + 160), "stream-failing")
        self.assertEqual(ev["lastFailCode"], -11)
        s = event_watch.summary(ev, T0 + 200, ended=True)
        self.assertFalse(s["wentOnAir"])
        self.assertEqual(s["reason"], "stream-failing")

    def test_each_read_takes_only_new_lines(self):
        ev = {"startedAt": T0}
        self.write(self.vpu, line(1, "Failed connecting to zixi://a:2088/x, because y return value: -2"))
        self.tick(ev, 10)
        self.tick(ev, 20)                       # nothing new: no double count
        self.assertEqual(ev["fails"], 1)
        self.write(self.vpu, line(21, "Failed connecting to zixi://a:2088/x, because y return value: -2"))
        self.write(self.vpu, "Info\t| partial line with no newl")   # VPU.exe mid-write
        self.tick(ev, 30)
        self.assertEqual(ev["fails"], 2)
        self.write(self.vpu, "ine yet\n")
        self.write(self.vpu, line(31, "Created Zixi stream: S"))
        self.tick(ev, 40)
        self.assertEqual(event_watch.verdict(ev, T0 + 40), "on-air")

    def test_a_new_pid_is_a_restart_and_two_are_a_loop(self):
        ev = {"startedAt": T0}
        self.tick(ev, 10, pid="100")
        self.tick(ev, 20, pid="200")
        self.assertEqual(ev["restarts"], 1)
        self.tick(ev, 30, pid="300")
        self.assertEqual(event_watch.verdict(ev, T0 + 30), "restart-loop")

    def test_a_camera_nic_that_drops_to_zero_is_camera_link_down(self):
        ev = {"startedAt": T0}
        self.write(self.bench, bench_row(10))
        self.tick(ev, 15)
        self.assertEqual(ev["nicsLinked"], ["Camera NIC 1 Speed", "Camera NIC 2 Speed"])
        self.write(self.bench, bench_row(320, nic2=0))
        self.tick(ev, 330)
        self.assertEqual(event_watch.verdict(ev, T0 + 330), "camera-link-down")
        self.write(self.bench, bench_row(640))
        self.tick(ev, 650)
        self.assertNotEqual(event_watch.verdict(ev, T0 + 650), "camera-link-down")   # it came back

    def test_drops_and_close_reason_reach_the_summary(self):
        ev = {"startedAt": T0}
        self.write(self.vpu, line(3, "Created Zixi stream: S"))
        self.write(self.vpu, line(4, "Debayer dropping queueSize 10 _throwPhase 5", level="Warning",
                                  module="LEAKY BUCKET"))
        self.write(self.vpu, line(3600, 'CloseUnit ... Reason: "stopStreaming event command"'))
        self.tick(ev, 3700)
        s = event_watch.summary(ev, T0 + 3700, ended=True)
        self.assertTrue(s["wentOnAir"])
        self.assertEqual(s["onAirSeconds"], 3597)
        self.assertEqual(s["drops"], 1)
        self.assertEqual(s["closeReason"], "stopStreaming event command")
        self.assertIsNone(s["reason"])

    def test_a_huge_backlog_is_read_from_its_tail(self):
        ev = {"startedAt": T0, "logFile": self.vpu, "offset": 0}
        old = event_watch.MAX_READ_BYTES
        event_watch.MAX_READ_BYTES = 4096
        try:
            self.write(self.vpu, line(1, "x" * 200) * 100)
            self.write(self.vpu, line(9, "Created Zixi stream: S"))
            cost = self.tick(ev, 10)
        finally:
            event_watch.MAX_READ_BYTES = old
        self.assertTrue(cost["skipped"])
        self.assertLessEqual(cost["bytes"], 4096)
        self.assertEqual(event_watch.verdict(ev, T0 + 10), "on-air")

    def test_missing_files_never_raise(self):
        ev = {"startedAt": T0}
        event_watch.observe(ev, "1", T0, log_dir=os.path.join(self.tmp.name, "nope"),
                            events_dir=os.path.join(self.tmp.name, "nope"))
        self.assertEqual(event_watch.verdict(ev, T0), "connecting")


if __name__ == "__main__":
    unittest.main()
