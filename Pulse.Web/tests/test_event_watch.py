"""The in-event reader (event_watch.py): files only, stdlib only."""

import json
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


class RealLinesTest(unittest.TestCase):
    """Lines copied from 6493's VPU log during the 2026-10-14 test event."""

    REAL = (
        "INFO\t| 2026-10-14 20:06:21 |MAIN\t|x(1)\t|x\t|START NEW LOG SESSION >>> VPU.exe - Version: 5.37.3 >>> Host: vpu\n"
        "Info\t| 2026-10-14 20:06:24.576 |DEFAULT_MODULE\t|x(1)\t|x\t|Copying directory from C:\\Pixellot\\Data\\configuration/calibration to d:/recordedEvents/2026-10-14_p_6ad018b2ec5d0313d04118a6/2026-10-14_p_6ad018b2ec5d0313d04118a6_metadata.2011.123.i/calibration\n"
        "Error\t| 2026-10-14 20:06:25.242 |VPU\t|x(1)\t|x\t|cannot find needed calibration for Americanfootball. Using default fixed-frame. turning off AP\n"
        "Info\t| 2026-10-14 20:06:35.041 |AVWriter\t|x(1)\t|x\t|urlToStreamWriter for urls rtsp://@:7788 finish\n"
        "Info\t| 2026-10-14 20:07:35.101 |AVWriter\t|x(1)\t|x\t|urlToStreamWriter for urls zixi://pxltd-100-62-83-36.pixellot.stream:2088/0_hd_2000|zixi://pxltd-100-62-83-36.pixellot.stream:443/0_hd_2000 finish\n"
        "Info\t| 2026-10-14 20:07:35.308 |ZixiStreams\t|x(1)\t|x\t|Created Zixi stream: HD_Writer0_Stream0\n"
        "Alert\t| 2026-10-14 20:11:05.944 |FFMPEGStreams\t|x(1)\t|x\t|Video Connection d:\\recordedEvents\\2026-10-14_p_6ad018b2ec5d0313d04118a6\\x_hd.mkv Created Successfuly\n"
        "Info\t| 2026-10-14 20:31:51.804 |StatusReporter\t|StatusReporter.cpp(694)\t|StatusReporter::reportStatus\t|VPU:|CFPS:,Avr=25.00  ,Min=24.99  ,Max=25.01   |Camera0AvgFps:Lst=25.40   |Camera0LowFpsCount:Lst=0.00    |Camera1AvgFps:Lst=25.40   |Camera1LowFpsCount:Lst=0.00    |Debayer_Drops:Lst=10.00   |HD_Writer0_Stream0_FPS:Lst=25.00   |HD_Writer0_Stream0_Fails:Lst=0     |HD_Writer0_Stream0_UrlPort:Lst=2088.00 |HD_WritersDroppedFrames:Lst=0.00    |Health:Lst=1.00    |\n"
    )
    DAILY = (
        "INFO\t| 2026-10-14 10:59:16 |MAIN\t|x(1)\t|x\t|START NEW LOG SESSION >>> VPU.exe - Version: 5.37.3 >>> Host: vpu\n"
        "Info\t| 2026-10-14 10:59:45.350 |DEFAULT_MODULE\t|x(1)\t|x\t|Copying directory from C:\\Pixellot\\Data\\configuration/calibration to d:/recordedEvents/2026-10-14_p_DAILYTEST20261014/2026-10-14_p_DAILYTEST20261014_metadata.0330.10.i/calibration\n"
        "Alert\t| 2026-10-14 11:30:25.025 |VPUGenericCommand\t|x(1)\t|x\t|GRPC receiving CloseUnit Command from Agent. Reason: \"AgentGui: stop recorder in manual mode was pressed\"\n"
    )

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.logs = os.path.join(self.tmp.name, "Log")
        os.makedirs(self.logs)
        self.vpu = os.path.join(self.logs, "VPU_vpu_20261014_105916.log")

    def tearDown(self):
        self.tmp.cleanup()

    def run_on(self, text, ev=None):
        with open(self.vpu, "a", encoding="utf-8") as fh:
            fh.write(text)
        ev = ev if ev is not None else {"startedAt": T0}
        event_watch.observe(ev, "1", T0 + 3000, log_dir=self.logs, events_dir=self.tmp.name)
        return ev

    def test_the_test_event_reads_on_air_uncalibrated_on_zixi_2088(self):
        ev = self.run_on(self.REAL)
        self.assertEqual(event_watch.verdict(ev, T0 + 3000), "on-air")
        s = event_watch.summary(ev, T0 + 3000, ended=False)
        self.assertEqual(s["eventId"], "6ad018b2ec5d0313d04118a6")
        self.assertEqual(s["kind"], "event")
        self.assertFalse(s["calibrated"])
        self.assertEqual(s["sport"], "Americanfootball")
        self.assertEqual(s["via"], "zixi")
        self.assertEqual(s["live"]["port"], 2088)
        self.assertEqual(s["live"]["fps"], 25.0)
        self.assertEqual(s["live"]["cameraFps"], [25.4, 25.4])
        self.assertEqual(s["restarts"], 0)
        self.assertEqual(ev["chain"][0], "zixi://pxltd-100-62-83-36.pixellot.stream:2088/0_hd_2000")

    def test_a_second_session_is_a_restart(self):
        ev = self.run_on(self.REAL)
        ev = self.run_on(self.REAL.splitlines(True)[0], ev)
        self.assertEqual(ev["restarts"], 1)

    def test_the_daily_test_is_labelled_and_never_borrows_an_older_event(self):
        ev = self.run_on(self.DAILY)
        s = event_watch.summary(ev, T0 + 3000, ended=True)
        self.assertEqual(s["eventId"], "DAILYTEST20261014")
        self.assertEqual(s["kind"], "daily-test")
        self.assertEqual(s["closeReason"], "AgentGui: stop recorder in manual mode was pressed")
        self.assertFalse(s["wentOnAir"])


class MidEventTest(RealLinesTest):
    def test_a_status_line_alone_is_not_on_air_and_the_next_restart_still_counts(self):
        status_only = self.REAL.splitlines(True)[-1]
        ev = self.run_on(status_only)                         # no session or connect line anywhere
        # Encoder FPS is not delivery (6493 read 25 fps through an outage).
        self.assertNotEqual(event_watch.verdict(ev, T0 + 3000), "on-air")
        ev = self.run_on(self.REAL.splitlines(True)[0], ev)   # then VPU.exe restarts
        self.assertEqual(ev["restarts"], 1)


class EventFolderTest(unittest.TestCase):
    def test_an_old_folder_still_being_written_is_the_live_event(self):
        with tempfile.TemporaryDirectory() as d:
            old = os.path.join(d, "2026-10-13_p_aaaaaaaaaaaaaaaaaaaaaaaa")
            live = os.path.join(d, "2026-10-14_p_6ad018b2ec5d0313d04118a6")
            os.makedirs(old); os.makedirs(live)
            hour_ago = time.time() - 3600
            os.utime(old, (hour_ago - 86400,) * 2)
            with open(os.path.join(live, "x_hd.mkv"), "w") as fh:
                fh.write("frames")                      # written just now
            os.utime(live, (hour_ago,) * 2)             # the folder itself is an hour old
            self.assertEqual(event_watch.newest_event_id(d, since=time.time()), "6ad018b2ec5d0313d04118a6")
            os.utime(os.path.join(live, "x_hd.mkv"), (hour_ago,) * 2)
            self.assertIsNone(event_watch.newest_event_id(d, since=time.time()))   # nothing live


class CatchUpTest(RealLinesTest):
    def test_a_mid_event_start_recovers_the_session_from_far_back(self):
        old = event_watch.MAX_READ_BYTES
        event_watch.MAX_READ_BYTES = 2048
        try:
            status = self.REAL.splitlines(True)[-1]
            with open(self.vpu, "a", encoding="utf-8") as fh:
                fh.write(self.DAILY)                       # an earlier session today
                fh.write(self.REAL)                        # this event's session
                fh.write(status * 200)                     # long past the read window
            ev = {"startedAt": T0}
            event_watch.observe(ev, "1", T0 + 3000, log_dir=self.logs, events_dir=self.tmp.name)
        finally:
            event_watch.MAX_READ_BYTES = old
        s = event_watch.summary(ev, T0 + 3000, ended=False)
        self.assertEqual(s["eventId"], "6ad018b2ec5d0313d04118a6")   # not the daily test's
        self.assertFalse(s["calibrated"])
        self.assertEqual(s["restarts"], 0)
        self.assertEqual(event_watch.verdict(ev, T0 + 3000), "on-air")
        self.assertTrue(ev["caughtUp"])


class OutageTest(RealLinesTest):
    """6493, 2026-10-14 21:00-21:04: every UDP path blocked by firewall rules."""

    OUTAGE = (
        "Info\t| 2026-10-14 20:58:55.717 |ZixiStreams\t|x(1)\t|x\t|Created Zixi stream: HD_Writer0_Stream0\n"
        "Error\t| 2026-10-14 21:01:30.969 |ZixiStreams\t|x(1)\t|x\t|Failed connecting to zixi://pxltd-100-62-83-36.pixellot.stream:443/0_hd_2000, because Failed to open Zixi stream: HD_Writer0_Stream0, return value: -2\n"
        "Info\t| 2026-10-14 21:02:01.261 |AVWriter\t|x(1)\t|x\t|onStreamDisconnect: zixi://pxltd-100-62-83-36.pixellot.stream:443/0_hd_2000 failed, move to zixi://100.1.2.3:2088/0_hd_2000\n"
        "Error\t| 2026-10-14 21:03:32.125 |ZixiStreams\t|x(1)\t|x\t|Failed connecting to zixi://100.1.2.3:443/0_hd_2000, because Failed to open Zixi stream: HD_Writer0_Stream0, return value: -2\n"
        "Info\t| 2026-10-14 21:03:40.000 |StatusReporter\t|StatusReporter.cpp(694)\t|StatusReporter::reportStatus\t|VPU:|HD_Writer0_Stream0_FPS:Lst=25.00   |HD_Writer0_Stream0_Fails:Lst=1     |HD_Writer0_Stream0_UrlPort:Lst=443.00 |\n"
    )
    RTMP = (
        "Info\t| 2026-10-14 21:04:02.395 |AVWriter\t|x(1)\t|x\t|onStreamDisconnect: zixi://100.1.2.3:443/0_hd_2000 failed, move to rtmp://pxltd-100-62-83-36.pixellot.stream:1935/live/0_hd_2000\n"
        "Alert\t| 2026-10-14 21:04:07.803 |FFMPEGStreams\t|x(1)\t|x\t|Video Connection rtmp://pxltd-100-62-83-36.pixellot.stream:1935/live/0_hd_2000 Created Successfuly\n"
        "Info\t| 2026-10-14 21:04:18.000 |StatusReporter\t|StatusReporter.cpp(694)\t|StatusReporter::reportStatus\t|VPU:|HD_Writer0_Stream0_FPS:Lst=25.13   |HD_Writer0_Stream0_Fails:Lst=0     |HD_Writer0_Stream0_UrlPort:Lst=1935.00 |\n"
    )

    def test_encoder_fps_during_an_outage_is_not_on_air(self):
        ev = self.run_on(self.REAL + self.OUTAGE)
        self.assertNotEqual(event_watch.verdict(ev, T0 + 3000), "on-air")

    def test_the_rtmp_fallback_is_on_air_and_flagged(self):
        ev = self.run_on(self.REAL + self.OUTAGE + self.RTMP)
        self.assertEqual(event_watch.verdict(ev, T0 + 3000), "on-air")
        s = event_watch.summary(ev, T0 + 3000, ended=False)
        self.assertEqual(s["path"], "rtmp-1935")
        self.assertTrue(s["fallback"])
        self.assertEqual(s["live"]["port"], 1935)

    def test_the_first_choice_path_is_not_a_fallback(self):
        ev = self.run_on(self.REAL)
        s = event_watch.summary(ev, T0 + 3000, ended=False)
        self.assertEqual(s["path"], "zixi-2088")
        self.assertFalse(s["fallback"])


class CameraDegradedTest(RealLinesTest):
    """6493, 2026-10-14 21:07-21:10: camera NIC forced to 100 Mbps."""

    SLOW = (
        "Info\t| 2026-10-14 21:08:08.731 |POE\t|x(1)\t|x\t|Request to disable the Poe. Reset POE counter: 1. Sleep for: 20000. Thread Id: 11564\n"
        "Alert\t| 2026-10-14 21:09:13.925 |Cameras\t|x(1)\t|x\t|Camera reset happened.\n"
        "Info\t| 2026-10-14 21:10:00.000 |StatusReporter\t|StatusReporter.cpp(694)\t|StatusReporter::reportStatus\t|VPU:|Camera0AvgFps:Lst=0.00   |Camera0LowFpsCount:Lst=70.00   |Camera1AvgFps:Lst=25.60   |HD_Writer0_Stream0_FPS:Lst=25.00   |HD_Writer0_Stream0_Fails:Lst=0     |HD_Writer0_Stream0_UrlPort:Lst=1935.00 |Health:Lst=0.63    |\n"
    )

    def test_a_starved_camera_reads_camera_degraded_with_pixellots_own_resets(self):
        ev = self.run_on(self.REAL + self.SLOW)
        self.assertEqual(event_watch.verdict(ev, T0 + 3000), "camera-degraded")
        s = event_watch.summary(ev, T0 + 3000, ended=False)
        self.assertEqual(s["camerasSlow"], [0])
        self.assertEqual(s["poeResets"], 1)
        self.assertEqual(s["cameraResets"], 1)
        self.assertEqual(s["live"]["health"], 0.63)


class CameraUnreachableTest(RealLinesTest):
    def test_the_unreachable_camera_is_named_by_its_stream_ip(self):
        lost = "Error\t| 2026-10-14 21:12:50.904 |Cameras\t|x(1)\t|x\t|Couldn't get response from camera rtsp://169.254.16.51/h264\n"
        ev = self.run_on(self.REAL + lost)
        ev["lastReadAt"] = time.mktime((2026, 10, 14, 21, 14, 0, 0, 0, -1))
        s = event_watch.summary(ev, ev["lastReadAt"], ended=False)
        self.assertEqual(s["camerasUnreachable"], ["169.254.16.51"])
        ev["lastReadAt"] += 600                                   # it came back
        s = event_watch.summary(ev, ev["lastReadAt"], ended=True)
        self.assertEqual(s["camerasUnreachable"], [])
        self.assertEqual(s["camerasLost"], ["169.254.16.51"])


class ScoreboardTest(RealLinesTest):
    def test_scorebug_age_data_rate_and_scoreconnect_down(self):
        sb = ("Info\t| 2026-10-14 21:19:16.804 |StatusReporter\t|StatusReporter.cpp(694)\t|StatusReporter::reportStatus\t"
              "|VPU:|GraphicsTimestampsDelta:,Avr=4312.25,Min=4311.77,Max=4312.73 |ScoreboardDataFrequencyPerSecond:Lst=0.00    |\n")
        with open(self.vpu, "a", encoding="utf-8") as fh:
            fh.write(self.REAL + sb)
        ev = {"startedAt": T0}
        event_watch.observe(ev, "1", T0 + 3000, log_dir=self.logs, events_dir=self.tmp.name,
                            images={"vpu.exe", "explorer.exe"})
        s = event_watch.summary(ev, T0 + 3000, ended=False)
        self.assertEqual(s["live"]["scorebugAgeSeconds"], 4312)
        self.assertEqual(s["live"]["scoreboardDataPerSecond"], 0.0)
        self.assertFalse(s["scoreConnectRunning"])
        self.assertTrue(s["scoreConnectWasDown"])


class GapsTest(OutageTest):
    START = ("Info\t| 2026-10-14 20:06:21.100 |Main Agent\t|x(1)\t|x\t|Start Reason:  event command. Event: "
             "Name[ gam894328ce3f Middle School Boys Football Sample ] _id[6ad018b2ec5d0313d04118a6] "
             "venue[5d6bdbe845b8870789141191] startDate[2026-10-15T00:11:00.000Z] endDate[2026-10-15T02:14:00.000Z]\n"
             "Info\t| 2026-10-14 20:06:33.000 |DEFAULT_MODULE\t|x(1)\t|x\t|ReplayManager::init(americanfootball)\n")

    def sc3_file(self, sport):
        path = os.path.join(self.tmp.name, "settings.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"slot": 0, "parms": [{"sbvendorname": sport, "bot_online": False, "ConfigurationStatus": 2,
                                             "ConfigurationStatusMessage": "Unable to find bot over USB/Serial interface."}]}, fh)
        return path

    def run_with_sc3(self, text, sport):
        old = event_watch.SC3_SETTINGS
        event_watch.SC3_SETTINGS = self.sc3_file(sport)
        try:
            with open(self.vpu, "a", encoding="utf-8") as fh:
                fh.write(text)
            ev = {"startedAt": T0}
            event_watch.observe(ev, "1", T0 + 3000, log_dir=self.logs, events_dir=self.tmp.name,
                                images={"vpu.exe", "scoreconnectiii.exe"})
            return ev
        finally:
            event_watch.SC3_SETTINGS = old

    def test_the_start_line_names_the_game_sport_and_schedule(self):
        ev = self.run_with_sc3(self.START + self.REAL, "Fairplay Football Code 23")
        s = event_watch.summary(ev, T0 + 3000, ended=False)
        self.assertEqual(s["nfhsGameKey"], "gam894328ce3f")
        self.assertEqual(s["scheduledEnd"], "2026-10-15T02:14:00.000Z")
        self.assertEqual(s["sport"], "americanfootball")
        self.assertTrue(s["scoreboard"]["sportMatch"])
        self.assertNotIn("scoreboard-sport-mismatch", s["warnings"])
        self.assertIn("scorelink-offline", s["warnings"])
        self.assertIn("uncalibrated", s["warnings"])

    def test_a_basketball_code_on_a_football_game_is_flagged(self):
        ev = self.run_with_sc3(self.START + self.REAL, "Fairplay Basketball Code 1")
        s = event_watch.summary(ev, T0 + 3000, ended=False)
        self.assertFalse(s["scoreboard"]["sportMatch"])
        self.assertEqual(s["warnings"][0], "scoreboard-sport-mismatch")

    def test_on_air_time_leaves_out_the_outage(self):
        ev = self.run_with_sc3(self.START + self.REAL + self.OUTAGE + self.RTMP, "Fairplay Football Code 23")
        ev["closedAt"] = time.mktime((2026, 10, 14, 21, 49, 44, 0, 0, -1))
        s = event_watch.summary(ev, T0 + 3000, ended=True)
        first = time.mktime((2026, 10, 14, 20, 7, 35, 0, 0, -1))
        outage = (time.mktime((2026, 10, 14, 21, 4, 7, 0, 0, -1)) - time.mktime((2026, 10, 14, 21, 1, 30, 0, 0, -1)))
        self.assertAlmostEqual(s["offAirSeconds"], int(outage), delta=1)
        self.assertAlmostEqual(s["onAirSeconds"], int(ev["closedAt"] - first - outage), delta=1)
        self.assertIn("off-air-gaps", s["warnings"])
        self.assertIn("stream-fallback", s["warnings"])
        self.assertIn("ended-early", s["warnings"])          # 21:49 vs a 22:14 scheduled end

    def test_the_summary_fits_the_workers_4kb_cap(self):
        ev = self.run_with_sc3(self.START + self.REAL + self.OUTAGE + self.RTMP, "Fairplay Football Code 23")
        ev["unreachable"] = {f"169.254.16.{i}": T0 + 2990 for i in range(50, 56)}
        s = event_watch.summary(ev, T0 + 3000, ended=True)
        self.assertLess(len(json.dumps(s)), 4096)
