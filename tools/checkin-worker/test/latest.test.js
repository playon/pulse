// unit_latest must say exactly what the views say (src/latest.js, PV-26).
// Random check-in streams go through ingest; then every unit's row is
// compared with units, unit_status and events, field by field. The same
// comparison runs after a full rebuild, and the migration file must match its
// generator.
import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import worker from "../src/index.js";
import { fakeD1 } from "./fake-d1.js";
import { rebuildLatest } from "../src/latest.js";
import { migration0015 } from "../scripts/gen-0015.mjs";

let env;
beforeEach(() => {
  env = { ROLE: "ingest", DB: fakeD1() };
});

function post(checkins) {
  return worker.fetch(new Request("https://w.test/checkin", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ checkins }),
  }), env);
}

// Small seeded PRNG, so a failure reproduces.
function rng(seed) {
  let s = seed >>> 0;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 2 ** 32);
}

const UNITS = [
  { venueId: "V1", vpuName: "Gym" }, { venueId: "V2", vpuName: "Field" },
  { venueId: null, vpuName: "Nameless" }, { venueId: "V4", vpuName: "Arena" },
];

function stream(seed, n) {
  const r = rng(seed);
  const pick = (a) => a[Math.floor(r() * a.length)];
  const out = [];
  for (let i = 0; i < n; i++) {
    const u = pick(UNITS);
    // Times collide on purpose (whole minutes), and run out of order.
    const sentAt = new Date(Date.UTC(2026, 9, 14, 18, Math.floor(r() * 90))).toISOString();
    const base = { checkinId: `aaaaaaaa-0000-0000-0000-${String(seed * 1000 + i).padStart(12, "0")}`, sentAt,
                   venueId: u.venueId, vpuName: u.vpuName };
    const kind = pick(["launch", "launch", "report", "report", "heartbeat", "paused", "ev-start", "ev-update", "ev-end"]);
    const status = pick(["PASS", "WARN", "FAIL"]);
    let c;
    if (kind === "launch") {
      c = { ...base, reason: pick([undefined, "startup"]), model: pick(["S2", "Z2"]), pulseVersion: pick(["1.4.1", "1.5.0"]),
            channel: "production", readiness: { status, policyVersion: "1", blockers: status === "FAIL" ? ["x"] : [], risks: [] } };
    } else if (kind === "report") {
      c = { ...base, reason: pick(["periodic", "state-change"]), model: "S2", pulseVersion: "1.5.0",
            telemetry: { schema: "pulse.telemetry/v1", status, headline: status === "PASS" ? null : `h-${i}`,
                         blockers: status === "FAIL" ? [`b-${i}`] : [], pixellotVersion: "5.37.3",
                         network: { streamingPath: pick(["zixi-2088", "rtmp-1935"]) },
                         cameras: { systemType: "S2", expected: 2, detected: pick([1, 2]) },
                         scoreboard: { source: "scoreconnect", ok: r() > 0.5 } } };
    } else if (kind === "heartbeat") {
      c = { ...base, reason: "heartbeat", status: "PASS" };
    } else if (kind === "paused") {
      c = { ...base, reason: "paused", pulseVersion: "1.5.0" };
    } else {
      const eventId = pick(["6ad018b2ec5d0313d04118a6", "aaaaaaaabbbbbbbbccccdddd", "DAILYTEST20261014"]);
      const state = kind === "ev-end" ? "ended" : pick(["on-air", "connecting", "stream-failing", "camera-degraded"]);
      c = { ...base, reason: kind === "ev-start" ? "event-start" : kind === "ev-update" ? "event-update" : "event-end",
            pulseVersion: "1.5.0",
            event: { schema: "pulse.event/v1", eventId, kind: eventId.startsWith("DAILYTEST") ? "daily-test" : "event",
                     state, wentOnAir: r() > 0.4, eventName: `gam${i} Football`, path: "zixi-2088",
                     reason: state === "ended" ? pick([null, "stream-failing"]) : null,
                     warnings: r() > 0.5 ? ["off-air-gaps"] : [] } };
    }
    // The fleet agent's posts carry its version, now and then with an update outcome (PV-49).
    if (kind !== "launch" && r() < 0.8) c.agentVersion = pick(["0.1.0", "0.2.0", "0.3.0"]);
    if (kind !== "launch" && r() < 0.2) {
      c.agentUpdate = { status: pick(["applied", "failed", "rolled-back"]), version: pick(["0.2.0", "0.3.0"]),
                        error: r() < 0.5 ? `e-${i}` : undefined };
    }
    out.push(c);
    if (r() < 0.1) out.push({ ...c });              // a replay of the same id: a duplicate
  }
  return out;
}

const UNIT_COLS = ["venue_id", "vpu_name", "model", "pulse_version", "channel", "readiness_status",
  "readiness_blockers", "readiness_risks", "first_seen", "last_seen", "run_count", "monitor_posts", "last_launch"];
const STATUS_MAP = {
  vpu_name: "tel_vpu_name", venue_id: "tel_venue_id", model: "tel_model", last_seen: "last_seen", last_kind: "last_kind",
  last_full_report: "tel_at", status: "status", status_since: "status_since", headline: "headline",
  blockers: "blockers", internet_reachable: "internet_reachable", streaming_path: "streaming_path",
  ports_failed: "ports_failed", system_type: "system_type", cameras_detected: "cameras_detected",
  cameras_expected: "cameras_expected", scoreboard_source: "scoreboard_source", scoreboard_ok: "scoreboard_ok",
  pixellot_version: "pixellot_version", pulse_version: "tel_pulse_version", telemetry: "telemetry",
};

function compare(label) {
  const db = env.DB.raw;
  // The views expose venue_id and vpu_name only; these streams have no hostname or serial.
  const key = "COALESCE(venue_id, vpu_name)";
  const latest = new Map(db.prepare("SELECT * FROM unit_latest").all().map((r) => [r.unit_key, r]));
  const units = db.prepare(`SELECT *, ${key} AS k FROM units`).all();
  assert.equal(latest.size, units.length, `${label}: one unit_latest row per unit`);
  for (const u of units) {
    const l = latest.get(u.k);
    assert.ok(l, `${label}: ${u.k} missing`);
    for (const c of UNIT_COLS) assert.deepEqual(l[c], u[c], `${label}: ${u.k}.${c}`);
  }
  for (const s of db.prepare(`SELECT *, ${key} AS k FROM unit_status`).all()) {
    const l = latest.get(s.k) || latest.get(s.vpu_name);
    for (const [view, col] of Object.entries(STATUS_MAP)) assert.deepEqual(l[col], s[view], `${label}: ${s.k}.${view}`);
  }
  // The newest event post per unit, as Vitals ranks the events view.
  // Two events can share the newest minute (the streams collide times on
  // purpose). unit_latest breaks that tie by check-in id, which the view
  // doesn't expose, so any event at the newest time is a valid pick: check
  // unit_latest chose one of them, then compare it field by field.
  const top = db.prepare(`SELECT * FROM (SELECT *, RANK() OVER (PARTITION BY unit_key ORDER BY updated_at DESC) rk
                          FROM events) WHERE rk = 1`).all();
  const tied = new Map();
  for (const e of top) tied.set(e.unit_key, [...(tied.get(e.unit_key) || []), e]);
  for (const [unitKey, events] of tied) {
    const l = latest.get(unitKey);
    const e = events.find((x) => x.event_id === l.ev_id);
    assert.ok(e, `${label}: ${unitKey} event id ${l.ev_id} is one of the newest (${events.map((x) => x.event_id)})`);
    assert.equal(l.ev_at, e.updated_at, `${label}: ${e.unit_key} event time`);
    assert.equal(l.ev_id, e.event_id, `${label}: ${e.unit_key} event id`);
    assert.equal(l.ev_state, e.state, `${label}: ${e.unit_key} event state`);
    assert.equal(l.ev_kind, e.last_kind);
    assert.equal(l.ev_on_air, e.went_on_air);
    assert.equal(l.ev_why, e.why_not_on_air);
    assert.equal(l.ev_name, e.event_name);
    assert.equal(l.ev_warnings, e.warnings);
    assert.equal(l.ev_type, e.kind === "daily-test" ? "daily-test" : "event", `${label}: ${e.unit_key} event type`);
  }
  // No view carries the agent groups: check them against the newest check-in
  // that has them, by (sent time, id), straight from checkins.
  const newest = (cond, cols) => db.prepare(`SELECT ${key} AS k, ${cols} FROM (
      SELECT *, ROW_NUMBER() OVER (PARTITION BY ${key} ORDER BY COALESCE(sent_at, received_at) DESC, id DESC) rn
      FROM checkins WHERE ${cond}) WHERE rn = 1`).all();
  const agents = newest("agent_version IS NOT NULL", "agent_version");
  assert.ok(agents.length > 0, `${label}: the stream has agent posts`);
  for (const a of agents) assert.equal(latest.get(a.k).agent_version, a.agent_version, `${label}: ${a.k} agent version`);
  for (const u of newest("agent_update_status IS NOT NULL", "agent_update_status, agent_update_version, agent_update_error")) {
    const l = latest.get(u.k);
    assert.deepEqual([l.agent_update_status, l.agent_update_version, l.agent_update_error],
                     [u.agent_update_status, u.agent_update_version, u.agent_update_error], `${label}: ${u.k} agent update`);
  }
  const withAgent = db.prepare("SELECT COUNT(*) n FROM unit_latest WHERE agent_version IS NOT NULL").get().n;
  assert.equal(withAgent, agents.length, `${label}: agent_version only where an agent posted`);
}

for (const seed of [1, 2, 3, 4, 5, 6, 7, 8]) {
  test(`unit_latest agrees with the views (seed ${seed}), kept by ingest and after a rebuild`, async () => {
    const all = stream(seed, 120);
    for (let i = 0; i < all.length; i += 7) {          // in batches, as clients send them
      const res = await post(all.slice(i, i + 7));
      assert.equal(res.status, 200);
    }
    compare("ingest");
    await rebuildLatest(env);
    compare("rebuild");
  });
}

test("sheet-imported rows count their run count and first seen, after a rebuild", async () => {
  env.DB.raw.exec(`INSERT INTO checkins (checkin_id, received_at, sent_at, venue_id, vpu_name, pulse_version, channel, source, raw)
    VALUES ('sheet-import-SN1', '2026-10-13T20:56:55Z', '2026-09-01T10:00:00.000Z', 'V1', 'Gym', 'web-v1.3.1',
            'production', 'sheet-import', '{"runCount":40,"firstSeen":"2026-06-01T09:00:00.000Z"}')`);
  await post(stream(9, 30));
  await rebuildLatest(env);
  compare("sheet");
  const l = env.DB.raw.prepare("SELECT run_count, first_seen FROM unit_latest WHERE unit_key = 'V1'").get();
  assert.equal(l.first_seen, "2026-06-01T09:00:00.000Z");
  assert.ok(l.run_count >= 40);
});

test("a failed unit_latest update never fails the check-in", async () => {
  env.DB.raw.exec("DROP TABLE unit_latest");
  const res = await post(stream(10, 3));
  const body = await res.json();
  assert.equal(body.ok, true);
  assert.ok(body.results.every((r) => r.status === "inserted" || r.status === "duplicate"));
});

test("migration 0016 backfills ev_type from the event each row points at", async () => {
  const all = stream(11, 120);
  for (let i = 0; i < all.length; i += 7) await post(all.slice(i, i + 7));
  const db = env.DB.raw;
  const want = db.prepare("SELECT unit_key, ev_type FROM unit_latest WHERE ev_row IS NOT NULL ORDER BY unit_key").all();
  assert.ok(want.length > 0, "the stream has events");
  db.exec("UPDATE unit_latest SET ev_type = NULL");
  const sql = readFileSync(new URL("../migrations/0016_unit_latest_event_type.sql", import.meta.url), "utf8");
  db.exec(sql.slice(sql.indexOf("UPDATE unit_latest")));
  assert.deepEqual(db.prepare("SELECT unit_key, ev_type FROM unit_latest WHERE ev_row IS NOT NULL ORDER BY unit_key").all(), want);
  assert.equal(db.prepare("SELECT COUNT(*) n FROM unit_latest WHERE ev_row IS NULL AND ev_type IS NOT NULL").get().n, 0);
});

test("migration 0015 is exactly its generator's output", () => {
  const file = readFileSync(new URL("../migrations/0015_unit_latest.sql", import.meta.url), "utf8");
  assert.equal(file, migration0015());
});
