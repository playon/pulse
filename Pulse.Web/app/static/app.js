/* Pulse Web — Vanilla JS SPA */

// ── Icons (Feather-style inline SVGs) ────────────────────────
function svgIcon(name, size) {
  const s = size || 16;
  const p = {
    grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    wifi: '<path d="M5 12.55a11 11 0 0 1 14.08 0"/><path d="M1.42 9a16 16 0 0 1 21.16 0"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><circle cx="12" cy="20" r="1"/>',
    camera: '<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/>',
    monitor: '<rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>',
    cpu: '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/>',
    server: '<rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><circle cx="6" cy="6" r="1"/><circle cx="6" cy="18" r="1"/>',
    hdd: '<line x1="22" y1="12" x2="2" y2="12"/><path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
    triangle: '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
    file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
    cog: '<circle cx="12" cy="12" r="3"/><path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>',
    info: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>',
    play: '<circle cx="12" cy="12" r="10"/><polygon points="10 8 16 12 10 16 10 8"/>',
    download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
    refresh: '<polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>',
    check: '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
    chevron: '<polyline points="9 18 15 12 9 6"/>',
    x: '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
    alert: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
    heartbeat: '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    zap: '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
    thermometer: '<path d="M14 14.76V3.5a2.5 2.5 0 0 0-5 0v11.26a4.5 4.5 0 1 0 5 0z"/>',
    clock: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    globe: '<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
    link: '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    database: '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>',
    mic: '<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/>',
    shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    users: '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    mouse: '<rect x="6" y="3" width="12" height="18" rx="6"/><line x1="12" y1="7" x2="12" y2="11"/>',
    keyboard: '<rect x="2" y="6" width="20" height="12" rx="2"/><line x1="6" y1="10" x2="6" y2="10"/><line x1="10" y1="10" x2="10" y2="10"/><line x1="14" y1="10" x2="14" y2="10"/><line x1="18" y1="10" x2="18" y2="10"/><line x1="8" y1="14" x2="16" y2="14"/>',
    volume: '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>',
    "volume-x": '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/>',
    activity: '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
    send: '<line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>',
    inbox: '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
    "external-link": '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>',
    copy: '<rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    help: '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
    scale: '<path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>',
    "file-down": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M12 18v-6"/><path d="m9 15 3 3 3-3"/>',
    "share-2": '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>',
    logs: '<path d="M13 12h8"/><path d="M13 18h8"/><path d="M13 6h8"/><path d="M3 12h1"/><path d="M3 18h1"/><path d="M3 6h1"/><path d="M8 12h1"/><path d="M8 18h1"/><path d="M8 6h1"/>',
    "folder-code": '<path d="M10 10.5 8 13l2 2.5"/><path d="m14 10.5 2 2.5-2 2.5"/><path d="M2 6a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2z"/>',
    settings: '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
    "file-warning": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "clipboard-list": '<rect x="8" y="2" width="8" height="4" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="M12 11h4"/><path d="M12 16h4"/><path d="M8 11h.01"/><path d="M8 16h.01"/>',
    "id-card": '<path d="M16 10h2"/><path d="M16 14h2"/><path d="M6.17 15a3 3 0 0 1 5.66 0"/><circle cx="9" cy="11" r="2"/><rect x="2" y="5" width="20" height="14" rx="2"/>',
    package: '<path d="m7.5 4.27 9 5.15"/><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="M3.3 7 12 12l8.7-5"/><path d="M12 22V12"/>',
    power: '<path d="M18.36 6.64a9 9 0 1 1-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/>',
  };
  return `<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${p[name] || ""}</svg>`;
}

// ── Pages & Nav Sections ─────────────────────────────────────
// 6-group IA (nav restructure v3). Phase A: regroup + rename only. The current
// System Overview (`system`) and Pixellot Configuration (`pixellot-config`) tabs
// are parked in their new groups as-is; later phases split them into Hardware /
// Applications / Environment and Pixellot Software / Camera Hardware /
// Calibrations, and add Pixellot Logs / Pulse Logs / Help.
const NAV_SECTIONS = [
  { label: "TRIAGE", pages: [
    { id: "dashboard", label: "Dashboard", icon: "grid" },
    { id: "inspection-report", label: "Inspection Report", icon: "file" },
    { id: "cloud-events", label: "Event Streaming", icon: "play" },
  ]},
  { label: "TROUBLESHOOTING", pages: [
    { id: "network", label: "Network Test", icon: "wifi" },
    { id: "cameras", label: "Camera Connectivity", icon: "camera" },
    { id: "scoreconnect", label: "ScoreConnect", icon: "monitor" },
    { id: "audio", label: "Audio", icon: "mic" },
    { id: "services", label: "Service Status", icon: "server" },
  ]},
  { label: "PIXELLOT CONFIGURATION", pages: [
    { id: "pixellot-software", label: "Pixellot Software", icon: "folder-code" },
    { id: "camera-hardware", label: "Camera Hardware", icon: "camera" },
    { id: "calibrations", label: "Camera Calibrations", icon: "scale" },
  ]},
  { label: "SYSTEM INFORMATION", pages: [
    { id: "hardware", label: "Hardware", icon: "cpu" },
    { id: "applications", label: "Applications", icon: "copy" },
    { id: "disk-health", label: "Disks", icon: "hdd" },
    { id: "environment", label: "Environment", icon: "globe" },
    { id: "reboots", label: "Power Events", icon: "power" },
  ]},
  { label: "DATA LOGS", pages: [
    { id: "pixellot-logs", label: "Pixellot Logs", icon: "logs" },
    { id: "events", label: "Windows Events", icon: "file-warning" },
    { id: "pulse-logs", label: "Pulse Logs", icon: "heartbeat" },
  ]},
  { label: "PULSE", pages: [
    { id: "settings", label: "Settings", icon: "settings" },
    { id: "reports", label: "Exports", icon: "file-down" },
    { id: "help", label: "Help", icon: "help" },
    { id: "about", label: "About", icon: "info" },
  ]},
];
const PAGES = NAV_SECTIONS.flatMap((s) => s.pages);
// Hidden pages (accessible via hash but not in nav)
// "share" is parked here while Share over LAN development is paused — the
// page and its backend still work via #share; restore the nav entry to resume.
const HIDDEN_PAGES = [
  { id: "fault-isolator", label: "Camera Connection Troubleshooting" },
  { id: "share", label: "Share over LAN" },
];
// Tabs retired in the nav restructure redirect to their nearest replacement so
// old bookmarks / deep-links don't land on an "Unknown page".
const RETIRED_PAGE_ALIASES = { system: "hardware", "pixellot-config": "pixellot-software" };

let currentPage = "";
let ws = null;
let wsRetryTimer = null;
let dataCache = {};
let logEntries = [];
let fetchingKeys = new Set();
let fetchPromises = {};

// PAGE_API keys are the *fetch* keys (the cache/endpoint identifiers), which
// are NOT 1:1 with nav ids / pageRenderers. Two endpoints (`system` and
// `pixellot-config`) each back several split pages: the nav was broken up into
// Hardware/Applications/Environment and Pixellot Software/Camera Hardware/
// Calibrations, but the collectors behind them weren't. So renderHardware,
// renderApplications, renderEnvironment all fetchSection("system"), and the
// Pixellot pages all fetchSection("pixellot-config"). Keep the retired keys
// here; RETIRED_PAGE_ALIASES only redirects the old nav ids at the router.
const PAGE_API = {
  dashboard: "/api/dashboard",
  "cloud-events": "/api/cloud-events",
  system: "/api/system",
  network: "/api/network",
  cameras: "/api/cameras",
  services: "/api/services",
  "disk-health": "/api/disk-health",
  events: "/api/events",
  reboots: "/api/reboots",
  audio: "/api/audio",
  scoreconnect: "/api/scoreconnect",
  "pixellot-config": "/api/pixellot-config",
  settings: "/api/settings",
};

// ── Router ───────────────────────────────────────────────────

function navigate(id) {
  id = RETIRED_PAGE_ALIASES[id] || id;
  if (id === currentPage) return;
  // Abort any in-flight fault-isolator poll when navigating away.
  if (currentPage === "fault-isolator" && _fi) _fi._aborted = true;
  // Entering the fault isolator is always a fresh start — reset so a prior
  // run's aborted state can't make the next baseline fail. Re-fetch history.
  if (id === "fault-isolator") { _fiReset(); _fiHistoryCache = null; }
  currentPage = id;
  window.location.hash = id;
  updateNav();
  renderPage(id);
}

function updateNav() {
  document.querySelectorAll(".nav-item").forEach((el) => {
    el.classList.toggle("active", el.dataset.page === currentPage);
  });
}

// Flag each subsystem's nav link with a warning triangle from the dashboard
// findings, so the sidebar doubles as the at-a-glance health map (replaces the
// old Subsystems panel). Only warning/critical show an icon — healthy and
// non-subsystem links (Dashboard, Settings, …) show nothing.
function updateNavHealth() {
  const health = {};
  try {
    _subsystemHealth((cached("dashboard") || {}).findings || [])
      .forEach((s) => { health[s.id] = s.health; });
  } catch (e) { return; }
  document.querySelectorAll(".nav-item").forEach((el) => {
    const slot = el.querySelector(".nav-status");
    if (!slot) return;
    const h = health[el.dataset.page];
    if (h === "Critical" || h === "Warning") {
      slot.className = "nav-status " + (h === "Critical" ? "nav-status-crit" : "nav-status-warn");
      slot.innerHTML = svgIcon("triangle", 14);
      slot.title = h;
    } else {
      slot.className = "nav-status";
      slot.innerHTML = "";
      slot.removeAttribute("title");
    }
  });
}

function renderPage(id) {
  const fn = pageRenderers[id];
  if (!fn) { $page().innerHTML = `<p class="text-pulse-muted">Unknown page: ${esc(id)}</p>`; return; }
  // Defensive: if someone calls renderPage() without going through
  // navigate() (e.g. via console eval or a future caller), keep the
  // sidebar active-state and currentPage in sync so the highlight
  // can't lie about where the user is.
  if (id !== currentPage) {
    currentPage = id;
    updateNav();
  }
  try {
    fn();
  } catch (err) {
    console.error("Render error on", id, err);
    $page().innerHTML = `<div class="card"><p class="text-red-400 font-bold">Render Error</p>
      <pre class="text-xs text-pulse-muted mt-2" style="white-space:pre-wrap">${esc(err.message)}\n${esc(err.stack || "")}</pre>
      <button class="btn-outline btn-ol-blue mt-3" onclick="refreshAll()">Retry</button></div>`;
  }
}

// ── Finding deep-link (jump to the issue on its tab) ─────────
// Clicking a dashboard finding navigates to its tab, then scrolls to and
// flashes the matching row. Works entirely on the destination DOM after it
// renders, so no other tab has to cooperate. Degrades gracefully: exact row
// match → that tab's issues panel → (nothing; leaves the user at the top).
let _pendingFindingTitle = null;

function findingJump(page, encTitle) {
  // Title is encodeURIComponent'd at the call site so it's safe inside the
  // inline onclick attribute regardless of quotes/punctuation in the title.
  _pendingFindingTitle = encTitle ? decodeURIComponent(encTitle) : null;
  if (page !== currentPage) navigate(page);
  _applyFindingHighlight(0);
}

function _findFindingTarget(title) {
  const page = $page();
  if (!page || !title) return null;
  const norm = title.trim().toLowerCase();
  // 1. Opt-in anchor any tab MAY expose (none do yet — future-proofing).
  try {
    const sel = (window.CSS && CSS.escape) ? CSS.escape(norm) : norm;
    const keyed = page.querySelector(`[data-finding-key="${sel}"]`);
    if (keyed) return keyed;
  } catch (e) { /* invalid selector — ignore */ }
  // 2. A finding/issue row whose text contains the full finding title.
  //    Pick the smallest match so we land on the row, not its container.
  const rows = page.querySelectorAll(".finding-item, .net-issue-row, .cam-finding-row, .dh-event-row, li, tr");
  let best = null;
  rows.forEach((el) => {
    const txt = (el.textContent || "").trim().toLowerCase();
    if (txt && txt.indexOf(norm) !== -1) {
      if (!best || el.textContent.length < best.textContent.length) best = el;
    }
  });
  if (best) return best;
  // 3. Fall back to the tab's primary issues/findings container.
  return page.querySelector(".net-issues-list, #cam-findings-wrap, .cc-findings-list, .af-list");
}

function _applyFindingHighlight(attempt) {
  attempt = attempt || 0;
  if (!_pendingFindingTitle) return;
  const el = _findFindingTarget(_pendingFindingTitle);
  if (el) {
    _pendingFindingTitle = null;  // one-shot
    try { el.scrollIntoView({ behavior: "smooth", block: "center" }); }
    catch (e) { el.scrollIntoView(); }
    el.classList.add("finding-flash");
    setTimeout(() => el.classList.remove("finding-flash"), 2200);
    return;
  }
  // The destination section may still be fetching — retry for ~3s.
  if (attempt < 12) {
    setTimeout(() => _applyFindingHighlight(attempt + 1), 250);
  } else {
    _pendingFindingTitle = null;
  }
}

// ── Helpers ──────────────────────────────────────────────────

const $page = () => document.getElementById("page");

async function api(path) {
  try {
    const r = await fetch(path);
    return await r.json();
  } catch (e) {
    return { error: true, message: e.message };
  }
}

async function apiPost(path, body) {
  try {
    const r = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return await r.json();
  } catch (e) {
    return { error: true, message: e.message };
  }
}

function esc(s) {
  if (s == null) return "";
  const d = document.createElement("div");
  d.textContent = String(s);
  return d.innerHTML;
}

function badge(text, type) {
  return `<span class="inline-block px-2 py-0.5 rounded text-xs font-medium badge-${esc(type)}">${esc(text)}</span>`;
}

function statusBadge(status) {
  const s = (status || "").toLowerCase();
  const cap = (status || "").charAt(0).toUpperCase() + (status || "").slice(1);
  if (s === "running" || s === "up" || s === "pass" || s === "ok" || s === "healthy")
    return badge(cap, "pass");
  if (s === "stopped" || s === "down" || s === "fail" || s === "critical")
    return badge(cap, "fail");
  if (s === "warning" || s === "warn" || s === "degraded")
    return badge(cap, "warn");
  if (s === "notfound") return badge("Not Found", "muted");
  return badge(cap || "Unknown", "muted");
}

function loading() {
  return `<div class="flex items-center gap-3 text-pulse-muted loading-pulse py-12 justify-center">
    <svg class="w-5 h-5 animate-spin" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" opacity="0.3"/>
      <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>
    </svg>
    Loading...
  </div>`;
}

function card(title, body, extra) {
  return `<div class="card ${extra || ""}">
    ${title ? `<h3 class="text-sm font-semibold text-pulse-muted uppercase tracking-wide mb-3">${esc(title)}</h3>` : ""}
    ${body}
  </div>`;
}

function errorBox(msg) {
  return card(
    "",
    `<p class="text-red-400">${esc(msg || "Failed to load data. Is this running on a Windows VPU?")}</p>`
  );
}

// ── Circular Gauge ───────────────────────────────────────────

function gauge(label, value, unit, color, opts) {
  const o = opts || {};
  const maxVal = o.max || 100;
  const pct = Math.min(Math.max((value || 0) / maxVal * 100, 0), 100);
  const r = 40;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - pct / 100);
  const warnAt = o.warn || 75;
  const critAt = o.crit || 90;
  const raw = value || 0;
  const c =
    raw > critAt
      ? "var(--c-accent-red)"
      : raw > warnAt
        ? "var(--c-accent-amber)"
        : color || "var(--c-accent-blue)";
  return `<div class="flex flex-col items-center gap-2">
    <div class="relative" style="width:7rem;height:7rem">
      <svg viewBox="0 0 100 100" class="w-full h-full">
        <circle cx="50" cy="50" r="${r}" stroke="var(--c-border)" stroke-width="8" fill="none"/>
        <circle cx="50" cy="50" r="${r}" stroke="${c}" stroke-width="8" fill="none"
          stroke-dasharray="${circ}" stroke-dashoffset="${offset}"
          stroke-linecap="round" transform="rotate(-90 50 50)" class="gauge-ring"/>
      </svg>
      <div class="absolute inset-0 flex items-center justify-center">
        <span class="text-xl font-bold"><span class="gauge-val">${value != null ? esc(String(value)) : "--"}</span><span class="text-xs text-pulse-muted">${esc(unit || "%")}</span></span>
      </div>
    </div>
    <span class="text-xs text-pulse-muted font-medium">${esc(label)}</span>
  </div>`;
}

// ── Data Preload (progressive) ──────────────────────────────

// Sections whose data feeds the dashboard cards (NIC table, gauges, services, etc.).
// Used by fetchSection to avoid unnecessary dashboard re-renders during preload.
const DASHBOARD_DEPENDENCIES = new Set([
  "dashboard", "cameras", "system", "disk-health", "services",
]);

function fetchSection(key) {
  if (dataCache[key]) return Promise.resolve(dataCache[key]);
  // Return the existing in-flight promise so multiple callers wait for the same request
  if (fetchPromises[key]) return fetchPromises[key];
  const url = PAGE_API[key];
  if (!url) return Promise.resolve(null);
  fetchingKeys.add(key);
  fetchPromises[key] = api(url).then((data) => {
    fetchingKeys.delete(key);
    delete fetchPromises[key];
    // Cache ALL responses including errors. Without this, a renderer that
    // doesn't find cached data falls back to `fetchSection()` which re-fires
    // the request, the API returns an error again, and the re-render loop
    // spins at ~140ms intervals (each renderPage → renderAudio → fetchSection).
    // Renderers check `data.error` themselves and show errorBox.
    if (data) {
      dataCache[key] = data;
    }
    // Refresh the sidebar health dots when the data that drives them lands.
    if (key === "dashboard" || key === "events") updateNavHealth();
    // Re-render the current page only when the completed fetch is relevant to it.
    // For dashboard, only its own deps trigger a refresh — non-dashboard data
    // (events, audio, scoreconnect, etc.) doesn't change anything visible.
    const shouldRender = currentPage === key
      || (currentPage === "dashboard" && DASHBOARD_DEPENDENCIES.has(key));
    if (shouldRender) renderPage(currentPage);
    return data;
  });
  return fetchPromises[key];
}

// ── Splash status helpers ──────────────────────────────────────────────
// The splash shows, top to bottom: the verb (Loading/Running diagnostics),
// an "X of N systems" count, a live checklist that ticks each section off in
// boot order, an issue banner (critical/warning findings, surfaced as soon
// as the dashboard lands), and a reassurance note that escalates if a slow
// box runs long.
//
// Section labels use the friendly nav title (e.g. "Disk & System Health")
// rather than the API key (e.g. "disk-health") — we build the lookup from
// NAV_SECTIONS on first use so it stays in sync with the sidebar even if
// labels change later.
let _SECTION_LABELS_CACHE = null;
function _sectionLabels() {
  if (_SECTION_LABELS_CACHE) return _SECTION_LABELS_CACHE;
  const map = {};
  NAV_SECTIONS.forEach((s) => s.pages.forEach((p) => { map[p.id] = p.label; }));
  HIDDEN_PAGES.forEach((p) => { map[p.id] = p.label; });
  // Retired ids still fetched during preload (their /api/* feeds the split
  // tabs) — give them friendly splash labels instead of raw keys.
  map.system = map.system || "System";
  map["pixellot-config"] = map["pixellot-config"] || "Pixellot Configuration";
  _SECTION_LABELS_CACHE = map;
  return map;
}

function _setSplashVerb(text) {
  const el = document.getElementById("splash-verb");
  if (el) el.textContent = text;
}

// The reassurance line under the checklist. Defaults to the up-front
// expectation; escalates to SLOW if a box runs long (see preloadProgressive).
// SPLASH_NOTE_DEFAULT must match the static text in index.html.
const SPLASH_NOTE_DEFAULT = "Running a full diagnostic sweep — this can take a moment.";
const SPLASH_NOTE_SLOW    = "Still working — some checks (camera frames, speed test) take longer on slower units.";
// Shown on the last frame before the splash fades. Without it the note still
// reads "this can take a moment" while the verb already says "Ready".
const SPLASH_NOTE_DONE    = "All checks complete.";

// Splash reveal order — cheap local collectors first, network probes and the
// Dashboard aggregate last. This mirrors how fast sections actually SETTLE:
// the dashboard gathers every subsystem (it's always the slowest), and the
// network sweep runs live port probes. With dashboard first, the strict
// in-order reveal couldn't tick anything until the slowest section landed,
// then flooded the other eleven checks in one frame. Fetch order is
// unaffected — the dashboard is still requested first (see
// preloadProgressive); this only orders the checklist.
const SPLASH_REVEAL_ORDER = [
  "settings", "system", "services", "events", "scoreconnect",
  "pixellot-config", "disk-health", "reboots", "audio", "cameras",
  "network", "dashboard",
];

// Preload sections in splash-reveal order. Single source for both the
// checklist and the X-of-Y count, so they can't drift from each other or
// from what's actually fetched. A PAGE_API key missing from
// SPLASH_REVEAL_ORDER (a new lane) still appears — appended at the end.
function _splashSectionKeys() {
  return SPLASH_REVEAL_ORDER.filter((k) => k in PAGE_API)
    .concat(Object.keys(PAGE_API).filter((k) => !SPLASH_REVEAL_ORDER.includes(k)));
}
function _splashSectionLabel(key) {
  return _sectionLabels()[key] || key.charAt(0).toUpperCase() + key.slice(1);
}

// (Re)build the checklist with every section pending, and reset the count.
function _buildSplashChecklist() {
  const wrap = document.getElementById("splash-checklist");
  if (wrap) {
    wrap.innerHTML = _splashSectionKeys().map((key) =>
      `<div class="splash-check" data-key="${esc(key)}">`
      +   `<span class="splash-check-mark"></span>`
      +   `<span class="splash-check-label">${esc(_splashSectionLabel(key))}</span>`
      + `</div>`
    ).join("");
  }
  _setSplashCount(0, _splashSectionKeys().length);
}

function _markSplashSectionDone(key) {
  if (!key) return;
  const wrap = document.getElementById("splash-checklist");
  const row = wrap && wrap.querySelector(`.splash-check[data-key="${key}"]`);
  if (row) row.classList.add("done");
}

// Final frame before the splash fades: everything checked, count full.
function _completeSplashChecklist() {
  const wrap = document.getElementById("splash-checklist");
  if (wrap) wrap.querySelectorAll(".splash-check").forEach((r) => r.classList.add("done"));
  const total = _splashSectionKeys().length;
  _setSplashCount(total, total);
}

function _setSplashCount(done, total) {
  const el = document.getElementById("splash-count");
  if (el) el.textContent = `Checked ${done} of ${total} system${total === 1 ? "" : "s"}`;
}

function _setSplashNote(text) {
  const el = document.getElementById("splash-note");
  if (el) el.textContent = text;
}

// Surface critical/warning findings on the splash. Driven by the dashboard
// payload (fetched first), whose findings already aggregate every subsystem
// — the same source the dashboard headline and nav health dots use. Hidden
// on a clean box; pass a falsy/empty payload to clear it.
function _setSplashIssues(dash) {
  const el = document.getElementById("splash-issues");
  if (!el) return;
  const findings = (dash && dash.findings) || [];
  const crit = findings.filter((f) => f.severity === "critical").length;
  const warn = findings.filter((f) => f.severity === "warning").length;
  if (!crit && !warn) { el.className = "splash-issues"; el.innerHTML = ""; return; }
  const parts = [];
  if (crit) parts.push(`${crit} Critical`);
  if (warn) parts.push(`${warn} Warning${warn === 1 ? "" : "s"}`);
  el.className = "splash-issues is-visible " + (crit ? "splash-issues-crit" : "splash-issues-warn");
  el.innerHTML = `${svgIcon("triangle", 14)}<span>${parts.join(" · ")} found — details on the Dashboard</span>`;
}

// "Still working" escalation timer. Armed only on real (non-demo) loads —
// demo finishes in ~3s, so the slow note would never legitimately fire there.
let _splashSlowTimer = null;
function _armSplashSlowTimer(active) {
  if (_splashSlowTimer) { clearTimeout(_splashSlowTimer); _splashSlowTimer = null; }
  if (active) _splashSlowTimer = setTimeout(() => _setSplashNote(SPLASH_NOTE_SLOW), 20000);
}
function _clearSplashSlowTimer() {
  if (_splashSlowTimer) { clearTimeout(_splashSlowTimer); _splashSlowTimer = null; }
}

let _splashPctAnim = null;
function _setSplashPct(targetPct) {
  const el = document.getElementById("splash-pct");
  const fill = document.getElementById("splash-progress-fill");
  if (!el && !fill) return;
  const clamped = Math.max(0, Math.min(100, targetPct));
  if (fill) fill.style.width = clamped + "%";
  if (!el) return;
  // Smoothly tween the displayed number from current → target over ~350ms
  // so the percentage feels like it's growing instead of jumping.
  if (_splashPctAnim) cancelAnimationFrame(_splashPctAnim);
  const start = parseInt(el.textContent, 10) || 0;
  const startTs = performance.now();
  const duration = 350;
  const step = (ts) => {
    const t = Math.min(1, (ts - startTs) / duration);
    const v = Math.round(start + (clamped - start) * t);
    el.textContent = v + "%";
    if (t < 1) _splashPctAnim = requestAnimationFrame(step);
    else _splashPctAnim = null;
  };
  _splashPctAnim = requestAnimationFrame(step);
}

function showSplash(verbText) {
  const splash = document.getElementById("splash");
  if (!splash) return;
  _setSplashVerb(verbText || "Loading diagnostics…");
  _setSplashNote(SPLASH_NOTE_DEFAULT);   // reset any prior "still working" escalation
  _setSplashIssues(null);                // clear a prior run's findings banner
  _buildSplashChecklist();               // all sections pending, count 0 of N
  _setSplashPct(0);
  splash.classList.remove("splash-hidden");
}

function hideSplash() {
  const splash = document.getElementById("splash");
  if (!splash) return;
  _clearSplashSlowTimer();
  _completeSplashChecklist();   // last visible frame: everything checked
  _setSplashPct(100);
  _setSplashVerb("Ready");
  _setSplashNote(SPLASH_NOTE_DONE);
  splash.classList.add("splash-hidden");
}

function preloadProgressive(opts) {
  // Resolves when every preload section has settled. The splash waits on
  // this Promise so the user sees a loading state through the whole cold
  // start, not just the dashboard fetch.
  //
  // Concurrency is throttled server-side by a 4-slot PowerShell semaphore
  // + a 25s result cache, so we fire everything in parallel here instead
  // of staggering by 300ms — the stagger was hand-throttling on top of a
  // throttle, adding 2–3s of pure waiting to the splash.
  const o = opts || {};
  const verb = o.verb || "Loading diagnostics";
  const deferred = Object.keys(PAGE_API).filter((k) => k !== "dashboard");
  // Pace each reveal with a small delay so the splash actually SHOWS each
  // section being checked instead of flashing past. Real boxes need this as
  // much as demo: sections settle in bunches (everything but the slow
  // aggregates lands within a few seconds), and with no gap the in-order
  // reveal ticks a bunch in one frame. Demo gets a longer gap (~280ms — its
  // ~3s total mirrors the field UX); real boxes a short one, since theirs
  // only spaces out bunched ticks on top of genuine load time.
  // window.__PULSE_DEMO_MODE is injected into the HTML at render time so we
  // know synchronously — relying on the /api/version response races with
  // the first reveal and (in practice) loses.
  const REAL_TICK_DELAY_MS = 150;
  let _tickDelayMs = (typeof window !== "undefined" && window.__PULSE_DEMO_MODE) ? 280 : REAL_TICK_DELAY_MS;

  // Sections are fetched in parallel below (fast — the server caps the real
  // work with a 4-slot PowerShell semaphore), so they SETTLE in arbitrary
  // order. The checklist, though, reveals strictly in SPLASH_REVEAL_ORDER
  // (cheap sections first, network/dashboard last — roughly settle order)
  // so it reads as steady top-to-bottom progress instead of checks popping
  // in at random. We decouple "data arrived" (markReady) from "shown
  // checked" (the reveal loop): each step is ticked off only once it AND
  // every step before it has landed — a deterministic boot sequence without
  // serializing (and thus slowing) the actual fetches.
  const order = _splashSectionKeys();   // settings, system, … network, dashboard
  const total = order.length;
  const _resolveReady = {};
  const _ready = {};
  order.forEach((k) => { _ready[k] = new Promise((res) => { _resolveReady[k] = res; }); });
  // Idempotent and failure-safe: a rejected fetch must still mark its step
  // ready, or the in-order reveal would wait on it forever and the splash
  // would never hide.
  const markReady = (key) => { const r = _resolveReady[key]; if (r) { _resolveReady[key] = null; r(); } };
  const _reveal = (async () => {
    for (let i = 0; i < order.length; i++) {
      const key = order[i];
      await _ready[key];
      if (_tickDelayMs > 0) await new Promise((r) => setTimeout(r, _tickDelayMs));
      _markSplashSectionDone(key);
      _setSplashCount(i + 1, total);
      _setSplashPct(((i + 1) / total) * 100);
    }
  })();

  _setSplashVerb(`${verb}…`);
  _setSplashNote(SPLASH_NOTE_DEFAULT);
  _setSplashIssues(null);
  _buildSplashChecklist();
  _setSplashPct(0);
  // Real boxes only: if the sweep runs long, soften the note so a slow
  // load never looks like a hang. Demo finishes in ~3s, so don't arm it.
  _armSplashSlowTimer(!(typeof window !== "undefined" && window.__PULSE_DEMO_MODE));

  // Version + log endpoints — run in parallel, not gated on dashboard.
  const versionPromise = api("/api/version").then((data) => {
    if (data?.version) {
      dataCache._version = data.version;
      const footer = document.querySelector(".sidebar-footer");
      if (footer) footer.textContent = data.version;
      if (currentPage === "about") renderPage("about");
    }
    // Engage the demo pacing for THIS preload (~2.5s total across 9 ticks).
    if (data?.demoMode) _tickDelayMs = 280;
    // One-shot notice: the server just moved this install off the retired
    // beta channel (see _migrate_retired_beta in main.py). Next launch is a
    // plain production install and the flag is gone, so this shows once.
    if (data?.channelMoved) _showChannelMovedBanner();
  });
  const logsPromise = api("/api/logs").then((logData) => {
    if (logData && !logData.error) {
      appendLogs(logData.logs || []);
      if (logData.demoMode) {
        document.getElementById("demo-banner")?.classList.remove("hidden");
      }
    }
  });

  // Dashboard first — its result lets us start the WebSocket for live metric
  // updates, and surfaces any critical/warning findings on the splash right
  // away (its findings already aggregate every subsystem). The second
  // (rejection) handler still markReady-s so a failed dashboard can't stall
  // the in-order reveal.
  const dashboardPromise = fetchSection("dashboard").then((res) => {
    markReady("dashboard");
    try { _setSplashIssues(res); } catch (e) {}
    connectWS();
    return res;
  }, () => { markReady("dashboard"); });

  // All other sections fire immediately. Identical-script requests dedupe
  // server-side, so this doesn't trigger duplicate PS work. markReady on both
  // outcomes, for the same no-stall reason as the dashboard above.
  const deferredPromises = deferred.map((key) =>
    fetchSection(key).then((res) => { markReady(key); return res; }, () => { markReady(key); })
  );

  // allSettled so one failing endpoint can't trap the splash. Also wait on
  // the reveal so the splash stays up until the paced checklist has
  // actually FINISHED ticking through — not just when the fetches return.
  return Promise.allSettled([
    dashboardPromise, versionPromise, logsPromise, ...deferredPromises,
  ]).then(async (results) => {
    await _reveal;
    _clearSplashSlowTimer();   // finished in time — no "still working" needed
    return results;
  });
}

async function refreshAll() {
  // Full re-run: clear local + server caches, drop the live WS, then
  // re-show the splash and gate it on a fresh preload — exactly like a
  // cold start. Without the server-side cache clear, "Run All" would
  // return the same 25-second-cached results that the splash just used.
  dataCache = {};
  fetchingKeys.clear();
  fetchPromises = {};
  if (ws && ws.readyState <= 1) { try { ws.close(); } catch {} }
  // Fire-and-forget the cache clear — we don't need to wait for the
  // ack before showing the splash; the next fetches will miss the
  // cache once the POST completes (sub-second).
  apiPost("/api/scripts/clear-cache", {}).catch(() => {});
  showSplash("Running diagnostics");
  renderPage(currentPage);
  const preloadPromise = preloadProgressive({ verb: "Running diagnostics" });
  const safetyTimeout = new Promise((resolve) => setTimeout(resolve, 60000));
  Promise.race([preloadPromise, safetyTimeout]).then(hideSplash);
}

async function refreshSection(key) {
  dataCache[key] = null;
  fetchingKeys.delete(key);
  delete fetchPromises[key];
  renderPage(currentPage);
  fetchSection(key);
}

function cancelAll() {
  apiPost("/api/scripts/cancel-all", {});
}

function cached(key) {
  return dataCache[key] || null;
}

function sectionLoading(label) {
  const isFetching = fetchingKeys.size > 0;
  return `<div class="section-loading">
    <div class="section-loading-inner">
      <svg class="w-5 h-5 animate-spin" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" opacity="0.3"/>
        <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>
      </svg>
      <span>Loading ${esc(label)}...</span>
      ${isFetching ? `<button class="btn-cancel" onclick="cancelAll()">Cancel</button>` : ""}
    </div>
  </div>`;
}

// ── Log helpers ─────────────────────────────────────────────
// The bottom log drawer was retired in favor of the full-page Pulse Logs tab
// (see renderPulseLogs). These helpers + the live `logEntries` buffer it
// accumulates are still shared with that tab.

function _logEmptyState(message) {
  return `<div class="log-empty">${esc(message)}</div>`;
}

// One script-call log row. Rendered by the Pulse Logs tab (_renderPulseLogsScript).
function _scriptLogEntryHtml(e) {
  const statusCls = e.status === "ok" ? "log-ok"
    : e.status === "timeout" || e.status === "warn" ? "log-warn"
    : "log-err";
  return `<div class="log-entry">
    <span class="log-ts">${esc(e.ts?.split("T")[1] || "")}</span>
    <span class="log-script">${esc(e.script)}</span>
    <span class="log-dur">${e.durationMs != null ? e.durationMs + "ms" : ""}</span>
    <span class="log-size">${e.bytes > 0 ? formatBytes(e.bytes) : ""}</span>
    <span class="log-status ${statusCls}">${esc(e.status)}</span>
    <span class="log-detail">${esc(e.detail)}</span>
  </div>`;
}

function appendLogs(newLogs) {
  if (!newLogs?.length) return;
  logEntries.push(...newLogs);
  if (logEntries.length > 500) logEntries = logEntries.slice(-500);
  // Keep the full-page Pulse Logs tab live as new script calls stream in.
  if (currentPage === "pulse-logs") _renderPulseLogsScript();
}

function _updateThemeToggle() {
  const btn = document.getElementById("theme-toggle");
  if (!btn) return;
  const isDark = document.documentElement.classList.contains("dark");
  btn.innerHTML = isDark
    ? `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg> Light mode`
    : `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg> Dark mode`;
}

function toggleTheme() {
  const isDark = document.documentElement.classList.toggle("dark");
  localStorage.setItem("pulse-theme", isDark ? "dark" : "light");
  _updateThemeToggle();
}

// ── WebSocket ────────────────────────────────────────────────

function connectWS() {
  if (ws && ws.readyState <= 1) return;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onopen = () => {
    _wsConnected = true;
    _wsEverConnected = true;
    _refreshLiveIndicator();
    if (currentPage === "network" && _liveNetHealth) _renderLiveNetHealth(_liveNetHealth);
  };
  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      if (msg.type === "metrics") {
        updateLiveMetrics(msg);
        appendLogs(msg.logs);
        _updateLmiCountdown(msg.lmiShutdownSecs);
      }
    } catch { /* ignore parse errors */ }
  };
  ws.onclose = () => {
    _wsConnected = false;
    _refreshLiveIndicator();
    if (currentPage === "network" && _liveNetHealth) _renderLiveNetHealth(_liveNetHealth);
    clearTimeout(wsRetryTimer);
    wsRetryTimer = setTimeout(connectWS, 5000);
  };
  ws.onerror = () => ws.close();
}

// Latest network health from WebSocket — shared between pages
var _liveNetHealth = null;
var _wsConnected = false;
// Track previous TCP counters to compute deltas (Get-Counter values are cumulative since boot)
var _prevLiveCounters = null;

// ── Live freshness indicator ─────────────────────────────────
// The System Status gauges update live over the WebSocket every few
// seconds, while the Command Center shows a one-time "Baseline completed"
// snapshot time. This indicator makes the distinction explicit so a tech
// knows the gauges are live (a green pulsing dot) or stalled ("Reconnecting…").
var _wsEverConnected = false;
function _liveIndicatorHtml() {
  if (_wsConnected) {
    // Healthy = nothing shown (no dot, no label). The indicator only appears
    // when the live stream drops, where it actually carries information.
    return "";
  }
  // "Connecting…" on first load (never connected yet) vs "Reconnecting…"
  // after a drop — the latter implies a problem, the former is normal.
  return _wsEverConnected
    ? `<span class="live-dot live-dot-off"></span><span>Reconnecting…</span>`
    : `<span class="live-dot live-dot-connecting"></span><span>Connecting…</span>`;
}
function _refreshLiveIndicator() {
  const el = document.getElementById("live-indicator");
  if (el) el.innerHTML = _liveIndicatorHtml();
}

// ── LMI auto-close countdown banner ──────────────────────────
// The server counts down to auto-close after the LogMeIn session that
// launched Pulse ends (main.py _lmi_session_watch). Every metrics frame
// carries lmiShutdownSecs — a number while that countdown runs, null
// otherwise. The banner ticks locally every second between frames so the
// time reads smoothly; a null frame after a countdown means the session
// reconnected, so flash the cancel confirmation and hide.
var _lmiDeadline = null;     // ms epoch of the pending close, or null
var _lmiTicker = null;
var _lmiCancelTimer = null;

function _lmiFmtLeft(ms) {
  const s = Math.max(0, Math.ceil(ms / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function _lmiRenderCountdown() {
  const el = document.getElementById("lmi-countdown");
  if (!el || _lmiDeadline == null) return;
  const left = _lmiDeadline - Date.now();
  el.textContent = left <= 0
    ? "Pulse is closing…"
    : `LogMeIn session ended — Pulse will close in ${_lmiFmtLeft(left)}. Reconnecting cancels this.`;
}

function _updateLmiCountdown(secs) {
  const el = document.getElementById("lmi-countdown");
  if (!el) return;
  if (typeof secs === "number") {
    clearTimeout(_lmiCancelTimer);
    _lmiCancelTimer = null;
    _lmiDeadline = Date.now() + secs * 1000;
    el.classList.remove("hidden", "ok");
    _lmiRenderCountdown();
    if (!_lmiTicker) _lmiTicker = setInterval(_lmiRenderCountdown, 1000);
    return;
  }
  // No countdown in this frame. If one was on screen, the session
  // reconnected and the server cancelled the close — confirm, then hide.
  if (_lmiDeadline != null) {
    _lmiDeadline = null;
    clearInterval(_lmiTicker);
    _lmiTicker = null;
    el.classList.add("ok");
    el.textContent = "LogMeIn session reconnected — auto-close cancelled.";
    _lmiCancelTimer = setTimeout(() => el.classList.add("hidden"), 6000);
  }
}

function updateLiveMetrics(msg) {
  // Store network health regardless of current page
  if (msg.networkHealth && !msg.networkHealth.error) {
    _liveNetHealth = msg.networkHealth;
    if (currentPage === "network") _renderLiveNetHealth(msg.networkHealth);
  }
  if (currentPage !== "dashboard") return;
  const perf = msg.performance || {};
  const cpu = perf.cpu?.usagePercent;
  const mem = perf.memory?.usedPercent;
  const disk = _systemDiskPct(perf);

  // Update system status gauge SVGs
  _updateGaugeLive("cpu", cpu);
  _updateGaugeLive("mem", mem);
  _updateGaugeLive("disk", disk);
  const liveT = perf.temperature?.celsius;
  _updateGaugeLive("temp", liveT, { max: 100, warn: 65, crit: 85, unit: "°C" });

  // Auto-refresh findings when live metrics diverge from cached snapshot.
  // We match by (category + severity) instead of title strings so this
  // doesn't silently break when finding wording changes in main.py.
  const dash = dataCache["dashboard"];
  if (dash && dash.findings?.length) {
    const hasFinding = (cat, sev) => dash.findings.some(
      (f) => (f.category || "").toLowerCase() === cat && f.severity === sev
    );
    const hadCpuCrit = hasFinding("performance", "critical")
      && dash.findings.some((f) => /cpu/i.test(f.title || ""));
    const hadCpuWarn = hasFinding("performance", "warning")
      && dash.findings.some((f) => /cpu/i.test(f.title || ""));
    const hadTempCrit = hasFinding("hardware", "critical")
      && dash.findings.some((f) => /temp/i.test(f.title || ""));
    const liveTemp = perf.temperature?.celsius;
    const stale =
      (hadCpuCrit && cpu != null && cpu <= 75) ||
      (hadCpuWarn && cpu != null && cpu <= 60) ||
      (hadTempCrit && liveTemp != null && liveTemp <= 85);
    if (stale) refreshSection("dashboard");
  }
}

function _updateGaugeLive(name, val, opts) {
  const col = document.querySelector(`[data-gauge="${name}"]`);
  if (!col) return;
  const o = opts || {};
  const maxVal = o.max || 100;
  const warnAt = o.warn || 75;
  const critAt = o.crit || 90;
  const ring = col.querySelector(".gauge-ring");
  const valEl = col.querySelector(".gauge-val");
  if (ring) {
    const pct = Math.min(Math.max((val || 0) / maxVal * 100, 0), 100);
    const r = 40;
    const circ = 2 * Math.PI * r;
    ring.setAttribute("stroke-dashoffset", String(circ * (1 - pct / 100)));
    const raw = val || 0;
    ring.setAttribute("stroke", raw > critAt ? "var(--c-accent-red)" : raw > warnAt ? "var(--c-accent-amber)" : "var(--c-accent-blue)");
  }
  if (valEl) valEl.textContent = val != null ? Math.round(val) : "--";
}

// ── Page Renderers ───────────────────────────────────────────

const pageRenderers = {
  dashboard: renderDashboard,
  // Read-only fleet-audit roll-up under TRIAGE. Reuses the cached /api/system,
  // /api/network and /api/cameras payloads — no own endpoint (skips PAGE_API).
  "inspection-report": renderInspectionReport,
  // Cloud-side view of this VPU's recent events and whether each streamed —
  // NFHS search/Unity/EQS lookups keyed off the box's own venueId + recorded
  // event ids. All calls server-side via /api/cloud-events.
  "cloud-events": renderCloudEvents,
  // System Overview was split into Hardware / Applications / Environment
  // (nav restructure v3); the `system` id is retired but its /api/system
  // payload still feeds all three (and Pixellot Software, below).
  hardware: renderHardware,
  applications: renderApplications,
  environment: renderEnvironment,
  network: renderNetwork,
  cameras: renderCameras,
  services: renderServices,
  "disk-health": renderDiskHealth,
  events: renderEvents,
  reboots: renderReboots,
  "pixellot-logs": renderPixellotLogs,
  "pulse-logs": renderPulseLogs,
  help: renderHelp,
  reports: renderReports,
  share: renderShare,
  audio: renderAudio,
  scoreconnect: renderScoreConnect,
  // Pixellot Configuration was split into Pixellot Software / Camera Hardware /
  // Calibrations (nav restructure v3); the `pixellot-config` id is retired but
  // its /api/pixellot-config payload still feeds all three.
  "pixellot-software": renderPixellotSoftware,
  "camera-hardware": renderCameraHardware,
  calibrations: renderCalibrations,
  "fault-isolator": renderFaultIsolator,
  settings: renderSettings,
  about: renderAbout,
};

// ── Event Streaming (cloud-events) ───────────────────────────
// "I am this VPU → I had this event → I did/didn't stream → because of X."
// Data: /api/cloud-events — the box's venueId + recorded event ids chained
// through the public NFHS cloud APIs (search, Unity, EQS) server-side, merged
// with local recording evidence from D:\recordedEvents. Cloud metrics are
// CURRENT state; only local recording facts are anchored to the event itself.

const _CE_VERDICTS = {
  streamed: ["ok", "Streamed"],
  quality:  ["warning", "Quality issues"],
  partial:  ["critical", "Ended early"],
  failed:   ["critical", "Did not stream"],
  live:     ["ok", "Live now"],
  unable:   ["critical", "Unable to stream"],
  upcoming: ["muted", "Upcoming"],
  unknown:  ["muted", "Unknown"],
};

function renderCloudEvents() {
  const data = cached("cloud-events");
  if (!data) { $page().innerHTML = sectionLoading("Event Streaming"); fetchSection("cloud-events"); return; }
  if (data.error) { $page().innerHTML = errorBox(data.message); return; }

  const ident = data.identity || {};
  const cloud = data.cloud || {};
  const localEv = (data.localEvents || {}).events || [];
  const header = pageHeader(
    "Event Streaming",
    "This VPU's recent events as the NFHS cloud sees them — did each one stream, and if not, why. Cloud evidence reflects right now; local recording facts are from the event itself.",
    `<button class="btn-outline btn-ol-blue" onclick="dataCache['cloud-events']=null;renderCloudEvents()">${svgIcon("refresh", 14)} Refresh</button>`
  );

  // No venue id on the box → we can't self-identify to the cloud.
  if (!ident.venueId) {
    $page().innerHTML = `${header}
      <div class="card">
        <div class="text-sm font-medium mb-1">No venue ID found on this box</div>
        <div class="text-xs text-pulse-muted">Pulse reads the Pixellot venue ID from the Coordinator log (C:\\Pixellot\\Data\\Log). A fresh image, rotated logs, or a non-VPU host can leave it empty — without it the cloud lookup can't identify this unit.</div>
      </div>`;
    return;
  }

  // Cloud unreachable → say so once, plainly; never a device finding.
  if (!cloud.available) {
    $page().innerHTML = `${header}
      <div class="card">
        <div class="flex items-center gap-2 mb-1">${svgIcon("alert", 16)}<span class="text-sm font-medium">Cloud lookup unavailable</span></div>
        <div class="text-xs text-pulse-muted">${esc(cloud.error || "The NFHS cloud APIs could not be reached from this network.")} This is a connectivity statement, not a device fault — school networks often block or intercept outbound HTTPS. See <a class="cam-hw-pointer" href="#network" onclick="navigate('network');return false;">Network Test</a>.</div>
      </div>
      ${_ceLocalOnlyTable(localEv)}`;
    return;
  }

  const prod = cloud.producer || {};
  const met = cloud.metrics || {};
  const school = (prod.publishers || [])[0] || {};

  const drift = prod.currentSwVersion && prod.targetSwVersion && prod.currentSwVersion !== prod.targetSwVersion;
  const identCard = `
    ${_cePanelTitle("PIXELLOT CLOUD IDENTITY", "globe")}
    <div class="card">
      <div class="text-sm font-medium">${esc(prod.name || school.name || ident.vpuName || "Unknown unit")}</div>
      <div class="text-xs text-pulse-muted font-mono mt-1">${school.key ? `school ${esc(school.key)} · ` : ""}${esc(prod.pixellotKey || "no pixellot key")}</div>
      <div class="flex items-center gap-2 flex-wrap mt-3">
        ${met.connection ? (prod.internalStatus === "broadcasting"
          // On a dormant (not-broadcasting) unit "connection Ok" just means
          // "checks in with Pixellot", not "ready to stream" — render it
          // neutral grey so a parked box doesn't lead with a green light.
          ? severityChip(met.connection === "Ok" ? "ok" : "critical", `Cloud connection: ${met.connection}`)
          : severityChip("muted", `Cloud connection: ${met.connection}`)) : ""}
        ${prod.internalStatus ? severityChip(prod.internalStatus === "broadcasting" ? "ok" : "warning", prod.internalStatus === "broadcasting" ? "NFHS Broadcasting Status: Broadcasting" : "NFHS Broadcasting Status: Not Broadcasting") : ""}
        ${drift ? severityChip("warning", `SW ${prod.currentSwVersion} → target ${prod.targetSwVersion}`)
                : prod.currentSwVersion ? severityChip("ok", `SW ${prod.currentSwVersion}`) : ""}
        ${cloud.eqsAvgScore !== null && cloud.eqsAvgScore !== undefined ? severityChip(cloud.eqsAvgScore >= 0.85 ? "ok" : "warning", `EQS ${(cloud.eqsAvgScore * 100).toFixed(0)}%`) : ""}
      </div>
    </div>`;

  const hints = (cloud.causeHints || []).map((h) => `
    <div class="flex items-start gap-2 py-1">
      ${severityChip(h.severity, (h.severity || "info").toUpperCase())}
      <div class="text-xs">${esc(h.text)}${h.page ? ` — <a class="cam-hw-pointer" href="#${esc(h.page)}" onclick="navigate('${esc(h.page)}');return false;">open ${esc(h.page === "cameras" ? "Camera Connectivity" : h.page === "scoreconnect" ? "ScoreConnect" : h.page === "audio" ? "Audio" : "Network Test")}</a>` : ""}</div>
    </div>`).join("");
  const hintsCard = `
    ${_cePanelTitle("CLOUD FINDINGS", "alert")}
    <div class="card">${hints || '<div class="text-xs text-pulse-muted">No active cloud findings.</div>'}</div>`;

  const events = cloud.events || [];
  const rows = events.map((ev) => {
    const [sev, label] = _CE_VERDICTS[ev.verdict] || _CE_VERDICTS.unknown;
    const vod = ev.local
      ? (ev.local.recorded ? `${formatBytes(ev.local.videoBytes)} recorded` : '<span class="sev-chip sev-chip-crit whitespace-nowrap">no recording</span>')
      : '<span class="text-pulse-muted">—</span>';
    const reasons = (ev.verdictReasons || []).map((r) => `<div>${esc(r)}</div>`).join("");
    const score = ev.eqs && ev.eqs.eventScore !== null && ev.eqs.eventScore !== undefined
      ? `${(ev.eqs.eventScore * 100).toFixed(0)}%` : '<span class="text-pulse-muted">—</span>';
    return `<tr>
      <td class="text-xs font-mono">${esc(ev.gameKey || ev.pixellotEventId || "—")}</td>
      <td class="text-xs">${esc(ev.headline || "—")}${ev.sport ? `<br><span class="text-pulse-muted">${esc(ev.sport)}</span>` : ""}</td>
      <td class="text-xs whitespace-nowrap font-mono">${formatTime(ev.startTime)}</td>
      <td class="whitespace-nowrap">${severityChip("muted", ev.unlisted ? "Unlisted" : "Listed")}</td>
      <td class="whitespace-nowrap">${severityChip(sev, label)}</td>
      <td class="text-xs">${vod}</td>
      <td class="text-xs">${score}</td>
      <td class="text-xs">${reasons || '<span class="text-pulse-muted">—</span>'}</td>
    </tr>`;
  }).join("");

  const table = `
    ${_cePanelTitle("RECENT &amp; UPCOMING EVENTS", "clock")}
    ${events.length ? `
    <div class="card">
      <div class="ev-count">${events.length} event${events.length === 1 ? "" : "s"} (last 14 days + upcoming week, plus anything the box recorded)</div>
      <div class="ev-table-wrap">
        <table class="data-table ev-table"><thead><tr>
          <th>Event ID</th><th>Event Name</th><th>Date/Time</th><th>Visibility</th><th>Verdict</th><th>Local VOD Status</th><th>EQS Score</th><th>Evidence</th>
        </tr></thead><tbody>${rows}</tbody></table>
      </div>
    </div>`
    : '<div class="card"><div class="text-center py-8 text-pulse-muted">No events found for this venue in the lookback window.</div></div>'}`;

  $page().innerHTML = `${header}${identCard}${hintsCard}${table}`;
}

// Small uppercase heading (icon + label) above each panel card.
function _cePanelTitle(t, icon) {
  return `<div class="flex items-center gap-2 text-xs font-medium text-pulse-muted mt-4 mb-1">${icon ? svgIcon(icon, 14) : ""}<span>${t}</span></div>`;
}

// Local-only fallback table when the cloud is unreachable: the box's own
// recording folders still tell a story (did it record? did it upload?).
function _ceLocalOnlyTable(localEv) {
  if (!localEv.length) return '<div class="card mt-4"><div class="text-center py-8 text-pulse-muted">No local recordings found under D:\\recordedEvents either.</div></div>';
  const rows = localEv.map((e) => `<tr>
    <td class="text-xs font-mono whitespace-nowrap">${esc(e.date)}</td>
    <td class="text-xs">${esc(e.name || e.eventId)}</td>
    <td class="text-xs">${e.videoBytes > 0 ? formatBytes(e.videoBytes) : '<span class="sev-chip sev-chip-crit">no recording</span>'}</td>
    <td class="text-xs">${e.uploadedCount || 0}</td>
  </tr>`).join("");
  return `<div class="card mt-4">
    <div class="ev-count">Local recordings (cloud unreachable — box-side evidence only)</div>
    <div class="ev-table-wrap">
      <table class="data-table ev-table"><thead><tr>
        <th>Date</th><th>Event</th><th>Recorded</th><th>Artifacts uploaded</th>
      </tr></thead><tbody>${rows}</tbody></table>
    </div>
  </div>`;
}

// ── Pixellot Configuration ───────────────────────────────────
// Local, on-host view of how the Pixellot software has this VPU + cameras
// configured (NOT the Pixellot Cloud lane). Data: /api/pixellot-config —
// registry + cameras.cfg + filesystem calibration, with live per-camera
// firmware/tvMode from the shared CGI probe.

const _PC_STALE_DAYS = 180; // calibration older than this is flagged stale

function _pcFmtDate(iso) {
  if (!iso) return "—";
  const dt = new Date(iso);
  if (isNaN(dt.getTime())) return esc(String(iso));
  const days = Math.floor((Date.now() - dt.getTime()) / 86400000);
  const label = dt.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  let ago = "";
  if (days === 0) ago = " (today)";
  else if (days === 1) ago = " (1 day ago)";
  else if (days > 1) ago = ` (${days} days ago)`;
  return esc(label) + `<span class="text-pulse-muted">${ago}</span>`;
}

function _pcDaysSince(iso) {
  if (!iso) return null;
  const dt = new Date(iso);
  if (isNaN(dt.getTime())) return null;
  return Math.floor((Date.now() - dt.getTime()) / 86400000);
}

// ── Pixellot Software (full) ─────────────────────────────────
// Version + GPU/OS compatibility (from /api/system) plus install/agent and the
// raw registry dump (from /api/pixellot-config). Reads both caches; the page id
// no longer matches either key, so it kicks off both fetches and re-renders.
function renderPixellotSoftware() {
  const sys = cached("system");
  const pc = cached("pixellot-config");
  if (!sys || !pc) {
    $page().innerHTML = sectionLoading("Pixellot Software");
    Promise.all([fetchSection("system"), fetchSection("pixellot-config")])
      .then(() => { if (currentPage === "pixellot-software") renderPixellotSoftware(); });
    return;
  }
  const id = sys.identity || {};
  const pix = id.pixellot || {};
  const reg = (!pc.error && pc.registryConfig) || {};
  const installPath = reg.InstallPath || reg.installPath || reg.Path || "C:\\Pixellot";
  const regKeys = Object.keys(reg);
  const regRows = regKeys.length
    ? regKeys.map((k) => kvRow(k, reg[k])).join("")
    : `<div class="info-chip">No HKLM\\SOFTWARE\\Pixellot values found.</div>`;

  $page().innerHTML = `
    ${pageHeader("Pixellot Software", "Pixellot version, install/agent config, and hardware compatibility.",
      `<button class="btn-outline btn-ol-blue" onclick="dataCache.system=null;dataCache['pixellot-config']=null;renderPixellotSoftware()">${svgIcon("refresh", 14)} Refresh</button>`)}

    <div class="card">
      ${sectionTitle("zap", "Version & Compatibility")}
      <div class="kv-grid kv-grid-wide">
        ${kvRow("App Version", pix.version)}
        ${kvRow("Image Version", pix.imageVersion)}
      </div>
      ${id.isNonVpuHost ? '<div class="info-chip mt-3">Not a VPU host</div>' : ""}
      ${_pixCompatBannerHtml(pix.compat)}
    </div>

    <div class="card">
      ${sectionTitle("server", "Install & Agent")}
      ${pc.error ? errorBox(pc.message) : `
        <div class="kv-grid">
          ${kvRow("Install Path", installPath)}
          ${kvRow("Dependencies", reg.dependencies || reg.Dependencies)}
          ${kvRowHtml("cameras.cfg", pc.cameraCfgExists ? badge("Present", "pass") : badge("Missing", "fail"))}
        </div>
      `}
    </div>

    ${pc.error ? "" : `
    <div class="card">
      ${sectionTitle("database", "Registry — HKLM\\SOFTWARE\\Pixellot")}
      <div class="kv-grid">${regRows}</div>
    </div>`}
  `;
}

// ── Camera Hardware ──────────────────────────────────────────
// Full per-camera CGI probe — device identity, firmware, network config,
// stream encoding, and image-sensor tuning — for every camera head detected
// on an active port. Sourced from /api/cameras (the same probe the Camera
// Connectivity lane runs), flattened across ports. Calibration status lives
// on the Calibrations tab; role/IP/MAC live-link state lives on Connectivity.
let _camHwHealing = false;  // one-shot guard: re-probe once when probe data is cold

function renderCameraHardware() {
  const d = cached("cameras");
  if (!d) {
    $page().innerHTML = sectionLoading("Camera Hardware");
    fetchSection("cameras").then(() => { if (currentPage === "camera-hardware") renderCameraHardware(); });
    return;
  }
  if (d.error) { $page().innerHTML = errorBox(d.message); return; }

  // Flatten detected cameras across all ports, carrying port context. A down
  // port has no live camera, so camerasDetected is already empty there.
  const entries = [];
  (d.ports || []).forEach((p) => {
    (p.camerasDetected || []).forEach((c) => entries.push({ cam: c, port: p }));
  });
  const anyCgi = entries.some((e) => e.cam.cgiConfirmed);

  const cards = entries.map((e) => _camHardwareCard(e.cam, e.port)).join("");
  const empty = `<div class="cam-no-detect">No cameras detected on any active port.</div>`;
  const noCgiNote = (entries.length && !anyCgi)
    ? `<div class="cam-connecting-note">${svgIcon("refresh", 12)} Probing camera heads (Admin CGI)… identity-only data shown until probes complete. Use Refresh to force a re-probe.</div>`
    : "";

  $page().innerHTML = `
    ${pageHeader("Camera Hardware",
      "Full CGI probe of every camera head on an active port — identity, firmware, network, stream, and sensor settings.",
      `<button class="btn-outline btn-ol-blue" onclick="_camHwRefresh()">${svgIcon("refresh", 14)} Refresh</button>`)}

    <div class="card">
      ${sectionTitle("camera", "Detected Cameras")}
      <p class="text-xs text-pulse-muted mb-3">Probed live from each camera head over the Admin CGI (<span class="font-mono">Admin:1234</span> · <span class="font-mono">param.cgi</span>) — the same probe the <strong>Camera Connectivity</strong> tab uses for identification. Cameras on a down port aren't probed.</p>
      ${noCgiNote}
      ${entries.length ? `<div class="cam-hw-grid">${cards}</div>` : empty}
    </div>
  `;

  // Cold-cache heal: the first /api/cameras paint can return before the CGI
  // probe cache is warm, so cameras arrive identity-only. Force one blocking
  // re-probe to fill in the hardware detail, guarded so it fires at most once
  // per cold state (a truly unreachable camera stays "No CGI", no loop).
  if (entries.length && !anyCgi && !_camHwHealing) {
    _camHwHealing = true;
    _camHwRefresh();
  } else if (anyCgi) {
    _camHwHealing = false;
  }
}

// One camera's full probe, laid out as a detail card. Reuses the same leaf
// formatters (_camDetailKv / _camStreamBlock / _fmtTvMode) the Connectivity
// lane used before this data moved here.
function _camHardwareCard(c, port) {
  var hasCgi = !!c.cgiConfirmed;
  var net = c.network || {};
  var sensor = c.sensor || {};
  var portLabel = port ? (port.portLabel || port.name) : null;

  var deviceRows =
    _camDetailKv("IP", c.ip) +
    _camDetailKv("MAC", c.cgiMac || c.mac) +
    _camDetailKv("Role", c.role) +
    _camDetailKv("Identity", c.identitySource);
  if (hasCgi) {
    deviceRows +=
      _camDetailKv("Model", c.model) +
      _camDetailKv("Model No.", c.modelNumber) +
      _camDetailKv("Serial", c.serialNumber) +
      _camDetailKv("Firmware", c.firmwareVersion) +
      _camDetailKv("TV Mode", _fmtTvMode(c.tvMode)) +
      _camDetailKv("Brand", c.brand) +
      _camDetailKv("Type", c.productType);
  }

  return '<div class="cam-detail-camera">' +
    '<div class="cam-detail-camera-header">' +
      svgIcon("camera", 14) + ' ' + esc(c.ip) +
      (c.modelNumber ? ' <span class="cam-model-label">' + esc(c.modelNumber) + '</span>' : '') +
      (portLabel ? ' <span class="cam-hw-port">' + esc(portLabel) + '</span>' : '') +
      (hasCgi ? ' <span class="cam-cgi-badge" title="Camera answered Pulse&#39;s admin probe (CGI)">CGI</span>' : ' <span class="cam-cgi-badge cam-cgi-none" title="Camera did not answer Pulse&#39;s admin probe (CGI) — it may be offline or unreachable">No CGI</span>') +
    '</div>' +

    // Device identity
    '<div class="cam-detail-group">' +
      '<div class="cam-detail-group-title">Device</div>' +
      deviceRows +
    '</div>' +

    // Network config (CGI only)
    (net.ip || net.subnet || net.gateway ? '<div class="cam-detail-group">' +
      '<div class="cam-detail-group-title">Network Config</div>' +
      _camDetailKv("IP Address", net.ip) +
      _camDetailKv("Subnet", net.subnet) +
      _camDetailKv("Gateway", net.gateway) +
      _camDetailKv("DHCP", net.dhcp) +
    '</div>' : '') +

    // Streams (CGI only)
    _camStreamBlock("Stream 0 — Primary", c.stream0) +
    _camStreamBlock("Stream 1 — Secondary", c.stream1) +

    // Image sensor (CGI only)
    (sensor.exposure || sensor.brightness ? '<div class="cam-detail-group">' +
      '<div class="cam-detail-group-title">Image Sensor</div>' +
      _camDetailKv("Exposure", sensor.exposure) +
      _camDetailKv("Brightness", sensor.brightness) +
      _camDetailKv("Contrast", sensor.contrast) +
      _camDetailKv("Saturation", sensor.colorLevel) +
      _camDetailKv("Max Gain", sensor.maxShutterGain) +
      _camDetailKv("Min Shutter", sensor.minShutterSpeed) +
    '</div>' : '') +
  '</div>';
}

// Refresh button + cold-cache heal: clears the backend CGI cache and blocks
// on a fresh probe so the hardware detail is current (mirrors the Camera
// Connectivity force-refresh).
function _camHwRefresh() {
  var btn = document.querySelector('[onclick*="_camHwRefresh"]');
  if (btn) { btn.disabled = true; btn.style.opacity = "0.5"; }
  api("/api/cameras?refresh=true").then(function(fresh) {
    if (fresh && !fresh.error) {
      dataCache.cameras = fresh;
      if (currentPage === "camera-hardware") renderCameraHardware();
    }
  }).finally(function() {
    var b = document.querySelector('[onclick*="_camHwRefresh"]');
    if (b) { b.disabled = false; b.style.opacity = ""; }
  });
}

// ── Calibrations ─────────────────────────────────────────────
// Main-camera multisport stitch + OCR / scoreboard (pipdesign) calibration
// status and advisories, from /api/pixellot-config.
function renderCalibrations() {
  const d = cached("pixellot-config");
  if (!d) {
    $page().innerHTML = sectionLoading("Camera Calibrations");
    fetchSection("pixellot-config").then(() => { if (currentPage === "calibrations") renderCalibrations(); });
    return;
  }
  if (d.error) { $page().innerHTML = errorBox(d.message); return; }
  const cal = d.calibration || {};
  const multi = cal.multisport || {};
  const ocr = cal.ocr || {};

  // Multisport sports with last-calibrated dates (kv-rows must live in a kv-grid).
  const sports = multi.sports || [];
  const sportRows = sports.map((s) => {
    const stale = (_pcDaysSince(s.lastCalibrated) ?? 0) > _PC_STALE_DAYS;
    const isPrimary = multi.primary && s.name && multi.primary.toLowerCase() === String(s.name).toLowerCase();
    return `<div class="kv-row">
      <span class="kv-label">${esc(s.name)}${isPrimary ? ` ${badge("primary", "muted")}` : ""}</span>
      <span class="kv-value">${_pcFmtDate(s.lastCalibrated)} ${stale ? badge("stale", "warn") : ""}</span>
    </div>`;
  }).join("");
  const sportsBlock = sports.length
    ? `<div class="kv-grid">${sportRows}</div>`
    : `<div class="info-chip">No sports calibrated — main camera multisport calibration is empty.</div>`;

  $page().innerHTML = `
    ${pageHeader("Camera Calibrations", "Main-camera multisport stitch and OCR / scoreboard calibration status.",
      `<button class="btn-outline btn-ol-blue" onclick="dataCache['pixellot-config']=null;renderCalibrations()">${svgIcon("refresh", 14)} Refresh</button>`)}

    <div class="card">
      ${sectionTitle("check", "Calibration")}
      <div class="flex flex-wrap gap-4">
        <div class="flex-1" style="min-width:260px">
          <div class="flex items-center gap-2 mb-2"><span class="font-semibold">Main camera — multisport</span>${multi.calibrated ? badge("Calibrated", "pass") : badge("Not calibrated", "warn")}</div>
          ${sportsBlock}
        </div>
        <div class="flex-1" style="min-width:260px">
          <div class="flex items-center gap-2 mb-2"><span class="font-semibold">OCR / scoreboard</span>${ocr.calibrated ? badge("Calibrated", "pass") : badge("Not calibrated", "warn")}</div>
          <div class="kv-grid">
            ${kvRowHtml("Last calibrated", ocr.lastCalibrated ? _pcFmtDate(ocr.lastCalibrated) : "—")}
            ${kvRowHtml("enhanced_pip.txt", ocr.hasEnhancedPip ? badge("present", "pass") : badge("missing", "warn"))}
            ${kvRowHtml("innerobjects.txt", ocr.hasInnerObjects ? badge("present", "pass") : badge("missing", "warn"))}
          </div>
        </div>
      </div>
    </div>
  `;
}

// ── Dashboard ────────────────────────────────────────────────

function _subsystemHealth(findings) {
  // Worst finding severity per category (2 = critical, 1 = warning), so a
  // subsystem with a critical lights red and one with only warnings lights
  // amber. Info findings are context, not faults — they never change a
  // subsystem's light. Each finding maps to exactly ONE subsystem — no
  // double-flagging.
  const sev = {};
  (findings || []).forEach((f) => {
    const s = (f.severity || "").toLowerCase();
    if (s === "info") return;
    const k = (f.category || "").toLowerCase();
    const rank = /^(critical|error)$/.test(s) ? 2 : 1;
    sev[k] = Math.max(sev[k] || 0, rank);
  });
  const worst = (...keys) => Math.max(0, ...keys.map((k) => sev[k] || 0));
  const lvl = (r) => (r === 2 ? "Critical" : r === 1 ? "Warning" : "OK");

  // Event Viewer doesn't generate dashboard findings of its own, so derive
  // its health from the cached event log: any recent Error-level entry
  // turns it amber. (Falls back to Healthy when events aren't loaded.)
  const evEntries = (cached("events") || {}).entries || [];
  const evErrorCount = evEntries.filter(
    (e) => (e.level || "").toLowerCase() === "error"
  ).length;

  // ids are nav page ids — updateNavHealth() lights the matching sidebar link.
  // Re-keyed for the 6-group IA: the old `system` panel split into hardware /
  // applications / environment, plus a Pixellot Software panel.
  return [
    { id: "hardware", label: "Hardware", icon: "cpu",
      health: lvl(worst("hardware", "performance")),
      desc: "CPU, memory, graphics, and storage." },
    { id: "applications", label: "Applications", icon: "copy",
      health: lvl(worst("software")),
      desc: "Installed software that can interfere with streaming." },
    { id: "environment", label: "Environment", icon: "globe",
      health: lvl(worst("system")),
      desc: "Windows OS, locale, uptime, users, and peripherals." },
    { id: "pixellot-software", label: "Pixellot Software", icon: "zap",
      health: lvl(worst("pixellot")),
      desc: "Pixellot version and hardware compatibility." },
    { id: "network", label: "Network", icon: "wifi",
      health: lvl(worst("network")),
      desc: "Internet, name lookups, firewall, and service ports." },
    { id: "cameras", label: "Camera Connectivity", icon: "camera",
      health: lvl(worst("camera")),
      desc: "Camera ports — link, speed, and camera detection." },
    { id: "services", label: "Service Status", icon: "server",
      health: lvl(worst("services")),
      desc: "Agent, encoder, watchdog service status." },
    { id: "disk-health", label: "Disks", icon: "hdd",
      health: lvl(worst("storage")),
      desc: "Free space, drive health (SMART), and disk events." },
    { id: "events", label: "Windows Events", icon: "triangle",
      health: evErrorCount > 0 ? "Warning" : "OK",
      desc: evErrorCount > 0
        ? `${evErrorCount} recent OS error${evErrorCount === 1 ? "" : "s"} logged.`
        : "Recent Windows errors from VPU components." },
  ];
}

function _findingPageFor(cat) {
  // Finding category → the tab that owns the fix. Updated for the 6-group IA:
  // System Overview split into hardware / applications / environment, and
  // pixellot findings land on the new Pixellot Software tab.
  const map = {
    network: "network",
    camera: "cameras",
    services: "services",
    storage: "disk-health",
    hardware: "hardware",
    performance: "hardware",
    system: "environment",        // timezone / uptime / OS
    pixellot: "pixellot-software",
    software: "applications",     // banned / concerning installed apps
  };
  return map[(cat || "").toLowerCase()] || "dashboard";
}

var _dashNicRefreshTimer = null;

function _renderNicRows(ports) {
  const rows = [];
  const count = Math.max(4, ports.length);
  // Assign camera numbers to non-OCR ports with detected cameras
  let camNum = 0;
  const roles = [];
  for (let i = 0; i < count; i++) {
    if (i < ports.length) {
      const p = ports[i];
      if (p.isOcr) roles.push("OCR");
      else if (p.isUp && (p.camerasDetected || []).length > 0) roles.push("Camera " + (++camNum));
      else roles.push(null);
    } else {
      roles.push(null);
    }
  }
  // Tooltips on each badge so the colored chips have plain-English meaning
  // for techs glancing at the dashboard — was previously no legend at all.
  const statusTip = {
    Linked: "Link up at the expected speed",
    Error:  "Link is up but degraded (e.g. 100 Mbps on a Gigabit port)",
    Down:   "No physical link detected on this port",
  };
  for (let i = 0; i < count; i++) {
    if (i < ports.length) {
      const p = ports[i];
      const speed = p.linkSpeedMbps
        ? p.linkSpeedMbps >= 1000 ? (p.linkSpeedMbps / 1000) + " Gbps" : p.linkSpeedMbps + " Mbps"
        : "—";
      let status, cls;
      if (!p.isUp) { status = "Down"; cls = "muted"; }
      else if (p.isDegraded) { status = "Error"; cls = "warn"; }
      else { status = "Linked"; cls = "pass"; }
      const role = roles[i];
      const roleTip = role === "OCR"
        ? "OCR (scoreboard overlay) camera port"
        : role
          ? "Pixellot camera detected on this port"
          : "";
      const roleBadge = role
        ? ` <span class="badge-ol badge-ol-info" title="${esc(roleTip)}">${esc(role)}</span>`
        : "";
      rows.push(`<div class="dash-nic-row">
        <span class="dash-nic-port">Port ${i + 1}</span>
        <span class="dash-nic-name">${esc(p.name)}</span>
        <span class="dash-nic-speed">${p.isUp ? esc(speed) : "—"}</span>
        <span class="dash-nic-badges"><span class="badge-ol badge-ol-${cls}" title="${esc(statusTip[status] || "")}">${esc(status)}</span>${roleBadge}</span>
      </div>`);
    } else {
      rows.push(`<div class="dash-nic-row">
        <span class="dash-nic-port">Port ${i + 1}</span>
        <span class="dash-nic-name" style="color:var(--c-dimmer)">Not detected</span>
        <span class="dash-nic-speed">—</span>
        <span class="dash-nic-badges"><span class="badge-ol badge-ol-muted" title="No NIC detected at this port index">—</span></span>
      </div>`);
    }
  }
  return rows.join("");
}

// System Disk gauge value = the C: (system) drive's OWN used%, read from the
// disk-health volume list. NOT perf.disk.usedPercent — Get-Performance.ps1
// computes that as an all-fixed-volumes aggregate, so a large near-empty D:
// drags it far below C:'s real value (e.g. shows 9% when C: is ~50% full).
// Falls back to the perf aggregate only until disk-health has been cached.
function _systemDiskPct(perf) {
  const vols = (cached("disk-health") || {}).logicalDisks || [];
  const sys = vols.find((d) => d.deviceID === "C:") || vols[0];
  if (sys && sys.usedPercent != null) return sys.usedPercent;
  return perf && perf.disk ? perf.disk.usedPercent : null;
}

function _renderVolumes(volumes) {
  if (!volumes.length) return '<div class="text-xs text-pulse-muted py-2">No storage data</div>';
  return volumes.map((d) => {
    const pct = d.usedPercent || 0;
    // Critical-only (matches the findings engine): red above 90%, no amber tier.
    const color = pct > 90 ? "var(--c-accent-red)" : "var(--c-accent-blue)";
    const role = d.deviceID === "C:" ? "System — OS & Pixellot"
               : d.deviceID === "D:" ? "Recordings — local game-video storage"
               : "Storage";
    return `<div class="dash-vol-row">
      <div class="dash-vol-top">
        <div class="dash-vol-id">
          <span class="font-semibold font-mono">${esc(d.deviceID)}</span>
          <span class="dash-vol-badge">${esc(role)}</span>
        </div>
        <span class="font-semibold" style="color:${color}">${pct}%</span>
      </div>
      <div class="dash-vol-bottom">
        <div class="dash-vol-bar"><div class="dash-vol-fill" style="width:${Math.min(pct, 100)}%;background:${color}"></div></div>
        <span class="dash-vol-free">${d.freeSpaceGB != null ? esc(String(d.freeSpaceGB)) : "—"} free of ${d.sizeGB != null ? esc(String(d.sizeGB)) + " GB" : "—"}</span>
      </div>
    </div>`;
  }).join("");
}

// ── Stream Readiness card ────────────────────────────────────
// One PASS / WARN / FAIL call on whether this VPU can stream tonight's game.
// The policy table + rollup live server-side (_compute_readiness in main.py);
// this just renders the verdict record that rides on dash.readiness.
var _RDY_META = {
  PASS: { word: "PASS", icon: "check", tone: "pass", tag: "Game-ready — no blockers, no risks." },
  WARN: { word: "WARNING", icon: "alert", tone: "warn", tag: "Will likely stream, but there are issues found that should be addressed to improve the system's reliability." },
  FAIL: { word: "FAIL", icon: "x",     tone: "fail", tag: "Don't expect a clean broadcast tonight — this needs pre-game attention." },
};

// Demo-only: flip the card through all three states live (e.g. in a meeting).
// Never set outside DEMO_MODE; the live verdict is used when it's null.
var _readinessDemoState = null;
function previewReadiness(state) {
  _readinessDemoState = (_readinessDemoState === state) ? null : state;
  renderDashboard();
}
function _demoVerdict(state) {
  var stamp = new Date().toISOString();
  var nicRisk = { code: "nic-slow", category: "Camera", title: "NIC Port 2 at 100 Mbps (expected 1 Gbps)", recommendation: "Camera streams on this port drop frames at reduced bandwidth. Check the cable (Cat5e+), reseat the connector, and confirm the switch port auto-negotiates." };
  if (state === "PASS") return { status: "PASS", policyVersion: "v1", timestamp: stamp, blockers: [], risks: [], info: [] };
  if (state === "WARN") return { status: "WARN", policyVersion: "v1", timestamp: stamp, blockers: [], info: [], risks: [
    nicRisk,
    { code: "disk-d-critical", category: "Storage", title: "Recording drive (D:) almost full", recommendation: "D: is 93% full. The post-event recording (VOD) is written to D: — if it fills during the game the recording may not save. Free space on D:." },
  ] };
  return { status: "FAIL", policyVersion: "v1", timestamp: stamp, info: [], risks: [nicRisk], blockers: [
    { code: "stream-blocked", category: "Network", title: "Streaming is blocked — VPU can't broadcast", recommendation: "The venue's network is blocking every streaming path (UDP/2088, UDP/443, and the TCP/1935 fallback), so the game can't broadcast until venue IT opens at least one." },
  ] };
}

function readinessCard(verdict, freshness) {
  var isDemo = (typeof window !== "undefined" && window.__PULSE_DEMO_MODE);
  if (isDemo && _readinessDemoState) verdict = _demoVerdict(_readinessDemoState);
  if (!verdict || !verdict.status) return "";
  var meta = _RDY_META[verdict.status] || _RDY_META.WARN;
  var blockers = verdict.blockers || [];
  var risks = verdict.risks || [];
  var asOf = verdict.timestamp ? new Date(verdict.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "";

  var demoBar = isDemo
    ? '<div class="rdy-demo-bar"><span class="rdy-demo-label">Demo preview</span>'
      + ["PASS", "WARN", "FAIL"].map(function(s) {
          var active = (_readinessDemoState === s) ? " rdy-demo-chip-active" : "";
          return '<button class="rdy-demo-chip rdy-demo-chip-' + s.toLowerCase() + active + '" onclick="previewReadiness(\'' + s + '\')">' + s + '</button>';
        }).join("")
      + (_readinessDemoState ? '<button class="rdy-demo-chip rdy-demo-reset" onclick="previewReadiness(null)">live</button>' : '')
      + '</div>'
    : "";

  return '<div class="card rdy-card rdy-card-' + meta.tone + '">'
    + '<div class="rdy-main">'
    +   '<div class="rdy-badge rdy-badge-' + meta.tone + '">' + svgIcon(meta.icon, 28) + '<span class="rdy-badge-word">' + meta.word + '</span></div>'
    +   '<div class="rdy-headline">'
    +     '<div class="rdy-title-row"><h3 class="rdy-title">Stream Readiness</h3>' + (asOf ? '<span class="rdy-asof">as of ' + esc(asOf) + '</span>' : '') + '</div>'
    +     '<p class="rdy-tag">' + esc(meta.tag) + '</p>'
    +     (freshness ? '<p class="rdy-fresh">' + svgIcon("check", 12) + ' ' + esc(freshness) + '</p>' : '')
    +   '</div>'
    + '</div>'
    + '<div class="rdy-foot">'
    +   '<span>' + blockers.length + ' blocker' + (blockers.length === 1 ? '' : 's') + ' · ' + risks.length + ' risk' + (risks.length === 1 ? '' : 's') + '</span>'
    +   '<span class="rdy-policy">policy ' + esc(verdict.policyVersion || "v1") + '</span>'
    + '</div>'
    + demoBar
    + '</div>';
}

function renderDashboard() {
  const dash = cached("dashboard");
  if (!dash) { $page().innerHTML = sectionLoading("Dashboard"); fetchSection("dashboard"); return; }
  if (dash.error) { $page().innerHTML = errorBox(dash.message); return; }

  // Pull from all cached data sources
  const net = cached("network") || {};
  const cam = cached("cameras") || {};
  const diskData = cached("disk-health") || {};
  const svcData = cached("services") || {};
  const sysData = cached("system") || {};

  const id = dash.identity || {};
  const perf = dash.performance || {};
  const findings = dash.findings || [];
  const svcs = (dash.services || svcData)?.services || [];
  const hostname = id.hostname || "VPU";
  const vpuName = id.vpuName;

  const cpu = perf.cpu?.usagePercent;
  const mem = perf.memory?.usedPercent;
  const disk = _systemDiskPct(perf);
  const temp = perf.temperature?.celsius;

  const totalFindings = findings.length;

  // Findings are shown in a single consolidated list, grouped by severity
  // (critical first, then warning, then info) — the natural triage order.
  // The sort is stable, so each group keeps its original ordering.
  // Cap at 10 to keep the panel from sprawling; surface a "+N more" hint
  // when there are more.
  const _SEV_RANK = { critical: 0, error: 0, warning: 1, warn: 1, info: 2 };
  const sortedFindings = findings
    .map((f, i) => [f, i])  // decorate with index for a stable sort
    .sort((a, b) => {
      const ra = _SEV_RANK[(a[0].severity || "").toLowerCase()] ?? 3;
      const rb = _SEV_RANK[(b[0].severity || "").toLowerCase()] ?? 3;
      return ra !== rb ? ra - rb : a[1] - b[1];
    })
    .map((pair) => pair[0]);
  const _MAX_FINDINGS_INLINE = 10;
  const visibleFindings = sortedFindings.slice(0, _MAX_FINDINGS_INLINE);
  const overflowCount = Math.max(0, sortedFindings.length - _MAX_FINDINGS_INLINE);
  const subsystems = _subsystemHealth(findings);
  const now = new Date();
  const timeStr = now.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  const baselineStr = subsystems.length + " panel" + (subsystems.length === 1 ? "" : "s") + " checked";

  // Network config — prefer dashboard-embedded data, fall back to full network cache
  const netCfg = dash.networkConfig || net.config || {};
  const uplinkName = netCfg.uplinkAdapter?.interfaceAlias || "—";
  // On a Pixellot VPU the uplink/gateway-bearing NIC should be the motherboard's
  // onboard port (cameras live on the dedicated multiport NIC card with
  // link-local IPs and no gateway). The backend tags adapter roles by PCI bus,
  // so we only assert "Motherboard Network Port" when the uplink really is the
  // onboard port — if the internet has been plugged into a camera-NIC port, say
  // so instead of mislabeling it (the matching critical finding has the fix).
  const _uplinkAdapter = (netCfg.adapters || []).find(
    (a) => a.name === uplinkName || a.interfaceAlias === uplinkName);
  const _uplinkRole = netCfg.uplinkRole || (_uplinkAdapter && _uplinkAdapter.role);
  const _onVpu = !id.isNonVpuHost && uplinkName !== "—";
  let uplinkDisplay;
  if (_onVpu && _uplinkRole === "camera")
    uplinkDisplay = `${esc(uplinkName)} <span class="dash-net-sub">(camera-NIC port — should be the motherboard port)</span>`;
  else if (_onVpu)
    uplinkDisplay = `Motherboard Network Port <span class="dash-net-sub">(${esc(uplinkName)})</span>`;
  else
    uplinkDisplay = esc(uplinkName);
  const ipConfigs = netCfg.ipConfig || netCfg.ipConfigurations || [];
  const uplinkIp = ipConfigs.find((ip) => ip.interfaceAlias === uplinkName);
  const ipAddr = _first(uplinkIp?.ipv4Address) || "—";
  const gw = _first(uplinkIp?.ipv4DefaultGateway) || netCfg.uplinkAdapter?.gateway || "—";
  const dnsRaw = uplinkIp?.dnsServers;
  const dns = dnsRaw ? String(dnsRaw).split(",").map(function(s) { return s.trim(); }).filter(Boolean).join(", ") : "—";
  const ntpSrv = netCfg.ntpSource || "—";
  const internetOk = netCfg.internetReachable;
  const internetFetching = fetchingKeys.has("network");
  const internetLabel = internetOk === true ? "Connected" : internetOk === false ? "Offline" : internetFetching ? "Checking" : "—";
  const internetColor = internetOk === true ? "var(--c-accent-green)" : internetOk === false ? "var(--c-accent-red)" : "var(--c-muted)";

  // Other data
  const nicPorts = cam.ports || [];
  const volumes = diskData.logicalDisks || [];
  const cpuInfo = sysData.hardware?.processors?.[0];
  const cpuName = (cpuInfo?.name || "")
    .replace(/\(R\)/gi, "").replace(/\(TM\)/gi, "")
    .replace(/\s+CPU\s*/i, " ").replace(/\s{2,}/g, " ").trim();
  const memTotalMB = perf.memory?.totalMB;
  const memUsedMB = perf.memory?.usedMB;
  const memCaption = memTotalMB
    ? (memUsedMB != null
        ? (memUsedMB / 1024).toFixed(1) + " / " + (memTotalMB / 1024).toFixed(0) + " GB"
        : (memTotalMB / 1024).toFixed(0) + " GB")
    : "";
  const sysDisk = volumes.find((d) => d.deviceID === "C:") || volumes[0];
  const diskCaption = sysDisk && sysDisk.freeSpaceGB != null && sysDisk.sizeGB != null ? `${sysDisk.freeSpaceGB} GB free of ${sysDisk.sizeGB} GB` : "";

  $page().innerHTML = `
    <!-- Header -->
    <div class="dash-header">
      <div>
        <div class="dash-title-row">
          <h2 class="text-2xl font-bold text-white">Dashboard</h2>
        </div>
        ${vpuName ? `<p class="text-sm text-pulse-muted">${esc(vpuName)}</p>` : ""}
      </div>
    </div>

    <!-- Stream Readiness — lead the triage page with "are we game-ready?" -->
    ${readinessCard(dash.readiness, baselineStr)}

    ${(dash.sourceErrors && dash.sourceErrors.length) ? `
    <!-- Partial-failure notice — some diagnostic scripts didn't complete -->
    <div class="dash-incomplete-bar">
      <span class="dash-incomplete-icon">${svgIcon("alert", 16)}</span>
      <span class="dash-incomplete-text">
        Some checks couldn't complete: <strong>${esc(dash.sourceErrors.join(", "))}</strong>.
        The affected cards may be blank or out of date.
      </span>
      <button class="btn-outline btn-ol-amber dash-incomplete-retry" onclick="refreshSection('dashboard')">
        ${svgIcon("refresh", 13)} Retry
      </button>
    </div>` : ""}

    ${totalFindings > 0 ? `
    <!-- Findings — lightweight list of the active warnings/criticals -->
    <div class="card dash-findings-card">
      <div class="flex justify-between items-center mb-2">
        <div class="dash-card-hdr mb-0">
          <span class="dash-hdr-icon">${svgIcon("clipboard-list", 16)}</span>
          <h3 class="card-label mb-0">FINDINGS</h3>
        </div>
        <span class="cc-findings-count">${totalFindings} issue${totalFindings === 1 ? "" : "s"}</span>
      </div>
      <div class="cc-findings-list">
        ${visibleFindings.map((f, i) => {
          const prev = visibleFindings[i - 1];
          const groupBreak = i > 0 && prev.severity !== f.severity ? `<div class="cc-findings-divider"></div>` : "";
          const fp = _findingPageFor(f.category);
          const encTitle = encodeURIComponent(f.title || "");
          return groupBreak + `
        <a class="finding-item" href="#${esc(fp)}" onclick="event.preventDefault();findingJump('${esc(fp)}','${encTitle}')" title="Opens the ${esc(f.category)} tab and highlights this issue">
          <span class="finding-dot finding-dot-${esc(f.severity)}"></span>
          <span class="finding-cat finding-cat-${esc(f.severity)}">[${esc((f.severity || "").toUpperCase())}]</span>
          <span class="finding-title">${esc(f.title)}</span>
          <span class="finding-arrow">${svgIcon("chevron", 14)}</span>
        </a>`;
        }).join("")}
        ${overflowCount > 0 ? `<div class="cc-findings-overflow">+${overflowCount} more — visit the relevant tab for the full list</div>` : ""}
      </div>
    </div>` : ""}

    ${id.isNonVpuHost ? `
    <!-- Non-VPU Host Banner -->
    <div class="dash-info-banner">
      <span class="dash-banner-icon">${svgIcon("info", 20)}</span>
      <div>
        <div class="font-semibold text-sm">Pixellot software not detected</div>
        <div class="text-xs text-pulse-muted mt-1">This host doesn't appear to be a Pixellot VPU — system metrics are still live, but expect blank values for VPU identity, services, and the diagnostic report.</div>
      </div>
    </div>` : ""}

    <!-- VPU Identity + Pixellot Software -->
    <div class="dash-2col">
      <div class="card">
        <div class="dash-card-hdr">
          <span class="dash-hdr-icon">${svgIcon("id-card", 16)}</span>
          <h3 class="card-label mb-0">VPU IDENTITY</h3>
        </div>
        ${vpuName ? `<div class="text-sm text-pulse-muted mb-3">${esc(vpuName)}</div>` : ""}
        <div class="dash-kv">
          <span class="dash-kv-l">Model</span><span class="dash-kv-v">${esc(id.model || "—")}</span>
          <span class="dash-kv-l">Hostname</span><span class="dash-kv-v">${esc(hostname)}</span>
          <span class="dash-kv-l">Manufacturer</span><span class="dash-kv-v">${esc(id.manufacturer || "—")}</span>
          <span class="dash-kv-l">Serial</span><span class="dash-kv-v">${esc(id.serialNumber || "—")}</span>
          ${id.venueId ? `<span class="dash-kv-l">Venue ID</span><span class="dash-kv-v font-mono">${esc(id.venueId)}</span>` : ""}
        </div>
      </div>
      <div class="card">
        <div class="dash-card-hdr">
          <span class="dash-hdr-icon">${svgIcon("package", 16)}</span>
          <h3 class="card-label mb-0">PIXELLOT SOFTWARE</h3>
        </div>
        <div class="text-lg font-bold text-white">${esc(id.pixellotVersion || "—")}</div>
        <div class="text-xs text-pulse-muted mb-3">App Version</div>
        <div class="dash-kv">
          <span class="dash-kv-l">Image Version</span><span class="dash-kv-v">${esc(id.imageVersion || "—")}</span>
          <span class="dash-kv-l">OS</span><span class="dash-kv-v">${esc(id.os || "—")}</span>
        </div>
      </div>
    </div>

    <!-- System Status Gauges -->
    <div class="card dash-gauges-card">
      <div class="dash-card-hdr-row">
        <div class="dash-card-hdr mb-0">
          <span class="dash-hdr-icon">${svgIcon("activity", 16)}</span>
          <h3 class="card-label mb-0">SYSTEM STATUS</h3>
        </div>
        <span id="live-indicator" class="live-indicator">${_liveIndicatorHtml()}</span>
      </div>
      <div class="dash-gauges-row" id="dash-gauges">
        <div class="dash-gauge-col" data-gauge="cpu">
          ${gauge("CPU", cpu != null ? Math.round(cpu) : null, "%")}
          ${cpuInfo ? `<div class="dash-gauge-sub">${esc(cpuName)}</div><div class="dash-gauge-sub">${cpuInfo.numberOfLogicalProcessors || ""} threads</div>` : ""}
        </div>
        <div class="dash-gauge-col" data-gauge="mem">
          ${gauge("Memory", mem != null ? Math.round(mem) : null, "%")}
          <div class="dash-gauge-sub">${esc(memCaption)}</div>
        </div>
        <div class="dash-gauge-col" data-gauge="disk">
          ${gauge("System Disk (C:)", disk != null ? Math.round(disk) : null, "%")}
          <div class="dash-gauge-sub">${esc(diskCaption)}</div>
        </div>
        <div class="dash-gauge-col" data-gauge="temp">
          ${gauge("Temperature", temp != null ? Math.round(temp) : null, "°C", "var(--c-accent-blue)", { max: 100, warn: 65, crit: 85 })}
        </div>
        <div class="dash-gauge-col dash-gauge-col-center">
          <div class="dash-icon-tile">
            <span class="text-blue-400">${svgIcon("clock", 26)}</span>
            <span class="dash-tile-val">${esc(id.uptime || "—")}</span>
          </div>
          <span class="text-xs text-pulse-muted font-medium">Uptime</span>
        </div>
        <div class="dash-gauge-col dash-gauge-col-center">
          <div class="dash-icon-tile">
            <span style="color:${internetColor}">${svgIcon("globe", 26)}</span>
            <span class="dash-tile-val" style="color:${internetColor}">${esc(internetLabel)}</span>
          </div>
          <span class="text-xs text-pulse-muted font-medium">Internet</span>
        </div>
      </div>
    </div>

    <!-- NIC Ports + Network -->
    <div class="dash-2col">
      <div class="card">
        <div class="dash-card-hdr">
          <span class="dash-hdr-icon">${svgIcon("link", 16)}</span>
          <h3 class="card-label mb-0">NETWORK INTERFACE CARD (NIC) CONNECTIONS</h3>
        </div>
        <div class="dash-nic-table" id="dash-nic-table">${_renderNicRows(nicPorts)}</div>
      </div>
      <div class="card">
        <div class="dash-card-hdr">
          <span class="dash-hdr-icon">${svgIcon("wifi", 16)}</span>
          <h3 class="card-label mb-0">NETWORK</h3>
        </div>
        <div class="dash-net-kv">
          <div class="dash-net-row"><span></span><span class="dash-kv-l">Uplink Adapter</span><span class="dash-kv-v">${uplinkDisplay}</span></div>
          <div class="dash-net-row"><span class="dash-net-dot" style="background:${ipAddr !== "—" ? "var(--c-accent-green)" : "var(--c-dimmer)"}"></span><span class="dash-kv-l">IP Address</span><span class="dash-kv-v font-mono">${esc(ipAddr)}</span></div>
          <div class="dash-net-row"><span class="dash-net-dot" style="background:${gw !== "—" ? "var(--c-accent-green)" : "var(--c-dimmer)"}"></span><span class="dash-kv-l">Gateway</span><span class="dash-kv-v font-mono">${esc(gw)}</span></div>
          <div class="dash-net-row"><span class="dash-net-dot" style="background:${dns !== "—" ? "var(--c-accent-green)" : "var(--c-dimmer)"}"></span><span class="dash-kv-l">DNS Servers</span><span class="dash-kv-v font-mono">${esc(dns)}</span></div>
          <div class="dash-net-row"><span class="dash-net-dot" style="background:${ntpSrv !== "—" ? "var(--c-accent-green)" : "var(--c-dimmer)"}"></span><span class="dash-kv-l">NTP Server</span><span class="dash-kv-v font-mono">${esc(ntpSrv)}</span></div>
        </div>
      </div>
    </div>

    <!-- Storage + Pixellot Services -->
    <div class="dash-2col">
      <div class="card">
        <div class="dash-card-hdr">
          <span class="dash-hdr-icon">${svgIcon("database", 16)}</span>
          <h3 class="card-label mb-0">STORAGE</h3>
        </div>
        ${_renderVolumes(volumes)}
      </div>
      <div class="card">
        <div class="dash-card-hdr">
          <span class="dash-hdr-icon">${svgIcon("server", 16)}</span>
          <h3 class="card-label mb-0">PIXELLOT SERVICES</h3>
        </div>
        <div class="dash-svc-list">
          ${svcs.map((s) => `
            <div class="dash-svc-row">
              <span class="dash-svc-name">${esc(s.displayName || s.name)}</span>
              ${statusBadge(s.status)}
            </div>`).join("")}
          ${!svcs.length ? '<div class="text-xs text-pulse-muted py-2">No services data</div>' : ""}
        </div>
      </div>
    </div>
  `;

  // ── Live NIC refresh: poll /api/cameras every 3s and update NIC table ──
  // Uses an in-flight flag to skip ticks while a previous request is pending,
  // so slow PowerShell on the VPU can't pile up overlapping requests.
  if (_dashNicRefreshTimer) clearInterval(_dashNicRefreshTimer);
  var _nicPollBusy = false;
  _dashNicRefreshTimer = setInterval(function() {
    if (currentPage !== "dashboard") { clearInterval(_dashNicRefreshTimer); _dashNicRefreshTimer = null; return; }
    if (_nicPollBusy) return;
    _nicPollBusy = true;
    api("/api/cameras").then(function(fresh) {
      if (!fresh || fresh.error || currentPage !== "dashboard") return;
      dataCache.cameras = fresh;
      var el = document.getElementById("dash-nic-table");
      if (el) el.innerHTML = _renderNicRows(fresh.ports || []);
    }).catch(function() { /* network blip — skip this tick */ })
      .then(function() { _nicPollBusy = false; });
  }, 3000);
}

// ── Shared Page Helpers ─────────────────────────────────────

function pageHeader(title, subtitle, actionsHtml) {
  return `<div class="page-header">
    <div>
      <h2 class="page-title">${esc(title)}</h2>
      ${subtitle ? `<p class="page-subtitle">${esc(subtitle)}</p>` : ""}
    </div>
    <div class="page-actions">${actionsHtml || ""}</div>
  </div>`;
}

function sectionTitle(icon, text) {
  return `<div class="section-hdr">
    <span class="section-hdr-icon">${svgIcon(icon, 16)}</span>
    <h3 class="section-hdr-text">${esc(text)}</h3>
  </div>`;
}

function kvRow(label, value) {
  return `<div class="kv-row"><span class="kv-label">${esc(label)}</span><span class="kv-value">${value != null ? esc(String(value)) : "—"}</span></div>`;
}

function kvRowHtml(label, html) {
  return `<div class="kv-row"><span class="kv-label">${esc(label)}</span><span class="kv-value">${html}</span></div>`;
}

function severityChip(sev, text) {
  const s = (sev || "").toLowerCase();
  // muted/info/none → neutral grey, so "no data" states don't masquerade as
  // healthy green. Everything unrecognised still falls through to ok (green) —
  // unchanged for existing callers.
  const cls =
    s === "critical" || s === "error" ? "sev-chip-crit" :
    s === "warning" ? "sev-chip-warn" :
    s === "muted" || s === "info" || s === "none" || s === "unknown" ? "sev-chip-muted" :
    "sev-chip-ok";
  return `<span class="sev-chip ${cls}">${esc(text || sev)}</span>`;
}

function _debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

// ── System Overview ──────────────────────────────────────────

// ── System Information tabs (split from the old System Overview) ───
// Hardware, Applications, and Environment — plus Pixellot Software under
// PIXELLOT CONFIGURATION — all read the shared `/api/system` payload (cached
// under the "system" key), so one fetch feeds every tab. The page id no longer
// matches the cache key, so each renderer kicks off the fetch and re-renders
// itself when the data lands.

// Pixellot version + GPU/OS compatibility banner. Lives on the Pixellot
// Software tab; pulled from /api/system identity.pixellot.compat.
function _pixCompatBannerHtml(c) {
  if (!c || c.status === "skip") return "";
  let cls = "sys-lifecycle-ok";
  let title = "";
  let detail = "";
  if (c.status === "ok") {
    cls = "sys-lifecycle-ok";
    title = "Version compatible with hardware";
    detail = `Pixellot ${esc(c.installedVersion)} is supported on this GPU${c.maxVersion ? ` (up to ${esc(c.maxVersion)})` : " — no version limit"}.`;
  } else if (c.status === "over") {
    cls = "sys-lifecycle-crit";
    title = "Version exceeds hardware compatibility cap";
    detail = `Installed ${esc(c.installedVersion)} is newer than ${esc(c.maxVersion)} (max for ${esc(c.architecture)}). Downgrade to stay supported.`;
  } else if (c.status === "no-gpu") {
    cls = "sys-lifecycle-crit";
    title = "No NVIDIA GPU detected";
    detail = "Pixellot requires NVIDIA hardware for encoding.";
  } else if (c.status === "anomaly") {
    cls = "sys-lifecycle-crit";
    title = "Unexpected GPU architecture";
    detail = `${esc(c.architecture)} is not a known Pixellot deployment — escalate to support.`;
  }
  return `<div class="sys-lifecycle ${cls} mt-3">
    ${svgIcon(cls === "sys-lifecycle-ok" ? "check" : "alert", 14)}
    <div>
      <div class="font-semibold">${esc(title)}</div>
      <div class="text-xs mt-1">${detail}</div>
    </div>
  </div>`;
}

// Windows edition lifecycle (end-of-support) banner. Lives on the Environment
// tab; pulled from /api/system identity.operatingSystem.lifecycle.
function _osLifecycleBannerHtml(lc) {
  if (!lc) return "";
  // Urgency keys on the date security updates actually STOP: the IoT
  // end-of-servicing date when the build has one (LTSC 2021), else the
  // headline end-of-support date. The headline date passing with servicing
  // still running is expected — the banner stays calm and says so.
  const hasServicing = !!lc.endOfServicingDate;
  const days = hasServicing && lc.daysToServicingEnd != null ? lc.daysToServicingEnd : lc.daysToEos;
  const eolDate = hasServicing ? lc.endOfServicingDate : lc.eosDate;
  const word = hasServicing ? "End-of-servicing" : "End-of-support";
  let cls = "sys-lifecycle-ok";
  let label = "";
  if (days == null) {
    label = `${word}: ${eolDate}`;
  } else if (days < 0) {
    cls = "sys-lifecycle-crit";
    label = `${word} reached on ${eolDate} (${Math.abs(days)} days ago)`;
  } else if (days < 90) {
    cls = "sys-lifecycle-crit";
    label = `${word} in ${days} days (${eolDate})`;
  } else if (days < 365) {
    cls = "sys-lifecycle-warn";
    const months = Math.floor(days / 30);
    label = `${word} in ~${months} months (${eolDate})`;
  } else {
    const years = Math.floor(days / 365);
    label = `${word}: ${eolDate} (${years}+ year${years === 1 ? "" : "s"} away)`;
  }
  // Note the (earlier) mainstream date alongside — with reassurance once
  // it's inside a year, so nobody mistakes it for the update cutoff.
  let mainstream = "";
  if (hasServicing) {
    const mDays = lc.daysToEos;
    mainstream = ` &middot; Mainstream support ${mDays != null && mDays < 0 ? "ended" : "ends"} ${esc(lc.eosDate)}`;
    if (mDays != null && mDays < 365) mainstream += " — OK, security updates continue";
  }
  return `<div class="sys-lifecycle ${cls} mt-3">
    ${svgIcon(cls === "sys-lifecycle-ok" ? "info" : "alert", 14)}
    <div>
      <div class="font-semibold">${esc(lc.ltscRelease)}</div>
      <div class="text-xs mt-1">${esc(label)}${mainstream}</div>
    </div>
  </div>`;
}

// ── Hardware ─────────────────────────────────────────────────
function renderHardware() {
  const data = cached("system");
  if (!data) {
    $page().innerHTML = sectionLoading("Hardware");
    fetchSection("system").then(() => { if (currentPage === "hardware") renderHardware(); });
    return;
  }
  if (data.identity?.error && data.hardware?.error) {
    $page().innerHTML = errorBox(data.identity?.message || data.hardware?.message);
    return;
  }

  const id = data.identity || {};
  const hw = data.hardware || {};
  const cs = id.computerSystem || {};
  const bios = id.bios || {};
  const procs = hw.processors || [];
  const memory = hw.memory || [];
  const gpus = hw.gpus || [];
  const drives = hw.diskDrives || [];

  $page().innerHTML = `
    ${pageHeader("Hardware", "CPU, memory, graphics, storage, and motherboard identity.",
      `<button class="btn-outline btn-ol-blue" onclick="dataCache.system=null;renderHardware()">
        ${svgIcon("refresh", 14)} Refresh
      </button>`
    )}

    <!-- VPU Identity -->
    <div class="card">
      ${sectionTitle("cpu", "VPU Identity")}
      <div class="kv-grid kv-grid-wide">
        ${kvRow("Hostname", cs.name)}
        ${kvRow("Manufacturer", cs.manufacturer)}
        ${kvRow("Model", cs.model)}
        ${kvRow("Serial Number", bios.serialNumber)}
      </div>
    </div>

    <!-- Processor + Memory -->
    <div class="dash-2col">
      <div class="card">
        ${sectionTitle("cpu", "Processor")}
        ${procs.length ? procs.map(p => `
          <div class="kv-grid">
            ${kvRow("Name", p.name)}
            ${kvRow("Cores", p.numberOfCores)}
            ${kvRow("Logical Processors", p.numberOfLogicalProcessors)}
            ${kvRow("Max Clock", p.maxClockSpeedMHz ? p.maxClockSpeedMHz + " MHz" : null)}
          </div>
        `).join("") : '<p class="text-pulse-muted text-sm">No processor data</p>'}
      </div>
      <div class="card">
        ${sectionTitle("server", "Memory")}
        ${memory.length ? `
          <table class="data-table"><thead><tr>
            <th>Capacity</th><th>Speed</th><th>Type</th><th>Slot</th>
          </tr></thead><tbody>
          ${memory.map(m => `<tr>
            <td>${m.capacityGB != null ? esc(String(m.capacityGB)) + " GB" : "—"}</td>
            <td>${m.speedMHz ? esc(String(m.speedMHz)) + " MHz" : "—"}</td>
            <td>${esc(m.memoryType)}</td>
            <td>${esc(m.deviceLocator)}</td>
          </tr>`).join("")}
          </tbody></table>
          ${(() => {
            const totalGb = memory.reduce((s, m) => s + (Number(m.capacityGB) || 0), 0);
            if (totalGb <= 0) return "";
            const formatted = Number.isInteger(totalGb) ? totalGb : totalGb.toFixed(2);
            if (totalGb < 32) {
              return `<div class="sys-mem-warn mt-3">
                ${svgIcon("alert", 14)}
                <span><strong>${esc(String(formatted))} GB installed</strong> — Pixellot VPUs require 32 GB. Encoder workloads may stall or drop frames.</span>
              </div>`;
            }
            return `<div class="text-xs text-pulse-muted mt-2">Total: ${esc(String(formatted))} GB</div>`;
          })()}
        ` : '<p class="text-pulse-muted text-sm">No memory data</p>'}
      </div>
    </div>

    <!-- Graphics + Storage -->
    <div class="dash-2col">
      <div class="card">
        ${sectionTitle("monitor", "Graphics")}
        ${gpus.length ? gpus.map(g => {
          // Dedicated GPU (NVIDIA/AMD with VRAM) gets a green chip; Intel iGPU
          // and others get a muted chip. Pixellot VPUs need at least one dedicated.
          const vendor = g.vendor || (g.adapterCompatibility ? g.adapterCompatibility : "GPU");
          const chipCls = g.isDedicated ? "gpu-vendor-dedicated" : "gpu-vendor-igpu";
          return `<div class="sub-card mb-2">
            <div class="flex items-center justify-between">
              <div class="text-sm font-semibold text-white">${esc(g.name)}</div>
              <span class="gpu-vendor-chip ${chipCls}">${esc(vendor)} · ${g.isDedicated ? "Dedicated" : "Integrated"}</span>
            </div>
            <div class="text-xs text-pulse-muted mt-1">RAM: ${g.adapterRAMMB ? esc(String(g.adapterRAMMB)) + " MB" : "N/A"} · Driver: ${esc(g.driverVersion)}</div>
          </div>`;
        }).join("") : '<p class="text-pulse-muted text-sm">No GPU data</p>'}
      </div>
      <div class="card">
        ${sectionTitle("hdd", "Storage")}
        ${drives.length ? `
          <table class="data-table"><thead><tr>
            <th>Model</th><th>Size</th><th>Interface</th><th>Serial</th>
          </tr></thead><tbody>
          ${drives.map(d => `<tr>
            <td>${esc(d.model)}</td>
            <td>${d.sizeGB != null ? esc(String(d.sizeGB)) + " GB" : "—"}</td>
            <td>${esc(d.interfaceType)}</td>
            <td class="font-mono text-xs">${esc(d.serialNumber)}</td>
          </tr>`).join("")}
          </tbody></table>
        ` : '<p class="text-pulse-muted text-sm">No drive data</p>'}
      </div>
    </div>

  `;
}

// ── Applications ─────────────────────────────────────────────
function renderApplications() {
  const data = cached("system");
  if (!data) {
    $page().innerHTML = sectionLoading("Applications");
    fetchSection("system").then(() => { if (currentPage === "applications") renderApplications(); });
    return;
  }
  const sw = data.software || {};
  if (sw.error) { $page().innerHTML = errorBox(sw.message); return; }
  const swList = sw.software || [];

  $page().innerHTML = `
    ${pageHeader("Applications", "Installed software, with anything that can interfere with streaming flagged.",
      `<button class="btn-outline btn-ol-blue" onclick="dataCache.system=null;renderApplications()">
        ${svgIcon("refresh", 14)} Refresh
      </button>`
    )}

    <div class="card">
      ${sectionTitle("copy", "Installed Software (" + swList.length + ")")}
      ${(() => {
        // Group concerning entries by severity for the summary banner.
        const flagged = swList.filter(s => s.concern);
        if (!flagged.length) return "";
        const critical = flagged.filter(s => s.concern.severity === "critical");
        const warning  = flagged.filter(s => s.concern.severity === "warning");
        const parts = [];
        if (critical.length) parts.push(`<span class="sw-flag-count sw-flag-critical">${critical.length} critical</span>`);
        if (warning.length)  parts.push(`<span class="sw-flag-count sw-flag-warning">${warning.length} warning</span>`);
        return `<div class="sw-concern-banner">
          ${svgIcon("alert", 14)}
          <span><strong>${flagged.length} concerning entr${flagged.length === 1 ? "y" : "ies"}</strong> ${parts.join(" · ")} — see flagged rows below.</span>
        </div>`;
      })()}
      ${swList.length ? `
        <input type="text" id="sw-filter" placeholder="Filter software..." class="sw-filter-input"/>
        <div class="sw-table-wrap">
          ${(() => {
            const hasConcerns = swList.some(s => s.concern);
            // Drop the Concern column entirely when nothing is flagged —
            // saves a wasted column of dashes on a healthy box.
            const sevRank = { critical: 0, warning: 1 };
            const sorted = [...swList].sort((a, b) => {
              const ra = a.concern ? sevRank[a.concern.severity] ?? 9 : 99;
              const rb = b.concern ? sevRank[b.concern.severity] ?? 9 : 99;
              return ra - rb;
            });
            const rows = sorted.map(s => {
              const c = s.concern;
              const rowCls = c ? ` class="sw-row-${esc(c.severity)}"` : "";
              const concernCell = hasConcerns ? `<td>${c
                ? `<span class="sw-concern-badge sw-concern-${esc(c.severity)}" title="${esc(c.reason)}">${esc(c.shortLabel || c.label)}</span>`
                : `<span class="text-pulse-muted text-xs">—</span>`}</td>` : "";
              return `<tr${rowCls}>
                <td>${esc(s.displayName)}</td>
                <td class="font-mono text-xs">${esc(s.displayVersion)}</td>
                <td class="text-pulse-muted">${esc(s.publisher)}</td>
                ${concernCell}
              </tr>`;
            }).join("");
            return `<table class="data-table" id="sw-table"><thead><tr>
              <th>Name</th><th>Version</th><th>Publisher</th>${hasConcerns ? "<th>Concern</th>" : ""}
            </tr></thead><tbody>${rows}</tbody></table>`;
          })()}
        </div>
      ` : '<p class="text-pulse-muted text-sm">No software data</p>'}
    </div>
  `;

  const swFilter = document.getElementById("sw-filter");
  if (swFilter) {
    const swRows = [...document.querySelectorAll("#sw-table tbody tr")];
    const swBody = document.querySelector("#sw-table tbody");
    swFilter.addEventListener("input", () => {
      const q = swFilter.value.toLowerCase();
      let shown = 0;
      swRows.forEach(tr => {
        const match = tr.textContent.toLowerCase().includes(q);
        tr.style.display = match ? "" : "none";
        if (match) shown++;
      });
      let none = document.getElementById("sw-no-match");
      if (shown === 0 && q) {
        if (!none && swBody) {
          none = document.createElement("tr");
          none.id = "sw-no-match";
          none.innerHTML = '<td colspan="4" class="text-pulse-muted text-sm" style="text-align:center;padding:1rem">No software matches your filter.</td>';
          swBody.appendChild(none);
        }
        if (none) none.style.display = "";
      } else if (none) {
        none.style.display = "none";
      }
    });
  }
}

// ── Environment ──────────────────────────────────────────────
function renderEnvironment() {
  const data = cached("system");
  if (!data) {
    $page().innerHTML = sectionLoading("Environment");
    fetchSection("system").then(() => { if (currentPage === "environment") renderEnvironment(); });
    return;
  }
  const id = data.identity || {};
  if (id.error) { $page().innerHTML = errorBox(id.message); return; }
  const os = id.operatingSystem || {};

  $page().innerHTML = `
    ${pageHeader("Environment", "Windows OS, locale, uptime, user accounts, and connected peripherals.",
      `<button class="btn-outline btn-ol-blue" onclick="dataCache.system=null;renderEnvironment()">
        ${svgIcon("refresh", 14)} Refresh
      </button>`
    )}

    <!-- OS & Locale -->
    <div class="card">
      ${sectionTitle("globe", "Operating System & Locale")}
      <div class="kv-grid kv-grid-wide">
        ${kvRow("OS", os.caption)}
        ${kvRow("Version", os.version)}
        ${kvRow("Build", os.buildNumber)}
        ${kvRow("Architecture", os.osArchitecture)}
        ${kvRow("Install Date", os.installDate ? String(os.installDate).slice(0, 10) : null)}
        ${kvRow("Uptime", id.uptime?.formatted)}
        ${kvRow("Timezone", id.timezone)}
        ${kvRow("Locale", id.locale)}
      </div>
      ${_osLifecycleBannerHtml(os.lifecycle)}
    </div>

    <!-- Users & Domains + Peripherals (lazy-filled below) -->
    <div class="dash-2col">
      <div class="card">
        ${sectionTitle("users", "Users & Domains")}
        <div id="sys-users-body">${loading()}</div>
      </div>
      <div class="card">
        ${sectionTitle("mouse", "Peripherals")}
        <div id="sys-peripherals-body">${loading()}</div>
      </div>
    </div>
  `;

  // Users & Domains + Peripherals — separate endpoints (not in the cached
  // system payload), so the tab paints immediately and these fill in.
  // Guard on currentPage so a late response after navigating away can't
  // write into another tab.
  const _panelFail = (id, what) => {
    if (currentPage !== "environment") return;
    const el = document.getElementById(id);
    if (el) el.innerHTML = `<p class="text-sm text-pulse-muted">Could not load ${what}.</p>`;
  };
  api("/api/users-domains").then(d => {
    if (currentPage !== "environment") return;
    const el = document.getElementById("sys-users-body");
    if (el) el.innerHTML = _usersPanelHtml(d);
  }).catch(() => _panelFail("sys-users-body", "users / domain"));
  api("/api/peripherals").then(d => {
    if (currentPage !== "environment") return;
    const el = document.getElementById("sys-peripherals-body");
    if (el) el.innerHTML = _peripheralsPanelHtml(d);
  }).catch(() => _panelFail("sys-peripherals-body", "peripherals"));
}

function _usersPanelHtml(d) {
  if (!d || d.error) return `<p class="text-sm text-pulse-muted">${esc((d && d.message) || "Could not read users / domain.")}</p>`;
  const dom = d.domain || {};
  const users = d.users || [];
  const membership = dom.partOfDomain
    ? `Domain &middot; ${esc(dom.domain || "—")}`
    : `Workgroup &middot; ${esc(dom.workgroup || "—")}`;
  return `
    <div class="kv-grid">
      ${kvRow("Computer", dom.computerName)}
      ${kvRowHtml("Membership", `<span class="${dom.partOfDomain ? "status-pass" : ""}">${membership}</span>`)}
      ${kvRow("Role", dom.role)}
      ${kvRow("Logged in", dom.currentUser || "— (no interactive user)")}
    </div>
    <div class="text-xs text-pulse-muted mt-3 mb-1">Local accounts: ${esc(String(d.userCount || 0))} &middot; ${esc(String(d.adminCount || 0))} admin</div>
    ${users.length ? `
      <table class="data-table"><thead><tr><th>Account</th><th>Access</th><th>Status</th></tr></thead><tbody>
      ${users.map(u => `<tr>
        <td><span class="font-mono">${esc(u.name)}</span>${u.fullName ? `<div class="text-xs text-pulse-muted">${esc(u.fullName)}</div>` : ""}</td>
        <td>${u.isAdmin ? '<span class="sev-chip sev-chip-info">Admin</span>' : '<span class="text-xs text-pulse-muted">Standard</span>'}</td>
        <td>${u.enabled ? '<span class="status-pass">Enabled</span>' : '<span class="text-pulse-muted">Disabled</span>'}${u.lockedOut ? ' <span class="status-fail">Locked</span>' : ""}</td>
      </tr>`).join("")}
      </tbody></table>
    ` : '<p class="text-sm text-pulse-muted">No local accounts found.</p>'}
  `;
}

function _peripheralsPanelHtml(d) {
  if (!d || d.error) return `<p class="text-sm text-pulse-muted">${esc((d && d.message) || "Could not read peripherals.")}</p>`;
  const row = (icon, label, dev) => {
    dev = dev || {};
    const on = !!dev.connected;
    // Names live under `devices` (mouse/keyboard) or `displays` (monitor).
    // PS 5.1 ConvertTo-Json unwraps a single-element array to a bare string,
    // so coerce back to an array before .join (see _first, above).
    const raw = dev.devices != null ? dev.devices : dev.displays;
    const names = Array.isArray(raw) ? raw : (raw ? [raw] : []);
    const detail = on
      ? (names.length ? names.join(", ") : `${dev.count || 0} connected`)
      : "Not detected";
    return `<div class="periph-row">
      <span class="periph-icon">${svgIcon(icon, 18)}</span>
      <div class="periph-main">
        <div class="periph-label">${esc(label)}</div>
        <div class="periph-detail" title="${esc(detail)}">${esc(detail)}</div>
      </div>
      <span class="periph-status ${on ? "periph-on" : "periph-off"}">
        ${svgIcon(on ? "check" : "x", 12)} ${on ? "Connected" : "None"}
      </span>
    </div>`;
  };
  return `
    ${row("mouse", "Mouse", d.mouse)}
    ${row("keyboard", "Keyboard", d.keyboard)}
    ${row("monitor", "Monitor", d.monitor)}
    <div class="periph-note">${svgIcon("info", 12)} <span>Reflects what the OS sees. Over RDP / LogMeIn these show the remote session, not the physical VPU.</span></div>
  `;
}

// ── Network ──────────────────────────────────────────────────

// PS single-element arrays unwrap to bare values — safe first-element accessor
function _first(v) { return Array.isArray(v) ? v[0] : v != null ? String(v) : null; }

// Local ping runner — manages preset and continuous ping modes
var _localPingState = { running: false, continuous: false, abortCtrl: null };

// Canonical "is name resolution demonstrably working?" signal, shared by the
// Issues & Recommendations DNS check and the Local Network Health ping card.
// A resolved domain in Domain Reachability, or any required hostname-based port
// that passed (you can't reach pixellot.tv:443 without first resolving
// pixellot.tv), proves DNS is fine — independent of whether the DNS server
// answers ICMP. So a dead ping to the DNS server is blocked ICMP, not a failure.
function _dnsResolvingFrom(domains, ports) {
  return (domains || []).some(function(d) {
      return d && d.resolvedTo && (d.status || "").toLowerCase() === "pass";
    }) || (ports || []).some(function(p) {
      return !p.optional && p.purpose !== "DNS" && (p.status || "").toLowerCase() === "pass"
        && /[a-z]/i.test(String(p.host || ""));
    });
}

function _renderPingCards(local) {
  var gw = (local || {}).gateway;
  var dns = (local || {}).dns;
  var el = document.getElementById("net-ping-results");
  if (!el) return;
  // The live ping loop only hands us {gateway, dns}; pull domains/ports from the
  // cached network data so the DNS card can soften a blocked-ICMP ping.
  var _net = cached("network") || {};
  var _resolving = _dnsResolvingFrom((_net.domains && _net.domains.results) || [], (_net.ports && _net.ports.results) || []);
  el.innerHTML = _pingCardHtml(gw, false) + _pingCardHtml(dns, _resolving);
}

function _fmtMs(v) {
  if (v == null) return "—";
  if (v === 0) return "< 1 ms";
  if (v < 1) return v.toFixed(2) + " ms";
  if (v < 10) return v.toFixed(1) + " ms";
  return Math.round(v) + " ms";
}

function _pingCardHtml(p, resolutionWorks) {
  if (!p || !p.target) return "";
  // ICMP to the DNS server is routinely firewalled even when the resolver is
  // perfectly healthy. When name resolution is demonstrably working but the
  // ping got no reply, present the card as a neutral INFO ("ping blocked")
  // rather than a red failure that reads as an outage.
  var icmpBlocked = !!resolutionWorks && !p.reachable;
  var sc, dot;
  if (icmpBlocked) {
    sc = "net-ping-info"; dot = "var(--c-accent-blue)";
  } else {
    sc = p.status === "pass" ? "net-ping-pass" : p.status === "warn" ? "net-ping-warn" : "net-ping-fail";
    dot = p.status === "pass" ? "var(--c-accent-green)" : p.status === "warn" ? "var(--c-accent-amber)" : "var(--c-accent-red)";
  }
  var latency = _fmtMs(p.avgMs);
  var loss = p.lossPercent != null ? p.lossPercent + "%" : "—";
  var range = (p.minMs != null && p.maxMs != null) ? _fmtMs(p.minMs).replace(" ms","") + " / " + _fmtMs(p.avgMs).replace(" ms","") + " / " + _fmtMs(p.maxMs).replace(" ms","") + " ms" : "—";
  var note = icmpBlocked
    ? '<div class="net-ping-note">' + svgIcon("info", 12) + ' ICMP ping blocked by firewall — name resolution is working' + '</div>'
    : "";
  return '<div class="net-ping-card ' + sc + '">' +
    '<div class="net-ping-header">' +
      '<span class="net-ping-dot" style="background:' + dot + '"></span>' +
      '<span class="net-ping-label">' + esc(p.label) + '</span>' +
      '<span class="net-ping-target font-mono">' + esc(p.target) + '</span>' +
    '</div>' +
    '<div class="net-ping-stats">' +
      '<div class="net-ping-stat"><span class="net-ping-stat-label">Latency</span><span class="net-ping-stat-value">' + esc(latency) + '</span></div>' +
      '<div class="net-ping-stat"><span class="net-ping-stat-label">Packet loss</span><span class="net-ping-stat-value">' + esc(loss) + '</span></div>' +
      '<div class="net-ping-stat"><span class="net-ping-stat-label">Min / Avg / Max</span><span class="net-ping-stat-value font-mono">' + esc(range) + '</span></div>' +
      '<div class="net-ping-stat"><span class="net-ping-stat-label">Packets</span><span class="net-ping-stat-value">' + esc(String(p.received || 0)) + ' / ' + esc(String(p.sent || 0)) + ' received</span></div>' +
    '</div>' +
    note +
  '</div>';
}

async function runLocalPing(count) {
  // If a run is already in progress, abort it and start a fresh batch with the new count.
  if (_localPingState.running) {
    stopLocalPing();
    // Give the previous abort a tick to settle so we don't race on _localPingState.
    await new Promise(function(r) { setTimeout(r, 30); });
  }
  _localPingState.running = true;
  _localPingState.continuous = (count === 0);
  _localPingState.abortCtrl = new AbortController();
  _updatePingControls();

  var batchSize = _localPingState.continuous ? 4 : count;
  var accum = { gateway: null, dns: null };

  try {
    while (_localPingState.running) {
      var resp = await fetch("/api/network/local-ping?count=" + batchSize, { signal: _localPingState.abortCtrl.signal });
      var data = await resp.json();
      if (!_localPingState.running) break;

      if (!_localPingState.continuous) {
        // One-shot: just show the result
        _renderPingCards(data);
        // Also update the cached data
        if (dataCache.network) dataCache.network.local = data;
        break;
      }

      // Continuous: accumulate stats
      accum = _accumPing(accum, data);
      _renderPingCards(accum);
      if (dataCache.network) dataCache.network.local = accum;
    }
  } catch (e) {
    if (e.name !== "AbortError") console.error("Local ping error:", e);
  }

  _localPingState.running = false;
  _localPingState.continuous = false;
  _localPingState.abortCtrl = null;
  _updatePingControls();
}

function _accumPing(prev, batch) {
  // First-hop gateway latency varies with switch load/Wi-Fi; only flag well
  // above a healthy LAN hop (30 ms). DNS (8.8.8.8) crosses the internet so a
  // higher 50 ms bar is normal. Packet loss flags either regardless.
  function merge(old, cur, warnLatencyMs) {
    if (!cur || !cur.target) return old;
    if (!old || !old.target) return cur;
    var sent = (old.sent || 0) + (cur.sent || 0);
    var recv = (old.received || 0) + (cur.received || 0);
    var minMs = (old.minMs != null && cur.minMs != null) ? Math.min(old.minMs, cur.minMs) : (cur.minMs != null ? cur.minMs : old.minMs);
    var maxMs = (old.maxMs != null && cur.maxMs != null) ? Math.max(old.maxMs, cur.maxMs) : (cur.maxMs != null ? cur.maxMs : old.maxMs);
    // Weighted average
    var avgMs = null;
    if (old.avgMs != null && cur.avgMs != null && old.received && cur.received) {
      avgMs = Math.round(((old.avgMs * old.received) + (cur.avgMs * cur.received)) / recv);
    } else if (cur.avgMs != null) { avgMs = cur.avgMs; }
    else { avgMs = old.avgMs; }
    var loss = sent > 0 ? Math.round(((sent - recv) / sent) * 100) : 100;
    var status = recv === 0 ? "fail" : loss > 0 || (avgMs != null && avgMs > warnLatencyMs) ? "warn" : "pass";
    return { target: cur.target, label: cur.label, reachable: recv > 0, sent: sent, received: recv,
             lossPercent: loss, minMs: minMs, avgMs: avgMs, maxMs: maxMs, status: status };
  }
  return {
    gateway: merge(prev.gateway, batch.gateway, 30),
    dns:     merge(prev.dns,     batch.dns,     50),
  };
}

function stopLocalPing() {
  _localPingState.running = false;
  _localPingState.continuous = false;
  if (_localPingState.abortCtrl) {
    _localPingState.abortCtrl.abort();
    _localPingState.abortCtrl = null;
  }
  _updatePingControls();
}

function _updatePingControls() {
  var bar = document.getElementById("net-ping-controls");
  if (!bar) return;
  var btns = bar.querySelectorAll("button");
  for (var i = 0; i < btns.length; i++) {
    btns[i].disabled = _localPingState.running && !btns[i].classList.contains("net-ping-stop");
  }
  var stopBtn = document.getElementById("net-ping-stop-btn");
  if (stopBtn) stopBtn.style.display = _localPingState.running ? "inline-flex" : "none";
  var spinner = document.getElementById("net-ping-spinner");
  if (spinner) spinner.style.display = _localPingState.running ? "inline-flex" : "none";
}

// Advanced diagnostics toggle
function _toggleAdvNet() {
  var sec = document.getElementById("net-adv-section");
  var arrow = document.getElementById("net-adv-arrow");
  if (!sec) return;
  // classList.toggle returns whether the class is present *after* the toggle —
  // i.e., true when the section is now collapsed.
  var collapsed = sec.classList.toggle("net-adv-collapsed");
  if (arrow) arrow.classList.toggle("net-adv-arrow-open", !collapsed);
}

// Re-run all network probes with a button spinner — avoids the flash-to-skeleton
// reload pattern that other tabs use.
async function _rerunNetworkTests(btn) {
  if (btn && btn.disabled) return;
  if (btn) {
    btn.disabled = true;
    var labelSpan = btn.querySelector("span");
    if (labelSpan) labelSpan.textContent = "Running…";
  }
  try {
    dataCache.network = null;
    await fetchSection("network");
  } finally {
    // renderNetwork will rebuild the page (including the button), so no need
    // to restore the label here.
  }
}

// Traceroute runner
var _traceState = { running: false };
async function _runTraceroute(target) {
  if (_traceState.running) return;
  _traceState.running = true;
  var out = document.getElementById("net-trace-results");
  var btn = document.getElementById("net-trace-btn");
  if (btn) btn.disabled = true;
  if (out) out.innerHTML = '<p class="text-pulse-muted text-sm loading-pulse">Running traceroute to ' + esc(target) + '…</p>';

  try {
    var resp = await fetch("/api/network/traceroute?target=" + encodeURIComponent(target));
    var data = await resp.json();
    if (data.error) {
      if (out) out.innerHTML = '<p class="text-sm status-fail">' + esc(data.message) + '</p>';
    } else {
      _renderTraceroute(out, data);
    }
  } catch (e) {
    if (out) out.innerHTML = '<p class="text-sm status-fail">Traceroute failed: ' + esc(String(e)) + '</p>';
  }
  _traceState.running = false;
  if (btn) btn.disabled = false;
}

function _renderTraceroute(el, d) {
  var hops = d.hops || [];
  var reachedCls = d.reached ? "status-pass" : "status-fail";
  var reachedLabel = d.reached ? "Reached" : "Not reached";
  el.innerHTML =
    '<div class="net-trace-summary">' +
      '<span class="text-sm text-pulse-muted">Target: <span class="font-mono text-white">' + esc(d.target) + '</span></span>' +
      '<span class="text-sm text-pulse-muted">IP: <span class="font-mono text-white">' + esc(d.targetIp || "—") + '</span></span>' +
      '<span class="text-sm ' + reachedCls + '">' + esc(reachedLabel) + ' in ' + esc(String(d.hopCount || 0)) + ' hops</span>' +
    '</div>' +
    '<table class="data-table net-trace-table"><thead><tr>' +
      '<th>#</th><th>IP Address</th><th>Hostname</th><th>RTT</th><th>Status</th>' +
    '</tr></thead><tbody>' +
    hops.map(function(h) {
      var sc = h.status === "reached" ? "status-pass" : h.status === "timeout" ? "text-pulse-muted" : h.status === "transit" ? "" : "status-fail";
      var rtt = h.rttMs != null ? h.rttMs + " ms" : "—";
      var statusLabel = h.status === "reached" ? "Reached" : h.status === "transit" ? "OK" : h.status === "timeout" ? "* * *" : esc(h.status);
      return '<tr' + (sc ? ' class="' + sc + '"' : '') + '>' +
        '<td>' + esc(String(h.hop)) + '</td>' +
        '<td class="font-mono">' + esc(h.ip || "* * *") + '</td>' +
        '<td class="text-pulse-muted">' + esc(h.hostname || "") + '</td>' +
        '<td class="font-mono">' + esc(rtt) + '</td>' +
        '<td>' + esc(statusLabel) + '</td>' +
      '</tr>';
    }).join("") +
    '</tbody></table>';
}

// Speed Test — fetch and display Speedtest.net result
async function _fetchSpeedtest() {
  var input = document.getElementById("net-speed-input");
  var out = document.getElementById("net-speed-results");
  var btn = document.getElementById("net-speed-fetch-btn");
  if (!input || !out) return;
  var val = input.value.trim();
  if (!val) { out.innerHTML = '<p class="text-sm status-fail">Please paste a Speedtest result URL or ID.</p>'; return; }

  btn.disabled = true;
  out.innerHTML = '<p class="text-pulse-muted text-sm loading-pulse">Fetching result…</p>';

  try {
    var resp = await fetch("/api/network/speedtest?result_id=" + encodeURIComponent(val));
    var data = await resp.json();
    if (data.error) {
      out.innerHTML = '<p class="text-sm status-fail">' + esc(data.message) + '</p>';
      btn.disabled = false;
      return;
    }
    _renderSpeedResult(out, data);
  } catch (e) {
    out.innerHTML = '<p class="text-sm status-fail">Request failed: ' + esc(String(e)) + '</p>';
  }
  btn.disabled = false;
}

function _renderSpeedResult(el, d) {
  var dlOk = d.download != null && d.download >= 10;
  var ulOk = d.upload != null && d.upload >= 10;
  var dlCls = d.download == null ? "" : dlOk ? "net-speed-ok" : "net-speed-bad";
  var ulCls = d.upload == null ? "" : ulOk ? "net-speed-ok" : "net-speed-bad";

  var findings = [];
  if (d.download != null && d.download < 10)
    findings.push("Download speed (" + d.download + " Mbps) is below the 10 Mbps minimum for Pixellot streaming.");
  if (d.upload != null && d.upload < 10)
    findings.push("Upload speed (" + d.upload + " Mbps) is below the 10 Mbps minimum for Pixellot streaming.");
  if (d.ping != null && d.ping > 50)
    findings.push("Ping (" + d.ping + " ms) is elevated — may cause stream buffering.");

  el.innerHTML =
    '<div class="net-speed-cards">' +
      '<div class="net-speed-card">' +
        '<div class="net-speed-card-label">DOWNLOAD</div>' +
        '<div class="net-speed-card-val ' + dlCls + '">' + (d.download != null ? d.download : "—") + '</div>' +
        '<div class="net-speed-card-unit">Mbps</div>' +
      '</div>' +
      '<div class="net-speed-card">' +
        '<div class="net-speed-card-label">UPLOAD</div>' +
        '<div class="net-speed-card-val ' + ulCls + '">' + (d.upload != null ? d.upload : "—") + '</div>' +
        '<div class="net-speed-card-unit">Mbps</div>' +
      '</div>' +
      '<div class="net-speed-card">' +
        '<div class="net-speed-card-label">PING</div>' +
        '<div class="net-speed-card-val">' + (d.ping != null ? d.ping : "—") + '</div>' +
        '<div class="net-speed-card-unit">ms</div>' +
      '</div>' +
      (d.jitter != null ? '<div class="net-speed-card">' +
        '<div class="net-speed-card-label">JITTER</div>' +
        '<div class="net-speed-card-val">' + d.jitter + '</div>' +
        '<div class="net-speed-card-unit">ms</div>' +
      '</div>' : '') +
    '</div>' +
    (d.isp || d.server ? '<div class="net-speed-meta">' +
      (d.isp ? '<span>ISP: ' + esc(d.isp) + '</span>' : '') +
      (d.server ? '<span>Server: ' + esc(d.server) + '</span>' : '') +
      '<a href="' + esc(d.url) + '" target="_blank" rel="noopener" class="text-xs" style="color:var(--c-accent-blue)">View full result ↗</a>' +
    '</div>' : '') +
    (findings.length ? '<div class="net-speed-findings">' +
      findings.map(function(f) {
        return '<div class="net-speed-finding">' + svgIcon("triangle", 14) + ' <span>' + esc(f) + '</span></div>';
      }).join('') +
    '</div>' :
      // Only claim "meets requirements" when we actually parsed both numbers.
      (d.download != null && d.upload != null
        ? '<div class="net-speed-ok-msg">' + svgIcon("check", 14) + ' Bandwidth meets Pixellot minimum requirements (≥ 10 Mbps up/down)</div>'
        : '<div class="net-speed-finding">' + svgIcon("triangle", 14) + ' <span>Speedtest returned partial results — could not verify all thresholds.</span></div>'));
}

// ── Live Network Health (WebSocket-driven) ──────────────────
function _renderLiveNetHealth(h) {
  var el = document.getElementById("net-live-body");
  if (!el) return;
  var tcp = h.tcp || {};
  var conns = h.connections || [];
  var nics = h.nics || [];

  // Update stale indicator (lives in the header, outside #net-live-body)
  var ind = document.querySelector(".net-live-indicator");
  if (ind) {
    ind.classList.toggle("net-live-stale", !_wsConnected);
    var label = ind.querySelector(".text-xs");
    if (label) label.textContent = _wsConnected ? "Live via WebSocket" : "Disconnected — reconnecting…";
  }

  // Retransmission gauge color
  var retrans = tcp.retransmitsSec || 0;
  var retCls = retrans > 10 ? "status-fail" : retrans > 2 ? "status-warn" : "status-pass";

  // Compute deltas for cumulative counters (Failures/Resets are cumulative since boot)
  var curFailures = tcp.connFailures || 0;
  var curResets   = tcp.connResets || 0;
  var failuresDelta = 0;
  var resetsDelta = 0;
  if (_prevLiveCounters) {
    failuresDelta = Math.max(0, curFailures - _prevLiveCounters.failures);
    resetsDelta   = Math.max(0, curResets - _prevLiveCounters.resets);
  }
  _prevLiveCounters = { failures: curFailures, resets: curResets };

  el.innerHTML =
    '<div class="net-live-gauges">' +
      _liveGauge("Retransmits/s", retrans, retCls) +
      _liveGauge("Established", tcp.established || 0, "") +
      _liveGauge("New Failures", failuresDelta, failuresDelta > 0 ? "status-warn" : "") +
      _liveGauge("New Resets", resetsDelta, resetsDelta > 0 ? "status-warn" : "") +
      _liveGauge("Segs Out/s", tcp.segsOutSec || 0, "") +
      _liveGauge("Segs In/s", tcp.segsInSec || 0, "") +
    '</div>' +
    (conns.length ? '<div class="net-live-conns">' +
      '<div class="net-live-conns-title">Active Connections (' + conns.length + ')</div>' +
      '<table class="data-table"><thead><tr>' +
        '<th>Remote Address</th><th>Port</th><th>Local Port</th><th>State</th>' +
      '</tr></thead><tbody>' +
      conns.map(function(c) {
        var stCls = c.state === "Established" ? "status-pass" : c.state === "TimeWait" ? "text-pulse-muted" : "status-warn";
        return '<tr>' +
          '<td class="font-mono text-xs">' + esc(c.remoteAddr) + '</td>' +
          '<td class="font-mono">' + esc(String(c.remotePort)) + '</td>' +
          '<td class="font-mono text-xs text-pulse-muted">' + esc(String(c.localPort || "")) + '</td>' +
          '<td class="' + stCls + '">' + esc(c.state) + '</td>' +
        '</tr>';
      }).join("") +
      '</tbody></table>' +
    '</div>' : '') +
    // Per-NIC live health — queue depth, error counters, and packet rates for
    // every physical interface, so a multi-NIC VPU shows per-port build-up
    // (camera card vs motherboard port) instead of one blended number.
    (nics.length ? '<div class="net-live-conns">' +
      '<div class="net-live-conns-title">Network Interfaces (' + nics.length + ')</div>' +
      '<table class="data-table"><thead><tr>' +
        '<th>Interface</th><th title="Output queue length — sustained &gt;2 means the NIC can\'t drain fast enough">Queue</th><th>RX Err</th><th>TX Err</th><th>RX/s</th><th>TX/s</th>' +
      '</tr></thead><tbody>' +
      nics.map(function(n) {
        var qCls  = (n.queueLen || 0) > 2 ? "status-warn" : "";
        var rxCls = (n.rxErrors || 0) > 0 ? "status-warn" : "";
        var txCls = (n.txErrors || 0) > 0 ? "status-warn" : "";
        var nicName = String(n.name || "").replace(/\[r\]/gi, "(R)");
        return '<tr>' +
          '<td class="text-xs">' + esc(nicName) + '</td>' +
          '<td class="font-mono ' + qCls + '">' + esc(String(n.queueLen || 0)) + '</td>' +
          '<td class="font-mono ' + rxCls + '">' + esc(String(n.rxErrors || 0)) + '</td>' +
          '<td class="font-mono ' + txCls + '">' + esc(String(n.txErrors || 0)) + '</td>' +
          '<td class="font-mono text-xs text-pulse-muted">' + esc(String(n.rxPktSec || 0)) + '</td>' +
          '<td class="font-mono text-xs text-pulse-muted">' + esc(String(n.txPktSec || 0)) + '</td>' +
        '</tr>';
      }).join("") +
      '</tbody></table>' +
    '</div>' : '');
}

function _liveGauge(label, val, cls) {
  return '<div class="net-live-gauge">' +
    '<div class="net-live-gauge-val ' + (cls || '') + '">' + esc(String(val)) + '</div>' +
    '<div class="net-live-gauge-label">' + esc(label) + '</div>' +
  '</div>';
}

// ── Network Capture (on-demand pktmon) ──────────────────────
var _captureState = { running: false };

async function _runCapture(duration) {
  if (_captureState.running) return;
  _captureState.running = true;

  var ctrls = document.getElementById("net-capture-controls");
  var spinner = document.getElementById("net-capture-status");
  var out = document.getElementById("net-capture-results");
  var presets = ctrls ? ctrls.querySelectorAll(".net-ping-preset") : [];
  // Highlight which duration is running, disable others.
  presets.forEach(function(b) {
    var bDur = parseInt((b.textContent || "").replace("s",""), 10);
    b.classList.toggle("net-ping-preset-active", bDur === duration);
    b.disabled = true;
  });
  if (spinner) spinner.style.display = "inline-flex";
  if (out) out.innerHTML = '<p class="text-pulse-muted text-sm loading-pulse">Running ' + duration + 's packet capture — analyzing TCP headers on ports 443, 1935, 80, UDP 2088…</p>';

  try {
    var resp = await fetch("/api/network/capture?duration=" + duration);
    var data = await resp.json();
    if (data.error) {
      if (out) out.innerHTML = '<p class="text-sm status-fail">' + esc(data.message) + '</p>';
    } else {
      _renderCapture(out, data);
    }
  } catch (e) {
    if (out) out.innerHTML = '<p class="text-sm status-fail">Capture failed: ' + esc(String(e)) + '</p>';
  }
  _captureState.running = false;
  presets.forEach(function(b) { b.disabled = false; });
  if (spinner) spinner.style.display = "none";
}

function _renderCapture(el, d) {
  var findings = d.findings || [];
  var topTalkers = d.topTalkers || [];

  el.innerHTML =
    // Summary stats
    '<div class="net-cap-summary">' +
      '<div class="net-cap-stat"><span class="net-cap-stat-val">' + esc(String(d.totalPackets || 0)) + '</span><span class="net-cap-stat-label">Packets</span></div>' +
      '<div class="net-cap-stat"><span class="net-cap-stat-val ' + ((d.tcpRetransmits || 0) > 0 ? 'status-warn' : '') + '">' + esc(String(d.tcpRetransmits || 0)) + '</span><span class="net-cap-stat-label">Retransmits</span></div>' +
      '<div class="net-cap-stat"><span class="net-cap-stat-val ' + ((d.tcpResets || 0) > 0 ? 'status-warn' : '') + '">' + esc(String(d.tcpResets || 0)) + '</span><span class="net-cap-stat-label">Resets</span></div>' +
      '<div class="net-cap-stat"><span class="net-cap-stat-val ' + ((d.droppedPackets || 0) > 0 ? 'status-fail' : '') + '">' + esc(String(d.droppedPackets || 0)) + '</span><span class="net-cap-stat-label">Drops</span></div>' +
      '<div class="net-cap-stat"><span class="net-cap-stat-val">' + esc(String(d.tcpSyns || 0)) + '</span><span class="net-cap-stat-label">SYN</span></div>' +
      '<div class="net-cap-stat"><span class="net-cap-stat-val">' + esc(String(d.tcpFins || 0)) + '</span><span class="net-cap-stat-label">FIN</span></div>' +
    '</div>' +
    // Findings
    (findings.length ? '<div class="net-cap-findings">' +
      findings.map(function(f) {
        var cls = f.severity === "critical" ? "net-rec-critical" : f.severity === "warning" ? "net-rec-warn" : f.severity === "pass" ? "net-cap-pass" : "net-rec-info";
        var icon = f.severity === "pass" ? svgIcon("check", 14) : svgIcon("triangle", 14);
        return '<div class="net-cap-finding ' + cls + '">' + icon + ' <strong>' + esc(f.title) + '</strong> — ' + esc(f.body) + '</div>';
      }).join("") +
    '</div>' : '') +
    // Top talkers
    '<div class="net-cap-talkers">' +
      '<div class="net-cap-talkers-title">Top Endpoints by Packet Count</div>' +
      (topTalkers.length
        ? '<table class="data-table"><thead><tr>' +
            '<th>Host</th><th>Address</th><th>Port</th><th>Packets</th>' +
          '</tr></thead><tbody>' +
          topTalkers.map(function(t) {
            return '<tr>' +
              '<td>' + esc(t.remoteHost || "—") + '</td>' +
              '<td class="font-mono text-xs">' + esc(t.remoteAddr) + '</td>' +
              '<td class="font-mono">' + esc(String(t.remotePort)) + '</td>' +
              '<td class="font-mono">' + esc(String(t.packets)) + '</td>' +
            '</tr>';
          }).join("") +
          '</tbody></table>'
        : '<p class="net-cap-empty">No outbound destinations parsed from the capture — this Windows build may not expose IP details via etl2txt.</p>') +
    '</div>';
}

function _prefixToMask(prefix) {
  if (prefix == null) return null;
  var n = parseInt(prefix, 10);
  if (isNaN(n) || n < 0 || n > 32) return null;
  var mask = n === 0 ? 0 : (0xFFFFFFFF << (32 - n)) >>> 0;
  return [24, 16, 8, 0].map(function(s) { return (mask >>> s) & 0xFF; }).join(".");
}

// "Impact if blocked" copy, sourced from the NFHS Network Firewall Setup doc
// where the endpoint appears there, and authored from Pixellot service
// knowledge for the few Pulse-only endpoints the doc doesn't list (Singular,
// leaf-* buckets). Single editable home — revisit/expand later.
// Ports are keyed by purpose; domains by hostname.
const NET_PORT_IMPACT = {
  "DNS": "The VPU can't resolve any hostname, so it can't reach any service.",
  "Pixellot": "System management and software updates are blocked, and the stream fails to broadcast.",
  // Streaming model (verified from VPU logs + packet capture, Olympic WA
  // 2026-08-18): the live broadcast walks a fixed failover chain — Zixi
  // UDP/2088 → Zixi UDP/443 (same protocol, disguise port) → RTMP TCP/1935 →
  // nothing. Either UDP rung alone is a fully healthy stream; RTMP is a
  // degraded last resort (~4 min late start, no loss protection). TCP/443 is
  // the CONTROL PLANE and carries no live video. Wording is per-port "in
  // isolation"; the live verdict is in the Port Connectivity finding.
  "Pixellot Echo": "Pixellot cloud services over HTTPS (TCP/443): event scheduling, system management, remote support, video upload. Carries no live video — but nothing on the unit works without it.",
  "NFHS Network": "Event scheduling, broadcast watermarks, and viewer access are unavailable.",
  "Singular Overlay": "On-screen graphics and scorebug overlays won't load.",
  "LogMeIn": "The support team can't diagnose the VPU remotely.",
  "NTP": "The clock can drift — the VPU may miss scheduled events if no valid time server is set.",
  "Zixi Backup": "Backup live-stream connection (Zixi over UDP/443 — the same streaming protocol as UDP/2088, not HTTPS). Either Zixi port alone carries a fully healthy stream; with both blocked the broadcast degrades to the RTMP fallback.",
  "Zixi Streaming": "The primary live-stream connection (Zixi over UDP/2088). If blocked, the stream fails over to Zixi UDP/443, then to the degraded RTMP fallback (TCP/1935).",
  "RTMP Fallback": "Last-resort streaming path (RTMP over TCP/1935) used only when both Zixi/UDP connections are blocked: games start ~4 minutes late with no packet-loss protection. If this is blocked too, a venue with both UDP ports blocked can't broadcast at all. (Tested against a stable public RTMP host — proves 1935 egress by port, not that pixellot.stream specifically is allowed.)",
  "Scorebot": "SportzCast scoreboard software can't connect or update (SportzCast sites only).",
};
const NET_DOMAIN_IMPACT = {
  "nfhsnetwork.com": "Event scheduling, broadcast watermarks, and viewer access are unavailable.",
  "pixellot.tv": "System management and software updates are blocked, and the stream fails to broadcast.",
  "software.pixellot.tv": "Software and firmware updates are blocked.",
  "sportzcast.net": "SportzCast scoreboard software can't connect or update (SportzCast sites only).",
  "service.singular.live": "On-screen graphics and scorebug overlays won't load.",
  "logmein.com": "The support team can't diagnose the VPU remotely.",
};
function _netPortImpact(p) { return (p && NET_PORT_IMPACT[p.purpose]) || ""; }

// Streaming failover chain (verified from VPU logs + packet capture, Olympic
// WA 2026-08-18): Zixi UDP/2088 → Zixi UDP/443 → RTMP TCP/1935 → nothing.
// Either Zixi/UDP rung alone is a fully healthy stream; RTMP is a degraded
// last resort (~4 min late start, no loss protection). TCP/443 (Pixellot
// Echo) is the control plane, NOT a streaming rung. Keep these purposes in
// sync with main.py and Test-NetworkPorts.ps1.
var ZIXI_PURPOSES = ["Zixi Streaming", "Zixi Backup"];
var RTMP_FALLBACK_PURPOSE = "RTMP Fallback";
var STREAM_RUNG_PURPOSES = ZIXI_PURPOSES.concat([RTMP_FALLBACK_PURPOSE]);
function _streamingHealth(ports) {
  function isPass(p) { return (p.status || "").toLowerCase() === "pass"; }
  var rungs = (ports || []).filter(function(p) {
    return STREAM_RUNG_PURPOSES.indexOf(p.purpose) !== -1 && !p.optional;
  });
  var blocked = rungs.filter(function(p) { return !isPass(p); });
  var zixiOpen = rungs.some(function(p) { return ZIXI_PURPOSES.indexOf(p.purpose) !== -1 && isPass(p); });
  var rtmpOpen = rungs.some(function(p) { return p.purpose === RTMP_FALLBACK_PURPOSE && isPass(p); });
  return {
    rungs: rungs, blocked: blocked,
    zixiOpen: zixiOpen, rtmpOpen: rtmpOpen,
    // Three verdict tiers: healthy (Zixi carries the stream), degraded (both
    // UDP rungs dead, games air late on unprotected RTMP), dark (every rung
    // dead — the broadcast cannot go on air).
    healthy: zixiOpen,
    degraded: rungs.length > 0 && !zixiOpen && rtmpOpen,
    dark: rungs.length > 0 && !zixiOpen && !rtmpOpen,
  };
}
// Is this individual blocked port a failover rung whose chain is still healthy
// (Zixi carrying the stream)? Softens its card from a red "Fail" to an amber
// "No backup" — the stream is fine, resiliency is what's lost. Once the stream
// is degraded or dark, every blocked rung is a real (red) failure.
function _isRedundantStreamBlock(p, health) {
  return health.zixiOpen
    && STREAM_RUNG_PURPOSES.indexOf(p.purpose) !== -1
    && (p.status || "").toLowerCase() !== "pass";
}
function _netDomainImpact(d) { return (d && NET_DOMAIN_IMPACT[d.domain]) || ""; }

// Styled "impact if blocked" tooltip bubble (replaces native title= tooltips,
// which are delayed, unstyled, and never show on keyboard focus or touch).
// The bubble is a real element inside the trigger; CSS shows it on
// :hover/:focus-within. The header line frames the impact sentence as a
// hypothetical — without it, "X is unavailable" on a passing row reads like
// a live failure. Callers outside the Network tab pass their own title.
function _impactTipHtml(impact, title) {
  return `<span class="net-tip-bubble" role="tooltip">` +
    `<span class="net-tip-title">${esc(title || "If blocked on the school's network")}</span>` +
    `${esc(impact)}</span>`;
}

// Impact per TLS-checked domain — what breaks when a firewall intercepts it.
// Keep the domains in sync with Test-TlsInspection.ps1.
const TLS_DOMAIN_IMPACT = {
  "singular.live": "On-screen graphics and scorebug overlays fail to load.",
  "app.singular.live": "On-screen graphics and scorebug overlays fail to load.",
  "api.singular.live": "On-screen graphics and scorebug overlays fail to load.",
  "datastream.singular.live": "The realtime data feed that drives graphics can't connect — overlays stay blank even though video streams.",
  "service.singular.live": "On-screen graphics and scorebug overlays fail to load.",
  "pixellot.tv": "System management and software updates are blocked.",
  "software.pixellot.tv": "Software and firmware updates are blocked.",
  "nfhsnetwork.com": "Event scheduling, broadcast watermarks, and viewer access are unavailable.",
  "secure.logmein.com": "The support team can't diagnose the VPU remotely.",
  "www.python.org": "The Pulse installer can't download Python on this network.",
};

function _tlsBadge(status) {
  switch ((status || "").toLowerCase()) {
    case "pass":           return badge("Pass", "pass");
    case "intercepted":    return badge("Intercepted", "fail");
    case "filtered":       return badge("Blocked by filter", "fail");
    case "handshake-fail": return badge("Handshake failed", "warn");
    case "cert-time":      return badge("Cert dates invalid", "warn");
    case "blocked":        return badge("Unreachable", "fail");
    default:               return badge(status || "Unknown", "muted");
  }
}

// Port Connectivity as a single status list (Required → Optional), one row
// per service. Replaces the old TCP|UDP card grid: uniform rows, service-led,
// protocol/port as metadata, a status pill, and a one-glance section summary.
function _renderPortConnectivity(ports) {
  ports = ports || [];
  if (!ports.length) return '<p class="text-pulse-muted text-sm mt-2">No port results.</p>';

  // Streaming-path redundancy: a blocked streaming transport that still has an
  // open sibling is "no failover" (amber), not a red "Fail" — broadcasting works.
  var health = _streamingHealth(ports);

  // Combine related results into one tile: hosts sharing a protocol/port (the
  // six TCP/443 services) group together, and a single host's port range
  // (Scorebot 1400–1405) collapses to one tile. Two passes — by proto/port
  // first, then by host for the leftovers — mirroring the original card grid.
  function groupPorts(list) {
    var byPort = {}, portOrder = [];
    list.forEach(function(p) {
      var key = (p.protocol || "").toUpperCase() + "/" + p.port;
      if (!byPort[key]) { byPort[key] = []; portOrder.push(key); }
      byPort[key].push(p);
    });
    var groups = [], singles = [];
    portOrder.forEach(function(key) {
      var items = byPort[key];
      if (items.length > 1) groups.push({ type: "byPort", items: items, order: list.indexOf(items[0]) });
      else singles.push(items[0]);
    });
    var byHost = {}, hostOrder = [];
    singles.forEach(function(p) {
      var key = (p.protocol || "").toUpperCase() + "|" + (p.host || "") + "|" + (p.purpose || "");
      if (!byHost[key]) { byHost[key] = []; hostOrder.push(key); }
      byHost[key].push(p);
    });
    hostOrder.forEach(function(key) {
      var items = byHost[key];
      groups.push({ type: items.length > 1 ? "byHost" : "single", items: items, order: list.indexOf(items[0]) });
    });
    // Ascending by port number — each tile reads left-to-right in numeric order
    // (53, 123, 443…). A group's port is its lowest member (a range tile sorts by
    // its start). Ties (443 TCP vs 443 UDP) fall back to first-appearance order,
    // keeping the protocols in a stable, predictable sequence.
    groups.sort(function(a, b) {
      var pa = Math.min.apply(null, a.items.map(function(p) { return Number(p.port) || 0; }));
      var pb = Math.min.apply(null, b.items.map(function(p) { return Number(p.port) || 0; }));
      return pa !== pb ? pa - pb : a.order - b.order;
    });
    return groups;
  }

  // Port number (the priority) + protocol for the port-led tile. A shared port
  // (443 across several hosts) → "443"; a range on one host (Scorebot
  // 1400–1405) → "1400–1405". Hosts/domains are intentionally NOT shown on the
  // tile — the domain detail lives in the Domain Reachability column.
  function portParts(items) {
    var proto = (items[0].protocol || "TCP").toUpperCase();
    var seen = {}, portsN = [];
    items.forEach(function(p) { if (!seen[p.port]) { seen[p.port] = 1; portsN.push(p.port); } });
    portsN.sort(function(a, b) { return a - b; });
    var num;
    if (portsN.length === 1) { num = String(portsN[0]); }
    else {
      var contiguous = portsN[portsN.length - 1] - portsN[0] + 1 === portsN.length;
      num = contiguous ? portsN[0] + "–" + portsN[portsN.length - 1] : portsN.join(",");
    }
    return { num: num, proto: proto };
  }

  // Status rollup for a (possibly multi-port) group → pill + accent colour.
  function rollup(items) {
    var pass = items.filter(function(p) { return (p.status || "").toLowerCase() === "pass"; }).length;
    var total = items.length, allPass = pass === total, optional = items[0].optional;
    // A single-port streaming transport that's blocked but still has an open
    // sibling: not a failure, just lost failover → amber "No failover".
    var redundant = !allPass && total === 1 && _isRedundantStreamBlock(items[0], health);
    var pillTxt, pillCls;
    if (total > 1) { pillTxt = pass + "/" + total; pillCls = allPass ? "pass" : (optional ? "muted" : "fail"); }
    else if (allPass) { pillTxt = "Pass"; pillCls = "pass"; }
    else if (redundant) { pillTxt = "No backup"; pillCls = "warn"; }
    else { pillTxt = optional ? "Blocked" : "Fail"; pillCls = optional ? "muted" : "fail"; }
    // Optional failures are de-emphasized (muted, not red); redundant streaming
    // blocks are amber. Only a real (non-redundant) required failure is red.
    var accent = allPass ? "var(--c-accent-green)"
      : redundant ? "var(--c-accent-amber)"
      : (optional ? "var(--c-dim)" : "var(--c-accent-red)");
    var stateCls = (!allPass && !optional && !redundant) ? " is-fail" : "";
    return { pillTxt: pillTxt, pillCls: pillCls, accent: accent, stateCls: stateCls };
  }

  // Port-led tile: the port number leads (priority) with the protocol beside
  // it and a status pill — no hosts/domains (those live in Domain Reachability).
  // A port shared by several required services (TCP/443) shows an N/M count.
  function card(group) {
    var items = group.items, p0 = items[0], st = rollup(items), pp = portParts(items);
    // Impact-if-blocked bubble on hover/focus/tap: single-service ports surface
    // their impact; a shared port points to the domain column instead of
    // listing hosts. A blocked required port also gets an always-visible
    // issues-panel finding with the same impact text, so the tile stays lean.
    var impact = items.length > 1
      ? "Several required services share this port — see Service Reachability for what each one does."
      : (NET_PORT_IMPACT[p0.purpose] || "");
    var tip = impact ? _impactTipHtml(impact) : "";
    var aria = impact ? ' aria-label="If blocked on the school\'s network: ' + esc(impact) + '"' : "";
    // Visible ? cue matching the Service Reachability rows, right of the port
    // number — the hover/tap target stays the whole tile, the icon just
    // signals the tooltip exists. Status uses the shared badge() pill so port
    // tiles and Service Reachability rows read as one vocabulary.
    var help = impact ? '<span class="domain-help net-port-help" aria-hidden="true">?</span>' : "";
    return '<div class="net-port-card net-tip' + st.stateCls + '" style="--rowaccent:' + st.accent + '" tabindex="0"' + aria + '>' + tip +
      '<div class="net-port-card-head">' +
        '<span class="net-port-card-lead"><span class="net-port-num">' + esc(pp.num) + '</span>' + help + '</span>' +
        badge(st.pillTxt, st.pillCls) +
      '</div>' +
      '<div class="net-port-card-foot">' +
        '<span class="net-port-proto-tag">' + esc(pp.proto) + '</span>' +
      '</div>' +
    '</div>';
  }

  var required = ports.filter(function(p) { return !p.optional; });
  var optional = ports.filter(function(p) { return p.optional; });
  var reqGroups = groupPorts(required);
  var optGroups = groupPorts(optional);
  var reqPass = required.filter(function(p) { return (p.status || "").toLowerCase() === "pass"; }).length;
  var reqBlocked = required.length - reqPass;

  // A required failure that ISN'T a failover rung of a still-healthy stream is
  // a real problem (red). If the only blocks are streaming rungs while Zixi
  // still carries the broadcast, the stream works — show amber, not red.
  var nonStreamBlocked = required.filter(function(p) {
    return (p.status || "").toLowerCase() !== "pass" && STREAM_RUNG_PURPOSES.indexOf(p.purpose) === -1;
  }).length;
  var summary;
  if (required.length === 0) {
    // Guard the degenerate case — don't render "All 0 required reachable".
    summary = '<span class="net-port-summary net-port-summary-opt">No required ports tested</span>';
  } else if (reqBlocked === 0) {
    summary = '<span class="net-port-summary net-port-summary-ok">' + svgIcon("check", 13) + ' All ' + required.length + ' required reachable</span>';
  } else if (nonStreamBlocked === 0 && health.healthy) {
    summary = '<span class="net-port-summary net-port-summary-warn">' + svgIcon("triangle", 13) + ' Streaming OK · ' + health.blocked.length + ' failover path' + (health.blocked.length === 1 ? "" : "s") + ' blocked</span>';
  } else {
    summary = '<span class="net-port-summary net-port-summary-bad">' + svgIcon("triangle", 13) + ' ' + reqBlocked + ' of ' + required.length + ' required blocked</span>';
  }
  // Optional count = tiles shown (a multi-host group or port range is one tile).
  if (optGroups.length) summary += '<span class="net-port-summary-opt">· ' + optGroups.length + ' optional</span>';

  var body = "";
  if (reqGroups.length) body += '<div class="net-port-group-label">Required</div><div class="net-port-grid">' + reqGroups.map(card).join("") + '</div>';
  if (optGroups.length) body += '<div class="net-port-group-label">Optional</div><div class="net-port-grid">' + optGroups.map(card).join("") + '</div>';

  return '<div class="net-port-summary-bar">' + summary + '</div>' + body;
}

// Severity ordering for Network tab issues. Returns a stable rank where
// critical comes first. The previous inline `(o[severity] || 3)` form
// treated critical as falsy (rank 0) and silently fell through to 3,
// which is why issues rendered in the wrong order.
function _netIssueRank(severity) {
  switch (severity) {
    case "critical": return 0;
    case "warning":  return 1;
    case "info":     return 2;
    default:         return 3;
  }
}

function _buildNetIssues(cfg, ports, domains, local, dnsResolution, wifi, tls) {
  var issues = [];
  var gw = (local || {}).gateway;
  var dns = (local || {}).dns;

  // ── Wi-Fi is the internet uplink (Canopy reportWifiConnection) ──
  // Only warn when Wi-Fi is actually carrying the VPU's internet traffic —
  // a real Wi-Fi NIC holds the default route and no wired adapter does.
  // Wi-Fi Direct / hosted-network virtual adapters always show "connected"
  // and must NOT trip this (they aren't the uplink).
  if (wifi && !wifi.error && wifi.uplinkIsWifi) {
    var wifiUplink = (wifi.adapters || []).filter(function(a) {
      return a.isUp && a.hasDefaultRoute && !a.isVirtual;
    });
    issues.push({
      severity: "warning",
      title: "VPU is using Wi-Fi for its internet connection — switch to wired Ethernet",
      body: "The Wi-Fi card is meant for the Pixellot Connect app, not the internet uplink — connect the motherboard Ethernet port to the venue network instead. Wi-Fi adds latency and packet loss that disrupt streaming.",
      details: wifiUplink.map(function(a) {
        var label = a.interfaceDescription || a.name || "Wi-Fi";
        var ssidPart = a.ssid ? " — SSID: " + a.ssid : "";
        return label + ssidPart;
      }),
    });
  }

  // ── Critical: internet plugged into a camera port (not the motherboard) ──
  // Backend tags each adapter's role by PCI bus (motherboard = onboard LOM on
  // bus 0; camera = a port on the multi-port NIC card). A camera port flags
  // only when it's link-Up AND carrying a real gateway — a disconnected port
  // can hold a stale gateway in the route table, so link state is the gate.
  if (cfg && cfg.adapters) {
    var _ipByIdx = {};
    (cfg.ipConfig || cfg.ipConfigurations || []).forEach(function(ipc) { _ipByIdx[ipc.interfaceIndex] = ipc; });
    function _camGw(a) {
      var ipc = _ipByIdx[a.interfaceIndex] || {};
      // PowerShell unwraps a single-element array to a scalar, so a one-gateway
      // adapter arrives as a bare string, not an array — normalize before use.
      var raw = ipc.ipv4DefaultGateway;
      var gws = Array.isArray(raw) ? raw : (raw ? [raw] : []);
      for (var i = 0; i < gws.length; i++) {
        if (gws[i] && String(gws[i]).indexOf("169.254.") !== 0) return gws[i];
      }
      return null;
    }
    var _misplaced = (cfg.adapters || []).filter(function(a) {
      return a.role === "camera" && String(a.status || "").toLowerCase() === "up" && _camGw(a);
    });
    if (_misplaced.length) {
      var _mobo = (cfg.adapters || []).filter(function(a) { return a.role === "motherboard"; });
      var _moboNote = "";
      if (_mobo.length) {
        var _m = _mobo[0];
        var _admin = String(_m.adminStatus || "").toLowerCase(), _st = String(_m.status || "").toLowerCase();
        if (_admin === "down" || _st === "disabled") _moboNote = " The motherboard network port is disabled — enable it in Windows.";
        else if (_st === "disconnected" || _st === "not present" || _st === "down") _moboNote = " The motherboard network port has no cable connected.";
      } else {
        _moboNote = " No motherboard network port was detected — it may be disabled.";
      }
      issues.push({
        severity: "critical",
        title: "Internet is plugged into a camera port, not the motherboard network port",
        body: "The internet/venue connection is on a camera-NIC port, which can disrupt camera discovery and streaming. On a Pixellot VPU it must connect to the motherboard network port — the 4-port NIC is for cameras only." + _moboNote + " Move the cable there and confirm the port is enabled. (Leave the Wi-Fi card enabled — it's for the Pixellot Connect app.)",
        details: _misplaced.map(function(a) { return (a.name || a.interfaceDescription || "?") + " — gateway " + _camGw(a) + " (a camera port)"; }),
      });
    }

    // ── Warning: Wi-Fi card disabled (Pixellot Connect can't reach the VPU) ──
    // A disabled Wi-Fi NIC reports status "Disabled" / adminStatus "Down"; an
    // absent card doesn't appear at all. Skip Wi-Fi Direct / virtual adapters.
    var _wifiOff = (cfg.adapters || []).filter(function(a) {
      if (a.role !== "wifi") return false;
      var d = a.interfaceDescription || "";
      if (d.indexOf("Direct") !== -1 || d.indexOf("Virtual") !== -1) return false;
      return String(a.status || "").toLowerCase() === "disabled" || String(a.adminStatus || "").toLowerCase() === "down";
    });
    if (_wifiOff.length) {
      issues.push({
        severity: "warning",
        title: "Wi-Fi card is disabled — the Pixellot Connect app can't reach this VPU",
        body: "The Wi-Fi card is what the Pixellot Connect app uses to talk to the VPU, so Connect won't find this unit until it's turned back on — enable it in Windows (Network Connections → right-click the Wi-Fi adapter → Enable). The internet uplink should stay on the motherboard Ethernet port; Wi-Fi is only for Connect.",
        details: _wifiOff.map(function(a) { return (a.interfaceDescription || a.name || "Wi-Fi") + " — disabled"; }),
      });
    }
  }

  // ── Gateway ──────────────────────────────────────────────
  if (gw && !gw.reachable) {
    if (!gw.target)
      issues.push({ severity: "critical", title: "VPU has no route to the network",
        body: "The internet adapter has no IPv4 default gateway. Set one (via DHCP or a static address) — the VPU can't reach the internet without it." });
    else if (cfg && cfg.internetReachable)
      // The gateway answers no ICMP, but the VPU is reaching the internet through
      // it — lots of routers/firewalls (and managed venue networks) silently drop
      // pings to the gateway itself while routing traffic fine. internetReachable
      // is authoritative (it has a TCP/443 fallback), so a dropped ping here is
      // filtering, not a fault — explain the red gateway test instead of falsely
      // calling the uplink dead and sending a tech to chase a cable.
      issues.push({ severity: "info", title: "Gateway doesn't answer ping, but traffic is routing normally (" + gw.target + ")",
        body: "The gateway isn't replying to ping (ICMP), so the gateway test above shows red — but the VPU is reaching the internet through it. Many routers and firewalls are set to ignore pings to themselves while still forwarding traffic, so this is expected and needs no action." });
    else
      issues.push({ severity: "critical", title: "VPU can't reach its gateway (" + gw.target + ")",
        body: "Verify the uplink Ethernet cable is seated, the switch port is active, and the VLAN is correct. No traffic will leave the VPU until this is resolved." });
  }
  // Packet loss to the first hop is the real instability signal. First-hop
  // latency varies with switch load/Wi-Fi and is harmless up to ~30 ms, so
  // only flag latency well above a healthy LAN gateway.
  else if (gw && gw.reachable && (gw.lossPercent > 0 || (gw.avgMs != null && gw.avgMs > 30)))
    issues.push({ severity: "warning", title: "Unstable connection to the gateway — " + (gw.avgMs || "?") + " ms latency, " + (gw.lossPercent || 0) + "% loss",
      body: "Try a different switch port, replace the Ethernet cable, or check for broadcast storms on the venue network." });

  // ── DNS server: blocked ICMP vs. real resolution failure ─
  // Is name resolution demonstrably working? (Shared signal — also gates the
  // UDP/53 probe below and the Local Network Health ping card.)
  var _dnsResolving = _dnsResolvingFrom(domains, ports);

  // A 100%-loss ping to the DNS server is NOT proof it's down — ICMP is
  // routinely firewalled on locked-down venue networks while the resolver keeps
  // answering real UDP/53 queries. When resolution is demonstrably working, the
  // dead ping is just blocked ICMP: report it as INFO, not a warning that sends
  // a tech chasing a healthy box. Only call lookups "failing" when nothing
  // resolved either.
  if (dns && !dns.reachable && _dnsResolving)
    issues.push({ severity: "info", title: "DNS server " + dns.target + " isn't answering pings, but name resolution is working",
      body: "The VPU is resolving domains normally — the DNS server just isn't replying to ICMP ping, which many venue firewalls block. No action needed." });
  else if (dns && !dns.reachable)
    issues.push({ severity: "warning", title: "Name lookups are failing (DNS server " + dns.target + " unreachable)",
      body: "Domain resolution will fail. Check DNS server address in adapter settings or try a public DNS (8.8.8.8, 1.1.1.1)." });
  else if (dns && dns.reachable) {
    if (dns.lossPercent > 0)
      issues.push({ severity: "warning", title: "Name lookups are unreliable — " + dns.lossPercent + "% loss to " + dns.target,
        body: "Resolution may be unreliable. Check cable or try a different DNS server." });
    if (dns.avgMs != null && dns.avgMs > 100)
      issues.push({ severity: "info", title: "Name lookups are slow — " + dns.avgMs + " ms to " + dns.target,
        body: "Consider switching to a closer DNS server (8.8.8.8 or 1.1.1.1)." });
  }

  // ── Critical: No internet ────────────────────────────────
  // cfg.internetReachable is authoritative: the backend already treats a
  // passing required TCP/443 service test as proof of internet, so it stays
  // True on locked-down networks that block ICMP/8.8.8.8. If it's explicitly
  // False here, the box genuinely can't reach Pixellot services.
  // Guard on === false (not falsy): when Network config fails to collect, the
  // field is absent — we can't conclude "no internet" from missing data (the
  // dashboard already flags "some checks couldn't complete"), and claiming it
  // sends a tech chasing a cable on a box that's actually online.
  if (cfg && cfg.internetReachable === false) {
    issues.push({ severity: "critical", title: "VPU has no internet connection",
      body: "Check the internet cable and the gateway/router before going further." });
    // Sort and return early — no point checking ports/domains
    issues.sort(function(a, b) { return _netIssueRank(a.severity) - _netIssueRank(b.severity); });
    return issues;
  }

  // ── SSL inspection (certificate substitution) ────────────
  // Test-TlsInspection completes a real TLS handshake to each critical HTTPS
  // service while accepting ANY certificate, then validates what was actually
  // presented against the VPU's trust store. "intercepted" = a middlebox
  // (school firewall doing SSL deep-packet inspection) substituted its own
  // cert. Field signature (Kent School District, 2026-07): video streams
  // fine, Singular graphics never load, and every plain port test is green —
  // which is why this ranks first among the criticals: it explains failures
  // the other checks can't see.
  var tlsRows = (tls && !tls.error && tls.results) || [];
  var tlsIntercepted = tlsRows.filter(function(r) { return r.status === "intercepted"; });
  var tlsHsFail = tlsRows.filter(function(r) { return r.status === "handshake-fail"; });
  var tlsFiltered = tlsRows.filter(function(r) { return r.status === "filtered"; });
  var tlsCertTime = tlsRows.filter(function(r) { return r.status === "cert-time"; });
  var tlsBlocked = tlsRows.filter(function(r) { return r.status === "blocked"; });
  if (tlsIntercepted.length) {
    var interceptorNames = ((tls && tls.interceptorIssuers) || []).join(", ");
    issues.push({
      severity: "critical",
      title: "The venue firewall is intercepting secure connections (SSL inspection)",
      body: "The venue's network is decrypting the VPU's secure traffic and substituting its own certificate"
        + (interceptorNames ? ' — the intercepting device identifies itself as "' + interceptorNames + '"' : "")
        + ". The VPU rejects the substituted certificate, so every service listed below is cut off — each "
        + "line shows what that breaks. Don't expect a clean broadcast until this is fixed, and it can only "
        + "be fixed on the venue's network. Ask the venue's IT team to add these domains "
        + "to the firewall's SSL decryption bypass/exemption list, using a wildcard that covers every "
        + "subdomain plus the bare domain (e.g. *.singular.live AND singular.live). A URL allowlist alone "
        + "is not enough — the traffic must be exempt from decryption.",
      details: tlsIntercepted.map(function(r) {
        var impact = TLS_DOMAIN_IMPACT[r.domain] || "";
        return r.domain + ' — certificate issued by "' + (r.issuerCn || r.issuer || "an untrusted authority")
          + '" instead of a public certificate authority' + (impact ? " — " + impact : "");
      }).concat(tlsHsFail.map(function(r) {
        return r.domain + " — the secure handshake was refused (consistent with the same inspection)";
      })),
    });
  }
  if (tlsFiltered.length) {
    // Category / SNI blocking: the filter reads the hostname from the
    // unencrypted ClientHello, decides the domain is in a blocked category
    // and resets the connection. NO certificate is substituted, which is why
    // this used to fall through to a vague "possible SSL inspection" warning
    // that told a tech nothing actionable (Linewize, Ohio venue 2026-08-19 —
    // eight critical hosts dead, readiness still green). Say the actual
    // thing: the venue's content filter has these domains on a blocklist,
    // and an SSL-decryption bypass will not lift it.
    var vendorNames = ((tls && tls.filterVendors) || []).filter(Boolean).join(" / ");
    var blockUrlRow = tlsFiltered.filter(function(r) { return r.blockPageUrl; })[0];
    issues.push({
      severity: "critical",
      title: (vendorNames ? "Venue web filter (" + vendorNames + ")" : "A web filter on the venue network")
        + " is blocking " + tlsFiltered.length + " Pixellot service"
        + (tlsFiltered.length === 1 ? "" : "s") + " by category",
      body: (vendorNames ? "The venue runs a " + vendorNames + " web filter. " : "")
        + "Each connection below reaches the server and is then dropped the instant the VPU says which site it wants — "
        + "the signature of a content filter matching the hostname against a blocked category. This is NOT certificate "
        + "inspection: the certificates are untouched, so an SSL-decryption bypass on its own will not fix it"
        + (blockUrlRow ? ", and a browser on this network is sent to the filter's own block page instead ("
            + blockUrlRow.blockPageHost + ")" : "")
        + ". Ask the venue's IT team to allow these domains in the web filter's category/URL policy, using a wildcard "
        + "plus the bare domain (e.g. *.singular.live AND singular.live) — a category exception, not just a URL entry. "
        + "While they are in the console, have them exempt the same domains from SSL decryption so the other failure "
        + "mode can't take its place. It can only be fixed on the venue's network.",
      // Per-service impact first, then the block page URL ONCE at the end:
      // it's the single most useful line to paste to venue IT (it carries the
      // rule and category the filter applied), and repeating a 200-character
      // URL on every row buries the impacts it sits next to.
      details: tlsFiltered.map(function(r) {
        var impact = TLS_DOMAIN_IMPACT[r.domain] || "";
        return r.domain + " — connection reset during the secure handshake"
          + (impact ? " — " + impact : "");
      }).concat(blockUrlRow ? ["Evidence to send venue IT — browsing to "
        + blockUrlRow.domain + " on this network lands here: " + blockUrlRow.blockPageUrl] : []),
    });
  }
  if (tlsHsFail.length && !tlsIntercepted.length) {
    // What's left after the reset case is split out: a handshake that died
    // for some other reason — protocol tampering, a downgrade proxy, or an
    // endpoint problem. Genuinely ambiguous, so it stays a warning.
    issues.push({
      severity: "warning",
      title: tlsHsFail.length + " secure service" + (tlsHsFail.length === 1 ? "" : "s") + " failed the TLS handshake",
      body: "The connection reached the server but the secure handshake was refused, and the reason isn't a blocked category or a substituted certificate (Pulse checks for both). A proxy that rewrites or downgrades TLS is the usual cause. If graphics or uploads are failing while video works, ask the venue's IT team what sits between this VPU and the internet on port 443, and have these domains exempted from it.",
      details: tlsHsFail.map(function(r) {
        var impact = TLS_DOMAIN_IMPACT[r.domain] || "";
        return r.domain + (r.detail ? " — " + r.detail : "") + (impact ? " — " + impact : "");
      }),
    });
  }
  if (tlsCertTime.length) {
    // Date-only chain failures are a clock/expiry problem, NOT interception —
    // a wrong VPU clock fails every certificate's validity window.
    issues.push({
      severity: "warning",
      title: tlsCertTime.length + " secure service" + (tlsCertTime.length === 1 ? "" : "s") + " presented a certificate with invalid dates",
      body: "Certificate validity dates don't match this VPU's clock. Check the Time Sync section — a wrong system clock makes every secure connection fail. If the clock is right, the service's certificate has expired.",
      details: tlsCertTime.map(function(r) { return r.domain + " — valid until " + (r.notAfter || "unknown"); }),
    });
  }
  if (tlsBlocked.length) {
    // Unreachable during the cert check — reachability criticals belong to the
    // port/domain panels; this warning exists because several of these hosts
    // (datastream/api/app.singular.live) appear ONLY in this check.
    issues.push({
      severity: "warning",
      title: tlsBlocked.length + " secure service" + (tlsBlocked.length === 1 ? "" : "s") + " couldn't be reached for the certificate check",
      body: "These services didn't answer on port 443, so their certificates couldn't be verified. If they stay unreachable, ask the venue's IT team to allow them through the firewall.",
      details: tlsBlocked.map(function(r) {
        var impact = TLS_DOMAIN_IMPACT[r.domain] || "";
        return r.domain + (impact ? " — " + impact : "");
      }),
    });
  }

  // ── Ports: required failures ─────────────────────────────
  // Pushed before DNS-comparison findings so that within the Critical
  // severity bucket, port blockages rank above DNS issues. The Network
  // tab's sort is stable on severity, so insertion order is the
  // tie-breaker within a bucket.
  function _portDetail(p) {
    var proto = (p.protocol || "TCP").toUpperCase();
    var impact = _netPortImpact(p);
    return proto + "/" + p.port + " (" + (p.purpose || "") + ") to " + (p.host || "remote")
      + (impact ? " — " + impact : "");
  }

  // Streaming verdict — three tiers off the failover chain (Zixi UDP/2088 →
  // Zixi UDP/443 → RTMP TCP/1935). Keep the copy in sync with the findings
  // main.py emits (stream-blocked / stream-degraded-rtmp /
  // stream-resiliency-reduced).
  var stream = _streamingHealth(ports);
  function _rungDetail(p) {
    var role = p.purpose === "Zixi Streaming" ? "the primary streaming connection"
      : p.purpose === "Zixi Backup" ? "the backup streaming connection"
      : "the last-resort RTMP fallback";
    return (p.protocol || "UDP").toUpperCase() + " port " + p.port
      + " to " + (p.host || "the streaming server") + " — " + role;
  }
  if (stream.dark) {
    // (1) Every rung dead — the only tier that earns "can't broadcast".
    issues.push({
      severity: "critical",
      title: "Streaming is blocked — the VPU can't broadcast",
      body: "The venue's network is blocking every path the VPU can use to send live video — the primary and "
        + "backup streaming connections and the last-resort fallback. The game can't broadcast until at least "
        + "one is unblocked. Ask the venue's IT or network team to open the connections below (by domain — "
        + "*.pixellot.stream — on filters that classify traffic by destination, since broadcast servers "
        + "rotate per event).",
      details: stream.blocked.map(_rungDetail),
    });
  } else if (stream.degraded) {
    // (2) Both Zixi/UDP rungs dead, RTMP reachable: games WILL air, but ~4 min
    // late on the unprotected last resort. Urgent, but not "can't broadcast" —
    // that wording burned a support case when a "blocked" venue streamed fine
    // (Olympic WA, 2026-08-18).
    issues.push({
      severity: "critical",
      title: "Streaming is degraded — running on the emergency fallback",
      body: "The venue's network blocks both Zixi streaming connections, so broadcasts fall back to RTMP over "
        + "TCP/1935: games start roughly 4 minutes late and stream with no packet-loss protection. Ask the "
        + "venue's IT or network team to open UDP 2088 and UDP 443 outbound — by domain (*.pixellot.stream) "
        + "on filters that classify traffic by destination, since broadcast servers rotate per event.",
      details: stream.blocked.map(_rungDetail),
    });
  } else if (stream.blocked.length > 0) {
    // (3) Stream healthy on Zixi, but part of the chain is blocked — reduced
    // resiliency, not an outage. Call out when the stream is already riding
    // the backup (primary blocked): one rung from degraded.
    var onBackup = !stream.rungs.some(function(p) {
      return p.purpose === "Zixi Streaming" && (p.status || "").toLowerCase() === "pass";
    });
    issues.push({
      severity: "warning",
      title: onBackup ? "Streaming is riding its backup connection" : "Streaming resiliency is reduced",
      body: (onBackup
        ? "The primary streaming connection (UDP/2088) is blocked, so the stream rides the UDP/443 backup — "
          + "full quality, but one rung from the degraded RTMP fallback. "
        : "The stream is healthy, but part of its failover chain is blocked — less to fall back on if the "
          + "main connection runs into trouble during a game. ")
        + "Ask the venue's IT or network team to unblock the connection"
        + (stream.blocked.length === 1 ? "" : "s") + " below.",
      details: stream.blocked.map(_rungDetail),
    });
  }

  // `_dnsResolving` (hoisted above with the DNS-server ping check) also gates
  // the UDP/53 probe here: a failed probe must NOT claim "can't resolve any
  // hostname" when resolution is clearly working — that probe can target a
  // stale resolver or just go unanswered.

  // Non-streaming required failures (DNS, NFHS, S3, Singular, LogMeIn,
  // pixellot.tv apex) — prerequisites, not redundant paths, so any one blocked
  // is critical on its own. The primary stream and the 443 backup channel are
  // handled above, so exclude both here; and skip a "blocked" DNS probe when
  // resolution is clearly working.
  var reqFailed = (ports || []).filter(function(p) {
    if (p.optional || (p.status || "").toLowerCase() === "pass") return false;
    if (STREAM_RUNG_PURPOSES.indexOf(p.purpose) !== -1) return false;
    if ((p.purpose === "DNS" || String(p.port) === "53") && _dnsResolving) return false;
    return true;
  });
  if (reqFailed.length > 0) {
    issues.push({ severity: "critical",
      title: reqFailed.length + " required service" + (reqFailed.length === 1 ? "" : "s") + " blocked",
      body: "Ensure these ports are allowed by the venue firewall and VLAN policy.",
      details: reqFailed.map(_portDetail) });
  }

  // ── DNS comparison vs Google DNS (PDF #10) ──────────────
  // If 8.8.8.8 resolves but the configured DNS doesn't, the school's
  // internal resolver is blocking Pixellot infrastructure. Pushed AFTER
  // required-ports so the port critical sorts above the DNS critical.
  if (dnsResolution && !dnsResolution.error) {
    var sysBlocked = (dnsResolution.results || []).filter(function(r) { return r.discrepancy === "system-blocked"; });
    if (sysBlocked.length) {
      issues.push({
        severity: "critical",
        title: sysBlocked.length + " domain(s) blocked by configured DNS but reachable via Google DNS (8.8.8.8)",
        body: "The local DNS resolver is filtering or failing on Pixellot infrastructure. Change the VPU's DNS servers to 8.8.8.8 / 8.8.4.4, or ask the venue's network admin to whitelist these hostnames.",
        details: sysBlocked.map(function(r) {
          return r.host + " — system: " + (r.system.error || "no answer") + "; google: " + (r.google.resolvedTo || "—");
        }),
      });
    }
    // Only a redirect (system DNS returns a private/internal IP while Google
    // returns a public one) is worth flagging — that's a captive portal or
    // SSL-inspection proxy. Two different *public* IPs are normal CDN/GeoDNS
    // load balancing and are intentionally NOT flagged.
    var redirects = (dnsResolution.results || []).filter(function(r) { return r.discrepancy === "redirect"; });
    if (redirects.length) {
      issues.push({
        severity: "warning",
        title: redirects.length + " domain(s) redirected by the local DNS to an internal IP",
        body: "The configured resolver returned a private/internal address where Google DNS returned a public one — typically a captive portal or SSL-inspection proxy. Pixellot traffic may be intercepted. Have the venue bypass inspection for these hosts.",
        details: redirects.map(function(r) {
          return r.host + " — system: " + r.system.resolvedTo + " (internal); google: " + r.google.resolvedTo;
        }),
      });
    }
  }

  // Optional-port failures are intentionally NOT surfaced as an issue.
  // They're informational only ("only act if streaming is failing") and were
  // crowding the panel with one bullet per port. The Port Connectivity grid
  // still shows their status; we just don't raise a finding for them.

  // ── Domains: failures ────────────────────────────────────
  var domFailed = (domains || []).filter(function(d) { return (d.status || "").toLowerCase() !== "pass"; });
  var domTotal = (domains || []).length;
  if (domFailed.length > 0) {
    var domDetails = domFailed.map(function(d) {
      var impact = _netDomainImpact(d);
      return d.domain + (impact ? " — " + impact : " — ensure it is whitelisted (firewall, DNS allow-list, SSL inspection bypass)");
    });
    issues.push({ severity: "warning", title: domFailed.length + " of " + domTotal + " domains failed DNS resolution",
      body: "Check DNS server settings on this adapter.",
      details: domDetails });
  }

  // ── Domains: slow resolution ─────────────────────────────
  var slowDns = (domains || []).filter(function(d) { return d.resolutionMs != null && d.resolutionMs > 500 && (d.status || "").toLowerCase() === "pass"; });
  if (slowDns.length > 0) {
    var slowDetails = slowDns.map(function(d) { return d.domain + " — " + d.resolutionMs + " ms"; });
    issues.push({ severity: "info", title: slowDns.length + " domain(s) resolved slowly (>500 ms)",
      body: "Slow DNS can delay connections. Consider switching to a faster DNS server.",
      details: slowDetails });
  }

  // ── Adapter: half-duplex ─────────────────────────────────
  var uStats = cfg.uplinkStats || {};
  if (uStats.fullDuplex === false)
    issues.push({ severity: "warning", title: "Uplink adapter running in half-duplex",
      body: "Set both the VPU NIC and the switch port to auto-negotiate, or hard-set both to 1 Gbps full-duplex." });

  // ── Adapter: interface errors ────────────────────────────
  var ifaceErrors = (uStats.rxErrors || 0) + (uStats.txErrors || 0);
  if (ifaceErrors > 0)
    issues.push({ severity: "warning", title: ifaceErrors + " interface error(s) on uplink adapter",
      body: "RX errors: " + (uStats.rxPacketErrors || 0) + ", RX discards: " + (uStats.rxDiscards || 0) +
            ", TX errors: " + (uStats.txPacketErrors || 0) + ", TX discards: " + (uStats.txDiscards || 0) +
            ". Try replacing the cable, switching ports, or updating the NIC driver." });

  // Sort by severity: critical → warning → info
  issues.sort(function(a, b) { return _netIssueRank(a.severity) - _netIssueRank(b.severity); });
  return issues;
}

// Time Sync card — Windows Time service status + peer list from `w32tm /query`.
// PDF #8 in the Pixellot Troubleshooting Tips.
function _netTimeSyncCard(cfg, ntp, ntpPeers) {
  // Always show the card so techs see drift even when w32tm /query fails.
  var st = (ntpPeers && ntpPeers.status) || {};
  var peers = (ntpPeers && ntpPeers.peers) || [];

  // NTP drift summary (from Test-NtpDrift.ps1). Drift is measured against the
  // configured source; ntp.source reports the server actually used so we can
  // label it unambiguously (it falls back to an independent reference when the
  // box isn't network-synced).
  var driftStatus = (ntp.status || "").toLowerCase();
  var offset = ntp.offsetSeconds != null ? ntp.offsetSeconds + "s" : "—";
  var driftRef = ntp.source ? ' vs ' + esc(ntp.source) : "";
  var driftLabel;
  if (driftStatus === "ok") driftLabel = '<span class="status-pass" style="font-weight:600">In sync (' + esc(offset) + ')</span><span class="text-xs text-pulse-muted">' + driftRef + '</span>';
  else if (driftStatus === "warn") driftLabel = '<span class="status-warn" style="font-weight:600">Drift (' + esc(offset) + ')</span><span class="text-xs text-pulse-muted">' + driftRef + '</span>';
  else if (driftStatus) driftLabel = '<span class="status-fail" style="font-weight:600">Error</span>';
  else driftLabel = "—";

  // Approval chip (mirrors the row in the Adapter card)
  var approvedChip = "";
  if (cfg.ntpSourceApproved === true)
    approvedChip = '<span class="ntp-source-chip ntp-source-ok">Approved</span>';
  else if (cfg.ntpSourceApproved === false)
    approvedChip = '<span class="ntp-source-chip ntp-source-bad">Unapproved</span>';

  var sourceDisplay = st.source || cfg.ntpSource || ntp.source || "—";
  var sourceIpDisplay = st.sourceIp ? st.sourceIp : "—";
  var stratumDisplay = st.stratum != null ? String(st.stratum) : "—";
  var lastSyncDisplay = st.lastSync || "Never synced";

  var peersHtml;
  if (!ntpPeers) {
    peersHtml = '<p class="text-pulse-muted text-sm mt-2">Time-server peer data unavailable.</p>';
  } else if (!peers.length) {
    peersHtml = '<p class="text-pulse-muted text-sm mt-2">No peers configured for the Windows Time service.</p>';
  } else {
    peersHtml =
      '<table class="data-table"><thead><tr>' +
        '<th>Peer</th><th>State</th><th>Stratum</th><th>Last Sync</th><th>Poll</th>' +
      '</tr></thead><tbody>' +
      peers.map(function(p) {
        var stateCls = (p.state || "").toLowerCase() === "active" ? "status-pass" : "text-pulse-muted";
        return '<tr>' +
          '<td class="font-mono text-xs">' + esc(p.name || "—") + '</td>' +
          '<td class="' + stateCls + '">' + esc(p.state || "—") + '</td>' +
          '<td>' + esc(p.stratum != null ? String(p.stratum) : "—") + '</td>' +
          '<td class="text-xs">' + esc(p.lastSyncTimestamp || "Never") + '</td>' +
          '<td class="text-xs text-pulse-muted">' + esc(p.peerPollInterval || "—") + '</td>' +
        '</tr>';
      }).join("") +
      '</tbody></table>';
  }

  // Flag the case where the VPU isn't syncing from any network time source.
  var syncWarning = ntp.networkSynced === false
    ? '<div class="net-iface-stats-warn">' + svgIcon("triangle", 12) +
      ' Clock is not syncing from a network time source (drift measured against ' +
      esc(ntp.source || "an independent reference") + '). Point the VPU at an approved NTP server.</div>'
    : "";

  return `<div class="card">
    ${sectionTitle("clock", "Time Sync (NTP)")}
    <div class="kv-grid">
      ${kvRowHtml("Source", esc(sourceDisplay) + " " + approvedChip)}
      ${kvRow("Source IP", sourceIpDisplay)}
      ${kvRow("Stratum", stratumDisplay)}
      ${kvRow("Last sync", lastSyncDisplay)}
      ${kvRowHtml("Drift status", driftLabel)}
    </div>
    ${syncWarning}
    <div class="net-ntp-peers">
      <div class="net-ntp-peers-title">${svgIcon("activity", 12)} Active Peers</div>
      ${peersHtml}
    </div>
  </div>`;
}

// DNS Resolution card — side-by-side comparison of system DNS vs Google DNS.
// PDF #10: a misconfigured school resolver can block Pixellot infrastructure
// while 8.8.8.8 works fine. Flag those rows clearly.
function _netDnsResolutionCard(dnsResolution, cfg) {
  if (!dnsResolution) {
    return `<div class="card">
      ${sectionTitle("globe", "Name Lookup Check (DNS)")}
      <p class="text-pulse-muted text-sm">DNS comparison data unavailable.</p>
    </div>`;
  }

  var results = dnsResolution.results || [];
  var googleSrv = dnsResolution.googleServer || "8.8.8.8";
  // Pull the configured system DNS server from the network config if we have it.
  var ipConfigs = cfg.ipConfig || cfg.ipConfigurations || [];
  var uplinkName = cfg.uplinkAdapter && cfg.uplinkAdapter.interfaceAlias;
  var uplinkIpCfg = uplinkName ? ipConfigs.find(function(ip) { return ip.interfaceAlias === uplinkName; }) : null;
  var systemDns = uplinkIpCfg && uplinkIpCfg.dnsServers
    ? String(uplinkIpCfg.dnsServers).split(",").map(function(s) { return s.trim(); }).filter(Boolean).join(", ")
    : "system resolver";

  var rowsHtml = results.length
    ? results.map(function(r) {
        var sys = r.system || {};
        var goog = r.google || {};
        function cellHtml(side) {
          if (side.status === "pass") {
            var ms = side.resolutionMs != null ? side.resolutionMs + " ms" : "";
            return '<div class="net-dns-ok">' +
              '<div class="net-dns-ip font-mono">' + esc(side.resolvedTo || "—") + '</div>' +
              '<div class="net-dns-ms text-xs text-pulse-muted">' + esc(ms) + '</div>' +
            '</div>';
          }
          return '<div class="net-dns-fail">' +
            '<div class="net-dns-ip status-fail">Failed</div>' +
            '<div class="net-dns-ms text-xs text-pulse-muted">' + esc(side.error || "no answer") + '</div>' +
          '</div>';
        }
        var rowCls = "";
        var note = "";
        if (r.discrepancy === "system-blocked") {
          rowCls = "net-dns-row-bad";
          note = '<span class="net-dns-note status-fail">School DNS blocking Pixellot</span>';
        } else if (r.discrepancy === "redirect") {
          rowCls = "net-dns-row-warn";
          note = '<span class="net-dns-note status-warn">Redirected to internal IP</span>';
        }
        return '<tr class="' + rowCls + '">' +
          '<td class="font-mono text-xs">' + esc(r.host) + '</td>' +
          '<td>' + cellHtml(sys) + '</td>' +
          '<td>' + cellHtml(goog) + '</td>' +
          '<td>' + note + '</td>' +
        '</tr>';
      }).join("")
    : '<tr><td colspan="4" class="text-pulse-muted text-sm">No DNS comparison data.</td></tr>';

  return `<div class="card">
    ${sectionTitle("globe", "Name Lookup Check (DNS)")}
    <p class="text-pulse-muted text-sm">
      Compares the configured DNS (<span class="font-mono">${esc(systemDns)}</span>)
      against Google DNS (<span class="font-mono">${esc(googleSrv)}</span>) for key Pixellot hosts.
      A row flagged red means the venue's DNS is filtering Pixellot infrastructure.
    </p>
    <table class="data-table net-dns-table"><thead><tr>
      <th>Host</th>
      <th>Configured DNS</th>
      <th>Google DNS (${esc(googleSrv)})</th>
      <th></th>
    </tr></thead><tbody>${rowsHtml}</tbody></table>
  </div>`;
}

// ── Inspection Report (fleet audit roll-up) ──────────────────
// Read-only TRIAGE tab that pools the handful of fields a fleet audit needs
// (identity, OS, network addressing, port-test result) onto one screen, so a
// tech auditing ~15k units doesn't have to hop across the Hardware, Network and
// Camera tabs per unit. NO new data/collector/endpoint — it reads the same
// cached /api/system, /api/network and /api/cameras payloads the other tabs use.

// Port-test verdict from the port results alone, using the same streaming-
// redundancy rules as the Network tab (_streamingHealth / _isRedundantStreamBlock)
// so the two never disagree: a blocked required port is a Fail, unless it's a
// backup stream transport whose sibling is still open (Warning); a blocked
// optional port is a Warning. Returns a severityChip-compatible {sev, label}.
function _portTestVerdict(ports) {
  ports = ports || [];
  if (!ports.length) return { sev: "muted", label: "No data" };
  var health = _streamingHealth(ports);
  var hasFail = false, hasWarn = false;
  ports.forEach(function(p) {
    if ((p.status || "").toLowerCase() === "pass") return;
    if (p.optional || _isRedundantStreamBlock(p, health)) { hasWarn = true; return; }
    hasFail = true;
  });
  if (hasFail) return { sev: "critical", label: "Fail" };
  if (hasWarn) return { sev: "warning", label: "Warning" };
  return { sev: "ok", label: "Pass" };
}

// Windows vs Linux from the OS caption. The current collectors only run on
// Windows VPUs, but key off the caption so a future Linux probe surfaces
// correctly rather than being silently mislabeled.
function _vpuType(osCaption) {
  var c = (osCaption || "").toLowerCase();
  if (c.indexOf("windows") !== -1) return "Windows";
  if (c.indexOf("linux") !== -1 || c.indexOf("ubuntu") !== -1 || c.indexOf("debian") !== -1) return "Linux";
  return null;
}

// Camera frames for the audit. Captured once when the tab opens (cached in
// _irFrames so a re-render doesn't re-fire), and — unlike the Camera tab —
// posted with {force:true}, which bypasses the vpu.exe capture interlock AND
// the cooldown so the audit always gets a frame, even on a live VPU. The frame
// grid itself is the Camera tab's renderer, reused verbatim.
var _irFrames = { state: "idle", data: null };

function _irCaptureFrames() {
  _irFrames = { state: "loading", data: null };
  _irPaintFrames();
  apiPost("/api/cameras/video-test", { force: true }).then(function(res) {
    // Stamp the capture time onto each frame so the cards read "Captured HH:MM"
    // — these are stills, and the audit wants to know how fresh they are.
    if (res && (res.results || []).length) {
      var t = new Date().toLocaleTimeString();
      res.results.forEach(function(r) { r._capturedAt = t; });
    }
    _irFrames = { state: "done", data: res };
    if (currentPage === "inspection-report") _irPaintFrames();
  }).catch(function() {
    _irFrames = { state: "error", data: null };
    if (currentPage === "inspection-report") _irPaintFrames();
  });
}

function _irPaintFrames() {
  var wrap = document.getElementById("ir-frames-wrap");
  if (!wrap) return;
  if (_irFrames.state === "loading") {
    wrap.innerHTML = '<div class="card">' + sectionTitle("camera", "Camera Frames") +
      '<div class="cam-video-running">' + svgIcon("refresh", 14) +
      ' Grabbing a frame from each connected camera…</div></div>';
  } else if (_irFrames.state === "error") {
    wrap.innerHTML = '<div class="card">' + sectionTitle("camera", "Camera Frames") +
      '<div class="cam-video-err">Frame capture failed to run.</div></div>';
  } else if (_irFrames.state === "done") {
    wrap.innerHTML = _camVideoResultsHtml(_irFrames.data, { showControls: false });
  } else {
    wrap.innerHTML = "";
  }
}

// Full report refresh: drop every cached payload it reads and re-capture frames.
function _irRefresh() {
  dataCache.system = null;
  dataCache.network = null;
  dataCache.cameras = null;
  dataCache.scoreconnect = null;
  _irFrames = { state: "idle", data: null };
  renderInspectionReport();
}

function renderInspectionReport() {
  // Three independent payloads back this tab; fetch any that aren't cached yet
  // and re-render as each lands (mirrors the Hardware/Environment split-tab
  // pattern). system/network/cameras are all in PAGE_API, so fetchSection works.
  var system = cached("system");
  var network = cached("network");
  var cameras = cached("cameras");
  var missing = [];
  if (!system) missing.push("system");
  if (!network) missing.push("network");
  if (!cameras) missing.push("cameras");
  if (missing.length) {
    $page().innerHTML = sectionLoading("Inspection Report");
    missing.forEach(function(k) {
      fetchSection(k).then(function() {
        if (currentPage === "inspection-report") renderInspectionReport();
      });
    });
    return;
  }

  // Identity — /api/system (identity) + /api/cameras (system type)
  var id = system.identity || {};
  var cs = id.computerSystem || {};
  var os = id.operatingSystem || {};
  var osCaption = os.caption || null;
  // LMI name = the Pixellot device/broadcast name (always starts with "PXL"),
  // parsed from the agent log's BROADCAST_NAME — NOT the Windows hostname, which
  // can differ. Fall back to the hostname when the agent log isn't readable,
  // matching the dashboard's vpuName-or-hostname treatment.
  var lmiName = (id.pixellot && id.pixellot.vpuName) || cs.name;
  var osText = osCaption ? osCaption + (os.version ? " (" + os.version + ")" : "") : null;
  var camType = cameras.systemType
    || (cameras.expectedMainCameras != null ? cameras.expectedMainCameras + "-camera" : null);

  // Network addressing — uplink adapter, joined across adapters[]/ipConfig[] the
  // same way the Network tab does, so the addressing shown here matches it.
  var cfg = network.config || {};
  var ipConfigs = cfg.ipConfig || cfg.ipConfigurations || [];
  var uplinkName = cfg.uplinkAdapter && cfg.uplinkAdapter.interfaceAlias;
  var uplinkAdapterRow = uplinkName
    ? (cfg.adapters || []).find(function(a) { return a.name === uplinkName; }) || null
    : null;
  var uplinkIpCfg = uplinkName
    ? ipConfigs.find(function(ip) { return ip.interfaceAlias === uplinkName; }) || null
    : null;
  var ipAddr = _first(uplinkIpCfg && uplinkIpCfg.ipv4Address);
  var macAddr = uplinkAdapterRow && uplinkAdapterRow.macAddress;
  var dhcpLabel = uplinkIpCfg && uplinkIpCfg.dhcpEnabled === true ? "DHCP"
    : uplinkIpCfg && uplinkIpCfg.dhcpEnabled === false ? "Static" : null;
  var subnetMask = uplinkIpCfg ? _prefixToMask(uplinkIpCfg.prefixLength) : null;
  var gateway = (cfg.uplinkAdapter && cfg.uplinkAdapter.gateway)
    || _first(uplinkIpCfg && uplinkIpCfg.ipv4DefaultGateway);

  // Port test — /api/network ports, rendered with the shared port component
  // plus a single overall verdict chip.
  var ports = (network.ports && network.ports.results) || [];
  var verdict = _portTestVerdict(ports);

  // Scoreboard — /api/scoreconnect. Fetched lazily so a slow ScoreConnect probe
  // never holds up the core report; the card fills in when it lands. vendor falls
  // back to the legacy SC I/II payload (sc2) when SC III isn't the source.
  var sc = cached("scoreconnect");
  if (!sc) {
    fetchSection("scoreconnect").then(function() {
      if (currentPage === "inspection-report") renderInspectionReport();
    });
  }
  var scCfg = (sc && sc.configuration) || {};
  var scSport = scCfg.sport || null;
  var scVendor = scCfg.vendor || (sc && sc.sc2 && sc.sc2.vendor) || null;
  var scLinkHtml;
  if (!sc) scLinkHtml = '<span class="text-pulse-muted">Checking…</span>';
  else if (sc.scoreLinkConnected === true) scLinkHtml = badge("Connected", "pass");
  else if (sc.scoreLinkConnected === false) scLinkHtml = badge("Not connected", "warn");
  else scLinkHtml = '<span class="text-pulse-muted">Not detected</span>';

  $page().innerHTML = `
    ${pageHeader("Inspection Report", "Every field the fleet audit needs, pooled from the Hardware, Network, Camera and ScoreConnect tabs onto one screen.",
      `<button class="btn-outline btn-ol-blue" onclick="_irRefresh()">
        ${svgIcon("refresh", 14)} Refresh
      </button>`
    )}

    <div class="dash-2col ir-block">
      <div class="card">
        ${sectionTitle("info", "Identity")}
        <div class="kv-grid kv-grid-wide">
          ${kvRow("LMI Name", lmiName)}
          ${kvRow("Camera Type", camType)}
          ${kvRow("Operating System", osText)}
          ${kvRow("VPU Type", _vpuType(osCaption))}
        </div>
      </div>
      <div class="card">
        ${sectionTitle("globe", "Network")}
        <div class="kv-grid kv-grid-wide">
          ${kvRow("IP Address", ipAddr)}
          ${kvRow("MAC Address", macAddr)}
          ${kvRow("Static / DHCP", dhcpLabel)}
          ${kvRow("Subnet Mask", subnetMask)}
          ${kvRow("Gateway", gateway)}
        </div>
      </div>
    </div>

    <div class="dash-2col ir-block">
      <div class="card">
        ${sectionTitle("monitor", "Scoreboard")}
        <div class="kv-grid kv-grid-wide">
          ${kvRow("Sport", scSport)}
          ${kvRow("Vendor", scVendor)}
          ${kvRowHtml("ScoreLink", scLinkHtml)}
        </div>
      </div>
      <div class="card">
        <div class="flex items-center justify-between">
          ${sectionTitle("link", "Network Port Test")}
          ${severityChip(verdict.sev, verdict.label)}
        </div>
        ${_renderPortConnectivity(ports)}
      </div>
    </div>

    <div id="ir-frames-wrap"></div>
  `;

  // Capture frames on first open; a later re-render (e.g. ScoreConnect data
  // landing) just repaints the existing capture rather than firing another.
  if (_irFrames.state === "idle") _irCaptureFrames();
  else _irPaintFrames();
}

function renderNetwork() {
  const data = cached("network");
  if (!data) { $page().innerHTML = sectionLoading("Network"); fetchSection("network"); return; }

  const cfg = data.config || {};
  const domains = data.domains?.results || [];
  const ports = data.ports?.results || [];
  const ntp = data.ntp || {};
  const local = data.local || {};
  const ntpPeers = (data.ntpPeers && !data.ntpPeers.error) ? data.ntpPeers : null;
  const dnsResolution = (data.dnsResolution && !data.dnsResolution.error) ? data.dnsResolution : null;
  const wifi = (data.wifi && !data.wifi.error) ? data.wifi : null;
  const tls = (data.tls && !data.tls.error) ? data.tls : null;
  const ipConfigs = cfg.ipConfig || cfg.ipConfigurations || [];

  const issues = _buildNetIssues(cfg, ports, domains, local, dnsResolution, wifi, tls);

  const hasCrit = issues.some(function(f) { return f.severity === "critical"; });
  const hasWarn = issues.some(function(f) { return f.severity === "warning"; });
  const sevClass = hasCrit ? "critical" : hasWarn ? "warn" : "ok";
  const sevLabel = hasCrit ? "Fail" : hasWarn ? "Warning" : "Pass";
  const statusChip = `<span class="dash-sev-pill dash-sev-${sevClass}"><span class="dash-sev-dot"></span> ${sevLabel}</span>`;

  // Primary adapter — join uplinkAdapter with adapters[] and ipConfig[]
  const uplinkName = cfg.uplinkAdapter?.interfaceAlias;
  const uplinkAdapterRow = uplinkName
    ? (cfg.adapters || []).find(function(a) { return a.name === uplinkName; }) || null
    : null;
  const uplinkIpCfg = uplinkName
    ? ipConfigs.find(function(ip) { return ip.interfaceAlias === uplinkName; }) || null
    : null;
  const adapterLinkState = uplinkAdapterRow
    ? ((uplinkAdapterRow.status || "").toLowerCase() === "up" ? "Up" : uplinkAdapterRow.status || "Unknown")
    : "—";
  const adapterIp = _first(uplinkIpCfg?.ipv4Address) || "—";
  const subnetMask = uplinkIpCfg ? _prefixToMask(uplinkIpCfg.prefixLength) : null;
  const dhcpLabel = uplinkIpCfg?.dhcpEnabled === true ? "DHCP" : uplinkIpCfg?.dhcpEnabled === false ? "Static" : "—";
  const dnsStr = uplinkIpCfg?.dnsServers
    ? String(uplinkIpCfg.dnsServers).split(",").map(function(s) { return s.trim(); }).filter(Boolean).join(", ")
    : "—";

  // Uplink adapter stats (duplex)
  const uplinkStats = cfg.uplinkStats || {};
  const duplexLabel = uplinkStats.fullDuplex === true ? "Full Duplex" : uplinkStats.fullDuplex === false ? "Half Duplex" : null;

  // Wired Ports — error/discard counters for EVERY wired NIC, not just the
  // uplink. A multi-NIC VPU has the motherboard port plus the camera card; a
  // bad cable or dirty switch port on a non-uplink port used to be invisible.
  // Role is tagged by the backend (PCI bus: motherboard = onboard LOM bus 0).
  // Sorted so the table reads top-down: uplink first, then the camera card's
  // ports in numeric order (#13, #14, …) instead of WMI enumeration order.
  const wiredPorts = (cfg.adapters || []).filter(function(a) {
    return String(a.physicalMediaType || "").toLowerCase().indexOf("802.3") !== -1;
  }).sort(function(a, b) {
    var rank = { motherboard: 0, camera: 1 };
    var ra = rank[a.role] != null ? rank[a.role] : 2;
    var rb = rank[b.role] != null ? rank[b.role] : 2;
    if (ra !== rb) return ra - rb;
    var da = a.interfaceDescription || a.name || "";
    var db = b.interfaceDescription || b.name || "";
    return da.localeCompare(db, undefined, { numeric: true });
  });
  const wiredPortsCard = wiredPorts.length ? `
    <div class="card">
      ${sectionTitle("link", "Wired Ports")}
      <p class="text-pulse-muted text-xs mb-3">Error and discard counters for every wired network port (cumulative since boot). Non-zero values usually mean a bad cable, a dirty switch port, or a NIC driver issue.</p>
      <table class="data-table"><thead><tr>
        <th>Port</th><th>Link</th><th>Speed</th><th>RX Err</th><th>TX Err</th>
      </tr></thead><tbody>
      ${wiredPorts.map(function(a) {
        var roleLabel = a.role === "motherboard" ? "Motherboard (uplink)" : a.role === "camera" ? "Camera NIC" : "Wired";
        var up = String(a.status || "").toLowerCase() === "up";
        var rxe = a.rxErrors || 0, txe = a.txErrors || 0;
        var rxNull = a.rxErrors == null, txNull = a.txErrors == null;
        return `<tr>
          <td><div class="font-semibold">${esc(roleLabel)}</div><div class="text-xs text-pulse-muted">${esc(a.interfaceDescription || a.name || "")}</div></td>
          <td><span style="color:${up ? "var(--c-accent-green)" : "var(--c-muted)"};font-weight:600">${esc(up ? "Up" : (a.status || "—"))}</span></td>
          <td class="text-xs">${esc(a.linkSpeed || "—")}</td>
          <td class="font-mono ${rxe > 0 ? "status-warn" : ""}">${rxNull ? "—" : esc(String(rxe))}</td>
          <td class="font-mono ${txe > 0 ? "status-warn" : ""}">${txNull ? "—" : esc(String(txe))}</td>
        </tr>`;
      }).join("")}
      </tbody></table>
    </div>` : "";

  const issuesPanel = issues.length ? `
    <div class="card">
      <div class="af-header">
        ${svgIcon("triangle", 16)}
        <span class="af-label">ISSUES & RECOMMENDATIONS</span>
        <span class="af-count-badge">${issues.length} item${issues.length !== 1 ? "s" : ""}</span>
      </div>
      <div class="net-issues-list">
        ${issues.map(function(item) {
          var sc = item.severity === "critical" ? "sev-chip-crit" : item.severity === "warning" ? "sev-chip-warn" : item.severity === "info" ? "sev-chip-info" : "sev-chip-ok";
          var borderCls = item.severity === "critical" ? "net-issue-critical" : item.severity === "warning" ? "net-issue-warn" : "net-issue-info";
          var detailsHtml = "";
          if (item.details && item.details.length) {
            detailsHtml = '<ul class="net-issue-details">' +
              item.details.map(function(d) { return '<li>' + esc(d) + '</li>'; }).join("") +
            '</ul>';
          }
          return '<div class="net-issue-row ' + borderCls + '">' +
            '<span class="sev-chip ' + sc + '">' + esc(item.severity.toUpperCase()) + '</span>' +
            '<div class="net-issue-text">' +
              '<div class="net-issue-title">' + esc(item.title) + '</div>' +
              '<div class="net-issue-body">' + esc(item.body) + '</div>' +
              detailsHtml +
            '</div>' +
          '</div>';
        }).join("")}
      </div>
    </div>` : "";

  $page().innerHTML = `
    ${pageHeader("Network Test", "Internet connection, name lookups (DNS), time sync, and whether the VPU can reach the services it needs.",
      statusChip + `<button id="net-run-test-btn" class="btn-outline btn-ol-blue" onclick="_rerunNetworkTests(this)">
        ${svgIcon("activity", 14)} <span>Run Test</span>
      </button>`
    )}

    ${issuesPanel}

    <!-- Connectivity: Ports (left) | Domains (right) in one panel -->
    <div class="card">
      <div class="net-conn-grid">
        <div class="net-conn-col">
          ${sectionTitle("link", "Port Connectivity")}
          <p class="net-conn-hint">Hover or tap a tile to see what stops working if the school's network blocks that port.</p>
          ${_renderPortConnectivity(ports)}
        </div>
        <div class="net-conn-col">
          ${sectionTitle("wifi", "Service Reachability")}
          <p class="net-conn-hint">Hover or tap a <span class="domain-help net-conn-hint-q">?</span> to see what stops working if the school's network blocks that service.</p>
          ${domains.length ? `
            <div class="domain-list">
              ${domains.map(function(d) {
                const ok = (d.status || "").toLowerCase() === "pass";
                var dnsTime = d.resolutionMs != null ? d.resolutionMs + " ms" : "";
                var dnsSlow = d.resolutionMs != null && d.resolutionMs > 200;
                var dotColor = ok ? "var(--c-accent-green)" : "var(--c-accent-red)";
                // "Impact if blocked" lives on an explicit ? help icon next to
                // the domain: a styled bubble on hover/focus/tap while the row
                // passes. Once the row FAILS, hover is the wrong delivery —
                // techs screenshot this panel for the school's IT — so the
                // impact renders inline under the failing row instead.
                var impact = _netDomainImpact(d);
                var help = impact && ok
                  ? `<span class="domain-help net-tip" tabindex="0" aria-label="If blocked on the school's network: ${esc(impact)}">?${_impactTipHtml(impact)}</span>`
                  : "";
                var impactLine = impact && !ok
                  ? `<div class="domain-impact">${svgIcon("triangle", 11)} While this is blocked: ${esc(impact)}</div>`
                  : "";
                return `<div class="domain-row">
                  <span class="domain-dot" style="background:${dotColor}"></span>
                  <span class="domain-name"><span class="domain-name-text">${esc(d.domain)}</span>${help}</span>
                  <span class="domain-ip">${esc(d.resolvedTo) || "—"}</span>
                  <span class="domain-dns-time font-mono${dnsSlow ? ' status-warn' : ''}">${esc(dnsTime)}</span>
                  ${statusBadge(d.status)}
                  ${impactLine}
                </div>`;
              }).join("")}
            </div>
          ` : '<p class="text-pulse-muted text-sm">No DNS data</p>'}
        </div>
      </div>
    </div>

    <!-- Local Network Health -->
    <div class="card">
      <div class="net-ping-toolbar">
        ${sectionTitle("activity", "Local Network Health")}
        <div id="net-ping-controls" class="net-ping-btns">
          <span class="text-xs text-pulse-muted" style="margin-right:4px">Ping count</span>
          <span id="net-ping-spinner" class="net-ping-spin" style="display:none">${svgIcon("refresh", 14)}</span>
          <button class="net-ping-preset${!local.gateway && !local.dns ? " net-ping-preset-active" : ""}" onclick="runLocalPing(4)">4</button>
          <button class="net-ping-preset" onclick="runLocalPing(10)">10</button>
          <button class="net-ping-preset" onclick="runLocalPing(20)">20</button>
          <button class="net-ping-preset" onclick="runLocalPing(50)">50</button>
          <button class="net-ping-preset net-ping-cont" onclick="runLocalPing(0)">Continuous</button>
          <button id="net-ping-stop-btn" class="net-ping-stop btn-outline btn-ol-blue" style="display:none" onclick="stopLocalPing()">
            ${svgIcon("square", 12)} Stop
          </button>
        </div>
      </div>
      <div id="net-ping-results" class="net-ping-grid">
        ${local && local.error
          ? '<p class="text-sm status-fail">Local network test failed: ' + esc(local.message || 'unknown error') + '</p>'
          : (local.gateway || local.dns)
            ? _pingCardHtml(local.gateway, false) + _pingCardHtml(local.dns, _dnsResolvingFrom(domains, ports))
            : '<p class="text-pulse-muted text-sm mt-2">Select a ping count above to test local network health.</p>'}
      </div>
    </div>

    <!-- Internet Adapter & IP Configuration (full width; domains moved up) -->
    <div class="card">
      ${sectionTitle("globe", "Internet Adapter & IP Configuration")}
        ${uplinkAdapterRow ? `
          <div class="font-semibold text-white mb-1">${esc(uplinkAdapterRow.name)}</div>
          <div class="text-pulse-muted text-xs mb-3">${esc(uplinkAdapterRow.interfaceDescription || "")}</div>` : `
          <p class="text-pulse-muted text-sm mb-3">No internet-bound adapter detected.</p>`}
        <div class="net-adapter-grid">
          <div class="net-adapter-section">
        <div class="net-iface-stats-title">IP Configuration</div>
        <div class="kv-grid">
          ${kvRow("IP address", adapterIp)}
          ${kvRow("Subnet mask", subnetMask || "—")}
          ${kvRowHtml("Assignment", (function() {
            // Canopy getIpStaticOrDynamic adoption — render the value as a
            // colored chip so the assignment mode pops at a glance.
            if (uplinkIpCfg?.dhcpEnabled === true)
              return '<span class="dhcp-chip dhcp-chip-dynamic">DHCP</span>';
            if (uplinkIpCfg?.dhcpEnabled === false)
              return '<span class="dhcp-chip dhcp-chip-static">Static</span>';
            return "—";
          })())}
          ${kvRow("Gateway", cfg.uplinkAdapter?.gateway || "—")}
          ${kvRow("DNS", dnsStr)}
        </div>
          </div>
          <div class="net-adapter-section">
        <div class="net-iface-stats-title">Link</div>
        <div class="kv-grid">
          ${kvRow("MAC address", uplinkAdapterRow?.macAddress || "—")}
          ${kvRowHtml("Link state", uplinkAdapterRow
            ? `<span style="color:${adapterLinkState === "Up" ? "var(--c-accent-green)" : "var(--c-muted)"};font-weight:600">${esc(adapterLinkState)}</span>`
            : "—")}
          ${kvRow("Link speed", uplinkAdapterRow?.linkSpeed || "—")}
          ${duplexLabel ? kvRowHtml("Duplex", duplexLabel === "Half Duplex"
            ? '<span class="status-warn" style="font-weight:600">Half Duplex</span>'
            : '<span style="color:var(--c-accent-green);font-weight:600">Full Duplex</span>') : ""}
        </div>
          </div>
          <div class="net-adapter-section">
        <div class="net-iface-stats-title">Connectivity</div>
        <div class="kv-grid">
          ${kvRowHtml("Internet", cfg.internetReachable
            ? '<span class="status-pass">Reachable</span>'
            : '<span class="status-fail">Unreachable</span>')}
          ${kvRow("Tested host", cfg.testedHost || "—")}
        </div>
          </div>
          <div class="net-adapter-section">
        <div class="net-iface-stats-title">Time Sync</div>
        <div class="kv-grid">
          ${kvRowHtml("NTP server", (function() {
            var src = cfg.ntpSource || ntp.source || "";
            if (!src) return "—";
            // PDF #9: the four *.us.pool.ntp.org hosts are the only approved sources.
            // Show a green Approved chip when matched, amber Unapproved chip otherwise.
            var approved = cfg.ntpSourceApproved;
            var approvedList = (cfg.ntpSourceApprovedList || []).join(", ");
            var chip;
            if (approved === true) {
              chip = '<span class="ntp-source-chip ntp-source-ok" title="Matches Pixellot approved NTP source list">Approved</span>';
            } else if (approved === false) {
              chip = '<span class="ntp-source-chip ntp-source-bad" title="Not in Pixellot approved list. Expected one of: ' + esc(approvedList) + '">Unapproved</span>';
            } else {
              chip = "";
            }
            var tooltip = "The server the VPU syncs its clock from. Drift is measured against this same source (see Time Sync under Advanced Diagnostics). The UDP/123 port test separately checks reachability to prod-echo.pixellot.tv.";
            return '<span title="' + esc(tooltip) + '" style="white-space:nowrap">' + esc(src) + '</span> ' + chip;
          })())}
          ${kvRowHtml("NTP status", (function() {
            var s = (ntp.status || "").toLowerCase();
            var offset = ntp.offsetSeconds != null ? " (" + ntp.offsetSeconds + "s)" : "";
            if (s === "ok") return '<span class="status-pass" style="font-weight:600">OK' + esc(offset) + '</span>';
            if (s === "warn") return '<span class="status-warn" style="font-weight:600">DRIFT' + esc(offset) + '</span>';
            if (!ntp.status) return "—";
            return '<span class="status-fail" style="font-weight:600">ERROR</span>';
          })())}
        </div>
          </div>
        </div>
      </div>

    ${wiredPortsCard}

    <!-- Speed Test (Speedtest.net paste-in) — promoted out of Advanced -->
    <div class="card">
      <div class="net-ping-toolbar">
        ${sectionTitle("zap", "Speed Test")}
        <div class="net-ping-btns">
          <a href="https://www.speedtest.net" target="_blank" rel="noopener" class="btn-outline btn-ol-blue" style="text-decoration:none">
            ${svgIcon("globe", 14)} Open Speedtest.net
          </a>
        </div>
      </div>
      <div id="net-speed-ui">
        <p class="text-pulse-muted text-sm mb-3">Run a test at speedtest.net, then paste the result URL below.</p>
        <div class="net-speed-input-row">
          <input id="net-speed-input" type="text" class="net-speed-input" placeholder="https://www.speedtest.net/result/123456789 or result ID" onkeydown="if(event.key==='Enter'){event.preventDefault();_fetchSpeedtest();}">
          <button id="net-speed-fetch-btn" class="btn-outline btn-ol-blue" onclick="_fetchSpeedtest()">
            ${svgIcon("refresh", 14)} Fetch Result
          </button>
        </div>
        <div id="net-speed-results"></div>
      </div>
    </div>

    <!-- Advanced Diagnostics Toggle -->
    <div class="net-adv-toggle" onclick="_toggleAdvNet()">
      <div class="net-adv-toggle-inner">
        <span class="net-adv-toggle-icon" id="net-adv-arrow">${svgIcon("chevron", 14)}</span>
        <span class="net-adv-toggle-label">Advanced Diagnostics</span>
        <span class="text-xs text-pulse-muted">Secure-connection checks, time sync, name-lookup checks, traffic capture, route tracing, and live monitoring</span>
      </div>
    </div>

    <!-- Advanced Diagnostics (collapsed by default) -->
    <div id="net-adv-section" class="net-adv-section net-adv-collapsed">

      <!-- Secure Connections — the two ways a venue middlebox kills HTTPS:
           a cert issued by anything other than a trusted public CA means the
           firewall is DECRYPTING the connection (Kent SD signature), while a
           handshake reset means a content filter has the domain on a BLOCKED
           CATEGORY list (Linewize signature). Different fixes — the card has
           to say which one, or IT checks the wrong console. -->
      <div class="card">
        ${sectionTitle("shield", "Secure Connections (Filtering & SSL Inspection)")}
        <p class="text-pulse-muted text-xs mb-3">What happens when the VPU opens each service's HTTPS connection. Port tests pass in both failure cases below, which is why they need their own check.<br>
        <strong>Blocked by filter</strong> — the connection is reset as soon as the VPU names the site: a content filter has the domain on a blocked category list. Fix: venue IT allows the domain in the web filter's category/URL policy (an SSL bypass will not do it).<br>
        <strong>Intercepted</strong> — the firewall substituted its own certificate and is decrypting the traffic. Fix: venue IT exempts the domain from SSL decryption (bypass list), not just an allowlist entry.<br>
        Either way, use a wildcard <em>and</em> the bare domain (e.g. *.singular.live AND singular.live).</p>
        ${(tls && tls.results && tls.results.length) ? `
          <table class="data-table"><thead><tr>
            <th>Service</th><th>Certificate issued by / why it failed</th><th>Status</th>
          </tr></thead><tbody>
          ${tls.results.map(function(r) {
            var st = (r.status || "").toLowerCase();
            var bad = st === "intercepted" || st === "blocked" || st === "filtered";
            // A filtered host never presents a certificate, so the cert column
            // carries the more useful fact instead: who blocked it.
            var issuerLabel = st === "filtered"
              ? (r.filterVendor
                  ? "Blocked by " + r.filterVendor + (r.blockPageHost ? " (" + r.blockPageHost + ")" : "")
                  : "No certificate — connection reset before the handshake finished")
              : (r.issuerCn
                  ? r.issuerCn + (r.issuerOrg && r.issuerOrg !== r.issuerCn ? " — " + r.issuerOrg : "")
                  : (st === "pass" ? "—" : (r.detail || "—")));
            return `<tr>
              <td><div class="font-semibold">${esc(r.domain)}</div><div class="text-xs text-pulse-muted">${esc(r.purpose || "")}</div></td>
              <td class="text-xs${bad ? " status-fail" : ""}" title="${esc(r.issuer || "")}">${esc(issuerLabel)}</td>
              <td>${_tlsBadge(r.status)}</td>
            </tr>`;
          }).join("")}
          </tbody></table>
        ` : '<p class="text-pulse-muted text-sm mt-2">No certificate results — run the network test again.</p>'}
      </div>

      ${_netTimeSyncCard(cfg, ntp, ntpPeers)}

      ${_netDnsResolutionCard(dnsResolution, cfg)}

      <!-- Packet Capture -->
      <div class="card">
        <div class="net-ping-toolbar">
          ${sectionTitle("shield", "Network Traffic Capture (advanced)")}
          <div id="net-capture-controls" class="net-ping-btns">
            <button class="net-ping-preset" onclick="_runCapture(10)">10s</button>
            <button class="net-ping-preset net-ping-preset-active" onclick="_runCapture(30)">30s</button>
            <button class="net-ping-preset" onclick="_runCapture(60)">60s</button>
            <span id="net-capture-status" class="net-ping-spin" style="display:none">${svgIcon("refresh", 14)}</span>
          </div>
        </div>
        <p class="text-pulse-muted text-sm">Watches outbound streaming traffic for dropped or retried connections. (Uses Windows pktmon on ports 443, 1935, 80, and UDP/2088.)</p>
        <p class="net-capture-admin-note">${svgIcon("shield", 12)} Requires Pulse to be running as administrator.</p>
        <div id="net-capture-results"></div>
      </div>

      <!-- Traceroute -->
      <div class="card">
        <div class="net-ping-toolbar">
          ${sectionTitle("share", "Traceroute")}
          <div class="net-ping-btns">
            <input id="net-trace-target" type="text" class="net-trace-input" placeholder="pixellot.tv" value="pixellot.tv" onkeydown="if(event.key==='Enter'){event.preventDefault();_runTraceroute(this.value.trim()||'pixellot.tv');}">
            <button id="net-trace-btn" class="btn-outline btn-ol-blue" onclick="_runTraceroute(document.getElementById('net-trace-target').value.trim()||'pixellot.tv')">
              ${svgIcon("activity", 14)} Run
            </button>
          </div>
        </div>
        <div id="net-trace-results">
          <p class="text-pulse-muted text-sm mt-2">Click Run to trace the network path to a target host.</p>
        </div>
      </div>

      <!-- Live Network Health (WebSocket-driven) -->
      <div class="card">
        <div class="net-ping-toolbar">
          ${sectionTitle("zap", "Live Network Health")}
          <div class="net-live-indicator">
            <span class="net-live-dot"></span> <span class="text-xs text-pulse-muted">Live via WebSocket</span>
          </div>
        </div>
        <div id="net-live-body">
          <p class="text-pulse-muted text-sm">Waiting for live data…</p>
        </div>
      </div>

    </div>
  `;

  // Seed live health panel if we already have WebSocket data
  if (_liveNetHealth) _renderLiveNetHealth(_liveNetHealth);
}

// ── Cameras ──────────────────────────────────────────────────

var _camerasRefreshTimer = null;
var _camerasFailCount = 0;  // consecutive /api/cameras failures during live refresh
var _camLastSignature = null;  // structural fingerprint of last rendered cameras
var _camPoeLastSignature = null;  // separate PoE fingerprint — watts change every tick, so PoE is patched in place and must not ride _camLastSignature
var _camNicLayout = "h";       // 4-port LED diagram orientation: 'h' upright (ports L→R) / 'v' on-side (ports top→bottom)
var _camLastVideo = null;      // last captured frame set, restored across re-renders (with a capture time so it's never mistaken for live)

// Structural fingerprint of the camera data — everything that affects the
// rendered layout EXCEPT the volatile RX/TX byte counters (which tick every
// few seconds). The live refresh only does a full DOM rebuild when this
// changes; otherwise it surgically updates the byte counters in place, so
// an open Details panel never flickers during steady-state polling.
function _camSignature(data) {
  var ports = (data && data.ports) || [];
  var portSig = ports.map(function(p) {
    var cams = (p.camerasDetected || []).map(function(c) {
      return [c.ip, c.mac, c.cgiMac, c.role, c.identitySource, c.modelNumber, c.cgiConfirmed].join("|");
    }).join(",");
    var errs = (p.rxPacketErrors || 0) + (p.txPacketErrors || 0) + (p.rxDiscards || 0) + (p.txDiscards || 0);
    return [p.portLabel, p.name, p.isUp, p.isOcr, p.isDegraded, p.connecting, p.cameraLabel,
            p.linkSpeedMbps, p.expectedSpeedMbps, p.fullDuplex, p.hasInternetUplink,
            errs, cams].join("~");
  }).join("||");
  var findSig = ((data && data.findings) || []).map(function(f) {
    return f.severity + ":" + f.title;
  }).join(";");
  return portSig + "##" + findSig;
}

function _camDetailKv(label, val) {
  if (!val && val !== 0) return '';
  return '<div class="kv-mini"><span>' + esc(String(label)) + '</span><span class="font-mono">' + esc(String(val)) + '</span></div>';
}

// Camera TV mode (CGI ImageSource.I0.Video.DetectedType) → friendly label.
// e.g. "ntsc_60" → "NTSC · 60 Hz", "pal_50" → "PAL · 50 Hz".
function _fmtTvMode(tv) {
  if (!tv) return null;
  var m = String(tv).toLowerCase().match(/^(ntsc|pal)[_-]?(\d+)?/);
  if (!m) return tv;
  return m[1].toUpperCase() + (m[2] ? " · " + m[2] + " Hz" : "");
}

function _camStreamBlock(label, s) {
  if (!s || (!s.codec && !s.resolution && !s.framerate)) return '';
  var enabled = s.enabled !== undefined ? (s.enabled === "yes" || s.enabled === true) : true;
  return '<div class="cam-detail-group">' +
    '<div class="cam-detail-group-title">' + esc(label) +
      (!enabled ? ' <span class="status-warn">Disabled</span>' : '') +
    '</div>' +
    _camDetailKv("Codec", s.codec) +
    _camDetailKv("Resolution", s.resolution) +
    _camDetailKv("Framerate", s.framerate ? s.framerate + " fps" : null) +
  '</div>';
}

function _camPortTile(port, index, ctx) {
  if (!port) {
    return `<div class="cam-port-tile cam-port-empty">
      <div class="cam-port-header">
        <span class="cam-port-num">Port ${index + 1}</span>
        <span class="cam-port-state">${badge("Not detected", "muted")}</span>
      </div>
    </div>`;
  }
  const p = port;
  const speed = p.linkSpeedMbps
    ? p.linkSpeedMbps >= 1000 ? (p.linkSpeedMbps / 1000) + " Gbps" : p.linkSpeedMbps + " Mbps"
    : "No link";
  // Link state lives in a shared badge() pill (same status vocabulary as the
  // Network tab's port tiles); the dot row below carries only the speed.
  // Down ports get a *reason*, not just "Down", + triage guidance below.
  var downLabelMap = { disabled: "Disabled", driver: "Driver error", "no-link": "No link" };
  let stateTxt, stateCls, dotCls;
  if (!p.isUp) { stateTxt = downLabelMap[p.downReason] || "Down"; stateCls = "fail"; dotCls = "cam-dot-down"; }
  else if (p.connecting) { stateTxt = "Connecting"; stateCls = "info"; dotCls = "cam-dot-connecting"; }
  else if (p.isDegraded) { stateTxt = "Degraded"; stateCls = "warn"; dotCls = "cam-dot-warn"; }
  // Fully linked → always green. OCR vs Main is shown by the role badge, so
  // the status dot just signals link health (green = established) and never
  // lingers blue, which reads as "still connecting".
  else { stateTxt = "Linked"; stateCls = "pass"; dotCls = "cam-dot-up"; }
  // Speed rides the dot row only while the port is up; a down port's state is
  // fully told by the badge + the triage guidance block.
  var speedRow = p.isUp && p.linkSpeedMbps
    ? `<div class="cam-port-status"><span class="cam-dot ${dotCls}"></span><span class="text-sm">${esc(speed)}</span></div>`
    : "";

  const cams = p.camerasDetected || [];
  var camLabel = p.cameraLabel;
  // Badge color: OCR → blue, Main Camera N → teal, generic Camera/Pixellot → muted.
  var camLabelCls;
  if (p.isOcr) camLabelCls = "badge-ol-info";
  else if (camLabel && camLabel.indexOf("Main") === 0) camLabelCls = "badge-ol-main";
  else camLabelCls = "badge-ol-muted";
  // The venue/internet cable in a camera port: the tile itself calls out the
  // mis-wired port (red border + INTERNET UPLINK badge + move-the-cable note)
  // so the tech can spot which physical port to fix without reading findings.
  var hasUplink = !!p.hasInternetUplink;
  var uplinkNote = hasUplink
    ? '<div class="cam-uplink-callout">' + svgIcon("alert", 12) + ' <span>Wrong port — this one is carrying the venue’s internet connection'
      + (p.uplinkGateway ? ' (gateway ' + esc(p.uplinkGateway) + ')' : '')
      + '. Move this cable to the motherboard network port; the 4-port camera card is for cameras only.</span></div>'
    : '';
  // Header carries only the port number + state pill, so the pill sits at the
  // same top-right spot on every tile; the (variable-width) role badge gets
  // its own row below and can never push the status onto a second line.
  return `<div class="cam-port-tile ${!p.isUp ? "cam-port-down" : hasUplink ? "cam-port-uplink" : p.isDegraded ? "cam-port-degraded" : "cam-port-active"}">
    <div class="cam-port-header">
      <span class="cam-port-num">Port ${index + 1}</span>
      <span class="cam-port-state">${badge(stateTxt, stateCls)}</span>
    </div>
    ${hasUplink ? '<div class="cam-port-role"><span class="badge-ol badge-ol-uplink">Internet Uplink</span></div>'
      : camLabel ? '<div class="cam-port-role"><span class="badge-ol ' + camLabelCls + '">' + esc(camLabel) + '</span></div>' : ''}
    <div class="cam-port-name">${esc(p.name)}</div>
    ${speedRow}
    <div class="cam-port-detail">
      <div class="kv-mini"><span>RX / TX</span><span id="cam-rxtx-${index}">${formatBytes(p.rxBytes)} / ${formatBytes(p.txBytes)}</span></div>
    </div>
    ${cams.length > 0 ? (() => {
      var c = cams[0];
      var displayModel = c.modelNumber || (c.model && c.model !== "IP Camera" ? c.model : null);
      return `<div class="cam-detected">
        <div class="cam-detected-label">Pixellot camera detected</div>
        <div class="cam-detected-entry">
          <span class="font-mono cam-entry-ip">${esc(c.ip)}</span>
          <span class="font-mono text-pulse-muted cam-entry-mac">${esc(c.mac)}</span>
          ${displayModel ? '<span class="cam-model-label">' + esc(displayModel) + '</span>' : ''}
          <span class="cam-entry-source text-pulse-muted">${esc(c.identitySource || '')}</span>
        </div>
        ${cams.length > 1 ? '<div class="cam-entry-source text-pulse-muted">+' + (cams.length - 1) + ' more camera' + (cams.length > 2 ? 's' : '') + ' on this port</div>' : ''}
      </div>
      <div class="cam-details-toggle"><a class="cam-hw-pointer" href="#camera-hardware" onclick="navigate('camera-hardware');return false;">${svgIcon("info", 12)} Hardware details</a></div>`;
    })()
    : p.connecting ? '<div class="cam-connecting-note">' + svgIcon("refresh", 12) + ' Establishing link — waiting for camera…</div>'
    : !p.isUp ? _camDownGuidanceHtml(p, ctx)
    : hasUplink ? ''
    : '<div class="cam-no-detect">No Pixellot cameras on this port</div>'}
    ${uplinkNote}
  </div>`;
}

// Triage guidance for a down port: explain the detected reason and, for the
// "no signal" case, use sibling ports to point at card vs cable/camera.
function _camDownGuidanceHtml(p, ctx) {
  var reason = p.downReason || "down";
  var msg;
  if (reason === "disabled") {
    msg = "Adapter is disabled in Windows — enable it in Network Connections to bring this port back.";
  } else if (reason === "driver") {
    msg = "The NIC driver reports a fault — reinstall the Intel network driver, then re-check.";
  } else {
    // no-link / generic: nothing detected on the wire.
    var othersUp = ctx && ctx.total > 1 && ctx.upCount >= 1;
    var allDown = ctx && ctx.total > 1 && ctx.upCount === 0;
    if (allDown) {
      msg = "No signal — and every camera port is down. This points to the network card, its driver, or power to the camera bank — not one cable.";
    } else if (othersUp) {
      msg = "Check this cable (both ends) and the camera's power, then run Camera Connection Troubleshooting. The other ports are linked, so the problem is likely just this cable, camera, or port — not a card-wide failure.";
    } else {
      msg = "No signal detected. Check the cable is seated both ends and the camera has power, then use Camera Connection Troubleshooting.";
    }
  }
  return '<div class="cam-down-guide">' + svgIcon("alert", 12) + ' <span>' + esc(msg) + '</span></div>';
}

function _camFindingsHtml(findings) {
  if (!findings.length) return "";
  return `<div class="card" id="cam-findings">
    ${sectionTitle("alert-circle", findings.length + " finding" + (findings.length !== 1 ? "s need" : " needs") + " attention")}
    ${findings.map(f => `
      <div class="cam-finding-row cam-finding-row-${esc(f.severity)}">
        <div class="cam-finding-header">
          <span class="cam-finding-pill cam-finding-pill-${esc(f.severity)}">${esc(f.severity.toUpperCase())}</span>
          <span class="font-semibold text-sm">${esc(f.title)}</span>
        </div>
        <div class="cam-finding-body">${esc(f.body)}</div>
      </div>`).join("")}
  </div>`;
}

function _camPortGridHtml(ports) {
  const portSlots = [];
  for (let i = 0; i < Math.max(4, ports.length); i++) {
    portSlots.push(ports[i] || null);
  }
  // Card-health context for down-port guidance: how many real NIC ports are up.
  const real = ports.filter(function(p) { return p; });
  const upCount = real.filter(function(p) { return p.isUp; }).length;
  const ctx = { upCount: upCount, total: real.length };
  return portSlots.slice().reverse().map((p, ri) => _camPortTile(p, portSlots.length - 1 - ri, ctx)).join("");
}

// Flip the 4-port LED row between horizontal (VPU upright) and vertical
// (VPU on its side). Toggles the class in place so it works on both the
// Camera Connectivity page and the Fault Isolator's reference diagram, and
// updates the persistent layout var so live-refresh rebuilds keep the choice.
function _camToggleNicLayout() {
  _camNicLayout = (_camNicLayout === "v") ? "h" : "v";
  var isV = _camNicLayout === "v";
  // Flip BOTH the LED row and its legend so they read in the same order — a
  // vertical LED column (Port 1 top → Port 4 bottom) must not sit next to a
  // legend that reads Port 4 → 1, or the labels contradict the lights.
  document.querySelectorAll(".nic-diagram-ports, .nic-diagram-legend").forEach(function(el) { el.classList.toggle("is-vertical", isV); });
  document.querySelectorAll(".nic-layout-toggle").forEach(function(b) {
    b.classList.toggle("is-active", isV);
    b.setAttribute("aria-pressed", isV ? "true" : "false");
  });
}

function _camNicDiagramHtml(ports, showLiveBadge, sysInfo) {
  if (showLiveBadge === undefined) showLiveBadge = true;
  const count = Math.max(4, ports.length);
  function ledColor(p) {
    if (!p || !p.isUp) return "nic-led-off";
    if (p.connecting) return "nic-led-connecting";
    if (p.isDegraded) return "nic-led-warn";
    return "nic-led-ok";
  }
  function ledDotColor(p) {
    if (!p || !p.isUp) return "var(--c-status-down)";
    if (p.connecting) return "var(--c-status-connecting)";
    if (p.isDegraded) return "var(--c-status-warn)";
    return "var(--c-status-ok)";
  }
  // Colorblind-safe: pair every status dot with a word, since the LEDs/legend
  // are otherwise color-only (the per-port tiles below already carry text).
  function ledStatusText(p) {
    if (!p) return "—";              // padding slot, no physical port
    if (!p.isUp) return "No link";
    if (p.connecting) return "Connecting";
    if (p.isDegraded) return "Degraded";
    return "Linked";
  }
  // Physical ports: reversed (highest port on left = physical chassis left)
  var portIcons = "";
  for (var ri = 0; ri < count; ri++) {
    var idx = count - 1 - ri;
    var p = ports[idx] || null;
    var cls = ledColor(p);
    portIcons += '<div class="nic-port-icon">' +
      '<div class="nic-port-body">' +
        '<div class="nic-port-slots"></div>' +
        '<div class="nic-port-led ' + cls + '"></div>' +
      '</div>' +
      '<div class="nic-port-label">Port ' + (idx + 1) + '</div>' +
    '</div>';
  }
  // Vertical legend on the right
  var legend = "";
  for (var li = count - 1; li >= 0; li--) {
    var lp = ports[li] || null;
    legend += '<div class="nic-legend-row">' +
      '<span class="nic-legend-dot" style="background:' + ledDotColor(lp) + '"></span>' +
      '<span class="nic-legend-label">Port ' + (li + 1) + '</span>' +
      '<span class="nic-legend-status">' + ledStatusText(lp) + '</span>' +
    '</div>';
  }
  // NIC header: show just the primary card name. Windows appends " #N"
  // to duplicate adapter descriptions from the same card — strip that
  // and use the first port's description as the card label.
  var nicDesc = "";
  for (var ni = 0; ni < ports.length; ni++) {
    var d = ports[ni] && ports[ni].interfaceDescription;
    if (d) { nicDesc = d.replace(/\s*#\d+\s*$/, "").trim(); break; }
  }
  var hasRealPorts = ports.length > 0;
  var headerLabel;
  if (nicDesc) headerLabel = svgIcon("cpu", 16) + ' ' + esc(nicDesc) + ' · ' + count + ' ports';
  else if (hasRealPorts) headerLabel = count + ' ports';
  else headerLabel = svgIcon("cpu", 16) + ' No NIC ports detected';
  // System-type chip (S1/S2/S2S) + expected main-camera count, when known.
  var sysChip = "";
  if (sysInfo && sysInfo.expectedMainCameras) {
    var sysName = sysInfo.systemType ? esc(sysInfo.systemType) + " · " : "";
    var n = sysInfo.expectedMainCameras;
    sysChip = '<span class="nic-sys-chip">' + sysName + n +
      ' main camera' + (n === 1 ? '' : 's') + ' expected</span>';
  }
  // Toggle to flip the LED row between upright (horizontal) and on-its-side
  // (vertical) so it matches however the VPU is physically mounted.
  var layoutToggle = hasRealPorts
    ? '<button class="nic-layout-toggle' + (_camNicLayout === "v" ? " is-active" : "") +
        '" aria-pressed="' + (_camNicLayout === "v" ? "true" : "false") +
        '" onclick="_camToggleNicLayout()" title="Flip the port row to match how the VPU is mounted — upright (left-to-right) or on its side (top-to-bottom).">' +
        svgIcon("refresh", 12) + ' Flip layout</button>'
    : '';
  var nicHeader = '<div class="nic-diagram-header">' +
    headerLabel + sysChip + layoutToggle +
    (showLiveBadge ? '<span id="cam-live-badge" class="cam-live-badge" aria-live="polite">Auto-Refresh</span>' : '') +
  '</div>';
  // Only show the physical-order note when we actually have NIC data;
  // otherwise it reads misleadingly on an empty system.
  var note = hasRealPorts
    ? '<div class="nic-diagram-note">Port order mirrors the physical orientation of the NIC — Port ' + count + ' is leftmost on the card.</div>'
    : '';
  return nicHeader + '<div class="nic-diagram-wrap">' +
    '<div class="nic-diagram-ports' + (_camNicLayout === "v" ? " is-vertical" : "") + '">' + portIcons + '</div>' +
    '<div class="nic-diagram-legend' + (_camNicLayout === "v" ? " is-vertical" : "") + '">' + legend + '</div>' +
    _camOrientationPanelHtml() +
  '</div>' + note;
}

// Supplemental "which way is the VPU sitting?" reference, shown beside the
// port diagram. Field techs were confused that "Port 4 is leftmost" depends
// on how the HP Z2 tower is mounted (upright vs on its side), which rotates
// the PCIe NIC bracket. Shows the chassis in both orientations with the
// camera (POE) port bank highlighted — it sits just above the AC power
// inlet on the back, which is the orientation-independent anchor.
function _camOrientationPanelHtml() {
  // Stylized HP Z2 tower BACK panel, top → bottom on a real unit:
  //   motherboard I/O cluster (DisplayPorts, onboard RJ-45, USB stack),
  //   a cooling fan grille, the PCIe camera card with the 4 POE ports
  //   (highlighted + numbered), a lower fan, and the AC power inlet.
  // Ports numbered 4→1 (Port 4 leftmost, matching the diagram above).
  // One drawing only. "On its side" is this SAME SVG rotated 90° via CSS,
  // so the two figures can never drift apart. Upright: POE ports 4→1 left to
  // right; rotated -90° puts Port 1 at top and Port 4 at bottom.
  var chassis =
    '<svg viewBox="0 0 104 156" width="98" height="147" class="orient-svg">' +
      '<rect x="12" y="4" width="80" height="148" rx="6" class="orient-chassis"/>' +
      // motherboard I/O zone
      '<rect x="18" y="10" width="68" height="44" rx="2" class="orient-iozone"/>' +
      '<rect x="23" y="13" width="22" height="3" rx="1" class="orient-io"/>' +       // top legacy/USB strip
      '<rect x="23" y="19" width="17" height="5" rx="1" class="orient-io"/>' +       // DisplayPort 1
      '<rect x="23" y="26" width="17" height="5" rx="1" class="orient-io"/>' +       // DisplayPort 2
      '<rect x="23" y="34" width="13" height="11" rx="1" class="orient-eth"/>' +     // onboard RJ-45
      '<rect x="45" y="19" width="9" height="6" rx="1" class="orient-io"/>' +        // USB stack
      '<rect x="45" y="27" width="9" height="6" rx="1" class="orient-io"/>' +
      '<rect x="45" y="35" width="9" height="6" rx="1" class="orient-io"/>' +
      '<circle cx="71" cy="32" r="13" class="orient-fan"/><circle cx="71" cy="32" r="7" class="orient-fan"/>' +
      // PCIe camera card — POE ports (highlighted), Port 4→1 left to right
      '<rect x="18" y="80" width="68" height="25" rx="3" class="orient-portbank"/>' +
      _orientPort(22, 85, 12, 15, "4") + _orientPort(37, 85, 12, 15, "3") +
      _orientPort(52, 85, 12, 15, "2") + _orientPort(67, 85, 12, 15, "1") +
      // lower fan + AC inlet
      '<circle cx="34" cy="130" r="12" class="orient-fan"/><circle cx="34" cy="130" r="6.5" class="orient-fan"/>' +
      '<rect x="56" y="122" width="28" height="17" rx="2" class="orient-acbox"/>' +
      '<circle cx="64" cy="130.5" r="1.6" class="orient-acpin"/>' +
      '<circle cx="76" cy="127" r="1.6" class="orient-acpin"/>' +
      '<circle cx="76" cy="134" r="1.6" class="orient-acpin"/>' +
    '</svg>';
  return '<div class="nic-orient-panel">' +
    '<div class="nic-orient-title">VPU orientation</div>' +
    '<div class="orient-figs">' +
      '<div class="orient-fig"><div class="orient-svg-box" role="img" ' +
        'aria-label="VPU standing upright: the four camera ports run left to right, Port 4 to Port 1.">' + chassis + '</div>' +
        '<div class="orient-fig-label">Standing upright</div></div>' +
      '<div class="orient-fig"><div class="orient-svg-box orient-svg-rot" role="img" ' +
        'aria-label="VPU on its side: the four camera ports stack top to bottom, Port 1 to Port 4.">' + chassis + '</div>' +
        '<div class="orient-fig-label">On its side</div></div>' +
    '</div>' +
    '<div class="orient-caption">' +
      'Camera ports (PoE — Power over Ethernet) are the highlighted bank above the <strong>AC power inlet</strong>. ' +
      '<strong>Tip:</strong> a lit jack matches the linked port above — use it to confirm regardless of mounting.' +
    '</div>' +
  '</div>';
}

// A POE port rectangle + centered number.
function _orientPort(x, y, w, h, num) {
  return '<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + h + '" rx="1.5" class="orient-port"/>' +
         '<text x="' + (x + w / 2) + '" y="' + (y + h / 2 + 3) + '" class="orient-port-num">' + num + '</text>';
}

// Force a fresh camera probe — clears the backend CGI cache and re-polls.
// Used by the manual Refresh button so on-site troubleshooting can override
// any stale ARP/probe data instead of waiting for the TTL.
function _camForceRefresh() {
  // A deliberate Refresh means "show me current state" — drop any stale
  // captured frames so they aren't restored on the re-render.
  _camLastVideo = null;
  var btn = document.querySelector('[onclick*="_camForceRefresh"]');
  if (btn) { btn.disabled = true; btn.style.opacity = "0.5"; }
  api("/api/cameras?refresh=true").then(function(fresh) {
    if (fresh && !fresh.error) {
      dataCache.cameras = fresh;
      if (currentPage === "cameras") renderCameras();
    }
  }).finally(function() {
    if (btn) { btn.disabled = false; btn.style.opacity = ""; }
  });
}

// ── Get Camera Frames (single-frame RTSP capture) ──
// Disable the button for a cooldown, counting down, then restore it. Mirrors
// the server-side rate limit so the button can't be spammed.
function _camFramesCooldown(seconds) {
  var btn = document.getElementById("cam-frames-btn");
  if (!btn) return;
  var left = seconds;
  btn.disabled = true;
  var tick = function() {
    if (left <= 0 || currentPage !== "cameras") {
      var b = document.getElementById("cam-frames-btn");
      if (b) { b.disabled = false; b.innerHTML = svgIcon("camera", 14) + " Get Camera Frames"; }
      return;
    }
    btn = document.getElementById("cam-frames-btn");
    if (btn) btn.innerHTML = svgIcon("refresh", 14) + " Wait " + left + "s…";
    left -= 1;
    setTimeout(tick, 1000);
  };
  tick();
}

function _camVerifyVideo() {
  var btn = document.getElementById("cam-frames-btn");
  var wrap = document.getElementById("cam-video-wrap");
  if (!wrap || (btn && btn.disabled)) return;
  if (btn) { btn.disabled = true; btn.innerHTML = svgIcon("refresh", 14) + " Capturing…"; }
  wrap.innerHTML = '<div class="card"><div class="cam-video-running">' +
    svgIcon("refresh", 14) +
    ' Grabbing a frame from each camera to confirm it is streaming…</div></div>';
  apiPost("/api/cameras/video-test", {}).then(function(res) {
    // Keep a real capture (not a vpu-block) so it survives a re-render /
    // navigate-away-and-back, stamped with the time so it's clearly a
    // snapshot, not live. Cleared by a manual Refresh (_camForceRefresh).
    if (res && (res.results || []).length) {
      var _t = new Date().toLocaleTimeString();
      res._capturedAt = _t;
      res.results.forEach(function(r) { r._capturedAt = _t; });
      _camLastVideo = res;
    }
    if (currentPage === "cameras") wrap.innerHTML = _camVideoResultsHtml(res);
    // If the server reported its own cooldown, honor exactly that; otherwise
    // start the standard cooldown after a real capture. A vpu-block doesn't
    // cooldown (nothing was captured) — just re-enable.
    if (res && res.blocked === "vpu") {
      var b = document.getElementById("cam-frames-btn");
      if (b) { b.disabled = false; b.innerHTML = svgIcon("camera", 14) + " Get Camera Frames"; }
    } else {
      _camFramesCooldown(res && res.cooldown ? res.cooldown : 15);
    }
  }).catch(function() {
    wrap.innerHTML = '<div class="card"><div class="cam-video-err">Frame capture failed to run.</div></div>';
    var b = document.getElementById("cam-frames-btn");
    if (b) { b.disabled = false; b.innerHTML = svgIcon("camera", 14) + " Get Camera Frames"; }
  });
}

// Generic countdown on any button element (used for the per-camera Refresh
// when the server's shared cooldown is still active). Re-enables itself, or
// stops quietly if the button is re-rendered away.
function _camCountdownBtn(btn, seconds, idleHtml) {
  if (!btn) return;
  var left = seconds;
  btn.disabled = true;
  (function tick() {
    if (!document.body.contains(btn)) return;
    if (left <= 0) { btn.disabled = false; btn.innerHTML = idleHtml; return; }
    btn.innerHTML = svgIcon("refresh", 12) + " Wait " + left + "s…";
    left -= 1;
    setTimeout(tick, 1000);
  })();
}

// Re-capture a single camera (the per-card Refresh button). Posts just that
// IP so we don't pull every camera, then merges the fresh frame back into the
// stored set and re-renders. Shares the server cooldown with the all-cameras
// capture.
function _camRefreshOne(ip) {
  if (!ip) return;
  var idle = svgIcon("refresh", 12) + " Refresh";
  var card = document.querySelector('.cam-frame[data-ip="' + ip + '"]');
  var btn = card ? card.querySelector(".cam-frame-refresh") : null;
  if (btn && btn.disabled) return;
  if (btn) { btn.disabled = true; btn.innerHTML = svgIcon("refresh", 12) + " Capturing…"; }
  apiPost("/api/cameras/video-test", { ips: [ip] }).then(function(res) {
    // Server refused (cooldown still ticking, or vpu.exe came up): leave the
    // existing frame in place and tell the tech why, on the button itself.
    if (res && res.blocked === "cooldown") {
      _camCountdownBtn(btn, res.cooldown || 15, idle);
      return;
    }
    if (res && (res.blocked === "vpu" || res.error)) {
      if (btn) { btn.disabled = false; btn.innerHTML = idle; }
      return;
    }
    var fresh = ((res && res.results) || []).filter(function(r) { return (r.ip || "") === ip; })[0];
    if (fresh) {
      fresh._capturedAt = new Date().toLocaleTimeString();
      if (_camLastVideo && _camLastVideo.results) {
        _camLastVideo.results = _camLastVideo.results.map(function(r) {
          return (r.ip || "") === ip ? fresh : r;
        });
      }
    }
    var wrap = document.getElementById("cam-video-wrap");
    if (wrap && currentPage === "cameras") wrap.innerHTML = _camVideoResultsHtml(_camLastVideo || res);
  }).catch(function() {
    if (btn) { btn.disabled = false; btn.innerHTML = idle; }
  });
}

// One "Label  value" row inside a frame card's detail block. value is already
// escaped by the caller; an empty value renders nothing (drops unknown fields).
function _camFrameKv(label, value, mono) {
  if (value == null || value === "") return "";
  return '<div class="cam-kv-row"><span class="cam-kv-k">' + label + "</span>" +
    '<span class="cam-kv-v' + (mono ? " font-mono" : "") + '">' + value + "</span></div>";
}

function _camVideoResultsHtml(res, opts) {
  // showControls=false (Inspection Report) drops the per-camera + all-cameras
  // Refresh buttons — they're wired to the Camera tab's DOM (#cam-video-wrap)
  // and would be dead on any other page; that tab's own Refresh re-captures.
  var showControls = !opts || opts.showControls !== false;
  if (!res || res.error) {
    return '<div class="card">' + sectionTitle("camera", "Camera Frames") +
      '<div class="cam-video-err">Error: ' + esc((res && res.message) || "unknown") + '</div></div>';
  }
  if (res.available === false) {
    return '<div class="card">' + sectionTitle("camera", "Camera Frames") +
      '<div class="cam-no-detect">' + esc(res.reason || "Couldn't read frame details on this VPU.") + '</div></div>';
  }
  var results = res.results || [];
  if (!results.length) {
    return '<div class="card">' + sectionTitle("camera", "Camera Frames") +
      '<div class="cam-no-detect">' + esc(res.reason || "No cameras detected to test.") + '</div></div>';
  }
  var camType = res.systemType ? esc(res.systemType) : null;
  var cards = results.map(function(r) {
    var stream = (esc(r.codec || "?") + " · " + (r.frameRate != null ? r.frameRate + " fps" : "? fps") + (r.resolution ? " · " + esc(r.resolution) : ""));
    var thumb = r.image
      ? '<img class="cam-frame-img" src="' + esc(r.image) + '" alt="' + esc(r.label || r.ip) + ' frame">'
      : '<div class="cam-frame-img cam-frame-empty">' + svgIcon("camera", 22) + '<span>No frame</span></div>';
    // Degraded link warning: a frame grabbed, but the link can't sustain
    // a reliable stream until the connection issue is resolved.
    var degraded = r.ok && r.degraded;
    var warn = "";
    if (degraded) {
      var spd = r.linkSpeedMbps ? r.linkSpeedMbps + " Mbps" : "low speed";
      var exp = r.expectedSpeedMbps
        ? (r.expectedSpeedMbps >= 1000 ? (r.expectedSpeedMbps / 1000) + " Gbps" : r.expectedSpeedMbps + " Mbps")
        : null;
      warn = '<div class="cam-frame-warn">' + svgIcon("alert", 11) +
        ' Degraded link — ' + spd + (exp ? ", expected " + exp : "") +
        '. A frame pulled, but the stream won\'t hold until this is fixed.</div>';
    }
    // Black-picture diagnosis: the frame grabbed (so it reads "Active"), but the
    // server found the picture is near-black — surface it instead of a false OK.
    var hasDiag = r.ok && r.diagnosis && r.diagnosis.summary;
    var diag = "";
    if (hasDiag) {
      diag = '<div class="cam-frame-diag">' + svgIcon("alert", 11) +
        ' <span>' + esc(r.diagnosis.summary) +
        (r.diagnosis.detail ? ' <span class="cam-frame-diag-detail">' + esc(r.diagnosis.detail) + '</span>' : "") +
        '</span></div>';
    }
    var cardCls = r.ok ? ((degraded || hasDiag) ? "cam-frame-degraded" : "") : "cam-frame-fail";
    var statusTxt = !r.ok ? "No video" : (hasDiag ? "Black picture" : (degraded ? "Active · degraded" : "Active"));
    var statusCls = !r.ok ? "status-fail" : ((hasDiag || degraded) ? "status-warn" : "status-pass");
    // Identity block: camera type (S1/S2/S2S — system-wide), IP, model and
    // firmware from the CGI probe, plus the live stream format when one pulled.
    var kv =
      _camFrameKv("Type", camType) +
      _camFrameKv("IP", esc(r.ip), true) +
      _camFrameKv("Model", r.model ? esc(r.model) : null) +
      _camFrameKv("Firmware", r.firmwareVersion ? esc(r.firmwareVersion) : null) +
      (r.ok ? _camFrameKv("Stream", stream) : "");
    var errLine = r.ok ? "" : '<div class="cam-frame-detail cam-frame-novideo">' + esc(r.error || "No video") + "</div>";
    var cap = r._capturedAt ? '<span class="cam-frame-cap">Captured ' + esc(r._capturedAt) + "</span>" : "";
    var refresh = showControls
      ? '<button class="btn-outline btn-ol-blue cam-frame-refresh" onclick="_camRefreshOne(\'' + esc(r.ip) + '\')" ' +
        'title="Capture a fresh still from this camera">' + svgIcon("refresh", 12) + " Refresh</button>"
      : "";
    return '<div class="cam-frame ' + cardCls + '" data-ip="' + esc(r.ip) + '">' +
      thumb +
      '<div class="cam-frame-meta">' +
        '<div class="cam-frame-head">' +
          '<span class="cam-frame-label">' + esc(r.label || r.ip) + '</span>' +
          '<span class="' + statusCls + '">' + statusTxt + '</span>' +
        '</div>' +
        '<div class="cam-frame-kv">' + kv + '</div>' +
        errLine +
        diag +
        warn +
        '<div class="cam-frame-foot">' + cap + refresh + '</div>' +
      '</div></div>';
  }).join("");
  // Still-image notice + an all-cameras refresh, both inside the results card
  // so the "this isn't live, grab a new one" cue sits right next to the frames.
  var notice = showControls
    ? '<div class="cam-frame-notice">' + svgIcon("info", 12) +
      ' These are still snapshots, not a live stream. To get a new image, use ' +
      '<strong>Refresh all cameras</strong> below, or <strong>Refresh</strong> on a single camera.</div>'
    : '<div class="cam-frame-notice">' + svgIcon("info", 12) +
      ' These are still snapshots, not a live stream — use <strong>Refresh</strong> above to recapture.</div>';
  var toolbar = showControls
    ? '<div class="cam-frame-toolbar">' +
      '<button class="btn-outline btn-ol-blue" onclick="_camVerifyVideo()" ' +
      'title="Capture a fresh still from every camera">' + svgIcon("refresh", 14) + " Refresh all cameras</button></div>"
    : "";
  return '<div class="card">' + sectionTitle("camera", "Camera Frames") +
    notice + toolbar +
    '<div class="cam-frame-grid">' + cards + '</div></div>';
}

// ── S1 (JAI) camera discovery — only renders on S1 systems ──
function _camLoadS1() {
  api("/api/cameras/s1").then(function(res) {
    var wrap = document.getElementById("cam-s1-wrap");
    if (!wrap || currentPage !== "cameras") return;
    if (res && res.available && (res.cameras || []).length) {
      wrap.innerHTML = _camS1Html(res);
    } else {
      wrap.innerHTML = "";  // not an S1 system (or none found) → show nothing
    }
  }).catch(function() {});
}

function _camS1Html(res) {
  var rows = (res.cameras || []).map(function(c) {
    return "<tr>" +
      '<td class="font-mono">' + esc(c.serialNumber || "") + "</td>" +
      '<td class="font-mono">' + esc(c.ip || "") + "</td>" +
      "<td>" + esc(c.model || "") + "</td></tr>";
  }).join("");
  return '<div class="card">' + sectionTitle("camera", "S1 Cameras (JAI) · " + res.count + " detected") +
    '<table class="data-table"><thead><tr><th>Serial Number</th><th>IP</th><th>Model</th></tr></thead>' +
    "<tbody>" + rows + "</tbody></table></div>";
}

// ── PoE power draw (ADLINK SmartPoE) ─────────────────────────────
// Ported from the gen-1 PowerShell tool's "PoE Status" section. Only the
// I210/I211 (GIE74P) camera NIC can measure this; see Get-PoePower.ps1 for the
// full gate. Watts change every poll, so the live tick patches the numbers in
// place (_camPoeUpdate) rather than rebuilding — a 2s innerHTML swap would
// flicker and fight the transition on the bars.

// Per-port PoE+ ceiling (IEEE 802.3at) — bars are a fraction of this, so fill
// reads as "how close to the per-port limit".
//
// Real Pixellot CHUs draw only 4-7 W (measured on a production GIE74P,
// 2026-08-12), so a healthy camera fills roughly a fifth of its bar. That's
// intentional: the bar answers "how much headroom does this port have", and
// showing a camera near the top of its scale would misrepresent a normal load.
var CAM_POE_PORT_MAX_W = 25.5;

// Structural signature: everything that changes the card's SHAPE rather than
// its numbers. Watts/voltage/current/temp are deliberately excluded.
function _camPoeSignature(poe) {
  if (!poe) return "none";
  var portSig = (poe.ports || []).map(function(p) {
    return p.port + ":" + (p.poeOn ? "1" : "0") + (p.readOk === false ? "x" : "");
  }).join(",");
  var tight = poe.budget ? (poe.budget.underPowered ? "1" : "0") : "-";
  // portSumOk gates the integrity footnote, so a change in it must rebuild the
  // card rather than be patched over.
  var sumOk = poe.budget ? (poe.budget.portSumOk === false ? "0" : "1") : "-";
  return [poe.supported ? "1" : "0", poe.available ? "1" : "0",
          poe.reason || "", tight, sumOk, portSig].join("~");
}

function _camPoeCardHtml(poe, ports) {
  // No payload at all (backend predates this field) — render nothing rather
  // than an empty box.
  if (!poe) return "";

  var hdr = sectionTitle("power", "PoE Power Draw");

  // Unsupported NIC family is a by-design N/A, NOT a fault. Render it neutral
  // and muted: gen-1 explicitly scored this step "pass" so techs don't chase
  // a measurement the hardware cannot take.
  if (!poe.supported) {
    return hdr +
      '<div class="cam-poe-note cam-poe-note-info">' +
        '<div class="cam-poe-note-title">Not measurable on this camera NIC</div>' +
        '<div class="cam-poe-note-body">' + esc(poe.reason || "") + "</div>" +
        (poe.cardLabel ? '<div class="cam-poe-note-meta font-mono">' + esc(poe.cardLabel) + "</div>" : "") +
      "</div>";
  }

  // Supported hardware but no reading — driver bundle missing, card not
  // detected, or the probe latched off after crashing. Actionable, so amber.
  if (!poe.available) {
    return hdr +
      '<div class="cam-poe-note cam-poe-note-warn">' +
        '<div class="cam-poe-note-title">Power readings unavailable</div>' +
        '<div class="cam-poe-note-body">' + esc(poe.reason || "") + "</div>" +
        (poe.cardLabel ? '<div class="cam-poe-note-meta font-mono">' + esc(poe.cardLabel) + "</div>" : "") +
      "</div>";
  }

  var b = poe.budget || {};
  // Deliberately worded close to Pixellot's VPU Manager ("POE Molex disconnected
  // or insufficient power. 20.0 W detected (expected >=55W)") so a tech reading
  // both tools sees one story, not two. Pulse adds the fix rather than just the
  // verdict.
  var lowBanner = b.underPowered
    ? '<div class="cam-poe-note cam-poe-note-warn cam-poe-low">' +
        '<div class="cam-poe-note-title">PoE Molex disconnected or insufficient power</div>' +
        '<div class="cam-poe-note-body">The card reports a total budget of ' + _camPoeW(b.totalW) +
          ', below the ' + _camPoeW(b.healthyFloorW) + ' a healthy card provides. The supplementary ' +
          'Molex power lead on the PoE card is most likely unplugged, so the card is running on slot ' +
          'power alone and cannot power a full set of cameras. Power the VPU down, reseat the Molex ' +
          'lead on the camera card, and re-check. VPU Manager reports this same fault as a failed ' +
          'POE Power Test.</div>' +
      "</div>"
    : "";

  var stats =
    '<div class="cam-poe-stats">' +
      _camPoeStat("Total budget", "cam-poe-total", _camPoeW(b.totalW)) +
      _camPoeStat("Drawing now", "cam-poe-consumed", _camPoeW(b.consumedW)) +
      _camPoeStat("Available", "cam-poe-remaining", _camPoeW(b.remainingW)) +
      _camPoeStat("Card temp", "cam-poe-temp", _camPoeC(b.tempC)) +
    "</div>";

  // PSE channel N is chassis Port N — proven by controlled experiment on a
  // GIE74P (VPU2, 2026-08-12) and consistent with a second production card, so
  // rows name the port outright. The collector guarantees the numbering; see
  // its 1-based channel note.
  var rows = (poe.ports || []).map(function(p) {
    var match = (ports || [])[p.port - 1] || null;
    var sub;
    if (p.readOk === false)              sub = "Read rejected by driver";
    else if (match && match.cameraLabel) sub = match.cameraLabel;
    else                                 sub = p.poeOn ? "Powered device" : "No device powered";
    return '<div class="cam-poe-row" id="cam-poe-row-' + p.port + '">' +
      '<div class="cam-poe-row-label">' +
        '<span class="cam-poe-port">Port ' + p.port + "</span>" +
        '<span class="cam-poe-sub">' + esc(sub) + "</span>" +
      "</div>" +
      '<div class="cam-poe-track">' +
        '<div class="cam-poe-fill' + _camPoeFillClass(p) + '" id="cam-poe-fill-' + p.port + '"' +
             ' style="width:' + _camPoePct(p) + '%"></div>' +
      "</div>" +
      '<div class="cam-poe-readout font-mono" id="cam-poe-readout-' + p.port + '">' +
        _camPoeReadout(p) +
      "</div>" +
    "</div>";
  }).join("");

  // Integrity note: the per-port readings should account for what the card says
  // it is delivering. A mismatch means Pulse is reading the wrong channels (the
  // exact shape of the 0-based bug found on 2026-08-12), not that the VPU has a
  // fault — so it is a quiet footnote, not a warning.
  var sumNote = (b.portSumOk === false)
    ? '<div class="cam-poe-note-meta">Per-port readings total ' + _camPoeW(b.portSumW) +
      ' but the card reports ' + _camPoeW(b.consumedW) + ' drawn — the per-port figures below ' +
      'may be incomplete. Card totals are still accurate.</div>'
    : "";

  return hdr + lowBanner + stats + '<div class="cam-poe-ports">' + rows + "</div>" + sumNote;
}

function _camPoeStat(label, id, value) {
  return '<div class="cam-poe-stat">' +
    '<div class="cam-poe-stat-label">' + esc(label) + "</div>" +
    '<div class="cam-poe-stat-value font-mono" id="' + id + '">' + esc(value) + "</div>" +
  "</div>";
}

function _camPoeW(w) {
  return (w == null) ? "--" : (Number(w).toFixed(1) + " W");
}

function _camPoeC(c) {
  return (c == null || c === 0) ? "--" : (Number(c).toFixed(1) + " °C");
}

function _camPoePct(p) {
  if (!p || !p.poeOn || p.watts == null) return 0;
  return Math.max(2, Math.min(100, (p.watts / CAM_POE_PORT_MAX_W) * 100));
}

function _camPoeFillClass(p) {
  if (!p || p.readOk === false) return " cam-poe-fill-off";
  if (!p.poeOn) return " cam-poe-fill-off";
  // Over the PoE+ per-port ceiling is a real fault; 80% is the heads-up.
  if (p.watts > CAM_POE_PORT_MAX_W) return " cam-poe-fill-hot";
  if (p.watts > CAM_POE_PORT_MAX_W * 0.8) return " cam-poe-fill-warn";
  return " cam-poe-fill-ok";
}

function _camPoeReadout(p) {
  if (!p) return "--";
  // A rejected read must not look like a confident "off" — same reason the
  // collector sends readOk instead of zeroing the values.
  if (p.readOk === false) return "not readable";
  if (!p.poeOn) return "off";
  return Number(p.watts).toFixed(1) + " W  ·  " +
         Number(p.voltage).toFixed(1) + " V  ·  " +
         Number(p.current).toFixed(3) + " A";
}

// Live tick. Patches only the volatile numbers unless the card's shape changed
// (a port powering up, the budget verdict flipping, the driver dropping out),
// in which case rebuild the whole card once.
function _camPoeUpdate(poe, ports) {
  var wrap = document.getElementById("cam-poe-card");
  if (!wrap) return;

  var sig = _camPoeSignature(poe);
  if (sig !== _camPoeLastSignature) {
    _camPoeLastSignature = sig;
    wrap.innerHTML = _camPoeCardHtml(poe, ports);
    wrap.style.display = poe ? "" : "none";
    return;
  }
  if (!poe || !poe.available) return;

  var b = poe.budget || {};
  var setText = function(id, text) {
    var el = document.getElementById(id);
    if (el) el.textContent = text;
  };
  setText("cam-poe-total", _camPoeW(b.totalW));
  setText("cam-poe-consumed", _camPoeW(b.consumedW));
  setText("cam-poe-remaining", _camPoeW(b.remainingW));
  setText("cam-poe-temp", _camPoeC(b.tempC));

  (poe.ports || []).forEach(function(p) {
    setText("cam-poe-readout-" + p.port, _camPoeReadout(p));
    var fill = document.getElementById("cam-poe-fill-" + p.port);
    if (fill) {
      fill.style.width = _camPoePct(p) + "%";
      fill.className = "cam-poe-fill" + _camPoeFillClass(p);
    }
  });
}

function renderCameras() {
  const data = cached("cameras");
  if (!data) { $page().innerHTML = sectionLoading("Camera Connectivity"); fetchSection("cameras"); return; }
  if (data.error) { $page().innerHTML = errorBox(data.message); return; }

  const ports = data.ports || [];
  const findings = data.findings || [];

  const portSlots = [];
  for (let i = 0; i < Math.max(4, ports.length); i++) {
    portSlots.push(ports[i] || null);
  }

  $page().innerHTML = `
    ${pageHeader("Camera Connectivity", "Camera ports — link status, speed, and which cameras are detected.",
      `<button class="btn-outline btn-ol-blue" onclick="_camForceRefresh()">
        ${svgIcon("refresh", 14)} Refresh
      </button>
      <button id="cam-frames-btn" class="btn-outline btn-ol-blue" onclick="_camVerifyVideo()"${data.vpuRunning ? " disabled" : ""}
        title="${data.vpuRunning ? "Disabled while the Pixellot capture engine (vpu.exe) is running — capturing frames could interfere with the live stream." : "Grabs a single frame from each camera to confirm it is streaming and show what it sees."}">
        ${svgIcon("camera", 14)} Get Camera Frames
      </button>
      <button class="btn-outline btn-ol-blue" onclick="navigate('fault-isolator')">
        ${svgIcon("zap", 14)} Camera Connection Troubleshooting
      </button>`
    )}

    <div class="cam-page-body">
      <div id="cam-findings-wrap">${_camFindingsHtml(findings)}</div>

      <div id="cam-video-wrap"></div>

      <div id="cam-s1-wrap"></div>

      <div class="card" id="cam-nic-diagram">${_camNicDiagramHtml(ports, true, {systemType: data.systemType, expectedMainCameras: data.expectedMainCameras})}</div>

      <div class="cam-port-grid" id="cam-port-grid">
        ${_camPortGridHtml(ports)}
      </div>

      <div class="card" id="cam-poe-card"${data.poe ? "" : ' style="display:none"'}>${_camPoeCardHtml(data.poe, ports)}</div>
    </div>

  `;

  // Restore a previously-captured frame set so navigating away and back (a
  // full re-render) doesn't silently discard it. Stamped with its capture
  // time so it can't be mistaken for live; a manual Refresh clears it.
  if (_camLastVideo) {
    var _vw = document.getElementById("cam-video-wrap");
    if (_vw) _vw.innerHTML = _camVideoResultsHtml(_camLastVideo);
  }

  // S1 (JAI) discovery — one-shot per full render; renders only on S1 systems.
  _camLoadS1();

  // ── Live refresh: poll /api/cameras every 2s and update port grid + findings ──
  // Seed the signature from what we just rendered so the first tick can
  // tell whether anything structural actually changed.
  _camLastSignature = _camSignature(data);
  _camPoeLastSignature = _camPoeSignature(data.poe);
  if (_camerasRefreshTimer) clearInterval(_camerasRefreshTimer);
  _camerasFailCount = 0;
  _camerasRefreshTimer = setInterval(function() {
    if (currentPage !== "cameras") { clearInterval(_camerasRefreshTimer); _camerasRefreshTimer = null; return; }
    var markStale = function() {
      // After 3 consecutive failures (~9s) flag the Auto-Refresh badge as stale.
      _camerasFailCount++;
      if (_camerasFailCount >= 3) {
        var b = document.getElementById("cam-live-badge");
        if (b) { b.classList.add("cam-live-stale"); b.textContent = "Stale (" + _camerasFailCount + ")"; }
      }
    };
    api("/api/cameras").then(function(fresh) {
      if (!fresh || fresh.error || currentPage !== "cameras") { markStale(); return; }
      _camerasFailCount = 0;
      dataCache.cameras = fresh;
      var freshPorts = fresh.ports || [];

      var newSig = _camSignature(fresh);
      if (newSig === _camLastSignature) {
        // Steady state — nothing structural changed. Update only the
        // volatile RX/TX counters in place so open Details panels and
        // the rest of the DOM stay untouched (no flicker).
        freshPorts.forEach(function(p, i) {
          var el = document.getElementById("cam-rxtx-" + i);
          if (el) el.textContent = formatBytes(p.rxBytes) + " / " + formatBytes(p.txBytes);
        });
      } else {
        // Structural change (port up/down, camera moved, speed, findings…)
        // — do a full rebuild. A brief flicker here is acceptable and even
        // useful: it signals a real change the tech should notice.
        _camLastSignature = newSig;
        var grid = document.getElementById("cam-port-grid");
        if (grid) {
          var openDetails = {};
          grid.querySelectorAll('details[open][data-port-idx]').forEach(function(d) {
            openDetails[d.dataset.portIdx] = true;
          });
          grid.innerHTML = _camPortGridHtml(freshPorts);
          Object.keys(openDetails).forEach(function(idx) {
            var d = grid.querySelector('details[data-port-idx="' + idx + '"]');
            if (d) d.setAttribute('open', '');
          });
        }
        var diag = document.getElementById("cam-nic-diagram");
        if (diag) diag.innerHTML = _camNicDiagramHtml(freshPorts, true, {systemType: fresh.systemType, expectedMainCameras: fresh.expectedMainCameras});
        var fw = document.getElementById("cam-findings-wrap");
        if (fw) fw.innerHTML = _camFindingsHtml(fresh.findings || []);
      }

      // PoE runs on its own signature, outside the branch above: watts move
      // every tick (so they must update even in "steady state"), and a port
      // powering up is a PoE structural change that need not be a port-grid
      // one. _camPoeUpdate decides patch-vs-rebuild for itself.
      _camPoeUpdate(fresh.poe, freshPorts);

      // Pulse the live badge to show the tick happened and clear any stale state
      var badge = document.getElementById("cam-live-badge");
      if (badge) {
        badge.classList.remove("cam-live-stale");
        badge.textContent = "Auto-Refresh";
        badge.classList.add("cam-live-tick");
        setTimeout(function() { badge.classList.remove("cam-live-tick"); }, 600);
      }
    }).catch(function() { markStale(); });
  }, 2000);  // 2s poll — paired with the backend's near-fresh NIC read so a
             // cable unplug/replug shows up in ~2s instead of ~15s.
}

function formatBytes(b) {
  if (b == null) return "--";
  if (b < 1024) return b + " B";
  if (b < 1048576) return (b / 1024).toFixed(1) + " KB";
  if (b < 1073741824) return (b / 1048576).toFixed(1) + " MB";
  return (b / 1073741824).toFixed(2) + " GB";
}

// ── Services ─────────────────────────────────────────────────

function renderServices() {
  const data = cached("services");
  if (!data) { $page().innerHTML = sectionLoading("Pixellot Services"); fetchSection("services"); return; }

  if (data.error) { $page().innerHTML = errorBox(data.message); return; }

  const svcs = data.services || [];

  function svcTile(s) {
    const st = (s.status || "").toLowerCase();
    let borderCls = "svc-tile-muted";
    if (st === "running") borderCls = "svc-tile-running";
    else if (st === "stopped") borderCls = "svc-tile-stopped";

    const isProcess = s.kind === "process";
    // Detail line: services show SCM start type; processes show PID + memory.
    let detail = "";
    if (isProcess && s.pid) {
      const mem = s.memoryMB != null ? ` · ${s.memoryMB} MB` : "";
      detail = `<div class="svc-tile-start">PID ${esc(String(s.pid))}${mem}</div>`;
    } else if (s.startType) {
      detail = `<div class="svc-tile-start">Start: ${esc(s.startType)}</div>`;
    }

    // Restart button only makes sense for real Windows services. Pixellot
    // core processes (agent/coordinator/vpu/keepagentup) aren't services —
    // they're managed by the KeepAgentUp watchdog, so the per-tile button is
    // replaced with a managed-by note. The "Restart Agent + Coordinator"
    // quick-action card above is the correct restart path for them.
    let actions = "";
    if (isProcess) {
      // Pixellot core processes don't have an individual restart button
      // because the KeepAgentUp watchdog supervises them — use the
      // "Restart Agent + Coordinator" quick action above instead.  The
      // notes here explain that to the tech so the missing button doesn't
      // read as a gap.
      actions = s.watchdog
        ? `<span class="svc-tile-note" title="This watchdog process restarts the Agent and Coordinator automatically when they exit.">${svgIcon("shield", 12)} Watchdog — restarts Agent/Coordinator on failure</span>`
        : `<span class="svc-tile-note" title="Use the 'Restart Agent + Coordinator' button above to restart this process.">${svgIcon("shield", 12)} Managed by KeepAgentUp — use Restart action above</span>`;
    } else if (s.status !== "NotFound") {
      actions = `<button class="btn-outline btn-ol-blue svc-restart-btn" data-name="${esc(s.name)}">
          ${svgIcon("refresh", 12)} Restart
        </button>`;
    }

    return `<div class="svc-tile ${borderCls}" data-svc="${esc(s.name)}">
      <div class="svc-tile-top">
        <span class="svc-tile-name">${esc(s.name)}</span>
        ${statusBadge(s.status)}
      </div>
      ${s.displayName && s.displayName !== s.name ? `<div class="svc-tile-display">${esc(s.displayName)}</div>` : ""}
      ${detail}
      <div class="svc-tile-actions">${actions}</div>
    </div>`;
  }

  // Two separate areas: Pixellot core *processes* (Agent/Coordinator/VPU/
  // watchdog — executables in C:\Pixellot\Bin, not services) and real Windows
  // *services* (ScoreConnect, LogMeIn) queried through the SCM. Keeping them
  // apart stops a "Not Found" service from reading as a stopped process and
  // vice-versa. Re-used on the post-restart in-place refresh below.
  function svcSectionsHtml(list) {
    function section(title, subtitle, items, emptyMsg) {
      return `<section class="svc-section">
        <div class="svc-section-head">
          <h3 class="svc-section-title">${esc(title)}</h3>
          <p class="svc-section-sub">${esc(subtitle)}</p>
        </div>
        <div class="svc-grid">
          ${items.map(svcTile).join("")}
          ${!items.length ? `<p class="text-pulse-muted text-sm">${esc(emptyMsg)}</p>` : ""}
        </div>
      </section>`;
    }
    const procs = list.filter(s => s.kind === "process");
    const services = list.filter(s => s.kind !== "process");
    return (
      section("Pixellot Core Processes",
        "Launched and supervised by the KeepAgentUp watchdog — these are executables in C:\\Pixellot\\Bin, not Windows services. Restart them with the action above.",
        procs, "No process data") +
      section("Windows Services",
        "Real Windows services queried through the Service Control Manager (SCM). Each can be restarted individually.",
        services, "No service data")
    );
  }

  $page().innerHTML = `
    ${pageHeader("Service Status", "Pixellot Agent, VPU encoder, and related Windows services",
      `<button class="btn-outline btn-ol-blue" onclick="dataCache.services=null;renderServices()">
        ${svgIcon("refresh", 14)} Refresh
      </button>`
    )}

    <!-- Installed Pixellot dependencies version (Canopy/Leaf adaptation) -->
    <!-- Filled in async by the /api/services/dependencies call below. -->
    <div id="svc-deps-line" class="svc-deps-line hidden"></div>

    <!-- keepagentup.exe — PDF #13 fast-remedy action -->
    <div class="card svc-quick-action">
      <div class="svc-quick-action-row">
        <div>
          <div class="svc-quick-action-title">Restart Agent + Coordinator</div>
          <div class="svc-quick-action-body">
            The documented first fix when the Pixellot Agent or Coordinator stops responding — try it before escalating for a hardware return (RMA). <span class="font-mono">Runs c:\\pixellot\\bin\\keepagentup.exe.</span>
          </div>
        </div>
        <button class="btn-outline btn-ol-blue" id="svc-keepagent-btn" title="Documented first-line remedy when Agent/Coordinator is unresponsive">
          ${svgIcon("zap", 14)} Restart Agent + Coordinator
        </button>
      </div>
      <div id="svc-keepagent-result" class="svc-quick-action-result hidden"></div>
    </div>

    <div id="svc-sections">
      ${svcSectionsHtml(svcs)}
    </div>
  `;

  // Installed Pixellot Dependencies (Canopy/Leaf/getVpuDepsFromRegistry.ps1
  // adaptation). Fills the always-visible status line at the top of the tab.
  (async () => {
    const r = await api("/api/services/dependencies");
    if (currentPage !== "services") return;
    const line = document.getElementById("svc-deps-line");
    if (!line || !r || r.error) return;
    line.classList.remove("hidden");

    const installed = r.installedVersion || "—";
    const latest = r.latestKnownVersion || "—";
    const status = r.status || "unknown";
    let cls = "svc-deps-current";
    let label = "Current";
    let icon = svgIcon("check", 12);
    if (status === "outdated") {
      cls = "svc-deps-outdated"; label = "Outdated"; icon = svgIcon("alert", 12);
    } else if (status === "missing") {
      cls = "svc-deps-missing"; label = "Not installed"; icon = svgIcon("alert", 12);
    } else if (status === "newer") {
      cls = "svc-deps-newer"; label = "Newer than known"; icon = svgIcon("info", 12);
    }

    line.className = "svc-deps-line " + cls;
    line.innerHTML = `
      ${icon}
      <span><strong>Pixellot Dependencies</strong> · Current: <span class="font-mono">${esc(installed)}</span> · Latest known: <span class="font-mono">${esc(latest)}</span></span>
      <span class="svc-deps-pill">${esc(label)}</span>
    `;
  })();

  document.getElementById("svc-sections")?.addEventListener("click", async (e) => {
    const btn = e.target.closest(".svc-restart-btn");
    if (!btn) return;
    const name = btn.dataset.name;
    btn.disabled = true;
    btn.innerHTML = "Restarting...";
    const result = await apiPost("/api/services/restart", { serviceName: name });
    btn.disabled = false;
    btn.innerHTML = `${svgIcon("refresh", 12)} Restart`;
    if (result.success) {
      dataCache.services = null;
      renderServices();
    } else {
      btn.innerHTML = result.message || "Failed";
      setTimeout(() => { btn.innerHTML = `${svgIcon("refresh", 12)} Restart`; }, 3000);
    }
  });

  // keepagentup.exe — confirmation modal + inline result
  document.getElementById("svc-keepagent-btn")?.addEventListener("click", async () => {
    const ok = confirm(
      "Restart Pixellot Agent + Coordinator?\n\n" +
      "This runs c:\\pixellot\\bin\\keepagentup.exe, which will briefly stop and " +
      "relaunch both services. Recording may pause for a few seconds.\n\n" +
      "Proceed?"
    );
    if (!ok) return;

    const btn = document.getElementById("svc-keepagent-btn");
    const resultEl = document.getElementById("svc-keepagent-result");
    btn.disabled = true;
    btn.innerHTML = `${svgIcon("refresh", 14)} Restarting...`;
    resultEl.classList.add("hidden");

    const r = await apiPost("/api/services/restart-agent", {});
    btn.disabled = false;
    btn.innerHTML = `${svgIcon("zap", 14)} Restart Agent + Coordinator`;

    const ok2 = r && r.success;
    // keepagentup exits 0 without doing anything when its resident watchdog
    // instance is already running — that's "nothing happened", not success.
    const resident = r && r.watchdogResident;
    resultEl.className = "svc-quick-action-result " +
      (ok2 ? "svc-result-ok" : resident ? "svc-result-warn" : "svc-result-err");
    const heading = ok2 ? svgIcon("check", 14) + " Success"
      : resident ? svgIcon("alert", 14) + " Not restarted — watchdog already running"
      : svgIcon("alert", 14) + " Failed";
    resultEl.innerHTML = `
      <div class="font-semibold">${heading}</div>
      <div class="text-sm mt-1">${esc(r?.message || "(no message)")}</div>
      ${r?.agentStatus ? `<div class="text-xs mt-2 text-pulse-muted">Agent: <span class="font-mono">${esc(r.agentStatus)}</span> &middot; Coordinator: <span class="font-mono">${esc(r.coordinatorStatus || "?")}</span></div>` : ""}
      ${r?.stdout ? `<pre class="svc-result-output">${esc(r.stdout)}</pre>` : ""}
      ${r?.stderr ? `<pre class="svc-result-output svc-result-stderr">${esc(r.stderr)}</pre>` : ""}
    `;

    if (ok2) {
      // Refresh service-tile statuses in-place so the result panel stays visible
      api("/api/services").then(fresh => {
        if (!fresh || fresh.error || currentPage !== "services") return;
        dataCache.services = fresh;
        const sections = document.getElementById("svc-sections");
        if (sections) sections.innerHTML = svcSectionsHtml(fresh.services || []);
      });
    }
  });

}

// ── Disk Health ──────────────────────────────────────────────

function renderDiskHealth() {
  const data = cached("disk-health");
  if (!data) { $page().innerHTML = sectionLoading("Disk & System Health"); fetchSection("disk-health"); return; }

  if (data.error) { $page().innerHTML = errorBox(data.message); return; }

  const logical = data.logicalDisks || [];
  const physical = data.physicalDisks || [];
  const events = data.diskEvents || [];
  const paths = data.pixellotPaths || [];

  // SMART: an empty physicalDisks array means collection FAILED — `every()`
  // on [] returns true, which would otherwise show a false "all healthy".
  // Beyond the coarse Healthy/Unhealthy rollup we now factor in the SSD-fleet
  // signals: the OS pre-fail flag, uncorrectable errors, and wear %.
  const haveSmart = physical.length > 0;
  const predictFail = data.predictFailure === true;
  const anyUnhealthy = haveSmart && physical.some(d => (d.healthStatus || "").toLowerCase() !== "healthy");
  const anyUncorrected = haveSmart && physical.some(d => {
    const s = d.smart || {};
    return (s.readErrorsUncorrected || 0) + (s.writeErrorsUncorrected || 0) > 0;
  });
  const maxWear = haveSmart ? physical.reduce((m, d) => {
    const w = (d.smart || {}).wearPercent;
    return (w != null && w > m) ? w : m;
  }, 0) : 0;
  const smartBad  = predictFail || anyUnhealthy || anyUncorrected;
  const smartWarn = !smartBad && maxWear >= 80;
  const smartSev  = !haveSmart ? "muted" : smartBad ? "critical" : smartWarn ? "warning" : "ok";
  const smartChip = !haveSmart ? "No data" : smartBad ? "Issue" : smartWarn ? "Wear high" : "OK";
  const smartVal  = !haveSmart ? "SMART not reported"
    : smartBad ? "Drive predicting failure"
    : smartWarn ? `Highest wear ${maxWear}%`
    : `${physical.length} disk${physical.length === 1 ? "" : "s"} checked`;

  const errorCount = events.length;
  const errorSev  = errorCount > 5 ? "critical" : errorCount > 0 ? "warning" : "ok";
  const errorChip = errorCount === 0 ? "Clean" : errorCount > 5 ? "High" : "Warning";
  const errorVal  = errorCount === 0 ? "None" : `${errorCount} event${errorCount === 1 ? "" : "s"}`;

  const osDrive = logical.find(d => d.deviceID === "C:") || logical[0];
  const osFreeGB = osDrive?.freeSpaceGB;
  const osPct = osDrive?.usedPercent;
  // Guard each field so a partial payload can't render "undefined GB free…".
  const osLabel = osDrive
    ? `${osFreeGB != null ? osFreeGB : "—"} GB free of ${osDrive.sizeGB != null ? osDrive.sizeGB : "—"} GB`
    : "No data";
  // Critical at >90% used (matches the volume bars and the [Storage] finding),
  // OR if absolute headroom drops below 50 GB (catches a nearly-full large
  // disk that's still under 90%). No warning tier — disk fill is critical-only.
  const osSev =
    (osPct != null && osPct > 90) || (osFreeGB != null && osFreeGB < 50) ? "critical" : "ok";

  function summaryCard(icon, title, chipSev, chipText, value, desc) {
    return `<div class="card dh-summary-card">
      <div class="dh-summary-top">
        <span class="dh-summary-icon">${svgIcon(icon, 18)}</span>
        <span class="dh-summary-title">${esc(title)}</span>
        ${severityChip(chipSev, chipText)}
      </div>
      <div class="dh-summary-val">${esc(value)}</div>
      <div class="dh-summary-desc">${esc(desc)}</div>
    </div>`;
  }

  // Storage Cleanup — offered only once D: hits 90% full (the same moment
  // the red "almost full" finding fires). The card stays visible after a
  // run so the tech keeps the receipt even though D: drops back under 90%.
  const dDrive = logical.find(d => d.deviceID === "D:");
  const dPct = dDrive?.usedPercent;
  const showCleanup = (dPct != null && dPct >= 90) || _cleanupReceipt != null;
  const cleanupCard = !showCleanup ? "" : `
    <div class="card mt-4" id="dh-cleanup-card">
      ${sectionTitle("database", "Storage Cleanup")}
      ${_cleanupReceipt ? _cleanupReceiptHtml() : `
        <p class="text-sm">
          The recordings drive D: is <b>${esc(String(dPct))}% full</b>
          (${dDrive?.freeSpaceGB != null ? esc(String(dDrive.freeSpaceGB)) : "—"} GB free).
          Pulse can permanently delete <b>daily test clips older than 90 days</b> and
          <b>game recordings older than 1 year</b> from D:\\recordedevents.
          Nothing from the last 90 days is ever touched.
        </p>
        <button class="btn-outline btn-ol-blue mt-2" id="dh-cleanup-review">
          ${svgIcon("database", 14)} Review what can be deleted
        </button>
        <div id="dh-cleanup-body" class="mt-3"></div>
      `}
    </div>`;

  $page().innerHTML = `
    ${pageHeader("Disks", "Drive health, free space, and the Pixellot folders that fill up first",
      `<button class="btn-outline btn-ol-blue" onclick="dataCache['disk-health']=null;renderDiskHealth()">
        ${svgIcon("refresh", 14)} Refresh
      </button>`
    )}

    <!-- 3 Summary Cards -->
    <div class="dh-summary-row">
      ${summaryCard("heartbeat", "Drive Self-Check (SMART)", smartSev, smartChip, smartVal, "Built-in health status reported by each drive")}
      ${summaryCard("alert", "Disk & Driver Errors", errorSev, errorChip, errorVal, "Disk, NVMe, NTFS & volume events from the Windows Event Log (last 24 h)")}
      ${summaryCard("hdd", "OS Drive", osSev, osSev === "ok" ? "OK" : "Critical", osLabel, "Critical when over 90% full or under 50 GB free")}
    </div>

    ${cleanupCard}

    <!-- Volumes -->
    <div class="card">
      ${sectionTitle("database", "Volumes")}
      ${logical.length ? logical.map(d => {
        const role = d.deviceID === "C:" ? "System — OS & Pixellot"
                   : d.deviceID === "D:" ? "Recordings — local game-video storage"
                   : "Storage";
        // Missing usedPercent = Unknown — don't default to 0% and paint a
        // green "OK" bar that makes a no-data volume look healthy.
        const hasPct = d.usedPercent != null;
        const pct = hasPct ? d.usedPercent : 0;
        // One severity drives BOTH the bar fill and the status label, in
        // theme tokens (no hardcoded blue OK bar next to a green OK label).
        let sevColor = "var(--c-accent-green)", status = "OK";
        if (!hasPct) { sevColor = "var(--c-dim)"; status = "Unknown"; }
        else if (pct > 90) { sevColor = "var(--c-accent-red)"; status = "Critical"; }
        const freeStr = d.freeSpaceGB != null ? `${d.freeSpaceGB} GB` : "—";
        const sizeStr = d.sizeGB != null ? `${d.sizeGB} GB` : "—";
        return `<div class="dh-vol-row">
          <span class="dh-vol-drive font-mono">${esc(d.deviceID)}</span>
          <span class="dh-vol-role">${esc(role)}</span>
          <div class="dh-vol-bar-wrap">
            <div class="dash-vol-bar"><div class="dash-vol-fill" style="width:${Math.min(pct, 100)}%;background:${sevColor}"></div></div>
          </div>
          <span class="dh-vol-free">${esc(freeStr)} free of ${esc(sizeStr)}</span>
          <span class="dh-vol-status" style="color:${sevColor}">${esc(status)}</span>
        </div>`;
      }).join("") : '<p class="text-pulse-muted text-sm">No volume data</p>'}
    </div>

    <!-- Pixellot Storage Paths -->
    ${paths.length ? (() => {
      // Drop the Status column entirely when no path reports a status —
      // saves a wasted column of dashes for the common case.
      const hasStatus = paths.some(p => p.status);
      return `
    <div class="card mt-4">
      ${sectionTitle("file", "Pixellot Storage Paths")}
      <table class="data-table"><thead><tr>
        <th>Path</th><th>Size</th><th>Files</th>
      </tr></thead><tbody>
      ${paths.map(p => `<tr>
        <td class="font-mono text-xs">${esc(p.path)}</td>
        <td class="font-semibold">${p.sizeGB != null ? esc(String(p.sizeGB)) + " GB" : esc(p.error || "—")}</td>
        <td class="text-pulse-muted">${p.fileCount != null ? esc(Number(p.fileCount).toLocaleString()) : "—"}</td>
      </tr>`).join("")}
      </tbody></table>
    </div>`;
    })() : ""}

    <!-- Physical Disks -->
    ${physical.length ? `
    <div class="card mt-4">
      ${sectionTitle("hdd", "Physical Disks")}
      <table class="data-table"><thead><tr>
        <th>Name</th><th>Type</th><th>Bus</th><th>Size</th><th title="Percentage of the SSD's rated write life used. From the drive's SMART/reliability counters.">Wear</th><th>Temp</th><th title="Total powered-on hours">Power-On</th><th>Health</th>
      </tr></thead><tbody>
      ${physical.map(d => {
        const s = d.smart || {};
        const wearStr = s.wearPercent != null ? s.wearPercent + "%" : "—";
        const wearCls = s.wearPercent != null && s.wearPercent >= 80 ? "status-warn" : "";
        const tempStr = s.temperatureC != null ? s.temperatureC + "°C" : "—";
        const tempCls = s.temperatureC != null && s.temperatureC >= 60 ? "status-warn" : "";
        const hoursStr = s.powerOnHours != null ? Number(s.powerOnHours).toLocaleString() + " h" : "—";
        // operationalStatus carries the actionable detail (e.g. "Predictive
        // Failure") that the coarse health rollup hides — surface it only when
        // it's not the boring "OK".
        const op = (d.operationalStatus || "").trim();
        const opLine = op && op.toLowerCase() !== "ok"
          ? `<div class="text-xs status-warn">${esc(op)}</div>` : "";
        return `<tr>
        <td>${esc(d.friendlyName)}</td>
        <td>${esc(d.mediaType)}</td>
        <td>${esc(d.busType)}</td>
        <td>${d.sizeGB != null ? esc(String(d.sizeGB)) + " GB" : "—"}</td>
        <td class="font-mono ${wearCls}">${esc(wearStr)}</td>
        <td class="font-mono ${tempCls}">${esc(tempStr)}</td>
        <td class="font-mono text-xs text-pulse-muted">${esc(hoursStr)}</td>
        <td>${statusBadge(d.healthStatus || "Unknown")}${opLine}</td>
      </tr>`;
      }).join("")}
      </tbody></table>
    </div>` : ""}

    <!-- Recent Disk Events -->
    ${events.length ? `
    <div class="card mt-4">
      ${sectionTitle("triangle", "Recent Disk Events")}
      <div class="max-h-60 overflow-y-auto">
        <table class="data-table"><thead><tr>
          <th>Time</th><th>Level</th><th>Source</th><th>Message</th>
        </tr></thead><tbody>
        ${events.map(e => `<tr>
          <td class="text-xs whitespace-nowrap">${formatTime(e.timeCreated)}</td>
          <td>${statusBadge(e.level)}</td>
          <td class="text-xs">${esc(e.source)}</td>
          <td class="text-xs dh-event-msg" title="${esc(e.message)}">${esc(e.message)}</td>
        </tr>`).join("")}
        </tbody></table>
      </div>
    </div>` : ""}

    <!-- Repair Tools (PDF #1) — GATED OFF for beta. DISM / sfc / chkdsk are
         destructive/long-running and we don't want beta testers running them
         unprompted. The _repairCard / _runRepairTool helpers, the
         /api/disk-health/repair endpoint, and Invoke-RepairTool.ps1 are all
         left intact — to re-enable, restore the card block below (see git
         history for commit that gated it). -->
  `;

  // Repair-tool button wiring is a no-op while the card is gated (no
  // .dh-repair-btn elements rendered). Kept for an easy restore.
  document.querySelectorAll(".dh-repair-btn").forEach(btn => {
    btn.addEventListener("click", () => _runRepairTool(btn.dataset.action));
  });

  document.getElementById("dh-cleanup-review")
    ?.addEventListener("click", _loadCleanupPreview);
  document.getElementById("dh-cleanup-dismiss")
    ?.addEventListener("click", () => { _cleanupReceipt = null; renderDiskHealth(); });
}

function _repairCard(action, title, body, command, amber) {
  const cls = amber ? "btn-ol-amber" : "btn-ol-blue";
  return `<div class="dh-repair-card">
    <div class="dh-repair-title">${esc(title)}</div>
    <div class="dh-repair-body">${esc(body)}</div>
    <div class="dh-repair-cmd font-mono">${esc(command)}</div>
    <button class="btn-outline ${cls} dh-repair-btn" data-action="${esc(action)}">
      ${svgIcon("play", 12)} Run
    </button>
    <div class="dh-repair-result hidden" id="dh-repair-result-${esc(action)}"></div>
  </div>`;
}

async function _runRepairTool(action) {
  const titles = {
    CheckHealth: "Check Image Health",
    RestoreHealth: "Restore Image",
    SfcScan: "Scan System Files",
    ChkdskSchedule: "Schedule a disk check (chkdsk)",
  };
  const slow = action === "RestoreHealth" || action === "SfcScan";
  if (slow) {
    const ok = confirm(
      `${titles[action]} can take 10–30 minutes to complete. ` +
      `Pulse will block waiting for it.\n\nProceed?`
    );
    if (!ok) return;
  }

  const btn = document.querySelector(`.dh-repair-btn[data-action="${action}"]`);
  const result = document.getElementById(`dh-repair-result-${action}`);
  if (!btn || !result) return;

  btn.disabled = true;
  btn.innerHTML = `${svgIcon("refresh", 12)} Running…`;
  result.classList.remove("hidden");
  result.innerHTML = `<div class="text-xs text-pulse-muted">Running ${esc(titles[action] || action)}… ${slow ? "this may take a long time." : ""}</div>`;

  const r = await apiPost("/api/disk-health/repair", { action });

  btn.disabled = false;
  btn.innerHTML = `${svgIcon("play", 12)} Run again`;

  if (!r || r.error) {
    result.innerHTML = `<div class="dh-repair-result-err">
      ${svgIcon("alert", 14)} <span class="font-semibold">Failed</span>
      <div class="text-xs mt-1">${esc(r?.message || "(no message)")}</div>
    </div>`;
    return;
  }

  const okState = !!r.success;
  const durSec = r.durationMs ? Math.round(r.durationMs / 1000) : null;
  result.innerHTML = `
    <div class="${okState ? "dh-repair-result-ok" : "dh-repair-result-err"}">
      ${svgIcon(okState ? "check" : "alert", 14)}
      <span class="font-semibold">${okState ? "Completed" : (r.timedOut ? "Timed out" : "Failed")}</span>
      ${durSec != null ? ` <span class="text-xs text-pulse-muted">· ${durSec}s · exit code ${esc(String(r.exitCode))}</span>` : ""}
    </div>
    <details class="dh-repair-details mt-2">
      <summary class="text-xs text-pulse-muted">Command output</summary>
      <pre class="dh-repair-output">${esc(r.stdout || "(empty)")}</pre>
      ${r.stderr ? `<pre class="dh-repair-output dh-repair-stderr">${esc(r.stderr)}</pre>` : ""}
    </details>
    ${(r.cbsTail || []).length ? `
      <details class="dh-repair-details">
        <summary class="text-xs text-pulse-muted">CBS.log tail (last ${r.cbsTail.length} lines)</summary>
        <pre class="dh-repair-output">${esc((r.cbsTail || []).join("\n"))}</pre>
      </details>
    ` : ""}
  `;
}

// ── Storage Cleanup (D: recordings) ──────────────────────────
// Pulse's first destructive action. The preview endpoint enumerates what
// the rules would delete; the tech reviews counts/sizes/names and confirms;
// the cleanup endpoint re-enumerates server-side with the same rules and
// deletes. The receipt survives re-renders (module var) so the card can
// keep showing what happened after D: drops back under the 90% gate.
let _cleanupReceipt = null;

async function _loadCleanupPreview() {
  const btn = document.getElementById("dh-cleanup-review");
  const body = document.getElementById("dh-cleanup-body");
  if (!btn || !body) return;
  btn.disabled = true;
  body.innerHTML = `<div class="text-xs text-pulse-muted">
    Measuring what can be deleted — on a full drive this can take a minute or two…
  </div>`;

  const p = await api("/api/disk-health/cleanup-preview");
  btn.disabled = false;

  if (!p || p.error) {
    body.innerHTML = `<div class="dh-repair-result-err">
      ${svgIcon("alert", 14)} <span class="font-semibold">Preview failed</span>
      <div class="text-xs mt-1">${esc(p?.message || "(no message)")}</div>
    </div>`;
    return;
  }
  if (p.rootExists === false) {
    body.innerHTML = `<p class="text-sm text-pulse-muted">
      No ${esc(p.root || "D:\\recordedevents")} folder found — nothing to clean up.
    </p>`;
    return;
  }

  const daily = p.dailyTest || {};
  const recs = p.recordings || {};
  const totalCount = (daily.count || 0) + (recs.count || 0);
  if (totalCount === 0) {
    body.innerHTML = `<p class="text-sm text-pulse-muted">
      Nothing is old enough to delete: ${esc(String(p.totalFolders ?? 0))} folders checked,
      ${esc(String(p.skippedRecent ?? 0))} kept because they're newer than the limits.
      Space on D: is being used by recent recordings — escalate rather than deleting them.
    </p>`;
    return;
  }

  const bucketRow = (label, b) => (b.count || 0) === 0 ? "" : `<tr>
    <td>${esc(label)}</td>
    <td class="font-semibold">${esc(String(b.count))}</td>
    <td class="font-semibold">${b.sizeGB != null ? esc(String(b.sizeGB)) + " GB" : "—"}</td>
    <td class="text-pulse-muted text-xs">${esc(b.oldest || "—")} → ${esc(b.newest || "—")}</td>
  </tr>`;
  const candidates = p.candidates || [];

  body.innerHTML = `
    <table class="data-table"><thead><tr>
      <th>What</th><th>Folders</th><th>Size</th><th>Date range</th>
    </tr></thead><tbody>
      ${bucketRow("Daily test clips older than 90 days", daily)}
      ${bucketRow("Game recordings older than 1 year", recs)}
    </tbody></table>
    <p class="text-sm mt-2">
      Deleting all ${esc(String(totalCount))} folders frees
      <b>${p.totalSizeGB != null ? esc(String(p.totalSizeGB)) : "—"} GB</b>
      ${p.projectedUsedPercent != null
        ? `— D: would drop to <b>${esc(String(p.projectedUsedPercent))}% full</b>
           (${esc(String(p.projectedFreeGB))} GB free)` : ""}.
      ${p.skippedRecent ? `${esc(String(p.skippedRecent))} newer folders are protected and won't be touched.` : ""}
    </p>
    ${candidates.length ? `
    <details class="dh-repair-details">
      <summary class="text-xs text-pulse-muted">Every folder that will be deleted (${candidates.length})</summary>
      <pre class="dh-repair-output">${esc(candidates.map(c =>
        `${c.date}  ${c.category === "dailytest" ? "test clip" : "recording"}  ${c.sizeMB != null ? c.sizeMB + " MB" : ""}  ${c.name}`
      ).join("\n"))}</pre>
    </details>` : ""}
    <button class="btn-outline btn-ol-red mt-2" id="dh-cleanup-run">
      ${svgIcon("alert", 14)} Permanently delete ${esc(String(totalCount))} folders…
    </button>
  `;
  document.getElementById("dh-cleanup-run")
    ?.addEventListener("click", () => _runStorageCleanup(p));
}

async function _runStorageCleanup(preview) {
  const daily = preview.dailyTest || {};
  const recs = preview.recordings || {};
  const totalCount = (daily.count || 0) + (recs.count || 0);
  const lines = [];
  if (daily.count) lines.push(`• ${daily.count} daily test clips older than 90 days (${daily.sizeGB} GB)`);
  if (recs.count) lines.push(`• ${recs.count} game recordings older than 1 year (${recs.sizeGB} GB)`);
  const ok = confirm(
    `Permanently delete ${totalCount} folders from D:\\recordedevents?\n\n` +
    lines.join("\n") + "\n\n" +
    "This cannot be undone — the folders do not go to the Recycle Bin.\n" +
    "Nothing from the last 90 days will be touched.\n\nProceed?"
  );
  if (!ok) return;

  const btn = document.getElementById("dh-cleanup-run");
  const body = document.getElementById("dh-cleanup-body");
  if (btn) { btn.disabled = true; btn.innerHTML = `${svgIcon("refresh", 14)} Deleting…`; }
  if (body) body.insertAdjacentHTML("beforeend",
    `<div class="text-xs text-pulse-muted mt-2" id="dh-cleanup-progress">
      Deleting ${esc(String(totalCount))} folders — this can take several minutes…
    </div>`);

  const r = await apiPost("/api/disk-health/cleanup", { confirm: true });
  _cleanupReceipt = r || { error: true, message: "(no response)" };
  dataCache["disk-health"] = null;
  renderDiskHealth();
}

function _cleanupReceiptHtml() {
  const r = _cleanupReceipt;
  if (!r) return "";
  const dismiss = `<button class="btn-outline btn-ol-blue mt-2" id="dh-cleanup-dismiss">Dismiss</button>`;
  if (r.error) {
    return `<div class="dh-repair-result-err">
      ${svgIcon("alert", 14)} <span class="font-semibold">Cleanup failed</span>
      <div class="text-xs mt-1">${esc(r.message || "(no message)")}</div>
    </div>${dismiss}`;
  }
  const after = r.after || {};
  const parts = [];
  if (r.deletedDailyTest) parts.push(`${r.deletedDailyTest} daily test clips`);
  if (r.deletedRecordings) parts.push(`${r.deletedRecordings} game recordings`);
  return `
    <div class="${r.failedCount ? "dh-repair-result-err" : "dh-repair-result-ok"}">
      ${svgIcon(r.failedCount ? "alert" : "check", 14)}
      <span class="font-semibold">Cleanup ${r.failedCount ? "finished with errors" : "complete"}</span>
      <div class="text-xs mt-1">
        Deleted ${esc(String(r.deletedCount ?? 0))} folders${parts.length ? ` (${esc(parts.join(", "))})` : ""},
        freeing ${esc(String(r.freedGB ?? "—"))} GB.
        ${after.usedPercent != null ? `D: is now ${esc(String(after.usedPercent))}% full (${esc(String(after.freeGB))} GB free).` : ""}
      </div>
    </div>
    ${(r.failed || []).length ? `
    <details class="dh-repair-details mt-2" open>
      <summary class="text-xs status-warn">${r.failed.length} folders could not be deleted</summary>
      <pre class="dh-repair-output">${esc(r.failed.map(f => `${f.name}: ${f.error}`).join("\n"))}</pre>
    </details>` : ""}
    ${(r.deleted || []).length ? `
    <details class="dh-repair-details mt-2">
      <summary class="text-xs text-pulse-muted">Deleted folders (${r.deleted.length})</summary>
      <pre class="dh-repair-output">${esc(r.deleted.map(d =>
        `${d.date}  ${d.category === "dailytest" ? "test clip" : "recording"}  ${d.sizeMB != null ? d.sizeMB + " MB" : ""}  ${d.name}`
      ).join("\n"))}</pre>
    </details>` : ""}
    ${dismiss}`;
}

function formatTime(iso) {
  if (!iso) return "--";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return esc(iso);
  }
}

// ── Event Viewer ─────────────────────────────────────────────

// ── Reboots ──────────────────────────────────────────────────
// "Why did this VPU restart, and is one pending?" Built from the System log
// (1074/1076/6008/41). A reboot Pulse itself triggered is positively labeled —
// Reboot-Vpu.ps1 stamps the event Comment, so an empty/other comment is proof
// it was external (a scheduled task, Windows Update, or a crash).
function renderReboots() {
  const data = cached("reboots");
  if (!data) { $page().innerHTML = sectionLoading("Reboot History"); fetchSection("reboots"); return; }
  if (data.error) { $page().innerHTML = errorBox(data.message); return; }

  const pending = data.pending || {};
  const isPending = !!pending.isPending;
  const reasons = pending.reasons || [];
  const history = data.history || [];
  const diTask = data.deviceInstallRebootTaskLastRun;

  function sumCard(icon, title, sev, chip, val, desc) {
    return `<div class="card dh-summary-card">
      <div class="dh-summary-top">
        <span class="dh-summary-icon">${svgIcon(icon, 18)}</span>
        <span class="dh-summary-title">${esc(title)}</span>
        ${severityChip(sev, chip)}
      </div>
      <div class="dh-summary-val">${esc(val)}</div>
      <div class="dh-summary-desc">${esc(desc)}</div>
    </div>`;
  }

  const pendCard = sumCard(
    isPending ? "alert" : "check", "Pending reboot",
    isPending ? "warning" : "ok", isPending ? "Reboot pending" : "None pending",
    isPending ? reasons.join("; ") : "Nothing is waiting on a restart",
    isPending ? "Windows may restart on its own — reboot at a safe time to clear it."
              : "No staged updates or pending file operations.");

  const uptimeCard = sumCard(
    "clock", "Uptime", "muted", "Since last boot",
    data.uptime || "—",
    data.lastBoot ? `Last boot ${formatTime(data.lastBoot)}` : "Last boot unknown");

  const diCard = sumCard(
    "zap", "Device-install reboot", diTask ? "info" : "muted", diTask ? "Has fired" : "Never",
    diTask ? formatTime(diTask) : "Not on this box",
    "Windows' built-in task that reboots after a driver install — the usual cause of an “unprovoked” restart at logon.");

  function row(h) {
    const typeChip = h.category === "unexpected"
      ? severityChip("critical", "Unexpected")
      : severityChip("muted", "Planned");
    const src = h.byPulse
      ? `<span class="sev-chip sev-chip-ok">${svgIcon("shield", 12)} ${esc(h.source || "Pulse")}</span>`
      : esc(h.source || "—");
    const reason = [h.reasonText, h.reasonCode].filter(Boolean).map(esc).join(" ");
    return `<tr>
      <td class="text-xs whitespace-nowrap font-mono">${formatTime(h.time)}</td>
      <td>${typeChip}</td>
      <td class="text-xs">${src}</td>
      <td class="text-xs font-mono">${esc(h.user || "—")}</td>
      <td class="text-xs">${reason || "—"}${h.process ? `<br><span class="text-pulse-muted font-mono">${esc(h.process)}</span>` : ""}</td>
      <td class="text-xs">${h.comment ? esc(h.comment) : '<span class="text-pulse-muted">— (empty: not Pulse)</span>'}</td>
    </tr>`;
  }

  const table = history.length ? `
    <div class="card mt-4">
      <div class="ev-count">${history.length} restart / shutdown event${history.length === 1 ? "" : "s"} (last 7 days)</div>
      <div class="ev-table-wrap">
        <table class="data-table ev-table"><thead><tr>
          <th>When</th><th>Type</th><th>Source</th><th>User</th><th>Reason / process</th><th>Comment</th>
        </tr></thead><tbody>
        ${history.map(row).join("")}
        </tbody></table>
      </div>
    </div>`
    : '<div class="card mt-4"><div class="text-center py-8 text-pulse-muted">No restarts or shutdowns recorded in the last 7 days.</div></div>';

  $page().innerHTML = `
    ${pageHeader("Power Events", "Why this VPU last restarted, and whether a reboot is pending. Reboots Pulse itself triggered are labeled — everything else is external.",
      `<button class="btn-outline btn-ol-blue" onclick="dataCache['reboots']=null;renderReboots()">${svgIcon("refresh", 14)} Refresh</button>`
    )}
    <div class="dh-summary-row">${pendCard}${uptimeCard}${diCard}</div>
    ${table}
  `;
}

function renderEvents() {
  $page().innerHTML = `
    ${pageHeader("Windows Events", "Recent Windows log entries for disk, network, Pixellot, and core services",
      `<button class="btn-outline btn-ol-blue" id="ev-refresh">
        ${svgIcon("refresh", 14)} Refresh
      </button>`
    )}

    <!-- Filter Row -->
    <div class="card ev-filter-card">
      <div class="ev-filter-row">
        <div class="ev-filter-group">
          <label class="ev-filter-label" for="ev-hours">TIME WINDOW</label>
          <select id="ev-hours" class="ev-select">
            <option value="12">Last 12 hours</option>
            <option value="24">Last 24 hours</option>
            <option value="48" selected>Last 48 hours</option>
            <option value="168">Last 7 days</option>
          </select>
        </div>
        <div class="ev-filter-group">
          <label class="ev-filter-label">LEVELS</label>
          <div class="ev-checks">
            <label class="ev-check"><input type="checkbox" id="ev-error" checked> <span style="color:var(--c-accent-red)">Error</span></label>
            <label class="ev-check"><input type="checkbox" id="ev-warning" checked> <span style="color:var(--c-accent-amber)">Warning</span></label>
            <label class="ev-check"><input type="checkbox" id="ev-info" checked> <span style="color:var(--c-accent-blue)">Information</span></label>
          </div>
        </div>
        <div class="ev-filter-group ev-filter-grow">
          <label class="ev-filter-label">SOURCE OR MESSAGE CONTAINS</label>
          <input type="text" id="ev-source" placeholder="e.g. disk, Pixellot, hardware error" class="ev-input"/>
        </div>
      </div>
    </div>

    <div class="card mt-4" id="ev-body">${loading()}</div>
  `;

  const loadEvents = async () => {
    const hours = document.getElementById("ev-hours").value;
    const evBody = document.getElementById("ev-body");
    evBody.innerHTML = loading();
    const data = await api(`/api/events?hours=${encodeURIComponent(hours)}&level=all`);
    if (currentPage !== "events") return;
    if (data.error) { evBody.innerHTML = errorBox(data.message); return; }

    const showError = document.getElementById("ev-error")?.checked;
    const showWarning = document.getElementById("ev-warning")?.checked;
    const showInfo = document.getElementById("ev-info")?.checked;
    const sourceFilter = (document.getElementById("ev-source")?.value || "").toLowerCase();

    let entries = data.entries || [];
    entries = entries.filter(e => {
      const lvl = (e.level || "").toLowerCase();
      if (lvl === "error" && !showError) return false;
      if (lvl === "warning" && !showWarning) return false;
      if ((lvl === "information" || lvl === "info") && !showInfo) return false;
      if (sourceFilter && !(e.source || "").toLowerCase().includes(sourceFilter) && !(e.message || "").toLowerCase().includes(sourceFilter)) return false;
      return true;
    });

    if (!entries.length) {
      evBody.innerHTML = '<div class="text-center py-8 text-pulse-muted">No events found for this filter.</div>';
      return;
    }

    function levelChip(level) {
      const l = (level || "").toLowerCase();
      if (l === "error") return '<span class="ev-level-chip ev-level-error">Error</span>';
      if (l === "warning") return '<span class="ev-level-chip ev-level-warn">Warning</span>';
      return '<span class="ev-level-chip ev-level-info">Information</span>';
    }

    evBody.innerHTML = `
      <div class="ev-count">${entries.length} events</div>
      <div class="ev-table-wrap">
        <table class="data-table ev-table"><thead><tr>
          <th>Timestamp</th><th>Level</th><th>Source</th><th>Event ID</th><th>Message</th>
        </tr></thead><tbody>
        ${entries.map(e => `<tr>
          <td class="text-xs whitespace-nowrap font-mono">${formatTime(e.timeCreated)}</td>
          <td>${levelChip(e.level)}</td>
          <td class="text-xs">${esc(e.source)}</td>
          <td class="text-xs font-mono">${esc(String(e.eventId || ""))}</td>
          <td class="text-xs ev-msg-cell" title="${esc(e.message)}">${esc(e.message)}</td>
        </tr>`).join("")}
        </tbody></table>
      </div>
    `;
  };

  document.getElementById("ev-refresh")?.addEventListener("click", loadEvents);
  document.getElementById("ev-hours")?.addEventListener("change", loadEvents);
  ["ev-error", "ev-warning", "ev-info"].forEach(id => {
    document.getElementById(id)?.addEventListener("change", loadEvents);
  });
  document.getElementById("ev-source")?.addEventListener("input", _debounce(loadEvents, 300));
  loadEvents();
}

// ── Pixellot Logs ────────────────────────────────────────────
// Scans C:\Pixellot\Data\Log for error / fatal / restart markers (PDF #5),
// flagging CUDNN/TensorFlow dependency errors so the tech can escalate to
// Pixellot support. Was a card on Windows Events; now its own tab under DATA LOGS.
function renderPixellotLogs() {
  $page().innerHTML = `
    ${pageHeader("Pixellot Logs", "Errors, fatals, and process restarts scanned from the Pixellot log directory.",
      `<button class="btn-outline btn-ol-blue" id="pxl-refresh">${svgIcon("refresh", 14)} Refresh</button>`
    )}

    <div class="card ev-filter-card">
      <div class="ev-filter-row">
        <div class="ev-filter-group">
          <label class="ev-filter-label" for="pxl-hours">TIME WINDOW</label>
          <select id="pxl-hours" class="ev-select">
            <option value="12">Last 12 hours</option>
            <option value="24" selected>Last 24 hours</option>
            <option value="48">Last 48 hours</option>
            <option value="168">Last 7 days</option>
          </select>
        </div>
      </div>
    </div>

    <div class="card mt-4" id="pxl-body">${loading()}</div>
  `;

  document.getElementById("pxl-refresh")?.addEventListener("click", _loadPixellotLogs);
  document.getElementById("pxl-hours")?.addEventListener("change", _loadPixellotLogs);
  _loadPixellotLogs();
}

async function _loadPixellotLogs() {
  const hours = document.getElementById("pxl-hours")?.value || "24";
  const body = document.getElementById("pxl-body");
  if (!body) return;
  body.innerHTML = loading();
  const data = await api(`/api/pixellot-logs?hours=${encodeURIComponent(hours)}`);
  if (currentPage !== "pixellot-logs") return;
  const el = document.getElementById("pxl-body");
  if (!el) return;

  if (data.error) {
    el.innerHTML = `${sectionTitle("file", "Pixellot Logs")}
      <p class="text-sm text-pulse-muted">${esc(data.message || "Failed to scan Pixellot logs")}</p>`;
    return;
  }

  const entries = data.entries || [];
  const stats = data.stats || {};
  const depsErr = !!data.depsErrorDetected;

  const levelChip = (lvl) => {
    const l = (lvl || "").toLowerCase();
    // Distinct visual class per severity — Fatal solid-fill (showstopper),
    // Error red-outline (single failure), Restart blue-outline (lifecycle
    // event, not a problem).
    if (l === "fatal")   return '<span class="ev-level-chip ev-level-fatal">Fatal</span>';
    if (l === "error")   return '<span class="ev-level-chip ev-level-error">Error</span>';
    if (l === "restart") return '<span class="ev-level-chip ev-level-restart">Restart</span>';
    return `<span class="ev-level-chip ev-level-info">${esc(l)}</span>`;
  };

  el.innerHTML = `
    ${sectionTitle("file", "Pixellot Logs")}
    <p class="text-xs text-pulse-muted mb-3">
      Scanned ${esc(String(data.scannedFiles || 0))} log file(s) in <span class="font-mono">C:\\Pixellot\\Data\\Log</span> over the last ${esc(String(data.hoursBack || ""))} hour(s).
    </p>

    <div class="px-log-summary">
      <span class="px-log-stat ${stats.fatal > 0 ? 'px-log-stat-bad' : ''}">${esc(String(stats.fatal || 0))} fatal</span>
      <span class="px-log-stat ${stats.error > 0 ? 'px-log-stat-bad' : ''}">${esc(String(stats.error || 0))} error</span>
      <span class="px-log-stat ${stats.restart > 0 ? 'px-log-stat-warn' : ''}">${esc(String(stats.restart || 0))} restart</span>
    </div>

    ${depsErr ? `<div class="px-log-deps-warn mt-3">
      ${svgIcon("alert", 14)}
      <div>
        <div class="font-semibold">Pixellot video dependency error detected (CUDNN/TensorFlow)</div>
        <div class="text-xs mt-1">A known Pixellot dependency error appeared in the logs. This needs a Pixellot-support-directed dependency reinstall — capture an export and escalate to Pixellot support.</div>
      </div>
    </div>` : ""}

    ${data.warning ? `<p class="text-xs text-pulse-muted mt-2">${esc(data.warning)}</p>` : ""}

    ${entries.length ? `
      <div class="ev-table-wrap mt-3">
        <table class="data-table ev-table"><thead><tr>
          <th>Time</th><th>Level</th><th>File</th><th>Line</th><th>Content</th>
        </tr></thead><tbody>
        ${entries.map(e => `<tr class="${e.depsError ? 'px-log-row-deps' : ''}">
          <td class="text-xs whitespace-nowrap font-mono">${esc(e.timestamp || formatTime(e.fileMTime))}</td>
          <td>${levelChip(e.level)}</td>
          <td class="text-xs font-mono">${esc(e.file)}</td>
          <td class="text-xs font-mono">${esc(String(e.lineNumber || ""))}</td>
          <td class="text-xs ev-msg-cell" title="${esc(e.content)}">${esc(e.content)}${e.depsError ? ' <span class="px-log-deps-pill">DEPS</span>' : ''}</td>
        </tr>`).join("")}
        </tbody></table>
      </div>
      ${data.truncated ? '<p class="text-xs text-pulse-muted mt-2">Results truncated at 500 matches.</p>' : ""}
    ` : '<p class="text-sm text-pulse-muted mt-3">No matching entries.</p>'}
  `;
}

// ── Pulse Logs ───────────────────────────────────────────────
// Pulse's own logs: the diagnostic script-call log (live, from logEntries) and
// the backend server log (pulse-server.log). Full-page promotion of the bottom
// log drawer.
function renderPulseLogs() {
  $page().innerHTML = `
    ${pageHeader("Pulse Logs", "Pulse's own diagnostic script-call log and backend server log.",
      `<button class="btn-outline btn-ol-blue" id="pulse-log-refresh">${svgIcon("refresh", 14)} Refresh</button>`
    )}

    <div class="card">
      ${sectionTitle("activity", "Script Call Log")}
      <p class="text-xs text-pulse-muted mb-3">Every PowerShell diagnostic script Pulse has run this session — duration, output size, and status. Updates live as checks run.</p>
      <div class="pulse-log-scroll" id="pulse-log-script">${loading()}</div>
    </div>

    <div class="card">
      ${sectionTitle("file", "Server Log")}
      <p class="text-xs text-pulse-muted mb-3">The Pulse backend's own log (<span class="font-mono">pulse-server.log</span>) — startup, requests, and errors.</p>
      <div class="pulse-log-scroll" id="pulse-log-server">${loading()}</div>
    </div>
  `;

  _renderPulseLogsScript();
  _loadPulseServerLog();
  document.getElementById("pulse-log-refresh")?.addEventListener("click", () => {
    _renderPulseLogsScript();
    _loadPulseServerLog();
  });
}

function _renderPulseLogsScript() {
  const el = document.getElementById("pulse-log-script");
  if (!el) return;
  const entries = logEntries.slice(-200);
  el.innerHTML = entries.length
    ? entries.map(_scriptLogEntryHtml).join("")
    : _logEmptyState("Waiting for diagnostic activity… script calls will appear here.");
  el.scrollTop = el.scrollHeight;
}

async function _loadPulseServerLog() {
  const el = document.getElementById("pulse-log-server");
  if (!el) return;
  const data = await api("/api/server-log?tail=500");
  if (currentPage !== "pulse-logs") return;
  const el2 = document.getElementById("pulse-log-server");
  if (!el2) return;
  const lines = (data && !data.error) ? (data.lines || []) : null;
  el2.innerHTML = (lines && lines.length)
    ? lines.map((l) => `<div class="log-entry server-log-line">${esc(l)}</div>`).join("")
    : _logEmptyState((data && data.error)
        ? (data.message || "Could not read the server log.")
        : "Server log empty. The server logs to pulse-server.log on startup and during requests.");
  el2.scrollTop = el2.scrollHeight;
}

// ── Help ─────────────────────────────────────────────────────
// Static how-to + first-line troubleshooting for field techs. No data fetch.
function renderHelp() {
  $page().innerHTML = `
    ${pageHeader("Help", "What Pulse is, how to read it, and the first things to try in the field.")}

    <div class="card">
      ${sectionTitle("info", "What Pulse is")}
      <p class="text-sm" style="line-height:1.7">Pulse is a read-only diagnostic tool for Pixellot VPUs. It collects the VPU's
      health — network, cameras, ScoreConnect, Pixellot software, system hardware, disks, and logs — into one place so you can
      tell, fast, whether a unit can stream tonight's game and what's standing in the way. Pulse does not change Pixellot
      settings; the few actions it offers (restart the Pixellot Agent, restart a service) are clearly labeled.</p>
    </div>

    <div class="card">
      ${sectionTitle("grid", "Reading the Dashboard")}
      <ul class="help-list">
        <li><strong>Stream Readiness</strong> is the headline call — <span class="status-pass">PASS</span>,
        <span class="status-warn">WARN</span>, or <span class="status-fail">FAIL</span> on whether this VPU can broadcast.
        FAIL means don't expect a clean broadcast without pre-game attention.</li>
        <li><strong>Findings</strong> list the specific issues behind the verdict, worst first. Click any finding to jump
        straight to the tab that owns the fix.</li>
        <li><strong>Sidebar warning triangles</strong> mark which areas have an open issue, so you know where to look
        without opening every tab.</li>
      </ul>
    </div>

    <div class="card">
      ${sectionTitle("wifi", "First things to try")}
      <ul class="help-list">
        <li><strong>No internet / can't reach services</strong> — On a VPU the venue/internet cable goes to the
        <em>motherboard</em> network port, not the 4-port camera card. Check <strong>Network Test</strong>; Pulse flags it
        if the cable is on the wrong port.</li>
        <li><strong>A camera is missing or slow</strong> — Check <strong>Camera Connectivity</strong> for the port's link
        and speed (camera ports should be 1 Gbps), then <strong>Camera Hardware</strong> for firmware and reachability.</li>
        <li><strong>Scores aren't showing</strong> — Check <strong>ScoreConnect</strong> for the service and the
        scoreboard feed, and confirm the OCR camera is calibrated under <strong>Calibrations</strong>.</li>
        <li><strong>Pixellot Agent looks stuck</strong> — <strong>Service Status</strong> shows the Agent / Coordinator /
        Watchdog. The documented first fix is <strong>Restart Agent + Coordinator</strong> on the
        <strong>Pixellot Software</strong> tab.</li>
        <li><strong>Recording errors / disk filling up</strong> — Check <strong>Disks</strong> for free space and drive
        health, and scan <strong>Pixellot Logs</strong> for fatal/restart markers (it flags the known CUDNN/TensorFlow
        dependency error).</li>
      </ul>
    </div>

    <div class="card">
      ${sectionTitle("inbox", "Capturing evidence for support")}
      <ul class="help-list">
        <li>Use <strong>Exports</strong> to generate a downloadable report to attach to a ticket — it re-runs
        every check and bundles the results into one file.</li>
        <li><strong>Pulse Logs</strong> shows Pulse's own script and server logs if Pulse itself is misbehaving.</li>
      </ul>
    </div>
  `;
}

// ── Reports ──────────────────────────────────────────────────

function renderReports() {
  // Reports page used to host both Generate Report (its primary action,
  // in the top-right) AND Run All Diagnostics (which belongs on Dashboard
  // — same button appears there). We move Generate Report INTO the card
  // describing it so action sits with its explanation, and drop the
  // redundant Run All Diagnostics button.
  $page().innerHTML = `
    ${pageHeader("Exports", "Diagnostic-run snapshots — generate and download full system reports")}

    <div class="card">
      ${sectionTitle("file", "Full Diagnostic Export")}
      <p class="text-sm text-pulse-muted mb-4">Generate a complete diagnostic report covering system, network, and service data. This runs every check and bundles the results into one downloadable file.</p>
      <button class="btn-outline btn-ol-green" id="rpt-export">
        ${svgIcon("download", 14)} Generate Report
      </button>
      <span id="rpt-status" class="text-sm text-pulse-muted ml-3"></span>
      <div id="rpt-result" class="mt-4"></div>
    </div>
  `;

  document.getElementById("rpt-export")?.addEventListener("click", async () => {
    const btn = document.getElementById("rpt-export");
    const status = document.getElementById("rpt-status");
    btn.disabled = true;
    status.textContent = "Running all checks...";
    const data = await api("/api/reports/export");
    btn.disabled = false;
    if (data.error) {
      status.textContent = "Error: " + (data.message || "Unknown");
      return;
    }
    status.textContent = "Report ready.";

    const meta = data._meta || {};
    const sectionCount = Object.keys(data).filter((k) => k !== "_meta").length;
    const findingCount = Array.isArray(data.findings) ? data.findings.length : 0;
    const errKeys = Object.keys(meta.sourceErrors || {});
    const summaryHtml = `
      <div class="text-sm text-pulse-muted mb-3">
        ${sectionCount} sections · ${findingCount} finding${findingCount === 1 ? "" : "s"} ·
        ${errKeys.length
          ? `<span style="color:var(--c-accent-amber)">${errKeys.length} check${errKeys.length === 1 ? "" : "s"} failed: ${esc(errKeys.join(", "))}</span>`
          : "all checks ran"}
        ${meta.pulseVersion ? " · " + esc(meta.pulseVersion) : ""}${meta.hostname ? " · " + esc(meta.hostname) : ""}
      </div>`;

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const hostname = data.identity?.computerSystem?.name || "vpu";
    const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    const filename = "pulse-report-" + hostname + "-" + ts + ".json";

    document.getElementById("rpt-result").innerHTML = `
      ${summaryHtml}
      <a href="${url}" download="${esc(filename)}" class="btn-outline btn-ol-green" style="display:inline-flex;align-items:center;gap:6px">
        ${svgIcon("download", 14)} Download ${esc(filename)}
      </a>
      <details class="mt-4">
        <summary class="text-sm text-pulse-muted cursor-pointer">Preview data</summary>
        <pre class="mt-2 p-4 bg-pulse-bg rounded text-xs overflow-auto max-h-96 text-pulse-muted">${esc(JSON.stringify(data, null, 2))}</pre>
      </details>
    `;
  });
}

// ── Share over LAN ───────────────────────────────────────────
// Push the diagnostic snapshot to another Pulse on the same network. The
// receiving side opts in (the only time Pulse listens on the LAN); the sender
// pastes the receiver's pairing code and hits Send. Backend: peer.py + the
// /api/peer/* routes in main.py.
//
// NOTE on rendering: the page SHELL below is a static template (innerHTML, no
// data interpolation). Everything peer-supplied — pairing codes, hostnames,
// IPs, report JSON — is built with textContent/createElement in the helpers,
// so untrusted data never reaches innerHTML.

var _shareInbox = { key: null, poll: null };

function _mk(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}

function _shareSetMsg(el, text, color) {
  if (!el) return;
  el.textContent = text || "";
  el.style.color = color || "";
}

function renderShare() {
  $page().innerHTML = `
    ${pageHeader("Share over LAN", "Send this VPU's diagnostic snapshot to another Pulse on the same network")}

    <div class="card">
      ${sectionTitle("send", "Send to another Pulse")}
      <p class="text-sm text-pulse-muted mb-3">Paste the <strong>pairing code</strong> from the receiving Pulse, then Send. (On that machine: Share over LAN → enable "Receive over LAN".) No file to move — Pulse sends the snapshot straight over.</p>
      <input type="text" id="share-code" class="settings-input" placeholder="Pairing code, e.g. tiger maple river copper dust" autocomplete="off" spellcheck="false" style="max-width:480px"/>
      <details class="mt-2" style="max-width:420px">
        <summary class="text-sm text-pulse-muted cursor-pointer">Receiver has more than one network? Override the address</summary>
        <input type="text" id="share-addr" class="settings-input mt-2" placeholder="192.168.1.42:8766 (optional)" autocomplete="off" spellcheck="false"/>
      </details>
      <div class="settings-actions">
        <button class="btn-outline btn-ol-blue" id="share-test">${svgIcon("activity", 14)} Test connection</button>
        <button class="btn-outline btn-ol-green" id="share-send">${svgIcon("send", 14)} Send snapshot</button>
        <span id="share-send-msg" class="text-sm text-pulse-muted"></span>
      </div>
      <div id="share-send-result" class="mt-3"></div>
    </div>

    <div class="card mt-4">
      ${sectionTitle("inbox", "Receive over LAN")}
      <p class="text-sm text-pulse-muted mb-3">Turn this on to let another Pulse send its snapshot to <em>this</em> machine. This opens a port to your local network — Windows may ask you to allow access the first time.</p>
      <div class="settings-actions">
        <button class="btn-outline btn-ol-blue" id="share-recv-toggle">${svgIcon("inbox", 14)} <span id="share-recv-label">Enable receiving</span></button>
        <span id="share-recv-msg" class="text-sm text-pulse-muted"></span>
      </div>
      <div id="share-recv-info" class="mt-3"></div>
      <div id="share-inbox" class="mt-4"></div>
    </div>
  `;

  document.getElementById("share-test").addEventListener("click", _shareTest);
  document.getElementById("share-send").addEventListener("click", _shareSend);
  document.getElementById("share-recv-toggle").addEventListener("click", _shareToggleReceive);
  document.getElementById("share-code").addEventListener("keydown", (e) => { if (e.key === "Enter") _shareSend(); });

  _shareLoadStatus();
  _shareStartInboxPoll();
}

// ── Send (sender side) ──

async function _shareTest() {
  const msg = document.getElementById("share-send-msg");
  const code = (document.getElementById("share-code").value || "").trim();
  const addrEl = document.getElementById("share-addr");
  const addr = ((addrEl && addrEl.value) || "").trim();
  if (!code && !addr) { _shareSetMsg(msg, "Enter a pairing code first."); return; }
  _shareSetMsg(msg, "Testing…");
  const q = "code=" + encodeURIComponent(code) + "&address=" + encodeURIComponent(addr);
  const r = await api("/api/peer/send/ping?" + q);
  if (r.ok) _shareSetMsg(msg, "Reachable — " + (r.hostname || r.address), "var(--c-accent-green)");
  else _shareSetMsg(msg, r.error || "Unreachable", "var(--c-accent-red)");
}

async function _shareSend() {
  const btn = document.getElementById("share-send");
  const msg = document.getElementById("share-send-msg");
  const result = document.getElementById("share-send-result");
  const code = (document.getElementById("share-code").value || "").trim();
  const addrEl = document.getElementById("share-addr");
  const addr = ((addrEl && addrEl.value) || "").trim();
  if (!code) { _shareSetMsg(msg, "Paste the receiver's pairing code.", "var(--c-accent-red)"); return; }
  btn.disabled = true;
  result.textContent = "";
  _shareSetMsg(msg, "Building snapshot and sending…");
  const r = await apiPost("/api/peer/send", { code: code, address: addr });
  btn.disabled = false;
  if (r.ok) {
    _shareSetMsg(msg, "Sent.", "var(--c-accent-green)");
    const line = _mk("div", "text-sm text-pulse-muted");
    line.appendChild(document.createTextNode("Delivered " + formatBytes(r.bytes) + " to "));
    line.appendChild(_mk("strong", null, r.peer || r.address || "peer"));
    line.appendChild(document.createTextNode(". It's now in that machine's Received Reports."));
    result.appendChild(line);
  } else {
    _shareSetMsg(msg, r.error || r.message || "Send failed", "var(--c-accent-red)");
  }
}

// ── Receive (receiver side) ──

async function _shareLoadStatus() {
  _shareRenderReceiveInfo(await api("/api/peer/receive-mode"));
}

async function _shareToggleReceive() {
  const btn = document.getElementById("share-recv-toggle");
  const msg = document.getElementById("share-recv-msg");
  const cur = await api("/api/peer/receive-mode");
  btn.disabled = true;
  _shareSetMsg(msg, cur.on ? "Stopping…" : "Starting…");
  const status = await apiPost("/api/peer/receive-mode", { on: !cur.on });
  btn.disabled = false;
  if (status.error) _shareSetMsg(msg, status.error, "var(--c-accent-red)");
  else _shareSetMsg(msg, "");
  _shareRenderReceiveInfo(status);
}

function _shareRenderReceiveInfo(status) {
  const btn = document.getElementById("share-recv-toggle");
  const label = document.getElementById("share-recv-label");
  const info = document.getElementById("share-recv-info");
  if (!btn || !info) return;
  info.textContent = "";
  if (!status || !status.on) {
    if (label) label.textContent = "Enable receiving";
    btn.classList.remove("btn-ol-red"); btn.classList.add("btn-ol-blue");
    return;
  }
  if (label) label.textContent = "Disable receiving";
  btn.classList.remove("btn-ol-blue"); btn.classList.add("btn-ol-red");

  const wrap = _mk("div", "share-pair");
  wrap.appendChild(_mk("div", "text-sm text-pulse-muted mb-1", "Pairing code — type these 5 words on the sending Pulse"));
  const row = _mk("div", "share-pair-row");
  const codeEl = _mk("span", "share-pair-code", status.code || "");
  codeEl.id = "share-code-display";
  const copyBtn = _mk("button", "btn-outline btn-ol-blue", "Copy");
  copyBtn.addEventListener("click", _shareCopyCode);
  row.appendChild(codeEl); row.appendChild(copyBtn);
  wrap.appendChild(row);

  const addrLine = _mk("div", "text-sm text-pulse-muted mt-2");
  addrLine.appendChild(document.createTextNode("Listening on "));
  addrLine.appendChild(_mk("strong", null, status.address || ""));
  addrLine.appendChild(document.createTextNode(". Leave this page open to keep receiving."));
  wrap.appendChild(addrLine);

  // Interface picker — a multi-NIC host (VPU uplink + camera ports) may pick
  // an IP the peer can't reach. Let the tech choose the one on the sender's
  // network; switching re-points the code without restarting the listener.
  const cands = status.candidates || [];
  if (cands.length > 1) {
    const pick = _mk("div", "share-pick mt-2");
    pick.appendChild(_mk("span", "text-sm text-pulse-muted", "On a different network than your other machine? Use address: "));
    const sel = document.createElement("select");
    sel.className = "share-ip-select";
    cands.forEach((ip) => {
      const o = document.createElement("option");
      o.value = ip; o.textContent = ip;
      if (ip === status.ip) o.selected = true;
      sel.appendChild(o);
    });
    sel.addEventListener("change", () => _shareSelectIp(sel.value));
    pick.appendChild(sel);
    wrap.appendChild(pick);
  }

  // Firewall outcome (Windows opens the port automatically; elsewhere, hint).
  const fw = status.firewall;
  if (fw && (fw.message || fw.error || fw.reason)) {
    const fwLine = _mk("div", "text-sm mt-2", fw.error || fw.message || fw.reason);
    fwLine.style.color = fw.error ? "var(--c-accent-amber)" : "var(--c-muted)";
    wrap.appendChild(fwLine);
  }

  info.appendChild(wrap);
}

async function _shareSelectIp(ip) {
  const status = await apiPost("/api/peer/receive-mode", { on: true, ip: ip });
  _shareRenderReceiveInfo(status);
}

function _shareCopyCode() {
  const el = document.getElementById("share-code-display");
  if (!el || !navigator.clipboard) return;
  navigator.clipboard.writeText(el.textContent);
  const msg = document.getElementById("share-recv-msg");
  if (msg) { _shareSetMsg(msg, "Copied."); setTimeout(() => _shareSetMsg(msg, ""), 1500); }
}

// ── Inbox ──

function _shareStartInboxPoll() {
  if (_shareInbox.poll) clearInterval(_shareInbox.poll);
  _shareInbox.key = null;
  _shareInboxTick();
  _shareInbox.poll = setInterval(_shareInboxTick, 3000);
}

async function _shareInboxTick() {
  // Self-terminate if the user navigated away — the router doesn't clear us.
  if (currentPage !== "share") {
    if (_shareInbox.poll) { clearInterval(_shareInbox.poll); _shareInbox.poll = null; }
    return;
  }
  const r = await api("/api/peer/inbox");
  const reports = (r && r.reports) || [];
  // Only re-render when the set of reports changes, so an open preview doesn't
  // collapse on every poll.
  const key = reports.map((x) => x.id).join(",");
  if (key === _shareInbox.key) return;
  _shareInbox.key = key;
  _shareRenderInbox(reports);
}

function _shareRenderInbox(reports) {
  const host = document.getElementById("share-inbox");
  if (!host) return;
  host.textContent = "";
  if (!reports.length) {
    host.appendChild(_mk("div", "text-sm text-pulse-muted", "No reports received yet."));
    return;
  }
  host.appendChild(_mk("div", "text-sm text-pulse-muted mb-2", "Received Reports (" + reports.length + ")"));
  reports.forEach((r) => {
    const card = _mk("div", "share-rx");
    const head = _mk("div", "share-rx-head");
    const left = _mk("div");
    left.appendChild(_mk("div", "share-rx-host", r.vpuName || r.hostname || "Unknown host"));
    let meta = "Received " + formatTime(r.receivedAt) + " from " + (r.senderIp || "?")
      + " · " + r.findingCount + " finding" + (r.findingCount === 1 ? "" : "s")
      + " · " + formatBytes(r.sizeBytes);
    if (r.sourceErrorCount) meta += " · " + r.sourceErrorCount + " check" + (r.sourceErrorCount === 1 ? "" : "s") + " failed";
    left.appendChild(_mk("div", "text-sm text-pulse-muted", meta));
    const actions = _mk("div", "share-rx-actions");
    const viewBtn = _mk("button", "btn-outline btn-ol-blue", "View");
    viewBtn.addEventListener("click", () => _shareViewReport(r.id));
    const dlBtn = _mk("button", "btn-outline btn-ol-green", "Download");
    dlBtn.addEventListener("click", () => _shareDownloadReport(r.id));
    const delBtn = _mk("button", "btn-outline btn-ol-red", "Delete");
    delBtn.addEventListener("click", () => _shareDeleteReport(r.id));
    actions.appendChild(viewBtn); actions.appendChild(dlBtn); actions.appendChild(delBtn);
    head.appendChild(left); head.appendChild(actions);
    card.appendChild(head);
    const body = _mk("div", "share-rx-body mt-2");
    body.id = "share-rx-body-" + r.id;
    card.appendChild(body);
    host.appendChild(card);
  });
}

function _shareSummaryEl(data) {
  const meta = data._meta || {};
  const sectionCount = Object.keys(data).filter((k) => !k.startsWith("_") && k !== "findings").length;
  const findingCount = Array.isArray(data.findings) ? data.findings.length : 0;
  const errKeys = Object.keys(meta.sourceErrors || {});
  const wrap = _mk("div", "text-sm text-pulse-muted mb-3");
  wrap.appendChild(document.createTextNode(
    sectionCount + " sections · " + findingCount + " finding" + (findingCount === 1 ? "" : "s") + " · "));
  if (errKeys.length) {
    const e = _mk("span", null, errKeys.length + " check" + (errKeys.length === 1 ? "" : "s") + " failed: " + errKeys.join(", "));
    e.style.color = "var(--c-accent-amber)";
    wrap.appendChild(e);
  } else {
    wrap.appendChild(document.createTextNode("all checks ran"));
  }
  const vpuName = data.identity && data.identity.pixellot && data.identity.pixellot.vpuName;
  const name = vpuName || meta.hostname;
  const tail = (meta.pulseVersion ? " · " + meta.pulseVersion : "") + (name ? " · " + name : "");
  if (tail) wrap.appendChild(document.createTextNode(tail));
  return wrap;
}

async function _shareViewReport(id) {
  const body = document.getElementById("share-rx-body-" + id);
  if (!body) return;
  if (body.dataset.open === "1") { body.textContent = ""; body.dataset.open = "0"; return; }
  body.dataset.open = "1";
  body.textContent = "Loading…";
  const data = await api("/api/peer/inbox/" + encodeURIComponent(id));
  body.textContent = "";
  if (data.error) { _shareSetMsg(body, data.error, "var(--c-accent-red)"); return; }
  body.appendChild(_shareSummaryEl(data));
  body.appendChild(_mk("pre", "p-4 bg-pulse-bg rounded text-xs overflow-auto max-h-96 text-pulse-muted",
    JSON.stringify(data, null, 2)));
}

async function _shareDownloadReport(id) {
  const data = await api("/api/peer/inbox/" + encodeURIComponent(id));
  if (data.error) return;
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const hostname = (data._meta && data._meta.hostname) || (data.identity && data.identity.computerSystem && data.identity.computerSystem.name) || "vpu";
  const a = _mk("a");
  a.href = url;
  a.download = "pulse-report-" + hostname + "-" + id + ".json";
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function _shareDeleteReport(id) {
  if (!confirm("Delete this received report?")) return;
  await fetch("/api/peer/inbox/" + encodeURIComponent(id), { method: "DELETE" });
  _shareInbox.key = null;  // force the next tick to re-render
  _shareInboxTick();
}

// ── ScoreConnect ─────────────────────────────────────────────

// ── SC III Installer ─────────────────────────────────────────

var _sc3InstallPoll = null;  // polling interval handle

async function installSc3(btn) {
  // Replace the upgrade banner contents with a progress UI
  var card = btn.closest(".card");
  if (!card) return;
  _renderSc3Progress(card, { stage: "starting", percent: 5, message: "Approve the Windows administrator prompt to begin installing ScoreConnect III." });

  // Kick off the install — backend returns immediately
  var result = await apiPost("/api/scoreconnect/install-sc3");
  if (!result || !result.ok) {
    _renderSc3Progress(card, {
      stage: "failed", percent: 0,
      message: "Failed to start install",
      error: (result && (result.error || result.message)) || "Unknown error"
    });
    return;
  }

  // Begin polling for progress every 1.5s
  if (_sc3InstallPoll) clearInterval(_sc3InstallPoll);
  var badPolls = 0;
  _sc3InstallPoll = setInterval(async function() {
    var s = await api("/api/scoreconnect/install-sc3/status");

    // Tolerate a few transient read failures (null response, or an 'unknown'
    // stage from a momentary file read race), then surface a Retry rather than
    // spinning silently forever.
    if (!s || s.stage === "unknown") {
      if (++badPolls >= 4) {
        clearInterval(_sc3InstallPoll); _sc3InstallPoll = null;
        _renderSc3Progress(card, {
          stage: "failed", percent: 0,
          message: "Lost contact with the installer.",
          error: (s && s.error) || "Could not read install status."
        });
      }
      return;
    }
    badPolls = 0;
    _renderSc3Progress(card, s);

    if (s.stage === "complete") {
      clearInterval(_sc3InstallPoll); _sc3InstallPoll = null;
      // Refresh the SC data after a moment so the user sees SC III detected
      setTimeout(function() {
        dataCache.scoreconnect = null;
        if (window.location.hash === "#scoreconnect") renderScoreConnect();
      }, 3000);
    } else if (s.stage === "failed" || s.stale) {
      clearInterval(_sc3InstallPoll); _sc3InstallPoll = null;
    }
  }, 1500);
}

function _renderSc3Progress(card, status) {
  var stage = status.stage || "unknown";
  var pct = Math.max(0, Math.min(100, status.percent || 0));
  var msg = status.message || "";
  var err = status.error || null;
  var stale = status.stale;

  var stageLabel = {
    starting:    "Starting…",
    downloading: "Downloading",
    installing:  "Installing",
    verifying:   "Verifying",
    complete:    "Complete",
    failed:      "Failed",
    idle:        "Idle"
  }[stage] || stage;

  var barColor = stage === "failed" ? "var(--c-accent-red)"
    : stage === "complete" ? "var(--c-accent-green)"
    : "var(--c-accent-blue)";

  var iconName = stage === "complete" ? "check"
    : stage === "failed" ? "x"
    : "refresh";

  card.innerHTML = `
    <div style="display:flex;align-items:flex-start;gap:0.75rem">
      <div style="margin-top:2px;color:${barColor}">${svgIcon(iconName, 18)}</div>
      <div style="flex:1">
        <div class="font-semibold" style="margin-bottom:0.25rem">
          ScoreConnect III Install — ${esc(stageLabel)}${pct ? ' <span class="text-pulse-muted" style="font-weight:normal">(' + pct + '%)</span>' : ''}
        </div>
        <div class="text-pulse-muted" style="font-size:0.8rem;line-height:1.5">${esc(msg)}</div>
        <div style="margin-top:0.6rem;height:8px;background:var(--c-deep-bg);border-radius:4px;overflow:hidden;border:1px solid var(--c-border)">
          <div style="height:100%;width:${pct}%;background:${barColor};transition:width 0.5s ease-out"></div>
        </div>
        ${err ? `<div class="status-fail" style="font-size:0.75rem;margin-top:0.5rem">${esc(err)}</div>` : ""}
        ${stale ? `<div class="text-pulse-muted" style="font-size:0.72rem;margin-top:0.35rem">Install appears stalled. Click Retry to start over.</div>` : ""}
        ${(stage === "failed" || stale) ? `<button class="btn-outline btn-ol-blue" style="margin-top:0.6rem" onclick="installSc3(this)">${svgIcon("refresh", 14)} Retry Install</button>` : ""}
        ${stage === "complete" ? `<div class="status-pass" style="font-size:0.8rem;margin-top:0.5rem">ScoreConnect III is now installed. Refreshing data…</div>` : ""}
      </div>
    </div>
  `;
}

// Format a Daktronics clock digit-run (no colon in the raw) into MM:SS.
// "1225" → "12:25", "0951" → "9:51", "5000" → "50:00". A "." means the
// controller is sending seconds.tenths (sub-minute) — show as-is.
function _fmtClock(d) {
  if (!d) return null;
  if (d.indexOf(".") >= 0) return d;        // SS.T seconds.tenths
  d = d.replace(/\D/g, "");
  if (d.length >= 4) {
    var mm = parseInt(d.substring(0, d.length - 2), 10);
    return mm + ":" + d.substring(d.length - 2);
  }
  if (d.length === 3) return d.charAt(0) + ":" + d.substring(1);
  if (d.length === 2) return "0:" + d;
  return d.length ? d : null;
}

// Highest period number that is plausible for a sport, used to reject a
// mis-read quarter instead of displaying it. 4-period sports allow 5 so a
// single overtime still shows; a second OT (6+) suppresses rather than risk
// passing garbage through. Innings-based and unknown sports get the full
// single-digit range, i.e. effectively no clamp.
function _maxPeriodForSport(sport) {
  var s = (sport || "").toLowerCase();
  if (s.indexOf("football") >= 0 || s.indexOf("basketball") >= 0) return 5;
  if (s.indexOf("hockey") >= 0 || s.indexOf("soccer") >= 0) return 4;
  return 9;
}

// ScoreConnect CG parser. SC III decodes scoreboard controllers into a
// FIXED-WIDTH ASCII layout. Confirmed byte-for-byte against live VPU captures
// (Daktronics Football, SC III 1.3.0.19) with field meanings verified by a
// field tech reading the physical controller:
//
//   "025728  25 38 42  33     3Home    Visitor R:S 00D3098DEBCEEA969B"
//    01234567890123456789012345
//    └┘                                 header  (pos 0-1, "02")
//      └──┘                             clock   (pos 2-5, right-justified)
//          └┘                           field A (pos 8-9)  — not surfaced
//             └┘                        HOME    (pos 11-12)
//                └┘                     VISITOR (pos 14-15)
//                   └┘                  field B (pos 18-19) — not surfaced
//                        │              quarter (pos 25)
//                         Home Visitor  team labels (alphabetic anchor)
//
// Scores are read from FIXED positions (a token split fails because field A
// sits before HOME and the clock gains a leading space under 10:00). Each
// score field is read with a 3-char window so 1-3 digit scores all parse.
//
// The quarter is read from pos 25 for the same reason. It used to be found by
// heuristic — "the last digit of the leading numeric run" — which is correct
// only when the numeric block ENDS at the quarter, as it does on Daktronics.
// Electro-Mech appends at least one more digit after it (PXLS2_21655 Bradwell
// GA, 2026-08-12: reported Q7 while the board was on Q2 and every
// fixed-position field on the same string was correct), so the heuristic
// reached past the quarter into a trailing field.
//
// pos 25 is CONFIRMED for Daktronics and INFERRED for every other vendor —
// which is why an implausible value is suppressed rather than displayed. The
// authoritative per-vendor layout is defined inside the SC III assemblies
// (its CG formatter + ElectromechModel enum); recovering it from there is the
// real fix and is tracked as a separate investigation.
function _parseCG(raw, sport) {
  if (raw.length < 16) return null;

  var header = raw.substring(0, 2);
  if (!/^\d{2}$/.test(header)) return null;   // not the CG header → not this format

  var clock = _fmtClock(raw.substring(2, 6).trim());

  // HOME at pos 11-12, VISITOR at pos 14-15 (each a right-justified field).
  // The 3-char windows include the leading separator and tolerate 1-3 digits.
  var home    = parseInt(raw.substring(10, 13).trim(), 10);
  var visitor = parseInt(raw.substring(13, 16).trim(), 10);
  if (isNaN(home) || isNaN(visitor)) return null;
  if (home > 199 || visitor > 199) return null;  // sanity — not a score line

  // Quarter at FIXED pos 25, immediately after the down/to-go/ball-on block.
  // A value that can't be a real period for the sport is dropped: on a support
  // tool a blank quarter is safe, but a confidently wrong one gets relayed to a
  // school. See _maxPeriodForSport for the per-sport ceiling.
  var qtr = null;
  if (raw.length > 25) {
    var qc = raw.charAt(25);
    if (qc >= "0" && qc <= "9") {
      var q = parseInt(qc, 10);
      if (q >= 1 && q <= 9 && q <= _maxPeriodForSport(sport)) qtr = q;
    }
  }

  // Down / to-go / ball-on: a 5-char packed field at pos 20-24, right before
  // the quarter. Matches the support-doc "11025" block (down 1 = 1 char,
  // to-go 10 = 2 chars, ball-on 25 = 2 chars). Blank (spaces) when the
  // controller has no down & distance set, so we only surface it when present.
  var down = null, togo = null, ballon = null;
  var dtb = raw.substring(20, 25);
  if (/\d/.test(dtb)) {
    var dn = parseInt(dtb.substring(0, 1), 10);
    var tg = parseInt(dtb.substring(1, 3), 10);
    var bo = parseInt(dtb.substring(3, 5), 10);
    if (dn >= 1 && dn <= 4) down = dn;
    if (!isNaN(tg) && tg >= 0 && tg <= 99) togo = tg;
    if (!isNaN(bo) && bo >= 0 && bo <= 99) ballon = bo;
  }

  return {
    clock: clock,
    homeScore: home,        // pos 11-12 — confirmed by field tech
    guestScore: visitor,    // pos 14-15 — UI shows visitor as "guest"
    period: qtr,
    down: down, toGo: togo, ballOn: ballon,
    possession: null,
    _strategy: "cg-fixed"
  };
}

// ── RTD Score Parser ─────────────────────────────────────────
// Multi-strategy parser for scoreboard data from SC III.
// Supports all major vendors: Daktronics, Fairplay, Nevco,
// Electro-Mech, Spectrum/Sportable/Varsity.
//
// Strategy order:
//   1. JSON — if raw data is a JSON string with named fields, parse it.
//      (Sportzcast TCP socket format uses JSON; SC III may pass it through.)
//   2. ScoreConnect CG token format (_parseCG) — the common decoded layout.
//   3. Vendor-specific positional — legacy fixed-width fallback.
//   4. Heuristic — regex pattern matching for clock/score/period.
//
// Returns { clock, homeScore, guestScore, period, down, toGo, ballOn,
//           possession, _strategy } or null if nothing extractable.
function parseRtdScores(rawData, vendor, sport) {
  if (!rawData || typeof rawData !== "string") return null;
  var vLower = (vendor || "").toLowerCase();
  var sLower = (sport  || "").toLowerCase();

  // ── Strategy 1: JSON parse ──────────────────────────────────────────
  // Sportzcast data may arrive as JSON: {"homeScore":"14","awayScore":"7",...}
  var trimmed = rawData.trim();
  if (trimmed.charAt(0) === "{") {
    try {
      var j = JSON.parse(trimmed);
      // Normalize field names (Sportzcast uses multiple conventions)
      var _jv = function() { for (var i=0;i<arguments.length;i++) { var v=j[arguments[i]]; if (v!=null&&v!=="") return v; } return null; };
      var r = {
        clock:      _jv("clock","Clock","time","Time","gameTime","gameClock"),
        homeScore:  _jv("homeScore","HomeScore","scoreHome","home_score","hScore"),
        guestScore: _jv("awayScore","AwayScore","guestScore","GuestScore","scoreAway","away_score","vScore","visitor_score"),
        period:     _jv("period","Period","quarter","Quarter","half","Half","inning","Inning"),
        down:       _jv("down","Down"),
        toGo:       _jv("toGo","ToGo","yardsToGo"),
        ballOn:     _jv("ballOn","BallOn"),
        possession: _jv("possession","Possession","poss"),
        _strategy:  "json"
      };
      // Coerce scores to numbers
      if (r.homeScore  != null) r.homeScore  = parseInt(r.homeScore, 10);
      if (r.guestScore != null) r.guestScore = parseInt(r.guestScore, 10);
      if (r.period     != null && !isNaN(parseInt(r.period,10))) r.period = parseInt(r.period, 10);
      if (r.down       != null) r.down = parseInt(r.down, 10);
      if (r.toGo       != null) r.toGo = parseInt(r.toGo, 10);
      if (r.ballOn     != null) r.ballOn = parseInt(r.ballOn, 10);
      if (r.clock || r.homeScore != null || r.guestScore != null) return r;
    } catch(e) { /* not JSON, continue */ }
  }

  // Capture clock run-state from the status token "R:S"/"S:S" — first char
  // is R (running) or S (stopped). Useful as a "clock live" hint.
  var clockRunning = null;
  var statusMatch = rawData.match(/\s+([A-Za-z]):([A-Za-z])\b/);
  if (statusMatch) clockRunning = (statusMatch[1].toUpperCase() === "R");

  // ── Strategy 2: ScoreConnect CG token format (all vendors) ──────────
  // The common decoded layout ScoreConnect produces. Try this first — it's
  // the format confirmed against real hardware + Daktronics support docs.
  var cg = _parseCG(rawData, sport);
  if (cg && (cg.clock || cg.homeScore != null || cg.guestScore != null)) {
    cg.clockRunning = clockRunning;
    return cg;
  }

  // ── Strategy 3: Vendor-specific positional fallback (legacy) ────────
  // Strip the trailing status token + MAC/checksum, then read fixed offsets.
  var cleaned = rawData
    .replace(/\s+[A-Za-z]:[A-Za-z]\b.*$/, "")   // strip "R:S 00D3..." / "S:S ..."
    .replace(/\s+[0-9A-Fa-f]{12,}\s*$/, "")     // or a bare trailing MAC/hex
    .replace(/\s+$/, "");
  if (cleaned.length < 5) { /* fall through to heuristic */ }
  else {
    // Helpers
    function chars(p, n) {
      if (p + n > cleaned.length) return null;
      var s = cleaned.substring(p, p + n).trim();
      return s.length ? s : null;
    }
    function num(p, n) {
      var s = chars(p, n);
      if (!s) return null;
      var v = parseInt(s, 10);
      return isNaN(v) ? null : v;
    }
    function numFlex(p, n) {
      // Try n chars, then n-1 at same position
      var v = num(p, n);
      if (v !== null) return v;
      return n > 1 ? num(p, n - 1) : null;
    }
    function extractClock(region) {
      var m = region.match(/(\d{1,2}:\d{2})/);
      if (m) return m[1];
      m = region.match(/(\d{1,2}\.\d)/);
      return m ? m[1] : null;
    }

    var r2 = { clock: null, homeScore: null, guestScore: null, period: null,
               down: null, toGo: null, ballOn: null, possession: null,
               clockRunning: clockRunning, _strategy: null };

    // ── Daktronics All Sport CG ───────────────────────────────────────
    // Clock pos 0-4, Guest 5-7, Home 8-10, Period 11, Poss 12, Down 13-14
    if (vLower.includes("daktronics")) {
      r2._strategy = "daktronics";
      r2.clock = extractClock(cleaned.substring(0, 12));
      r2.guestScore = numFlex(5, 3);
      r2.homeScore  = numFlex(8, 3);
      r2.period     = num(11, 1);
      if (sLower.includes("football")) {
        var pChar = chars(12, 1);
        if (pChar === "<" || pChar === ">") r2.possession = pChar;
        r2.down   = numFlex(13, 2);
        r2.ballOn = numFlex(15, 2);
        r2.toGo   = numFlex(17, 2);
      }
    }

    // ── Fairplay (MP-69, MP-80, Proline) ──────────────────────────────
    // BCD-decoded output: clock first, then digit-pair scores.
    // Format: Clock(5) Guest(3) Home(3) Period(1) — similar to Daktronics
    // but score digits are BCD-decoded pairs (Tens+Ones).
    else if (vLower.includes("fairplay") || vLower.includes("fair play") || vLower.includes("fair-play")) {
      r2._strategy = "fairplay";
      r2.clock = extractClock(cleaned.substring(0, 12));
      r2.guestScore = numFlex(5, 3);
      r2.homeScore  = numFlex(8, 3);
      r2.period     = num(11, 1);
    }

    // ── Nevco ─────────────────────────────────────────────────────────
    // BCD-decoded output via NevcoDigit/NevcoShotclockBcd.
    // Decoded layout follows similar positional convention.
    else if (vLower.includes("nevco")) {
      r2._strategy = "nevco";
      r2.clock = extractClock(cleaned.substring(0, 12));
      r2.guestScore = numFlex(5, 3);
      r2.homeScore  = numFlex(8, 3);
      r2.period     = num(11, 1);
    }

    // ── Electro-Mech ──────────────────────────────────────────────────
    // Multiple controller models (ElectromechModel enum).
    // Try common positional layout.
    else if (vLower.includes("electro") && vLower.includes("mech")) {
      r2._strategy = "electromech";
      r2.clock = extractClock(cleaned.substring(0, 12));
      r2.guestScore = numFlex(5, 3);
      r2.homeScore  = numFlex(8, 3);
      r2.period     = num(11, 1);
    }

    // ── Spectrum / Sportable / Varsity ────────────────────────────────
    // Multiple protocol generations (V2E, V2W, Gen2).
    // Try common positional layout.
    else if (vLower.includes("spectrum") || vLower.includes("sportable") || vLower.includes("varsity")) {
      r2._strategy = "spectrum";
      r2.clock = extractClock(cleaned.substring(0, 12));
      r2.guestScore = numFlex(5, 3);
      r2.homeScore  = numFlex(8, 3);
      r2.period     = num(11, 1);
    }

    // ── Unknown vendor — still try positional ─────────────────────────
    else if (cleaned.length >= 10) {
      r2._strategy = "positional-generic";
      r2.clock = extractClock(cleaned.substring(0, 12));
      r2.guestScore = numFlex(5, 3);
      r2.homeScore  = numFlex(8, 3);
      r2.period     = num(11, 1);
    }

    // Did positional parsing find anything?
    if (r2._strategy && (r2.clock || r2.homeScore != null || r2.guestScore != null)) {
      return r2;
    }
  }

  // ── Strategy 3: Heuristic regex extraction ──────────────────────────
  // Last resort — try to pull recognizable patterns from any data string.
  var h = { clock: null, homeScore: null, guestScore: null, period: null,
            down: null, toGo: null, ballOn: null, possession: null, _strategy: "heuristic" };

  // Clock: look for MM:SS or M:SS or SS.T anywhere in the string
  var cm = rawData.match(/\b(\d{1,2}:\d{2})\b/);
  if (cm) h.clock = cm[1];
  else { cm = rawData.match(/\b(\d{1,2}\.\d)\b/); if (cm) h.clock = cm[1]; }

  // Scores: look for two small numbers (0-199) separated by whitespace
  // near the clock, skipping the clock digits themselves.
  var afterClock = h.clock ? rawData.substring(rawData.indexOf(h.clock) + h.clock.length) : rawData;
  var scoreNums = [];
  var numRe = /\b(\d{1,3})\b/g;
  var nm;
  while ((nm = numRe.exec(afterClock)) !== null) {
    var v = parseInt(nm[1], 10);
    if (v <= 199) scoreNums.push(v);
    if (scoreNums.length >= 3) break;
  }
  if (scoreNums.length >= 2) {
    h.guestScore = scoreNums[0];
    h.homeScore  = scoreNums[1];
    if (scoreNums.length >= 3 && scoreNums[2] <= 9) h.period = scoreNums[2];
  }

  if (h.clock || h.homeScore != null || h.guestScore != null) return h;
  return null;
}

function renderScoreConnect() {
  const data = cached("scoreconnect");
  if (!data) { $page().innerHTML = sectionLoading("ScoreConnect"); fetchSection("scoreconnect"); return; }
  // Only fatal when there's nothing to render. A legacy SC I/II box reports the
  // SC III endpoint as unreachable but still returns usable `sc2` data — don't
  // discard it. run_ps transport failures set `message`; the script's own
  // `error` is a string — surface whichever exists rather than the generic
  // "Failed to load data" fallback.
  if (data.error && !data.reachable && !(data.sc2 && data.sc2.reachable)) {
    // Still surface the recorded configuration history — "what was this box
    // configured as before it went down" is exactly when it's most useful.
    $page().innerHTML = errorBox(data.message || (typeof data.error === "string" ? data.error : null))
      + '<div id="sc-config-history-wrap">' + (_scHistCache ? _scConfigHistoryHtml(_scHistCache, null) : "") + "</div>";
    _scLoadConfigHistory(null);
    return;
  }

  const sc2 = data.sc2;  // SC II data (from settings.json on disk)
  const config = data.configuration || {};
  const botStatus = data.botStatus || {};
  const isDetected = data.reachable;  // SC III
  const anySC = isDetected || (sc2 && sc2.reachable);
  const version = data.version;
  const hasData = data.dataStatus && !data.dataStatus.toLowerCase().includes("no scoreboard");
  const dataReceiving = hasData && data.rawData;

  // RTD parsed scores from SC III raw data
  const rtdParsed = dataReceiving ? parseRtdScores(data.rawData, config.vendor, config.sport) : null;

  // Only TRUST the parsed scoreboard for validated vendor/sport combos (or an
  // explicitly-keyed JSON parse). Outside that, show raw data — never guessed
  // scores. comboValidated is vendor/sport-based (static for the session), so
  // the scoreboard hero stays put even when data briefly drops.
  // Parse-driven gate. ScoreConnect III normalises every vendor's protocol
  // into the same CG layout, so the parser is vendor-agnostic — field-tested
  // across the major scoreboard manufacturers, not just Daktronics. Show the
  // scoreboard whenever the parser can actually extract data; fall back to raw
  // only when it genuinely can't (its sanity checks null out unreadable feeds,
  // so we never fabricate scores).
  const showScoreboard = isDetected && rtdParsed != null;
  const rtdShown = showScoreboard ? rtdParsed : null;

  // Legacy ScoreConnect config/teams. The probe routes whichever legacy
  // install is running (SC I or SC II) into `sc2`; hardware/productName
  // distinguish them so we can label the panel correctly.
  const sc2Teams = sc2 && sc2.teamNames || {};
  const sc2HasConfig = sc2 && sc2.reachable && (sc2.vendor || sc2.botNumber || sc2.version);
  const legacyIsSc1 = sc2 && ((sc2.hardware || "").toLowerCase() === "scoreconnect"
    || (sc2.productName || "").indexOf("SC I") !== -1);
  const legacyFull = legacyIsSc1 ? "ScoreConnect I" : "ScoreConnect II";

  // Team name source: SC II settings.json has configured names, use as labels
  const visitorLabel = sc2Teams.visitor || "GUEST";
  const homeLabel = sc2Teams.home || "HOME";

  // Build BOT and ScoreLink cards independently
  const botCard = botStatus.isConnected != null ? `
    <div class="card">
      ${sectionTitle("globe", "Cloud (Bot) Status")}
      <div class="kv-grid">
        ${kvRowHtml("Status", botStatus.isConnected
          ? badge("Connected", "pass")
          : badge("Not connected", "fail"))}
        ${botStatus.scoreConnectId ? kvRowHtml("ScoreConnect ID",
          `${esc(botStatus.scoreConnectId)} <span class="text-pulse-dim ml-1" style="font-size:0.85em;cursor:help" title="ScoreConnect III reports this ID at startup. If the BOT service has reconfigured since, the displayed value can briefly lag.">${svgIcon("info", 12)}</span>`)
          : ""}
        ${kvRow("Bot Server", botStatus.botServerAddress)}
        ${botStatus.lastErrorMessage ? kvRowHtml("Last Error", `<span class="text-pulse-muted">${esc(botStatus.lastErrorMessage)}</span>`) : ""}
      </div>
    </div>` : "";

  const slCard = data.scoreLinkConnected != null && anySC ? `
    <div class="card sc-sl-card mt-4">
      ${sectionTitle("link", "ScoreLink Device")}
      <div id="sc3-scorelink" class="sc-scorelink ${data.scoreLinkConnected ? "sc-scorelink-ok" : "sc-scorelink-err"}">
        <span class="sc-scorelink-dot"></span>
        <span class="font-semibold">${esc(data.scoreLinkStatusLabel || (data.scoreLinkConnected ? "ScoreLink Connected" : "ScoreLink Not Detected"))}</span>
      </div>
    </div>` : "";

  // Page subtitle reflects the single active version (ScoreConnect III takes
  // precedence when present — it's the live data source). We never show both.
  const subtitle = isDetected
    ? "ScoreConnect III — service, configuration, and live data"
    : sc2 && sc2.reachable
    ? legacyFull + " — configuration from device"
    : "ScoreConnect — service not detected";

  $page().innerHTML = `
    ${pageHeader("ScoreConnect", subtitle,
      `${isDetected ? `<button class="btn-outline btn-ol-green" onclick="window.open('${esc(data.baseUrl || "http://localhost:5000")}','_blank','noopener')" title="Opens the local ScoreConnect III web UI in a new tab">
        ${svgIcon("external-link", 14)} Open ScoreConnect III
      </button>` : ""}
      <button class="btn-outline btn-ol-blue" onclick="dataCache.scoreconnect=null;renderScoreConnect()">
        ${svgIcon("refresh", 14)} Refresh
      </button>`
    )}

    <!-- HERO: Live Scoreboard — only for validated vendor/sport combos -->
    ${showScoreboard ? `
    <div class="sc-board sc-board-hero" id="sc3-hero-board">
      <div class="sc-header">
        <div class="sc-team-home" style="min-width:0">
          <div class="sc-team-label" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:18ch;margin:0 auto">${esc(visitorLabel)}</div>
          <div class="sc-score" id="sc3-guest">${rtdShown && rtdShown.guestScore != null ? esc(String(rtdShown.guestScore)) : "—"}</div>
        </div>
        <div class="sc-center">
          <div class="sc-period-label" id="sc3-period">${rtdShown && rtdShown.period ? "Q" + rtdShown.period : "GAME CLOCK"}</div>
          <div class="sc-clock" id="sc3-clock">${rtdShown && rtdShown.clock ? esc(rtdShown.clock) : "--:--"}</div>
          <div class="sc-data-desc" id="sc3-down">${rtdShown ? _sc3DownText(rtdShown) : ""}</div>
          <div id="sc3-live-badge" style="margin-top:0.4rem;font-size:0.62rem;letter-spacing:0.1em;color:${dataReceiving ? "var(--c-board-ok)" : "var(--c-board-bad)"};display:flex;align-items:center;justify-content:center;gap:0.3rem">
            ${_sc3StageBadge(dataReceiving ? "live" : "disconnected", 0)}
          </div>
        </div>
        <div class="sc-team-away" style="min-width:0">
          <div class="sc-team-label" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:18ch;margin:0 auto">${esc(homeLabel)}</div>
          <div class="sc-score" id="sc3-home">${rtdShown && rtdShown.homeScore != null ? esc(String(rtdShown.homeScore)) : "—"}</div>
        </div>
      </div>
    </div>
    ` : isDetected ? `
    <!-- SC III detected but vendor/sport not yet validated — show status, NOT guessed scores -->
    <div class="sc-board sc-board-hero" id="sc3-hero-board">
      <div class="sc-header">
        <div class="sc-team-home">
          <div class="sc-team-label">Vendor</div>
          <div class="sc-team-name">${esc(config.vendor || "—")}</div>
        </div>
        <div class="sc-center">
          <div class="sc-data-status"><span class="sc-data-label">${dataReceiving ? "Receiving Data" : "No Data"}</span></div>
          <div id="sc3-live-badge" style="margin-top:0.4rem;font-size:0.62rem;letter-spacing:0.1em;color:${dataReceiving ? "var(--c-board-ok)" : "var(--c-board-bad)"};display:flex;align-items:center;justify-content:center;gap:0.3rem">
            ${_sc3StageBadge(dataReceiving ? "live" : "disconnected", 0)}
          </div>
          ${dataReceiving
            ? `<div class="sc-data-desc" style="margin-top:0.6rem;max-width:360px;line-height:1.4">Receiving data, but Pulse couldn't parse this feed${config.vendor ? " (" + esc(config.vendor) + ")" : ""} — raw data shown below.</div>`
            : `<div class="sc-data-desc" style="margin-top:0.6rem;max-width:360px;line-height:1.4">Waiting for scoreboard data…</div>`}
        </div>
        <div class="sc-team-away">
          <div class="sc-team-label">Sport</div>
          <div class="sc-team-name">${esc(config.sport || "—")}</div>
        </div>
      </div>
    </div>
    ` : !(sc2 && sc2.reachable) ? `<div class="sc-board sc-board-hero sc-board-empty">${data.error ? esc(typeof data.error === "string" ? data.error : "No ScoreConnect service detected") : "No ScoreConnect service detected"}</div>` : ""}

    <!-- ScoreLink USB device — directly below the scoreboard hero -->
    ${slCard}

    <!-- ScoreConnect → SC III Upgrade Prompt -->
    ${sc2 && sc2.reachable && !isDetected ? `
    <div class="card mt-4" style="border:1px solid var(--c-accent-blue)">
      <div style="display:flex;align-items:flex-start;gap:0.75rem">
        <div style="margin-top:2px;color:var(--c-accent-blue)">${svgIcon("refresh", 18)}</div>
        <div style="flex:1">
          <div class="font-semibold" style="margin-bottom:0.25rem">Upgrade to ScoreConnect III</div>
          <div class="text-pulse-muted" style="font-size:0.8rem;line-height:1.5">
            ScoreConnect III is the preferred version. It provides live scoreboard data, parsed
            scores, and live status — with no interference to the data stream.
          </div>
          <div style="margin-top:0.75rem">
            <button class="btn-outline btn-ol-blue" id="btn-install-sc3" onclick="installSc3(this)">
              ${svgIcon("download", 14)} Install ScoreConnect III
            </button>
          </div>
          <div class="text-pulse-muted" style="font-size:0.72rem;margin-top:0.5rem">
            Downloads the official installer and runs it in the background. A Windows
            administrator prompt appears on the VPU desktop — approve it to continue.
          </div>
        </div>
      </div>
    </div>
    ` : ""}

    <!-- Active legacy version (ScoreConnect I/II) — only when ScoreConnect III is NOT present -->
    ${!isDetected && sc2HasConfig ? `
    <div class="card mt-4">
      ${sectionTitle("server", legacyFull)}
      <div class="kv-grid">
        ${kvRowHtml("Status", sc2.outOfDate
          ? _scDot(true, "var(--c-accent-amber)") + '<span class="status-warn">Running — software out of date</span>'
          : _scDot(true) + '<span class="status-pass">Running</span>')}
        ${kvRow("Version", sc2.version)}
        ${kvRow("Hardware", (sc2.hardware || "").replace("ScoreConnectII", "ScoreConnect II"))}
        ${kvRow("UID", sc2.uid)}
        ${sc2.botNumber ? kvRow("Bot Number", sc2.botNumber) : ""}
        ${sc2.vendor ? (sc2.vendorIsCode
          ? kvRowHtml("Vendor", `${esc(String(sc2.vendor))} <span class="text-pulse-muted" style="font-size:0.75rem">(code)</span>`)
          : kvRow("Vendor", sc2.vendor)) : ""}
        ${sc2.sport ? kvRow("Sport Code", sc2.sport) : ""}
        ${sc2.license ? kvRow("License Expires", sc2.license) : ""}
        ${sc2.scoreLink ? kvRow("ScoreLink", sc2.scoreLink.description) : ""}
        ${sc2.scoreLink && sc2.scoreLink.serial ? kvRow("ScoreLink Serial", sc2.scoreLink.serial) : ""}
        ${sc2Teams.visitor ? kvRow("Visitor Name", sc2Teams.visitor) : ""}
        ${sc2Teams.home ? kvRow("Home Name", sc2Teams.home) : ""}
      </div>
      ${sc2.networkIfaces && sc2.networkIfaces.length ? `
      <div style="margin-top:0.75rem;padding-top:0.75rem;border-top:1px solid var(--c-border)">
        <div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.05em;color:var(--c-muted);margin-bottom:0.5rem">Network Interfaces</div>
        <div class="kv-grid">
          ${sc2.networkIfaces.map(n => kvRow(n.name, n.address)).join("")}
        </div>
      </div>` : ""}
    </div>` : ""}

    <!-- ScoreConnect III — status, configuration, and live data (all grouped) -->
    ${isDetected ? `
    <div class="card mt-4">
      ${sectionTitle("server", "ScoreConnect III")}
      <div class="kv-grid">
        ${kvRowHtml("Status", `<span id="sc3-svc-status">${_sc3SvcStatusHtml("live")}</span>`)}
        ${kvRowHtml("Scoreboard Data", `<span id="sc3-data-status">${_sc3DataStatusHtml(dataReceiving ? "live" : "disconnected", 0, data.dataStatus)}</span>`)}
        ${kvRow("Version", version)}
        ${kvRow("Base URL", data.baseUrl)}
        ${config.vendor ? kvRow("Vendor", config.vendor) : ""}
        ${config.sport ? kvRow("Sport", config.sport) : ""}
        ${config.vendorConfigurationName ? kvRow("Connection Type", config.vendorConfigurationName) : ""}
        ${config.device ? kvRow("Device", config.device) : ""}
        ${config.serialPort ? kvRow("Serial Port", config.serialPort) : ""}
        ${config.firmware ? kvRow("Firmware", config.firmware) : ""}
        ${config.eventType ? kvRow("Event Type", config.eventType) : ""}
        ${kvRow("Network", data.networkStatus)}
        ${kvRowHtml("Local Stream", data.hasLocalStream != null
          ? (data.hasLocalStream ? '<span class="status-pass">Detected</span>' : '<span class="status-fail">Not detected</span>')
          : '—')}
      </div>
      ${data.rawData ? `
      <div class="sc-raw-data" style="margin-top:0.85rem">
        <div class="sc-raw-label">RAW SCOREBOARD DATA (ScoreConnect III)</div>
        <div class="sc-raw-value" id="sc3-raw-value">${esc(data.rawData)}</div>
      </div>` : ""}
    </div>` : ""}

    <!-- Cloud BOT (ScoreLink panel moved up under the hero) -->
    ${botCard ? `<div class="mt-4">${botCard}</div>` : ""}

    <!-- Previous scoreboard configurations recorded on this VPU -->
    <div id="sc-config-history-wrap">${_scHistCache ? _scConfigHistoryHtml(_scHistCache, data) : ""}</div>
  `;
  _scLoadConfigHistory(data);

  // Start live polling whenever SC III is detected — even if not currently
  // receiving data, so the hero updates the moment the feed starts. Safe:
  // stateless REST, no SC II contact, no WMI.
  if (isDetected) {
    _sc3StartLivePoll(config.vendor, config.sport, showScoreboard);
  } else {
    _sc3StopLivePoll();
  }
}

// ── SC III Live Score Polling ────────────────────────────────
// SC III is a stateless REST API — polling get-status repeatedly is safe
// and does NOT interfere with the data stream (Pixellot's agent reads it
// the same way). We poll a lightweight endpoint every 1.5s and update the
// scoreboard values in place, without re-rendering the whole page.

var _sc3LivePoll = null;
var _sc3PollGen = 0;   // bumped on every stop/start so an in-flight tick that
                       // resolves after being superseded can detect it and bail

function _sc3DownText(p) {
  if (!p || !p.down) return "";
  var ord = { 1: "1ST", 2: "2ND", 3: "3RD", 4: "4TH" }[p.down] || (p.down + "");
  var t = ord;
  if (p.toGo != null) t += " & " + (p.toGo === 0 ? "GOAL" : p.toGo);
  if (p.ballOn != null) t += " ON " + p.ballOn;
  return t;
}

// Status dot: green + flashing when active, grey + static when off. Pass an
// explicit `color` (e.g. amber) to override — used for the out-of-date warning
// so the dot color matches the message instead of staying green.
function _scDot(on, color) {
  var c = color || (on ? "var(--c-accent-green)" : "var(--c-dim)");
  var anim = on ? "animation:pulse-live 1.4s ease-in-out infinite;" : "";
  return '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
    + 'background:' + c + ';' + anim + 'margin-right:7px;vertical-align:middle"></span>';
}

// ScoreConnect III "Status" row cell. The service is Running unless the live
// poll finds it unreachable (offline stage) — then it must say so, instead of
// staying a contradictory green "Running".
function _sc3SvcStatusHtml(stage) {
  return stage === "offline"
    ? _scDot(false) + '<span class="status-fail">Not responding</span>'
    : _scDot(true) + '<span class="status-pass">Running</span>';
}

// Hero badge per data stage. Mirrors SC III's own behaviour.
//   live         — data flowing
//   stale        — frozen briefly; show last data + disconnect countdown
//   disconnected — frozen past the window / SC III reports no data
//   offline      — SC III service itself not responding
function _sc3StageBadge(stage, secs) {
  // Board tokens, not --c-accent-*: this badge sits on the fixed-dark stadium
  // board in BOTH themes, so a light-theme accent here renders dark-on-black
  // (the old --c-accent-green was 3.7:1 in light mode).
  var map = {
    live:         { c: "var(--c-board-ok)",     flash: true,  txt: "LIVE" },
    stale:        { c: "var(--c-board-accent)", flash: true,  txt: "STALE · " + secs + "s" },
    disconnected: { c: "var(--c-board-bad)",    flash: false, txt: "NO SIGNAL" },
    offline:      { c: "var(--c-board-muted)",  flash: false, txt: "ScoreConnect III Offline" }
  };
  var s = map[stage] || map.offline;
  var anim = s.flash ? "animation:pulse-live 1.4s ease-in-out infinite;" : "";
  return '<span style="width:6px;height:6px;border-radius:50%;background:' + s.c + ';'
    + 'display:inline-block;' + anim + '"></span>' + s.txt;
}
// Colour for #sc3-live-badge, which lives on the dark board — board tokens for
// the same reason as _sc3StageBadge above.
var _SC3_STAGE_COLOR = {
  live: "var(--c-board-ok)", stale: "var(--c-board-accent)",
  disconnected: "var(--c-board-bad)", offline: "var(--c-board-muted)"
};

// Status-card "Scoreboard Data" cell markup per stage.
function _sc3DataStatusHtml(stage, secs, statusText) {
  if (stage === "live") {
    return _scDot(true) + '<span class="status-pass">' + esc(statusText || "Data is present and in the correct format") + '</span>';
  }
  if (stage === "stale") {
    return '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--c-accent-amber);animation:pulse-live 1.4s ease-in-out infinite;margin-right:7px;vertical-align:middle"></span>'
      + '<span style="color:var(--c-accent-amber)">Data stale — no new packets (disconnecting in ' + secs + 's)</span>';
  }
  if (stage === "offline") {
    return _scDot(false) + '<span class="status-fail">ScoreConnect III not responding</span>';
  }
  return _scDot(false) + '<span class="status-fail">No scoreboard data is being received</span>';
}

// Stale-data tracking. The per-packet checksum in the raw string changes
// while the controller (serial or USB) is transmitting, and FREEZES the
// moment it drops. We track when the raw data last changed and derive the
// stage from how long it's been frozen — mirroring SC III, which holds the
// last packet for ~60s before reporting "no scoreboard data".
var _SC3_POLL_MS = 300;
var _SC3_STALE_GRACE_MS = 3000;    // brief no-change tolerance before "stale"
var _SC3_DISCONNECT_MS = 60000;    // frozen this long → disconnected
var _sc3LastRaw = null;
var _sc3LastChangeMs = 0;

// Compute the current data stage from a /live response.
function _sc3ComputeStage(live) {
  var now = Date.now();
  if (!live || !live.reachable) return { stage: "offline", secs: 0 };
  // SC III's own verdict is authoritative for "no data".
  var scStatus = (live.dataStatus || "").toLowerCase();
  if (!live.rawData || scStatus.indexOf("no scoreboard") !== -1) {
    return { stage: "disconnected", secs: 0 };
  }
  // Track raw-data changes to measure staleness.
  if (live.rawData !== _sc3LastRaw) {
    _sc3LastRaw = live.rawData;
    _sc3LastChangeMs = now;
  }
  var frozenMs = now - _sc3LastChangeMs;
  if (frozenMs >= _SC3_DISCONNECT_MS) return { stage: "disconnected", secs: 0 };
  if (frozenMs >= _SC3_STALE_GRACE_MS) {
    return { stage: "stale", secs: Math.max(0, Math.ceil((_SC3_DISCONNECT_MS - frozenMs) / 1000)) };
  }
  return { stage: "live", secs: 0 };
}

function _sc3StopLivePoll() {
  _sc3PollGen++;   // invalidate any in-flight tick from a prior run
  if (_sc3LivePoll) { clearTimeout(_sc3LivePoll); _sc3LivePoll = null; }
  _sc3StopUsbPoll();
}

// ── ScoreLink USB monitor ─────────────────────────────────────
// A scoreboard's ScoreConnect device (ScoreLink) plugs in over USB. If it's
// unplugged, the data drop looks identical to the controller being turned
// off — so the staleness handler above already flags the data loss. This
// poll additionally pinpoints the CAUSE by watching the USB port (a light
// WMI check, every 5s) and updating the ScoreLink panel live.
var _sc3UsbPoll = null;
var _SC3_USB_POLL_MS = 5000;

function _sc3StopUsbPoll() {
  if (_sc3UsbPoll) { clearTimeout(_sc3UsbPoll); _sc3UsbPoll = null; }
}

function _sc3StartUsbPoll() {
  _sc3StopUsbPoll();
  async function tick() {
    if (currentPage !== "scoreconnect" || !document.getElementById("sc3-scorelink")) {
      _sc3StopUsbPoll();
      return;
    }
    var sl = await api("/api/scoreconnect/scorelink");
    var el = document.getElementById("sc3-scorelink");
    if (el && sl && sl.connected != null) {
      el.className = "sc-scorelink " + (sl.connected ? "sc-scorelink-ok" : "sc-scorelink-err");
      var label = sl.statusLabel || (sl.connected ? "ScoreLink Connected" : "ScoreLink device disconnected");
      el.innerHTML = '<span class="sc-scorelink-dot"></span><span class="font-semibold">' + esc(label) + '</span>';
    }
    _sc3UsbPoll = setTimeout(tick, _SC3_USB_POLL_MS);
  }
  // First check after one interval (initial state already rendered server-side).
  _sc3UsbPoll = setTimeout(tick, _SC3_USB_POLL_MS);
}

function _sc3StartLivePoll(vendor, sport, showScoreboard) {
  _sc3StopLivePoll();
  var myGen = _sc3PollGen;   // this run's token; if it changes, we've been superseded
  // Reset staleness tracking for a fresh session.
  _sc3LastRaw = null;
  _sc3LastChangeMs = Date.now();
  _sc3StartUsbPoll();

  // Both hero variants (scoreboard + unvalidated status) carry #sc3-hero-board
  // and #sc3-live-badge, so the poll runs for either — only the scoreboard
  // variant has the score elements to update.
  async function tick() {
    // Self-terminate if the user navigated away from the page.
    if (currentPage !== "scoreconnect" || !document.getElementById("sc3-hero-board")) {
      _sc3StopLivePoll();
      return;
    }

    var live = await api("/api/scoreconnect/live");

    // Bail if a newer poll superseded this one during the await (generation
    // token), or the user navigated away.
    if (myGen !== _sc3PollGen) return;
    if (currentPage !== "scoreconnect" || !document.getElementById("sc3-hero-board")) {
      _sc3StopLivePoll();
      return;
    }

    var st = _sc3ComputeStage(live);

    // Always refresh the raw-data readout (shown for any SC III vendor).
    if (live && live.rawData) {
      var rawEl = document.getElementById("sc3-raw-value");
      if (rawEl) rawEl.textContent = live.rawData;
    }

    // If the feed has started parsing but we're on the status hero (scores
    // weren't shown), promote to the scoreboard hero with a re-render. Fires
    // only on that one-way transition, so no flapping/loop.
    if (!showScoreboard && live && live.rawData && parseRtdScores(live.rawData, vendor, sport)) {
      var cd = cached("scoreconnect");
      if (cd) { cd.rawData = live.rawData; cd.dataStatus = live.dataStatus; }
      renderScoreConnect();
      return;
    }

    // Update parsed scores ONLY for validated vendor/sport combos. Outside
    // those we never write fabricated numbers — the raw data above is the
    // source of truth. While live, refresh from the new packet.
    if (showScoreboard && st.stage === "live" && live.rawData) {
      var p = parseRtdScores(live.rawData, vendor, sport);
      if (p) {
        _sc3SetText("sc3-clock", p.clock || "--:--");
        _sc3SetText("sc3-period", p.period ? "Q" + p.period : "GAME CLOCK");
        if (p.guestScore != null) _sc3SetText("sc3-guest", String(p.guestScore));
        if (p.homeScore != null)  _sc3SetText("sc3-home", String(p.homeScore));
        _sc3SetText("sc3-down", _sc3DownText(p));
      }
    }
    // In stale/disconnected/offline we keep the LAST known scores on screen
    // (mirroring SC III holding the last packet) — only the status changes.

    // Hero badge.
    var badge = document.getElementById("sc3-live-badge");
    if (badge) {
      badge.style.color = _SC3_STAGE_COLOR[st.stage] || "var(--c-board-muted)";
      badge.innerHTML = _sc3StageBadge(st.stage, st.secs);
    }

    // When the data is dead, dim ONLY the score cluster (scores/clock/period/
    // down) — never the badge, so the failure indicator stays fully legible.
    var dead = (st.stage === "disconnected" || st.stage === "offline");
    ["sc3-guest", "sc3-home", "sc3-clock", "sc3-period", "sc3-down"].forEach(function(id) {
      var el = document.getElementById(id);
      if (el) el.style.opacity = dead ? "0.4" : "";
    });

    // "Scoreboard Data" cell + the service "Status" row.
    var dataCell = document.getElementById("sc3-data-status");
    if (dataCell) dataCell.innerHTML = _sc3DataStatusHtml(st.stage, st.secs, live && live.dataStatus);
    var svcCell = document.getElementById("sc3-svc-status");
    if (svcCell) svcCell.innerHTML = _sc3SvcStatusHtml(st.stage);

    // Schedule the next poll only after this one completes.
    _sc3LivePoll = setTimeout(tick, _SC3_POLL_MS);
  }

  tick();
}

function _sc3SetText(id, text) {
  var el = document.getElementById(id);
  if (el && el.textContent !== text) el.textContent = text;
}

// ── ScoreConnect configuration history ───────────────────────
// Read-only log of previous scoreboard configurations recorded on this VPU.
// The server appends an entry whenever the config fingerprint changes while
// scoreboard data is confirmed flowing ("Data is present…"), so entries are
// known-working states — not mid-reconfigure noise. Reuses the fault-isolator
// history styles (fi-hist-*), which are generic collapsible history rows.

var _scHistCache = null;  // persisted entries (null = not yet fetched)

// Display label per snapshot field, in the SAME order as the server's
// fingerprint (_SC_CONFIG_FP_FIELDS in main.py) so change detection and the
// "Current" match track exactly what opens a new entry server-side.
var _SC_HIST_FIELDS = [
  ["vendor", "Vendor"], ["sport", "Sport"], ["configName", "Connection Type"],
  ["device", "Device"], ["serialPort", "Serial Port"], ["eventType", "Event Type"],
  ["botNumber", "Bot #"], ["scoreLinkModel", "ScoreLink"],
];

function _scLoadConfigHistory(current) {
  api("/api/scoreconnect/history").then(function(d) {
    _scHistCache = (d && d.entries) || [];
    var w = document.getElementById("sc-config-history-wrap");
    if (w && currentPage === "scoreconnect") w.innerHTML = _scConfigHistoryHtml(_scHistCache, current);
  }).catch(function() {});
}

function _scConfigHistoryHtml(entries, current) {
  if (!entries || !entries.length) return "";
  function fv(v) { return v == null ? "" : String(v); }
  var cfg = current && current.configuration || {};
  var bot = current && current.botStatus || {};
  var liveFp = [cfg.vendor, cfg.sport, cfg.vendorConfigurationName, cfg.device,
    cfg.serialPort, cfg.eventType, bot.scoreConnectId,
    current && current.scoreLinkModel].map(fv).join("|");

  var items = entries.slice(0, 15).map(function(e, i) {
    var prev = entries[i + 1];  // next-older entry
    var changed = prev ? _SC_HIST_FIELDS.filter(function(f) { return fv(e[f[0]]) !== fv(prev[f[0]]); })
      .map(function(f) { return f[1]; }) : [];
    var fp = _SC_HIST_FIELDS.map(function(f) { return fv(e[f[0]]); }).join("|");
    var isCurrent = i === 0 && !!current && fp === liveFp;

    var first = e.firstSeen ? new Date(e.firstSeen) : null;
    var last = e.lastSeen ? new Date(e.lastSeen) : null;
    var when = first ? first.toLocaleDateString() : "";
    if (first && last && last.toLocaleDateString() !== first.toLocaleDateString()) {
      when += " – " + last.toLocaleDateString();
    }
    var title = [e.vendor, e.sport].filter(Boolean).join(" · ") || "Configuration";

    return '<details class="fi-hist-run">' +
      '<summary class="fi-hist-summary">' +
        '<span class="fi-hist-when">' + esc(when) + "</span>" +
        '<span class="fi-hist-where">' + esc(title) +
          (e.botNumber ? ' <span class="font-mono text-pulse-muted">BOT ' + esc(fv(e.botNumber)) + "</span>" : "") +
        "</span>" +
        (isCurrent ? badge("Current", "pass")
          : changed.length ? '<span class="fi-hist-chip fi-hist-chip-amber">Changed: ' + esc(changed.join(", ")) + "</span>"
          : '<span class="fi-hist-chip fi-hist-chip-muted">Earliest recorded</span>') +
      "</summary>" +
      '<div class="fi-hist-body"><div class="kv-grid">' +
        (first ? kvRow("First seen", first.toLocaleString()) : "") +
        (last ? kvRow("Last seen", last.toLocaleString()) : "") +
        _SC_HIST_FIELDS.map(function(f) { return e[f[0]] != null && e[f[0]] !== "" ? kvRow(f[1], e[f[0]]) : ""; }).join("") +
        (e.scoreLinkPort ? kvRow("ScoreLink Port", e.scoreLinkPort) : "") +
        (e.version ? kvRow("Version", e.version) : "") +
        (e.firmware ? kvRow("Firmware", e.firmware) : "") +
      "</div></div>" +
    "</details>";
  }).join("");

  return '<div class="card mt-4">' +
    sectionTitle("clock", "Previous Configurations") +
    '<div class="text-pulse-muted" style="font-size:0.75rem;margin:-0.25rem 0 0.6rem;line-height:1.5">' +
      "Recorded automatically each time the scoreboard configuration changes while data is confirmed flowing. " +
      "Bot numbers are best-effort — ScoreConnect III can report a stale number until its service restarts." +
    "</div>" + items + "</div>";
}

// ── Camera Fault Isolator ────────────────────────────────────
//
// 4-phase swap test — process of elimination:
//   Phase 1 (Baseline): measure suspect port speed.
//   Phase 2 (NIC Port): move same cable+camera to test port. Fault follows?
//     Pass (1 Gbps on test) → NIC Port fault.  Fail (still degraded) → Phase 3.
//   Phase 3 (Cable): swap cable for known-good on test port. Fault follows?
//     Pass → Cable fault.  Fail → Phase 4.
//   Phase 4 (Camera): swap camera for known-good on test port. Fault follows?
//     Pass → Camera fault.  Fail → NIC Hardware fault.
//     "No spare CHU" → infer camera fault from Phase 2+3 eliminations.
//
// Ported from FaultIsolatorViewModel.cs (v0.8.21-beta).

var _fi = null;
var _fiHistoryCache = null;  // persisted prior runs (null = not yet fetched)
// How long each link check waits for the speed to reach the threshold before
// giving up. A healthy link returns the instant a good sample lands, so this
// is just the max wait on a failing check. Kept short so the tech isn't left
// staring at a countdown. The on-screen timer is decoupled from the network
// poll (see pollPeakSpeed) so it ticks smoothly instead of jumping per poll.
var _FI_CHECK_WINDOW = 10;   // seconds

// Fetch persisted fault-isolator runs and render them into the history panel.
function _fiLoadHistory() {
  api("/api/fault-isolator/history").then(function(d) {
    _fiHistoryCache = (d && d.runs) || [];
    var w = document.getElementById("fi-history-wrap");
    if (w && currentPage === "fault-isolator") w.innerHTML = _fiHistoryHtml(_fiHistoryCache);
  }).catch(function() {});
}

// Map a conclusion code to a colored verdict chip.
function _fiVerdictChip(conclusion, title) {
  var label = (title || conclusion || "").replace(/^CONCLUSION — /i, "") || "Result";
  var cls = "fi-hist-chip-muted";
  if (conclusion === "Cable") cls = "fi-hist-chip-amber";
  else if (conclusion === "Camera" || conclusion === "LikelyCamera") cls = "fi-hist-chip-amber";
  else if (conclusion === "NicPort" || conclusion === "NicHardware") cls = "fi-hist-chip-red";
  return '<span class="fi-hist-chip ' + cls + '">' + esc(label) + '</span>';
}

// "Previous tests on this VPU" — collapsible per-run summary + phase detail.
function _fiHistoryHtml(runs) {
  if (!runs || !runs.length) return "";
  var items = runs.slice(0, 15).map(function(r) {
    var when = r.ts ? new Date(r.ts).toLocaleString() : "";
    var camTxt = r.camera && (r.camera.label || r.camera.ip)
      ? (esc(r.camera.label || "") + (r.camera.ip ? ' <span class="font-mono text-pulse-muted">' + esc(r.camera.ip) + "</span>" : ""))
      : "";
    var phaseRows = (r.history || []).map(function(h) {
      var sc = h.severity === "Pass" ? "status-pass" : h.severity === "Fail" ? "status-fail" : "status-info";
      return "<tr><td><strong>" + esc(h.phase || "") + "</strong></td>" +
        '<td class="font-mono">' + esc(h.speed || "") + "</td>" +
        '<td><span class="' + sc + '">' + esc(h.severity || "") + "</span></td>" +
        '<td class="text-pulse-muted" style="font-size:0.78rem">' + esc(h.verdict || "") + "</td></tr>";
    }).join("");
    return '<details class="fi-hist-run">' +
      '<summary class="fi-hist-summary">' +
        '<span class="fi-hist-when">' + esc(when) + "</span>" +
        '<span class="fi-hist-where">' + esc(r.suspectPort || "") + (camTxt ? " · " + camTxt : "") + "</span>" +
        _fiVerdictChip(r.conclusion, r.title) +
      "</summary>" +
      '<div class="fi-hist-body">' +
        (r.recommendation ? '<div class="fi-hist-rec">' + esc(r.recommendation) + "</div>" : "") +
        (phaseRows ? '<table class="data-table fi-hist-table"><thead><tr><th>Phase</th><th>Speed</th><th>Result</th><th>Verdict</th></tr></thead><tbody>' + phaseRows + "</tbody></table>" : "") +
      "</div>" +
    "</details>";
  }).join("");
  return '<div class="card" style="margin-top:1.25rem">' +
    sectionTitle("clock", "Previous tests on this VPU") + items + "</div>";
}

function _fiReset() {
  // Abort any in-flight poll from a previous run before replacing state.
  if (_fi) _fi._aborted = true;
  _fi = {
    phase: 0,           // 0=PickPort 1=AwaitingNicPortTest 2=AwaitingCableTest 3=AwaitingCameraTest 4=Concluded
    conclusion: "",     // NicPort | Cable | Camera | NicHardware | LikelyCamera
    suspectIdx: -1,
    testIdx: -1,
    expectedSpeedMbps: null,  // captured from suspect port at baseline time
    suspectCameraMacs: [],    // captured at end of baseline; used to verify the physical swap in phase 1
    history: [],        // [{ts,phase,config,speed,verdict,severity}]
    resultHeadline: "",
    resultDetail: "",
    resultSeverity: "", // pass | info | fail
    phaseTitle: "SELECT A PORT TO BEGIN",
    phaseInstruction: "Select the NIC port with a degraded or missing link, then Start Baseline.",
    actionLabel: "Start Baseline",
    checking: false,
    _aborted: false,
  };
}

function renderFaultIsolator() {
  var cams = cached("cameras");
  if (!cams) {
    $page().innerHTML = sectionLoading("Camera Connection Troubleshooting");
    api("/api/cameras").then(function(d) { dataCache.cameras = d; renderFaultIsolator(); });
    return;
  }
  if (cams.error) { $page().innerHTML = errorBox(cams.message); return; }

  var ports = cams.ports || [];
  if (!_fi) _fiReset();

  // ── helpers ──────────────────────────────────────────────────

  function portLabel(idx) {
    return "Port " + (idx + 1);
  }

  function formatSpeed(mbps) {
    if (mbps === null || mbps === undefined) return "—";
    if (mbps >= 1000) {
      var g = mbps / 1000;
      return (g === Math.floor(g) ? g : g.toFixed(1)) + " Gbps";
    }
    if (mbps > 0) return mbps + " Mbps";
    return "No link";
  }

  function stepDots() {
    var labels = ["Baseline", "NIC Port", "Cable", "Camera", "Verdict"];
    var html = '<div class="fi-stepper">';
    for (var i = 0; i < 5; i++) {
      var cls = "fi-step-dot";
      var lblCls = "fi-step-label";
      if (_fi.phase > i) { cls += " fi-dot-done"; lblCls += " fi-step-label-done"; }
      else if (_fi.phase === i) { cls += " fi-dot-active"; lblCls += " fi-step-label-active"; }
      html += '<div class="fi-step-cell">' +
        '<div class="' + cls + '">' + (i + 1) + "</div>" +
        '<div class="' + lblCls + '">' + labels[i] + "</div>" +
      '</div>';
      if (i < 4) html += '<div class="fi-step-line' + (_fi.phase > i ? " fi-line-done" : "") + '"></div>';
    }
    return html + "</div>";
  }

  function resultRow() {
    if (!_fi.resultHeadline) return "";
    var sev = _fi.resultSeverity || "info";
    var chip = sev === "pass" ? "PASS" : sev === "fail" ? "FAIL" : "INFO";
    return '<div class="fi-result-row fi-result-' + sev + '">' +
      '<span class="fi-result-chip">' + chip + "</span>" +
      "<div>" +
        '<div class="fi-result-note">' + esc(_fi.resultHeadline) + "</div>" +
        (_fi.resultDetail ? '<div class="fi-result-detail">' + esc(_fi.resultDetail) + "</div>" : "") +
      "</div>" +
      "</div>";
  }

  function historyTable() {
    if (!_fi.history.length) return "";
    var rows = _fi.history.map(function(h) {
      var sc = h.severity === "Pass" ? "status-pass" : h.severity === "Fail" ? "status-fail" : "status-info";
      return "<tr>" +
        '<td class="font-mono" style="font-size:0.7rem;color:var(--c-dim)">' + esc(h.ts) + "</td>" +
        '<td><span class="' + sc + '">' + esc(h.severity) + "</span></td>" +
        "<td><strong>" + esc(h.phase) + "</strong></td>" +
        '<td class="text-pulse-muted" style="font-size:0.78rem">' + esc(h.config) + "</td>" +
        '<td class="font-mono" style="font-size:0.78rem">' + esc(h.speed) + "</td>" +
        '<td class="text-pulse-muted" style="font-size:0.78rem">' + esc(h.verdict) + "</td>" +
        "</tr>";
    }).join("");
    return '<div class="mt-4">' +
      '<div class="text-sm font-semibold mb-2 text-pulse-muted">Phase history (newest first)</div>' +
      '<div style="overflow-x:auto"><table class="data-table">' +
      "<thead><tr><th>Time</th><th>Result</th><th>Phase</th><th>Configuration</th><th>Speed</th><th>Verdict</th></tr></thead>" +
      "<tbody>" + rows + "</tbody></table></div></div>";
  }

  // ── port option builder (shared by Phase 0 and Phase 1 dropdowns) ──
  function portOption(p, i, excludeIdx) {
    if (i === excludeIdx) return "";
    // Camera label (Main Camera 1, OCR, etc.) — same one shown on the port tile.
    var camLbl = p.cameraLabel ? " (" + p.cameraLabel + ")" : "";
    var down = !p.isUp || !(p.linkSpeedMbps > 0);
    var spd;
    if (down) spd = " — No link";
    // Trust the backend isDegraded flag — it knows the expected speed for
    // each camera model. A 100 Mbps OCR isn't degraded; an unknown 100 Mbps
    // camera might be.
    else if (p.isDegraded) spd = " — " + formatSpeed(p.linkSpeedMbps) + " (FAULT)";
    else if (p.isOcr) spd = " — " + formatSpeed(p.linkSpeedMbps || 100) + " (expected)";
    else spd = " — " + formatSpeed(p.linkSpeedMbps);
    // Every non-suspect port is selectable — including an empty "No link" port,
    // which is the natural swap target (you light it up by moving the camera
    // onto it). A port's current speed reflects its current occupant, not its
    // capacity, so it must not gate selection.
    return '<option value="' + i + '">' + esc("Port " + (i + 1) + camLbl + spd) + "</option>";
  }

  // ── phase HTML ───────────────────────────────────────────────
  var inner = "";

  if (_fi.phase === 0) {
    var allOpts = ports.map(function(p, i) { return portOption(p, i, -1); }).join("");
    var def = '<option value="-1">— Select —</option>';
    inner = '<div class="fi-phase-card">' +
      '<div class="fi-phase-title">' + esc(_fi.phaseTitle) + "</div>" +
      '<div class="fi-phase-instr">' + esc(_fi.phaseInstruction) + "</div>" +
      resultRow() +
      '<div style="margin:16px 0;max-width:480px">' +
        '<div class="text-xs text-pulse-muted mb-1">Suspect port (has the fault)</div>' +
        '<select id="fi-suspect" class="ev-select" style="width:100%" aria-label="Suspect port (has the fault)">' + def + allOpts + "</select>" +
      "</div>" +
      '<div style="display:flex;gap:10px;justify-content:flex-end">' +
        '<button id="fi-action" class="btn-outline btn-ol-blue" disabled>' + esc(_fi.actionLabel) + " →</button>" +
      "</div>" +
      "</div>";

  } else if (_fi.phase === 4) {
    var verdictClsMap = {
      NicPort: "fi-verdict-nic", Cable: "fi-verdict-cable",
      Camera: "fi-verdict-camera", LikelyCamera: "fi-verdict-camera", NicHardware: "fi-verdict-nic"
    };
    var vCls = verdictClsMap[_fi.conclusion] || "fi-verdict-unknown";
    inner = '<div class="fi-verdict-card ' + esc(vCls) + '">' +
      '<div class="fi-verdict-title">' + esc(_fi.phaseTitle) + "</div>" +
      '<div class="fi-verdict-body">' + esc(_fi.phaseInstruction) + "</div>" +
      "</div>" +
      '<div style="display:flex;gap:10px;margin-top:16px">' +
        '<button id="fi-action" class="btn-outline btn-ol-blue">' + esc(_fi.actionLabel) + "</button>" +
        '<button id="fi-startover" class="btn-outline btn-ol-blue">Start Over</button>' +
      "</div>";

  } else {
    // Phases 1-3: active swap phases
    var btnLabel = _fi.checking ? ("Checking… " + (_fi.checkElapsed || 0) + "s / " + _FI_CHECK_WINDOW + "s") : _fi.actionLabel;
    // Phase 1 (AwaitingNicPortTest): show test port dropdown so the tech can
    // change it after a pre-check failure without starting over entirely.
    // Mirrors WPF's IsPickingTestPort => Phase == AwaitingNicPortTest.
    var testPortPicker = "";
    if (_fi.phase === 1 && !_fi.checking) {
      var testOpts = '<option value="-1">— Select —</option>' +
        ports.map(function(p, i) { return portOption(p, i, _fi.suspectIdx); }).join("");
      testPortPicker = '<div style="margin:12px 0">' +
        '<div class="text-xs text-pulse-muted mb-1">Test port — where you\'ll move the camera</div>' +
        '<select id="fi-test" class="ev-select" style="width:100%;max-width:360px">' + testOpts + "</select>" +
        '<div class="text-xs text-pulse-muted" style="margin-top:4px">An empty (No link) port is fine — you light it up by moving the camera over. Pick one you expect to run at this camera\'s speed.</div>' +
        "</div>";
    }
    inner = '<div class="fi-phase-card">' +
      '<div class="fi-phase-title">' + esc(_fi.phaseTitle) + "</div>" +
      '<div class="fi-phase-instr">' + esc(_fi.phaseInstruction) + "</div>" +
      resultRow() +
      testPortPicker +
      "</div>" +
      '<div style="display:flex;gap:10px;justify-content:flex-end;margin-top:12px">' +
        '<button id="fi-startover" class="btn-outline btn-ol-blue">Start Over</button>' +
        (_fi.phase === 3 && !_fi.checking ? '<button id="fi-infer" class="btn-outline btn-ol-muted">No Spare CHU — Infer</button>' : "") +
        '<button id="fi-action" class="btn-outline btn-ol-blue"' + (_fi.checking ? " disabled" : "") + ">" + esc(btnLabel) + "</button>" +
      "</div>";
  }

  // Reference NIC port diagram (static snapshot — no live badge here since
  // this page doesn't continuously poll). Lets the tech keep the physical
  // port layout in view while running the swap test.
  var diagramCard = ports.length
    ? '<div class="card" style="margin-bottom:1rem">' + _camNicDiagramHtml(ports, false) + '</div>'
    : '';

  $page().innerHTML = pageHeader(
    "Camera Connection Troubleshooting",
    "Swap test that pins a camera fault to the port, the cable, or the camera (CHU).",
    '<button class="btn-outline btn-ol-blue" onclick="navigate(\'cameras\')">' + svgIcon("arrow-left", 14) + " Back to Camera Connectivity</button>"
  ) + diagramCard + '<div class="card">' + stepDots() + inner + historyTable() + "</div>" +
    '<div id="fi-history-wrap">' + _fiHistoryHtml(_fiHistoryCache || []) + '</div>';

  // Load persisted run history on first entry (cached so phase transitions
  // don't re-fetch or flicker the panel).
  if (_fiHistoryCache === null) _fiLoadHistory();

  // ── event wiring ─────────────────────────────────────────────
  var suspectSel = document.getElementById("fi-suspect");
  var testSel    = document.getElementById("fi-test");
  var actionBtn  = document.getElementById("fi-action");
  var inferBtn   = document.getElementById("fi-infer");
  var soBtn      = document.getElementById("fi-startover");

  // Phase 0: only suspect dropdown — baseline is discovery only
  if (suspectSel && _fi.phase === 0) {
    if (_fi.suspectIdx >= 0) suspectSel.value = String(_fi.suspectIdx);
    var updateBegin = function() {
      var s = parseInt(suspectSel.value);
      if (actionBtn) actionBtn.disabled = (s < 0);
    };
    suspectSel.addEventListener("change", function() {
      _fi.suspectIdx = parseInt(suspectSel.value);
      updateBegin();
    });
    updateBegin();
  }

  // Phase 1: test port dropdown. No auto-default — the tech is physically
  // relocating hardware, so the destination is a conscious choice (defaults to
  // "— Select —"). The earlier auto-default steered toward an OCCUPIED port,
  // which means displacing a working camera; an empty port is the better target.
  if (testSel && _fi.phase === 1) {
    if (_fi.testIdx >= 0 && _fi.testIdx !== _fi.suspectIdx) testSel.value = String(_fi.testIdx);
    testSel.addEventListener("change", function() {
      _fi.testIdx = parseInt(testSel.value);
      // Visual feedback: confirm the selection by updating the instruction text
      // so the tech can see "Check Now" will use the new port.
      if (_fi.testIdx >= 0 && _fi.suspectIdx >= 0) {
        var sn = portLabel(_fi.suspectIdx);
        var tn = portLabel(_fi.testIdx);
        _fi.phaseInstruction = "Move the SAME cable + camera from " + sn +
          " to " + tn + ", then Check Now.";
        renderFaultIsolator();
      }
    });
  }

  if (actionBtn && _fi.phase === 4) {
    actionBtn.addEventListener("click", function() { navigate("cameras"); });
  } else if (actionBtn && !_fi.checking) {
    actionBtn.addEventListener("click", doAction);
  }
  if (inferBtn) inferBtn.addEventListener("click", doInfer);
  if (soBtn) soBtn.addEventListener("click", function() { _fiReset(); renderFaultIsolator(); });

  // ── async state machine ──────────────────────────────────────

  // expectedMbps: optional. If provided, polling exits early once peak
  // hits or exceeds the camera's expected speed. Defaults to 1 Gbps.
  async function pollPeakSpeed(portIdx, windowSec, expectedMbps) {
    // ── Demo mode: scripted phase results so the wizard walks all 4 phases ──
    // Static demo /api/cameras can't reflect post-swap state, so a live poll
    // would either (a) immediately conclude on whichever test port the user
    // picked, or (b) time out for 20s every phase. Scripting the per-phase
    // result lets the demo show the full 4-phase narrative ending at the
    // CAMERA verdict — the capability we want to demonstrate. Phase 0
    // (baseline) still reads the real suspect port so picking different
    // ports shows different baselines (Port 2 = degraded, Port 1 = healthy).
    var fi = _fi;
    if (dataCache.cameras && dataCache.cameras.demoMode) {
      var btn = document.getElementById("fi-action");
      // Brief animated "Checking..." beat so it doesn't snap; total ~2.5s.
      for (var t = 1; t <= 3; t++) {
        if (fi._aborted || _fi !== fi) return 0;
        fi.checkElapsed = t;
        if (btn) btn.textContent = "Checking... " + t + "s / 3s";
        await new Promise(function(r) { setTimeout(r, 800); });
      }
      if (_fi.phase === 0) {
        // Baseline: read the REAL suspect port speed (one fetch, no looping —
        // demo data is static, the first sample is the final sample).
        try {
          var fresh0 = await api("/api/cameras");
          dataCache.cameras = fresh0;
          var p0 = (fresh0.ports || [])[portIdx];
          return p0 ? (p0.linkSpeedMbps || 0) : 0;
        } catch (e) { return 0; }
      }
      if (_fi.phase === 1) return 100;   // NIC Port test — still degraded
      if (_fi.phase === 2) return 100;   // Cable test    — still degraded
      return 1000;                       // Camera test   — restored ⇒ CAMERA verdict
    }

    var threshold = expectedMbps || 1000;
    var peak = 0;
    var start = Date.now();
    var deadline = start + windowSec * 1000;
    // Smooth countdown, decoupled from the poll. The network poll below
    // iterates roughly every (api call + 1s) — 2-3s on a real VPU — so driving
    // the timer from it made the seconds jump 2-3 at a time. This ticker
    // refreshes the button ~5×/sec so the count ticks fluidly every second.
    var ticker = setInterval(function() {
      if (fi._aborted || _fi !== fi) return;
      var elapsed = Math.min(windowSec, Math.floor((Date.now() - start) / 1000));
      fi.checkElapsed = elapsed;
      var b = document.getElementById("fi-action");
      if (b) b.textContent = "Checking… " + elapsed + "s / " + windowSec + "s";
    }, 200);
    try {
      // bind to this run; a reset swaps the global _fi out
      while (Date.now() < deadline) {
        if (fi._aborted || _fi !== fi) return peak;
        var fresh;
        try { fresh = await api("/api/cameras"); dataCache.cameras = fresh; }
        catch (e) { fresh = { ports: [] }; }
        var portData = (fresh.ports || [])[portIdx];
        var sample = portData ? (portData.linkSpeedMbps || 0) : 0;
        if (sample > peak) peak = sample;
        if (peak >= threshold) return peak;
        await new Promise(function(r) { setTimeout(r, 800); });
      }
      return peak;
    } finally {
      clearInterval(ticker);
    }
  }

  function addHistory(phaseName, config, speed, verdict, severity) {
    _fi.history.unshift({ ts: new Date().toLocaleTimeString(), phase: phaseName,
      config: config, speed: speed, verdict: verdict, severity: severity });
  }

  function showResult(headline, detail, severity) {
    _fi.resultHeadline = headline;
    _fi.resultDetail   = detail;
    _fi.resultSeverity = severity.toLowerCase();
  }

  function clearResult() {
    _fi.resultHeadline = "";
    _fi.resultDetail   = "";
    _fi.resultSeverity = "";
  }

  function conclude(conclusion, title, instruction) {
    _fi.conclusion = conclusion;
    _fi.phase = 4;
    _fi.phaseTitle = title;
    _fi.phaseInstruction = instruction;
    _fi.actionLabel = "Run Full Diagnostic";
    _fi.checking = false;
    _fiSaveRun();  // persist this verdict for a returning tech
  }

  // Persist the concluded run to the backend history, then refresh the panel.
  function _fiSaveRun() {
    var suspect = ports[_fi.suspectIdx] || {};
    var cam = (suspect.camerasDetected || [])[0] || {};
    var rec = {
      ts: new Date().toISOString(),
      conclusion: _fi.conclusion,
      title: _fi.phaseTitle,
      recommendation: _fi.phaseInstruction,
      suspectPort: portLabel(_fi.suspectIdx),
      testPort: _fi.testIdx >= 0 ? portLabel(_fi.testIdx) : null,
      camera: { label: suspect.cameraLabel || null, ip: cam.ip || null, mac: cam.mac || null },
      history: (_fi.history || []).slice(),
    };
    apiPost("/api/fault-isolator/history", rec).then(function() {
      _fiHistoryCache = null;       // force a fresh fetch including this run
      _fiLoadHistory();
    }).catch(function() {});
  }

  async function doAction() {
    if (_fi.checking) return;
    var myFi = _fi;  // if the isolator is reset mid-poll, bail rather than clobber
    // Clear the previous phase's PASS/FAIL chip so the user sees only the
    // current phase's status while polling.
    clearResult();

    // Phase 0 — Baseline: poll suspect port speed (discovery only, no test port yet)
    if (_fi.phase === 0) {
      var si = _fi.suspectIdx;
      if (si < 0) return;
      // Per-port expected speed. Backend sets expectedSpeedMbps from the
      // camera model when CGI probe succeeded. If absent, fall back to
      // 100 Mbps for OCR (most common OCR variant) or 1 Gbps for Main.
      var suspectPort = ports[si] || {};
      var expectedSpd = suspectPort.expectedSpeedMbps
        || (suspectPort.isOcr ? 100 : 1000);
      var expectedLbl = formatSpeed(expectedSpd);
      _fi.checking = true;
      renderFaultIsolator();

      var spd0 = await pollPeakSpeed(si, _FI_CHECK_WINDOW, expectedSpd);
      if (_fi !== myFi || _fi._aborted) return;
      _fi.checking = false;
      var sl0 = formatSpeed(spd0);
      var sn0 = portLabel(si);
      var cfg0 = "Port: " + sn0 + "  |  Cable: (original)  |  Camera: (original)";

      // Healthy if speed meets or exceeds expected for the camera type.
      if (spd0 >= expectedSpd) {
        addHistory("Phase 1 - Baseline", cfg0, sl0, "Port healthy — no fault on this port.", "Pass");
        showResult("Baseline: " + sl0 + " — port is healthy.",
          "At the expected " + expectedLbl + " — no fault here.", "pass");
        _fi.phaseTitle = "PORT HEALTHY — NO FAULT FOUND";
        _fi.phaseInstruction = "This port is at its expected speed — no fault to isolate here. To test a different port, select it above and start its baseline. Otherwise close the wizard.";
        _fi.actionLabel = "Start Baseline";
        // Reset to phase 0 so the suspect dropdown reappears for re-selection.
        _fi.phase = 0;
        renderFaultIsolator();
        return;
      }

      var bMsg, bInstr;
      if (spd0 <= 0) {
        bMsg = "No link";
        bInstr = "Confirm the camera is powered and the cable seated (both ends). Still no link? Pick a test port below, move the camera over, then Check Now.";
      } else {
        bMsg   = "Degraded — " + sl0 + " (expected " + expectedLbl + ")";
        bInstr = "Pick a test port below, then move the SAME cable + camera from " + sn0 + " to it. Check Now.";
      }
      addHistory("Phase 1 - Baseline", cfg0, sl0, bMsg + " — isolating.", "Fail");
      // Detail omitted on purpose — the next step already shows as the phase
      // instruction directly above this callout; repeating bInstr was clutter.
      showResult("Baseline: " + bMsg + ".", "", "fail");
      // Remember expected speed so subsequent phases use the right pass threshold.
      _fi.expectedSpeedMbps = expectedSpd;
      // Capture the suspect's camera MAC(s) so Phase 1 can verify the swap
      // actually moved the camera to the test port (vs. user clicked Check
      // Now without doing anything).
      _fi.suspectCameraMacs = (suspectPort.camerasDetected || []).map(function(c) {
        return String(c.mac || "").toUpperCase().replace(/-/g, ":");
      }).filter(function(m) { return m; });
      _fi.phase = 1;
      _fi.phaseTitle = "DOES THE FAULT FOLLOW THE NIC PORT?";
      _fi.phaseInstruction = bInstr;
      _fi.actionLabel = "Check Now";
      renderFaultIsolator();
      return;
    }

    // Phase 1 — NIC Port Test: poll test port after moving cable+camera
    if (_fi.phase === 1) {
      // Re-read test port index from dropdown (may have changed via test port picker)
      var testSel1 = document.getElementById("fi-test");
      if (testSel1) _fi.testIdx = parseInt(testSel1.value);
      if (_fi.testIdx < 0 || _fi.testIdx === _fi.suspectIdx) {
        showResult("No test port selected.", "Pick a test port from the dropdown before continuing.", "fail");
        renderFaultIsolator();
        return;
      }
      // No pre-check on the test port's pre-swap speed: an empty target reads
      // "No link" and a port hosting an OCR reads 100, yet either can be a fine
      // 1 Gbps target once the suspect camera is moved onto it. The real guards
      // come AFTER the swap — the swap-verification (suspect MAC moved to the
      // test port) and the post-swap speed reading interpret the result.
      // Expected speed for the suspect camera — drives the pass threshold.
      var expSpd1 = _fi.expectedSpeedMbps || 1000;
      var expLbl1 = formatSpeed(expSpd1);
      _fi.checking = true;
      renderFaultIsolator();
      var spd1 = await pollPeakSpeed(_fi.testIdx, _FI_CHECK_WINDOW, expSpd1);
      if (_fi !== myFi || _fi._aborted) return;
      _fi.checking = false;
      var sl1 = formatSpeed(spd1);
      var tn1 = portLabel(_fi.testIdx);
      var sn1 = portLabel(_fi.suspectIdx);
      var cfg1 = "Port: " + tn1 + " (test port)  |  Cable: (original)  |  Camera: (original)";

      // Swap verification: the suspect camera's MAC should now appear on
      // the test port's ARP. If it doesn't AND the suspect port still has
      // it, the user clicked Check Now without performing the physical
      // swap. Without this check, a healthy test port + unmoved cable
      // would falsely conclude "NIC port fault".
      // Skipped in demo mode — static demo data can't simulate the ARP change.
      var swapVerified = true;
      var isDemo = !!(dataCache.cameras && dataCache.cameras.demoMode);
      if (!isDemo && (_fi.suspectCameraMacs || []).length > 0) {
        var fresh = dataCache.cameras || {};
        var freshPorts = fresh.ports || [];
        var testPortFresh = freshPorts[_fi.testIdx] || {};
        var suspectPortFresh = freshPorts[_fi.suspectIdx] || {};
        var macsOnTest = (testPortFresh.camerasDetected || []).map(function(c) {
          return String(c.mac || "").toUpperCase().replace(/-/g, ":");
        });
        var macsOnSuspect = (suspectPortFresh.camerasDetected || []).map(function(c) {
          return String(c.mac || "").toUpperCase().replace(/-/g, ":");
        });
        var movedToTest = _fi.suspectCameraMacs.some(function(m) {
          return macsOnTest.indexOf(m) >= 0;
        });
        var stillOnSuspect = _fi.suspectCameraMacs.some(function(m) {
          return macsOnSuspect.indexOf(m) >= 0;
        });
        // If the camera didn't appear on the test port AND it's still on
        // the suspect port, the swap clearly wasn't done.
        if (!movedToTest && stillOnSuspect) {
          swapVerified = false;
          var suspectMac = _fi.suspectCameraMacs[0];
          addHistory("Phase 2 - NIC Port Test", cfg1, sl1,
            "Swap not verified — camera " + suspectMac + " still on " + sn1 + ", not on " + tn1 + ".", "Info");
          showResult(
            "Swap not detected — test inconclusive.",
            "The suspect camera (" + suspectMac + ") still appears on " + sn1 +
            " and was not detected on " + tn1 + ". Please physically move the cable and camera from " +
            sn1 + " to " + tn1 + ", then click Check Now again. " +
            "Note: the network can take up to 30 seconds to register the move.",
            "fail"
          );
          renderFaultIsolator();
          return;
        }
      }

      if (spd1 >= expSpd1) {
        var v1 = "Link restored on the test port — fault is the original NIC port.";
        addHistory("Phase 2 - NIC Port Test", cfg1, sl1, v1, "Pass");
        showResult("Phase 2: " + sl1 + " — fault follows the NIC port.", "", "pass");
        conclude("NicPort", "CONCLUSION — FAULTY NIC PORT",
          "Moving to " + tn1 + " restored the link — the original NIC port is the fault. Escalate for NIC/motherboard repair.");
        renderFaultIsolator();
        return;
      }
      if (spd1 <= 0) {
        addHistory("Phase 2 - NIC Port Test", cfg1, sl1, "No link detected — test inconclusive.", "Info");
        _fi.phaseInstruction = "No link on " + tn1 + ". Check the cable is seated and the camera powered, then Check Now.";
        showResult("Phase 2: No link — test inconclusive.", _fi.phaseInstruction, "info");
        renderFaultIsolator();
        return;
      }
      var cv1 = "Fault followed the cable/camera — NIC port is fine.";
      addHistory("Phase 2 - NIC Port Test", cfg1, sl1, cv1, "Info");
      showResult("Phase 2: " + sl1 + " — NIC port is fine; fault follows the cable/camera.", "", "info");
      _fi.phase = 2;
      _fi.phaseTitle = "DOES THE FAULT FOLLOW THE CABLE?";
      _fi.phaseInstruction = "Keep the camera on " + tn1 + ". Swap the original cable for a known-good one (both ends), then Check Now.";
      _fi.actionLabel = "Check Now";
      renderFaultIsolator();
      return;
    }

    // Phase 2 — Cable Test: poll test port after swapping cable
    if (_fi.phase === 2) {
      var expSpd2 = _fi.expectedSpeedMbps || 1000;
      _fi.checking = true;
      renderFaultIsolator();
      var spd2 = await pollPeakSpeed(_fi.testIdx, _FI_CHECK_WINDOW, expSpd2);
      if (_fi !== myFi || _fi._aborted) return;
      _fi.checking = false;
      var sl2 = formatSpeed(spd2);
      var tn2 = portLabel(_fi.testIdx);
      var cfg2 = "Port: " + tn2 + "  |  Cable: (NEW — known good)  |  Camera: (original)";

      if (spd2 >= expSpd2) {
        var v2 = "Link restored with a known-good cable — cable is the fault.";
        addHistory("Phase 3 - Cable Test", cfg2, sl2, v2, "Pass");
        showResult("Phase 3: " + sl2 + " — fault follows the cable.", "", "pass");
        conclude("Cable", "CONCLUSION — FAULTY CABLE",
          "Replacing the cable restored the link — the original cable is the fault. Re-terminate both ends or replace the run, and check it for damage (kinks, crushing, pinch points).");
        renderFaultIsolator();
        return;
      }
      if (spd2 <= 0) {
        addHistory("Phase 3 - Cable Test", cfg2, sl2, "No link detected — test inconclusive.", "Info");
        _fi.phaseInstruction = "No link on " + tn2 + ". Check the new cable (both ends) and camera power, then Check Now.";
        showResult("Phase 3: No link — test inconclusive.", _fi.phaseInstruction, "info");
        renderFaultIsolator();
        return;
      }
      var cv2 = "Fault followed the camera — cable is fine.";
      addHistory("Phase 3 - Cable Test", cfg2, sl2, cv2, "Info");
      showResult("Phase 3: " + sl2 + " — cable is fine; fault follows the camera.", "", "info");
      _fi.phase = 3;
      _fi.phaseTitle = "DOES THE FAULT FOLLOW THE CAMERA?";
      _fi.phaseInstruction = "Keep the new cable on " + tn2 + ". Connect a known-good camera, then Check Now. No spare? Click \"No Spare CHU — Infer\".";
      _fi.actionLabel = "Check Now";
      renderFaultIsolator();
      return;
    }

    // Phase 3 — Camera Test: poll test port after swapping camera
    // Note: known-good camera is most likely a Main Camera (1 Gbps) since
    // OCR spares are rare. Pass threshold is 1 Gbps here, not the suspect's
    // expected speed — we're testing the NEW camera's capability.
    if (_fi.phase === 3) {
      _fi.checking = true;
      renderFaultIsolator();
      var spd3 = await pollPeakSpeed(_fi.testIdx, _FI_CHECK_WINDOW);
      if (_fi !== myFi || _fi._aborted) return;
      _fi.checking = false;
      var sl3 = formatSpeed(spd3);
      var tn3 = portLabel(_fi.testIdx);
      var cfg3 = "Port: " + tn3 + "  |  Cable: (NEW)  |  Camera: (NEW — known good)";

      if (spd3 >= 1000) {
        var v3 = "Link restored with a known-good camera — camera is the fault.";
        addHistory("Phase 4 - Camera Test", cfg3, sl3, v3, "Pass");
        showResult("Phase 4: " + sl3 + " — fault follows the camera.", "", "pass");
        conclude("Camera", "CONCLUSION — FAULTY CAMERA (CHU)",
          "Replacing the camera restored the link — the original camera (CHU) is the fault. Replace the camera unit.");
        renderFaultIsolator();
        return;
      }
      if (spd3 <= 0) {
        addHistory("Phase 4 - Camera Test", cfg3, sl3, "No link detected — test inconclusive.", "Info");
        _fi.phaseInstruction = "No link on " + tn3 + ". Check the known-good camera is connected and powered, then Check Now.";
        showResult("Phase 4: No link — test inconclusive.", _fi.phaseInstruction, "info");
        renderFaultIsolator();
        return;
      }
      var vf3 = "Still failing with known-good cable and camera — likely NIC hardware or motherboard.";
      addHistory("Phase 4 - Camera Test", cfg3, sl3, vf3, "Fail");
      showResult("Phase 4: " + sl3 + " — still failing with known-good equipment.", "", "fail");
      conclude("NicHardware", "CONCLUSION — NIC / HARDWARE FAULT",
        "Known-good cable and camera still fail on " + tn3 + " — the fault is in the NIC hardware or motherboard. Run the full diagnostic and escalate to hardware repair.");
      renderFaultIsolator();
      return;
    }
  }

  function doInfer() {
    if (_fi.phase !== 3) return;
    var tn = portLabel(_fi.testIdx);
    var cfg = "Port: " + tn + "  |  Cable: (NEW)  |  Camera: (no spare available)";
    addHistory("Phase 4 - SKIPPED", cfg, "—",
      "No spare CHU — inferred from Phase 2 and Phase 3.", "Info");
    showResult("Phase 4 skipped — inferred conclusion.",
      "NIC port (Phase 2) and cable (Phase 3) are both cleared — the camera (CHU) is the remaining suspect.", "info");
    conclude("LikelyCamera", "LIKELY CAMERA (CHU) FAULT — UNVERIFIED",
      "NIC port and cable are already cleared, so the camera (CHU) is the remaining suspect. Replace it when a known-good spare is available; if a known-good camera still fails, it's likely NIC hardware — run the full diagnostic and escalate.");
    renderFaultIsolator();
  }
}

// ── Audio ────────────────────────────────────────────────────

// Thresholds & timing constants
const AUDIO_SIGNAL_THRESHOLD = 1;
const AUDIO_PEAK_HOT = 80;
const AUDIO_REFRESH_MS = 2000;

let _audioRefreshTimer = null;
let _audioFetchInFlight = false;

function renderAudio() {
  const data = cached("audio");
  if (!data) { $page().innerHTML = sectionLoading("Audio"); fetchSection("audio"); return; }

  // Clear any previous live-refresh timer + reset in-flight guard
  if (_audioRefreshTimer) { clearInterval(_audioRefreshTimer); _audioRefreshTimer = null; }
  _audioFetchInFlight = false;

  // Hard error — show errorBox like other renderers
  if (data.error) { $page().innerHTML = errorBox(data.message || "Couldn't detect audio devices"); return; }

  const devices = data.devices || [];
  // Windows keeps an endpoint entry for every audio device it has EVER seen;
  // on a long-lived VPU those NotPresent ghosts outnumber real devices ~10:1
  // (81 of 91 on the bench VPU). Drop them entirely — a tech can't touch them.
  const present = devices.filter(d => d.state !== "NotPresent");
  const presentInputs = present.filter(d => d.dataFlow === "Input");
  const presentOutputs = present.filter(d => d.dataFlow === "Output");
  // Main sections show only Active devices; Unplugged/Disabled ones are real
  // hardware but not usable right now, so they share one disclosure below.
  const inputs = presentInputs.filter(d => d.state === "Active");
  const outputs = presentOutputs.filter(d => d.state === "Active");
  const inactive = [...presentInputs, ...presentOutputs].filter(d => d.state !== "Active");
  // WMI fallback returns dataFlow="Unknown" — surface these so they're not invisible
  const others = present.filter(d => d.dataFlow !== "Input" && d.dataFlow !== "Output");

  // Page-level indicator: is anything making sound?
  const anySignal = devices.some(d => d.peak != null && d.peak > AUDIO_SIGNAL_THRESHOLD);

  // Findings — surface diagnostic warnings (PULSEDEV-38)
  const findings = _audioFindings(devices, data);

  $page().innerHTML = `
    ${pageHeader("Audio", "Audio devices, volume, and signal activity",
      `<button class="btn-outline btn-ol-blue" onclick="dataCache.audio=null;renderAudio()">
        ${svgIcon("refresh", 14)} Refresh
      </button>`
    )}

    ${findings.length ? `<div class="card audio-findings">
      ${findings.map(f => `<div class="audio-finding audio-finding-${esc(f.severity)}">
        <span class="audio-finding-pill audio-finding-pill-${esc(f.severity)}">${esc(f.severity.toUpperCase())}</span>
        <div><div class="audio-finding-title">${esc(f.title)}</div>
          <div class="audio-finding-body">${esc(f.body)}</div></div>
      </div>`).join("")}
    </div>` : ""}

    <div class="audio-summary">
      ${_audioSummaryCard("Input Devices", inputs.length, presentInputs.length, "mic")}
      ${_audioSummaryCard("Output Devices", outputs.length, presentOutputs.length, "volume")}
      <div class="card audio-signal-card">
        <div class="audio-signal-dot ${anySignal ? "audio-signal-active" : "audio-signal-silent"}"></div>
        <div>
          <div class="text-sm font-semibold">${anySignal ? "Signal Detected" : "No Signal"}</div>
          <div class="text-xs text-pulse-muted">${anySignal ? "Audio activity on one or more devices" : "All devices silent"}</div>
        </div>
      </div>
    </div>

    <div class="card mt-4">
      ${sectionTitle("mic", "Input Devices")}
      ${inputs.length
        ? inputs.map(d => _audioDeviceRow(d)).join("")
        : '<p class="text-sm text-pulse-muted">No active input devices</p>'}
    </div>

    <div class="card mt-4">
      ${sectionTitle("volume", "Output Devices")}
      ${outputs.length
        ? outputs.map(d => _audioDeviceRow(d)).join("")
        : '<p class="text-sm text-pulse-muted">No active output devices</p>'}
    </div>

    ${others.length ? `<div class="card mt-4">
      ${sectionTitle("info", "Other Devices")}
      <p class="text-xs text-pulse-muted mb-2">Devices Windows reports without an input or output direction.</p>
      ${others.map(d => _audioDeviceRow(d)).join("")}
    </div>` : ""}

    ${inactive.length ? `<details class="card mt-4 audio-inactive">
      <summary class="audio-inactive-summary">${inactive.length} inactive device${inactive.length === 1 ? "" : "s"} (unplugged or disabled)</summary>
      <p class="text-xs text-pulse-muted mt-2 mb-2">Connected hardware that isn't usable right now — a jack with nothing plugged in, or a device disabled in Windows.</p>
      ${inactive.map(d => _audioDeviceRow(d)).join("")}
    </details>` : ""}
  `;

  // Wire up volume sliders with success/error feedback
  devices.forEach(d => {
    if (d.state !== "Active" || d.volume == null) return;
    const slug = _audioSlug(d.id);
    const slider = document.getElementById(`vol-${slug}`);
    const label  = document.getElementById(`vol-lbl-${slug}`);
    const msg    = document.getElementById(`vol-msg-${slug}`);
    if (!slider) return;

    slider.addEventListener("change", async () => {
      const val = parseInt(slider.value, 10);
      if (label) label.textContent = val + "%";
      const r = await apiPost("/api/audio/volume", { deviceId: d.id, volume: val });
      if (!msg) return;
      if (r && r.error) {
        msg.textContent = "Failed: " + (r.message || "unknown error");
        msg.className = "audio-vol-msg audio-vol-msg-err";
      } else {
        msg.textContent = "Saved";
        msg.className = "audio-vol-msg audio-vol-msg-ok";
        setTimeout(() => { if (msg) msg.textContent = ""; }, 1500);
      }
    });
    slider.addEventListener("input", () => {
      if (label) label.textContent = parseInt(slider.value, 10) + "%";
    });
  });

  // Live-refresh peak meters. In-flight guard prevents overlapping requests
  // when the backend script takes longer than the refresh interval on slow VPUs.
  _audioRefreshTimer = setInterval(() => {
    if (currentPage !== "audio") {
      clearInterval(_audioRefreshTimer); _audioRefreshTimer = null; return;
    }
    if (_audioFetchInFlight) return;
    _audioFetchInFlight = true;
    api("/api/audio").then(fresh => {
      _audioFetchInFlight = false;
      if (!fresh || fresh.error || currentPage !== "audio") return;
      (fresh.devices || []).forEach(d => _audioUpdateMeter(d));
    }).catch(() => { _audioFetchInFlight = false; });
  }, AUDIO_REFRESH_MS);
}

function _audioUpdateMeter(d) {
  const slug = _audioSlug(d.id);
  const bar = document.getElementById(`peak-${slug}`);
  const lbl = document.getElementById(`peak-lbl-${slug}`);
  if (bar && d.peak != null) {
    bar.style.width = Math.min(d.peak, 100) + "%";
    bar.className = "audio-peak-fill" + _audioPeakClass(d.peak);
  }
  if (lbl) lbl.textContent = d.peak != null ? d.peak + "%" : "—";
}

function _audioPeakClass(peak) {
  if (peak == null) return "";
  if (peak > AUDIO_PEAK_HOT) return " audio-peak-hot";
  if (peak > AUDIO_SIGNAL_THRESHOLD) return " audio-peak-ok";
  return "";
}

// Surface diagnostic findings — e.g. "Line-In active but silent" (PULSEDEV-38).
function _audioFindings(devices, data) {
  const out = [];
  const silentLineIns = devices.filter(d =>
    d.state === "Active" &&
    d.dataFlow === "Input" &&
    (d.formFactor === "LineLevel" || /line.in/i.test(d.name || "")) &&
    d.peak != null && d.peak <= AUDIO_SIGNAL_THRESHOLD
  );
  silentLineIns.forEach(d => {
    out.push({
      severity: "warning",
      title: "Line-in source is silent",
      body: `${d.name || "Line-in device"} is active but no audio signal detected. Verify the source is connected and unmuted.`
    });
  });
  if (data.wmiFallback) {
    out.push({
      severity: "info",
      title: "Limited device info",
      body: "Couldn't read full device details — volume, mute, and signal meters are unavailable."
    });
  }
  return out;
}

// Short stable slug from a device ID — djb2-style hash so HTML IDs stay
// compact even for long Windows endpoint GUIDs.
function _audioSlug(id) {
  const s = String(id || "");
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0;
  return "d" + (h >>> 0).toString(36);
}

function _audioSummaryCard(label, active, total, icon) {
  return `<div class="card audio-summary-card">
    <div class="audio-summary-icon">${svgIcon(icon, 20)}</div>
    <div class="audio-summary-num">${active}<span class="text-pulse-muted text-sm font-normal"> / ${total}</span></div>
    <div class="text-xs text-pulse-muted">${esc(label)}</div>
  </div>`;
}

function _audioFormFactorBadge(ff) {
  const labels = {
    LineLevel: "Line-In", Microphone: "Mic", Headphones: "Headphones",
    Headset: "Headset", Speakers: "Speakers", SPDIF: "S/PDIF",
    DigitalDisplay: "HDMI/DP", DigitalPassthrough: "Digital", RemoteNetwork: "Network",
    Handset: "Handset", Unknown: "Unknown"
  };
  const text = labels[ff] || ff || "Unknown";
  return `<span class="audio-port-badge">${esc(text)}</span>`;
}

function _audioFormFactorLabel(ff) {
  const labels = {
    LineLevel: "Line-in", Microphone: "Microphone", Headphones: "Headphone",
    Headset: "Headset", Speakers: "Speaker", SPDIF: "S/PDIF",
    DigitalDisplay: "Display audio (HDMI/DisplayPort)",
    DigitalPassthrough: "Digital passthrough", RemoteNetwork: "Network",
    Handset: "Handset"
  };
  return labels[ff] || ff;
}

function _audioDeviceRow(d) {
  const slug = _audioSlug(d.id);
  const isActive = d.state === "Active";
  // Use the canonical pill component so audio state matches every other
  // status indicator in the app (Services, Disk Health, etc.) instead of
  // appearing as bare colored text.
  const badgeKind = isActive ? "pass" : d.state === "Disabled" ? "warn" : "fail";
  // Windows default recording/playback device — what most capture software
  // (including Pixellot's pipeline) records from unless configured otherwise.
  const isDefault = d.dataFlow === "Input" ? d.isDefaultCapture : d.isDefaultRender;

  return `<div class="audio-device${isActive ? "" : " audio-device-inactive"}">
    <div class="audio-device-header">
      <div class="audio-device-name">${esc(d.name || "Unknown Device")}</div>
      <div class="audio-device-badges">
        ${isDefault ? '<span class="audio-port-badge">Default</span>' : ""}
        ${_audioFormFactorBadge(d.formFactor)}
        ${badge(d.state, badgeKind)}
      </div>
    </div>
    ${isActive ? `
      <div class="audio-device-controls">
        <div class="audio-meter-row">
          <span class="audio-meter-label">Signal</span>
          <div class="audio-peak-track">
            <div id="peak-${slug}" class="audio-peak-fill${_audioPeakClass(d.peak)}" style="width:${Math.min(d.peak || 0, 100)}%"></div>
          </div>
          <span id="peak-lbl-${slug}" class="audio-meter-val">${d.peak != null ? d.peak + "%" : "—"}</span>
        </div>
        ${d.volume != null ? `
          <div class="audio-meter-row">
            <span class="audio-meter-label">${d.muted ? svgIcon("volume-x", 14) : svgIcon("volume", 14)}</span>
            <input type="range" id="vol-${slug}" class="audio-slider${d.muted ? " audio-slider-muted" : ""}" min="0" max="100" value="${Math.round(d.volume)}" aria-label="Volume — ${esc(d.name || "audio device")}"/>
            <span id="vol-lbl-${slug}" class="audio-meter-val">${Math.round(d.volume)}%</span>
            <span id="vol-msg-${slug}" class="audio-vol-msg"></span>
          </div>` : ""}
      </div>
    ` : (d.formFactor && d.formFactor !== "Unknown" ? `
      <div class="audio-device-controls">
        <p class="text-xs text-pulse-muted">${esc(_audioFormFactorLabel(d.formFactor))} device — controls unavailable while ${d.state === "NotPresent" ? "not connected" : esc(d.state.toLowerCase())}.</p>
      </div>
    ` : "")}
  </div>`;
}

// ── Settings ─────────────────────────────────────────────────

function renderSettings() {
  const data = cached("settings");
  if (!data) { $page().innerHTML = sectionLoading("Settings"); fetchSection("settings"); return; }

  $page().innerHTML = `
    ${pageHeader("Settings", "App preferences and diagnostic helpers")}

    <!-- Software Update -->
    <div class="card">
      ${sectionTitle("refresh", "Software Update")}
      <p class="text-sm text-pulse-muted mb-3">Check for a newer Pulse build on this VPU's channel and install it. Pulse restarts and this page reloads automatically — no need to re-run the launcher.</p>
      <div class="settings-actions">
        <button class="btn-outline btn-ol-blue" id="set-update-check">
          ${svgIcon("globe", 14)} Check for Update
        </button>
        <button class="btn-outline btn-ol-green" id="set-update-apply" style="display:none">
          ${svgIcon("refresh", 14)} Update &amp; Restart
        </button>
        <span id="set-update-msg" class="text-sm text-pulse-muted"></span>
      </div>
      <div id="set-update-notes" class="update-notes" style="display:none"></div>
    </div>

    <!-- Restart Pulse app -->
    <div class="card mt-4">
      ${sectionTitle("refresh", "Restart Pulse App")}
      <p class="text-sm text-pulse-muted mb-3">Restart the Pulse app if the page is stuck or behaving oddly. The VPU and any active recording keep running, and this page reloads automatically once Pulse is back — usually a few seconds.</p>
      <div class="settings-actions">
        <button class="btn-outline btn-ol-blue" id="set-restart-app">
          ${svgIcon("refresh", 14)} Restart Pulse app
        </button>
        <span id="set-restart-msg" class="text-sm text-pulse-muted"></span>
      </div>
    </div>

    <!-- Reboot VPU -->
    <div class="card mt-4">
      ${sectionTitle("power", "Reboot VPU")}
      <p class="text-sm text-pulse-muted mb-3">Reboot the whole VPU to restart Windows. This interrupts any active recording and the unit is offline for a few minutes. Pulse won't reopen on its own — relaunch it from the desktop shortcut once Windows is back.</p>
      <div class="settings-actions">
        <button class="btn-outline btn-ol-red" id="set-reboot-vpu">
          ${svgIcon("power", 14)} Reboot VPU
        </button>
        <span id="set-reboot-msg" class="text-sm text-pulse-muted"></span>
      </div>
    </div>
  `;

  // ── Software Update ──
  const upCheckBtn = document.getElementById("set-update-check");
  const upApplyBtn = document.getElementById("set-update-apply");
  const upMsg = document.getElementById("set-update-msg");
  let upLatest = null, upCurrent = null;

  upCheckBtn?.addEventListener("click", async () => {
    upCheckBtn.disabled = true;
    upApplyBtn.style.display = "none";
    _renderUpdateNotes(null);
    upMsg.textContent = "Checking…";
    try {
      const r = await api("/api/update/check");
      upCurrent = r.current || null;
      if (r.error) {
        // The api() helper signals failures with { error: true, message }, so
        // render a string — never the bare boolean (which showed as "true").
        upMsg.textContent = typeof r.error === "string" ? r.error : (r.message || "Couldn't check for updates.");
      } else if (!r.managed) {
        upMsg.textContent = r.note || "Updates are managed externally on this install.";
      } else if (r.updateAvailable) {
        upLatest = r.latest;
        upMsg.innerHTML = `Update available: <strong>${esc(r.latest)}</strong> <span class="text-pulse-muted">(installed ${esc(r.current)})</span>`;
        upApplyBtn.style.display = "";
        _renderUpdateNotes(r.notes);
      } else {
        upMsg.textContent = `You're on the latest build (${esc(r.current)}).`;
      }
    } catch (e) {
      upMsg.textContent = "Couldn't check for updates.";
    } finally {
      upCheckBtn.disabled = false;
    }
  });

  upApplyBtn?.addEventListener("click", async () => {
    if (!confirm(`Download and install ${upLatest}?\n\nPulse will restart and this page will reload automatically.`)) return;
    upApplyBtn.disabled = true;
    upCheckBtn.disabled = true;
    upMsg.textContent = "Starting update…";
    try {
      const r = await apiPost("/api/update/apply", {});
      if (!r.ok) {
        upMsg.textContent = (typeof r.error === "string" ? r.error : r.message) || "Update couldn't start.";
        upApplyBtn.disabled = false;
        upCheckBtn.disabled = false;
        return;
      }
      _showUpdateOverlay(upLatest);
      _pollForRestart(upCurrent);
    } catch (e) {
      upMsg.textContent = "Update couldn't start.";
      upApplyBtn.disabled = false;
      upCheckBtn.disabled = false;
    }
  });

  // ── Restart Pulse app / Reboot VPU ──
  const restartBtn = document.getElementById("set-restart-app");
  const rebootBtn = document.getElementById("set-reboot-vpu");
  const restartMsg = document.getElementById("set-restart-msg");
  const rebootMsg = document.getElementById("set-reboot-msg");

  restartBtn?.addEventListener("click", async () => {
    if (!confirm("Restart the Pulse app?\n\nPulse closes and relaunches the same build. This page reloads automatically once it's back — usually a few seconds. The VPU and any recording keep running.")) return;
    restartBtn.disabled = true;
    rebootBtn.disabled = true;
    restartMsg.textContent = "Restarting…";
    try {
      const r = await apiPost("/api/maintenance/restart-app", {});
      if (!r.ok) {
        restartMsg.textContent = (typeof r.error === "string" ? r.error : r.message) || "Couldn't restart Pulse.";
        restartBtn.disabled = false;
        rebootBtn.disabled = false;
        return;
      }
      _showMaintenanceOverlay("Restarting Pulse…", "Pulse is relaunching. This page reloads automatically once it's back — usually a few seconds.");
      _pollForRestart(dataCache._version);
    } catch (e) {
      restartMsg.textContent = "Couldn't restart Pulse.";
      restartBtn.disabled = false;
      rebootBtn.disabled = false;
    }
  });

  rebootBtn?.addEventListener("click", async () => {
    if (!confirm("Reboot the whole VPU?\n\nThis restarts Windows. Any active recording is interrupted, and the unit is offline for a few minutes. Pulse won't come back on its own — reopen it from the desktop shortcut once Windows is back.")) return;
    restartBtn.disabled = true;
    rebootBtn.disabled = true;
    rebootMsg.textContent = "Sending reboot…";
    try {
      // Reboot-Vpu.ps1 returns { success, message }; api() wraps failures in { error }.
      const r = await apiPost("/api/maintenance/reboot-vpu", {});
      if (r && r.success) {
        _showMaintenanceOverlay("Rebooting the VPU…",
          (r.message ? r.message + " " : "The VPU is restarting. ") +
          "Reopen Pulse from the desktop shortcut once Windows is back.");
        _pollForRestart(dataCache._version);
      } else {
        rebootMsg.textContent = (r && (r.message || (typeof r.error === "string" ? r.error : null))) || "Couldn't reboot the VPU.";
        restartBtn.disabled = false;
        rebootBtn.disabled = false;
      }
    } catch (e) {
      rebootMsg.textContent = "Couldn't reboot the VPU.";
      restartBtn.disabled = false;
      rebootBtn.disabled = false;
    }
  });
}

// Dismissible strip at the top of the content pane, shown the one time the
// server migrates this install off the retired beta channel (boot-time
// /api/version -> channelMoved). Deliberately calm: the move is done and
// needs nothing from the tech — this is a courtesy heads-up, not an alert.
function _showChannelMovedBanner() {
  if (document.getElementById("channel-moved-banner")) return;
  const el = document.createElement("div");
  el.id = "channel-moved-banner";
  el.className = "channel-moved-banner";
  el.setAttribute("role", "status");
  el.innerHTML = `
    <span>${svgIcon("info", 16)}</span>
    <span class="channel-moved-text">The Pulse beta program has wrapped up — thanks for testing!
      This VPU has been moved to the <strong>production</strong> version of Pulse, which opens
      automatically from your next launch. Nothing to do on your end.</span>
    <button class="channel-moved-dismiss" title="Dismiss" aria-label="Dismiss">&times;</button>`;
  el.querySelector(".channel-moved-dismiss").addEventListener("click", () => el.remove());
  const content = document.getElementById("content");
  content?.insertBefore(el, content.firstChild);
}

// ── Software Update helpers (module scope so they survive a re-render) ──
function _renderUpdateNotes(notes) {
  const el = document.getElementById("set-update-notes");
  if (!el) return;
  const text = (notes || "").trim();
  // GitHub release bodies are markdown; show them as readable escaped text
  // with line breaks preserved (CSS white-space) — no markdown renderer and
  // no injection risk.
  el.textContent = text;
  el.style.display = text ? "" : "none";
}

function _showUpdateOverlay(tag) {
  let el = document.getElementById("pulse-update-overlay");
  if (!el) {
    el = document.createElement("div");
    el.id = "pulse-update-overlay";
    el.className = "update-overlay";
    document.body.appendChild(el);
  }
  el.innerHTML = `
    <div class="update-overlay-box">
      <div class="update-spinner" aria-hidden="true"></div>
      <div class="update-overlay-title">Updating Pulse${tag ? " to " + esc(tag) : ""}…</div>
      <p class="update-overlay-sub" id="update-overlay-sub">Pulse is restarting. This page reloads automatically once it's back — usually under a minute.</p>
    </div>`;
  el.style.display = "flex";
}

// Generic full-screen "please wait, the server is coming back" overlay, shared
// by the Restart-Pulse and Reboot-VPU actions. Same element/markup as the
// update overlay, just with caller-supplied title + subtext.
function _showMaintenanceOverlay(title, sub) {
  let el = document.getElementById("pulse-update-overlay");
  if (!el) {
    el = document.createElement("div");
    el.id = "pulse-update-overlay";
    el.className = "update-overlay";
    document.body.appendChild(el);
  }
  el.innerHTML = `
    <div class="update-overlay-box">
      <div class="update-spinner" aria-hidden="true"></div>
      <div class="update-overlay-title">${esc(title)}</div>
      <p class="update-overlay-sub" id="update-overlay-sub">${esc(sub)}</p>
    </div>`;
  el.style.display = "flex";
}

function _pollForRestart(currentVer) {
  let sawDown = false;
  const startedAt = Date.now();
  const tick = async () => {
    if (Date.now() - startedAt > 180000) {
      const sub = document.getElementById("update-overlay-sub");
      if (sub) sub.textContent = "This is taking longer than expected. If Pulse doesn't come back on its own, relaunch it from the desktop shortcut.";
      return;
    }
    try {
      const res = await fetch("/api/version", { cache: "no-store" });
      if (res.ok) {
        let changed = false;
        try {
          const d = await res.json();
          changed = !!(currentVer && d && d.version && d.version !== currentVer);
        } catch (_) {}
        if (sawDown || changed) { location.reload(); return; }
      } else {
        sawDown = true;
      }
    } catch (e) {
      sawDown = true;
    }
    setTimeout(tick, 2000);
  };
  setTimeout(tick, 3000);
}

// ── About ────────────────────────────────────────────────────

function renderAbout() {
  const dash = cached("dashboard");
  if (!dash) fetchSection("dashboard");
  const id = (dash || {}).identity || {};
  const ver = dataCache._version;

  $page().innerHTML = `
    <div class="about-container">
      <div class="card about-card">
        <div class="about-icon">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--c-accent-blue)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
          </svg>
        </div>
        <h2 class="about-title">Pulse</h2>
        <p class="about-tagline">Pixellot Unified Live System Evaluator</p>
        <div class="about-version" id="about-version">${ver ? esc(ver) + " · Web Edition" : "… · Web Edition"}</div>
        <p class="about-desc">A lightweight, self-contained diagnostic tool for Pixellot VPU systems. Collects system identity, hardware, performance metrics, network configuration, camera connectivity, service status, disk health, and event logs.</p>
        <div class="about-info">
          <div class="kv-grid kv-grid-center">
            ${kvRow("Hostname", id.hostname || "—")}
            ${kvRow("OS", id.os || "—")}
            ${kvRow("Backend", "Python + FastAPI + Uvicorn")}
            ${kvRow("Frontend", "Vanilla HTML/JS + Tailwind CSS")}
            ${kvRow("Data Collection", "PowerShell + WMI/CIM")}
          </div>
        </div>
        <div class="about-links">
          <a href="https://github.com/playon/pulse/releases" target="_blank" rel="noopener" class="btn-outline btn-ol-green" title="Open the GitHub releases page in a new tab">
            ${svgIcon("external-link", 14)} View Releases
          </a>
          <a href="https://github.com/playon/pulse" target="_blank" rel="noopener" class="btn-outline btn-ol-blue" title="Open the source repository in a new tab">
            ${svgIcon("external-link", 14)} Source Repo
          </a>
        </div>
      </div>
    </div>
  `;
  if (!ver) {
    api("/api/version").then((d) => {
      const el = document.getElementById("about-version");
      if (el && d?.version) el.textContent = d.version + " · Web Edition";
    }).catch(() => {});
  }
}

// ── Init ─────────────────────────────────────────────────────

async function init() {
  const navEl = document.getElementById("nav-links");
  navEl.innerHTML = NAV_SECTIONS.map((section) => `
    <div class="nav-section">
      <div class="nav-section-header">${esc(section.label)}</div>
      ${section.pages.map((p) =>
        `<a class="nav-item" data-page="${esc(p.id)}" href="#${esc(p.id)}">
          <span class="nav-icon">${svgIcon(p.icon, 16)}</span>
          <span>${esc(p.label)}</span>
          <span class="nav-status"></span>
        </a>`
      ).join("")}
    </div>
  `).join("");

  navEl.addEventListener("click", (e) => {
    const item = e.target.closest(".nav-item");
    if (item) {
      e.preventDefault();
      navigate(item.dataset.page);
    }
  });

  window.addEventListener("hashchange", () => {
    const hash = window.location.hash.slice(1) || "dashboard";
    if (hash !== currentPage) navigate(hash);
  });

  const startPage = window.location.hash.slice(1) || "dashboard";
  navigate(startPage);
  _updateThemeToggle();
  // Hold the splash screen until every preload section has settled
  // (success or error), so users see the loading state through a full
  // cold start instead of a half-rendered dashboard.
  //
  // Belt-and-suspenders: also enforce a maximum 60s splash duration so
  // a single hung endpoint can't strand the user behind the splash.
  const preloadPromise = preloadProgressive();
  const safetyTimeout = new Promise((resolve) => setTimeout(resolve, 60000));
  Promise.race([preloadPromise, safetyTimeout]).then(hideSplash);
  // WebSocket is started inside preloadProgressive() after dashboard loads
}

document.addEventListener("DOMContentLoaded", init);
