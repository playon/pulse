// Minimal Chrome DevTools Protocol client, shared by sweep.mjs and states.mjs.
//
// Stock node only -- node 22+ has a global WebSocket and fetch. No npm, no
// Playwright: this has to still run in three years without anyone tending a
// lockfile.
//
// Why CDP rather than `chrome --dump-dom`: Pulse holds a live WebSocket, so
// Chrome's virtual time never runs out and --dump-dom never exits. Its
// --timeout flag either fires before the SPA has rendered or hangs. CDP does
// not depend on the browser deciding it is finished.

import { spawn } from "node:child_process";
import { existsSync } from "node:fs";

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const CHROME_CANDIDATES = [
  process.env.CHROME_PATH,
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/usr/bin/google-chrome",
  "/usr/bin/google-chrome-stable",
  "/usr/bin/chromium-browser",
  "/usr/bin/chromium",
].filter(Boolean);

export function findChrome() {
  return CHROME_CANDIDATES.find((p) => existsSync(p)) || null;
}

export class CDP {
  constructor(ws) {
    this.ws = ws;
    this.id = 0;
    this.pending = new Map();
    this.events = [];
    ws.addEventListener("message", (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id !== undefined) {
        const p = this.pending.get(msg.id);
        if (p) {
          this.pending.delete(msg.id);
          msg.error ? p.reject(new Error(JSON.stringify(msg.error))) : p.resolve(msg.result);
        }
      } else {
        this.events.push(msg);
      }
    });
  }

  send(method, params = {}) {
    const id = ++this.id;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      setTimeout(() => {
        if (this.pending.delete(id)) reject(new Error(method + " timed out"));
      }, 30000);
    });
  }

  async eval(expression) {
    const r = await this.send("Runtime.evaluate", {
      expression,
      returnByValue: true,
      awaitPromise: true,
    });
    if (r.exceptionDetails) {
      throw new Error("eval failed: " + (r.exceptionDetails.exception?.description || ""));
    }
    return r.result.value;
  }

  drainConsole() {
    const out = [];
    for (const e of this.events) {
      if (e.method === "Runtime.exceptionThrown") {
        out.push("uncaught: " + (e.params.exceptionDetails?.exception?.description
          || e.params.exceptionDetails?.text || "?").split("\n")[0]);
      } else if (e.method === "Runtime.consoleAPICalled" && e.params.type === "error") {
        out.push("console.error: " + e.params.args
          .map((a) => a.value ?? a.description ?? "?").join(" ").split("\n")[0]);
      }
    }
    this.events.length = 0;
    return out;
  }
}

/** Launch headless Chrome and attach to its page target. */
export async function launch({ width = 1366, height = 900, cdpPort = 9223, profile = "/tmp/pulse-cdp-profile" } = {}) {
  const chrome = findChrome();
  if (!chrome) throw new Error("no Chrome found -- set CHROME_PATH");

  const proc = spawn(chrome, [
    "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
    "--no-default-browser-check", "--disable-extensions",
    "--user-data-dir=" + profile,
    `--remote-debugging-port=${cdpPort}`,
    `--window-size=${width},${height}`,
    "about:blank",
  ], { stdio: "ignore" });

  let target = null;
  for (let i = 0; i < 50 && !target; i++) {
    await sleep(200);
    try {
      const list = await (await fetch(`http://127.0.0.1:${cdpPort}/json/list`)).json();
      target = list.find((t) => t.type === "page");
    } catch { /* still booting */ }
  }
  if (!target) {
    proc.kill();
    throw new Error("Chrome did not expose a CDP page target");
  }

  // Everything past the target lookup must also kill Chrome on failure, or a
  // handshake error leaves a headless browser running for the rest of the run.
  let ws;
  try {
    ws = new WebSocket(target.webSocketDebuggerUrl);
    await new Promise((res, rej) => {
      ws.addEventListener("open", res, { once: true });
      ws.addEventListener("error", rej, { once: true });
      setTimeout(() => rej(new Error("CDP websocket did not open in 20s")), 20000);
    });
    const cdp = new CDP(ws);
    await cdp.send("Page.enable");
    await cdp.send("Runtime.enable");
    return { cdp, close: () => { try { ws.close(); } catch {} proc.kill(); } };
  } catch (e) {
    try { if (ws) ws.close(); } catch {}
    proc.kill();
    throw e;
  }
}

/**
 * Load Pulse and wait for the splash to clear.
 * The splash gates the app (app.js hides it when its checklist finishes), and
 * its duration varies with how fast the collectors answer, so polling for it
 * beats any fixed sleep.
 */
export async function openPulse(cdp, base, { theme = "light", settleMs = 400 } = {}) {
  await cdp.send("Page.navigate", { url: base + "/" });
  await sleep(500);
  await cdp.eval(`localStorage.setItem("pulse-theme", ${JSON.stringify(theme)})`);
  await cdp.send("Page.navigate", { url: base + "/" });

  // Hard wall-clock bound. An unbounded poll let a wedged renderer burn past
  // the CI job's own timeout, so the job was CANCELLED rather than failing
  // with a usable message.
  const deadline = Date.now() + 45000;
  for (let i = 0; i < 80 && Date.now() < deadline; i++) {
    await sleep(250);
    try {
      const ready = await cdp.eval(
        `!!document.querySelector("#splash.splash-hidden") || !document.querySelector("#splash")`
      );
      if (ready) {
        await sleep(settleMs);
        return true;
      }
    } catch { /* mid-navigation */ }
  }
  return false;
}

/** Visible text of the main content panel, and of the whole page. */
export async function pageText(cdp) {
  return cdp.eval(`(() => {
    const norm = (s) => (s || "").replace(/\\s+/g, " ").trim();
    const el = document.getElementById("content");
    return { panel: norm(el && el.innerText), page: norm(document.body.innerText) };
  })()`);
}

/** Navigate to a tab, forcing a re-render even if it is already showing. */
export async function gotoTab(cdp, tab, allTabs = []) {
  const cur = await cdp.eval(`location.hash.replace("#","")`);
  if (cur === tab) {
    const other = allTabs.find((t) => t !== tab);
    if (other) {
      await cdp.eval(`location.hash = ${JSON.stringify("#" + other)}`);
      await sleep(200);
    }
  }
  await cdp.eval(`location.hash = ${JSON.stringify("#" + tab)}`);
  await sleep(450);
}
