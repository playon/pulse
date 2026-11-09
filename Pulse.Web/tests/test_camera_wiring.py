"""Camera-port wiring and addressing faults that read as "check the cables".

Field case: Watertown (TN) Main Gym, PXLS2_12458, 2026-11-09. Ports 2-4 were
linked at 1 Gbps with no camera answering. Two causes, both invisible to the
old checks:

* Pixellot's config pointed at 169.254.16.50 / .51 / .52, while the camera
  ports were set up on the older one-subnet-per-port layout
  (169.254.71.100, 72.100, 73.100, all with mask 255.255.0.0).
* The camera ports were patched into the school network: `arp -a` on the
  motherboard port (10.44.4.107) listed all three camera-port MACs, the links
  stayed up with PoE switched off, and Ports 3 and 4 showed identical traffic.

Fixtures below are that unit's real adapters, addresses and ARP rows.
"""

import copy
import os
import sys
import unittest

_APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import main  # noqa: E402


def _nic(name, mac, up, arp=None):
    return {"name": name, "status": "Up" if up else "Disconnected",
            "linkSpeedMbps": 1000 if up else None, "mac": mac, "arpEntries": arp or []}


def _adapter(name, desc, mac, idx, bus, up=True):
    return {"name": name, "interfaceDescription": desc, "status": "Up" if up else "Disconnected",
            "adminStatus": "Up", "physicalMediaType": "802.3", "macAddress": mac,
            "interfaceIndex": idx, "pciBus": bus}


def _watertown():
    nics = {"ports": [
        _nic("Ethernet 24", "00-30-64-65-8E-06", False),
        _nic("Ethernet 25", "00-30-64-65-8E-07", True),
        _nic("Ethernet 26", "00-30-64-65-8E-08", True),
        _nic("Ethernet 27", "00-30-64-65-8E-09", True),
    ]}
    cfg = {
        "adapters": [
            _adapter("Ethernet", "Intel(R) Ethernet Connection (7) I219-LM #2", "9C-7B-EF-28-96-00", 32, 0),
            _adapter("Ethernet 24", "Intel(R) I210 Gigabit Network Connection #9", "00-30-64-65-8E-06", 24, 2, up=False),
            _adapter("Ethernet 25", "Intel(R) I210 Gigabit Network Connection #10", "00-30-64-65-8E-07", 25, 3),
            _adapter("Ethernet 26", "Intel(R) I210 Gigabit Network Connection #11", "00-30-64-65-8E-08", 30, 4),
            _adapter("Ethernet 27", "Intel(R) I210 Gigabit Network Connection #12", "00-30-64-65-8E-09", 33, 5),
        ],
        "ipConfigurations": [
            {"interfaceAlias": "Ethernet", "interfaceIndex": 32, "ipv4Address": ["10.44.4.107"],
             "ipv4DefaultGateway": ["10.44.0.1"], "prefixLength": 20},
            {"interfaceAlias": "Ethernet 25", "interfaceIndex": 25, "ipv4Address": ["169.254.71.100"],
             "ipv4DefaultGateway": [], "prefixLength": 16},
            {"interfaceAlias": "Ethernet 26", "interfaceIndex": 30, "ipv4Address": ["169.254.72.100"],
             "ipv4DefaultGateway": [], "prefixLength": 16},
            {"interfaceAlias": "Ethernet 27", "interfaceIndex": 33, "ipv4Address": ["169.254.73.100"],
             "ipv4DefaultGateway": [], "prefixLength": 16},
        ],
        # `arp -a`, interface 10.44.4.107: the VPU's own camera ports.
        "selfNeighborSightings": [
            {"mac": "003064658E07", "ip": "169.254.71.100", "seenOnInterfaceIndex": 32,
             "seenOnInterfaceAlias": "Ethernet", "state": "Stale"},
            {"mac": "003064658E08", "ip": "169.254.72.100", "seenOnInterfaceIndex": 32,
             "seenOnInterfaceAlias": "Ethernet", "state": "Stale"},
            {"mac": "003064658E09", "ip": "169.254.73.100", "seenOnInterfaceIndex": 32,
             "seenOnInterfaceAlias": "Ethernet", "state": "Stale"},
        ],
    }
    expectations = {"expectedMainCameras": 2, "systemType": "S2", "configuredCameras": [
        {"role": "main", "index": 0, "ip": "169.254.16.50"},
        {"role": "main", "index": 1, "ip": "169.254.16.51"},
        {"role": "ocr", "index": 0, "ip": "169.254.16.52"},
    ]}
    return nics, cfg, expectations


def _ports(nics, cfg, probes=None):
    ports = main._enrich_ports(nics, probes or {})
    main._flag_uplink_ports(ports, cfg)
    return ports


class _GraceMixin:
    def setUp(self):
        self._saved_start = main._PROCESS_START_MONO
        self._saved_tracker = main._PORT_STATE_TRACKER
        main._PORT_STATE_TRACKER = {}
        main._PROCESS_START_MONO = main.time.monotonic()  # inside the startup grace

    def tearDown(self):
        main._PROCESS_START_MONO = self._saved_start
        main._PORT_STATE_TRACKER = self._saved_tracker


class TestWatertown(_GraceMixin, unittest.TestCase):

    def _findings(self, nics, cfg, expectations):
        return main._compute_findings(
            identity={"pixellot": {"version": "5.37.3"}}, performance={}, services={},
            nics=nics, network_config=cfg, probe_results={}, expectations=expectations)

    def test_the_switch_is_the_cause_and_the_mismatch_waits(self):
        # Ports on a switch: the cameras aren't on them, so re-running camera
        # setup changes nothing tonight. The mismatch stays visible as a risk
        # to re-check once the cabling is fixed; cam-none is the one blocker.
        f = self._findings(*_watertown())
        codes = [x["code"] for x in f]
        for code in ("cam-none", "camera-port-on-network", "camera-ip-mismatch-unconfirmed"):
            self.assertIn(code, codes)
        self.assertNotIn("camera-ip-mismatch", codes)
        verdict = main._compute_readiness(f)
        self.assertEqual(verdict["status"], "FAIL")
        self.assertEqual([b["code"] for b in verdict["blockers"]], ["cam-none"])
        mm = [x for x in f if x["code"] == "camera-ip-mismatch-unconfirmed"][0]
        self.assertIn("Fix the camera cabling first", mm["recommendation"])

    def test_without_the_switch_the_mismatch_blocks(self):
        # Past the startup grace: linked ports with no switch flag would
        # otherwise read "not confirmed yet" in the first minute.
        main._PROCESS_START_MONO = main.time.monotonic() - 3600
        nics, cfg, exp = _watertown()
        del cfg["selfNeighborSightings"]
        f = self._findings(nics, cfg, exp)
        blockers = [b["code"] for b in main._compute_readiness(f)["blockers"]]
        self.assertIn("camera-ip-mismatch", blockers)
        cam = [x for x in f if x["code"] == "cam-none"][0]
        self.assertIn("Pixellot support", cam["recommendation"])
        self.assertNotIn("seated", cam["recommendation"])

    def test_zero_cameras_is_not_softened_by_the_startup_grace(self):
        # Links that run to a switch prove nothing about cameras, so they
        # must not turn cam-none into "not confirmed yet".
        codes = [x["code"] for x in self._findings(*_watertown())]
        self.assertNotIn("cam-count-pending", codes)

    def test_cam_none_names_the_cause_not_the_cables(self):
        cam = [x for x in self._findings(*_watertown()) if x["code"] == "cam-none"][0]
        self.assertNotIn("seated", cam["recommendation"])
        self.assertIn("Trace the camera cables", cam["recommendation"])
        self.assertNotIn("Pixellot support", cam["recommendation"])
        self.assertIn("Port 2: linked to a network, not a camera", cam["details"])

    def test_mismatch_lists_every_camera_and_the_port_addresses(self):
        nics, cfg, exp = _watertown()
        f = main._camera_ip_mismatch_finding(_ports(nics, cfg), cfg, exp)
        self.assertEqual(f["code"], "camera-ip-mismatch-unconfirmed")
        self.assertEqual(f["details"][:3], [
            "Main camera 1: set to 169.254.16.50, no camera port on 169.254.16.x",
            "Main camera 2: set to 169.254.16.51, no camera port on 169.254.16.x",
            "Scoreboard camera: set to 169.254.16.52, no camera port on 169.254.16.x",
        ])
        self.assertEqual(f["details"][3], "Camera ports: Port 2 169.254.71.100, "
                                          "Port 3 169.254.72.100, Port 4 169.254.73.100")

    def test_network_finding_names_the_ports_and_where_they_were_heard(self):
        nics, cfg, _ = _watertown()
        f = main._camera_port_network_finding(_ports(nics, cfg))
        self.assertEqual(f["title"], "Port 2, Port 3 and Port 4 are plugged into the venue network, not a camera")
        self.assertIn("Port 3 (Ethernet 26): heard on Ethernet", f["details"])
        self.assertEqual(main._readiness_class(f["code"]), "risk")

    def test_no_poe_power_on_linked_ports_backs_up_the_switch(self):
        nics, cfg, _ = _watertown()
        poe = {"available": True, "ports": [
            {"port": n, "poeOn": False, "readOk": True, "watts": 0.0} for n in (1, 2, 3, 4)]}
        f = main._camera_port_network_finding(_ports(nics, cfg), poe)
        self.assertIn("Port 2 (Ethernet 25): heard on Ethernet, linked but drawing no PoE power",
                      f["details"])
        self.assertIn("a switch powers itself", f["evidence"])
        # Without a PoE read the finding still stands, it just says less.
        bare = main._camera_port_network_finding(_ports(nics, cfg))
        self.assertNotIn("PoE", bare["evidence"])

    def test_port_tiles_carry_the_flag(self):
        nics, cfg, _ = _watertown()
        ports = _ports(nics, cfg)
        self.assertEqual([bool(p.get("onSharedNetwork")) for p in ports], [False, True, True, True])
        self.assertTrue(ports[1]["sharedNetworkIsVenue"])
        self.assertEqual(ports[1]["sharedNetworkSeenOn"], "Ethernet")


class TestCameraIpMismatch(unittest.TestCase):

    @staticmethod
    def _unit(port_ips, configured, cams=None):
        """One camera port per address; `cams` maps port index -> camera IP seen in ARP."""
        cams = cams or {}
        nics = {"ports": []}
        cfg = {"adapters": [], "ipConfigurations": []}
        for i, ip in enumerate(port_ips):
            mac = f"00-30-64-00-00-0{i}"
            arp = [{"ip": cams[i], "mac": f"00-D0-89-00-00-0{i}"}] if i in cams else []
            nics["ports"].append(_nic(f"Ethernet {i + 1}", mac, True, arp))
            cfg["adapters"].append(_adapter(f"Ethernet {i + 1}", "Intel(R) I210", mac, 10 + i, 2 + i))
            cfg["ipConfigurations"].append({"interfaceIndex": 10 + i, "ipv4Address": [ip], "prefixLength": 24})
        exp = {"expectedMainCameras": 2, "configuredCameras": configured}
        return _ports(nics, cfg), cfg, exp

    MAIN = [{"role": "main", "index": 0, "ip": "169.254.16.50"},
            {"role": "main", "index": 1, "ip": "169.254.16.51"}]

    def test_current_layout_is_quiet(self):
        ports, cfg, exp = self._unit(["169.254.16.100", "169.254.16.101"], self.MAIN)
        self.assertIsNone(main._camera_ip_mismatch_finding(ports, cfg, exp))

    def test_old_per_port_layout_is_quiet_when_config_matches(self):
        ports, cfg, exp = self._unit(
            ["169.254.71.100", "169.254.72.100"],
            [{"role": "main", "index": 0, "ip": "169.254.71.50"},
             {"role": "main", "index": 1, "ip": "169.254.72.50"}])
        self.assertIsNone(main._camera_ip_mismatch_finding(ports, cfg, exp))

    def test_a_camera_answering_at_its_address_wins_over_the_rule(self):
        ports, cfg, exp = self._unit(["169.254.71.100", "169.254.72.100"], self.MAIN,
                                     cams={0: "169.254.16.50", 1: "169.254.16.51"})
        self.assertIsNone(main._camera_ip_mismatch_finding(ports, cfg, exp))

    def test_vpu2_random_link_local_ports_say_nothing(self):
        # VPU2, 2026-11-09 smoke run: camera ports on random link-local
        # addresses (/16), main camera .51 answering, .50 dark. That's not a
        # layout mismatch; the dark camera is cam-partial's job.
        ports, cfg, exp = self._unit(
            ["169.254.243.153", "169.254.117.195", "169.254.69.30"],
            self.MAIN + [{"role": "ocr", "index": 0, "ip": "169.254.16.52"}],
            cams={1: "169.254.16.51", 2: "169.254.16.52"})
        self.assertIsNone(main._camera_ip_mismatch_finding(ports, cfg, exp))

    def test_only_the_scoreboard_camera_is_a_risk(self):
        ports, cfg, exp = self._unit(
            ["169.254.16.100", "169.254.16.101"],
            self.MAIN + [{"role": "ocr", "index": 0, "ip": "169.254.20.52"}])
        f = main._camera_ip_mismatch_finding(ports, cfg, exp)
        self.assertEqual(f["code"], "camera-ip-mismatch-ocr")
        self.assertEqual(main._readiness_class(f["code"]), "risk")

    def test_unknown_inputs_say_nothing(self):
        ports, cfg, exp = self._unit(["169.254.71.100"], self.MAIN)
        self.assertIsNone(main._camera_ip_mismatch_finding(ports, cfg, {"expectedMainCameras": 2}))
        self.assertIsNone(main._camera_ip_mismatch_finding(ports, cfg, {"error": True}))
        self.assertIsNone(main._camera_ip_mismatch_finding(ports, None, exp))
        no_ips = copy.deepcopy(cfg)
        no_ips["ipConfigurations"] = []
        self.assertIsNone(main._camera_ip_mismatch_finding(ports, no_ips, exp))


class TestSharedNetworkPorts(unittest.TestCase):

    def test_a_port_with_a_camera_is_not_flagged_by_a_stale_sighting(self):
        nics, cfg, _ = _watertown()
        nics["ports"][1]["arpEntries"] = [{"ip": "169.254.71.50", "mac": "00-D0-89-1A-6E-53"}]
        ports = _ports(nics, cfg)
        self.assertFalse(ports[1].get("onSharedNetwork"))
        self.assertTrue(ports[2].get("onSharedNetwork"))

    def test_a_down_port_is_not_flagged(self):
        nics, cfg, _ = _watertown()
        nics["ports"][3]["status"] = "Disconnected"
        self.assertFalse(_ports(nics, cfg)[3].get("onSharedNetwork"))

    def test_camera_ports_hearing_each_other_read_as_a_switch(self):
        nics, cfg, _ = _watertown()
        cfg["selfNeighborSightings"] = [
            {"mac": "003064658E08", "ip": "169.254.72.100", "seenOnInterfaceIndex": 33,
             "seenOnInterfaceAlias": "Ethernet 27"}]
        f = main._camera_port_network_finding(_ports(nics, cfg))
        self.assertEqual(f["title"], "Port 3 is plugged into a network switch, not a camera")
        self.assertIn("can hear each other", f["recommendation"])

    def test_no_sightings_no_flag(self):
        nics, cfg, _ = _watertown()
        del cfg["selfNeighborSightings"]
        self.assertIsNone(main._camera_port_network_finding(_ports(nics, cfg)))


if __name__ == "__main__":
    unittest.main()
