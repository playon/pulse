// Render every Pulse tab headlessly and assert what a screenshot cannot.
//
// Pulse runs inside LogMeIn remote-desktop windows at sizes nobody chose, on
// 1366x768 VPU consoles, and sometimes maximised. No CI check has ever opened
// the page: python-tests filters Pulse.Web/app/**.py, ps-ascii-check filters
// scripts/**.ps1, launcher-sync filters the .bat copies. web-auto-tag.yml,
// however, fires on Pulse.Web/** -- so a static-only change ran zero checks
// and then published a dev pre-release.
//
// Stock node driving Chrome over CDP. No npm, no Playwright: node 22+ has a
// global WebSocket and fetch, and the fleet's constraint here is "must still
// work in three years with nobody maintaining a dependency tree".
//
// Usage (from the repo root, with tools/ui-sweep/serve_demo.py already up):
//   node tools/ui-sweep/sweep.mjs --port 8797
//   node tools/ui-sweep/sweep.mjs --port 8797 --widths 1366 --themes light
//   node tools/ui-sweep/sweep.mjs --port 8797 --tab network --verbose

import { launch, openPulse, gotoTab, sleep } from "./cdp.mjs";

const argv = process.argv.slice(2);
const arg = (name, dflt) => {
  const i = argv.indexOf("--" + name);
  return i === -1 ? dflt : argv[i + 1];
};
const flag = (name) => argv.includes("--" + name);

const PORT = Number(arg("port", 8797));
const WIDTHS = String(arg("widths", "1366,1100,900")).split(",").map(Number);
const THEMES = String(arg("themes", "light,dark")).split(",");
const ONLY_TAB = arg("tab", null);
const VERBOSE = flag("verbose");
const CDP_PORT = Number(arg("cdp-port", 9223));
const HEIGHT = Number(arg("height", 900));

// ------------------------------------------------------------ in-page checks
// Each returns a list of human-readable problems. They run in the page, so
// they must be self-contained strings.

const PAGE_SCROLL = `(() => {
  const d = document.documentElement;
  return d.scrollWidth > d.clientWidth + 1
    ? ["page scrolls horizontally: scrollWidth " + d.scrollWidth + " > " + d.clientWidth]
    : [];
})()`;

// Every identifier invoked from an inline onclick/onchange/onkeydown must
// exist as a global. A renamed or deleted handler is otherwise silent until a
// tech clicks it on a VPU.
const DEAD_HANDLERS = `(() => {
  const bad = new Set();
  for (const el of document.querySelectorAll("[onclick],[onchange],[onkeydown],[oninput]")) {
    for (const attr of ["onclick","onchange","onkeydown","oninput"]) {
      const code = el.getAttribute(attr);
      if (!code) continue;
      for (const m of code.matchAll(/([A-Za-z_$][\\w$]*)\\s*\\(/g)) {
        const name = m[1];
        if (["if","for","while","switch","catch","return","typeof","function","new"].includes(name)) continue;
        if (typeof window[name] === "function") continue;
        // Method calls (a.b()) and locals are not globals; only flag a bare
        // identifier at the start of an expression.
        const before = code[m.index - 1];
        if (before === "." || before === "$") continue;
        bad.add(name);
      }
    }
  }
  return [...bad].map(n => "inline handler calls missing global: " + n + "()");
})()`;

// Text clipped by ellipsis that carries no title= cannot be read OR copied --
// on a remote desktop that is the difference between a usable value and a
// dead one. Only leaf nodes, and only where nothing scrollable can reveal it.
const HIDDEN_TRUNCATION = `(() => {
  const out = [];
  for (const el of document.querySelectorAll("*")) {
    if (el.children.length) continue;
    const t = (el.textContent || "").trim();
    if (!t) continue;
    // Visually-hidden text is clipped on purpose -- that is the whole
    // mechanism. It exists so a signal carried by colour or an icon has an
    // accessible name, and a title= on it would be wrong, not missing.
    if (el.classList.contains("sr-only")) continue;
    if (el.scrollWidth <= el.clientWidth + 1) continue;
    if (el.getAttribute("title")) continue;
    let p = el.parentElement, scrollable = false;
    while (p && p !== document.body) {
      const o = getComputedStyle(p).overflowX;
      if ((o === "auto" || o === "scroll") && p.scrollWidth > p.clientWidth + 1) { scrollable = true; break; }
      p = p.parentElement;
    }
    if (scrollable) continue;
    out.push((el.className && typeof el.className === "string"
      ? "." + el.className.trim().split(/\\s+/).join(".") : el.tagName.toLowerCase())
      + ' clips "' + t.slice(0, 40) + '" with no title=');
  }
  return [...new Set(out)];
})()`;

// Content escaping its card is the visible symptom of a grid that assumed a
// wider window.
const CARD_OVERFLOW = `(() => {
  const out = [];
  for (const card of document.querySelectorAll(".card")) {
    const cr = card.getBoundingClientRect();
    if (cr.width === 0) continue;
    for (const el of card.querySelectorAll("*")) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      if (r.right > cr.right + 2) {
        out.push((el.className && typeof el.className === "string"
          ? "." + el.className.trim().split(/\\s+/)[0] : el.tagName.toLowerCase())
          + " overflows its .card by " + Math.round(r.right - cr.right) + "px");
        break;
      }
    }
  }
  return [...new Set(out)];
})()`;

// Blocking checks vs reported ones. The first three are deterministic given a
// pinned demo venue; the layout two are advisory because a one-pixel font
// difference between runners should never fail a build.
const BLOCKING = [
  ["console", null],
  ["page-scroll", PAGE_SCROLL],
  ["dead-handlers", DEAD_HANDLERS],
];
const ADVISORY = [
  ["card-overflow", CARD_OVERFLOW],
  ["hidden-truncation", HIDDEN_TRUNCATION],
];

// ------------------------------------------------------------------ the run
async function main() {
  const base = `http://127.0.0.1:${PORT}`;
  try {
    const probe = await fetch(base + "/", { signal: AbortSignal.timeout(4000) });
    if (!probe.ok) throw new Error("status " + probe.status);
  } catch (e) {
    console.error(`FAIL: no Pulse on ${base} (${e.message})`);
    console.error("      start it first:  python3 tools/ui-sweep/serve_demo.py --port " + PORT);
    process.exit(1);
  }

  let browser;
  try {
    browser = await launch({
      width: WIDTHS[0], height: HEIGHT, cdpPort: CDP_PORT,
      profile: "/tmp/pulse-sweep-profile",
    });
  } catch (e) {
    console.error("FAIL: " + e.message);
    process.exit(1);
  }
  const { cdp } = browser;

  const problems = [];   // blocking
  const notes = [];      // advisory
  let checked = 0;

  const record = (bucket, where, kind, items) => {
    for (const it of items) bucket.push({ where, kind, detail: it });
  };

  for (const theme of THEMES) {
    // Seed the theme the way index.html reads it, then load fresh so the
    // pre-paint hook applies it without a flash-and-restyle.
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: WIDTHS[0], height: HEIGHT, deviceScaleFactor: 1, mobile: false,
    });
    await cdp.send("Page.navigate", { url: base + "/" });
    await sleep(500);
    await cdp.eval(`localStorage.setItem("pulse-theme", ${JSON.stringify(theme)})`);
    await cdp.send("Page.navigate", { url: base + "/" });

    // The splash gates the app; app.js:590 hides it when the checklist is done.
    let ready = false;
    for (let i = 0; i < 80 && !ready; i++) {
      await sleep(250);
      try {
        ready = await cdp.eval(
          `!!document.querySelector("#splash.splash-hidden") || !document.querySelector("#splash")`
        );
      } catch { /* mid-navigation */ }
    }
    if (!ready) {
      problems.push({ where: `theme=${theme}`, kind: "startup", detail: "splash never cleared" });
      continue;
    }
    await sleep(400);

    // Startup errors belong to nobody's tab -- the landing page renders
    // before the loop starts, so without this its console output is never
    // attributed to anything and a render error on the default tab is
    // invisible. (Found by a mutation test that stayed green.)
    const startupErrs = cdp.drainConsole();
    if (startupErrs.length) record(problems, `startup ${theme}`, "console", startupErrs);

    const tabs = await cdp.eval(
      `[...NAV_SECTIONS.flatMap(s => s.pages.map(p => p.id)), ...HIDDEN_PAGES.map(p => p.id)]`
    );
    const list = ONLY_TAB ? tabs.filter((t) => t === ONLY_TAB) : tabs;
    if (ONLY_TAB && !list.length) {
      console.error(`FAIL: no such tab "${ONLY_TAB}". Known: ${tabs.join(", ")}`);
      browser.close();
      process.exit(1);
    }

    for (const width of WIDTHS) {
      await cdp.send("Emulation.setDeviceMetricsOverride", {
        width, height: HEIGHT, deviceScaleFactor: 1, mobile: false,
      });
      for (const tab of list) {
        const where = `${tab} @${width} ${theme}`;
        // Drain BEFORE navigating, never after: this tab's render happens
        // during the settle below, so a drain placed after it would discard
        // the very errors we are here to catch. (It did, until a mutation
        // test that injected a console.error came back green.)
        cdp.drainConsole();
        // Setting the hash to the tab already showing is a no-op, so that
        // tab would never be re-rendered and never measured. Hop through a
        // different one first.
        const cur = await cdp.eval(`location.hash.replace("#","")`);
        if (cur === tab) {
          const other = tabs.find((t) => t !== tab);
          if (other) {
            await cdp.eval(`location.hash = ${JSON.stringify("#" + other)}`);
            await sleep(200);
            cdp.drainConsole();
          }
        }
        await cdp.eval(`location.hash = ${JSON.stringify("#" + tab)}`);
        await sleep(350);
        await cdp.eval(`window.dispatchEvent(new Event("resize"))`);
        await sleep(250);
        checked++;

        const consoleErrs = cdp.drainConsole();
        if (consoleErrs.length) record(problems, where, "console", consoleErrs);
        for (const [kind, expr] of BLOCKING) {
          if (!expr) continue;
          try {
            record(problems, where, kind, await cdp.eval(expr));
          } catch (e) {
            record(problems, where, kind, ["check threw: " + e.message]);
          }
        }
        for (const [kind, expr] of ADVISORY) {
          try {
            record(notes, where, kind, await cdp.eval(expr));
          } catch { /* advisory: never fail the run on a probe error */ }
        }
        if (VERBOSE) console.log(`  checked ${where}`);
      }
    }
  }

  browser.close();

  // ------------------------------------------------------------- reporting
  console.log("");
  console.log(`Pulse render sweep -- ${checked} tab/width/theme combinations`);
  console.log(`  widths ${WIDTHS.join(", ")}  themes ${THEMES.join(", ")}`);
  console.log("");

  const group = (rows) => {
    const by = new Map();
    for (const r of rows) {
      const k = `${r.kind}: ${r.detail}`;
      if (!by.has(k)) by.set(k, []);
      by.get(k).push(r.where);
    }
    return by;
  };

  if (notes.length) {
    const by = group(notes);
    console.log(`ADVISORY  ${by.size} layout issue(s) -- reported, not failing:`);
    for (const [what, wheres] of [...by].slice(0, VERBOSE ? 1e9 : 25)) {
      console.log(`    ${what}`);
      console.log(`      ${wheres.length} place(s), e.g. ${wheres.slice(0, 3).join("; ")}`);
    }
    if (!VERBOSE && by.size > 25) console.log(`    ... and ${by.size - 25} more (--verbose)`);
    console.log("");
  } else {
    console.log("ADVISORY  no layout issues found");
    console.log("");
  }

  if (problems.length) {
    const by = group(problems);
    console.log(`FAIL  ${by.size} blocking problem(s):`);
    for (const [what, wheres] of by) {
      console.log(`    ${what}`);
      console.log(`      ${wheres.length} place(s), e.g. ${wheres.slice(0, 3).join("; ")}`);
      console.log(`::error::${what} (${wheres.slice(0, 3).join("; ")})`);
    }
    console.log("");
    console.log("These break the page rather than just crowd it: a JS error, a");
    console.log("handler a tech can click that does not exist, or a window that");
    console.log("scrolls sideways. Reproduce with:");
    console.log(`  python3 tools/ui-sweep/serve_demo.py --port ${PORT} &`);
    console.log(`  node tools/ui-sweep/sweep.mjs --port ${PORT} --verbose`);
    process.exit(1);
  }

  console.log("OK: every tab rendered clean at every width in both themes.");
  process.exit(0);
}

main().catch((e) => {
  console.error("FAIL: " + e.stack);
  process.exit(1);
});
