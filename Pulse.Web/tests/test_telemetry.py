"""pulse.telemetry/v1: the utilitarian payload sent with each monitor post."""

import asyncio
import json
import os
import re
import sys
import unittest

_APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import main  # noqa: E402
import powershell  # noqa: E402

MAC = re.compile(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$")


class TestBuildTelemetry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Earlier test files leave the PowerShell semaphore bound to their own
        # event loop (Python 3.9 binds it at creation); start fresh.
        powershell._PS_SEMAPHORE = None
        cls.raw = {}
        cls.dash = asyncio.run(main._collect_dashboard(raw_out=cls.raw))
        asyncio.run(main._collect_telemetry_extras(cls.raw))
        cls.t = main._build_telemetry(cls.dash, cls.raw, "2026-10-13T19:00:00Z")

    def test_the_fields_ian_kept(self):
        t = self.t
        self.assertEqual(t["schema"], "pulse.telemetry/v1")
        for key in ("status", "statusSince", "headline", "blockers", "checkedAt", "pixellotVersion",
                    "network", "cameras", "servicesDown", "scoreboard", "power"):
            self.assertIn(key, t)
        self.assertEqual(set(t["network"]), {"internetReachable", "streamingPath", "portsFailed", "internet"})
        self.assertEqual(set(t["cameras"]), {"systemType", "expected", "detected", "slow", "ports"})
        # source and ok are Ian's v1 fields; the rest are additive detail
        # (2026-10-14: ok read true all event with 6493's ScoreLink missing).
        self.assertTrue({"source", "ok"} <= set(t["scoreboard"]))
        self.assertTrue(set(t["scoreboard"]) <= {"source", "ok", "scoreLinkConnected", "dataFlowing",
                                                  "dataStatus", "sport"})
        self.assertEqual(set(t["power"]), {"lastBoot", "unexpectedShutdowns7d"})

    def test_status_matches_the_verdict(self):
        self.assertEqual(self.t["status"], self.dash["readiness"]["status"])
        self.assertEqual(self.t["statusSince"], "2026-10-13T19:00:00Z")
        settled = main._build_telemetry(self.dash, self.raw, status="PASS")
        self.assertEqual(settled["status"], "PASS")

    def test_headline_follows_the_settled_findings(self):
        v = self.dash["readiness"]
        first = (v["blockers"] or v["risks"])
        self.assertTrue(first, "demo verdict should carry a blocker or risk")
        unconfirmed = main._build_telemetry(self.dash, self.raw, status="PASS", open_codes=[])
        self.assertIsNone(unconfirmed["headline"])
        self.assertEqual(unconfirmed["blockers"], [])
        confirmed = main._build_telemetry(self.dash, self.raw, open_codes=[first[0]["code"]])
        self.assertEqual(confirmed["headline"], first[0]["title"])

    def test_internet_adapter_setup(self):
        inet = self.t["network"]["internet"]
        for key in ("ip", "subnetMask", "gateway", "dns1", "dns2", "dhcp", "mac"):
            self.assertIn(key, inet)
        self.assertTrue(inet["ip"])
        self.assertRegex(inet["mac"], MAC)

    def test_per_port_camera_detail(self):
        ports = self.t["cameras"]["ports"]
        cams = [p for p in ports if p["state"] == "camera"]
        self.assertTrue(cams)
        for p in cams:
            self.assertRegex(p["cameraMac"], MAC)
            self.assertIn("linkMbps", p)
            self.assertIn("slow", p)
        self.assertEqual(self.t["cameras"]["slow"], sum(1 for p in ports if p["slow"]))

    def test_dropped_fields_stay_out(self):
        # Ian, 2026-10-13: no hostname, serial, or separate camera-MAC list;
        # troubleshooting detail waits for a later tier.
        text = json.dumps(self.t)
        for gone in ("hostname", "serialNumber", "camera_macs", "cameraMacs", '"findings"',
                     "clockOffset", '"poe"', "recentRecordings", '"gpus"', '"adapters"'):
            self.assertNotIn(gone, text)

    def test_skipped_port_probe_is_null_not_blocked(self):
        n = main._build_telemetry(self.dash, dict(self.raw, port_tests=None))["network"]
        self.assertIsNone(n["portsFailed"])
        self.assertIsNone(n["streamingPath"])

    def test_failed_collectors_leave_parts_null(self):
        raw = {"nics": {"error": True}, "port_tests": {"error": True}}
        t = main._build_telemetry(self.dash, raw)
        self.assertIsNone(t["cameras"]["detected"])
        self.assertIsNone(t["network"]["portsFailed"])
        self.assertIsNone(t["power"]["unexpectedShutdowns7d"])

    def test_small(self):
        self.assertLess(len(json.dumps(self.t)), 4000)

    def test_services_down_ignores_idle_vpu_and_unneeded_scoreconnect(self):
        svc = {"agent": "Running", "coordinator": "Stopped", "vpu": "Stopped",
               "keepagentup": "Running", "ScoreConnectIII": "Stopped", "LogMeIn": "Running"}
        self.assertEqual(main._services_down(svc, {"source": "ocr"}), ["coordinator"])
        self.assertEqual(main._services_down(svc, {"source": "scoreconnect"}),
                         ["coordinator", "ScoreConnectIII"])
        self.assertEqual(main._services_down(dict(svc, ScoreConnectIII="NotFound"),
                                             {"source": "scoreconnect"}), ["coordinator"])

    def test_fingerprint_ignores_timestamps_but_not_changes(self):
        fp = main._telemetry_fingerprint(self.t, ["nic-slow"])
        later = dict(self.t, checkedAt="2099-01-01T00:00:00Z", statusSince="2099-01-01T00:00:00Z")
        self.assertEqual(main._telemetry_fingerprint(later, ["nic-slow"]), fp)
        self.assertNotEqual(main._telemetry_fingerprint(self.t, []), fp)
        moved = json.loads(json.dumps(self.t))
        moved["network"]["streamingPath"] = "blocked"
        self.assertNotEqual(main._telemetry_fingerprint(moved, ["nic-slow"]), fp)

    def test_prefix_to_mask(self):
        self.assertEqual(main._prefix_to_mask(24), "255.255.255.0")
        self.assertEqual(main._prefix_to_mask(23), "255.255.254.0")
        self.assertIsNone(main._prefix_to_mask(33))

    def test_norm_mac(self):
        self.assertEqual(main._norm_mac("a0-36-9f-11-22-33"), "A0:36:9F:11:22:33")
        self.assertIsNone(main._norm_mac("not a mac"))


class TestCheckinEntries(unittest.TestCase):
    def setUp(self):
        powershell._PS_SEMAPHORE = None

    def test_heartbeat_is_one_line(self):
        dash = {"identity": {"venueId": "V1", "vpuName": "PXLS2_1 Test", "hostname": "VPU"}}
        e = asyncio.run(main._build_checkin_entry(dash, heartbeat=True))
        self.assertEqual(set(e), {"checkinId", "sentAt", "reason", "venueId", "vpuName", "status"})
        self.assertEqual((e["reason"], e["status"]), ("heartbeat", "PASS"))

    def test_no_hostname_or_serial_in_any_check_in(self):
        launch = asyncio.run(main._build_checkin_entry())
        mon = asyncio.run(main._build_checkin_entry(telemetry={"schema": "pulse.telemetry/v1"},
                                                    reason="periodic"))
        for e in (launch, mon):
            self.assertNotIn("hostname", e)
            self.assertNotIn("serialNumber", e)
            self.assertIn("model", e)

    def test_lost_identity_falls_back_to_the_last_known(self):
        saved = dict(main._CHECKIN_IDENTITY_FALLBACK)
        try:
            main._CHECKIN_IDENTITY_FALLBACK = {"venueId": "V-known", "vpuName": "PXLS2_1 Known"}
            beat = asyncio.run(main._build_checkin_entry({"identity": {}}, heartbeat=True))
            self.assertEqual((beat["venueId"], beat["vpuName"]), ("V-known", "PXLS2_1 Known"))
            fresh = asyncio.run(main._build_checkin_entry(
                {"identity": {"venueId": "V-new", "vpuName": "PXLS2_2 New"}}, heartbeat=True))
            self.assertEqual(fresh["venueId"], "V-new")      # a good read always wins
        finally:
            main._CHECKIN_IDENTITY_FALLBACK = saved

    def test_monitor_entry_is_utilitarian(self):
        mon = asyncio.run(main._build_checkin_entry(telemetry={"schema": "pulse.telemetry/v1"},
                                                    reason="periodic"))
        for later in ("channel", "osBuild", "ubr", "readiness"):
            self.assertNotIn(later, mon)


if __name__ == "__main__":
    unittest.main()


class TestScoreboardDetail(unittest.TestCase):
    """6493, 2026-10-14: scoreboard ok (ScoreConnect running) all event with no ScoreLink."""

    def test_scorelink_data_and_sport_ride_along_without_changing_ok(self):
        sc = {"reachable": True, "scoreLinkConnected": False, "dataStatus": "No Scoreboard data is being received",
              "configuration": {"sport": "Fairplay Basketball Code 1"}}
        out = main._telemetry_scoreboard({"scoreconnect": sc, "nics": None})
        self.assertEqual(out["source"], "scoreconnect")
        self.assertTrue(out["ok"])                       # v1 meaning unchanged
        self.assertFalse(out["scoreLinkConnected"])
        self.assertFalse(out["dataFlowing"])
        self.assertEqual(out["sport"], "Fairplay Basketball Code 1")
