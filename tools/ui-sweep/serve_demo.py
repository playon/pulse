#!/usr/bin/env python3
"""Run Pulse in demo mode, deterministically, for the render sweep.

demo_data.py is deliberately random -- `_VENUE = random.choice(...)` at
import, randomised uptime, scores, bot ids. That is right for a demo and
wrong for a layout check: a sweep that measures text overflow has to see the
same strings every run, or a passing build and a failing build differ only by
which venue name the dice picked.

This wrapper seeds `random` before demo_data is imported, then pins the venue
to the LONGEST name in the pool. Longest is the point: venue names are the
string most likely to overflow a header or a table cell, so the sweep should
measure the worst case the fleet can actually produce, not an average one.

Nothing in Pulse.Web changes -- demo_data reads `_VENUE` inside its functions,
so reassigning the module global after import is enough.

Usage:
    python3 tools/ui-sweep/serve_demo.py [--port 8797] [--seed 1]
"""

import argparse
import os
import random
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8797)))
    ap.add_argument("--seed", type=int, default=int(os.environ.get("PULSE_DEMO_SEED", 1)))
    ap.add_argument("--venue", default=os.environ.get("PULSE_DEMO_VENUE", "longest"),
                    help='"longest" (default), "random", or a hostname like PXLS2-29115')
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

    import main
    import uvicorn

    print("seed=%d  port=%d" % (args.seed, args.port))
    uvicorn.run(main.app, host="127.0.0.1", port=args.port, reload=False,
                log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
