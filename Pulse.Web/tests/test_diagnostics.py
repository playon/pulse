"""Unit tests for Pulse's pure-Python diagnostic logic.

Runs with the standard library only — no pytest, no extra deps — so it
works on a locked-down VPU or any checkout:

    cd Pulse.Web && .venv/bin/python -m unittest discover -s tests -v
    # or:  python3 -m unittest discover -s tests

These cover the finding/compatibility/parsing logic that is easy to break
silently when multiple sessions edit main.py and powershell.py. They do NOT
exercise PowerShell or the network — pure functions only.
"""

import os
import sys
import unittest

# Make `app/` importable (mirrors how main.py puts itself on sys.path).
_APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import main  # noqa: E402
import powershell  # noqa: E402


def _finding_text(f):
    """Everything a finding tells the reader: the body, the venue-IT line,
    the evidence and the per-row details. Findings carry their facts in
    whichever of these fits the audience, so assert against all of them."""
    return " ".join([f.get("recommendation") or "", f.get("it") or "",
                     f.get("evidence") or ""] + list(f.get("details") or []))


# ── Version comparison (GPU compat caps) ─────────────────────
class TestVersionCompare(unittest.TestCase):
    def test_wildcard_cap_allows_any_patch(self):
        self.assertFalse(main._version_exceeds_cap("5.2.0", "5.2.x"))
        self.assertFalse(main._version_exceeds_cap("5.2.99", "5.2.x"))

    def test_wildcard_cap_blocks_higher_minor_or_major(self):
        self.assertTrue(main._version_exceeds_cap("5.3.0", "5.2.x"))
        self.assertTrue(main._version_exceeds_cap("6.0.0", "5.2.x"))
        self.assertTrue(main._version_exceeds_cap("5.13.6", "5.2.x"))

    def test_wildcard_cap_allows_lower(self):
        self.assertFalse(main._version_exceeds_cap("5.1.99", "5.2.x"))
        self.assertFalse(main._version_exceeds_cap("4.99.0", "5.2.x"))

    def test_exact_cap_boundary(self):
        self.assertFalse(main._version_exceeds_cap("2.66.17", "2.66.17"))  # equal = OK
        self.assertFalse(main._version_exceeds_cap("2.66.16", "2.66.17"))
        self.assertTrue(main._version_exceeds_cap("2.66.18", "2.66.17"))
        self.assertTrue(main._version_exceeds_cap("2.67.0", "2.66.17"))

    def test_empty_inputs_never_exceed(self):
        self.assertFalse(main._version_exceeds_cap("", "5.2.x"))
        self.assertFalse(main._version_exceeds_cap("5.2.0", ""))

    def test_suffix_tolerance(self):
        # Beta/suffix tags shouldn't crash the parser.
        self.assertFalse(main._version_exceeds_cap("5.2.0-beta", "5.2.x"))


# ── US timezone allowlist ────────────────────────────────────
class TestUsTimezone(unittest.TestCase):
    def test_us_standard_names_accepted(self):
        for tz in ("Eastern Standard Time", "Central Standard Time",
                   "Mountain Standard Time", "Pacific Standard Time",
                   "US Mountain Standard Time", "US Eastern Standard Time",
                   "Alaskan Standard Time", "Aleutian Standard Time",
                   "Hawaiian Standard Time"):
            self.assertTrue(main._is_us_timezone(tz, ""), tz)

    def test_non_us_rejected(self):
        for tz in ("Israel Standard Time", "GMT Standard Time", "UTC",
                   "Tokyo Standard Time", "Central Europe Standard Time",
                   "Central America Standard Time", "Pacific Standard Time (Mexico)",
                   "Atlantic Standard Time"):
            self.assertFalse(main._is_us_timezone(tz, ""), tz)

    def test_caption_fallback(self):
        self.assertTrue(main._is_us_timezone("", "(UTC-05:00) Eastern Time (US & Canada)"))
        self.assertTrue(main._is_us_timezone("", "(UTC-09:00) Alaska"))
        self.assertTrue(main._is_us_timezone("", "(UTC-07:00) Arizona"))
        self.assertFalse(main._is_us_timezone("", "(UTC+02:00) Jerusalem"))

    def test_empty_is_not_us(self):
        self.assertFalse(main._is_us_timezone("", ""))


# ── GPU compatibility matrix ─────────────────────────────────
def _identity(version, os_caption="Microsoft Windows 10 IoT Enterprise LTSC", build="19044"):
    return {
        "pixellot": {"version": version},
        "operatingSystem": {"caption": os_caption, "buildNumber": build},
    }


def _gpu(arch):
    return {"primaryArchitecture": arch}


class TestPixellotCompat(unittest.TestCase):
    def test_pascal_caps_at_52x(self):
        r = main._check_pixellot_compatibility(_identity("5.13.6"), _gpu("Pascal"))
        self.assertEqual(r["status"], "over")
        self.assertEqual(r["maxVersion"], "5.2.x")

    def test_pascal_within_cap_ok(self):
        r = main._check_pixellot_compatibility(_identity("5.2.4"), _gpu("Pascal"))
        self.assertEqual(r["status"], "ok")

    def test_turing_unlimited(self):
        r = main._check_pixellot_compatibility(_identity("5.13.6"), _gpu("Turing"))
        self.assertEqual(r["status"], "ok")
        self.assertIsNone(r["maxVersion"])

    def test_maxwell_caps_at_26617(self):
        r = main._check_pixellot_compatibility(_identity("5.13.6"), _gpu("Maxwell"))
        self.assertEqual(r["status"], "over")
        self.assertEqual(r["maxVersion"], "2.66.17")

    def test_volta_is_anomaly(self):
        r = main._check_pixellot_compatibility(_identity("5.13.6"), _gpu("Volta"))
        self.assertEqual(r["status"], "anomaly")

    def test_win8_caps_regardless_of_gpu(self):
        ident = _identity("5.13.6", os_caption="Microsoft Windows 8.1 Pro", build="9600")
        r = main._check_pixellot_compatibility(ident, _gpu("Turing"))
        self.assertEqual(r["status"], "over")
        self.assertEqual(r["maxVersion"], "2.66.17")

    def test_no_gpu(self):
        r = main._check_pixellot_compatibility(_identity("5.13.6"), {"primaryArchitecture": "None"})
        self.assertEqual(r["status"], "no-gpu")

    def test_missing_pixellot_version_skips(self):
        r = main._check_pixellot_compatibility(_identity(None), _gpu("Pascal"))
        self.assertEqual(r["status"], "skip")


# ── OS lifecycle ─────────────────────────────────────────────
class TestOsLifecycle(unittest.TestCase):
    def test_known_builds_have_eos(self):
        for build in ("17763", "19044"):
            lc = main._os_lifecycle(build)
            self.assertIsNotNone(lc, build)
            self.assertIn("eosDate", lc)
            self.assertIn("daysToEos", lc)

    def test_unknown_build_returns_none(self):
        self.assertIsNone(main._os_lifecycle("19045"))  # 22H2 — not an LTSC we track
        self.assertIsNone(main._os_lifecycle(None))


# ── Total RAM resolution ─────────────────────────────────────
class TestTotalRam(unittest.TestCase):
    def test_prefers_dimm_sum(self):
        hw = {"memory": [{"capacityGB": 16}, {"capacityGB": 16}]}
        self.assertEqual(main._total_ram_gb(hw, None), 32.0)

    def test_falls_back_to_performance_total_mb(self):
        self.assertEqual(main._total_ram_gb({"memory": []}, {"memory": {"totalMB": 32768}}), 32.0)

    def test_zero_when_no_source(self):
        self.assertEqual(main._total_ram_gb(None, None), 0.0)


# ── Concerning-software detection ────────────────────────────
class TestConcerningSoftware(unittest.TestCase):
    def _sw(self, *names):
        return {"software": [{"displayName": n, "displayVersion": "1.0"} for n in names]}

    def test_security_av_detected(self):
        out = main._detect_concerning_software(self._sw("CrowdStrike Falcon Sensor"))
        self.assertEqual(len(out["security"]), 1)

    def test_clean_box_no_hits(self):
        out = main._detect_concerning_software(self._sw("Google Chrome", "7-Zip 23.01 (x64)"))
        self.assertEqual(sum(len(v) for v in out.values()), 0)

    def test_categories_route_correctly(self):
        out = main._detect_concerning_software(
            self._sw("qBittorrent", "CCleaner", "TeamViewer", "Steam"))
        self.assertEqual(len(out["torrent"]), 1)
        self.assertEqual(len(out["system_cleaner"]), 1)
        self.assertEqual(len(out["alt_remote"]), 1)
        self.assertEqual(len(out["game_platform"]), 1)

    def test_error_payload_is_safe(self):
        self.assertEqual(
            sum(len(v) for v in main._detect_concerning_software({"error": True}).values()), 0)


# ── _compute_findings integration (the high-churn function) ──
class TestComputeFindings(unittest.TestCase):
    def _titles(self, **kwargs):
        return {f["title"] for f in main._compute_findings(**kwargs)}

    def test_clean_system_no_findings(self):
        # Healthy: US tz, 32GB, Turing GPU running a capped version, no bad SW.
        # Build 17763 (LTSC 2019) — EOS 2029, far enough out that the OS
        # lifecycle warning does not fire. (19044/21H2 would, by design.)
        ident = _identity("5.2.0", build="17763")
        ident["timezoneId"] = "Eastern Standard Time"
        ident["uptime"] = {"totalSeconds": 3600}
        titles = self._titles(
            identity=ident,
            performance={"cpu": {"usagePercent": 20}, "memory": {"usedPercent": 40},
                         "disk": {"usedPercent": 50}},
            services={"services": []},
            nics={"ports": []},
            hardware={"memory": [{"capacityGB": 16}, {"capacityGB": 16}],
                      "gpus": [{"vendor": "NVIDIA", "isDedicated": True}]},
            installed_sw={"software": [{"displayName": "Google Chrome"}]},
            gpu_info=_gpu("Turing"),
        )
        self.assertEqual(titles, set())

    def test_low_ram_flagged(self):
        titles = self._titles(
            identity=_identity("5.2.0"),
            performance={}, services={}, nics={},
            hardware={"memory": [{"capacityGB": 8}, {"capacityGB": 8}],
                      "gpus": [{"vendor": "NVIDIA", "isDedicated": True}]},
            gpu_info=_gpu("Turing"),
        )
        self.assertIn("Not enough memory for a VPU", titles)

    def test_no_dedicated_gpu_flagged(self):
        titles = self._titles(
            identity=_identity("5.2.0"),
            performance={}, services={}, nics={},
            hardware={"memory": [{"capacityGB": 16}, {"capacityGB": 16}],
                      "gpus": [{"vendor": "Intel", "isDedicated": False}]},
            gpu_info=_gpu("Turing"),
        )
        self.assertIn("No dedicated graphics card, so this is the wrong hardware for a VPU", titles)

    def test_findings_have_required_shape(self):
        # Every finding must carry severity + title so the dashboard can render it.
        findings = main._compute_findings(
            identity=_identity("5.13.6"),  # Pascal over-cap
            performance={}, services={}, nics={},
            hardware={"gpus": [{"vendor": "NVIDIA", "isDedicated": True}]},
            gpu_info=_gpu("Pascal"),
        )
        self.assertTrue(findings)
        for f in findings:
            # "info" is a first-class severity, not a leak: the dashboard styles
            # it (.finding-dot-info / .finding-cat-info / .sev-chip-info) and the
            # findings list is sorted, not severity-filtered. It exists so a
            # reassuring result — e.g. os-mainstream-eos, "Windows mainstream
            # support ends soon but this VPU stays covered" — can be stated
            # plainly instead of being dressed up as a warning.
            self.assertIn(f.get("severity"), ("critical", "warning", "info"), f)
            self.assertTrue(f.get("title"), f)

    def test_no_duplicate_findings(self):
        findings = main._compute_findings(
            identity=_identity("5.13.6"),
            performance={}, services={}, nics={},
            hardware={"gpus": [{"vendor": "Intel", "isDedicated": False}]},
            gpu_info=_gpu("Pascal"),
        )
        keys = [(f.get("category", ""), f["title"]) for f in findings]
        self.assertEqual(len(keys), len(set(keys)), "duplicate findings present")

    # ── OCR slow-port flicker (ARP-independent guard) ──
    # The OCR/scoreboard camera is natively 100 Mbps. Its NIC neighbor entry
    # ages out when the camera is quiet, so a cold poll showed its port with
    # an empty ARP list and the dashboard wrongly flagged it "running slow";
    # the next poll re-warmed ARP and the finding vanished. A CGI probe
    # confirms the OCR regardless of ARP, so it must suppress the flag.
    def _ocr_probe(self):
        return {"00:D0:89:1B:03:01": {
            "mac": "00:D0:89:1B:03:01", "ip": "169.254.16.52",
            "is_ocr": True, "modelNumber": "R2SD-G"}}

    def test_ocr_port_not_flagged_when_probe_confirms_despite_cold_arp(self):
        nics = {"ports": [
            {"name": "Ethernet 29", "status": "Up", "linkSpeedMbps": 100,
             "mac": "A4:4C:C8:00:00:03", "arpEntries": []},
        ]}
        titles = self._titles(
            identity=_identity("5.2.0"), performance={}, services={},
            nics=nics, probe_results=self._ocr_probe(),
        )
        self.assertFalse(any("running slow" in t for t in titles), titles)

    def test_slow_port_flagged_without_probe_results(self):
        # No probe ran (e.g. a caller that doesn't pass probe_results): the
        # ARP-only path is preserved and a sub-gigabit port is still flagged.
        nics = {"ports": [
            {"name": "Ethernet 29", "status": "Up", "linkSpeedMbps": 100,
             "mac": "A4:4C:C8:00:00:03", "arpEntries": []},
        ]}
        titles = self._titles(
            identity=_identity("5.2.0"), performance={}, services={}, nics=nics,
        )
        self.assertTrue(any("running slow" in t for t in titles), titles)

    def test_degraded_main_camera_flagged_even_with_ocr_present(self):
        # A gigabit main camera negotiated down to 100 Mbps is a real fault and
        # must still flag, even though the box also has a confirmed OCR.
        nics = {"ports": [
            {"name": "Ethernet 28", "status": "Up", "linkSpeedMbps": 100,
             "mac": "A4:4C:C8:00:00:02",
             "arpEntries": [{"ip": "169.254.16.50", "mac": "00:D0:89:18:CE:E8"}]},
        ]}
        titles = self._titles(
            identity=_identity("5.2.0"), performance={}, services={},
            nics=nics, probe_results=self._ocr_probe(),
        )
        self.assertTrue(any("running slow" in t for t in titles), titles)


# ── Missing-main-cameras finding: probe-aware + cold-start grace ──
class TestCamCountFinding(unittest.TestCase):
    """The cam-none/cam-partial finding must not trust the ARP snapshot
    alone. On a cold start (Pulse just launched, cameras quiet), neighbor
    entries have aged out AND the CGI probes can starve under the collection
    burst — the ARP-only count read zero and fired a false CRITICAL
    "No main cameras detected" on VPU2 (2026-07-28) minutes before a demo."""

    def setUp(self):
        self._saved_start = main._PROCESS_START_MONO
        self._saved_tracker = main._PORT_STATE_TRACKER
        main._PORT_STATE_TRACKER = {}

    def tearDown(self):
        main._PROCESS_START_MONO = self._saved_start
        main._PORT_STATE_TRACKER = self._saved_tracker

    def _expire_grace(self):
        main._PROCESS_START_MONO = (
            main.time.monotonic() - main._STARTUP_GRACE_SECONDS - 1
        )

    def _enter_grace(self):
        main._PROCESS_START_MONO = main.time.monotonic()

    @staticmethod
    def _cam_findings(nics, probe_results=None, expected=2):
        findings = main._compute_findings(
            identity=_identity("5.2.0"), performance={}, services={},
            nics=nics,
            expectations={"expectedMainCameras": expected},
            probe_results=probe_results,
        )
        return [f for f in findings if f.get("code") in ("cam-none", "cam-partial")]

    @staticmethod
    def _up_port(name="Ethernet 28", mac="A4:4C:C8:00:00:02", arp=None):
        return {"name": name, "status": "Up", "linkSpeedMbps": 1000,
                "mac": mac, "arpEntries": arp or []}

    @staticmethod
    def _main_probes():
        # Two Z4SF-5 mains answering CGI on the default main IPs.
        return {
            "00:D0:89:18:CE:E8": {"mac": "00:D0:89:18:CE:E8",
                                  "ip": "169.254.16.50", "is_ocr": False,
                                  "modelNumber": "Z4SF-5"},
            "00:D0:89:18:CE:F4": {"mac": "00:D0:89:18:CE:F4",
                                  "ip": "169.254.16.51", "is_ocr": False,
                                  "modelNumber": "Z4SF-5"},
        }

    def test_probe_confirmed_mains_suppress_cam_none_despite_cold_arp(self):
        # ARP aged out on every port, but both mains answered the CGI probe:
        # no camera finding, even long after startup.
        self._expire_grace()
        nics = {"ports": [self._up_port(), self._up_port("Ethernet 31", "A4:4C:C8:00:00:04")]}
        self.assertEqual(self._cam_findings(nics, self._main_probes()), [])

    def test_ocr_probe_does_not_count_toward_main_total(self):
        self._expire_grace()
        nics = {"ports": [self._up_port()]}
        ocr_only = {"00:D0:89:1B:03:01": {
            "mac": "00:D0:89:1B:03:01", "ip": "169.254.16.52",
            "is_ocr": True, "modelNumber": "R2SD-G"}}
        found = self._cam_findings(nics, ocr_only)
        self.assertEqual(len(found), 1, found)
        self.assertEqual(found[0]["code"], "cam-none")

    def test_cold_start_zero_with_live_link_suppressed_in_grace(self):
        # The VPU2 incident: empty ARP, probes ran but none answered, ports
        # linked, seconds after launch — must NOT fire the critical.
        self._enter_grace()
        nics = {"ports": [self._up_port()]}
        self.assertEqual(self._cam_findings(nics, probe_results={}), [])

    def test_zero_with_live_link_fires_after_grace(self):
        # Same reading out of the grace window is a real alarm.
        self._expire_grace()
        nics = {"ports": [self._up_port()]}
        found = self._cam_findings(nics, probe_results={})
        self.assertEqual(len(found), 1, found)
        self.assertEqual(found[0]["code"], "cam-none")
        self.assertEqual(found[0]["severity"], "critical")

    def test_zero_with_all_ports_down_fires_even_in_grace(self):
        # Down links are trustworthy — nothing is connected. Alarm at once.
        self._enter_grace()
        nics = {"ports": [{"name": "Ethernet 28", "status": "Disconnected",
                           "linkSpeedMbps": None, "mac": "A4:4C:C8:00:00:02",
                           "arpEntries": []}]}
        found = self._cam_findings(nics, probe_results={})
        self.assertEqual(len(found), 1, found)
        self.assertEqual(found[0]["code"], "cam-none")

    def test_no_probe_context_keeps_legacy_arp_behavior_in_grace(self):
        # Callers that never probe (probe_results=None) are not subject to
        # the grace suppression — ARP-only counting stands.
        self._enter_grace()
        nics = {"ports": [self._up_port()]}
        found = self._cam_findings(nics, probe_results=None)
        self.assertEqual(len(found), 1, found)
        self.assertEqual(found[0]["code"], "cam-none")

    def test_partial_count_still_warns_in_grace(self):
        # One of two mains confirmed by probe: cam-partial fires (warning)
        # even inside the grace window — suppression is only for the
        # nothing-anywhere cold-start signature.
        self._enter_grace()
        nics = {"ports": [self._up_port()]}
        one_main = {"00:D0:89:18:CE:E8": {
            "mac": "00:D0:89:18:CE:E8", "ip": "169.254.16.50",
            "is_ocr": False, "modelNumber": "Z4SF-5"}}
        found = self._cam_findings(nics, one_main)
        self.assertEqual(len(found), 1, found)
        self.assertEqual(found[0]["code"], "cam-partial")
        self.assertEqual(found[0]["severity"], "warning")

    def test_arp_count_still_works_without_probes(self):
        # Two mains present in ARP on default IPs, no probes: no finding.
        self._expire_grace()
        nics = {"ports": [
            self._up_port(arp=[{"ip": "169.254.16.50", "mac": "00:D0:89:18:CE:E8"}]),
            self._up_port("Ethernet 31", "A4:4C:C8:00:00:04",
                          arp=[{"ip": "169.254.16.51", "mac": "00:D0:89:18:CE:F4"}]),
        ]}
        self.assertEqual(self._cam_findings(nics, probe_results=None), [])

    def test_slow_port_cold_start_ambiguity_suppressed_in_grace(self):
        # Companion false finding from the same incident: the OCR port at
        # 100 Mbps with empty ARP and probes-ran-but-empty must not flag
        # "running slow" during the grace window.
        self._enter_grace()
        nics = {"ports": [
            {"name": "Ethernet 29", "status": "Up", "linkSpeedMbps": 100,
             "mac": "A4:4C:C8:00:00:03", "arpEntries": []},
        ]}
        findings = main._compute_findings(
            identity=_identity("5.2.0"), performance={}, services={},
            nics=nics, probe_results={},
        )
        self.assertFalse(
            any("running slow" in f["title"] for f in findings), findings)
        # …but out of grace the same reading is a real degraded-link alarm.
        self._expire_grace()
        findings = main._compute_findings(
            identity=_identity("5.2.0"), performance={}, services={},
            nics=nics, probe_results={},
        )
        self.assertTrue(
            any("running slow" in f["title"] for f in findings), findings)


# ── Storage finding: per-volume, not the all-drives aggregate (PULSEDEV-49) ──
class TestStorageFinding(unittest.TestCase):
    """The disk-space alert must evaluate each volume separately. The perf
    aggregate sums all fixed drives, so on the typical fleet box (small C: +
    large D:) a critically full C: averaged out and the alert never fired."""

    def _storage(self, disk_health=None, performance=None):
        findings = main._compute_findings(
            identity=_identity("5.2.0"), performance=performance or {},
            services={}, nics={},
            hardware={"gpus": [{"vendor": "NVIDIA", "isDedicated": True}]},
            gpu_info=_gpu("Turing"), disk_health=disk_health,
        )
        return [f for f in findings if f.get("category") == "Storage"]

    @staticmethod
    def _dh(**vols):
        return {"logicalDisks": [
            {"deviceID": f"{letter}:", "usedPercent": pct}
            for letter, pct in vols.items()
        ]}

    def test_full_c_not_masked_by_empty_d(self):
        # The PULSEDEV-49 regression: C: 92% + near-empty D: gave an aggregate
        # of ~24%, so the old aggregate check stayed silent.
        found = self._storage(
            disk_health=self._dh(C=92, D=24),
            performance={"disk": {"usedPercent": 24}},
        )
        self.assertEqual(len(found), 1, found)
        self.assertEqual(found[0]["severity"], "critical")
        self.assertIn("C:", found[0]["title"])

    def test_full_d_fires_with_vod_advice(self):
        found = self._storage(disk_health=self._dh(C=40, D=91))
        self.assertEqual(len(found), 1, found)
        self.assertEqual(found[0]["severity"], "critical")
        self.assertIn("D:", found[0]["title"])
        self.assertIn("VOD", found[0]["recommendation"])

    def test_no_finding_between_80_and_90(self):
        # c85bdfd removed the 80–90% "space low" warning tier: Storage Cleanup
        # only offers itself at 90%, so a warning below that was noise the tech
        # could do nothing about. Disk fill is critical-only now.
        self.assertEqual(self._storage(disk_health=self._dh(C=84, D=20)), [])

    def test_both_volumes_flagged_independently(self):
        # Guards the PULSEDEV-49 fix: each volume is judged on its own, not on
        # an average. Both volumes are over 90 because that is the only fill
        # tier left — the point is still that TWO findings come back, one per
        # drive, rather than a single aggregate one.
        found = self._storage(disk_health=self._dh(C=92, D=91))
        self.assertEqual(len(found), 2, found)
        self.assertEqual({f["severity"] for f in found}, {"critical"})
        self.assertEqual({"C:" in f["title"] for f in found}, {True, False})

    def test_healthy_volumes_stay_quiet(self):
        self.assertEqual(self._storage(disk_health=self._dh(C=62, D=25)), [])

    def test_aggregate_fallback_when_disk_health_missing(self):
        found = self._storage(performance={"disk": {"usedPercent": 93}})
        self.assertEqual(len(found), 1, found)
        self.assertEqual(found[0]["severity"], "critical")

    def test_aggregate_ignored_when_per_volume_data_exists(self):
        # A bogus-high aggregate must not fire once real per-volume data is in.
        found = self._storage(
            disk_health=self._dh(C=50, D=30),
            performance={"disk": {"usedPercent": 95}},
        )
        self.assertEqual(found, [])

    def test_disk_health_error_falls_back_to_aggregate(self):
        # Still testing the fallback, not the tier: when the per-volume
        # collector errors we must fall back to the performance aggregate. The
        # figure is 93 rather than the old 85 only because 80–90 no longer
        # emits anything (c85bdfd) — the behaviour under test is unchanged.
        found = self._storage(
            disk_health={"error": "collector failed"},
            performance={"disk": {"usedPercent": 93}},
        )
        self.assertEqual(len(found), 1, found)
        self.assertEqual(found[0]["severity"], "critical")

    def test_disk_health_error_with_mid_band_aggregate_stays_quiet(self):
        # The other half of the fallback contract: falling back must not
        # resurrect the retired 80–90 tier.
        self.assertEqual(self._storage(
            disk_health={"error": "collector failed"},
            performance={"disk": {"usedPercent": 85}},
        ), [])


# ── run_ps stdout JSON recovery (the resilience fix) ─────────
class TestExtractJson(unittest.TestCase):
    def test_clean_json(self):
        self.assertEqual(powershell._extract_json('{"a": 1}'), {"a": 1})

    def test_leading_noise_recovered(self):
        # PS leaked a warning line before the JSON — must still recover.
        noisy = 'WARNING: module slow to load\n{"devices": [], "ok": true}'
        self.assertEqual(powershell._extract_json(noisy), {"devices": [], "ok": True})

    def test_multiline_picks_json_line(self):
        blob = "VERBOSE: starting\nVERBOSE: done\n{\"x\": 5}"
        self.assertEqual(powershell._extract_json(blob), {"x": 5})

    def test_unparseable_returns_none(self):
        self.assertIsNone(powershell._extract_json("not json at all"))
        self.assertIsNone(powershell._extract_json(""))
        self.assertIsNone(powershell._extract_json(None))

    def test_array_payload(self):
        self.assertEqual(powershell._extract_json('[1, 2, 3]'), [1, 2, 3])

    def test_literal_control_chars_tolerated(self):
        # Windows PowerShell 5.1's ConvertTo-Json leaves literal C0 bytes
        # unescaped inside strings — e.g. STX/ETX in a raw Daktronics RTD
        # string, or a NUL scraped by findstr from a UTF-16 SC I log. Python's
        # default strict parse rejects these ("Invalid control character"); the
        # extractor must still recover the payload.
        blob = '{"reachable":false,"rawData":"02\x025728\x03","error":null}'
        self.assertEqual(
            powershell._extract_json(blob),
            {"reachable": False, "rawData": "02\x025728\x03", "error": None},
        )


# ── DNS discrepancy classification (PDF #10) ─────────────────
class TestDnsDiscrepancy(unittest.TestCase):
    """A real DNS redirect (system resolver returns an internal IP) must be
    distinguished from benign CDN/GeoDNS load balancing (two different public
    IPs) — the latter is normal and must not warn."""

    def test_private_ip_detection(self):
        for ip in ("10.0.0.5", "192.168.1.1", "172.16.4.9", "169.254.1.1",
                   "127.0.0.1", "100.64.0.1"):
            self.assertTrue(main._is_private_or_bogon_ip(ip), ip)
        for ip in ("52.44.182.199", "143.204.160.127", "8.8.8.8", "1.1.1.1"):
            self.assertFalse(main._is_private_or_bogon_ip(ip), ip)
        for junk in ("", None, "not-an-ip", "example.com"):
            self.assertFalse(main._is_private_or_bogon_ip(junk), junk)

    def _row(self, sys_ip, sys_status, goog_ip, goog_status):
        return ({"resolvedTo": sys_ip, "status": sys_status},
                {"resolvedTo": goog_ip, "status": goog_status})

    def test_cdn_different_public_ips_is_benign(self):
        # The reported false positive: software.pixellot.tv on CloudFront.
        s, g = self._row("143.204.160.127", "pass", "143.204.160.99", "pass")
        self.assertIsNone(main._classify_dns_row(s, g))
        # And the apex domain on different AWS IPs.
        s, g = self._row("52.44.182.199", "pass", "52.1.53.61", "pass")
        self.assertIsNone(main._classify_dns_row(s, g))

    def test_same_ip_is_benign(self):
        s, g = self._row("52.1.53.61", "pass", "52.1.53.61", "pass")
        self.assertIsNone(main._classify_dns_row(s, g))

    def test_redirect_to_internal_ip_flagged(self):
        # Captive portal / SSL-inspection proxy: system returns a private IP.
        s, g = self._row("192.168.1.50", "pass", "52.1.53.61", "pass")
        self.assertEqual(main._classify_dns_row(s, g), "redirect")

    def test_system_blocked_flagged(self):
        s, g = self._row(None, "fail", "52.1.53.61", "pass")
        self.assertEqual(main._classify_dns_row(s, g), "system-blocked")

    def test_google_blocked_flagged(self):
        s, g = self._row("52.1.53.61", "pass", None, "fail")
        self.assertEqual(main._classify_dns_row(s, g), "google-blocked")

    def test_annotate_recomputes_counts(self):
        dns = {"results": [
            {"system": {"resolvedTo": None, "status": "fail"},
             "google": {"resolvedTo": "52.1.53.61", "status": "pass"}},
            {"system": {"resolvedTo": "143.204.160.127", "status": "pass"},
             "google": {"resolvedTo": "143.204.160.99", "status": "pass"}},
            {"system": {"resolvedTo": "192.168.1.50", "status": "pass"},
             "google": {"resolvedTo": "52.1.53.61", "status": "pass"}},
        ]}
        out = main._annotate_dns_resolution(dns)
        self.assertEqual(out["systemBlockedCount"], 1)
        self.assertEqual(out["redirectCount"], 1)
        self.assertEqual([r["discrepancy"] for r in out["results"]],
                         ["system-blocked", None, "redirect"])


# ── Internet reachability derivation ─────────────────────────
class TestInternetReachable(unittest.TestCase):
    """A locked-down venue network blocks ICMP/8.8.8.8 but Pixellot services
    stay reachable. internetReachable must come from real service reachability
    (a passing TCP/443 test), not just the 8.8.8.8 probe."""

    _PORTS_443_PASS = {"results": [
        {"protocol": "TCP", "port": 443, "host": "pixellot.tv",
         "purpose": "Pixellot", "optional": False, "status": "pass"},
    ]}
    _PORTS_443_FAIL = {"results": [
        {"protocol": "TCP", "port": 443, "host": "pixellot.tv",
         "purpose": "Pixellot", "optional": False, "status": "fail"},
    ]}

    def test_probe_success_wins(self):
        cfg = {"internet": {"reachable": True, "testedHost": "8.8.8.8"}}
        self.assertEqual(main._internet_reachable(cfg, None), (True, "8.8.8.8"))

    def test_icmp_blocked_but_443_passes(self):
        # The field case: probe failed, but HTTPS to pixellot.tv works.
        cfg = {"internet": {"reachable": False, "testedHost": None}}
        reachable, host = main._internet_reachable(cfg, self._PORTS_443_PASS)
        self.assertTrue(reachable)
        self.assertEqual(host, "pixellot.tv:443")

    def test_truly_offline(self):
        cfg = {"internet": {"reachable": False, "testedHost": None}}
        self.assertEqual(main._internet_reachable(cfg, self._PORTS_443_FAIL), (False, None))

    def test_optional_443_does_not_count(self):
        cfg = {"internet": {"reachable": False, "testedHost": None}}
        ports = {"results": [{"protocol": "TCP", "port": 443, "host": "x",
                              "optional": True, "status": "pass"}]}
        self.assertEqual(main._internet_reachable(cfg, ports), (False, None))

    def test_missing_ports_falls_back_to_probe(self):
        cfg = {"internet": {"reachable": False, "testedHost": None}}
        self.assertEqual(main._internet_reachable(cfg, None), (False, None))


# ── Wi-Fi uplink finding gating ──────────────────────────────
class TestWifiUplinkFinding(unittest.TestCase):
    """The Wi-Fi warning must fire only when Wi-Fi is the actual internet
    uplink — never for Wi-Fi Direct / virtual adapters that merely show
    'connected'."""

    def _wifi_titles(self, wifi):
        findings = main._compute_findings(
            identity=_identity("5.2.0"), performance={}, services={}, nics={},
            hardware={"gpus": [{"vendor": "NVIDIA", "isDedicated": True}]},
            gpu_info=_gpu("Turing"), wifi=wifi,
        )
        return {f["title"] for f in findings if f.get("category") == "Network"}

    def _has_wifi_finding(self, titles):
        return any("Wi-Fi" in t or "WiFi" in t for t in titles)

    def test_virtual_adapter_does_not_warn(self):
        # The reported false positive: Wi-Fi Direct virtual adapter, connected,
        # but not the uplink. uplinkIsWifi=False → no finding.
        wifi = {
            "uplinkIsWifi": False, "ethernetHasDefaultRoute": True,
            "adapters": [{
                "interfaceDescription": "Microsoft Wi-Fi Direct Virtual Adapter #2",
                "isUp": True, "isVirtual": True, "hasDefaultRoute": False,
                "connected": True, "ssid": "DIRECT-3a-DESKTOP",
            }],
        }
        self.assertFalse(self._has_wifi_finding(self._wifi_titles(wifi)))

    def test_real_wifi_uplink_warns(self):
        # Real Wi-Fi NIC holding the default route, no wired uplink → warn.
        wifi = {
            "uplinkIsWifi": True, "ethernetHasDefaultRoute": False,
            "adapters": [{
                "interfaceDescription": "Intel(R) Wi-Fi 6 AX201 160MHz",
                "isUp": True, "isVirtual": False, "hasDefaultRoute": True,
                "connected": True, "ssid": "Venue-WiFi",
            }],
        }
        self.assertTrue(self._has_wifi_finding(self._wifi_titles(wifi)))

    def test_no_wifi_payload_no_warn(self):
        self.assertFalse(self._has_wifi_finding(self._wifi_titles(None)))
        self.assertFalse(self._has_wifi_finding(self._wifi_titles({"error": True})))


# ── Adapter role classification + "internet on a camera port" ────────
# Fixtures are derived from two real VPU dumps (good config + internet moved
# onto the 4-port camera NIC). On that hardware: motherboard = Intel I219-LM on
# PCI bus 0; the 4-port camera NIC = 4× Intel 82574L on PCI buses 4-7. The
# disconnected port keeps a STALE gateway in the route table in both dumps, so
# the detection must gate on link status — these fixtures lock that in.
class TestAdapterRoles(unittest.TestCase):
    def _adapters(self, mobo_status, cam_uplink_status):
        # mobo = Ethernet 5 (I219-LM, bus 0); Ethernet 28 (82574L, bus 4) is the
        # camera port the internet cable gets moved to; 29/30/31 are normal
        # link-local camera ports.
        return [
            {"name": "Ethernet 5", "interfaceDescription": "Intel(R) Ethernet Connection (7) I219-LM",
             "status": mobo_status, "adminStatus": "Up", "physicalMediaType": "802.3",
             "macAddress": "C8-D9-D2-30-5E-4F", "interfaceIndex": 22, "pciBus": 0},
            {"name": "Ethernet 28", "interfaceDescription": "Intel(R) 82574L Gigabit Network Connection #13",
             "status": cam_uplink_status, "adminStatus": "Up", "physicalMediaType": "802.3",
             "macAddress": "00-30-64-5F-61-86", "interfaceIndex": 23, "pciBus": 4},
            {"name": "Ethernet 29", "interfaceDescription": "Intel(R) 82574L Gigabit Network Connection #14",
             "status": "Up", "adminStatus": "Up", "physicalMediaType": "802.3",
             "macAddress": "00-30-64-5F-61-87", "interfaceIndex": 17, "pciBus": 5},
            {"name": "Ethernet 30", "interfaceDescription": "Intel(R) 82574L Gigabit Network Connection #15",
             "status": "Up", "adminStatus": "Up", "physicalMediaType": "802.3",
             "macAddress": "00-30-64-5F-61-88", "interfaceIndex": 19, "pciBus": 6},
            {"name": "Ethernet 31", "interfaceDescription": "Intel(R) 82574L Gigabit Network Connection #16",
             "status": "Up", "adminStatus": "Up", "physicalMediaType": "802.3",
             "macAddress": "00-30-64-5F-61-89", "interfaceIndex": 25, "pciBus": 7},
        ]

    def _ip_configs(self):
        # Both dumps carry the SAME ip/route rows — including a stale gateway on
        # the camera port (idx 23) — regardless of which port is actually linked.
        return [
            {"interfaceAlias": "Ethernet 5", "interfaceIndex": 22, "ipv4Address": ["192.168.102.196"], "ipv4DefaultGateway": ["192.168.100.1"]},
            {"interfaceAlias": "Ethernet 28", "interfaceIndex": 23, "ipv4Address": ["192.168.101.98"], "ipv4DefaultGateway": ["192.168.100.1"]},
            {"interfaceAlias": "Ethernet 29", "interfaceIndex": 17, "ipv4Address": ["169.254.188.134"], "ipv4DefaultGateway": []},
            {"interfaceAlias": "Ethernet 30", "interfaceIndex": 19, "ipv4Address": ["169.254.18.170"], "ipv4DefaultGateway": []},
            {"interfaceAlias": "Ethernet 31", "interfaceIndex": 25, "ipv4Address": ["169.254.201.146"], "ipv4DefaultGateway": []},
        ]

    def _good(self):  # internet on motherboard (Eth5 Up), camera port Eth28 Disconnected
        return {"adapters": self._adapters("Up", "Disconnected"), "ipConfigurations": self._ip_configs()}

    def _bad(self):  # internet moved to camera port (Eth28 Up), motherboard Eth5 unplugged
        return {"adapters": self._adapters("Disconnected", "Up"), "ipConfigurations": self._ip_configs()}

    def test_roles_by_pci_bus(self):
        cfg = self._good()
        main._classify_network_adapters(cfg)
        roles = {a["name"]: a["role"] for a in cfg["adapters"]}
        self.assertEqual(roles["Ethernet 5"], "motherboard")  # I219-LM on bus 0
        for cam in ("Ethernet 28", "Ethernet 29", "Ethernet 30", "Ethernet 31"):
            self.assertEqual(roles[cam], "camera", cam)  # 82574L on buses 4-7

    def test_wifi_role_by_media_type(self):
        # Same chipset family, on bus 0, but Native 802.11 → wifi, not motherboard.
        cfg = {"adapters": [{"interfaceDescription": "Intel(R) Wireless-AC 9560",
                             "physicalMediaType": "Native 802.11", "pciBus": 0,
                             "status": "Up", "interfaceIndex": 99}]}
        main._classify_network_adapters(cfg)
        self.assertEqual(cfg["adapters"][0]["role"], "wifi")

    def test_good_config_no_false_positive(self):
        # The camera port (Eth28) has a STALE gateway but is Disconnected → must
        # NOT flag. Internet is correctly on the motherboard port.
        self.assertIsNone(main._camera_nic_uplink_finding(self._good()))

    def test_internet_on_camera_port_flags_critical(self):
        f = main._camera_nic_uplink_finding(self._bad())
        self.assertIsNotNone(f)
        self.assertEqual(f["severity"], "critical")
        self.assertIn("camera port", f["title"].lower())
        self.assertIn("Ethernet 28", _finding_text(f))
        self.assertIn("no cable connected", _finding_text(f))  # motherboard cable is out

    def test_motherboard_disabled_note(self):
        cfg = self._bad()
        cfg["adapters"][0]["adminStatus"] = "Down"  # motherboard administratively disabled
        cfg["adapters"][0]["status"] = "Disabled"
        f = main._camera_nic_uplink_finding(cfg)
        self.assertIn("disabled", f["recommendation"].lower())

    def test_finding_surfaces_in_compute_findings(self):
        findings = main._compute_findings(
            identity={}, performance={}, services={}, nics={},
            network_config=self._bad(),
        )
        titles = [f["title"] for f in findings if f.get("category") == "Network"]
        self.assertTrue(any("camera port" in t.lower() for t in titles), titles)

    def test_scalar_gateway_is_handled(self):
        # PowerShell unwraps a single-element array to a scalar, so a one-gateway
        # camera port arrives with ipv4DefaultGateway as a bare STRING, not a
        # list. The finding must still fire and report the whole gateway — not
        # iterate the string's characters (the bug that crashed the real VPU).
        cfg = self._bad()
        for ipc in cfg["ipConfigurations"]:
            if ipc["interfaceIndex"] == 23:  # the up camera port (Ethernet 28)
                ipc["ipv4DefaultGateway"] = "192.168.100.1"   # scalar, not a list
        f = main._camera_nic_uplink_finding(cfg)
        self.assertIsNotNone(f)
        self.assertIn("192.168.100.1", _finding_text(f))  # full gateway, not "1"


# ── Wi-Fi card disabled (Pixellot Connect) ───────────────────────────
# Fixture from a third real VPU dump: internet correctly on the motherboard
# (I219-LM #2 on PCI bus 0), all four 82574L camera ports link-local, and the
# Wi-Fi card (Wireless-AC 9560, Native 802.11) administratively DISABLED. A
# disabled Wi-Fi NIC shows status "Disabled" / adminStatus "Down"; an absent
# card doesn't appear at all (so this never false-fires on Wi-Fi-less units).
class TestWifiDisabled(unittest.TestCase):
    def _cfg(self, wifi_status="Disabled", wifi_admin="Down"):
        return {
            "adapters": [
                {"name": "Ethernet 13", "interfaceDescription": "Intel(R) Ethernet Connection (7) I219-LM #2",
                 "status": "Up", "adminStatus": "Up", "physicalMediaType": "802.3",
                 "macAddress": "9C-7B-EF-26-CB-D5", "interfaceIndex": 41, "pciBus": 0},
                {"name": "Ethernet 31", "interfaceDescription": "Intel(R) 82574L Gigabit Network Connection #16",
                 "status": "Up", "adminStatus": "Up", "physicalMediaType": "802.3",
                 "macAddress": "00-30-64-36-73-AA", "interfaceIndex": 21, "pciBus": 4},
                {"name": "Ethernet 28", "interfaceDescription": "Intel(R) 82574L Gigabit Network Connection #13",
                 "status": "Up", "adminStatus": "Up", "physicalMediaType": "802.3",
                 "macAddress": "00-30-64-36-73-AB", "interfaceIndex": 37, "pciBus": 5},
                {"name": "Wi-Fi", "interfaceDescription": "Intel(R) Wireless-AC 9560 160MHz",
                 "status": wifi_status, "adminStatus": wifi_admin, "physicalMediaType": "Native 802.11",
                 "macAddress": "C8-58-C0-39-4D-D8", "interfaceIndex": 33, "pciBus": 0},
            ],
            "ipConfigurations": [
                {"interfaceAlias": "Ethernet 13", "interfaceIndex": 41, "ipv4Address": ["192.168.101.230"], "ipv4DefaultGateway": ["192.168.100.1"]},
                {"interfaceAlias": "Ethernet 31", "interfaceIndex": 21, "ipv4Address": ["169.254.63.3"], "ipv4DefaultGateway": []},
                {"interfaceAlias": "Ethernet 28", "interfaceIndex": 37, "ipv4Address": ["169.254.16.100"], "ipv4DefaultGateway": []},
            ],
        }

    def test_roles_include_wifi_and_motherboard(self):
        cfg = self._cfg()
        main._classify_network_adapters(cfg)
        roles = {a["name"]: a["role"] for a in cfg["adapters"]}
        self.assertEqual(roles["Ethernet 13"], "motherboard")  # I219-LM on bus 0
        self.assertEqual(roles["Wi-Fi"], "wifi")               # Native 802.11
        self.assertEqual(roles["Ethernet 28"], "camera")       # 82574L on bus 5

    def test_disabled_wifi_warns(self):
        f = main._wifi_disabled_finding(self._cfg())
        self.assertIsNotNone(f)
        self.assertEqual(f["severity"], "warning")
        self.assertIn("Connect", f["recommendation"])
        self.assertIn("Wireless-AC 9560", _finding_text(f))

    def test_enabled_wifi_does_not_warn(self):
        self.assertIsNone(main._wifi_disabled_finding(self._cfg(wifi_status="Up", wifi_admin="Up")))

    def test_internet_on_motherboard_no_camera_finding(self):
        # Internet is on the I219 motherboard port; cameras are link-local — so
        # the camera-NIC finding must stay quiet even though Wi-Fi is disabled.
        self.assertIsNone(main._camera_nic_uplink_finding(self._cfg()))

    def test_compute_findings_warns_wifi_not_camera(self):
        findings = main._compute_findings(
            identity={}, performance={}, services={}, nics={}, network_config=self._cfg())
        net = [(f["severity"], f["title"]) for f in findings if f.get("category") == "Network"]
        self.assertTrue(any("Wi-Fi card is disabled" in t for _, t in net), net)
        self.assertFalse(any("camera port" in t.lower() for _, t in net), net)


# ── DNS UDP/53 probe must not false-fire when resolution works ───────
# Field report: the DNS probe targeted a stale resolver (10.0.0.136) off a
# secondary adapter and failed, raising "can't resolve any hostname" — while
# every domain on the same screen resolved fine. A failed UDP/53 probe must be
# suppressed when names are demonstrably resolving (a hostname-based service
# passed), but still reported when nothing resolves.
class TestDnsProbeFalsePositive(unittest.TestCase):
    def _ports(self, dns_status, pixellot_status):
        return {"results": [
            {"protocol": "UDP", "port": 53, "host": "10.0.0.136", "purpose": "DNS", "optional": False, "status": dns_status},
            {"protocol": "TCP", "port": 443, "host": "pixellot.tv", "purpose": "Pixellot", "optional": False, "status": pixellot_status},
        ]}

    def _net_titles(self, port_tests):
        f = main._compute_findings(identity={}, performance={}, services={}, nics={}, port_tests=port_tests)
        return [x["title"] for x in f if x.get("category") == "Network"]

    def test_dns_probe_fail_suppressed_when_resolution_works(self):
        # DNS UDP/53 fails, but pixellot.tv:443 passed → names resolve → no DNS finding.
        titles = self._net_titles(self._ports("fail", "pass"))
        self.assertFalse(any("DNS" in t for t in titles), titles)

    def test_dns_reported_when_nothing_resolves(self):
        # DNS fails AND no hostname-based service passed → genuine DNS problem, still flag.
        titles = self._net_titles(self._ports("fail", "fail"))
        self.assertTrue(any("blocking name lookups" in t for t in titles), titles)


# ── NTP source allowlist (PDF #9) ────────────────────────────
class TestNtpAllowlist(unittest.TestCase):
    def test_canonical_sources_approved(self):
        for s in ("0.us.pool.ntp.org", "1.us.pool.ntp.org",
                  "2.us.pool.ntp.org", "3.us.pool.ntp.org"):
            self.assertTrue(main._is_approved_ntp_source(s), s)

    def test_case_and_whitespace_tolerant(self):
        self.assertTrue(main._is_approved_ntp_source("2.US.POOL.NTP.ORG"))
        self.assertTrue(main._is_approved_ntp_source("  0.us.pool.ntp.org  "))

    def test_any_us_pool_subdomain_approved(self):
        # The four canonical names are aliases into the same pool.
        self.assertTrue(main._is_approved_ntp_source("custom.us.pool.ntp.org"))

    def test_off_pool_sources_rejected(self):
        for s in ("time.windows.com", "time.nist.gov", "pool.ntp.org",
                  "Local CMOS Clock", "", None):
            self.assertFalse(main._is_approved_ntp_source(s), s)


# ── Demo-data contract (catches demo-vs-real drift) ──────────
class TestDemoDataContract(unittest.TestCase):
    """Every PowerShell script the backend invokes via run_ps must have a
    demo-mode entry, or demo mode silently returns null for that section
    on a non-Windows host. This is the class of bug behind the earlier
    Get-NetworkHealth `remoteHost` mismatch."""

    # Scripts referenced by main.py that intentionally have no demo entry yet.
    # Keep this minimal — each entry is a known gap. Remove an entry once its
    # demo data lands (test_exempt_list_has_no_stale_entries enforces that).
    _DEMO_EXEMPT = set()

    # Side-effect / action scripts: they *do* something (change system state)
    # rather than return diagnostic data, so demo mode has nothing meaningful
    # to mock. Permanently exempt — unlike _DEMO_EXEMPT, these will never gain
    # a demo entry, so they're excluded from the stale-entry guard too.
    _ACTION_SCRIPTS = {
        # Opens a Windows firewall port when the user enables report sharing.
        "Set-PulseShareFirewall.ps1",
        # Reboots the VPU — a side effect, returns no diagnostic data to mock.
        "Reboot-Vpu.ps1",
        # Background uninstallers for Canopy-deployment leftovers, fired at
        # launch and gated on the leftover actually being present. Nothing in
        # the UI consumes their result, so there is nothing to mock.
        "Remove-CanopyLeaf.ps1",
        "Remove-Splashtop.ps1",
    }

    def _referenced_scripts(self):
        import re
        with open(os.path.join(_APP_DIR, "main.py"), encoding="utf-8") as f:
            src = f.read()
        return set(re.findall(r'run_ps\(\s*"([^"]+\.ps1)"', src))

    def test_every_referenced_script_has_demo(self):
        import demo_data
        referenced = self._referenced_scripts()
        missing = referenced - set(demo_data.DEMO) - self._DEMO_EXEMPT - self._ACTION_SCRIPTS
        self.assertEqual(
            missing, set(),
            f"Scripts invoked by main.py with no demo_data entry — demo mode "
            f"returns null for these: {sorted(missing)}",
        )

    def test_exempt_list_has_no_stale_entries(self):
        # If an exempt script gained a demo entry, drop it from the exempt set
        # so the contract stays honest.
        import demo_data
        stale = self._DEMO_EXEMPT & set(demo_data.DEMO)
        self.assertEqual(
            stale, set(),
            f"In _DEMO_EXEMPT but now have demo entries — remove them: {sorted(stale)}",
        )

    def test_demo_entries_callable_and_serializable(self):
        # A demo lambda that raises or returns non-JSON would break demo mode
        # for that section. Each must run with no args and serialize cleanly.
        import json
        import demo_data
        for name, fn in demo_data.DEMO.items():
            with self.subTest(script=name):
                result = fn()
                self.assertIsInstance(result, (dict, list), name)
                json.dumps(result, default=str)


# ── Stream readiness policy ──────────────────────────────────
class TestReadinessPolicy(unittest.TestCase):
    """Guards against the class of bug that shipped to East Henderson (NC) on
    2026-08-10: a `critical` dashboard finding with no entry in the policy
    table silently falls through to `info`, so readiness reported WARN ("will
    likely stream") on a VPU whose graphics, uploads and updates were all
    severed by venue SSL inspection."""

    def test_ssl_inspection_is_a_blocker(self):
        verdict = main._compute_readiness(
            [{"code": "ssl-inspection", "severity": "critical",
              "category": "Network", "title": "t", "recommendation": "r"}]
        )
        self.assertEqual(verdict["status"], "FAIL")
        self.assertEqual([b["code"] for b in verdict["blockers"]], ["ssl-inspection"])

    def test_category_filtering_is_a_blocker(self):
        """The Linewize case (Ohio venue, 2026-08-19): a content filter resets
        the handshake to eight Pixellot-critical hosts. No certificate is
        substituted, so `ssl-inspection` never fires - and before `tls-filtered`
        existed the whole event scored a green PASS with the only clue a soft
        "possible SSL inspection" note on the Network tab."""
        verdict = main._compute_readiness(
            [{"code": "tls-filtered", "severity": "critical",
              "category": "Network", "title": "t", "recommendation": "r"}]
        )
        self.assertEqual(verdict["status"], "FAIL")
        self.assertEqual([b["code"] for b in verdict["blockers"]], ["tls-filtered"])

    def test_support_only_filtering_does_not_gate(self):
        """LogMeIn / python.org blocked is a support headache, not a reason to
        tell a tech tonight's game is at risk."""
        verdict = main._compute_readiness(
            [{"code": "tls-filtered-support", "severity": "warning",
              "category": "Network", "title": "t", "recommendation": "r"}]
        )
        self.assertEqual(verdict["status"], "PASS")

    def test_every_critical_finding_code_is_classified(self):
        # `info` is the default for UNKNOWN codes, which is right for new or
        # unverifiable checks — but a code we ship as `critical` reaching that
        # default means we forgot to classify it. Every critical must be an
        # explicit table entry (blocker, or info/risk with a reason in-line).
        unclassified = sorted(
            code for code in _CRITICAL_FINDING_CODES
            if code not in main._READINESS_POLICY
        )
        self.assertEqual(
            unclassified, [],
            "critical findings missing from _READINESS_POLICY (they silently "
            f"default to `info` and never gate readiness): {unclassified}",
        )



# ── Zero cameras must never read PASS ─────────────────────────────────
class TestNoCamerasNeverPasses(unittest.TestCase):
    """North East (MD) Gym, 2026-09-22, web-v1.3.0: 2 main cameras expected,
    none connected, the venue's internet cable in camera port 2 -- and Stream
    Readiness said PASS "Game-ready". The cold-start guard read port 2's link
    as proof of a camera; the Dashboard never re-collected; and with no
    expected count the check would not have run at all."""

    def setUp(self):
        self._saved_start = main._PROCESS_START_MONO
        self._saved_tracker = main._PORT_STATE_TRACKER
        main._PORT_STATE_TRACKER = {}
        main._PROCESS_START_MONO = main.time.monotonic()  # inside the grace window

    def tearDown(self):
        main._PROCESS_START_MONO = self._saved_start
        main._PORT_STATE_TRACKER = self._saved_tracker

    @staticmethod
    def _port(name, mac, up):
        return {"name": name, "status": "Up" if up else "Disconnected",
                "linkSpeedMbps": 1000 if up else None, "mac": mac, "arpEntries": []}

    def _north_east(self):
        nics = {"ports": [
            self._port("Ethernet 28", "00:30:64:5F:61:86", True),   # the internet cable
            self._port("Ethernet 29", "00:30:64:5F:61:87", False),
            self._port("Ethernet 30", "00:30:64:5F:61:88", False),
            self._port("Ethernet 31", "00:30:64:5F:61:89", False),
        ]}
        cfg = {"adapters": [
            {"name": "Ethernet 5", "interfaceDescription": "Intel(R) Ethernet Connection (7) I219-LM",
             "status": "Disconnected", "adminStatus": "Up", "physicalMediaType": "802.3",
             "macAddress": "E0-D5-5E-00-00-01", "interfaceIndex": 22, "pciBus": 0},
            {"name": "Ethernet 28", "interfaceDescription": "Intel(R) 82574L Gigabit Network Connection #13",
             "status": "Up", "adminStatus": "Up", "physicalMediaType": "802.3",
             "macAddress": "00-30-64-5F-61-86", "interfaceIndex": 23, "pciBus": 4},
        ], "ipConfigurations": [
            {"interfaceAlias": "Ethernet 28", "interfaceIndex": 23, "ipv4DefaultGateway": "10.10.60.1"},
        ]}
        return nics, cfg

    def _findings(self, nics, cfg=None, expected=2, probes=None, identity=None):
        return main._compute_findings(
            identity=identity or _identity("5.37.2"), performance={}, services={}, nics=nics,
            network_config=cfg, probe_results={} if probes is None else probes,
            expectations={"expectedMainCameras": expected} if expected else None)

    def test_internet_cable_link_is_not_camera_evidence(self):
        nics, cfg = self._north_east()
        f = self._findings(nics, cfg)
        cam = [x for x in f if x["code"] == "cam-none"]
        self.assertEqual(len(cam), 1, [x["code"] for x in f])
        self.assertIn("internet cable", " ".join(cam[0]["details"]))
        self.assertIn("carrying the internet cable", cam[0]["recommendation"])
        verdict = main._compute_readiness(f)
        self.assertEqual(verdict["status"], "FAIL")
        self.assertIn("cam-none", [b["code"] for b in verdict["blockers"]])

    def test_zero_cameras_fire_without_an_expected_count(self):
        nics, cfg = self._north_east()
        cam = [x for x in self._findings(nics, cfg, expected=None) if x["code"] == "cam-none"]
        self.assertEqual(len(cam), 1)
        self.assertNotIn("expected", cam[0]["title"])

    def test_non_vpu_host_without_count_stays_quiet(self):
        nics, cfg = self._north_east()
        f = self._findings(nics, cfg, expected=None,
                           identity={**_identity("5.37.2"), "isNonVpuHost": True})
        self.assertEqual([x for x in f if x["code"].startswith("cam-")], [])

    def test_cold_start_on_a_real_camera_link_is_pending_not_pass(self):
        # The VPU2 case (camera links up, caches cold) still doesn't fire the
        # critical, but it no longer reads as a pass either.
        nics = {"ports": [self._port("Ethernet 28", "00:30:64:5F:61:86", True)]}
        f = self._findings(nics)
        self.assertEqual([x["code"] for x in f if x["code"].startswith("cam-")], ["cam-count-pending"])
        self.assertEqual(main._compute_readiness(f)["status"], "WARN")

    def test_camera_tab_carries_the_same_finding(self):
        nics, cfg = self._north_east()
        ports = main._enrich_ports(nics, None, {})
        main._flag_uplink_ports(ports, cfg)
        f = main._camera_count_findings(ports, 2, {}, True)
        self.assertEqual([x["code"] for x in f], ["cam-none"])


class TestMainCameraCount(unittest.TestCase):
    """_count_main_cameras counts each camera once, by MAC, across the
    neighbour table and the CGI probes. It used to take max(ARP, probes)."""

    @staticmethod
    def _port(macs, up=True, ocr=False, uplink=False):
        return {"isUp": up, "isOcr": ocr, "hasInternetUplink": uplink,
                "camerasDetected": [{"mac": m, "role": "Main Camera"} for m in macs]}

    def test_one_camera_under_two_addresses_counts_once(self):
        ports = [self._port(["00-0E-53-AA-01-01"]), self._port(["00:0e:53:aa:01:01"])]
        self.assertEqual(main._count_main_cameras(ports, {}), 1)

    def test_each_source_seeing_a_different_camera_counts_both(self):
        ports = [self._port(["00:0E:53:AA:01:01"])]
        probes = {"00:0E:53:BB:02:01": {"mac": "00:0E:53:BB:02:01", "ip": "169.254.16.51",
                                         "modelNumber": "Z4SF-5"}}
        self.assertEqual(main._count_main_cameras(ports, probes), 2)  # max() said 1

    def test_uplink_ocr_and_down_ports_never_count(self):
        ports = [self._port(["00:0E:53:AA:01:01"], uplink=True),
                 self._port(["00:D0:89:1B:03:01"], ocr=True),
                 self._port(["00:0E:53:AA:01:02"], up=False)]
        self.assertEqual(main._count_main_cameras(ports, {}), 0)

    def test_scoreboard_state_only_when_configured_or_present(self):
        self.assertIsNone(main._scoreboard_camera_state([self._port([])], {"cameras": []}))
        live = {"isUp": True, "isOcr": True, "portLabel": "Port 3", "linkSpeedMbps": 100}
        st = main._scoreboard_camera_state([live], None)
        self.assertEqual((st["connected"], st["port"], st["speedMbps"]), (True, "Port 3", 100))
        st = main._scoreboard_camera_state([], {"cameras": [{"role": "OCR"}]})
        self.assertEqual((st["configured"], st["connected"]), (True, False))

# ── LogMeIn service-log evidence (Get-LmiGatewayLog) ─────────────────
# Fixture numbers are the real field log (2026-08-28): a VPU dark in LMI all
# day - 201 handshakes killed with "SSL error: SSLv3/TLS write client hello"
# across 142 gateway connects - until the district disabled packet inspection
# at 15:59:50 and it logged straight in. The dashboard warns only while the
# block is CURRENT; a recovered block is history and stays on the Network tab.
class TestLmiGatewayLogFinding(unittest.TestCase):
    def _lmi(self, blocked=True):
        return {
            "installed": True, "logsFound": True,
            "logDir": "C:\\ProgramData\\LogMeIn", "windowDays": 7,
            "filesScanned": 2, "attempts": 142, "sslFailures": 201,
            "handshakeFailures": 60, "gatewayFailures": 141,
            "logins": 0 if blocked else 1,
            "firstSslFailure": "2026-08-28 00:04:03",
            "lastSslFailure": "2026-08-28 15:54:16",
            "lastLogin": None if blocked else "2026-08-28 15:59:50",
            "blockedNow": blocked,
            "recoveredAt": None if blocked else "2026-08-28 15:59:50",
            "gatewayHosts": ["control.lmi-app25-12.logmein.com"],
        }

    def _findings(self, lmi_log):
        return main._compute_findings(
            identity={}, performance={}, services={}, nics={}, lmi_log=lmi_log)

    def test_current_block_warns(self):
        f = [x for x in self._findings(self._lmi(blocked=True))
             if x["code"] == "lmi-ssl-blocked"]
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0]["severity"], "warning")
        self.assertIn("201", _finding_text(f[0]))
        # The fix has to name the gateway wildcard - an allowlist entry for
        # secure.logmein.com alone leaves control.lmi-app*.logmein.com dead.
        self.assertIn("*.logmein.com", _finding_text(f[0]))

    def test_recovered_block_stays_off_dashboard(self):
        # Failures followed by a successful login = venue lifted the block.
        # That is Network-tab history, not a live dashboard warning.
        self.assertEqual(
            [x for x in self._findings(self._lmi(blocked=False))
             if x["code"] == "lmi-ssl-blocked"], [])

    def test_clean_log_is_quiet(self):
        clean = self._lmi(blocked=False)
        clean.update({"sslFailures": 0, "handshakeFailures": 0,
                      "gatewayFailures": 0, "firstSslFailure": None,
                      "lastSslFailure": None, "blockedNow": False,
                      "recoveredAt": None})
        self.assertEqual(
            [x for x in self._findings(clean) if x["code"] == "lmi-ssl-blocked"], [])

    def test_collector_error_is_quiet(self):
        self.assertEqual(
            [x for x in self._findings({"error": True, "message": "boom"})
             if x["code"] == "lmi-ssl-blocked"], [])

    def test_lmi_block_does_not_gate_readiness(self):
        # Support plane, same rationale as tls-filtered-support: remote
        # support is cut off, tonight's game is not.
        verdict = main._compute_readiness(
            [{"code": "lmi-ssl-blocked", "severity": "warning",
              "category": "Network", "title": "t", "recommendation": "r"}]
        )
        self.assertEqual(verdict["status"], "PASS")


# Finding codes emitted with severity "critical" by _compute_findings. Kept
# explicit rather than scraped so adding a critical is a deliberate two-line
# change: emit it, then classify it.
_CRITICAL_FINDING_CODES = {
    # Emitted with a literal "severity": "critical".
    "cpu-critical",
    "disk-critical",
    "disk-smart-prefail",
    "gpu-anomaly",
    "gpu-none",
    "mem-critical",
    "os-eos-imminent",
    "os-eos-reached",
    "pixellot-over-cap",
    "ssl-inspection",
    "stream-blocked",
    "tls-filtered",
    "stream-degraded-rtmp",
    "sw-security",
    "temp-critical",
    "tz-non-us",
    "uplink-on-camera-port",
    # port-dns-blocked / port-required-blocked share one emit site.
    "port-dns-blocked",
    "port-required-blocked",
    # Built from a variable at emit time: the `{name}-down` service findings
    # and cam-none (critical when zero main cameras are present).
    "agent-down",
    "coordinator-down",
    "watchdog-down",
    "cam-none",
}


if __name__ == "__main__":
    unittest.main(verbosity=2)
