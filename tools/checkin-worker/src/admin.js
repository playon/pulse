import { accessIdentity } from "./access.js";

const UNIT_COLUMNS = [
  "hostname", "serial_number", "venue_id", "vpu_name", "model", "pulse_version",
  "channel", "readiness_status", "readiness_blockers", "readiness_risks",
  "first_seen", "last_seen", "run_count",
];
const CHECKIN_COLUMNS = [
  "received_at", "sent_at", "hostname", "serial_number", "venue_id", "vpu_name",
  "model", "pulse_version", "channel", "readiness_status", "readiness_policy",
  "readiness_blockers", "readiness_risks", "country", "source", "checkin_id",
];

export async function handleAdmin(request, env) {
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
        `SELECT ${CHECKIN_COLUMNS.join(", ")} FROM checkins WHERE received_at >= ? ORDER BY received_at DESC`,
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
      "SELECT hostname, serial_number, venue_id, vpu_name, pulse_version, channel, readiness_status, first_seen, last_seen, run_count FROM units ORDER BY last_seen DESC",
    ).all(),
    env.DB.prepare(
      "SELECT (SELECT COUNT(*) FROM checkins WHERE received_at >= ?) AS day, (SELECT COUNT(*) FROM checkins WHERE received_at >= ?) AS week, (SELECT MAX(received_at) FROM checkins) AS last",
    ).bind(iso(86400e3), iso(7 * 86400e3)).first(),
  ]);
  const rows = units.results
    .map((u) => `<tr>${[
      u.hostname, u.vpu_name, u.venue_id, u.serial_number, u.pulse_version, u.channel,
      u.readiness_status, short(u.first_seen), short(u.last_seen), u.run_count,
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
<p>${esc(units.results.length)} units &middot; ${esc(stats.day)} check-ins in 24 h &middot; ${esc(stats.week)} in 7 days &middot; last received ${esc(short(stats.last) || "never")}
&middot; <a href="/units.csv">units.csv</a> &middot; <a href="/checkins.csv?days=30">checkins.csv (30 days)</a></p>
<div class="wrap"><table><thead><tr>
<th>Hostname</th><th>VPU name</th><th>Venue</th><th>Serial</th><th>Pulse</th><th>Channel</th><th>Readiness</th><th>First seen</th><th>Last seen</th><th>Runs</th>
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

function short(iso) {
  return iso ? String(iso).slice(0, 16).replace("T", " ") : "";
}

function clamp(n, lo, hi) {
  return Math.min(hi, Math.max(lo, n));
}
