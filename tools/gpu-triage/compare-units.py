#!/usr/bin/env python3
"""Compare gpu-triage JSON summaries from several units.

Eight failing GPUs in two weeks is either eight dead cards or one shared
cause. This prints the per-unit verdicts side by side and then looks for
fields that are IDENTICAL across every failing unit - a shared driver
version, OS build, or BIOS is the signature of a software regression, not
of a coincidental cluster of hardware failures.

Usage:
    python3 compare-units.py gpu-triage-*.json
"""
import json
import sys
from collections import Counter

# Fields worth correlating; a value shared by every failing unit is a lead.
CORRELATE = [
    "platform", "model", "os", "buildLab", "distro", "kernel",
    "bios", "gpuName", "pciId", "driverVersion",
]


def main(paths):
    units = []
    for p in paths:
        try:
            with open(p) as fh:
                d = json.load(fh)
            d["_file"] = p
            units.append(d)
        except Exception as exc:  # a malformed file should not kill the run
            print("skip %s: %s" % (p, exc), file=sys.stderr)

    if not units:
        print("no readable triage files", file=sys.stderr)
        return 1

    print("=== PER-UNIT VERDICTS ===")
    row = "%-18s %-18s %-10s %-8s %-8s %s"
    print(row % ("HOST", "VERDICT", "DRIVER", "NVENC", "NVDEC", "GPU"))
    for u in units:
        print(row % (
            (u.get("host") or "?")[:18],
            u.get("verdict") or "?",
            (u.get("driverVersion") or "-")[:10],
            u.get("nvencTest") or "-",
            u.get("nvdecTest") or "-",
            (u.get("gpuName") or "-")[:30],
        ))

    print()
    print("=== VERDICT TALLY ===")
    for verdict, n in Counter(u.get("verdict") for u in units).most_common():
        print("  %-18s %d" % (verdict, n))

    print()
    print("=== SHARED FACTORS ACROSS ALL UNITS ===")
    print("(a field identical on every unit is a candidate common cause)")
    found_shared = False
    for field in CORRELATE:
        values = set()
        reported = 0
        for u in units:
            v = u.get(field)
            if v not in (None, ""):
                values.add(str(v))
                reported += 1
        if not values:
            continue
        if len(values) == 1 and reported == len(units) and len(units) > 1:
            # Every unit reported this field and every value matched.
            found_shared = True
            print("  SHARED  %-14s = %s" % (field, sorted(values)[0]))
        elif len(values) == 1:
            # Only some units reported it - a real lead, but not proof, so it
            # must never be printed as if all units agreed.
            print("  partial %-14s = %s  (reported by %d of %d units only)"
                  % (field, sorted(values)[0], reported, len(units)))
        else:
            print("  varies  %-14s : %s" % (field, ", ".join(sorted(values))[:90]))
    if not found_shared:
        print("  (no field is identical across every unit)")

    print()
    print("=== EVIDENCE FREQUENCY ===")
    hw = Counter()
    sw = Counter()
    for u in units:
        for e in u.get("hardwareEvidence") or []:
            hw[e] += 1
        for e in u.get("softwareEvidence") or []:
            sw[e] += 1
    print("-- hardware evidence --")
    for e, n in hw.most_common():
        print("  %2d/%d  %s" % (n, len(units), e))
    if not hw:
        print("  (none on any unit)")
    print("-- software/config evidence --")
    for e, n in sw.most_common():
        print("  %2d/%d  %s" % (n, len(units), e))
    if not sw:
        print("  (none on any unit)")

    print()
    hw_units = [u for u in units if u.get("verdict") == "HARDWARE_SUSPECT"]
    not_hw = [u for u in units if u.get("verdict") in ("NOT_HARDWARE", "SOFTWARE_FAULT")]
    print("=== READING ===")
    print("  %d of %d units show hardware evidence." % (len(hw_units), len(units)))
    print("  %d of %d units are software/config or pass the functional test." % (len(not_hw), len(units)))
    if not_hw and len(not_hw) >= len(hw_units):
        print("  Most of these units should NOT have been RMA'd on the evidence collected.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))
