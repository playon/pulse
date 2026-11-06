import { accessIdentity } from "./access.js";
import { handleAgentReleases, handleAgentTarget } from "./agent-target.js";

const UNIT_COLUMNS = [
  "venue_id", "vpu_name", "model", "pulse_version",
  "channel", "readiness_status", "readiness_blockers", "readiness_risks",
  "first_seen", "first_seen_et", "last_seen", "last_seen_et", "run_count",
  "monitor_posts", "last_launch", "last_launch_et",
];
const CHECKIN_COLUMNS = [
  "received_at", "received_at_et", "sent_at", "sent_at_et", "hostname", "serial_number", "venue_id", "vpu_name",
  "model", "pulse_version", "channel", "readiness_status", "readiness_policy",
  "readiness_blockers", "readiness_risks", "country", "source", "checkin_id",
];

export async function handleAdmin(request, env) {
  // The one write: the agent target, for Pulse Vitals (PV-85). It does its own
  // Access check and its own editor check. So does the read-only list of
  // published agent builds the target dialog picks from.
  const path = new URL(request.url).pathname;
  if (path === "/agent-target") return handleAgentTarget(request, env);
  if (path === "/agent-releases" || path.startsWith("/agent-releases/")) return handleAgentReleases(request, env);
  if (request.method !== "GET") return new Response("Method not allowed", { status: 405 });
  const who = await accessIdentity(request, env);
  if (!who) return new Response("Forbidden", { status: 403 });

  const url = new URL(request.url);
  switch (url.pathname) {
    case "/":
      return page(env);
    case "/units.csv": {
      const { results } = await env.DB.prepare(
        `SELECT ${UNIT_COLUMNS.join(", ")} FROM units ORDER BY last_seen DESC`,
      ).all();
      return csv("pulse-units.csv", UNIT_COLUMNS, results);
    }
    case "/checkins.csv": {
      const days = clamp(Number.parseInt(url.searchParams.get("days"), 10) || 30, 1, 3650);
      const since = new Date(Date.now() - days * 86400 * 1000).toISOString();
      const { results } = await env.DB.prepare(
        `SELECT ${CHECKIN_COLUMNS.join(", ")} FROM checkins_et WHERE received_at >= ? ORDER BY received_at DESC`,
      ).bind(since).all();
      return csv(`pulse-checkins-${days}d.csv`, CHECKIN_COLUMNS, results);
    }
    default:
      return new Response("Not found", { status: 404 });
  }
}

async function page(env) {
  const now = Date.now();
  const iso = (ms) => new Date(now - ms).toISOString();
  const [units, stats] = await Promise.all([
    env.DB.prepare(
      "SELECT venue_id, vpu_name, model, pulse_version, channel, readiness_status, first_seen, last_seen, run_count FROM units ORDER BY last_seen DESC",
    ).all(),
    env.DB.prepare(
      "SELECT (SELECT COUNT(*) FROM checkins WHERE received_at >= ?) AS day, (SELECT COUNT(*) FROM checkins WHERE received_at >= ?) AS week, (SELECT MAX(received_at) FROM checkins) AS last",
    ).bind(iso(86400e3), iso(7 * 86400e3)).first(),
  ]);
  const rows = units.results
    .map((u) => `<tr>${[
      u.vpu_name, u.venue_id, u.model, u.pulse_version, u.channel,
      u.readiness_status, eastern(u.first_seen), eastern(u.last_seen), u.run_count,
    ].map((v) => `<td>${esc(v)}</td>`).join("")}</tr>`)
    .join("");

  const html = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pulse Check-ins</title>
<style>
:root{--bg:#fff;--fg:#1a1d21;--muted:#5f6670;--line:#e3e6ea;--head:#f5f6f8}
@media (prefers-color-scheme:dark){:root{--bg:#15171a;--fg:#e8eaed;--muted:#9aa1ab;--line:#2b2f35;--head:#1d2024}}
body{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif}
h1{font-size:18px;margin:0 0 4px} p{margin:0 0 12px;color:var(--muted)}
a{color:inherit} .wrap{overflow-x:auto;border:1px solid var(--line);border-radius:6px}
table{border-collapse:collapse;width:100%;white-space:nowrap}
th,td{padding:6px 10px;border-bottom:1px solid var(--line);text-align:left}
th{background:var(--head);position:sticky;top:0;font-weight:600}
td:last-child,th:last-child{text-align:right}
</style></head><body>
<h1>Pulse check-ins</h1>
<p>${esc(units.results.length)} units &middot; ${esc(stats.day)} check-ins in 24 h &middot; ${esc(stats.week)} in 7 days &middot; last received ${esc(eastern(stats.last) || "never")}
&middot; <a href="/units.csv">units.csv</a> &middot; <a href="/checkins.csv?days=30">checkins.csv (30 days)</a></p>
<div class="wrap"><table><thead><tr>
<th>VPU name</th><th>Venue</th><th>Model</th><th>Pulse</th><th>Channel</th><th>Readiness</th><th>First seen</th><th>Last seen</th><th>Runs</th>
</tr></thead><tbody>${rows}</tbody></table></div>
</body></html>`;
  return new Response(html, {
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
      "Cache-Control": "no-store",
    },
  });
}

function csv(filename, columns, rows) {
  const lines = [columns.join(",")];
  for (const r of rows) lines.push(columns.map((c) => csvCell(r[c])).join(","));
  return new Response(lines.join("\r\n") + "\r\n", {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="${filename}"`,
      "Cache-Control": "no-store",
    },
  });
}

// VPU-supplied text lands in Excel/Sheets, so neutralise formula prefixes.
function csvCell(v) {
  if (v === null || v === undefined) return "";
  let s = String(v);
  if (/^[=+\-@\t\r]/.test(s)) s = "'" + s;
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function esc(v) {
  if (v === null || v === undefined) return "";
  return String(v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

// Eastern time, the zone the team works in: "2026-10-14 10:33 EDT".
const EASTERN = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit",
  hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZoneName: "short",
});
function eastern(iso) {
  const d = iso ? new Date(iso) : null;
  if (!d || Number.isNaN(d.getTime())) return "";
  const p = Object.fromEntries(EASTERN.formatToParts(d).map((x) => [x.type, x.value]));
  return `${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute} ${p.timeZoneName}`;
}

function clamp(n, lo, hi) {
  return Math.min(hi, Math.max(lo, n));
}
