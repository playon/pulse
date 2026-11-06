"""TLS flight parsing in real PowerShell, plus the Network copy consumers.

Only extracted function definitions run: never the collector's live sweep.
Windows schannel / PowerShell 5.1 still needs a real-VPU validation.
"""
import base64
import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

WEB = Path(__file__).resolve().parents[1]
SCRIPT = WEB / "scripts" / "Test-TlsInspection.ps1"
JS = WEB / "app" / "static" / "app.js"
PWSH = shutil.which("pwsh") or shutil.which("powershell")
NODE = shutil.which("node")
sys.path.insert(0, str(WEB / "app"))
import main
from pulse_agent import telemetry


def function(text, name):
    match = re.search(r"^function " + re.escape(name) + r"\b.*?^}\n", text, re.M | re.S)
    if not match:
        raise AssertionError("Missing function " + name)
    return match.group(0)


def record(payload, kind=22, declared=None):
    return bytes([kind, 3, 3]) + (len(payload) if declared is None else declared).to_bytes(2, "big") + payload


def message(kind, payload=b""):
    return bytes([kind]) + len(payload).to_bytes(3, "big") + payload


@unittest.skipUnless(PWSH, "PowerShell isn't installed")
class TestTlsFlightPowerShell(unittest.TestCase):
    def run_ps(self, code):
        text = SCRIPT.read_text(encoding="ascii")
        definitions = "\n".join(function(text, name) for name in
                                ("Add-U16", "New-ClientHello", "Read-TlsFlight", "Test-RawFlight"))
        p = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-Command",
                            "$ErrorActionPreference = 'Stop'\n" + definitions + code],
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def flight(self, data):
        encoded = base64.b64encode(data).decode("ascii")
        return self.run_ps("\nRead-TlsFlight -Bytes ([Convert]::FromBase64String('" + encoded
                           + "')) | ConvertTo-Json -Compress")

    def test_hello_lengths_and_sni_include_high_length_byte(self):
        sni = "x" * 200 + ".example.org"
        encoded = self.run_ps("\n[Convert]::ToBase64String([byte[]](New-ClientHello '" + sni
                              + "')) | ConvertTo-Json -Compress")
        hello = base64.b64decode(encoded)
        self.assertEqual(hello[:3], bytes([22, 3, 1]))
        self.assertGreater(len(hello), 255)
        self.assertEqual(int.from_bytes(hello[3:5], "big"), len(hello) - 5)
        self.assertEqual(hello[5], 1)
        self.assertEqual(int.from_bytes(hello[6:9], "big"), len(hello) - 9)
        self.assertIn(sni.encode("ascii"), hello)
        # Decode the SNI extension's two nested length fields too.
        extensions_at = 9 + 2 + 32 + 1 + 2 + 16 + 2
        self.assertEqual(int.from_bytes(hello[extensions_at:extensions_at + 2], "big"),
                         len(hello) - extensions_at - 2)
        sni_at = extensions_at + 2
        self.assertEqual(hello[sni_at:sni_at + 2], b"\0\0")
        self.assertEqual(int.from_bytes(hello[sni_at + 2:sni_at + 4], "big"), len(sni) + 5)
        self.assertEqual(int.from_bytes(hello[sni_at + 4:sni_at + 6], "big"), len(sni) + 3)

    def test_complete_flight_across_record_boundaries(self):
        hs = message(2, b"s" * 300) + message(11, b"c" * 600) + message(12, b"k" * 20) + message(14)
        result = self.flight(record(hs[:350]) + record(hs[350:]))
        self.assertTrue(result["complete"])
        self.assertTrue(result["handshake"])
        self.assertFalse(result["alert"])
        self.assertEqual(result["messages"], "ServerHello, Certificate, ServerKeyExchange, ServerHelloDone")

    def test_hoover_partial_record_does_not_count_certificate_header_as_complete(self):
        payload = message(2, b"s" * 50) + bytes([11, 0, 0x35, 0]) + b"c" * 1385
        data = record(payload, declared=13824)
        self.assertEqual(len(data), 1448)
        result = self.flight(data)
        self.assertEqual(result["rawBytes"], 1448)
        self.assertEqual(result["messages"], "ServerHello")
        self.assertTrue(result["handshake"])
        self.assertFalse(result["complete"])

    def test_partial_message_high_length_byte_is_not_lost(self):
        result = self.flight(record(bytes([11, 1, 0, 0]) + b"c" * 300))
        self.assertEqual(result["messages"], "")
        self.assertFalse(result["complete"])

    def test_alert_is_not_a_truncated_reply(self):
        result = self.flight(record(message(2), declared=None) + record(bytes([2, 40]), kind=21))
        self.assertTrue(result["alert"])
        self.assertFalse(result["complete"])
        self.assertEqual(result["messages"], "ServerHello")

    def test_no_bytes_and_non_tls_are_not_partial_handshakes(self):
        for data in (b"", b"HTTP/1.1 403 Forbidden\r\n"):
            with self.subTest(data=data):
                result = self.flight(data)
                self.assertFalse(result["handshake"])
                self.assertFalse(result["complete"])

    def test_classification_keeps_inconclusive_alert_and_complete_probes_unchanged(self):
        text = SCRIPT.read_text(encoding="ascii")
        classification = text.split("    # ---- Did the server's reply get cut off mid-flight?", 1)[1].split("\n", 1)[1].split(
            "    # ---- Identify the filter behind the block", 1)[0]
        code = """
$flights = @{
    partial = @{ rawBytes=1448; messages='ServerHello'; handshake=$true; complete=$false; alert=$false }
    dropped = @{ rawBytes=0; messages=''; handshake=$false; complete=$false; alert=$false }
    failed = @{ rawBytes=$null; messages=''; handshake=$false; complete=$false; alert=$false }
    alert = @{ rawBytes=7; messages=''; handshake=$false; complete=$false; alert=$true }
    complete = @{ rawBytes=6000; messages='ServerHelloDone'; handshake=$true; complete=$true; alert=$false }
}
function Test-RawFlight { param($Domain) return $flights[$Domain] }
$results = foreach ($name in @('partial', 'dropped', 'failed', 'alert', 'complete')) {
    [ordered]@{ domain=$name; status='handshake-fail'; failureKind='protocol'; detail=$null; rawBytes=$null; serverMessages=$null }
}
"""
        # The collector intentionally samples only three. Exercise each outcome
        # as the first row in its own real classification block.
        code += "$allResults = $results; $classified = foreach ($item in $allResults) { $results = @($item)\n"
        code += classification + "\n$results\n}\nConvertTo-Json -InputObject @($classified) -Compress"
        results = {r["domain"]: r for r in self.run_ps(code)}
        self.assertEqual(results["partial"]["status"], "truncated")
        self.assertEqual(results["dropped"]["failureKind"], "dropped")
        for name in ("failed", "alert", "complete"):
            self.assertEqual(results[name]["status"], "handshake-fail")
            self.assertEqual(results[name]["failureKind"], "protocol")


@unittest.skipUnless(NODE, "Node isn't installed")
class TestTlsNetworkCopy(unittest.TestCase):
    def run_js(self, code):
        text = JS.read_text()
        definitions = "\n".join(function(text, name) for name in
                                ("_tlsIsFiltered", "_tlsReplyDetail", "_tlsBadge", "_buildNetIssues",
                                 "_srvIssue", "_netIssueRank", "_dnsResolvingFrom"))
        # badge is a formatting primitive: retain the label/tone as data here.
        setup = "function badge(text, type) { return {text, type}; }\nvar NET_TOP_FINDING_CODES = [];\n"
        p = subprocess.run([NODE, "-e", setup + definitions + code], capture_output=True, text=True, timeout=15)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def test_filter_states_have_red_badges_and_explain_the_reply(self):
        rows = [dict(status="truncated", rawBytes=1448, serverMessages="ServerHello", filterVendor="FortiGuard"),
                dict(status="handshake-fail", failureKind="dropped", rawBytes=0)]
        results = self.run_js("\nconsole.log(JSON.stringify(" + json.dumps(rows) + ".map(r => ({"
                              "badge: _tlsBadge(r.status, r.failureKind), detail: _tlsReplyDetail(r),"
                              "filtered: _tlsIsFiltered(r)}))));")
        for result in results:
            self.assertEqual(result["badge"], {"text": "Blocked by filter", "type": "fail"})
            self.assertTrue(result["filtered"])
        for phrase in ("1448 bytes", "rest was dropped", "ServerHello", "FortiGuard"):
            self.assertIn(phrase, results[0]["detail"])
        self.assertIn("no TLS reply arrived", results[1]["detail"])

    def test_dropped_row_uses_server_finding_without_generic_handshake_warning(self):
        row = {"domain": "singular.live", "status": "handshake-fail", "failureKind": "dropped"}
        findings = main._tls_findings({"results": [row]})
        issues = self.run_js("\nconsole.log(JSON.stringify(_buildNetIssues({}, [], [], null, null, null, "
                             + json.dumps({"results": [row]}) + ", null, " + json.dumps(findings) + "))); ")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["code"], "tls-filtered")
        self.assertIn("no TLS reply arrived", issues[0]["evidence"])

    def test_unknown_status_stays_neutral(self):
        result = self.run_js("\nconsole.log(JSON.stringify(_tlsBadge('future-status')));")
        self.assertEqual(result["type"], "muted")


class TestTlsTelemetryAndDemo(unittest.TestCase):
    def test_both_demo_failures_reach_existing_telemetry_blockers(self):
        import demo_data
        tls = demo_data.DEMO["Test-TlsInspection.ps1"]()
        self.assertTrue(any(r["status"] == "truncated" for r in tls["results"]))
        self.assertTrue(any(r["failureKind"] == "dropped" for r in tls["results"]))
        findings = main._tls_findings(tls)
        dashboard = {"readiness": main._compute_readiness(findings)}
        t = telemetry._build_telemetry(dashboard, {}, status="FAIL", open_codes=["tls-filtered"])
        self.assertEqual(t["status"], "FAIL")
        self.assertEqual(t["blockers"], [findings[0]["title"]])
        self.assertEqual(t["headline"], findings[0]["title"])
        # No collector metadata is added to the v1 telemetry contract.
        self.assertNotIn("rawBytes", json.dumps(t))
        self.assertNotIn("serverMessages", json.dumps(t))
