#!/usr/bin/env python3
"""Run Pulse in demo mode, deterministically, with optional collector faults.

Two jobs, both about making demo mode predictable enough to assert against.

1. DETERMINISM (for the render sweep). demo_data.py is deliberately random --
   `_VENUE = random.choice(...)` at import, randomised uptime, scores, bot
   ids. Right for a demo, wrong for a layout check: a sweep that measures
   text overflow has to see the same strings every run, or a passing build
   and a failing build differ only by which venue name the dice picked. This
   seeds `random` before demo_data is imported and pins the venue to the
   LONGEST name in the pool -- the worst case the fleet can actually produce.

2. FAULT INJECTION (for the honest-states check). demo_data.py contains zero
   '"error": True', so no degraded path is reachable in demo mode and every
   failure branch in the UI ships unseen. `--fault` makes a named collector
   return the same `{"error": True, "message": ...}` shape run_ps produces on
   a real VPU when a script dies; `--empty` makes it return nothing; `--slow`
   makes it time out. That is how you find out whether a failed check renders
   as a failure or as a green Pass.

Nothing in Pulse.Web changes. demo_data reads `_VENUE` inside its functions
and dispatches through the DEMO registry dict, so reassigning module globals
after import is enough.

Usage:
    python3 tools/ui-sweep/serve_demo.py --port 8797
    python3 tools/ui-sweep/serve_demo.py --fault Get-NetworkConfig.ps1
    python3 tools/ui-sweep/serve_demo.py --fault network --empty cameras
    python3 tools/ui-sweep/serve_demo.py --list-collectors
"""

import argparse
import atexit
import json
import os
import random
import sys


def _short(script_name):
    """Get-NetworkConfig.ps1 -> networkconfig, so --fault can take a friendly name."""
    base = script_name.rsplit(".", 1)[0]
    for prefix in ("Get-", "Test-", "Invoke-", "Restart-", "Set-", "Start-", "Search-", "Install-"):
        if base.startswith(prefix):
            base = base[len(prefix):]
            break
    return base.lower()


def _resolve(spec, registry):
    """Turn a --fault value into a concrete set of DEMO registry keys.

    Accepts exact script names, the short form (`networkconfig`), a substring
    (`network` matches every network collector), or `all`. Unmatched names are
    fatal: silently faulting nothing would make the harness green for the
    wrong reason.
    """
    spec = (spec or "").strip()
    if not spec:
        return set()
    if spec == "all":
        return set(registry)
    out = set()
    for raw in spec.split(","):
        want = raw.strip()
        if not want:
            continue
        hits = {k for k in registry
                if k == want or _short(k) == want.lower() or want.lower() in _short(k)}
        if not hits:
            raise SystemExit(
                "FAIL: --fault/--empty/--slow names no collector: %r\n"
                "      list them with --list-collectors" % want)
        out |= hits
    return out


def _inject(demo_data, faults, empties, slows):
    """Replace DEMO registry entries so named collectors fail, empty or hang.

    get_demo() looks the callable up in DEMO at call time, so swapping the
    values here is enough -- no change to Pulse.Web, and powershell.run_ps
    already turns a {"error": True, ...} payload into the same shape a dead
    script produces on a real VPU.
    """
    import time as _time

    def erroring(name):
        return lambda **kw: {"error": True,
                             "message": "Injected fault: %s did not complete" % name}

    def emptying(name):
        return lambda **kw: {}

    def slowing(name, original):
        def fn(**kw):
            # Block past any caller timeout, then ERROR -- do not fall through
            # to the healthy payload. Returning the real data after the delay
            # made --slow indistinguishable from a healthy (if late) collector,
            # which is the opposite of what it is for.
            _time.sleep(40)
            return {"error": True,
                    "message": "Injected fault: %s timed out" % name}
        return fn

    for name in sorted(faults):
        demo_data.DEMO[name] = erroring(name)
    for name in sorted(empties - faults):
        demo_data.DEMO[name] = emptying(name)
    for name in sorted(slows - faults - empties):
        demo_data.DEMO[name] = slowing(name, demo_data.DEMO[name])

    if faults:
        print("faulted:  %s" % ", ".join(sorted(faults)))
    if empties - faults:
        print("emptied:  %s" % ", ".join(sorted(empties - faults)))
    if slows - faults - empties:
        print("slowed:   %s" % ", ".join(sorted(slows - faults - empties)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8797)))
    ap.add_argument("--seed", type=int, default=int(os.environ.get("PULSE_DEMO_SEED", 1)))
    ap.add_argument("--venue", default=os.environ.get("PULSE_DEMO_VENUE", "longest"),
                    help='"longest" (default), "random", or a hostname like PXLS2-29115')
    ap.add_argument("--fault", default=os.environ.get("PULSE_FAULT", ""),
                    help="comma-separated collectors that should error, or 'all'")
    ap.add_argument("--empty", default=os.environ.get("PULSE_EMPTY", ""),
                    help="comma-separated collectors that should return nothing")
    ap.add_argument("--slow", default=os.environ.get("PULSE_SLOW", ""),
                    help="comma-separated collectors that should time out")
    ap.add_argument("--list-collectors", action="store_true",
                    help="print every name --fault accepts and exit")
    args = ap.parse_args()

    app_dir = os.path.join(os.getcwd(), "Pulse.Web", "app")
    if not os.path.isdir(app_dir):
        print("FAIL: run this from the repo root (no Pulse.Web/app here)")
        return 1
    sys.path.insert(0, app_dir)

    # Seed BEFORE demo_data is imported -- its module-level randomness runs
    # at import time and is otherwise unreachable.
    random.seed(args.seed)

    os.environ.setdefault("PULSE_NO_BROWSER", "1")
    os.environ["PORT"] = str(args.port)

    import demo_data

    if args.venue != "random":
        pool = demo_data._DEMO_VENUES
        if args.venue == "longest":
            pick = max(pool, key=lambda v: len(v["vpuName"]))
        else:
            matches = [v for v in pool if v["hostname"] == args.venue]
            if not matches:
                print("FAIL: no demo venue with hostname %s" % args.venue)
                print("      choices: %s" % ", ".join(v["hostname"] for v in pool))
                return 1
            pick = matches[0]
        demo_data._VENUE = pick
        print("demo venue pinned: %s (%d chars)" % (pick["vpuName"], len(pick["vpuName"])))

    if args.list_collectors:
        for name in sorted(demo_data.DEMO):
            print("  %-34s %s" % (name, _short(name)))
        return 0

    faults = _resolve(args.fault, demo_data.DEMO)
    empties = _resolve(args.empty, demo_data.DEMO)
    slows = _resolve(args.slow, demo_data.DEMO)
    if faults or empties or slows:
        _inject(demo_data, faults, empties, slows)

    # Identify ourselves on disk so a harness can prove the server answering
    # on this port is the one it just started, with the fault set it asked
    # for. Inferring that from an API response is guesswork: a server from a
    # previous scenario that has not finished dying still returns 200.
    # Explicitly /tmp, not tempfile.gettempdir(): on macOS that returns a
    # per-user $TMPDIR under /var/folders, so the harness looked for the
    # marker somewhere this process never wrote it.
    marker = "/tmp/pulse-serve-%d.json" % args.port
    try:
        with open(marker, "w") as fh:
            json.dump({"port": args.port, "pid": os.getpid(),
                       "fault": args.fault, "empty": args.empty, "slow": args.slow,
                       "seed": args.seed,
                       # The RESOLVED sets, not just the spec: _resolve does
                       # unanchored substring matching, so "network" quietly
                       # matches five collectors. Recording what was actually
                       # faulted makes over-matching visible to a reader and
                       # to the harness.
                       "resolvedFault": sorted(faults),
                       "resolvedEmpty": sorted(empties - faults),
                       "resolvedSlow": sorted(slows - faults - empties)}, fh)
        atexit.register(lambda: os.path.exists(marker) and os.remove(marker))
    except OSError:
        pass

    import main
    import uvicorn

    print("seed=%d  port=%d" % (args.seed, args.port))
    uvicorn.run(main.app, host="127.0.0.1", port=args.port, reload=False,
                log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
