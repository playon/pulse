import { updateLatest } from "./latest.js";
// No write key (Ian, 2026-10-13). Pulse ships from a public repo, so any key in
// it was readable by anyone and only looked like protection (Snyk flagged it,
// PR #229). What protects the table is what this file enforces: the per-IP rate
// limit, the body/batch size caps, and field-by-field validation that drops
// anything malformed. Older builds still send a "secret" field; it is ignored.
// Real per-unit auth comes with the Unity/DevOps transport.

const MAX_BODY_BYTES = 64 * 1024;
const MAX_BATCH = 50;
const MAX_FIELD = 128;
const MAX_CODES = 50;
const FUTURE_SKEW_MS = 10 * 60 * 1000;
const CHECKIN_ID_RE = /^[A-Za-z0-9-]{8,64}$/;
const MAX_EVENTS = 25;
// "paused": the hourly identity-only line from a monitor that fleet control
// has switched off (monitor_control below).
// "event-start" / "event-update" / "event-end": the monitor's in-event reader
// (event_watch.py), which reads Pixellot's own logs while VPU.exe runs.
const REASONS = new Set(["startup", "periodic", "state-change", "heartbeat", "paused",
                         "event-start", "event-update", "event-end"]);
const EVENT_SCHEMA = "pulse.event/v1";
const MAX_EVENT_BYTES = 4 * 1024;
const EVENT_STATES = new Set(["on-air", "connecting", "stream-failing", "restart-loop", "camera-link-down", "camera-degraded", "ended"]);
const PASSES = new Set(["full", "partial"]);
const STATUSES = new Set(["PASS", "WARN", "FAIL"]);
const PATHS = new Set(["zixi-2088", "zixi-443", "rtmp-1935", "blocked"]);
const TELEMETRY_SCHEMA = "pulse.telemetry/v1";
const MAX_TELEMETRY_BYTES = 16 * 1024;
// The fleet agent's update outcome (agentUpdate.status), PV-49.
const UPDATE_STATUSES = new Set(["applied", "failed", "rolled-back"]);
// A pinned agent target. The agent builds a URL from the version and checks
// the zip against the hash, so both must be exactly this shape.
const TARGET_VERSION_RE = /^\d{1,4}\.\d{1,4}\.\d{1,6}$/;
const SHA256_RE = /^[0-9a-f]{64}$/;

const INSERT_SQL = `
INSERT INTO checkins (
  checkin_id, received_at, sent_at, hostname, serial_number, venue_id, vpu_name,
  model, pulse_version, channel, readiness_status, readiness_policy,
  readiness_blockers, readiness_risks, country, source, raw,
  reason, os_build, ubr, delta_status, delta_prev_status, delta_opened,
  delta_resolved, monitor_pass, monitor_seconds, monitor_ps_runs, event_live,
  tel_status, tel_status_since, tel_headline, tel_blocker_count, tel_risk_count,
  tel_pixellot_version, tel_cameras_expected, tel_cameras_detected,
  tel_streaming_path, telemetry,
  tel_system_type, tel_blockers, tel_cameras_slow, tel_ports_failed,
  tel_services_down, tel_scoreboard_source, tel_scoreboard_ok, tel_ip,
  tel_subnet_mask, tel_gateway, tel_dns1, tel_dns2, tel_dhcp, tel_last_boot,
  tel_unexpected_7d, tel_reboot_pending, tel_poe_draw_w, tel_clock_offset_s,
  tel_mac, tel_camera_macs, tel_internet_reachable,
  monitor_cpu_seconds, monitor_cpu_percent, monitor_processes, monitor_memory_peak_mb,
  event_id, event_state, event_reason, event_on_air, event,
  agent_version, agent_update_status, agent_update_version, agent_update_error
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
          ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
          ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
          ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
          ?, ?, ?, ?, ?,
          ?, ?, ?, ?)
ON CONFLICT (checkin_id) DO NOTHING`;

export async function handleIngest(request, env) {
  const url = new URL(request.url);
  if (url.pathname === "/health" && request.method === "GET") {
    return Response.json({ ok: true });
  }
  if (url.pathname !== "/checkin") return notFound();
  if (request.method !== "POST") {
    return Response.json({ ok: false, error: "method" }, { status: 405 });
  }
  if (env.INGEST_LIMITER) {
    const key = request.headers.get("CF-Connecting-IP") || "unknown";
    const { success } = await env.INGEST_LIMITER.limit({ key });
    if (!success) return Response.json({ ok: false, error: "rate-limited" }, { status: 429 });
  }

  const declared = Number(request.headers.get("Content-Length") || 0);
  if (declared > MAX_BODY_BYTES) return tooLarge();
  const text = await request.text();
  if (new TextEncoder().encode(text).length > MAX_BODY_BYTES) return tooLarge();

  let body;
  try {
    body = JSON.parse(text);
  } catch {
    return badRequest("json");
  }
  if (!body || typeof body !== "object" || Array.isArray(body)) return badRequest("shape");
  if (!Array.isArray(body.checkins) || body.checkins.length === 0) return badRequest("checkins");
  if (body.checkins.length > MAX_BATCH) return badRequest("batch-too-large");

  const receivedAt = new Date().toISOString();
  // The Apps Script sheet forwards the check-ins that reached it because a
  // school filter blocked this Worker. Those arrive from Google, so the
  // country would be Google's, not the school's: leave it empty. The header
  // only labels the row; it grants nothing.
  const relayed = request.headers.get("X-Pulse-Relay") === "sheet";
  const source = relayed ? "sheet-relay" : "pulse";
  const country = relayed ? null : (request.cf && request.cf.country) || null;
  const results = [];
  const statements = [];
  const slots = [];
  let unit = null;

  for (const item of body.checkins) {
    const row = normalize(item, receivedAt);
    if (!row) {
      results.push({ checkinId: idOf(item), status: "invalid" });
      continue;
    }
    unit = unit || row.venueId || row.vpuName;
    slots.push(results.length);
    results.push({ checkinId: row.checkinId, status: null });
    statements.push(
      env.DB.prepare(INSERT_SQL).bind(
        row.checkinId, receivedAt, row.sentAt, row.hostname, row.serialNumber,
        row.venueId, row.vpuName, row.model, row.pulseVersion, row.channel,
        row.readinessStatus, row.readinessPolicy, row.blockers, row.risks,
        country, source, row.raw,
        row.reason, row.osBuild, row.ubr, row.deltaStatus, row.deltaPrevStatus,
        row.opened, row.resolved, row.monitorPass, row.monitorSeconds,
        row.monitorPsRuns, row.eventLive,
        row.tel.status, row.tel.since, row.tel.headline, row.tel.blockers,
        row.tel.risks, row.tel.pixellotVersion, row.tel.camerasExpected,
        row.tel.camerasDetected, row.tel.streamingPath, row.tel.json,
        row.tel.systemType, row.tel.blockerTitles, row.tel.camerasSlow,
        row.tel.portsFailed, row.tel.servicesDown, row.tel.scoreboardSource,
        row.tel.scoreboardOk, row.tel.ip, row.tel.subnetMask, row.tel.gateway,
        row.tel.dns1, row.tel.dns2, row.tel.dhcp, row.tel.lastBoot,
        row.tel.unexpected7d, row.tel.rebootPending, row.tel.poeDrawW,
        row.tel.clockOffsetS, row.tel.mac, row.tel.cameraMacs, row.tel.internetReachable,
        row.monitorCpuSeconds, row.monitorCpuPercent, row.monitorProcesses, row.monitorMemoryPeakMb,
        row.ev.id, row.ev.state, row.ev.reason, row.ev.onAir, row.ev.json,
        row.agentVersion, row.upd.status, row.upd.version, row.upd.error,
      ),
    );
  }

  if (statements.length) {
    let outcomes;
    try {
      outcomes = await env.DB.batch(statements);
    } catch (e) {
      console.error("d1 batch failed", e && e.message);
      return Response.json({ ok: false, error: "storage" }, { status: 500 });
    }
    outcomes.forEach((res, i) => {
      const changed = res && res.meta && res.meta.changes;
      results[slots[i]].status = changed ? "inserted" : "duplicate";
    });
    // Only newly stored check-ins move unit_latest: a duplicate (a replay of
    // one already stored) must not count twice.
    await updateLatest(env, results.filter((r) => r.status === "inserted").map((r) => r.checkinId));
  }

  const control = await controlFor(env, unit);
  return Response.json(control ? { ok: true, results, control } : { ok: true, results });
}

// Fleet control for the scheduled monitor: the remote off switch, from
// Canopy Leaf's rollout (#leaf-deploy-coordination). Its memory leak took four
// months of hand-edited cron jobs to find; here one row stops the monitor, or
// one collector, on a unit or the whole fleet. A unit's own row decides its
// mode; skip lists add up. Any failure leaves control out of the reply, and
// Pulse then keeps the last instruction it had.
//
// It also carries the agent build a unit should run (PV-49), as agent:
// { version, sha256 }. A unit's own row wins when it sets a version (a canary,
// or a unit held back); otherwise the fleet row's applies. The pair comes from
// one row, and a malformed one means no target at all rather than the fleet's,
// so a unit that was held back is never moved by a typo. No target: the agent
// stays on what it runs.
async function controlFor(env, unit) {
  try {
    const { results } = await env.DB.prepare(
      "SELECT scope, mode, skip, agent_version, agent_sha256 FROM monitor_control WHERE scope = 'fleet' OR scope = ?",
    ).bind(unit || "").all();
    if (!results || !results.length) return { mode: "on", skip: [] };
    const fleet = results.find((r) => r.scope === "fleet");
    const own = results.find((r) => r.scope !== "fleet");
    const mode = (own || fleet).mode === "off" ? "off" : "on";
    const skip = new Set();
    for (const r of [fleet, own]) {
      if (!r) continue;
      try {
        for (const name of JSON.parse(r.skip || "[]")) if (typeof name === "string" && name) skip.add(name);
      } catch {
        // a malformed skip list in one row never blocks the reply
      }
    }
    const control = { mode, skip: [...skip].slice(0, 50) };
    const pin = [own, fleet].find((r) => r && r.agent_version !== null && r.agent_version !== undefined);
    if (pin && TARGET_VERSION_RE.test(pin.agent_version) && SHA256_RE.test(pin.agent_sha256 || "")) {
      control.agent = { version: pin.agent_version, sha256: pin.agent_sha256 };
    }
    return control;
  } catch (e) {
    console.error("control lookup failed", e && e.message);
    return null;
  }
}

function normalize(item, receivedAt) {
  if (!item || typeof item !== "object" || Array.isArray(item)) return null;
  const checkinId = typeof item.checkinId === "string" ? item.checkinId : "";
  if (!CHECKIN_ID_RE.test(checkinId)) return null;

  const readiness = item.readiness && typeof item.readiness === "object" ? item.readiness : {};
  const delta = item.delta && typeof item.delta === "object" && !Array.isArray(item.delta) ? item.delta : null;
  const mon = item.monitor && typeof item.monitor === "object" && !Array.isArray(item.monitor) ? item.monitor : null;
  const reason = str(item.reason);
  const clean = {
    checkinId,
    sentAt: normalizeTime(item.sentAt, receivedAt),
    hostname: str(item.hostname),
    serialNumber: str(item.serialNumber),
    venueId: str(item.venueId),
    vpuName: str(item.vpuName),
    model: str(item.model),
    pulseVersion: str(item.pulseVersion),
    channel: str(item.channel),
    // A heartbeat is one line: identity plus a top-level "status": "PASS".
    readinessStatus: verdict(readiness.status) || (reason === "heartbeat" ? verdict(item.status) : null),
    readinessPolicy: str(readiness.policyVersion),
    blockers: codes(readiness.blockers),
    risks: codes(readiness.risks),
    reason: REASONS.has(reason) ? reason : null,
    osBuild: str(item.osBuild),
    ubr: str(item.ubr),
    deltaStatus: delta ? str(delta.status) : null,
    deltaPrevStatus: delta ? str(delta.prevStatus) : null,
    opened: delta ? events(delta.opened) : null,
    resolved: delta ? events(delta.resolved) : null,
    monitorPass: mon && PASSES.has(mon.pass) ? mon.pass : null,
    monitorSeconds: mon ? num(mon.seconds, 0, 3600) : null,
    monitorPsRuns: mon ? int(mon.psRuns, 0, 1000) : null,
    monitorCpuSeconds: mon ? num(mon.cpuSeconds, 0, 3600) : null,
    monitorCpuPercent: mon ? num(mon.cpuPercent, 0, 100) : null,
    monitorProcesses: mon ? int(mon.processes, 0, 100000) : null,
    monitorMemoryPeakMb: mon ? num(mon.memoryPeakMb, 0, 65536) : null,
    eventLive: mon && typeof mon.eventLive === "boolean" ? (mon.eventLive ? 1 : 0) : null,
    tel: telemetry(item.telemetry),
    ev: eventDoc(item.event),
    agentVersion: str(item.agentVersion, 64),
    upd: agentUpdate(item.agentUpdate),
  };
  clean.raw = JSON.stringify({
    checkinId: clean.checkinId,
    sentAt: clean.sentAt,
    hostname: clean.hostname,
    serialNumber: clean.serialNumber,
    venueId: clean.venueId,
    vpuName: clean.vpuName,
    model: clean.model,
    pulseVersion: clean.pulseVersion,
    agentVersion: clean.agentVersion,
    channel: clean.channel,
    readiness: {
      status: clean.readinessStatus,
      policyVersion: clean.readinessPolicy,
      blockers: clean.blockers && JSON.parse(clean.blockers),
      risks: clean.risks && JSON.parse(clean.risks),
    },
    reason: clean.reason,
    osBuild: clean.osBuild,
    ubr: clean.ubr,
    delta: delta && {
      status: clean.deltaStatus,
      prevStatus: clean.deltaPrevStatus,
      opened: clean.opened && JSON.parse(clean.opened),
      resolved: clean.resolved && JSON.parse(clean.resolved),
    },
    telemetry: clean.tel.json ? TELEMETRY_SCHEMA : undefined,
    monitor: mon && {
      pass: clean.monitorPass,
      seconds: clean.monitorSeconds,
      psRuns: clean.monitorPsRuns,
      cpuSeconds: clean.monitorCpuSeconds,
      cpuPercent: clean.monitorCpuPercent,
      processes: clean.monitorProcesses,
      memoryPeakMb: clean.monitorMemoryPeakMb,
      eventLive: clean.eventLive === null ? null : clean.eventLive === 1,
    },
    agentUpdate: clean.upd.status ? { status: clean.upd.status, version: clean.upd.version,
                                      error: clean.upd.error } : undefined,
  });
  return clean;
}

const NO_UPDATE = { status: null, version: null, error: null };

// How the agent's last update attempt went: { status, version, error }.
// Kept only with a known status; version is the build it tried to move to.
function agentUpdate(u) {
  if (!u || typeof u !== "object" || Array.isArray(u)) return NO_UPDATE;
  const status = str(u.status);
  if (!UPDATE_STATUSES.has(status)) return NO_UPDATE;
  return { status, version: str(u.version, 64), error: str(u.error, 256) };
}

function str(v, max = MAX_FIELD) {
  if (typeof v === "number" && Number.isFinite(v)) v = String(v);
  if (typeof v !== "string") return null;
  const t = v.trim();
  return t ? t.slice(0, max) : null;
}

// PASS | WARN | FAIL, the same set telemetry.status uses; anything else is null.
function verdict(v) {
  const s = str(v);
  return STATUSES.has(s) ? s : null;
}

function codes(v) {
  if (!Array.isArray(v)) return null;
  const out = v.map((x) => str(x)).filter(Boolean).slice(0, MAX_CODES);
  return JSON.stringify(out);
}

// pulse.telemetry/v1: tier 1 pulled into columns, the whole document kept as
// JSON. Stored as sent (re-serialized), so readers must escape it on display.
const NO_TELEMETRY = {
  status: null, since: null, headline: null, blockers: null, risks: null,
  pixellotVersion: null, camerasExpected: null, camerasDetected: null,
  streamingPath: null, json: null, systemType: null, blockerTitles: null,
  camerasSlow: null, portsFailed: null, servicesDown: null, scoreboardSource: null,
  scoreboardOk: null, ip: null, subnetMask: null, gateway: null, dns1: null,
  dns2: null, dhcp: null, lastBoot: null, unexpected7d: null, rebootPending: null,
  poeDrawW: null, clockOffsetS: null, mac: null, cameraMacs: null,
  internetReachable: null,
};
const MAC_RE = /^([0-9A-F]{2}:){5}[0-9A-F]{2}$/;
const SYSTEM_TYPES = new Set(["S1", "S2", "S2S"]);
const SCORE_SOURCES = new Set(["ocr", "scoreconnect"]);

const NO_EVENT = { id: null, state: null, reason: null, onAir: null, json: null };

// The in-event reader's summary, stored whole like telemetry (pulse.event/v1).
// eventId is Pixellot's; Unity resolves it to the NFHS game and broadcast.
function eventDoc(e) {
  if (!e || typeof e !== "object" || Array.isArray(e) || e.schema !== EVENT_SCHEMA) return NO_EVENT;
  const json = JSON.stringify(e);
  if (new TextEncoder().encode(json).length > MAX_EVENT_BYTES) return NO_EVENT;
  const id = str(e.eventId, 64);
  const state = str(e.state);
  return {
    id: id && /^[0-9A-Za-z]{8,40}$/.test(id) ? id : null,
    state: EVENT_STATES.has(state) ? state : null,
    reason: str(e.reason),
    onAir: typeof e.wentOnAir === "boolean" ? (e.wentOnAir ? 1 : 0) : null,
    json,
  };
}

function telemetry(t) {
  if (!t || typeof t !== "object" || Array.isArray(t) || t.schema !== TELEMETRY_SCHEMA) return NO_TELEMETRY;
  const json = JSON.stringify(t);
  if (new TextEncoder().encode(json).length > MAX_TELEMETRY_BYTES) return NO_TELEMETRY;
  const net = obj(t.network);
  const inet = obj(net.internet);
  const cams = obj(t.cameras);
  const power = obj(t.power);
  const board = obj(t.scoreboard);
  const status = str(t.status);
  const path = str(net.streamingPath);
  const sys = str(cams.systemType);
  const src = str(board.source);
  const blockerTitles = list(t.blockers, 256);
  return {
    ...NO_TELEMETRY,
    status: STATUSES.has(status) ? status : null,
    since: str(t.statusSince),
    headline: str(t.headline, 256),
    blockers: Array.isArray(t.blockers) ? Math.min(t.blockers.length, MAX_CODES) : null,
    blockerTitles,
    pixellotVersion: str(t.pixellotVersion),
    internetReachable: bool(net.internetReachable),
    streamingPath: PATHS.has(path) ? path : null,
    portsFailed: list(net.portsFailed),
    ip: str(inet.ip),
    subnetMask: str(inet.subnetMask),
    gateway: str(inet.gateway),
    dns1: str(inet.dns1),
    dns2: str(inet.dns2),
    dhcp: bool(inet.dhcp),
    mac: macOf(inet.mac),
    systemType: SYSTEM_TYPES.has(sys) ? sys : null,
    camerasExpected: int(cams.expected, 0, 64),
    camerasDetected: int(cams.detected, 0, 64),
    camerasSlow: int(cams.slow, 0, 64),
    servicesDown: list(t.servicesDown),
    scoreboardSource: SCORE_SOURCES.has(src) ? src : null,
    scoreboardOk: bool(board.ok),
    lastBoot: str(power.lastBoot),
    unexpected7d: int(power.unexpectedShutdowns7d, 0, 1000),
    json,
  };
}

function macOf(v) {
  const m = str(v);
  return m && MAC_RE.test(m) ? m : null;
}

function list(v, max = MAX_FIELD) {
  if (!Array.isArray(v)) return null;
  return JSON.stringify(v.map((x) => str(x, max)).filter(Boolean).slice(0, MAX_CODES));
}

function bool(v) {
  return typeof v === "boolean" ? (v ? 1 : 0) : null;
}

function obj(v) {
  return v && typeof v === "object" && !Array.isArray(v) ? v : {};
}

// Finding transitions from the monitor: code + class + title + since, capped.
function events(v) {
  if (!Array.isArray(v)) return null;
  const out = [];
  for (const e of v.slice(0, MAX_EVENTS)) {
    if (!e || typeof e !== "object") continue;
    const code = str(e.code);
    if (!code) continue;
    out.push({ code, class: str(e.class), title: str(e.title), since: str(e.since) });
  }
  return JSON.stringify(out);
}

function num(v, lo, hi) {
  return typeof v === "number" && Number.isFinite(v) && v >= lo && v <= hi ? v : null;
}

function int(v, lo, hi) {
  const n = num(v, lo, hi);
  return n === null ? null : Math.trunc(n);
}

// A clock far in the future would pin last_seen ahead of reality; drop it and
// fall back to received_at rather than trust it.
function normalizeTime(v, receivedAt) {
  if (typeof v !== "string") return null;
  const t = Date.parse(v);
  if (!Number.isFinite(t)) return null;
  if (t > Date.parse(receivedAt) + FUTURE_SKEW_MS) return null;
  return new Date(t).toISOString();
}

function idOf(item) {
  return item && typeof item.checkinId === "string" ? item.checkinId.slice(0, 64) : null;
}

function notFound() {
  return Response.json({ ok: false, error: "not-found" }, { status: 404 });
}
function badRequest(error) {
  return Response.json({ ok: false, error }, { status: 400 });
}
function tooLarge() {
  return Response.json({ ok: false, error: "too-large" }, { status: 413 });
}
