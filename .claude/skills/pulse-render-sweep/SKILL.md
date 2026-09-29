---
name: pulse-render-sweep
description: Render every Pulse tab headlessly at remote-desktop widths in both themes and check it - JS errors, dead inline handlers, horizontal scroll, content overflowing its card, text clipped with no title. Use before committing or merging any change under Pulse.Web/app/static, when adding or renaming a tab, after changing a grid, table, media query or breakpoint, and when asked to check the layout, test at RDP widths, verify the UI without a VPU, or confirm a page still renders.
---

# Pulse render sweep

`pulse-ui-contract` reads the source. This opens the page. They catch
different things: a class that does not exist is static, a handler a tech can
click that throws is not.

Pulse is used over LogMeIn far more often than at the box, so the widths that
matter are **1366** (the VPU console) and **1100 / 900** (realistic remote
windows), in **both themes**.

## Run it

Two processes. The server must be up first.

```bash
python3 tools/ui-sweep/serve_demo.py --port 8797 &
node tools/ui-sweep/sweep.mjs --port 8797
```

Narrow it while iterating:

```bash
node tools/ui-sweep/sweep.mjs --port 8797 --tab network --widths 900 --themes light --verbose
```

Stop the server when done: `pkill -f serve_demo.py`

Flags: `--tab <id>`, `--widths 1366,1100,900`, `--themes light,dark`,
`--height 900`, `--verbose`, `--cdp-port 9223`, `--port <server port>`.

## What it checks

**Blocking** (exit 1) - deterministic, cannot flake:

| Check | Catches |
|---|---|
| `console` | any `console.error` or uncaught exception during startup or a tab's render |
| `dead-handlers` | an inline `onclick=`/`onchange=` calling an identifier that is not a global - a renamed or deleted handler, silent until a tech clicks it |
| `page-scroll` | the window scrolls sideways at that width |

**Advisory** (reported, never fails) - real, but font rendering differs
between a CI runner and a VPU, and one pixel must not block a merge:

| Check | Catches |
|---|---|
| `card-overflow` | an element whose right edge escapes its `.card` |
| `hidden-truncation` | a leaf clipped by ellipsis with no `title=` and no scrollable ancestor - unreadable *and* uncopyable on a remote desktop |

Current advisory state on `dev`: ~15 issues, mostly `.data-table` escaping its
card below 1366 (no scroll wrapper) and `.log-detail` clipping without a
`title`.

## Determinism matters here

`demo_data.py` randomises the venue at import, and the names in the pool
differ by 15 characters - enough to change what overflows. `serve_demo.py`
seeds `random` and pins the **longest** name, so a layout result is
reproducible and reflects the worst case the fleet can produce.

It changes nothing in `Pulse.Web`: `demo_data` reads `_VENUE` inside its
functions, so reassigning the module global after import is enough.

```bash
python3 tools/ui-sweep/serve_demo.py --venue PXLS2-29115   # a specific unit
python3 tools/ui-sweep/serve_demo.py --venue random        # back to normal
python3 tools/ui-sweep/serve_demo.py --seed 7              # different dice
```

## Mechanics that are easy to get wrong

- **A static edit needs a server restart, not a reload.** `main.py`
  cache-busts `?v=` at serve time from the version plus boot timestamp.
- **Wait on `#splash.splash-hidden`**, not a fixed sleep. The splash gates
  the app and its checklist length varies with how fast the collectors
  answer.
- **Theme is `localStorage["pulse-theme"]`**, read by a pre-paint hook in
  `index.html`. Set it, then reload - setting it after load does nothing.
  Light is the default for anyone with no saved preference, so check it
  first. The sweep does all of this already.
- **Re-rendering the tab that is already showing is a no-op.** Setting
  `location.hash` to the current tab does not re-run its render function.
  The sweep hops through another tab first; hand-written checks usually
  forget this and silently measure nothing.
- **Startup errors belong to no tab.** The landing page renders before any
  navigation, so its console output has to be captured separately or a
  render error on the default tab is invisible.

## Extending it

The in-page checks are self-contained expression strings near the top of
`sweep.mjs` (`PAGE_SCROLL`, `DEAD_HANDLERS`, `HIDDEN_TRUNCATION`,
`CARD_OVERFLOW`). Add one, then put it in `BLOCKING` or `ADVISORY`.

**Put it in `BLOCKING` only if it cannot flake across machines.** Anything
that depends on measured text width is advisory: the runner's font stack is
not the fleet's.

**Then prove it fires.** Break the thing it checks, run the sweep, confirm it
reports, restore. Two of the checks here passed their first review and were
still broken - the console check was draining its own evidence, and it could
not see the default tab at all. A check that has never failed has not been
tested.

## What this cannot tell you

Whether a collector failure renders as a green PASS (demo mode has no error
states), whether the page is keyboard-operable, or whether the copy is right.
It renders the happy path at several sizes and asserts the page is not
broken.
