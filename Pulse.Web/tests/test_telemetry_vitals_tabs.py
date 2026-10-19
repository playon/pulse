"""pulse.telemetry/v1 blocks for Vitals' unit tabs (PV-65, PV-66, PV-68, PV-70,
PV-71, PV-74, PV-75, PV-76): the camera card and its PoE, power events, disk
space, drive health, streaming components, installed applications, whether
Pixellot's programs can start, and the Windows build, time zone and clock.

Unknown is null throughout, never a healthy-looking default."""

import asyncio
import copy
import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

_APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import main  # noqa: E402  (binds the engine)
import powershell  # noqa: E402
from pulse_agent import telemetry as T  # noqa: E402

HOSTNAME = "PXLS2-55555"
IDENTITY = {"computerSystem": {"name": HOSTNAME, "model": "HP Z2 Tower G9"},
            "bios": {"serialNumber": "CZC9QX7LMN"},
            "operatingSystem": {"caption": "Microsoft Windows 10 IoT Enterprise LTSC 2019", "buildNumber": "17763"},
            "timezone": "(UTC-05:00) Eastern Time (US & Canada)", "timezoneId": "Eastern Standard Time"}


def build(raw, dashboard=None):
    return T._build_telemetry(dashboard or {}, raw)


def fp(t):
    return T._telemetry_fingerprint(t, [])


# ── Camera card (PV-65) and PoE (PV-66) ──────────────────────────────────────

def adapter(name, desc, bus):
    return {"name": name, "interfaceDescription": desc, "physicalMediaType": "802.3", "pciBus": bus}


def network(card_desc="Intel(R) I210 Gigabit Network Connection", ports=4, onboard="Intel(R) I210 Gigabit Network Connection"):
    adapters = [adapter("Ethernet", onboard, 0)]   # the motherboard port: same chip, bus 0
    adapters += [adapter(f"Ethernet {i + 1}", f"{card_desc} #{i + 1}", i + 1) for i in range(ports)]
    adapters.append({"name": "Wi-Fi", "interfaceDescription": "Intel(R) Wireless-AC 9560",
                     "physicalMediaType": "Native 802.11", "pciBus": 0})
    return {"adapters": adapters}


def poe_read(**budget):
    return {"supported": True, "available": True, "nicModel": "I210",
            "budget": {"totalW": 59.64, "consumedW": 11.62, "remainingW": 48.02, "tempC": 46.4,
                       "underPowered": False, "healthyFloorW": 55, **budget},
            "ports": [{"port": 1, "voltage": 54.709, "current": 0.1061, "watts": 5.81, "poeOn": True, "readOk": True},
                      {"port": 2, "voltage": 54.149, "current": 0.1, "watts": 5.41, "poeOn": True, "readOk": True},
                      {"port": 3, "voltage": 0.187, "current": 0, "watts": 0, "poeOn": False, "readOk": True},
                      {"port": 4, "voltage": 0, "current": 0, "watts": 0, "poeOn": False, "readOk": False,
                       "state": "Unreadable"}]}


class TestCameraCard(unittest.TestCase):
    def test_gie74_with_poe(self):
        nic = build({"network_config": network(), "poe": poe_read()})["cameras"]["nic"]
        self.assertEqual({k: nic[k] for k in ("model", "chip", "portCount", "poeSupported")},
                         {"model": "GIE74 series", "chip": "I210", "portCount": 4, "poeSupported": True})
        self.assertEqual(nic["poe"]["budget"], {"totalW": 59.6, "consumedW": 11.6, "remainingW": 48.0, "tempC": 46})
        self.assertFalse(nic["poe"]["underPowered"])
        self.assertEqual(nic["poe"]["ports"][0], {"port": 1, "on": True, "volts": 54.7, "amps": 0.106, "watts": 5.8})
        self.assertEqual(nic["poe"]["ports"][2]["on"], False)
        # A port the card couldn't read is unknown, not off.
        self.assertEqual(nic["poe"]["ports"][3], {"port": 4, "on": None, "volts": None, "amps": None, "watts": None})

    def test_the_onboard_port_is_not_a_card_port(self):
        self.assertEqual(T._camera_card(network(ports=4))["portCount"], 4)

    def test_gie64_reports_no_poe(self):
        nic = build({"network_config": network("Intel(R) 82574L Gigabit Network Connection"),
                     "poe": poe_read()})["cameras"]["nic"]
        self.assertEqual((nic["model"], nic["chip"], nic["poeSupported"], nic["poe"]), ("GIE64 series", "82574L", False, None))

    def test_gie74p_an(self):
        nic = T._camera_card(network("Intel(R) I350 Gigabit Network Connection"))
        self.assertEqual((nic["model"], nic["poeSupported"]), ("GIE74P-AN", False))

    def test_unrecognised_card_is_a_null_model_never_a_guess(self):
        nic = T._camera_card(network("Realtek PCIe GbE Family Controller", ports=2))
        self.assertEqual(nic, {"model": None, "chip": None, "portCount": 2, "poeSupported": None})

    def test_no_card_or_no_read_is_null(self):
        self.assertIsNone(build({})["cameras"]["nic"])
        self.assertIsNone(build({"network_config": {"error": True}})["cameras"]["nic"])
        self.assertIsNone(build({"network_config": network(ports=0)})["cameras"]["nic"])

    def test_a_poe_card_whose_read_failed_says_supported_with_no_figures(self):
        for poe in (None, {"error": True}, {"supported": True, "available": False, "reason": "no SmartPoE.dll"},
                    {"supported": True, "available": False, "reason": "crashed 3 times"}):
            nic = build({"network_config": network(), "poe": poe})["cameras"]["nic"]
            self.assertTrue(nic["poeSupported"])
            self.assertIsNone(nic["poe"])

    def test_temperature_zero_is_unknown(self):
        nic = build({"network_config": network(), "poe": poe_read(tempC=0)})["cameras"]["nic"]
        self.assertIsNone(nic["poe"]["budget"]["tempC"])

    def test_under_powered_card(self):
        nic = build({"network_config": network(), "poe": poe_read(underPowered=True, totalW=20.1)})["cameras"]["nic"]
        self.assertTrue(nic["poe"]["underPowered"])

    def test_the_monitor_loads_smartpoe_only_for_a_card_that_reports_poe(self):
        ran = []

        async def fake(script, *a, **k):
            ran.append(script)
            return {}
        saved = main.run_ps
        main.run_ps = fake
        try:
            for net, want in ((network(), True), (network("Intel(R) 82574L"), False),
                              (network("Intel(R) I350"), False), (None, False)):
                ran.clear()
                asyncio.run(T._collect_telemetry_extras({"network_config": net}))
                self.assertEqual("Get-PoePower.ps1" in ran, want, net and net["adapters"][1])
        finally:
            main.run_ps = saved

    def test_poe_readings_move_the_fingerprint_only_when_a_port_turns_on_or_off(self):
        base = build({"network_config": network(), "poe": poe_read()})
        jitter = poe_read(consumedW=12.9, remainingW=46.7, tempC=48)
        jitter["ports"][0].update(current=0.12, watts=6.6)
        self.assertEqual(fp(build({"network_config": network(), "poe": jitter})), fp(base))
        off = poe_read()
        off["ports"][1].update(poeOn=False, watts=0)
        self.assertNotEqual(fp(build({"network_config": network(), "poe": off})), fp(base))


# ── Power events (PV-68) ─────────────────────────────────────────────────────

def reboots(history=None, **kw):
    out = {"lastBoot": "2026-10-18T08:00:00.0000000-04:00",
           "pending": {"isPending": False, "reasons": []},
           "afterPowerLoss": {"status": "read", "value": "Power On", "options": ["Power Off", "Power On"],
                              "manufacturer": "HP", "model": "HP EliteDesk 800 G4", "message": None},
           "deviceInstallRebootTaskLastRun": "2026-10-14T13:20:00.0000000-04:00",
           "history": history if history is not None else [], "count": len(history or [])}
    out.update(kw)
    return out


def restart(day, *, unexpected=False, by_pulse=False, event_id=1074):
    return {"time": f"2026-10-{day:02d}T13:00:00.0000000-04:00", "eventId": 41 if unexpected else event_id,
            "kind": "unexpected" if unexpected else "restart", "category": "unexpected" if unexpected else "planned",
            "process": f"C:\\Windows\\system32\\shutdown.exe ({HOSTNAME})", "user": f"{HOSTNAME}\\Pixellot",
            "reasonCode": "0x80040002", "reasonText": "" if unexpected else "Other (Planned)",
            "comment": "Reboot requested from Pulse diagnostics" if by_pulse else "",
            "byPulse": by_pulse,
            "source": "Unexpected (kernel-power: no clean shutdown)" if unexpected
                      else "Pulse (Reboot VPU)" if by_pulse else "Planned - external",
            "message": f"The process shutdown.exe ({HOSTNAME}) has initiated the restart of computer {HOSTNAME}"}


class TestPowerEvents(unittest.TestCase):
    def test_the_full_block(self):
        p = build({"reboots": reboots([restart(12, by_pulse=True), restart(14, unexpected=True)])})["power"]
        self.assertEqual(p["unexpectedShutdowns7d"], 1)
        self.assertEqual(p["pendingReboot"], {"isPending": False, "reasons": []})
        self.assertEqual(p["afterPowerLoss"], {"status": "read", "value": "Power On"})
        self.assertEqual(p["deviceInstallRebootLastRun"], "2026-10-14T13:20:00-04:00")
        self.assertEqual(p["events"], [
            {"time": "2026-10-14T13:00:00-04:00", "category": "unexpected", "byPulse": False,
             "source": "Unexpected (kernel-power: no clean shutdown)", "reasonText": None},
            {"time": "2026-10-12T13:00:00-04:00", "category": "planned", "byPulse": True,
             "source": "Pulse (Reboot VPU)", "reasonText": "Other (Planned)"}])

    def test_no_restarts_is_an_empty_list(self):
        p = build({"reboots": reboots([])})["power"]
        self.assertEqual((p["events"], p["unexpectedShutdowns7d"]), ([], 0))

    def test_an_older_or_failed_read_leaves_the_new_fields_out(self):
        # Vitals then says "hasn't reported", never "Never" or "no restarts".
        for raw in ({}, {"reboots": None}):
            self.assertEqual(set(build(raw)["power"]), {"lastBoot", "unexpectedShutdowns7d"})

    def test_bios_setting_unread_is_never_power_on(self):
        for status, value in (("error", None), ("unsupported", None)):
            apl = {"status": status, "value": "Power On" if status == "error" else None, "message": "boom"}
            p = build({"reboots": reboots(afterPowerLoss=apl)})["power"]
            self.assertEqual(p["afterPowerLoss"], {"status": status, "value": value})
        self.assertIsNone(build({"reboots": reboots(afterPowerLoss=None)})["power"]["afterPowerLoss"])
        off = build({"reboots": reboots(afterPowerLoss={"status": "read", "value": "Power Off"})})["power"]
        self.assertEqual(off["afterPowerLoss"]["value"], "Power Off")

    def test_task_that_never_ran(self):
        p = build({"reboots": reboots(deviceInstallRebootTaskLastRun="1999-11-30T00:00:00.0000000")})["power"]
        self.assertIsNone(p["deviceInstallRebootLastRun"])
        self.assertIsNone(build({"reboots": reboots(deviceInstallRebootTaskLastRun=None)})["power"]["deviceInstallRebootLastRun"])

    def test_pending_reboot_with_reasons(self):
        p = build({"reboots": reboots(pending={"isPending": True, "reasons": ["Windows Update is waiting to finish",
                                                                                "Computer rename pending"]})})["power"]
        self.assertEqual(p["pendingReboot"]["reasons"], ["Windows Update is waiting to finish", "Computer rename pending"])

    def test_nothing_names_the_computer(self):
        text = json.dumps(build({"identity": IDENTITY, "reboots": reboots([restart(12), restart(13, by_pulse=True)])})["power"])
        for gone in (HOSTNAME, "shutdown.exe", "Pixellot\\\\", "Reboot requested", "initiated", "0x8004"):
            self.assertNotIn(gone, text)

    def test_capped_at_20_newest_first_and_the_count_counts_them_all(self):
        hist = [restart(1 + i % 28, unexpected=i % 2 == 0) for i in range(30)]
        p = build({"reboots": reboots(hist)})["power"]
        self.assertEqual(len(p["events"]), 20)
        self.assertEqual(p["unexpectedShutdowns7d"], 15)
        times = [e["time"] for e in p["events"]]
        self.assertEqual(times, sorted(times, reverse=True))

    def test_count_matches_the_rows_under_the_cap(self):
        hist = [restart(10, unexpected=True), restart(11), restart(12, event_id=6008)]
        hist[2]["category"] = "planned"   # a 6008 the collector didn't label still counts, as before
        p = build({"reboots": reboots(hist)})["power"]
        self.assertEqual(p["unexpectedShutdowns7d"], sum(e["category"] == "unexpected" for e in p["events"]))


# ── Disk space (PV-70) and drive health (PV-74) ──────────────────────────────

def disk_health(volumes=None, physical=None, predict=False):
    return {"logicalDisks": volumes if volumes is not None else [
                {"deviceID": "D:", "freeSpaceGB": 86.12, "sizeGB": 953.86, "usedPercent": 91.0, "fileSystem": "NTFS",
                 "volumeName": "Lincoln HS Recordings"},
                {"deviceID": "C:", "freeSpaceGB": 176.4, "sizeGB": 465.13, "usedPercent": 62.1, "fileSystem": "NTFS"}],
            "physicalDisks": physical if physical is not None else [
                {"friendlyName": "Samsung SSD 870 EVO 500GB", "serialNumber": "S3Z8NB0K901234A", "sizeGB": 465,
                 "healthStatus": "Healthy", "operationalStatus": "OK",
                 "smart": {"wearPercent": 11, "powerOnHours": 8423, "temperatureC": 41,
                           "readErrorsUncorrected": 0, "writeErrorsUncorrected": 0}}],
            "predictFailure": predict}


def hardware(*drives):
    return {"diskDrives": [dict(d, index=i) for i, d in enumerate(drives or (
        {"model": "Samsung SSD 870 EVO 500GB", "sizeGB": 465.76, "mediaType": "SSD", "interfaceType": "SATA",
         "serialNumber": "S3Z8NB0K901234A"},))]}


class TestVolumes(unittest.TestCase):
    def test_letters_and_sizes_only_by_letter(self):
        v = build({"disk_health": disk_health()})["hardware"]["volumes"]
        self.assertEqual(v, [{"letter": "C", "sizeGb": 465.1, "freeGb": 176.4},
                             {"letter": "D", "sizeGb": 953.9, "freeGb": 86.1}])
        self.assertNotIn("Lincoln", json.dumps(v))

    def test_failed_read_is_null_never_empty(self):
        for dh in (None, {"error": True}, disk_health(volumes=[])):
            hw = build({"hardware": hardware(), "disk_health": dh})["hardware"]
            self.assertIsNone(hw["volumes"])

    def test_single_volume(self):
        v = build({"disk_health": disk_health(volumes=[{"deviceID": "C:", "freeSpaceGB": 50, "sizeGB": 238.4}])})
        self.assertEqual(v["hardware"]["volumes"], [{"letter": "C", "sizeGb": 238.4, "freeGb": 50.0}])

    def test_exactly_90_percent_agrees_with_the_finding(self):
        # The finding is "over 90%": exactly 90.0 used must not read full here either.
        vol = {"deviceID": "C:", "freeSpaceGB": 46.5, "sizeGB": 465.0, "usedPercent": 90.0}
        v = build({"disk_health": disk_health(volumes=[vol])})["hardware"]["volumes"][0]
        self.assertEqual(round(100 * (v["sizeGb"] - v["freeGb"]) / v["sizeGb"], 1), 90.0)

    def test_bad_rows_are_skipped_and_the_list_capped(self):
        rows = [{"deviceID": f"{chr(ord('C') + i)}:", "freeSpaceGB": 1, "sizeGB": 10} for i in range(12)]
        rows += [{"deviceID": "\\\\server\\share", "freeSpaceGB": 1, "sizeGB": 10},
                 {"deviceID": "Z:", "freeSpaceGB": 20, "sizeGB": 10}, {"deviceID": "Y:", "sizeGB": 0, "freeSpaceGB": 0}]
        v = build({"disk_health": disk_health(volumes=rows)})["hardware"]["volumes"]
        self.assertEqual([x["letter"] for x in v], list("CDEFGHIJ"))

    def test_free_space_moves_the_fingerprint_only_by_whole_percent(self):
        def t(free):
            return build({"disk_health": disk_health(volumes=[{"deviceID": "D:", "freeSpaceGB": free, "sizeGB": 953.0}])})
        self.assertEqual(fp(t(200.0)), fp(t(200.9)))
        self.assertNotEqual(fp(t(200.0)), fp(t(185.0)))

    def test_disk_health_alone_still_sends_a_block(self):
        hw = build({"disk_health": disk_health()})["hardware"]
        self.assertIsNone(hw["disks"])
        self.assertEqual(len(hw["volumes"]), 2)


class TestDriveHealth(unittest.TestCase):
    def test_matched_by_serial_and_the_serial_never_sent(self):
        hw = build({"hardware": hardware(), "disk_health": disk_health()})["hardware"]
        self.assertEqual(hw["disks"][0], {"model": "Samsung SSD 870 EVO 500GB", "sizeGb": 466, "type": "SSD",
                                          "health": "Healthy", "wearPercent": 11, "powerOnHours": 8423,
                                          "uncorrectedErrors": 0})
        self.assertFalse(hw["predictFailure"])
        self.assertNotIn("S3Z8NB0K901234A", json.dumps(hw))

    def test_unreadable_drive_is_null_per_field(self):
        pd = [{"friendlyName": "Samsung SSD 870 EVO 500GB", "serialNumber": "S3Z8NB0K901234A",
               "healthStatus": "Unknown", "smart": None}]
        d = build({"hardware": hardware(), "disk_health": disk_health(physical=pd)})["hardware"]["disks"][0]
        self.assertEqual([d[k] for k in T._DRIVE_FIELDS], [None] * 4)

    def test_predicted_failure_and_errors(self):
        pd = [{"friendlyName": "WDC", "serialNumber": "S3Z8NB0K901234A", "healthStatus": "Warning",
               "smart": {"wearPercent": 0, "powerOnHours": 0, "readErrorsUncorrected": 3, "writeErrorsUncorrected": None}}]
        hw = build({"hardware": hardware(), "disk_health": disk_health(physical=pd, predict=True)})["hardware"]
        self.assertTrue(hw["predictFailure"])
        self.assertEqual({k: hw["disks"][0][k] for k in T._DRIVE_FIELDS},
                         {"health": "Warning", "wearPercent": 0, "powerOnHours": 0, "uncorrectedErrors": 3})

    def test_worn_drive(self):
        pd = copy.deepcopy(disk_health()["physicalDisks"])
        pd[0]["smart"]["wearPercent"] = 85
        d = build({"hardware": hardware(), "disk_health": disk_health(physical=pd)})["hardware"]["disks"][0]
        self.assertEqual(d["wearPercent"], 85)

    def test_matched_by_model_when_no_serial_but_never_guessed_between_two(self):
        one = hardware({"model": "Samsung SSD 870 EVO 500GB", "sizeGB": 465})
        pd = [dict(disk_health()["physicalDisks"][0], serialNumber=None)]
        self.assertEqual(build({"hardware": one, "disk_health": disk_health(physical=pd)})["hardware"]["disks"][0]["health"], "Healthy")
        two = hardware({"model": "Same", "sizeGB": 465}, {"model": "Same", "sizeGB": 465})
        pd = [{"friendlyName": "Same", "healthStatus": "Healthy"}, {"friendlyName": "Same", "healthStatus": "Unhealthy"}]
        disks = build({"hardware": two, "disk_health": disk_health(physical=pd)})["hardware"]["disks"]
        self.assertEqual([d["health"] for d in disks], [None, None])

    def test_failed_health_read(self):
        hw = build({"hardware": hardware(), "disk_health": {"error": True}})["hardware"]
        self.assertIsNone(hw["predictFailure"])
        self.assertEqual([hw["disks"][0][k] for k in T._DRIVE_FIELDS], [None] * 4)

    def test_power_on_hours_dont_move_the_fingerprint(self):
        pd = copy.deepcopy(disk_health()["physicalDisks"])
        pd[0]["smart"]["powerOnHours"] += 5
        a = build({"hardware": hardware(), "disk_health": disk_health()})
        b = build({"hardware": hardware(), "disk_health": disk_health(physical=pd)})
        self.assertEqual(fp(a), fp(b))
        pd[0]["healthStatus"] = "Warning"
        self.assertNotEqual(fp(a), fp(build({"hardware": hardware(), "disk_health": disk_health(physical=pd)})))


# ── Streaming components and applications (PV-71) ───────────────────────────

def dash_services(**over):
    svc = {"agent": "Running", "coordinator": "Running", "vpu": "Stopped", "keepagentup": "Running",
           "ScoreConnectIII": "Running", "LogMeIn": "Running"}
    svc.update(over)
    return {"services": {"services": [{"name": k, "status": v} for k, v in svc.items() if v is not None]}}


class TestServices(unittest.TestCase):
    def states(self, dash):
        return {s["name"]: s["state"] for s in build({}, dash)["services"]}

    def test_all_running(self):
        self.assertEqual(self.states(dash_services()), {"agent": "running", "coordinator": "running",
                                                        "keepagentup": "running", "vpu": "stopped",
                                                        "scoreconnect": "running", "logmein": "running"})

    def test_agent_stopped(self):
        t = build({}, dash_services(agent="Stopped"))
        self.assertEqual(t["services"][0], {"name": "agent", "state": "stopped"})
        self.assertEqual(t["servicesDown"], ["agent"])          # v1 field unchanged

    def test_ocr_unit_with_no_scoreconnect(self):
        self.assertEqual(self.states(dash_services(ScoreConnectIII="NotFound"))["scoreconnect"], "not-installed")

    def test_unlisted_or_odd_states_are_unknown(self):
        st = self.states(dash_services(keepagentup=None, coordinator="StartPending", LogMeIn=None))
        self.assertEqual((st["keepagentup"], st["coordinator"]), ("unknown", "unknown"))
        self.assertNotIn("logmein", st)

    def test_collector_failed_is_null(self):
        self.assertIsNone(build({}, {})["services"])


def software(n, **row):
    return {"count": n, "software": [dict({"displayName": f"App {i:03d}", "displayVersion": "1.0",
                                           "publisher": "Vendor"}, **row) for i in range(n)]}


class TestApplications(unittest.TestCase):
    def test_pixellot_first_then_by_name(self):
        sw = {"software": [{"displayName": "7-Zip 23.01 (x64)", "displayVersion": "23.01", "publisher": "Igor Pavlov"},
                           {"displayName": "Pixellot VPU Agent", "displayVersion": "5.36.1", "publisher": "Pixellot Ltd."},
                           {"displayName": "Google Chrome", "displayVersion": "120", "publisher": "Google LLC",
                            "installLocation": "C:\\Program Files\\Google", "installDate": "20240115"}]}
        t = build({"installed_sw": sw})
        self.assertEqual([a["name"] for a in t["applications"]], ["Pixellot VPU Agent", "7-Zip 23.01 (x64)", "Google Chrome"])
        self.assertEqual(set(t["applications"][0]), {"name", "version", "publisher"})
        self.assertEqual(t["applicationsTotal"], 3)

    def test_failure_is_null_never_empty(self):
        for sw in (None, {"error": True}, {"software": []}):
            t = build({"installed_sw": sw})
            self.assertIsNone(t["applications"])
            self.assertIsNone(t["applicationsTotal"])

    def test_capped_at_150_and_counted(self):
        t = build({"installed_sw": software(400)})
        self.assertEqual(len(t["applications"]), 150)
        self.assertEqual(t["applicationsTotal"], 400)

    def test_fields_capped(self):
        a = build({"installed_sw": software(1, displayName="N" * 300, displayVersion="V" * 300,
                                            publisher="P" * 300)})["applications"][0]
        self.assertEqual((len(a["name"]), len(a["version"]), len(a["publisher"])), (80, 32, 40))

    def test_a_name_carrying_the_hostname_is_dropped(self):
        sw = {"software": [{"displayName": f"Agent for {HOSTNAME}", "displayVersion": "1"},
                           {"displayName": "Fine", "publisher": f"{HOSTNAME} IT"}]}
        t = build({"identity": IDENTITY, "installed_sw": sw})
        self.assertEqual(t["applications"], [{"name": "Fine", "version": None, "publisher": None}])


# ── Can the programs start (PV-76) ───────────────────────────────────────────

def ts(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S%z")[:-2] + ":" + dt.strftime("%z")[-2:]


NOW = datetime(2026, 10, 18, 14, 0, tzinfo=timezone(timedelta(hours=-4)))


def binaries(missing=None, popup_age=None, stuck=False, **exe_over):
    exes = [{"name": "VPU.exe", "present": True, "readable": True, "scanned": 53, "missing": []},
            {"name": "Agent.exe", "present": True, "readable": True, "scanned": 1, "missing": []},
            {"name": "Coordinator.exe", "present": True, "readable": True, "scanned": 1, "missing": []}]
    exes[0].update(exe_over)
    if missing:
        exes[0]["missing"] = [{"dll": d, "neededBy": "VPU.exe"} for d in missing]
    popups = []
    if popup_age is not None:
        popups = [{"exe": "VPU.exe", "title": "System Error", "dll": "libcef.dll", "count": 66,
                   "text": "The code execution cannot proceed because libcef.dll was not found.",
                   "first": ts(NOW - timedelta(days=6)), "last": ts(NOW - popup_age)}]
    return {"now": ts(NOW), "exes": exes, "popups": popups, "popupDays": 7,
            "vpuProcesses": [{"pid": 1, "workingSetMB": 2.8, "stuckOnLoaderError": True}] if stuck else []}


class TestPrograms(unittest.TestCase):
    def blocks_the_stream(self, b):
        return any(f["code"] in ("pixellot-dll-missing", "pixellot-start-error") for f in main._binary_findings(b))

    def test_healthy(self):
        p = build({"binaries": binaries()})["programs"]
        self.assertEqual(p, [{"name": n, "canStart": True, "missing": [], "loaderErrors": None}
                             for n in ("VPU.exe", "Agent.exe", "Coordinator.exe")])

    def test_missing_library(self):
        b = binaries(missing=["libcef.dll"], popup_age=timedelta(minutes=4), stuck=True)
        vpu = build({"binaries": b})["programs"][0]
        self.assertEqual(vpu, {"name": "VPU.exe", "canStart": False, "missing": ["libcef.dll"],
                               "loaderErrors": {"count": 66, "last": ts(NOW - timedelta(minutes=4))}})
        self.assertNotIn("not found", json.dumps(vpu))        # no pop-up text

    def test_failed_scan_is_null(self):
        for b in (None, {"error": True}):
            self.assertIsNone(build({"binaries": b})["programs"])
        for over in ({"present": False}, {"readable": False}, {"scanned": 0}):
            self.assertIsNone(build({"binaries": binaries(**over)})["programs"][0]["canStart"], over)

    def test_missing_list_capped(self):
        vpu = build({"binaries": binaries(missing=[f"lib{i}" + "x" * 60 + ".dll" for i in range(9)])})["programs"][0]
        self.assertEqual(len(vpu["missing"]), 5)
        self.assertTrue(all(len(m) == 40 for m in vpu["missing"]))

    def test_same_verdict_as_the_finding(self):
        live, recent, old = (timedelta(minutes=30), timedelta(hours=5), timedelta(days=3))
        cases = [binaries(), binaries(missing=["libcef.dll"]), binaries(popup_age=live),
                 binaries(popup_age=recent), binaries(popup_age=old), binaries(popup_age=recent, stuck=True)]
        for b in cases:
            cant = any(p["canStart"] is False for p in build({"binaries": b})["programs"])
            self.assertEqual(cant, self.blocks_the_stream(b), json.dumps(b)[:200])

    def test_an_old_popup_is_shown_but_the_program_can_start(self):
        vpu = build({"binaries": binaries(popup_age=timedelta(days=3))})["programs"][0]
        self.assertTrue(vpu["canStart"])
        self.assertEqual(vpu["loaderErrors"]["count"], 66)


# ── Windows, time zone and clock (PV-75) ─────────────────────────────────────

NTP = {"offsetSeconds": 0.2134, "status": "ok", "source": "0.us.pool.ntp.org",
       "configuredSource": "0.us.pool.ntp.org", "networkSynced": True}
UBR = {"ubr": 253, "currentBuild": "17763", "fullBuild": "17763.253"}


class TestEnvironment(unittest.TestCase):
    def test_full_block(self):
        e = build({"identity": IDENTITY, "ubr": UBR, "ntp": NTP})["environment"]
        self.assertEqual(e, {
            "os": {"name": "Windows 10 IoT Enterprise LTSC 2019", "build": "17763", "ubr": 253},
            "timeZone": {"caption": "(UTC-05:00) Eastern Time (US & Canada)", "us": True},
            "clock": {"offsetSeconds": 0.213, "status": "ok", "source": "0.us.pool.ntp.org", "synced": True}})
        self.assertNotIn(HOSTNAME, json.dumps(e))

    def test_non_us_time_zone_agrees_with_the_blocker(self):
        ident = dict(IDENTITY, timezone="(UTC+02:00) Jerusalem", timezoneId="Israel Standard Time")
        e = build({"identity": ident})["environment"]
        self.assertFalse(e["timeZone"]["us"])
        codes = {f["code"] for f in main._compute_findings(ident, None, None, None)}
        self.assertIn("tz-non-us", codes)
        us = {f["code"] for f in main._compute_findings(IDENTITY, None, None, None)}
        self.assertNotIn("tz-non-us", us)

    def test_failed_time_read_is_null(self):
        e = build({"identity": IDENTITY, "ntp": None})["environment"]
        self.assertIsNone(e["clock"])
        e = build({"identity": IDENTITY, "ntp": dict(NTP, offsetSeconds=None, status="fail", networkSynced=None)})["environment"]
        self.assertEqual(e["clock"], {"offsetSeconds": None, "status": "fail", "source": "0.us.pool.ntp.org", "synced": None})
        e = build({"identity": IDENTITY, "ntp": dict(NTP, status="weird")})["environment"]
        self.assertIsNone(e["clock"]["status"])             # unknown, never "ok"

    def test_older_agent_or_nothing_read(self):
        self.assertIsNone(build({})["environment"])
        self.assertIsNone(build({"identity": {"error": True}, "ubr": {"error": True}})["environment"])

    def test_build_without_identity_and_a_mismatched_ubr(self):
        e = build({"ubr": UBR})["environment"]
        self.assertEqual(e["os"], {"name": None, "build": "17763", "ubr": 253})
        e = build({"identity": IDENTITY, "ubr": dict(UBR, currentBuild="19044")})["environment"]
        self.assertIsNone(e["os"]["ubr"])                    # a patch level for another build is no answer

    def test_clock_jitter_doesnt_move_the_fingerprint_but_drift_does(self):
        def t(off, status="ok"):
            return build({"identity": IDENTITY, "ntp": dict(NTP, offsetSeconds=off, status=status)})
        self.assertEqual(fp(t(0.21)), fp(t(-0.38)))
        self.assertNotEqual(fp(t(0.21)), fp(t(4.2)))
        self.assertNotEqual(fp(t(0.21)), fp(t(0.21, "warn")))


# ── The monitor, size and caching ────────────────────────────────────────────

class TestMonitorAndSize(unittest.TestCase):
    def test_new_reads_ride_the_monitor_cache(self):
        import monitor_once
        ttl = monitor_once.SLOW_COLLECTOR_TTLS
        self.assertGreaterEqual(ttl.get("Get-WindowsUbr.ps1", 0), 3600)
        self.assertGreaterEqual(ttl.get("Test-NtpDrift.ps1", 0), 3600)
        self.assertGreaterEqual(ttl.get("Get-PoePower.ps1", 0), 3600)

    def test_the_dashboard_hands_the_monitor_what_these_blocks_read(self):
        powershell._PS_SEMAPHORE = None
        raw = {}
        asyncio.run(main._collect_dashboard(raw_out=raw))
        for key in ("services", "installed_sw", "binaries", "disk_health", "network_config", "identity"):
            self.assertIsInstance(raw.get(key), dict, key)

    def worst(self):
        long = "X" * 300
        raw = {"identity": IDENTITY, "network_config": network(), "poe": poe_read(), "ubr": UBR, "ntp": NTP,
               "reboots": reboots([dict(restart(1 + i % 28), source=long, reasonText=long) for i in range(40)]),
               "disk_health": disk_health(volumes=[{"deviceID": f"{chr(67 + i)}:", "freeSpaceGB": 1.0,
                                                    "sizeGB": 99999.0} for i in range(12)]),
               "installed_sw": software(400, displayName=long, displayVersion=long, publisher=long),
               "binaries": binaries(missing=[long] * 9, popup_age=timedelta(minutes=1))}
        raw["installed_sw"]["software"] = [dict(r, displayName=f"{i:03d}{long}") for i, r in
                                           enumerate(raw["installed_sw"]["software"])]
        return raw

    def test_never_over_the_workers_telemetry_cap(self):
        t = build(self.worst(), dash_services())
        size = len(json.dumps(t, separators=(",", ":")).encode("utf-8"))
        self.assertLessEqual(size, T._TELEMETRY_MAX_BYTES, size)
        self.assertLess(T._TELEMETRY_MAX_BYTES, 16 * 1024)   # MAX_TELEMETRY_BYTES in the check-in Worker
        # The cut falls on the application list, which still says how long it was.
        self.assertLess(len(t["applications"]), 150)
        self.assertEqual(t["applicationsTotal"], 400)
        self.assertEqual(len(t["power"]["events"]), 20)

    def test_a_typical_unit_keeps_its_whole_list(self):
        t = build(dict(self.worst(), installed_sw=software(90), reboots=reboots([restart(12)])), dash_services())
        self.assertEqual(len(t["applications"]), 90)

    def test_the_demo_pass_carries_every_block(self):
        powershell._PS_SEMAPHORE = None
        raw = {}
        dash = asyncio.run(main._collect_dashboard(raw_out=raw))
        powershell._PS_SEMAPHORE = None
        asyncio.run(T._collect_telemetry_extras(raw))
        t = T._build_telemetry(dash, raw)
        for key in ("services", "applications", "programs", "environment"):
            self.assertIsNotNone(t[key], key)
        self.assertIsNotNone(t["cameras"]["nic"]["poe"])
        self.assertIsNotNone(t["environment"]["clock"])
        self.assertTrue(all(e["time"] for e in t["power"]["events"]))


if __name__ == "__main__":
    unittest.main()
