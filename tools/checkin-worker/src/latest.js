// unit_latest: one row per unit, kept current as check-ins arrive (PV-26).
//
// The units, unit_status and events views recompute from every check-in on
// each read, so a fleet read costs several passes over the whole table: about
// 18 rows read per stored check-in. On 2026-10-15 a local Vitals refreshing
// each minute against the live database spent D1's 5M free daily row reads in
// under an hour. This table answers the same questions in one row per unit.
//
// One statement does all the work: an upsert whose proposed row is computed
// from a single check-in. Ingest runs it for each check-in it just stored (one
// row read through the checkin_id index), and the backfill / daily rebuild
// runs the same statement over every check-in, ordered by id. Because both use
// the same SQL, the table can't drift from what ingest does. The rules mirror
// the views (migrations 0008, 0010, 0012) exactly; test/latest.test.js checks
// that they agree on random check-in streams.
//
// Each group of columns keeps the (time, id) of the check-in it came from, and
// a later check-in replaces a group only if it is newer by that order. So a
// replayed backlog never outranks a newer report, as in the views.

const UNIT_KEY = "COALESCE(c.venue_id, c.vpu_name, c.hostname, c.serial_number)";
const SEEN = "COALESCE(c.sent_at, c.received_at)";
const HEARD = "CASE WHEN c.source = 'sheet-import' THEN COALESCE(c.sent_at, c.received_at) ELSE c.received_at END";
const LAUNCHES = `CASE
    WHEN c.source = 'sheet-import' THEN COALESCE(CAST(json_extract(c.raw, '$.runCount') AS INTEGER), 1)
    WHEN c.telemetry IS NULL AND (c.reason IS NULL OR c.reason = 'startup') THEN 1
    ELSE 0 END`;
const MONITOR_POST = "CASE WHEN c.reason IN ('periodic', 'state-change', 'heartbeat') THEN 1 ELSE 0 END";
const FIRST_AT = "CASE WHEN c.source = 'sheet-import' THEN json_extract(c.raw, '$.firstSeen') ELSE COALESCE(c.sent_at, c.received_at) END";

// Column groups replaced together, each when its condition holds for the
// check-in and the check-in is the newest such for the unit.
const GROUPS = [
  {
    name: "detail", when: "c.pulse_version IS NOT NULL",
    cols: { venue_id: "c.venue_id", vpu_name: "c.vpu_name", model: "c.model",
            pulse_version: "c.pulse_version", channel: "c.channel" },
  },
  {
    name: "verdict",
    when: "COALESCE(c.tel_status, c.readiness_status) IS NOT NULL AND c.reason IS NOT 'heartbeat'",
    cols: { readiness_status: "COALESCE(c.tel_status, c.readiness_status)",
            readiness_blockers: "c.readiness_blockers", readiness_risks: "c.readiness_risks" },
  },
  {
    name: "kind", when: "1",
    cols: { last_kind: "c.reason" },
  },
  {
    name: "tel", when: "c.telemetry IS NOT NULL",
    cols: {
      tel_venue_id: "c.venue_id", tel_vpu_name: "c.vpu_name", tel_model: "c.model",
      status: "c.tel_status", status_since: "c.tel_status_since", headline: "c.tel_headline",
      blockers: "c.tel_blockers", internet_reachable: "c.tel_internet_reachable",
      streaming_path: "c.tel_streaming_path", ports_failed: "c.tel_ports_failed", ip: "c.tel_ip",
      subnet_mask: "c.tel_subnet_mask", gateway: "c.tel_gateway", dns1: "c.tel_dns1", dns2: "c.tel_dns2",
      dhcp: "c.tel_dhcp", mac: "c.tel_mac", system_type: "c.tel_system_type",
      cameras_detected: "c.tel_cameras_detected", cameras_expected: "c.tel_cameras_expected",
      cameras_slow: "c.tel_cameras_slow", services_down: "c.tel_services_down",
      scoreboard_source: "c.tel_scoreboard_source", scoreboard_ok: "c.tel_scoreboard_ok",
      last_boot: "c.tel_last_boot", unexpected_shutdowns_7d: "c.tel_unexpected_7d",
      pixellot_version: "c.tel_pixellot_version", tel_pulse_version: "c.pulse_version",
      telemetry: "c.telemetry",
    },
  },
  {
    name: "ev", when: "c.event_id IS NOT NULL",
    cols: {
      ev_id: "c.event_id", ev_state: "c.event_state", ev_kind: "c.reason", ev_on_air: "c.event_on_air",
      ev_why: "c.event_reason", ev_path: "json_extract(c.event, '$.path')",
      ev_name: "json_extract(c.event, '$.eventName')", ev_warnings: "json_extract(c.event, '$.warnings')",
    },
  },
];

// Running totals and extremes over every check-in of the unit.
const AGG = {
  run_count: { expr: LAUNCHES, merge: (o, n) => `${o} + ${n}` },
  monitor_posts: { expr: MONITOR_POST, merge: (o, n) => `${o} + ${n}` },
  first_seen: { expr: FIRST_AT, merge: (o, n) => `MIN(COALESCE(${o}, ${n}), COALESCE(${n}, ${o}))` },
  last_seen: { expr: HEARD, merge: (o, n) => `MAX(COALESCE(${o}, ${n}), COALESCE(${n}, ${o}))` },
  last_launch: { expr: `CASE WHEN (${LAUNCHES}) > 0 THEN ${SEEN} END`,
                 merge: (o, n) => `MAX(COALESCE(${o}, ${n}), COALESCE(${n}, ${o}))` },
};

function columns() {
  const cols = ["unit_key", ...Object.keys(AGG)];
  for (const g of GROUPS) cols.push(`${g.name}_at`, `${g.name}_row`, ...Object.keys(g.cols));
  return cols;
}

function proposed() {
  const out = [`${UNIT_KEY} AS unit_key`];
  for (const [k, a] of Object.entries(AGG)) out.push(`${a.expr} AS ${k}`);
  for (const g of GROUPS) {
    out.push(`CASE WHEN ${g.when} THEN ${SEEN} END AS ${g.name}_at`);
    out.push(`CASE WHEN ${g.when} THEN c.id END AS ${g.name}_row`);
    for (const [k, expr] of Object.entries(g.cols)) out.push(`CASE WHEN ${g.when} THEN ${expr} END AS ${k}`);
  }
  return out;
}

function updates() {
  const set = [];
  for (const [k, a] of Object.entries(AGG)) set.push(`${k} = ${a.merge(`unit_latest.${k}`, `excluded.${k}`)}`);
  for (const g of GROUPS) {
    const at = `${g.name}_at`;
    const row = `${g.name}_row`;
    const newer = `(excluded.${at} IS NOT NULL AND (unit_latest.${at} IS NULL OR excluded.${at} > unit_latest.${at}
        OR (excluded.${at} = unit_latest.${at} AND excluded.${row} > unit_latest.${row})))`;
    for (const k of [at, row, ...Object.keys(g.cols)]) {
      set.push(`${k} = CASE WHEN ${newer} THEN excluded.${k} ELSE unit_latest.${k} END`);
    }
  }
  return set;
}

// `where` picks the check-ins: one by id for ingest, all of them (ordered) to
// rebuild. SQLite applies the upsert row by row, so a rebuild is a replay.
export function upsertSql(where) {
  return `INSERT INTO unit_latest (${columns().join(", ")})
SELECT ${proposed().join(",\n       ")}
FROM checkins c
WHERE ${UNIT_KEY} IS NOT NULL AND (${where})
ORDER BY c.id
ON CONFLICT (unit_key) DO UPDATE SET
  ${updates().join(",\n  ")}`;
}

export const UPSERT_ONE = upsertSql("c.checkin_id = ?");
export const REBUILD = ["DELETE FROM unit_latest", upsertSql("1")];

// The table's DDL, for the migration generator (scripts/gen-0015.mjs).
export function tableSql() {
  const types = { run_count: "INTEGER NOT NULL DEFAULT 0", monitor_posts: "INTEGER NOT NULL DEFAULT 0" };
  const cols = columns().map((c) => (c === "unit_key" ? "unit_key TEXT PRIMARY KEY" : `${c} ${types[c] || ""}`.trim()));
  return `CREATE TABLE unit_latest (\n  ${cols.join(",\n  ")}\n)`;
}

// After ingest stores a batch: bring unit_latest up to date for the
// check-ins that were new. Failure is logged, never surfaced: the check-ins
// are stored, and the daily rebuild repairs the table.
export async function updateLatest(env, checkinIds) {
  if (!checkinIds.length) return;
  try {
    await env.DB.batch(checkinIds.map((id) => env.DB.prepare(UPSERT_ONE).bind(id)));
  } catch (e) {
    console.error("unit_latest update failed", e && e.message);
  }
}

export async function rebuildLatest(env) {
  await env.DB.batch(REBUILD.map((sql) => env.DB.prepare(sql)));
}
