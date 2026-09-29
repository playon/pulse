"""ScoreConnect III setup client and the scoreboard chain's saved facts.

Every fixture string here was captured from a real SC III install (vpu-home,
2026-09-29), not written from the swagger docs, because the docs do not say
what SC III actually answers: an empty device list is HTTP 204, an incomplete
wireless setup is HTTP 400 with prose field names, and so on.
"""

import os
import re
import shutil
import sys
import tempfile
import unittest

_APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import sc3_client as c  # noqa: E402
from sc3_demo_catalog import CATALOG  # noqa: E402


class RequiredFields(unittest.TestCase):
    def test_captured_field_names_parse(self):
        self.assertEqual(c.parse_required_field("Group (BCAST, 0 - 8)"),
                         {"key": "group", "label": "Group", "type": "int", "hint": "BCAST",
                          "min": 0, "max": 8, "raw": "Group (BCAST, 0 - 8)"})
        ch = c.parse_required_field("Channel (Group #, 0 - 99)")
        self.assertEqual((ch["key"], ch["min"], ch["max"], ch["hint"]), ("channel", 0, 99, "Group #"))
        ch = c.parse_required_field("Channel (Channel, 0 - 255)")
        self.assertEqual((ch["key"], ch["max"]), ("channel", 255))

    def test_antenna_is_a_checkbox_with_or_without_its_range(self):
        for raw in ("ExternalAntenna (true - false)", "ExternalAntenna"):
            f = c.parse_required_field(raw)
            self.assertEqual((f["key"], f["type"]), ("externalAntenna", "bool"), raw)

    def test_unparseable_field_keeps_sc3s_words(self):
        f = c.parse_required_field("?? weird: field")
        self.assertIsNone(f["key"])
        self.assertEqual(f["raw"], "?? weird: field")


class Brands(unittest.TestCase):
    def test_models_fold_into_their_brand(self):
        for vendor, brand in (("Daktronics", "daktronics"), ("Daktronics AllSport CG", "daktronics"),
                              ("Fairplay MP70", "fairplay"), ("FairPlay MP80 Wireless", "fairplay"),
                              ("Nevco", "nevco"), ("ElectroMech V2", "electromech"),
                              ("Spectrum V2", "other"), ("", None), (None, None)):
            self.assertEqual(c.brand_of(vendor), brand, vendor)

    def test_every_catalogue_vendor_has_a_brand(self):
        for v in CATALOG["vendors"]:
            self.assertIsNotNone(c.brand_of(v["description"]), v)


class Files(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _write(self, name, text):
        p = os.path.join(self.dir, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        return p

    def test_graphics_cfg_reads_general_type_not_singular(self):
        # vpu-home's file: TYPE appears under [GENERAL] and again under [SINGULAR].
        p = self._write("graphics.cfg",
                        "[GENERAL]\nBOT_NUMBER, string, 02130\n"
                        "TYPE, string, OCR\t\t//options WEB,SPORTZCAST,DAKTRONICS,OUTFITTERS,OCR\n"
                        "PORT, int, 1402\n[SINGULAR]\nTYPE, string, FLOW\t\t//options: REST, FLOW\n")
        self.assertEqual(c.read_graphics_cfg(p), {"source": "OCR", "botNumber": "02130", "error": None})

    def test_missing_graphics_cfg_says_so(self):
        r = c.read_graphics_cfg(os.path.join(self.dir, "nope.cfg"))
        self.assertTrue(r["error"])
        self.assertNotIn("source", r)

    def test_settings_json_device(self):
        p = self._write("settings.json", '{"parms": {"scorelink_desc": "USB ScoreLinkII", "port": "COM4"}}')
        self.assertEqual(c.read_sc3_settings(p), {"deviceType": "ScoreLinkII", "port": "COM4", "error": None})
        self.assertEqual(c.device_type_of("USB ScoreLink"), "ScoreLink")

    def test_settings_json_parms_is_a_list_per_slot(self):
        # The real shape on vpu-home: parms is a list, slot picks the entry.
        p = self._write("settings.json", '{"slot": 1, "slots": 2, "parms": ['
                        '{"scorelink_desc": "USB ScoreLink", "port": "COM3"},'
                        '{"scorelink_desc": "USB ScoreLinkII", "port": "COM8"}]}')
        self.assertEqual(c.read_sc3_settings(p), {"deviceType": "ScoreLinkII", "port": "COM8", "error": None})
        p = self._write("settings.json", '{"slot": 0, "slots": 1, "parms": [{"scorelink_desc": "USB ScoreLinkII", "port": "COM8"}]}')
        self.assertEqual(c.read_sc3_settings(p)["deviceType"], "ScoreLinkII")
        p = self._write("settings.json", '{"parms": "nonsense"}')
        self.assertTrue(c.read_sc3_settings(p)["error"])

    def _log(self, lines):
        os.makedirs(os.path.join(self.dir, "logs"), exist_ok=True)
        with open(os.path.join(self.dir, "logs", "Log_2026-09-29.txt"), "w") as f:
            f.write("\n".join(lines) + "\n")
        return os.path.join(self.dir, "logs")

    def test_serial_state_follows_the_usb_swap_recorded_on_vpu_home(self):
        unplugged = [
            "2026-09-29 19:27:15 UTC - Main - Local BotServer - Serial thread started, Baudrate:19200",
            "2026-09-29 19:28:05 UTC - Main - Local BotServer - Serial thread error:The operation was canceled.",
            "2026-09-29 19:28:05 UTC - Main - Local BotServer - Serial Thread Stopped",
            "2026-09-29 19:28:10 UTC - Main - USB/Serial Manager - SER BOT failed to connect",
            "2026-09-29 19:28:15 UTC - Main - USB/Serial Manager - SER BOT failed to connect",
        ]
        s = c.read_sc3_serial_state(self._log(unplugged))
        self.assertEqual((s["state"], s["failures"], s["at"]), ("failing", 3, "2026-09-29T19:28:15Z"))
        replugged = unplugged + [
            "2026-09-29 19:28:25 UTC - Main - Local BotServer - Serial thread started, Baudrate:19200"]
        s = c.read_sc3_serial_state(self._log(replugged))
        self.assertEqual((s["state"], s["failures"]), ("open", 0))

    def test_config_problem_from_the_device_mismatch_recorded_on_vpu_home(self):
        run = [
            "2026-09-29 21:00:21 UTC - Main - Bot Configuration - Configuration Started",
            "2026-09-29 21:00:21 UTC - Main - Bot Configuration - ScoreLinkII USB Mode",
            "2026-09-29 21:00:29 UTC - Main - Local BotServer - Serial thread started, Baudrate:19200",
            "2026-09-29 21:29:16 UTC - Main - Bot Configuration - Configuration Started",
            "2026-09-29 21:29:16 UTC - Main - Bot Configuration - ScoreLink USB Mode",
            "2026-09-29 21:29:16 UTC - Main - Bot Configuration - Configuration problem: Unable to communicate "
            "with the selector chip in the bot. Please retry the bot configuration.",
            "2026-09-29 21:29:22 UTC - Main - Local BotServer - Serial thread started, Baudrate:19200",
        ]
        s = c.read_sc3_serial_state(self._log(run))
        self.assertEqual((s["state"], s["configMode"], s["configAt"]), ("open", "ScoreLink", "2026-09-29T21:29:16Z"))
        self.assertTrue(s["configProblem"].startswith("Unable to communicate with the selector chip"))
        # Switching back to ScoreLinkII: a clean run clears the problem.
        fixed = run + ["2026-09-29 21:29:52 UTC - Main - Bot Configuration - Configuration Started",
                       "2026-09-29 21:29:52 UTC - Main - Bot Configuration - ScoreLinkII USB Mode"]
        s = c.read_sc3_serial_state(self._log(fixed))
        self.assertEqual((s["configMode"], s["configProblem"]), ("ScoreLinkII", None))

    def test_serial_state_unknown_without_a_log(self):
        self.assertEqual(c.read_sc3_serial_state(os.path.join(self.dir, "none"))["state"], "unknown")

    def test_backup_keeps_the_last_ten(self):
        src = self._write("settings.json", "{}")
        bdir = os.path.join(self.dir, "bk")
        from datetime import datetime, timedelta
        t0 = datetime(2026, 9, 29, 12, 0, 0)
        for i in range(12):
            c.backup_settings(bdir, src, now=t0 + timedelta(seconds=i))
        self.assertEqual(len(os.listdir(bdir)), 10)

    def test_backup_failure_refuses(self):
        with self.assertRaises(c.Sc3Error):
            c.backup_settings(os.path.join(self.dir, "bk"), os.path.join(self.dir, "missing.json"))


class Configure(unittest.TestCase):
    """configure() against the demo SC III, which answers with vpu-home's shapes."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.sc3 = c.DemoSc3(CATALOG)
        self.prev = os.path.join(self.dir, "prev.json")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _go(self, **req):
        base = {"vendorSportId": 180, "vendorConfigurationId": 11,
                "botNumber": 51244, "deviceType": "ScoreLinkII"}
        base.update(req)
        return c.configure(self.sc3, base, self.dir, self.prev,
                           read_settings=lambda _p: self.sc3.settings(),
                           backup=lambda d, s: "backup", sleep=lambda _s: None)

    def test_empty_device_list_triggers_discovery_first(self):
        self.assertEqual(self.sc3.devices, [])
        r = self._go(vendorSportId=10, vendorConfigurationId=17)   # Electro-Mech Football, Wired
        self.assertTrue(r["ok"], r)
        self.assertTrue(r["discovered"])
        self.assertEqual(r["after"]["vendorName"], "ElectroMech V2")
        self.assertEqual(r["after"]["vendorConfigurationName"], "Wired")

    def test_incomplete_wireless_is_refused_and_nothing_changes(self):
        r = self._go(vendorConfigurationId=12)   # Daktronics Wireless, no group/channel
        self.assertFalse(r["ok"])
        self.assertIn("additional properties", r["warningMessage"])
        self.assertEqual([f["key"] for f in r["requiredFields"]], ["group", "channel", "externalAntenna"])
        self.assertEqual(self.sc3.cfg["vendorSportId"], 180)
        self.assertFalse(os.path.exists(self.prev), "a refused save must not replace the restore point")

    def test_connection_type_of_another_vendor_is_refused(self):
        r = self._go(vendorSportId=10, vendorConfigurationId=11)   # Electro-Mech sport, Daktronics Wired id
        self.assertFalse(r["ok"])

    def test_previous_setup_is_kept_and_restores(self):
        r = self._go(vendorSportId=10, vendorConfigurationId=17)
        self.assertTrue(r["ok"])
        prev = c.load_previous(self.prev)
        self.assertEqual(prev["setup"]["vendorSportName"], "Daktronics 3000 Football")
        r2 = c.configure(self.sc3, c.restore_request(prev), self.dir, self.prev,
                         read_settings=lambda _p: self.sc3.settings(),
                         backup=lambda d, s: "backup", sleep=lambda _s: None)
        self.assertTrue(r2["ok"])
        self.assertEqual(self.sc3.cfg["vendorSportId"], 180)

    def test_backup_failure_stops_the_write(self):
        def boom(d, s):
            raise c.Sc3Error("disk full")
        with self.assertRaises(c.Sc3Error):
            c.configure(self.sc3, {"vendorSportId": 10, "vendorConfigurationId": 17, "botNumber": 0,
                                   "deviceType": "ScoreLink"}, self.dir, self.prev,
                        read_settings=None, backup=boom, sleep=lambda _s: None)
        self.assertEqual(self.sc3.cfg["vendorSportId"], 180)

    def test_request_validation(self):
        for bad, msg in (({"deviceType": "USB"}, "ScoreLink"),
                         ({"botNumber": 100000}, "0 to 99999"),
                         ({"vendorSportId": "x"}, "whole number")):
            req = {"vendorSportId": 10, "vendorConfigurationId": 17, "botNumber": 0, "deviceType": "ScoreLink"}
            req.update(bad)
            with self.assertRaises(ValueError) as cm:
                c.validate_request(req)
            self.assertIn(msg, str(cm.exception))


class Chain(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "chain.json")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_confirm_clear_and_reject_unknown(self):
        basis = {"vendorName": "Daktronics", "scoreLinkModel": None}
        ch = c.save_chain(self.path, {}, {"cable": "gray", "controller": "daktronics", "model": "dak-5000"}, basis,
                          allowed={"model": ("dak-5000",)})
        self.assertEqual(ch["cable"]["value"], "gray")
        ch = c.save_chain(self.path, c.load_chain(self.path), {"cable": None}, basis)
        self.assertNotIn("cable", ch)
        with self.assertRaises(ValueError):
            c.save_chain(self.path, ch, {"cable": "purple"}, basis)
        with self.assertRaises(ValueError):
            c.save_chain(self.path, ch, {"wifi": "yes"}, basis)
        with self.assertRaises(ValueError):
            c.save_chain(self.path, ch, {"model": "made-up"}, basis, allowed={"model": ("dak-5000",)})
        with self.assertRaises(ValueError):
            c.save_chain(self.path, ch, {"cable": "multitip"}, basis)

    def test_vendor_change_marks_console_and_cable_stale(self):
        ch = c.save_chain(self.path, {}, {"cable": "gray", "controller": "daktronics", "device": "ScoreLinkII"},
                          {"vendorName": "Daktronics", "scoreLinkModel": None})
        out = c.chain_with_staleness(ch, {"vendorName": "Fairplay", "scoreLinkModel": None})
        self.assertTrue(out["cable"]["stale"])
        self.assertTrue(out["controller"]["stale"])
        self.assertFalse(out["device"]["stale"])
        out = c.chain_with_staleness(ch, {"vendorName": "Daktronics", "scoreLinkModel": None})
        self.assertFalse(any(v["stale"] for v in out.values()))


class ConsoleGuide(unittest.TestCase):
    """SC_CONSOLES is the article's chart in data form."""

    @classmethod
    def setUpClass(cls):
        import main
        cls.consoles, cls.tips = main.SC_CONSOLES, main.SC_BRAND_TIPS

    def test_ids_unique_and_fields_known(self):
        ids = [x["id"] for x in self.consoles]
        self.assertEqual(len(ids), len(set(ids)))
        for x in self.consoles:
            self.assertIn(x["brand"], c.CHAIN_FIELDS["controller"], x["id"])
            self.assertIn(x["tip"], (None, "wireless") + c.CHAIN_FIELDS["cable"], x["id"])
            if x["tip"] in ("gray", "red", "bnc", "custom"):
                self.assertTrue(x.get("port"), x["id"] + " needs a port to name")
                self.assertIn(x.get("extension"), ("trs", "coax", "none"), x["id"])
            if x["tip"] is None:
                self.assertTrue(x.get("note"), x["id"] + " needs the school's options")

    def test_bench_proven_row(self):
        # vpu-home 2026-09-29: All Sport 5000, gray tip, J port, data present.
        row = next(x for x in self.consoles if x["id"] == "dak-5000")
        self.assertEqual((row["tip"], row["port"]), ("gray", "J1, J2 or J3 on the back"))

    def test_brand_tips_agree_with_their_models(self):
        for brand, tip in self.tips.items():
            wired = [x for x in self.consoles if x["brand"] == brand and x["tip"] in ("gray", "red", "bnc")]
            self.assertTrue(wired and all(x["tip"] == tip for x in wired), brand)

    def test_nevco_extension_is_coax(self):
        self.assertEqual(next(x for x in self.consoles if x["id"] == "nv-mpc")["extension"], "coax")


class CopyContract(unittest.TestCase):
    """Every break and symptom the page can pick has words in main.py, and
    every placeholder in those words is one the page fills."""

    @classmethod
    def setUpClass(cls):
        import main
        cls.copy = main.SC_CHAIN_COPY
        with open(os.path.join(_APP_DIR, "static", "app.js"), encoding="utf-8") as f:
            js = f.read()
        start = js.index("// ── ScoreConnect chain ──")
        cls.js = js[start:js.index("// ── SC III Live Score Polling", start)]

    def test_every_break_the_page_raises_has_copy(self):
        codes = set()
        for call in re.findall(r"\badd\(([^;]*)\);", self.js):
            codes |= set(re.findall(r'"([a-z][a-z0-9-]*)"', call))
        self.assertGreaterEqual(len(codes), 10, codes)
        missing = sorted(code for code in codes if code not in self.copy["breaks"])
        self.assertEqual(missing, [], "break codes raised in app.js with no SC_CHAIN_COPY entry")

    def test_placeholders_are_all_filled(self):
        m = re.search(r"function _sccFills\(data, parts\) \{(.*?)\n\}", self.js, re.S)
        filled = set(re.findall(r"^\s{4}(\w+):", m.group(1), re.M))
        texts = []
        for b in self.copy["breaks"].values():
            texts += [b["title"], b["say"]]
        for s in self.copy["symptoms"].values():
            texts += s["checks"]
        texts.append(self.copy["legacy"])
        used = set()
        for t in texts:
            used |= set(re.findall(r"\{(\w+)\}", t))
        self.assertEqual(sorted(used - filled), [])

    def test_break_tones_are_verdict_words(self):
        for code, b in self.copy["breaks"].items():
            self.assertIn(b["tone"], ("critical", "warning", "soon", "info"), code)
            self.assertTrue(set(b["where"]) <= {"vpu", "usb", "device", "cable", "extension", "controller"}, code)


if __name__ == "__main__":
    unittest.main()
