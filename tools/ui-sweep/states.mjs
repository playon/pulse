// Kill a collector, load the page, and check Pulse admits it.
//
// A PowerShell collector on a real VPU can die: a script times out, WMI
// hangs, a device disappears. Pulse's job in that moment is to say so. What
// it does instead, in most lanes, is render the failure as a healthy result.
//
// Demonstrated, not inferred. With Get-NetworkConfig.ps1 faulted the page
// reads "Ready - Checked 13 of 13 systems", "All checks complete", and the
// word "Pass" nineteen times, with no occurrence of "error", "unable",
// "could not" or "timed out" anywhere on it. With the three camera
// collectors faulted, Camera Connectivity renders "No NIC ports detected"
// and four fabricated "Port N - Not detected" rows -- pixel-identical to a
// genuinely absent GIE74P PoE card, which is the signature that sends a unit
// to RMA.
//
// The cause is structural:
//   - demo_data.py has zero '"error": True', so no degraded path was
//     reachable before this harness and every failure branch shipped unseen
//   - main.py has 35 `and not X.get("error")` guards, many with no paired else
//   - _build_network (main.py:3347) sets `net = {}` on a collector error,
//     destroying the flag server-side, right below a comment promising the
//     frontend will surface it
//   - the readiness verdict (main.py:2675) is
//     `"FAIL" if blockers else "WARN" if risks else "PASS"` -- derived from
//     the ABSENCE of issues, with no term for how many checks actually ran
//
// One server per scenario: powershell.py keeps a short-TTL result cache, so
// switching faults at runtime would be masked by it.
//
// Usage (from the repo root):
//   node tools/ui-sweep/states.mjs
//   node tools/ui-sweep/states.mjs --scenario cameras --verbose
//   node tools/ui-sweep/states.mjs --list

import { spawn } from "node:child_process";
import { readFileSync, rmSync } from "node:fs";
import { launch, openPulse, pageText, gotoTab, sleep } from "./cdp.mjs";

const argv = process.argv.slice(2);
const arg = (n, d) => { const i = argv.indexOf("--" + n); return i === -1 ? d : argv[i + 1]; };
const flag = (n) => argv.includes("--" + n);

const PORT = Number(arg("port", 8799));
const ONLY = arg("scenario", null);
const VERBOSE = flag("verbose");

// Words that mean "this check did not run". A lane that faults a collector
// and shows none of these is telling the tech nothing went wrong.
const ADMISSION = [
  "could not", "couldn't", "cannot", "can't", "unable", "failed", "failure",
  "error", "timed out", "timeout", "unavailable", "not available",
  "no data", "not checked", "didn't run", "did not run", "did not complete",
  "check failed",
];

// Claims of health. One of these while a collector is dead is the defect --
// worse than a blank panel, because a tech acts on it.
const HEALTH_CLAIM = [
  "all checks complete", "no issues found", "everything looks", "game-ready",
];

const SCENARIOS = [
  { key: "network", fault: "networkconfig", tab: "network",
    why: "the adapter/IP collector dies; _build_network turns the error into config:{}" },
  { key: "cameras", fault: "nicadapters,s1cameras,poepower", tab: "cameras",
    why: "all three camera collectors die; Math.max(4, ports.length) invents 4 rows",
    forbid: ["Not detected"] },
  { key: "ports", fault: "networkports", tab: "network",
    why: "the port sweep dies; the header verdict must not read Pass" },
  { key: "hardware", fault: "hardware", tab: "hardware",
    why: "Get-Hardware dies; renderHardware only shows errorBox when BOTH sub-payloads fail" },
  { key: "disks", fault: "diskhealth", tab: "disk-health",
    why: "the SMART/disk collector dies" },
  { key: "services", fault: "services", tab: "services",
    why: "the service list dies; a stopped Pixellot agent and an unknown one must differ" },
  { key: "scoreconnect", fault: "scoreconnectlive,scoreconnectstatus,scorelinkstatus", tab: "scoreconnect",
    why: "the scoreboard feed dies; a dark scoreboard and an unchecked one must differ" },
  { key: "audio", fault: "audiodevices", tab: "audio",
    why: "the audio device collector dies" },
  { key: "reboots", fault: "reboothistory", tab: "reboots",
    why: "the reboot history collector dies" },
  { key: "dashboard", fault: "performance,services,nicadapters", tab: "dashboard",
    why: "three dashboard inputs die; the readiness verdict has no term for checks that did not run" },
  // POSITIVE CONTROL. Local Network Health is the one panel of 42 that gets
  // this right: it prints "Local network test failed: <collector message>".
  // It is deliberately NOT baselined -- if this scenario ever reports as
  // dishonest, the harness is broken, not the lane. A suite that can only
  // ever say "dishonest" is not measuring anything.
  { key: "local-network", fault: "localnetwork", tab: "network",
    why: "POSITIVE CONTROL: this lane handles a dead collector correctly and must keep passing" },
];

// Scenarios already known to render a dead collector as healthy, measured at
// dev@7bdb56c. The guard fails on anything NOT listed. Delete a line when the
// lane is fixed -- this reports baselined scenarios that start passing.
//
// This list is the point of the exercise: the first enumeration of where
// Pulse is silent about a check it never ran.
const BASELINE = {
  // Measured at dev@7bdb56c, not predicted. My hand-written guess said all
  // ten lanes were dishonest; running it said four. Six lanes -- disks,
  // services, scoreconnect, audio, reboots and the dashboard -- do admit a
  // dead collector, and would have been slandered by a baseline nobody ran.
  network: "no admission on the Network tab when the adapter/IP collector dies",
  cameras: "fabricates 4 'Port N - Not detected' rows; identical to an absent GIE74P",
  ports: "no admission when the port sweep dies",
  hardware: "a single sub-payload failure renders with no error",
};

// Every scenario gets its OWN port. Sharing one port meant a server that had
// not finished dying still answered waitUp(), so the next scenario silently
// measured the PREVIOUS scenario's fault set -- which is what made the
// positive control pass alone and fail in a full run.
function portFor(index) { return PORT + index; }

function startServer(fault, index) {
  try { rmSync(`/tmp/pulse-serve-${portFor(index)}.json`, { force: true }); } catch {}
  const proc = spawn("python3",
    ["tools/ui-sweep/serve_demo.py", "--port", String(portFor(index)), "--fault", fault],
    { stdio: "ignore" });
  return proc;
}

/** Prove the server answering this port is the one we just started.
 *
 * A server from the previous scenario that has not finished dying still
 * returns 200, so waitUp() alone is not evidence. serve_demo.py writes a
 * marker file naming its port, pid and fault set once it has bound; we read
 * that instead of inferring server identity from an API response. */
function assertServerIdentity(port, fault) {
  const marker = `/tmp/pulse-serve-${port}.json`;
  let info;
  try {
    info = JSON.parse(readFileSync(marker, "utf8"));
  } catch {
    throw new Error(`no marker at ${marker} -- the server on this port is not ours`);
  }
  if (String(info.fault || "") !== String(fault || "")) {
    throw new Error(
      `port ${port} is serving fault="${info.fault}" but we asked for "${fault}" `
      + "-- a previous server is still bound to it");
  }
  try {
    process.kill(info.pid, 0);
  } catch {
    throw new Error(`the server that wrote ${marker} (pid ${info.pid}) is gone`);
  }
}

/** Confirm the scenario's fault is actually live on the server being measured.
 *
 * Two tiers, because the strict version false-fails on the very defect under
 * test. The injected message ("Injected fault: <script> did not complete") is
 * distinctive, so finding it in a response is proof the fault is live. But
 * _build_network (main.py:3347) replaces an errored config with `net = {}`
 * and main.py:3336 does the same for performance -- Pulse DESTROYS the error
 * payload server-side. Requiring the message to survive to the API therefore
 * marks the two worst lanes "could not be checked".
 *
 * So: message found = confirmed live. Message absent but the server's own
 * marker records a non-empty resolved fault set = confirmed configured, and
 * the erasure is itself the bug. Neither = the fault never applied, which is
 * a real harness failure. */
async function assertFaultLanded(base, sc, port) {
  const endpoints = ["/api/" + sc.tab, "/api/network", "/api/cameras",
                     "/api/system", "/api/dashboard"];
  for (const ep of endpoints) {
    try {
      const r = await fetch(base + ep, { signal: AbortSignal.timeout(30000) });
      if (!r.ok) continue;
      if ((await r.text()).includes("Injected fault:")) return "live";
    } catch { /* try the next one */ }
  }
  let info;
  try {
    info = JSON.parse(readFileSync(`/tmp/pulse-serve-${port}.json`, "utf8"));
  } catch {
    throw new Error(`--fault ${sc.fault} could not be confirmed: no marker for port ${port}`);
  }
  if ((info.resolvedFault || []).length) return "erased";
  throw new Error(
    `--fault ${sc.fault} resolved to no collectors -- the fault never applied`);
}

async function waitUp(base, timeoutMs = 45000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const r = await fetch(base + "/", { signal: AbortSignal.timeout(2000) });
      if (r.ok) return true;
    } catch { /* not up yet */ }
    await sleep(500);
  }
  return false;
}

/** Capture the healthy text of every tab we will fault, in ONE session.
 *
 * The baselines do not depend on the scenario, so starting a server per
 * healthy render wasted eight boots. One server, one browser, walk the tabs.
 *
 * It runs on its own port: the faulted server holds PORT for the duration of
 * a scenario, and a second server started there silently fails to bind while
 * waitUp() happily succeeds against the FAULTED one -- which made the
 * "healthy" baseline identical to the faulted render, the differential always
 * report "no change", and the positive control fail. */
async function captureHealthy(tabsWanted) {
  const port = PORT + 100;
  const base = `http://127.0.0.1:${port}`;
  try { rmSync(`/tmp/pulse-serve-${port}.json`, { force: true }); } catch {}
  const server = spawn("python3",
    ["tools/ui-sweep/serve_demo.py", "--port", String(port)], { stdio: "ignore" });
  let browser = null;
  const out = new Map();
  try {
    if (!await waitUp(base)) throw new Error("healthy baseline server did not start");
    assertServerIdentity(PORT + 100, "");
    browser = await launch({ profile: "/tmp/pulse-states-healthy", cdpPort: 9299 });
    const { cdp } = browser;
    if (!await openPulse(cdp, base)) throw new Error("splash never cleared (healthy)");
    const tabs = await cdp.eval(`NAV_SECTIONS.flatMap(s => s.pages.map(p => p.id))`);
    for (const t of tabsWanted) {
      await gotoTab(cdp, t, tabs);
      out.set(t, await pageText(cdp));
    }
    return out;
  } finally {
    if (browser) browser.close();
    server.kill();
    await sleep(600);
  }
}

let healthyCache = new Map();

async function runScenario(sc, index) {
  const base = `http://127.0.0.1:${portFor(index)}`;
  const server = startServer(sc.fault, index);
  let browser = null;
  try {
    // Throw, never return: runScenario must have exactly ONE non-throwing
    // exit, the one that carries a real measurement. Two early returns here
    // previously lacked broken:true, so a scenario that never ran was filed
    // under BASELINE and the run exited 0.
    if (!await waitUp(base)) throw new Error(`server did not start with --fault ${sc.fault}`);
    assertServerIdentity(portFor(index), sc.fault);

    // A fresh CDP port and profile per scenario. Reusing one port let a
    // slow-exiting Chrome from the previous scenario still hold it, so
    // launch() attached to a browser that was on its way out and every
    // Runtime.evaluate timed out.
    browser = await launch({
      profile: `/tmp/pulse-states-profile-${index}`,
      cdpPort: 9300 + index,
    });
    const { cdp } = browser;
    if (!await openPulse(cdp, base)) throw new Error("splash never cleared");

    const tabs = await cdp.eval(`NAV_SECTIONS.flatMap(s => s.pages.map(p => p.id))`);
    // Prove the injected fault actually reached the server backing THIS
    // render. Without it, a scenario whose fault silently did nothing scores
    // the healthy page and reports the lane as honest.
    const faultState = await assertFaultLanded(base, sc, portFor(index));
    cdp.drainConsole();
    await gotoTab(cdp, sc.tab, tabs);
    const { panel, page } = await pageText(cdp);
    const lowPanel = panel.toLowerCase(), lowPage = page.toLowerCase();

    // Differential, not keyword bingo. Several tabs contain the words
    // "error" or "failed" in ordinary body copy, so merely FINDING an
    // admission word proves nothing. Compare against the same tab rendered
    // healthy: the faulted render must say something the healthy one did
    // not.
    const healthy = healthyCache.get(sc.tab);
    if (!healthy) throw new Error(`no healthy baseline captured for tab ${sc.tab}`);
    // An empty baseline makes the differential trivially passable: every word
    // in the faulted render counts as "gained".
    if (!healthy.panel || healthy.panel.length < 200) {
      throw new Error(`healthy baseline for ${sc.tab} is empty or truncated `
        + `(${(healthy.panel || "").length} chars) -- nothing to diff against`);
    }

    // A renderer CRASH is not an admission. app.js renderPage() catches a
    // throw and writes "Render Error" + the stack into #page, which lives
    // inside #content -- so the words "cannot"/"error" land in the scored
    // text and the lane reads as honest. A mutation test confirmed a crashing
    // tab scored "admits the failure" and reported a baselined lane as fixed.
    if (panel.includes("Render Error")) {
      throw new Error(`${sc.tab} threw during render (the page shows "Render Error") `
        + "-- that is a crash, not an admission");
    }
    const consoleErrs = cdp.drainConsole();
    if (consoleErrs.length) {
      throw new Error(`${sc.tab} logged an error while rendering: ${consoleErrs[0]}`);
    }
    const lowHealthy = healthy.panel.toLowerCase();
    const gained = ADMISSION.filter((w) => lowPanel.includes(w) && !lowHealthy.includes(w));

    const reasons = [];
    if (!gained.length) {
      reasons.push(`the ${sc.tab} tab says nothing it does not also say when healthy`);
    }
    // The splash checklist claim is GLOBAL -- it fires on every tab whatever
    // died, so folding it into each lane's verdict swamped them all and made
    // even the one honest lane report as dishonest. Collect it separately and
    // report it once.
    const globalClaims = HEALTH_CLAIM.filter((c) => lowPage.includes(c));
    for (const bad of sc.forbid || []) {
      if (lowPanel.includes(bad.toLowerCase())) reasons.push(`fabricated content present: "${bad}"`);
    }
    if (VERBOSE) {
      console.log("      fault   : " + faultState
        + (faultState === "erased"
            ? " (Pulse discarded the error payload before the API -- that is the defect)"
            : ""));
      console.log("      healthy: " + healthy.panel.slice(0, 200));
      console.log("      faulted: " + panel.slice(0, 200));
      console.log("      gained admission words: " + (gained.join(", ") || "(none)"));
    }
    return { ok: reasons.length === 0, reasons, globalClaims };
  } catch (e) {
    // Distinct from a dishonest lane: this means the check did not run, so it
    // must never be absorbed by BASELINE. "We don't know" is not "known bad".
    return { ok: false, broken: true, reasons: ["harness error: " + e.message] };
  } finally {
    if (browser) browser.close();
    server.kill();
    await sleep(600);
  }
}

async function main() {
  if (flag("list")) {
    for (const s of SCENARIOS) {
      console.log(`  ${s.key.padEnd(13)} fault=${s.fault.padEnd(46)} tab=${s.tab.padEnd(12)}` +
        (BASELINE[s.key] ? " BASELINED" : ""));
    }
    return 0;
  }

  const todo = SCENARIOS.filter((s) => !ONLY || s.key === ONLY);
  if (ONLY && !todo.length) {
    console.error(`FAIL: no scenario "${ONLY}" (see --list)`);
    return 1;
  }

  console.log(`Pulse honest-states check -- ${todo.length} scenario(s)`);
  console.log("");
  const wantedTabs = [...new Set(todo.map((s) => s.tab))];
  console.log(`capturing healthy baselines for ${wantedTabs.length} tab(s)...`);
  try {
    healthyCache = await captureHealthy(wantedTabs);
  } catch (e) {
    console.log("FAIL: could not capture healthy baselines: " + e.message);
    return 1;
  }
  console.log("");

  const regressions = [], known = [], fixed = [], broken = [];
  const globalSeen = new Set();
  for (let i = 0; i < todo.length; i++) {
    const sc = todo[i];
    const { ok, reasons, broken: isBroken, globalClaims } = await runScenario(sc, i);
    for (const c of globalClaims || []) globalSeen.add(c);
    if (isBroken) {
      broken.push([sc, reasons]);
      console.log(`ERROR ${sc.key.padEnd(13)} ${reasons[0]}`);
    } else if (ok) {
      console.log(`OK    ${sc.key.padEnd(13)} admits the failure`);
      if (BASELINE[sc.key]) fixed.push(sc.key);
    } else if (BASELINE[sc.key]) {
      known.push([sc.key, reasons]);
      console.log(`known ${sc.key.padEnd(13)} ${reasons[0]}`);
    } else {
      regressions.push([sc, reasons]);
      console.log(`FAIL  ${sc.key.padEnd(13)} ${reasons[0]}`);
      for (const r of reasons.slice(1)) console.log(`      ${"".padEnd(13)} ${r}`);
    }
  }

  console.log("");
  if (globalSeen.size) {
    console.log("GLOBAL  the page claims completeness no matter which collector died:");
    for (const c of globalSeen) console.log(`    "${c}"`);
    console.log("    (the splash checklist marks a step ready on its failure arm too,");
    console.log("     so all 12 rows tick green with collectors dead - app.js markReady)");
    console.log("");
  }
  if (fixed.length) {
    console.log(`${fixed.length} baselined scenario(s) now pass -- delete them from BASELINE:`);
    for (const k of fixed) console.log(`    ${k}`);
    console.log("");
  }
  if (known.length) {
    console.log(`${known.length} known-dishonest scenario(s), unchanged:`);
    for (const [k] of known) console.log(`    ${k.padEnd(13)} ${BASELINE[k]}`);
    console.log("");
  }

  if (broken.length) {
    console.log(`FAIL: ${broken.length} scenario(s) could not be checked at all.`);
    for (const [sc, reasons] of broken) {
      console.log(`    ${sc.key.padEnd(13)} ${reasons[0]}`);
      console.log(`::error::${sc.key} could not be checked: ${reasons[0]}`);
    }
    console.log("");
    console.log("A scenario that errors is not a scenario that passed, and it is not");
    console.log("covered by BASELINE either. Fix the harness or the page before");
    console.log("trusting this run.");
    return 1;
  }

  if (regressions.length) {
    console.log(`FAIL: ${regressions.length} lane(s) render a dead collector as a healthy result.`);
    for (const [sc, reasons] of regressions) {
      console.log("");
      console.log(`  ${sc.key} -- ${sc.why}`);
      for (const r of reasons) console.log(`      ${r}`);
      console.log("      reproduce:");
      console.log(`        python3 tools/ui-sweep/serve_demo.py --port 8799 --fault ${sc.fault} &`);
      console.log(`        open http://127.0.0.1:8799/#${sc.tab}`);
      console.log(`::error::${sc.key} renders a failed collector as healthy: ${reasons[0]}`);
    }
    console.log("");
    console.log("A tech reads this screen to decide what is broken at a venue. A");
    console.log("check that did not run must not look like a check that passed.");
    console.log("Say so in the panel, and keep it out of any pass/fail verdict.");
    return 1;
  }

  console.log("OK: no lane outside the known baseline hides a dead collector.");
  return 0;
}

main().then((c) => process.exit(c)).catch((e) => {
  console.error("FAIL: " + e.stack);
  process.exit(1);
});
