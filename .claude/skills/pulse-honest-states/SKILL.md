---
name: pulse-honest-states
description: The four-state contract for any Pulse panel fed by a collector - loading, genuinely empty, collector-failed and stale must each look different, and no verdict may count a check that never ran as a pass. Includes a fault-injection harness that kills a collector and checks the page admits it. Use when writing or editing a render function in Pulse.Web/app/static/app.js, adding a verdict, summary or rollup card, adding a collector to main.py, or when asked what a tab looks like if a collector times out or why something shows green.
---

# Pulse honest states

A collector can die on a real VPU: a script times out, WMI hangs, a device
disappears. Pulse's job in that moment is to say so. In most lanes it does
the opposite.

Two measurements, at different resolutions -- keep them apart:

- A **source-level map of 42 sub-panels** rated 28 dishonest, 13 ambiguous,
  1 honest. Adversarial review of the suspect ratings: 23 checked, 0 refuted.
- The **harness below tests 10 whole tabs** by actually killing collectors.
  It finds **4 dishonest** (Network, Cameras, ports, Hardware) plus one
  global defect.

The numbers differ because they measure different things: a tab can carry a
dishonest sub-panel and still admit the failure somewhere else on the page.
Trust the harness for "is this tab honest", the map for "which panel".

With `Get-NetworkConfig.ps1` faulted the page reads "Ready - Checked 13 of 13
systems", "All checks complete" and the word "Pass" nineteen times, with no
occurrence of "error", "unable", "could not" or "timed out" anywhere on it.

The worst one is worth its own sentence. With the camera collectors faulted,
Camera Connectivity renders **"No NIC ports detected" plus four fabricated
`Port N - Not detected` rows** - pixel-identical to a genuinely absent
GIE74P PoE card, which is the signature that sends a unit to RMA. A timed-out
script and a missing GIE74P card look the same on screen.

## Run the harness

```bash
node tools/ui-sweep/states.mjs                          # all scenarios
node tools/ui-sweep/states.mjs --scenario cameras --verbose
node tools/ui-sweep/states.mjs --list
```

It starts one server per scenario (on its own port) with the relevant
collectors faulted, renders the affected tab, and compares the visible text
against the **same tab rendered healthy**. The faulted render must say
something the healthy one does not.

That differential matters: several tabs contain "error" or "failed" in
ordinary body copy, so merely finding an admission word proves nothing. The
first version of this check did exactly that and passed lanes that say
nothing at all.

`BASELINE` holds the four lanes already known to be dishonest, so the guard
is green today and fails on a **new** one. Delete a line when you fix it; it
reports baselined scenarios that start passing.

`local-network` is a **positive control** -- the one lane that handles this
correctly, deliberately not baselined. If it ever fails, the harness is
broken, not the lane. A suite that can only say "dishonest" measures
nothing.

Drive faults by hand while working on a lane:

```bash
python3 tools/ui-sweep/serve_demo.py --port 8799 --fault cameras &
open http://127.0.0.1:8799/#cameras

python3 tools/ui-sweep/serve_demo.py --list-collectors   # every name --fault takes
python3 tools/ui-sweep/serve_demo.py --fault all         # everything dies
python3 tools/ui-sweep/serve_demo.py --empty diskhealth  # succeeds, returns nothing
python3 tools/ui-sweep/serve_demo.py --slow networkports # times out
```

`--fault` makes a collector return the same `{"error": True, "message": ...}`
shape `run_ps` produces when a script dies on a VPU. Nothing in `Pulse.Web`
changes.

## The contract

Answer all four for every panel you write. They are four different screens,
not one.

| State | Must look like |
|---|---|
| **loading** | a skeleton or spinner - never zeros, never an empty list |
| **empty** | "none found", stated as a *result* the check produced |
| **failed** | "could not check X", naming what failed, ideally with a retry |
| **stale** | the data, plus when it was last good |

Three rules that follow from it:

1. **An empty array is not a healthy result.** `X.length === 0` must never be
   a verdict input. Distinguish "the collector returned zero rows" from "the
   collector did not answer".
2. **A verdict counts what ran, not what complained.** `main.py:2675` is
   `"FAIL" if blockers else "WARN" if risks else "PASS"` - absence of issues,
   with no term for coverage. A verdict computed over checks that never ran
   is not a verdict.
3. **Never fabricate rows to fill a shape.** `Math.max(4, ports.length)`
   (app.js:1535, :4531, :4560) invents four blank port rows when the
   collector errored. That is not a placeholder, it is a diagnosis.

## Copy this one

`Network Test - Local Network Health` is the only panel of 42 that gets it
right: on a collector error it prints red text reading
`Local network test failed: <the collector's own message>` (app.js:4127). It
says what failed, in the panel that owned the check, using the message the
collector produced. Copy that shape.

Six whole tabs also pass the harness today -- Disks, Service Status,
ScoreConnect, Audio, Power Events and the Dashboard admit a dead collector
somewhere on the page. Read one of those before writing a new lane.

The two other patterns worth reusing are the Disks SMART guard and the
Cameras stale badge (`markStale`), which is the only stale marker in the app.

## Backend rules

- **Never destroy an error flag.** `_build_network` (main.py:3347) sets
  `net = {}` when the config collector errored, directly below a comment
  promising the frontend will surface it. The frontend then cannot tell
  "errored" from "no adapters". Pass the error through.
- **Every `and not X.get("error")` guard needs a paired else** that emits an
  "unable to check" entry. There are 35 such guards.
- **`_sources` (main.py:3318) must list every collector you gather.** It
  names 8; many more are fetched, so a failure in the rest cannot reach the
  "some checks couldn't complete" notice.
- **A new collector must be added to `demo_data.py`** or every lane that uses
  it is permanently untestable in demo mode.

## Why this was invisible

`grep -c '"error": True' Pulse.Web/app/demo_data.py` returns **0**. Demo mode
could not produce a single degraded state, so every failure branch in the UI
shipped without anyone seeing it once. That is the root cause, and the reason the harness exists rather than a checklist alone.

## If you add a check to this harness

The harness has had **nine** bugs found in it during development, every one
of which made it report green while measuring nothing. That is the hazard of
test tooling: a broken check looks exactly like a passing one. The ones worth
knowing about, because they are easy to reintroduce:

- **A renderer crash is not an admission.** `renderPage` (app.js:207) catches
  a throw and writes "Render Error" plus the stack into `#page`, which sits
  inside `#content` -- so the words "cannot" and "error" land in the scored
  text. A crashing tab scored "admits the failure" and recommended deleting a
  baseline entry. The harness now treats a Render Error box, or any console
  error during the render, as a harness failure.
- **Every did-not-run path must be `broken`, never `ok: false`.** Two early
  returns lacked the flag, so a scenario whose server never started was filed
  under BASELINE and the run exited 0. `runScenario` now has exactly one
  non-throwing exit -- the one carrying a real measurement.
- **Prove the fault reached the render you are scoring**, in two tiers. The
  injected message is distinctive, so finding it is proof. But Pulse
  *destroys* error payloads server-side (`net = {}` at main.py:3347,
  performance at main.py:3336), so requiring the message to survive to the
  API false-fails the two worst lanes. Absent the message, the server's own
  marker must record a non-empty resolved fault set -- and the erasure is
  itself the defect.
- **One port per scenario, and verify server identity.** A server that has
  not finished dying still answers, so the next scenario silently measured
  the previous one's fault set. `serve_demo.py` writes
  `/tmp/pulse-serve-<port>.json` naming its port, pid and resolved faults.
- **An empty healthy baseline makes the differential trivially passable** --
  every word counts as gained. It is now rejected.

Then prove your check fires: break the thing it checks, run it, confirm it
reports, restore. A check that has never failed has not been tested.

## What it cannot tell you

Whether the *content* of an error message is useful, whether a real VPU fails
the same way demo mode simulates, or anything about partial failure inside a
collector that still returns 200. It answers one question well: when a check
does not run, does the screen say so.
