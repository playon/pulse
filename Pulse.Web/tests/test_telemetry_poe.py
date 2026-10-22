"""PV-66: bounded PoE collection and unknown-safe telemetry. No native DLL is loaded."""

import asyncio
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

APP = Path(__file__).resolve().parents[1] / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import main  # noqa: E402 (binds the shared engine)
import monitor_once  # noqa: E402
import powershell  # noqa: E402
from pulse_agent import telemetry as T  # noqa: E402

SCRIPT = "Get-PoePower.ps1"
SOURCE = APP.parent / "scripts" / SCRIPT


def network(chip="I210"):
    return {"adapters": [{"name": "Fixture camera port", "interfaceDescription": "Intel " + chip,
                           "physicalMediaType": "802.3", "pciBus": 1}]}


def reading():
    return {"supported": True, "available": True, "nicModel": "I210",
            "dllPath": "DO-NOT-SEND", "reason": "DO-NOT-SEND",
            "budget": {"totalW": 62.7, "consumedW": 11.3, "remainingW": 51.4,
                       "tempC": 41.2, "underPowered": False, "healthyFloorW": 55},
            "ports": [{"port": n, "poeOn": n < 3, "voltage": 54.3 if n < 3 else 0.187,
                       "current": 0.104 if n < 3 else 0, "watts": 5.6 if n < 3 else 0,
                       "readOk": True} for n in range(1, 5)]}


def build(poe, chip="I210"):
    return T._build_telemetry({}, {"network_config": network(chip), "poe": poe})


class TestPoeTelemetry(unittest.TestCase):
    def test_gie74p_carries_only_the_card_figures(self):
        t = build(reading())
        poe = t["cameras"]["nic"]["poe"]
        self.assertEqual(poe["budget"], {"totalW": 62.7, "consumedW": 11.3, "remainingW": 51.4, "tempC": 41.2})
        self.assertEqual(poe["ports"][0], {"port": 1, "on": True, "volts": 54.3, "amps": 0.104, "watts": 5.6})
        self.assertFalse(poe["underPowered"])
        self.assertNotIn("DO-NOT-SEND", json.dumps(t))
        self.assertLess(T._telemetry_bytes(poe), 600)
        self.assertLess(T._telemetry_bytes(t), 16 * 1024)

    def test_gie64_and_gie74p_an_cannot_inherit_a_stale_supported_read(self):
        for chip in ("82574L", "I350", "I354"):
            nic = build(reading(), chip)["cameras"]["nic"]
            self.assertFalse(nic["poeSupported"])
            self.assertIsNone(nic["poe"])

    def test_missing_crash_latched_and_unreadable_collectors_are_null(self):
        for value in (None, {}, {"error": True}, {"supported": False, "available": False},
                      {"supported": True, "available": False, "reason": "crash guard latched"},
                      {"supported": True, "available": True, "budget": None}):
            self.assertIsNone(build(value)["cameras"]["nic"]["poe"])

    def test_unreadable_port_is_unknown_not_off_and_temperature_is_nullable(self):
        r = reading()
        r["ports"][0].update(readOk=False, poeOn=False, watts=0)
        r["budget"]["tempC"] = None
        poe = build(r)["cameras"]["nic"]["poe"]
        self.assertEqual(poe["ports"][0], {"port": 1, "on": None, "volts": None, "amps": None, "watts": None})
        self.assertIsNone(poe["budget"]["tempC"])
        self.assertFalse(poe["ports"][3]["on"])
        self.assertEqual(poe["ports"][3]["watts"], 0)

    def test_only_four_unique_pse_ports_can_enter_the_payload(self):
        r = reading()
        r["ports"] += [r["ports"][0]] * 100 + [{"port": 0}, {"port": 5}]
        self.assertEqual(len(build(r)["cameras"]["nic"]["poe"]["ports"]), 4)

    def test_drift_does_not_post_but_power_state_or_underpower_does(self):
        before = build(reading())
        changed = copy.deepcopy(before)
        poe = changed["cameras"]["nic"]["poe"]
        poe["budget"].update(totalW=60.9, remainingW=49.6, tempC=42)
        poe["ports"][0].update(watts=5.5, volts=54.2, amps=0.103)
        fingerprint = lambda t: T._telemetry_fingerprint(t, [])
        self.assertEqual(fingerprint(before), fingerprint(changed))
        self.assertEqual(poe["budget"]["totalW"], 60.9)  # fingerprint must not mutate the report
        poe["underPowered"] = True
        self.assertNotEqual(fingerprint(before), fingerprint(changed))
        poe["underPowered"] = False
        poe["ports"][0]["on"] = False
        self.assertNotEqual(fingerprint(before), fingerprint(changed))
        self.assertNotEqual(fingerprint(before), fingerprint(build(None)))

    def test_large_report_still_fits_with_poe(self):
        r = {"network_config": network(), "poe": reading(),
             "installed_sw": {"software": [{"displayName": "Fixture app " + str(i) + "x" * 60,
                                               "displayVersion": "1" * 32, "publisher": "Fixture publisher"}
                                              for i in range(150)]}}
        t = T._build_telemetry({}, r)
        self.assertIsNotNone(t["cameras"]["nic"]["poe"])
        self.assertLessEqual(T._telemetry_bytes(t), T._TELEMETRY_MAX_BYTES)


class TestPoeMonitorCache(unittest.TestCase):
    NAMES = ("_PS_CONCURRENCY", "_PS_LOW_PRIORITY", "_PS_SEMAPHORE", "_DISK_CACHE_PATH",
             "_DISK_CACHE_TTLS", "_PS_BATCH", "_PS_SKIP")

    def setUp(self):
        self.saved = {n: getattr(powershell, n) for n in self.NAMES}
        self.tmp = tempfile.TemporaryDirectory()
        powershell.configure_background(disk_cache_path=os.path.join(self.tmp.name, "cache.json"),
                                        disk_cache_ttls=monitor_once.SLOW_COLLECTOR_TTLS)

    def tearDown(self):
        for n, v in self.saved.items():
            setattr(powershell, n, v)
        powershell._RESULT_CACHE.clear()
        self.tmp.cleanup()

    def run_tick(self):
        powershell._RESULT_CACHE.clear()  # fresh monitor process, same disk cache
        powershell._PS_SEMAPHORE = None
        return asyncio.run(powershell.run_ps(SCRIPT, timeout=20))

    def test_hourly_cached_read_uses_isolated_process_not_batch(self):
        self.assertEqual(monitor_once.SLOW_COLLECTOR_TTLS[SCRIPT], 3600)
        with mock.patch.object(powershell, "DEMO_MODE", False), \
             mock.patch.object(powershell, "_run_ps_inner", new_callable=mock.AsyncMock, return_value=reading()) as isolated, \
             mock.patch.object(powershell, "_batch_submit", new_callable=mock.AsyncMock) as batch:
            self.assertEqual(self.run_tick(), self.run_tick())
            self.assertEqual(isolated.await_count, 1)
            batch.assert_not_awaited()

    def test_three_unfinished_attempts_then_latched_result_stops_retries(self):
        crash = {"error": True, "exitCode": -1073741819}
        latched = {"supported": True, "available": False, "reason": "three unfinished attempts"}
        with mock.patch.object(powershell, "DEMO_MODE", False), \
             mock.patch.object(powershell.time, "time", return_value=10000) as clock, \
             mock.patch.object(powershell, "_run_ps_inner", new_callable=mock.AsyncMock,
                               side_effect=[crash, crash, crash, latched]) as isolated:
            results = []
            for hour in range(4):
                clock.return_value = 10000 + hour * 3600
                results.append(self.run_tick())
                clock.return_value += 300
                self.assertEqual(self.run_tick(), results[-1])  # no 5-minute crash loop
                self.assertEqual(isolated.await_count, hour + 1)
            self.assertEqual(results[-1], latched)
            self.assertTrue(all(T._telemetry_poe(r) is None for r in results))

    def test_fleet_skip_never_starts_the_native_process(self):
        powershell._PS_SKIP = {SCRIPT.lower()}
        with mock.patch.object(powershell, "_run_ps_inner", new_callable=mock.AsyncMock) as isolated:
            self.assertTrue(self.run_tick()["skipped"])
            isolated.assert_not_awaited()


@unittest.skipUnless(shutil.which("pwsh"), "local pwsh required for managed-only collector fixtures")
class TestPoeCollectorGuard(unittest.TestCase):
    """Execute the real gates and reads with a managed fixture shim, NEVER SmartPoE.

    Remove the entire production shim/loader before execution, not just its
    DLL path. An accidental gate regression still cannot load native code.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sentinel = Path(self.tmp.name) / "PulsePoE-probe.sentinel"
        source = SOURCE.read_text(encoding="ascii")
        self.source = source[:source.index("if (-not ([System.Management.Automation.PSTypeName]")] + source[source.index("$registered = $false"):]
        self.assertNotIn("DllImport", self.source.split("#>", 1)[1])

    def tearDown(self):
        self.tmp.cleanup()

    def probe(self, chip="I210", crash="", temp_rc=0):
        shim = """
namespace Pulse {
 public static class AdlinkPoE {
  public static short SmartPoE_Register_Card(ushort c) { return 0; }
  public static short SmartPoE_Release_Card(ushort c) { RELEASE; return 0; }
  public static short SmartPoE_Get_Temperature(ushort c, out double v) { v=41.2; return TEMP_RC; }
  public static short SmartPoE_Get_POEConsPowbudget(ushort c, out double v) { READ; v=11.3; return 0; }
  public static short SmartPoE_Get_POELeftPowbudget(ushort c, out double v) { v=51.4; return 0; }
  public static short SmartPoE_Get_PSEPortVoltage(ushort c, ushort p, out double v) { v=54.3; return 0; }
  public static short SmartPoE_Get_PSEPortCurrent(ushort c, ushort p, out double v) { v=0.104; return 0; }
 }
}
""".replace("RELEASE;", "System.Environment.Exit(86);" if crash == "release" else "") \
   .replace("READ;", "System.Environment.Exit(86);" if crash == "read" else "") \
   .replace("TEMP_RC", str(temp_rc))
        harness = """
function Get-NetAdapter { [pscustomobject]@{ InterfaceDescription = 'Intel %s' } }
function Test-Path {
 param([string]$LiteralPath)
 if ($LiteralPath -like '*SmartPoE.dll') { return $true }
 Microsoft.PowerShell.Management\\Test-Path -LiteralPath $LiteralPath
}
Add-Type -TypeDefinition @'
%s
'@
%s
""" % (chip, shim, self.source)
        env = {**os.environ, "TEMP": self.tmp.name, "SystemRoot": self.tmp.name}
        return subprocess.run([shutil.which("pwsh"), "-NoProfile", "-NonInteractive", "-Command", harness],
                              env=env, text=True, capture_output=True, timeout=20)

    def test_unsupported_models_exit_before_any_native_attempt(self):
        for chip in ("82574L", "I350", "I354"):
            p = self.probe(chip)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertFalse(json.loads(p.stdout)["supported"])
            self.assertFalse(self.sentinel.exists())

    def test_getter_and_release_crashes_both_latch_after_three_fresh_processes(self):
        for crash in ("read", "release"):
            self.sentinel.unlink(missing_ok=True)
            for count in range(1, 4):
                p = self.probe(crash=crash)
                self.assertEqual(p.returncode, 86, p.stderr)
                self.assertEqual(p.stdout.strip(), "")  # no successful JSON before release
                self.assertEqual(self.sentinel.read_text().strip(), str(count))
            p = self.probe(crash=crash)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertFalse(json.loads(p.stdout)["available"])
            self.assertEqual(self.sentinel.read_text().strip(), "3")

    def test_success_resets_guard_and_failed_temperature_is_null(self):
        self.sentinel.write_text("2")
        p = self.probe(temp_rc=1)
        self.assertEqual(p.returncode, 0, p.stderr)
        r = json.loads(p.stdout)
        self.assertTrue(r["available"])
        self.assertEqual(r["budget"]["totalW"], 62.7)
        self.assertIsNone(r["budget"]["tempC"])
        self.assertEqual([r["port"] for r in r["ports"]], [1, 2, 3, 4])
        self.assertFalse(self.sentinel.exists())

    def test_unreadable_or_unsavable_sentinel_fails_closed(self):
        self.sentinel.write_text("corrupted")
        p = self.probe(crash="read")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertFalse(json.loads(p.stdout)["available"])
        self.sentinel.unlink()
        self.sentinel.mkdir()  # not a writable sentinel file
        p = self.probe(crash="read")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertFalse(json.loads(p.stdout)["available"])


if __name__ == "__main__":
    unittest.main()
