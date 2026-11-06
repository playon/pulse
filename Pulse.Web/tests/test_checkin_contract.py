"""PV-42: validate the real builders and shared examples with JSON Schema.

Install tests/requirements.txt as well as app/requirements.txt. The validator
is test-only; it is deliberately not part of the deployed app or agent.
"""
import asyncio
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Pulse.Web/app"))
import main  # noqa: E402 -- binds the shared engine used by the real builders
from pulse_agent import checkin, telemetry  # noqa: E402

CONTRACT = ROOT / "tools/checkin-worker/contract"
SCHEMA = json.loads((CONTRACT / "pulse.telemetry.v1.schema.json").read_text())
GOLDEN = json.loads((CONTRACT / "golden-checkins.json").read_text())


def validator(definition):
    return Draft202012Validator({"$schema": SCHEMA["$schema"], "$defs": SCHEMA["$defs"],
                                "$ref": f"#/$defs/{definition}"})


class TestCheckinContract(unittest.TestCase):
    def test_schema_and_golden_examples(self):
        Draft202012Validator.check_schema(SCHEMA)
        for example in GOLDEN["examples"]:
            with self.subTest(example=example["name"]):
                entry = example["checkin"]
                if example["expected"]["ingest"] == "invalid":
                    self.assertFalse(validator("checkin").is_valid(entry))
                    self.assertFalse(Draft202012Validator(SCHEMA).is_valid(entry))
                    continue
                validator("producedCheckin").validate(entry)
                Draft202012Validator(SCHEMA).validate(entry)
                validator("request").validate({"checkins": [entry]})
                if "telemetry" in entry:
                    Draft202012Validator(SCHEMA).validate(entry["telemetry"])
                    self.assertLessEqual(len(json.dumps(entry["telemetry"]).encode()), 16 * 1024)

    def test_real_builders_keep_the_contract_field_names(self):
        identity = {"computerSystem": {"model": "FAKE Test Workstation"},
                    "pixellot": {"venueId": "FAKE-VENUE-BUILDER", "vpuName": "FAKE VPU builder"},
                    "operatingSystem": {"buildNumber": "17763"}}
        raw = {"identity": identity, "expectations": {"systemType": "S2", "expectedMainCameras": 2}}
        for status in ("PASS", "WARN", "FAIL"):
            dash = {"identity": {**identity["pixellot"], "pixellotVersion": "0.0.0-test"},
                    "readiness": {"status": status, "policyVersion": "1", "timestamp": GOLDEN["receivedAt"],
                                  "blockers": [], "risks": []}}
            document = telemetry._build_telemetry(dash, raw, GOLDEN["receivedAt"])
            with self.subTest(status=status):
                validator("producedTelemetry").validate(document)
                self.assertLessEqual(telemetry._telemetry_bytes(document), 15 * 1024)
                # Unknown collector values are valid nulls, never fake healthy readings.
                self.assertIsNone(document["network"]["internetReachable"])
                self.assertIsNone(document["cameras"]["detected"])
            async def run_ps(name, **kwargs):
                return identity if name == "Get-SystemIdentity.ps1" else {"ubr": 9999}
            with patch.object(main, "run_ps", side_effect=run_ps), \
                    patch.object(checkin, "_AGENT_VERSION", "0.0.0"), \
                    patch.object(checkin, "_AGENT_UPDATE_PATH", ""):
                for reason in ("startup", "periodic", "state-change"):
                    entry = asyncio.run(checkin._build_checkin_entry(
                        dash, reason=reason,
                        telemetry=None if reason == "startup" else document,
                        delta={"status": status, "prevStatus": "PASS", "opened": [], "resolved": []},
                        monitor={"pass": "full", "seconds": 1, "psRuns": 1, "eventLive": False}))
                    with self.subTest(status=status, reason=reason):
                        validator("producedCheckin").validate(entry)
                validator("producedCheckin").validate(asyncio.run(
                    checkin._build_checkin_entry(dash, heartbeat=True)))
                validator("producedCheckin").validate(asyncio.run(
                    checkin._build_checkin_entry(paused=True)))

    def test_additive_v1_fields_and_minimal_older_documents(self):
        validator("telemetry").validate({"schema": "pulse.telemetry/v1"})
        validator("checkin").validate({"checkinId": "old-build-0001", "unknownEnvelopeField": True})
        entry = copy.deepcopy(GOLDEN["examples"][2]["checkin"])
        entry["telemetry"]["futureField"] = {"anything": [1, True, None]}
        entry["telemetry"]["network"]["futureField"] = True
        validator("producedCheckin").validate(entry)
        # A typo is not a compatible addition: current builders must retain the old name.
        entry["telemetry"]["network"]["streamingPathRenamed"] = entry["telemetry"]["network"].pop("streamingPath")
        self.assertFalse(validator("producedCheckin").is_valid(entry))

    def test_strict_wire_rules(self):
        entry = copy.deepcopy(GOLDEN["examples"][2]["checkin"])
        for path, value in ((["checkinId"], "short"),
                            (["telemetry", "schema"], "pulse.telemetry/v2"),
                            (["telemetry", "status"], "HEALTHY"),
                            (["telemetry", "cameras", "detected"], 65),
                            (["telemetry", "network", "internet", "mac"], "aa:bb:cc:dd:ee:ff"),
                            (["monitor", "cpuPercent"], 101)):
            bad = copy.deepcopy(entry)
            parent = bad
            for key in path[:-1]:
                parent = parent[key]
            parent[path[-1]] = value
            with self.subTest(path=path):
                self.assertFalse(validator("checkin").is_valid(bad))


if __name__ == "__main__":
    unittest.main()
