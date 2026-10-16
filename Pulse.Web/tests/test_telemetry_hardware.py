"""pulse.telemetry/v1 `hardware` block (PV-64): what the box is, never who it is."""

import asyncio
import copy
import json
import os
import sys
import tempfile
import unittest

_APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import main  # noqa: E402  (binds the engine)
import powershell  # noqa: E402
from pulse_agent import telemetry as agent_telemetry  # noqa: E402

hw_block = agent_telemetry._telemetry_hardware
KEYS = {"model", "cpu", "memoryGb", "disks", "gpus", "bios"}
BIOS_SERIAL = "CZC9QX7LMN"
DISK_SERIAL = "Z9K1ABCDEFGH"
HOSTNAME = "PXLS2-55555"
ASSET_TAG = "PLAYON-ASSET-0042"


def desktop():
    """vpu-home's real collector output (HP EliteDesk 800 G4, PS 5.1,
    2026-10-16), with made-up serials and hostname put back in."""
    identity = {
        "computerSystem": {"name": HOSTNAME, "manufacturer": "HP", "model": "HP EliteDesk 800 G4 WKS TWR"},
        "bios": {"smbiosVersion": "Q01 Ver. 02.07.01", "releaseDate": "2019-04-22T20:00:00.0000000-04:00",
                 "serialNumber": BIOS_SERIAL},
        "assetTag": ASSET_TAG,
        "pixellot": {"vpuName": "PXLS2_55555 Test", "venueId": "5fdb1c042e3a86412c7a04b8"},
    }
    hardware = {
        "processors": [{"name": "Intel(R) Core(TM) i5-8500 CPU @ 3.00GHz", "numberOfCores": 6,
                        "numberOfLogicalProcessors": 6, "socketDesignation": "U3E1"}],
        "memory": [{"capacityGB": 16, "deviceLocator": "DIMM1", "partNumber": "HMA82GU6CJR8N-VK"},
                   {"capacityGB": 16, "deviceLocator": "DIMM3", "partNumber": "HMA82GU6CJR8N-VK"}],
        "gpus": [{"name": "NVIDIA GeForce GTX 1650", "adapterRAMMB": 4095, "vramMB": 4096,
                  "driverVersion": "32.0.15.7628", "vendor": "NVIDIA", "isDedicated": True},
                 {"name": "Intel(R) UHD Graphics 630", "adapterRAMMB": 1024, "vramMB": None,
                  "driverVersion": "24.20.100.6136", "vendor": "Intel", "isDedicated": False}],
        "diskDrives": [{"index": 0, "sizeGB": 931.51, "interfaceType": "SATA", "mediaType": "HDD",
                        "model": "TOSHIBA DT01ACA100", "serialNumber": DISK_SERIAL,
                        "firmwareRevision": "MS2OA8L0"}],
    }
    return {"identity": identity, "hardware": hardware}


def laptop():
    raw = desktop()
    raw["identity"]["computerSystem"]["model"] = "HP ZBook Fury 15 G8 Mobile Workstation PC"
    raw["hardware"]["processors"] = [{"name": "11th Gen Intel(R) Core(TM) i7-11850H @ 2.50GHz",
                                      "numberOfCores": 8, "numberOfLogicalProcessors": 16}]
    raw["hardware"]["gpus"] = [
        {"name": "Intel(R) UHD Graphics", "adapterRAMMB": 128, "vramMB": None, "driverVersion": "30.0.101.1340"},
        {"name": "NVIDIA RTX A2000 Laptop GPU", "adapterRAMMB": 4095, "vramMB": 4096,
         "driverVersion": "31.0.15.3623"},
    ]
    raw["hardware"]["diskDrives"] = [{"index": 0, "sizeGB": 476.94, "interfaceType": "NVMe", "mediaType": "SSD",
                                      "model": "SAMSUNG MZVL2512HCJQ-00BH1", "serialNumber": DISK_SERIAL}]
    return raw


class TestHardwareBlock(unittest.TestCase):
    def test_real_desktop(self):
        self.assertEqual(hw_block(desktop()), {
            "model": "HP EliteDesk 800 G4 WKS TWR",
            "cpu": {"name": "Intel(R) Core(TM) i5-8500 CPU @ 3.00GHz", "cores": 6, "threads": 6},
            "memoryGb": 32,
            "disks": [{"model": "TOSHIBA DT01ACA100", "sizeGb": 932, "type": "HDD"}],
            "gpus": [{"name": "NVIDIA GeForce GTX 1650", "driver": "32.0.15.7628", "vramMb": 4096},
                     {"name": "Intel(R) UHD Graphics 630", "driver": "24.20.100.6136", "vramMb": 1024}],
            # The collector prints UTC midnight as local time: 04-22 20:00 ET is 04-23.
            "bios": {"version": "Q01 Ver. 02.07.01", "date": "2019-04-23"},
        })

    def test_laptop(self):
        h = hw_block(laptop())
        self.assertEqual(h["model"], "HP ZBook Fury 15 G8 Mobile Workstation PC")
        self.assertEqual((h["cpu"]["cores"], h["cpu"]["threads"]), (8, 16))
        self.assertEqual([g["name"] for g in h["gpus"]], ["Intel(R) UHD Graphics", "NVIDIA RTX A2000 Laptop GPU"])
        self.assertEqual(h["disks"], [{"model": "SAMSUNG MZVL2512HCJQ-00BH1", "sizeGb": 477, "type": "NVMe"}])

    def test_demo_pass(self):
        powershell._PS_SEMAPHORE = None
        raw = {}
        dash = asyncio.run(main._collect_dashboard(raw_out=raw))
        h = agent_telemetry._build_telemetry(dash, raw)["hardware"]
        self.assertEqual(set(h), KEYS)
        self.assertEqual(h["memoryGb"], 32)
        self.assertEqual(h["bios"], {"version": "U50 Ver. 01.02.03", "date": "2023-04-12"})
        self.assertEqual(h["disks"][0]["type"], "SSD")

    def test_memory_is_the_dimm_sum_the_ram_finding_reads(self):
        raw = desktop()
        raw["hardware"]["memory"] = [{"capacityGB": 8}, {"capacityGB": 7.99}]
        self.assertEqual(hw_block(raw)["memoryGb"], 16)
        self.assertEqual(hw_block(raw)["memoryGb"], round(main._total_ram_gb(raw["hardware"], None)))
        raw["hardware"]["memory"] = []
        self.assertIsNone(hw_block(raw)["memoryGb"])      # unknown, not the OS-visible guess

    # ── Unknown is null ──────────────────────────────────────────────────────
    def test_identity_collector_failed(self):
        raw = desktop()
        raw["identity"] = {"error": True, "message": "Timeout"}
        h = hw_block(raw)
        self.assertIsNone(h["model"])
        self.assertIsNone(h["bios"])
        self.assertEqual(h["memoryGb"], 32)

    def test_hardware_collector_failed(self):
        raw = desktop()
        raw["hardware"] = {"error": True, "message": "Get-Hardware.ps1 failed"}
        h = hw_block(raw)
        for k in ("cpu", "memoryGb", "disks", "gpus"):
            self.assertIsNone(h[k], k)
        self.assertEqual(h["model"], "HP EliteDesk 800 G4 WKS TWR")

    def test_switched_off_by_fleet_control(self):
        raw = desktop()
        raw["hardware"] = {"error": "Switched off by fleet control", "skipped": True}
        self.assertIsNone(hw_block(raw)["gpus"])

    def test_both_failed_or_absent_is_no_block(self):
        self.assertIsNone(hw_block({"identity": {"error": True}, "hardware": {"error": True}}))
        self.assertIsNone(hw_block({}))
        self.assertIsNone(agent_telemetry._build_telemetry({}, {})["hardware"])

    def test_missing_fields_are_null(self):
        raw = desktop()
        raw["identity"]["bios"] = {"serialNumber": BIOS_SERIAL}
        raw["identity"]["computerSystem"]["model"] = "To Be Filled By O.E.M."
        raw["hardware"]["processors"] = [{"name": "Some CPU"}]
        raw["hardware"]["gpus"] = [{"name": "NVIDIA T1000", "adapterRAMMB": 4095}]   # no vramMB: older build
        raw["hardware"]["diskDrives"] = [{"model": "Old disk", "interfaceType": "IDE"}]  # WMI fallback
        h = hw_block(raw)
        self.assertIsNone(h["model"])
        self.assertIsNone(h["bios"])
        self.assertEqual(h["cpu"], {"name": "Some CPU", "cores": None, "threads": None})
        self.assertIsNone(h["gpus"][0]["vramMb"])          # 4095 is the 32-bit ceiling, not a size
        self.assertEqual(h["disks"], [{"model": "Old disk", "sizeGb": None, "type": None}])

    def test_no_gpu_is_an_empty_list_not_unknown(self):
        raw = desktop()
        raw["hardware"]["gpus"] = []
        self.assertEqual(hw_block(raw)["gpus"], [])

    def test_remote_session_adapters_are_left_out(self):
        raw = desktop()
        raw["hardware"]["gpus"] += [{"name": "Microsoft Remote Display Adapter"},
                                    {"name": "LogMeIn Mirror Driver"}]
        before = hw_block(desktop())
        self.assertEqual(hw_block(raw)["gpus"], before["gpus"])
        raw["hardware"]["gpus"] = [{"name": "Microsoft Basic Display Adapter"}]   # no driver: keep
        self.assertEqual(hw_block(raw)["gpus"][0]["name"], "Microsoft Basic Display Adapter")

    def test_several_disks(self):
        raw = desktop()
        raw["hardware"]["diskDrives"] = [
            {"index": 2, "model": "SanDisk Cruzer", "sizeGB": 28.6, "interfaceType": "USB", "mediaType": "SSD"},
            {"index": 0, "model": "Samsung SSD 970 EVO 1TB", "sizeGB": 931.51, "interfaceType": "NVMe",
             "mediaType": "SSD"},
            {"index": 1, "model": "Samsung SSD 870 EVO 500GB", "sizeGB": 465.76, "interfaceType": "SATA",
             "mediaType": "SSD"},
            {"index": 3, "model": "WDC WD40EFRX", "sizeGB": 3726.02, "interfaceType": "SATA", "mediaType": "HDD"},
            {"index": 4, "model": "Unknown media", "sizeGB": 100, "interfaceType": "SATA"},
        ]
        self.assertEqual(hw_block(raw)["disks"], [
            {"model": "Samsung SSD 970 EVO 1TB", "sizeGb": 932, "type": "NVMe"},
            {"model": "Samsung SSD 870 EVO 500GB", "sizeGb": 466, "type": "SSD"},
            {"model": "SanDisk Cruzer", "sizeGb": 29, "type": "USB"},
            {"model": "WDC WD40EFRX", "sizeGb": 3726, "type": "HDD"},
            {"model": "Unknown media", "sizeGb": 100, "type": "SATA"},
        ])

    # ── Caps and size ────────────────────────────────────────────────────────
    def worst_case(self):
        raw = desktop()
        long = "X" * 200
        raw["identity"]["computerSystem"]["model"] = long
        raw["identity"]["bios"]["smbiosVersion"] = long
        raw["hardware"]["processors"] = [{"name": long, "numberOfCores": 64, "numberOfLogicalProcessors": 128}] * 2
        raw["hardware"]["diskDrives"] = [{"index": i, "model": long, "sizeGB": 99999.99,
                                          "interfaceType": "SATA", "mediaType": "HDD",
                                          "serialNumber": f"SER{i:09d}"} for i in range(12)]
        raw["hardware"]["gpus"] = [{"name": long, "driverVersion": long, "vramMB": 49152}] * 6
        return raw

    def test_caps_and_trims(self):
        h = hw_block(self.worst_case())
        self.assertEqual(len(h["disks"]), 8)
        self.assertEqual(len(h["gpus"]), 4)
        names = [h["model"], h["cpu"]["name"]] + [d["model"] for d in h["disks"]] + [g["name"] for g in h["gpus"]]
        self.assertTrue(all(len(s) == 80 for s in names))
        versions = [h["bios"]["version"]] + [g["driver"] for g in h["gpus"]]
        self.assertTrue(all(len(s) == 32 for s in versions))
        self.assertEqual(h["cpu"]["cores"], 128)            # two sockets summed

    def test_worst_case_under_2_kb(self):
        # Python's default separators: larger than the Worker's JSON.stringify.
        size = len(json.dumps(hw_block(self.worst_case())).encode("utf-8"))
        self.assertLess(size, 2048, size)

    def test_typical_unit_is_small(self):
        self.assertLess(len(json.dumps(hw_block(desktop())).encode("utf-8")), 800)

    # ── Never a serial ───────────────────────────────────────────────────────
    def test_never_a_serial_or_hostname(self):
        raw = desktop()
        # An odd OEM puts the serial in a model string; a USB disk's model
        # carries its own serial; the hostname turns up in a GPU name.
        raw["identity"]["computerSystem"]["model"] = f"Custom PC {BIOS_SERIAL}"
        raw["identity"]["bios"]["smbiosVersion"] = f"Ver {ASSET_TAG}"
        raw["hardware"]["diskDrives"].append({"index": 1, "model": f"USB Disk {DISK_SERIAL[:4]}{DISK_SERIAL[4:]}",
                                              "sizeGB": 32, "interfaceType": "USB", "serialNumber": DISK_SERIAL})
        raw["hardware"]["diskDrives"].append({"index": 2, "model": "Plain disk", "sizeGB": 32,
                                              "interfaceType": "SATA", "serialNumber": "WD-WCC4E0123456"})
        raw["hardware"]["gpus"].append({"name": f"{HOSTNAME.lower()} display", "driverVersion": "1"})
        raw["hardware"]["processors"][0]["serialNumber"] = "CPU-SERIAL-77"
        raw["hardware"]["processors"][0]["processorId"] = "BFEBFBFF000906EA"
        raw["hardware"]["memory"][0]["serialNumber"] = "DIMM-SERIAL-99"
        t = agent_telemetry._build_telemetry({}, raw)
        text = json.dumps(t)
        for secret in (BIOS_SERIAL, DISK_SERIAL, "WD-WCC4E0123456", HOSTNAME, HOSTNAME.lower(), ASSET_TAG,
                       "CPU-SERIAL-77", "BFEBFBFF000906EA", "DIMM-SERIAL-99", "HMA82GU6CJR8N", "MS2OA8L0"):
            self.assertNotIn(secret, text)
        self.assertNotIn("serial", text.lower())
        self.assertNotIn("hostname", text.lower())
        self.assertIsNone(t["hardware"]["model"])
        self.assertIsNone(t["hardware"]["bios"]["version"])
        names = [g["name"] for g in t["hardware"]["gpus"]]
        self.assertIn(None, names)                         # the GPU named after the host
        self.assertEqual([d["model"] for d in t["hardware"]["disks"]][1:], [None, "Plain disk"])

    def test_only_the_contract_fields(self):
        h = hw_block(desktop())
        self.assertEqual(set(h), KEYS)
        self.assertEqual(set(h["cpu"]), {"name", "cores", "threads"})
        self.assertEqual(set(h["bios"]), {"version", "date"})
        self.assertTrue(all(set(d) == {"model", "sizeGb", "type"} for d in h["disks"]))
        self.assertTrue(all(set(g) == {"name", "driver", "vramMb"} for g in h["gpus"]))

    def test_bios_dates(self):
        f = agent_telemetry._hw_bios_date
        self.assertEqual(f("2019-04-22T20:00:00.0000000-04:00"), "2019-04-23")
        self.assertEqual(f("2023-04-12T00:00:00.0000000+00:00"), "2023-04-12")
        self.assertEqual(f("2023-04-12T00:00:00Z"), "2023-04-12")
        self.assertEqual(f("2023-04-12"), "2023-04-12")
        for bad in (None, "", "junk", "2023-13-40"):
            self.assertIsNone(f(bad))


class TestHardwareCacheAndFingerprint(unittest.TestCase):
    def fp(self, raw):
        return agent_telemetry._telemetry_fingerprint(agent_telemetry._build_telemetry({}, raw), [])

    def test_fingerprint_moves_on_a_hardware_change_only(self):
        base = self.fp(desktop())
        self.assertEqual(self.fp(desktop()), base)
        self.assertEqual(self.fp(copy.deepcopy(desktop())), base)
        # Fields the block leaves out don't count either.
        noise = desktop()
        noise["hardware"]["processors"][0]["maxClockSpeedMHz"] = 2999
        noise["hardware"]["gpus"][0]["driverDate"] = "2099-01-01T00:00:00"
        self.assertEqual(self.fp(noise), base)
        for change in ("driver", "dimm", "disk", "bios"):
            raw = desktop()
            if change == "driver":
                raw["hardware"]["gpus"][0]["driverVersion"] = "32.0.15.9999"
            elif change == "dimm":
                raw["hardware"]["memory"].pop()
            elif change == "disk":
                raw["hardware"]["diskDrives"].append({"index": 1, "model": "New SSD", "sizeGB": 500,
                                                      "interfaceType": "NVMe"})
            else:
                raw["identity"]["bios"]["smbiosVersion"] = "Q01 Ver. 02.08.00"
            self.assertNotEqual(self.fp(raw), base, change)

    def test_building_the_block_runs_no_collector(self):
        saved = main.run_ps

        async def boom(*a, **k):
            raise AssertionError("the hardware block must not start a collector")
        main.run_ps = boom
        try:
            self.assertIsNotNone(hw_block(desktop()))
            agent_telemetry._build_telemetry({}, desktop())
        finally:
            main.run_ps = saved

    def test_the_monitor_reads_hardware_from_its_disk_cache(self):
        """Second pass (a new tick process) runs Get-Hardware.ps1 zero times
        and builds the same block, so no new work per pass."""
        import monitor_once
        self.assertGreaterEqual(monitor_once.SLOW_COLLECTOR_TTLS.get("Get-Hardware.ps1", 0), 3600)
        names = ("_PS_CONCURRENCY", "_PS_LOW_PRIORITY", "_PS_SEMAPHORE", "_DISK_CACHE_PATH",
                 "_DISK_CACHE_TTLS", "_PS_BATCH", "_PS_SKIP")
        saved = {n: getattr(powershell, n) for n in names}
        with tempfile.TemporaryDirectory() as tmp:
            try:
                powershell.configure_background(disk_cache_path=os.path.join(tmp, "cache.json"),
                                                disk_cache_ttls=monitor_once.SLOW_COLLECTOR_TTLS)
                blocks, runs = [], []
                for _ in range(2):
                    powershell._RESULT_CACHE.clear()          # a tick is a fresh process
                    powershell._PS_SEMAPHORE = None           # and a fresh event loop
                    powershell.LOG_BUFFER.clear()
                    raw = {}
                    dash = asyncio.run(main._collect_dashboard(raw_out=raw))
                    blocks.append(agent_telemetry._build_telemetry(dash, raw)["hardware"])
                    runs.append(sum(1 for e in powershell.LOG_BUFFER if e["script"] == "Get-Hardware.ps1"))
                self.assertEqual(runs, [1, 0])
                self.assertEqual(blocks[0], blocks[1])
                self.assertIsNotNone(blocks[0]["gpus"])
            finally:
                for n, v in saved.items():
                    setattr(powershell, n, v)
                powershell._RESULT_CACHE.clear()


if __name__ == "__main__":
    unittest.main()
