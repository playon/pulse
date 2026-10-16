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
from pulse_agent import checkin as agent_checkin  # noqa: E402
from pulse_agent import telemetry as agent_telemetry  # noqa: E402
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
        asyncio.run(agent_telemetry._collect_telemetry_extras(cls.raw))
        cls.t = agent_telemetry._build_telemetry(cls.dash, cls.raw, "2026-10-13T19:00:00Z")

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
                                                  "dataStatus", "sport", "ocr", "scoreConnect"})
        self.assertEqual(set(t["power"]), {"lastBoot", "unexpectedShutdowns7d"})

    def test_status_matches_the_verdict(self):
        self.assertEqual(self.t["status"], self.dash["readiness"]["status"])
        self.assertEqual(self.t["statusSince"], "2026-10-13T19:00:00Z")
        settled = agent_telemetry._build_telemetry(self.dash, self.raw, status="PASS")
        self.assertEqual(settled["status"], "PASS")

    def test_headline_follows_the_settled_findings(self):
        v = self.dash["readiness"]
        first = (v["blockers"] or v["risks"])
        self.assertTrue(first, "demo verdict should carry a blocker or risk")
        unconfirmed = agent_telemetry._build_telemetry(self.dash, self.raw, status="PASS", open_codes=[])
        self.assertIsNone(unconfirmed["headline"])
        self.assertEqual(unconfirmed["blockers"], [])
        confirmed = agent_telemetry._build_telemetry(self.dash, self.raw, open_codes=[first[0]["code"]])
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
        n = agent_telemetry._build_telemetry(self.dash, dict(self.raw, port_tests=None))["network"]
        self.assertIsNone(n["portsFailed"])
        self.assertIsNone(n["streamingPath"])

    def test_failed_collectors_leave_parts_null(self):
        raw = {"nics": {"error": True}, "port_tests": {"error": True}}
        t = agent_telemetry._build_telemetry(self.dash, raw)
        self.assertIsNone(t["cameras"]["detected"])
        self.assertIsNone(t["network"]["portsFailed"])
        self.assertIsNone(t["power"]["unexpectedShutdowns7d"])

    def test_small(self):
        self.assertLess(len(json.dumps(self.t)), 4000)

    def test_services_down_ignores_idle_vpu_and_unneeded_scoreconnect(self):
        svc = {"agent": "Running", "coordinator": "Stopped", "vpu": "Stopped",
               "keepagentup": "Running", "ScoreConnectIII": "Stopped", "LogMeIn": "Running"}
        self.assertEqual(agent_telemetry._services_down(svc, {"source": "ocr"}), ["coordinator"])
        self.assertEqual(agent_telemetry._services_down(svc, {"source": "scoreconnect"}),
                         ["coordinator", "ScoreConnectIII"])
        self.assertEqual(agent_telemetry._services_down(dict(svc, ScoreConnectIII="NotFound"),
                                             {"source": "scoreconnect"}), ["coordinator"])

    def test_fingerprint_ignores_timestamps_but_not_changes(self):
        fp = agent_telemetry._telemetry_fingerprint(self.t, ["nic-slow"])
        later = dict(self.t, checkedAt="2099-01-01T00:00:00Z", statusSince="2099-01-01T00:00:00Z")
        self.assertEqual(agent_telemetry._telemetry_fingerprint(later, ["nic-slow"]), fp)
        self.assertNotEqual(agent_telemetry._telemetry_fingerprint(self.t, []), fp)
        moved = json.loads(json.dumps(self.t))
        moved["network"]["streamingPath"] = "blocked"
        self.assertNotEqual(agent_telemetry._telemetry_fingerprint(moved, ["nic-slow"]), fp)

    def test_prefix_to_mask(self):
        self.assertEqual(agent_telemetry._prefix_to_mask(24), "255.255.255.0")
        self.assertEqual(agent_telemetry._prefix_to_mask(23), "255.255.254.0")
        self.assertIsNone(agent_telemetry._prefix_to_mask(33))

    def test_norm_mac(self):
        self.assertEqual(agent_telemetry._norm_mac("a0-36-9f-11-22-33"), "A0:36:9F:11:22:33")
        self.assertIsNone(agent_telemetry._norm_mac("not a mac"))


class TestCheckinEntries(unittest.TestCase):
    def setUp(self):
        powershell._PS_SEMAPHORE = None

    def test_heartbeat_is_one_line(self):
        dash = {"identity": {"venueId": "V1", "vpuName": "PXLS2_1 Test", "hostname": "VPU"}}
        e = asyncio.run(agent_checkin._build_checkin_entry(dash, heartbeat=True))
        self.assertEqual(set(e), {"checkinId", "sentAt", "reason", "venueId", "vpuName", "status"})
        self.assertEqual((e["reason"], e["status"]), ("heartbeat", "PASS"))

    def test_no_hostname_or_serial_in_any_check_in(self):
        launch = asyncio.run(agent_checkin._build_checkin_entry())
        mon = asyncio.run(agent_checkin._build_checkin_entry(telemetry={"schema": "pulse.telemetry/v1"},
                                                    reason="periodic"))
        for e in (launch, mon):
            self.assertNotIn("hostname", e)
            self.assertNotIn("serialNumber", e)
            self.assertIn("model", e)

    def test_lost_identity_falls_back_to_the_last_known(self):
        saved = dict(agent_checkin._CHECKIN_IDENTITY_FALLBACK)
        try:
            agent_checkin._CHECKIN_IDENTITY_FALLBACK = {"venueId": "V-known", "vpuName": "PXLS2_1 Known"}
            beat = asyncio.run(agent_checkin._build_checkin_entry({"identity": {}}, heartbeat=True))
            self.assertEqual((beat["venueId"], beat["vpuName"]), ("V-known", "PXLS2_1 Known"))
            fresh = asyncio.run(agent_checkin._build_checkin_entry(
                {"identity": {"venueId": "V-new", "vpuName": "PXLS2_2 New"}}, heartbeat=True))
            self.assertEqual(fresh["venueId"], "V-new")      # a good read always wins
        finally:
            agent_checkin._CHECKIN_IDENTITY_FALLBACK = saved

    def test_agent_version_only_on_the_agents_posts(self):
        import pulse_agent
        self.assertRegex(pulse_agent.AGENT_VERSION, r"^\d+\.\d+\.\d+$")
        launch = asyncio.run(agent_checkin._build_checkin_entry())
        self.assertNotIn("agentVersion", launch)            # Diagnostics' launch check-in
        saved = (agent_checkin._AGENT_VERSION, dict(agent_checkin._CHECKIN_IDENTITY_FALLBACK))
        try:
            agent_checkin._AGENT_VERSION = "9.8.7"
            agent_checkin._CHECKIN_IDENTITY_FALLBACK = {"venueId": "V1"}
            posts = [
                asyncio.run(agent_checkin._build_checkin_entry(telemetry={"schema": "pulse.telemetry/v1"},
                                                               reason="periodic")),
                asyncio.run(agent_checkin._build_checkin_entry({"identity": {}}, heartbeat=True)),
                asyncio.run(agent_checkin._build_checkin_entry(reason="paused", paused=True)),
            ]
            for e in posts:
                self.assertEqual(e["agentVersion"], "9.8.7", e["reason"])
        finally:
            agent_checkin._AGENT_VERSION, agent_checkin._CHECKIN_IDENTITY_FALLBACK = saved

    def test_monitor_entry_is_utilitarian(self):
        mon = asyncio.run(agent_checkin._build_checkin_entry(telemetry={"schema": "pulse.telemetry/v1"},
                                                    reason="periodic"))
        for later in ("channel", "osBuild", "ubr", "readiness"):
            self.assertNotIn(later, mon)


class TestScoreboardDetail(unittest.TestCase):
    """6493, 2026-10-14: scoreboard ok (ScoreConnect running) all event with no ScoreLink."""

    def test_scorelink_data_and_sport_ride_along_without_changing_ok(self):
        sc = {"reachable": True, "scoreLinkConnected": False, "dataStatus": "No Scoreboard data is being received",
              "configuration": {"sport": "Fairplay Basketball Code 1"}}
        out = agent_telemetry._telemetry_scoreboard({"scoreconnect": sc, "nics": None})
        self.assertEqual(out["source"], "scoreconnect")
        self.assertTrue(out["ok"])                       # v1 meaning unchanged
        self.assertFalse(out["scoreLinkConnected"])
        self.assertFalse(out["dataFlowing"])
        self.assertEqual(out["sport"], "Fairplay Basketball Code 1")


_SC_FULL = {
    # Shaped like Get-ScoreConnectStatus.ps1's SC III result: Pick-First makes
    # every configuration value a string, scoreLinkModel is ScoreLink or
    # ScoreLinkII, and botStatus.scoreConnectId carries the bot number.
    "reachable": True, "version": "1.4.2.2", "scoreLinkConnected": True,
    "scoreLinkModel": "ScoreLinkII", "scoreLinkPort": "COM5",
    "dataStatus": "Data is present and in the correct format",
    "configuration": {"vendor": "Daktronics", "sport": "Football", "device": "ScoreLinkII",
                      "serialPort": "COM5", "firmware": "2.4.1", "eventType": "Football"},
    "botStatus": {"isConnected": True, "scoreConnectId": "54025",
                  "botServerAddress": "bot.example.invalid", "lastErrorMessage": None},
}
_NICS = {"ports": []}
_PIX_NONE = {"pixellot_config": {"cameras": [], "cameraCfgExists": True}}
_OCR_ON = {"pixellot_config": {"cameras": [{"role": "OCR"}], "cameraCfgExists": True}}
_SC_KEYS = {"version", "firmware", "scoreLinkModel", "scoreLinkPort", "serialPort", "eventType", "botNumber"}


def _board(sc, pix=_PIX_NONE, nics=_NICS):
    return agent_telemetry._telemetry_scoreboard(dict(pix or {}, scoreconnect=sc, nics=nics))


class TestScoreboardDetailPV59(unittest.TestCase):
    """PV-59: the OCR and ScoreConnect detail that ok/source don't carry."""

    def test_scoreconnect_source_carries_every_field(self):
        out = _board(_SC_FULL)
        self.assertEqual(out["source"], "scoreconnect")
        self.assertTrue(out["ok"])
        self.assertEqual(out["scoreConnect"], {
            "version": "1.4.2.2", "firmware": "2.4.1", "scoreLinkModel": "ScoreLinkII",
            "scoreLinkPort": "COM5", "serialPort": "COM5", "eventType": "Football", "botNumber": "54025"})
        # Both camera reads worked and cameras.cfg has no OCR entry: a real
        # "not configured", with no OCR issue.
        self.assertEqual(out["ocr"], {"configured": False, "issue": None})

    def test_no_hostname_or_device_leaves_the_box(self):
        body = json.dumps(_board(_SC_FULL))
        self.assertNotIn("bot.example.invalid", body)
        self.assertNotIn("botServerAddress", body)
        self.assertNotIn("Daktronics", body)             # vendor/device stay out of this block

    def test_ocr_source_reports_configured_and_issue(self):
        out = _board(_SC_FULL, _OCR_ON)
        self.assertEqual(out["source"], "ocr")
        self.assertFalse(out["ok"])
        self.assertEqual(out["ocr"], {"configured": True, "issue": "ocr-not-connected"})
        # ScoreConnect is still collected while OCR is the source: both blocks appear.
        self.assertEqual(out["scoreConnect"]["version"], "1.4.2.2")
        self.assertTrue(out["scoreLinkConnected"])

    def test_ocr_seen_live_without_a_cameras_cfg_entry(self):
        ocr = {"configured": False, "connected": True, "port": "Port 4", "speedMbps": 1000}
        src = main._scoreboard_source(_SC_FULL, ocr)
        self.assertEqual(src["source"], "ocr")
        self.assertEqual(agent_telemetry._telemetry_scoreboard_ocr(ocr, src, _PIX_NONE["pixellot_config"]),
                         {"configured": False, "issue": None})

    def test_scoreconnect_down_is_not_an_ocr_issue(self):
        out = _board({"reachable": False})
        self.assertEqual(out["source"], "scoreconnect")
        self.assertFalse(out["ok"])
        self.assertEqual(out["ocr"], {"configured": False, "issue": None})

    def test_ocr_is_null_when_the_camera_state_is_unreadable(self):
        for pix, nics in ((_PIX_NONE, None),                                    # NIC read failed
                          ({"pixellot_config": {"error": True, "message": "x"}}, _NICS),
                          ({}, _NICS)):                                         # config never read
            out = _board(_SC_FULL, pix, nics)
            self.assertIsNone(out["ocr"], (pix, nics))
            self.assertEqual(set(out["scoreConnect"]), _SC_KEYS)

    def test_scoreconnect_without_the_new_fields_reads_null_not_empty(self):
        # The collector's own empties: no ScoreLink found ('' model and port),
        # SC III not answering (configuration and botStatus null), no exe.
        sparse = {"reachable": False, "version": None, "scoreLinkConnected": False,
                  "scoreLinkModel": "", "scoreLinkPort": "", "configuration": None, "botStatus": None,
                  "error": None}
        out = _board(sparse)
        self.assertEqual(set(out["scoreConnect"]), _SC_KEYS)
        self.assertTrue(all(v is None for v in out["scoreConnect"].values()))

    def test_sc3_not_answering_still_sends_the_block_with_what_the_disk_and_usb_know(self):
        # The collector's shape when SC III doesn't answer on :5000: no error,
        # configuration and botStatus null, the exe version and the USB scan
        # still filled in.
        down = {"reachable": False, "version": "1.4.2.2", "dataStatus": None,
                "configuration": None, "botStatus": None, "scoreLinkConnected": False,
                "scoreLinkModel": "", "scoreLinkPort": "", "error": None, "sc2": None}
        out = _board(down)["scoreConnect"]
        self.assertEqual(out, {"version": "1.4.2.2", "firmware": None, "scoreLinkModel": None,
                               "scoreLinkPort": None, "serialPort": None, "eventType": None,
                               "botNumber": None})
        plugged = _board(dict(down, scoreLinkConnected=True, scoreLinkModel="ScoreLink",
                              scoreLinkPort="COM7"))["scoreConnect"]
        self.assertEqual((plugged["scoreLinkModel"], plugged["scoreLinkPort"]), ("ScoreLink", "COM7"))
        self.assertIsNone(plugged["botNumber"])

    def test_scoreconnect_block_is_null_only_when_the_collector_failed(self):
        for sc in (None, {"error": "timed out", "reachable": False}):
            out = _board(sc, _OCR_ON)
            self.assertIsNone(out["scoreConnect"])
            self.assertNotIn("scoreLinkConnected", out)
        # Neither half readable: no scoreboard block at all (unchanged).
        self.assertIsNone(agent_telemetry._telemetry_scoreboard({"scoreconnect": None, "nics": None}))

    def test_values_are_trimmed_capped_and_stringified(self):
        sc = dict(_SC_FULL, version="  1.4.2.2  ", scoreLinkModel="x" * 200, scoreLinkPort="   ",
                  botStatus={"scoreConnectId": 54025}, configuration={"firmware": True, "eventType": 7})
        out = _board(sc)["scoreConnect"]
        self.assertEqual(out["version"], "1.4.2.2")
        self.assertEqual(len(out["scoreLinkModel"]), 80)
        self.assertIsNone(out["scoreLinkPort"])
        self.assertEqual(out["botNumber"], "54025")
        self.assertIsNone(out["firmware"])               # a bool is not a firmware version
        self.assertEqual(out["eventType"], "7")

    def test_a_change_moves_the_fingerprint(self):
        def fp(sc, pix=_PIX_NONE):
            t = {"schema": "pulse.telemetry/v1", "scoreboard": _board(sc, pix)}
            return agent_telemetry._telemetry_fingerprint(t, [])
        base = fp(_SC_FULL)
        self.assertEqual(fp(dict(_SC_FULL)), base)
        self.assertNotEqual(fp(dict(_SC_FULL, version="1.4.2.3")), base)
        self.assertNotEqual(fp(dict(_SC_FULL, scoreLinkModel="ScoreLink")), base)
        self.assertNotEqual(fp(dict(_SC_FULL, botStatus={"scoreConnectId": "31882"})), base)
        self.assertNotEqual(fp(dict(_SC_FULL, configuration=dict(_SC_FULL["configuration"], eventType="Basketball"))),
                            base)
        self.assertNotEqual(fp(_SC_FULL, _OCR_ON), base)                       # ocr.configured
        self.assertNotEqual(fp(_SC_FULL, {"pixellot_config": {"error": True}}), base)  # ocr -> null

    def test_full_scoreboard_block_stays_under_1kb(self):
        sc = dict(_SC_FULL, configuration=dict(_SC_FULL["configuration"], sport="Fairplay Basketball Code 1"))
        out = _board(sc, _OCR_ON)
        self.assertEqual(set(out), {"source", "ok", "scoreLinkConnected", "dataFlowing", "dataStatus", "sport",
                                    "ocr", "scoreConnect"})
        self.assertTrue(all(v is not None for v in out["scoreConnect"].values()))
        self.assertIsNotNone(out["ocr"]["issue"])
        self.assertLess(len(json.dumps(out).encode("utf-8")), 1024)

    def test_every_string_at_its_cap_is_still_far_under_the_worker_limit(self):
        # Pathological: all seven values at the 80-char cap plus the older
        # capped fields. The Worker drops a telemetry document over 16 KB.
        y = "y" * 200
        sc = dict(_SC_FULL, version=y, scoreLinkModel=y, scoreLinkPort=y, dataStatus=y,
                  configuration={"sport": y, "serialPort": y, "firmware": y, "eventType": y},
                  botStatus={"scoreConnectId": y})
        out = _board(sc, _OCR_ON)
        self.assertTrue(all(len(v) == 80 for v in out["scoreConnect"].values()))
        self.assertLess(len(json.dumps(out).encode("utf-8")), 1536)


if __name__ == "__main__":
    unittest.main()
