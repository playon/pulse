import { test, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { generateKeyPairSync, createSign } from "node:crypto";
import worker from "../src/index.js";
import { runAlertCheck } from "../src/alert.js";
import { fakeD1 } from "./fake-d1.js";

const SECRET = "test-secret";
let env;
let realFetch;
let fetchCalls;

beforeEach(() => {
  env = { ROLE: "ingest", CHECKIN_SECRET: SECRET, DB: fakeD1() };
  realFetch = globalThis.fetch;
  fetchCalls = [];
});
afterEach(() => {
  globalThis.fetch = realFetch;
});

function post(body, headers = {}) {
  const text = typeof body === "string" ? body : JSON.stringify(body);
  return worker.fetch(
    new Request("https://w.test/checkin", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: text,
    }),
    env,
  );
}

function receivedAt(checkinId) {
  return env.DB.raw.prepare("SELECT received_at FROM checkins WHERE checkin_id = ?").get(checkinId).received_at;
}

function checkin(overrides = {}) {
  return {
    checkinId: "11111111-2222-3333-4444-555555555555",
    sentAt: "2026-09-20T14:00:00Z",
    hostname: "PXLS2_10893",
    serialNumber: "SN123",
    venueId: "V42",
    vpuName: "Main Gym",
    model: "S2",
    pulseVersion: "1.4.0-dev",
    channel: "dev",
    readiness: { status: "PASS", policyVersion: "1", blockers: [], risks: ["tz-drift"] },
    ...overrides,
  };
}

test("health answers without auth", async () => {
  const r = await worker.fetch(new Request("https://w.test/health"), env);
  assert.equal(r.status, 200);
});

test("unknown paths are 404", async () => {
  const r = await worker.fetch(new Request("https://w.test/units.csv"), env);
  assert.equal(r.status, 404);
});

test("no write key is needed", async () => {
  delete env.CHECKIN_SECRET;
  const r = await post({ checkins: [checkin()] });
  assert.equal(r.status, 200);
  assert.equal((await r.json()).results[0].status, "inserted");
});

test("an older build's key is accepted, ignored, and never stored", async () => {
  const r = await post({ secret: "anything-at-all", checkins: [checkin()] });
  assert.equal(r.status, 200);
  const row = env.DB.raw.prepare("SELECT raw FROM checkins").get();
  assert.ok(!row.raw.includes("anything-at-all"));
});

test("inserts, then a replay of the same id is a duplicate", async () => {
  const a = checkin();
  const b = checkin({ checkinId: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", sentAt: "2026-09-21T09:00:00Z" });
  let body = await (await post({ secret: SECRET, checkins: [a, b] })).json();
  assert.deepEqual(body.results.map((x) => x.status), ["inserted", "inserted"]);

  body = await (await post({ secret: SECRET, checkins: [a] })).json();
  assert.equal(body.ok, true);
  assert.equal(body.results[0].status, "duplicate");
  assert.equal(env.DB.raw.prepare("SELECT COUNT(*) n FROM checkins").get().n, 2);
});

test("invalid items are reported without sinking the batch", async () => {
  const body = await (await post({
    secret: SECRET,
    checkins: [checkin(), { checkinId: "short" }, "not-an-object"],
  })).json();
  assert.deepEqual(body.results.map((x) => x.status), ["inserted", "invalid", "invalid"]);
});

test("future sentAt is dropped, stored fields are trimmed and capped", async () => {
  await post({
    secret: SECRET,
    checkins: [checkin({ sentAt: "2099-01-01T00:00:00Z", hostname: "  " + "x".repeat(300) + "  " })],
  });
  const row = env.DB.raw.prepare("SELECT sent_at, hostname, readiness_risks, raw FROM checkins").get();
  assert.equal(row.sent_at, null);
  assert.equal(row.hostname.length, 128);
  assert.equal(row.readiness_risks, '["tz-drift"]');
  assert.ok(!row.raw.includes(SECRET));
});

test("units view rolls up first/last seen and run count per unit", async () => {
  await post({
    secret: SECRET,
    checkins: [
      checkin({ checkinId: "id-00000001", sentAt: "2026-09-18T10:00:00Z", pulseVersion: "1.3.1" }),
      checkin({ checkinId: "id-00000002", sentAt: "2026-09-22T10:00:00Z", pulseVersion: "1.4.0-dev" }),
      checkin({ checkinId: "id-00000003", sentAt: "2026-09-20T10:00:00Z", pulseVersion: "1.3.1" }),
      checkin({ checkinId: "id-00000004", venueId: "V99", vpuName: "Other Gym" }),
    ],
  });
  // A unit is its venue id now (check-ins no longer carry hostname or serial).
  const units = env.DB.raw.prepare("SELECT * FROM units ORDER BY venue_id").all();
  assert.equal(units.length, 2);
  const main = units.find((u) => u.venue_id === "V42");
  assert.equal(main.run_count, 3);
  assert.equal(main.first_seen, "2026-09-18T10:00:00.000Z");
  assert.equal(main.last_seen, receivedAt("id-00000002"));   // when the Worker heard it
  assert.equal(main.pulse_version, "1.4.0-dev");
});

test("batch and body limits", async () => {
  const many = Array.from({ length: 51 }, (_, i) => checkin({ checkinId: `id-${String(i).padStart(8, "0")}` }));
  assert.equal((await post({ secret: SECRET, checkins: many })).status, 400);
  assert.equal((await post("x".repeat(70 * 1024))).status, 413);
  assert.equal((await post("{not json")).status, 400);
  assert.equal((await post({ secret: SECRET, checkins: [] })).status, 400);
});

test("rate limiter rejection is 429", async () => {
  env.INGEST_LIMITER = { limit: async () => ({ success: false }) };
  assert.equal((await post({ secret: SECRET, checkins: [checkin()] })).status, 429);
});

test("storage failure is a non-ok 500 so the client keeps its queue", async () => {
  env.DB.batch = async () => { throw new Error("D1 down"); };
  const r = await post({ secret: SECRET, checkins: [checkin()] });
  assert.equal(r.status, 500);
  assert.equal((await r.json()).ok, false);
});

function captureSlack(status = 200) {
  globalThis.fetch = async (url, init) => {
    fetchCalls.push({ url: String(url), body: init && init.body });
    return new Response("ok", { status });
  };
}

test("alert fires on an empty window and names the last check-in", async () => {
  env.SLACK_WEBHOOK_URL = "https://hooks.slack.test/x";
  captureSlack();
  await post({ secret: SECRET, checkins: [checkin()] });
  env.DB.raw.exec("UPDATE checkins SET received_at = '2026-09-19T08:00:00.000Z'");
  const res = await runAlertCheck(env, new Date("2026-09-23T13:00:00Z"));
  assert.equal(res.alerted, true);
  assert.equal(fetchCalls.length, 1);
  const text = JSON.parse(fetchCalls[0].body).text;
  assert.match(text, /0 received in the last 24 h/);
  assert.match(text, /2026-09-19 08:00 UTC/);
});

test("alert stays quiet when check-ins arrived", async () => {
  env.SLACK_WEBHOOK_URL = "https://hooks.slack.test/x";
  captureSlack();
  await post({ secret: SECRET, checkins: [checkin()] });
  const res = await runAlertCheck(env, new Date());
  assert.equal(res.alerted, false);
  assert.equal(fetchCalls.length, 0);
});

test("alert reports a database failure instead of staying silent", async () => {
  env.SLACK_WEBHOOK_URL = "https://hooks.slack.test/x";
  captureSlack();
  env.DB = { prepare: () => ({ bind: () => ({ first: async () => { throw new Error("boom"); } }) }) };
  await runAlertCheck(env, new Date());
  assert.match(JSON.parse(fetchCalls[0].body).text, /could not read the database \(boom\)/);
});

test("a failing Slack webhook surfaces as an error", async () => {
  env.SLACK_WEBHOOK_URL = "https://hooks.slack.test/x";
  captureSlack(500);
  await assert.rejects(runAlertCheck(env, new Date()), /Slack webhook returned 500/);
});

// ── admin ──

const TEAM = "pulse-test.cloudflareaccess.com";
const AUD = "aud-tag-123";
const { privateKey, publicKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
const JWK = { ...publicKey.export({ format: "jwk" }), kid: "k1", alg: "RS256" };

function b64url(buf) {
  return Buffer.from(buf).toString("base64url");
}
function signJwt(claims, kid = "k1") {
  const head = b64url(JSON.stringify({ alg: "RS256", kid }));
  const body = b64url(JSON.stringify(claims));
  const sig = createSign("RSA-SHA256").update(`${head}.${body}`).sign(privateKey);
  return `${head}.${body}.${b64url(sig)}`;
}
function goodClaims(extra = {}) {
  const now = Math.floor(Date.now() / 1000);
  return { aud: [AUD], iss: `https://${TEAM}`, exp: now + 600, iat: now, email: "ian.moore@playonsports.com", ...extra };
}

function adminEnv() {
  return { ...env, ROLE: "admin", ACCESS_TEAM_DOMAIN: TEAM, ACCESS_AUD: AUD };
}
function adminGet(path, token, e = adminEnv()) {
  const headers = token ? { "Cf-Access-Jwt-Assertion": token } : {};
  return worker.fetch(new Request(`https://a.test${path}`, { headers }), e);
}
function serveCerts() {
  globalThis.fetch = async (url) => {
    fetchCalls.push({ url: String(url) });
    return Response.json({ keys: [JWK] });
  };
}

test("admin refuses requests without an Access token", async () => {
  serveCerts();
  assert.equal((await adminGet("/units.csv")).status, 403);
});

test("admin refuses when Access isn't configured, even with a token", async () => {
  serveCerts();
  const e = { ...adminEnv(), ACCESS_AUD: "REPLACE_WITH_APPLICATION_AUD_TAG" };
  assert.equal((await adminGet("/units.csv", signJwt(goodClaims()), e)).status, 403);
});

test("admin accepts a valid Access JWT", async () => {
  serveCerts();
  await post({ secret: SECRET, checkins: [checkin()] });
  const r = await adminGet("/units.csv", signJwt(goodClaims()));
  assert.equal(r.status, 200);
  assert.match(await r.text(), /Main Gym/);
});

test("admin rejects wrong audience, wrong issuer, expired, and forged tokens", async () => {
  serveCerts();
  const bad = [
    signJwt(goodClaims({ aud: ["someone-else"] })),
    signJwt(goodClaims({ iss: "https://evil.cloudflareaccess.com" })),
    signJwt(goodClaims({ exp: Math.floor(Date.now() / 1000) - 5 })),
    signJwt(goodClaims(), "unknown-kid"),
  ];
  const t = signJwt(goodClaims());
  bad.push(t.slice(0, t.lastIndexOf(".") + 1) + b64url(Buffer.alloc(256)));
  for (const token of bad) assert.equal((await adminGet("/", token)).status, 403);
});

test("CSV neutralises formulas and HTML escapes VPU-supplied text", async () => {
  serveCerts();
  await post({
    secret: SECRET,
    checkins: [checkin({ model: '=HYPERLINK("http://x")', vpuName: "<script>alert(1)</script>" })],
  });
  const token = signJwt(goodClaims());
  const csvText = await (await adminGet("/units.csv", token)).text();
  assert.match(csvText, /"'=HYPERLINK\(""http:\/\/x""\)"/);
  const html = await (await adminGet("/", token)).text();
  assert.ok(!html.includes("<script>alert(1)</script>"));
  assert.match(html, /&lt;script&gt;/);
});

test("checkins.csv honours the days window", async () => {
  serveCerts();
  await post({ secret: SECRET, checkins: [checkin(), checkin({ checkinId: "old-00000001" })] });
  env.DB.raw.exec("UPDATE checkins SET received_at = '2020-01-01T00:00:00.000Z' WHERE checkin_id = 'old-00000001'");
  const text = await (await adminGet("/checkins.csv?days=7", signJwt(goodClaims()))).text();
  assert.equal(text.trim().split("\r\n").length, 2);
});

test("monitor check-in stores reason, delta and pass cost", async () => {
  const c = checkin({
    reason: "state-change",
    osBuild: "17763",
    ubr: 253,
    delta: {
      status: "FAIL",
      prevStatus: "PASS",
      opened: [{ code: "stream-blocked", class: "blocker", title: "Streaming is blocked", since: "2026-10-12T20:00:00Z" }],
      resolved: [],
      persisting: ["nic-slow"],
    },
    monitor: { pass: "full", seconds: 41.5, psRuns: 9, eventLive: false, coreDown: false,
               cpuSeconds: 8.19, cpuPercent: 6.9, processes: 16 },
  });
  const body = await (await post({ secret: SECRET, checkins: [c] })).json();
  assert.equal(body.results[0].status, "inserted");
  const row = env.DB.raw.prepare("SELECT * FROM checkins").get();
  assert.equal(row.reason, "state-change");
  assert.equal(row.ubr, "253");
  assert.equal(row.delta_status, "FAIL");
  assert.equal(row.monitor_pass, "full");
  assert.equal(row.monitor_seconds, 41.5);
  assert.equal(row.monitor_ps_runs, 9);
  assert.equal(row.monitor_cpu_seconds, 8.19);
  assert.equal(row.monitor_cpu_percent, 6.9);
  assert.equal(row.monitor_processes, 16);
  assert.equal(row.event_live, 0);
  const t = env.DB.raw.prepare("SELECT * FROM transitions").all();
  assert.equal(t.length, 1);
  assert.equal(t[0].kind, "opened");
  assert.equal(t[0].code, "stream-blocked");
  assert.equal(t[0].class, "blocker");
});

test("launch check-in leaves monitor columns empty", async () => {
  await post({ secret: SECRET, checkins: [checkin({ reason: "startup" })] });
  const row = env.DB.raw.prepare("SELECT * FROM checkins").get();
  assert.equal(row.reason, "startup");
  assert.equal(row.delta_opened, null);
  assert.equal(row.monitor_pass, null);
  assert.equal(env.DB.raw.prepare("SELECT COUNT(*) n FROM transitions").get().n, 0);
});

test("junk monitor fields are dropped, not stored", async () => {
  const c = checkin({
    reason: "rm -rf",
    delta: { opened: "nope", resolved: [{ title: "no code" }, null] },
    monitor: { pass: "huge", seconds: -5, psRuns: 1e9, eventLive: "yes" },
  });
  await post({ secret: SECRET, checkins: [c] });
  const row = env.DB.raw.prepare("SELECT * FROM checkins").get();
  assert.equal(row.reason, null);
  assert.equal(row.delta_opened, null);
  assert.equal(row.delta_resolved, "[]");
  assert.equal(row.monitor_pass, null);
  assert.equal(row.monitor_seconds, null);
  assert.equal(row.monitor_ps_runs, null);
  assert.equal(row.event_live, null);
});

function telemetryDoc(overrides = {}) {
  return {
    schema: "pulse.telemetry/v1",
    status: "FAIL",
    statusSince: "2026-10-13T19:20:00Z",
    headline: "The venue network is blocking clock sync",
    blockers: ["The venue network is blocking clock sync"],
    checkedAt: "2026-10-13T19:34:30Z",
    pixellotVersion: "5.37.3",
    network: {
      internetReachable: true,
      streamingPath: "rtmp-1935",
      portsFailed: ["Clock sync (UDP 123)"],
      internet: { adapter: "Internet", mac: "C8:D9:D2:1C:29:2A", ip: "192.168.111.251",
                  subnetMask: "255.255.254.0", gateway: "192.168.110.1", dns1: "192.168.110.1",
                  dns2: null, dhcp: false },
    },
    cameras: { systemType: "S2", expected: 2, detected: 1, slow: 1,
               ports: [{ port: "Port 1", state: "camera", linkMbps: 100, slow: true, cameraMac: "00:D0:89:19:71:57" }] },
    servicesDown: [],
    scoreboard: { source: "scoreconnect", ok: true },
    power: { lastBoot: "2026-10-13T14:48:23", unexpectedShutdowns7d: 4 },
    ...overrides,
  };
}

test("utilitarian telemetry lands as unit_status columns", async () => {
  await post({ secret: SECRET, checkins: [checkin({ reason: "periodic", telemetry: telemetryDoc() })] });
  const u = env.DB.raw.prepare("SELECT * FROM unit_status").get();
  assert.equal(u.vpu_name, "Main Gym");
  assert.equal(u.model, "S2");
  assert.equal(u.status, "FAIL");
  assert.equal(u.headline, "The venue network is blocking clock sync");
  assert.equal(u.blockers, '["The venue network is blocking clock sync"]');
  assert.equal(u.internet_reachable, 1);
  assert.equal(u.streaming_path, "rtmp-1935");
  assert.equal(u.ports_failed, '["Clock sync (UDP 123)"]');
  assert.equal(u.ip, "192.168.111.251");
  assert.equal(u.subnet_mask, "255.255.254.0");
  assert.equal(u.gateway, "192.168.110.1");
  assert.equal(u.dns1, "192.168.110.1");
  assert.equal(u.dns2, null);
  assert.equal(u.dhcp, 0);
  assert.equal(u.mac, "C8:D9:D2:1C:29:2A");
  assert.equal(u.system_type, "S2");
  assert.equal(u.cameras_detected, 1);
  assert.equal(u.cameras_expected, 2);
  assert.equal(u.cameras_slow, 1);
  assert.equal(u.services_down, "[]");
  assert.equal(u.scoreboard_source, "scoreconnect");
  assert.equal(u.scoreboard_ok, 1);
  assert.equal(u.unexpected_shutdowns_7d, 4);
  assert.equal(u.pixellot_version, "5.37.3");
  for (const gone of ["hostname", "serial_number", "camera_macs"]) assert.ok(!(gone in u), gone);
  const port = env.DB.raw.prepare(
    "SELECT json_extract(telemetry, '$.cameras.ports[0].cameraMac') m FROM checkins").get();
  assert.equal(port.m, "00:D0:89:19:71:57");
});

test("telemetry.calibration (PV-57) is kept whole in unit_status", async () => {
  const calibration = {
    primary: "football",
    sports: [{ name: "football", at: "2026-08-20T15:02:11-04:00" }, { name: "soccer", at: null }],
    ocr: { calibrated: false, at: null },
  };
  await post({ secret: SECRET, checkins: [checkin({ telemetry: telemetryDoc({ calibration }) })] });
  const u = env.DB.raw.prepare("SELECT telemetry FROM unit_status").get();
  assert.deepEqual(JSON.parse(u.telemetry).calibration, calibration);
  // Unknown stays null, not dropped.
  env.DB.raw.exec("DELETE FROM checkins");
  await post({ secret: SECRET, checkins: [checkin({ telemetry: telemetryDoc({ calibration: null }) })] });
  const n = env.DB.raw.prepare("SELECT telemetry FROM unit_status").get();
  assert.equal(JSON.parse(n.telemetry).calibration, null);
});

test("the hardware block (PV-64) is kept whole in the telemetry document", async () => {
  const hardware = {
    model: "HP EliteDesk 800 G4 WKS TWR",
    cpu: { name: "Intel(R) Core(TM) i5-8500 CPU @ 3.00GHz", cores: 6, threads: 6 },
    memoryGb: 32,
    disks: [{ model: "TOSHIBA DT01ACA100", sizeGb: 932, type: "HDD" }],
    gpus: [{ name: "NVIDIA GeForce GTX 1650", driver: "32.0.15.7628", vramMb: 4096 },
           { name: "Intel(R) UHD Graphics 630", driver: "24.20.100.6136", vramMb: 1024 }],
    bios: { version: "Q01 Ver. 02.07.01", date: "2019-04-23" },
  };
  await post({ secret: SECRET, checkins: [checkin({ reason: "periodic", telemetry: telemetryDoc({ hardware }) })] });
  const row = env.DB.raw.prepare("SELECT telemetry FROM checkins").get();
  assert.deepEqual(JSON.parse(row.telemetry).hardware, hardware);
  const g = env.DB.raw.prepare(
    "SELECT json_extract(telemetry, '$.hardware.gpus[0].vramMb') v FROM checkins").get();
  assert.equal(g.v, 4096);
});

test("a heartbeat moves last_seen but keeps the last full reading", async () => {
  const full = checkin({ reason: "state-change", telemetry: telemetryDoc({ status: "PASS", blockers: [] }) });
  const beat = { checkinId: "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee", sentAt: "2026-09-20T15:00:00Z",
                 reason: "heartbeat", venueId: "V42", vpuName: "Main Gym", status: "PASS" };
  await post({ secret: SECRET, checkins: [full] });
  await new Promise((r) => setTimeout(r, 5));
  const r = await (await post({ secret: SECRET, checkins: [beat] })).json();
  assert.deepEqual(r.results.map((x) => x.status), ["inserted"]);
  const u = env.DB.raw.prepare("SELECT * FROM unit_status").get();
  assert.equal(u.last_seen, receivedAt(beat.checkinId));
  assert.equal(u.last_full_report, "2026-09-20T14:00:00.000Z");
  assert.equal(u.last_kind, "heartbeat");
  assert.equal(u.status, "PASS");
  const hb = env.DB.raw.prepare("SELECT readiness_status FROM checkins WHERE reason = 'heartbeat'").get();
  assert.equal(hb.readiness_status, "PASS");
});

test("unit_status keeps only the newest telemetry per unit", async () => {
  const a = checkin({ telemetry: telemetryDoc() });
  const b = checkin({ checkinId: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", sentAt: "2026-09-20T15:00:00Z",
                      telemetry: telemetryDoc({ status: "PASS", blockers: [] }) });
  const other = checkin({ checkinId: "cccccccc-cccc-cccc-cccc-cccccccccccc", venueId: "V7", vpuName: "Field",
                          telemetry: telemetryDoc() });
  await post({ secret: SECRET, checkins: [a, b, other] });
  const u = env.DB.raw.prepare("SELECT venue_id, status FROM unit_status ORDER BY venue_id").all();
  assert.deepEqual(u.map((r) => [r.venue_id, r.status]), [["V42", "PASS"], ["V7", "FAIL"]]);
});

test("wrong-schema or oversized telemetry is dropped, the check-in still lands", async () => {
  const big = telemetryDoc({ pad: "x".repeat(20000) });
  const r = await (await post({ secret: SECRET, checkins: [
    checkin({ telemetry: { schema: "other", status: "FAIL" } }),
    checkin({ checkinId: "dddddddd-dddd-dddd-dddd-dddddddddddd", telemetry: big }),
  ] })).json();
  assert.deepEqual(r.results.map((x) => x.status), ["inserted", "inserted"]);
  const n = env.DB.raw.prepare("SELECT COUNT(*) n FROM checkins WHERE telemetry IS NOT NULL").get().n;
  assert.equal(n, 0);
});


test("run_count counts launches, not the monitor's posts", async () => {
  const launch = (id, at) => checkin({ checkinId: id, sentAt: at });
  const report = (id, at, reason, extra = {}) => checkin({ checkinId: id, sentAt: at, reason,
    readiness: undefined, telemetry: { schema: "pulse.telemetry/v1", status: "PASS" }, ...extra });
  const beat = { checkinId: "beat-0000-0000-0000-000000000009", sentAt: "2026-09-21T09:00:00Z",
                 reason: "heartbeat", venueId: "V42", vpuName: "Main Gym", status: "PASS" };
  await post({ checkins: [
    launch("aaaaaaaa-0000-0000-0000-000000000001", "2026-09-20T10:00:00Z"),
    launch("aaaaaaaa-0000-0000-0000-000000000002", "2026-09-20T12:00:00Z"),
    report("aaaaaaaa-0000-0000-0000-000000000003", "2026-09-20T13:00:00Z", "state-change"),
    report("aaaaaaaa-0000-0000-0000-000000000004", "2026-09-20T14:00:00Z", "periodic"),
    beat,
  ] });
  const u = env.DB.raw.prepare("SELECT * FROM units").all();
  assert.equal(u.length, 1);
  assert.equal(u[0].run_count, 2);
  assert.equal(u[0].monitor_posts, 3);
  assert.equal(u[0].last_launch, "2026-09-20T12:00:00.000Z");
  assert.equal(u[0].last_seen, receivedAt("beat-0000-0000-0000-000000000009"));
  assert.equal(u[0].pulse_version, "1.4.0-dev");       // the heartbeat carries no version
  assert.equal(u[0].readiness_status, "PASS");
});

test("an imported sheet unit keeps the sheet's run count and first seen", async () => {
  env.DB.raw.prepare(
    `INSERT INTO checkins (checkin_id, received_at, sent_at, venue_id, vpu_name, pulse_version, channel, source, raw)
     VALUES ('sheet-import-SN1', '2026-10-13T20:56:55Z', '2026-09-01T10:00:00.000Z', 'V42', 'Main Gym',
             'web-v1.3.1', 'production', 'sheet-import',
             '{"imported":"Runs.csv","sheetKey":"SN1","firstSeen":"2026-06-01T09:00:00.000Z","runCount":40}')`,
  ).run();
  // Its received_at is the import date, so last_seen keeps the sheet's own time.
  assert.equal(env.DB.raw.prepare("SELECT last_seen FROM units").get().last_seen, "2026-09-01T10:00:00.000Z");
  await post({ checkins: [checkin({ sentAt: "2026-10-14T10:00:00Z" })] });
  const u = env.DB.raw.prepare("SELECT * FROM units").get();
  assert.equal(u.run_count, 41);                      // 40 from the sheet + this launch
  assert.equal(u.first_seen, "2026-06-01T09:00:00.000Z");
  assert.equal(u.pulse_version, "1.4.0-dev");          // the newest check-in, not the import
});

test("a check-in with no unit identity never becomes its own unit", async () => {
  // No venue id or name, and (like every current build) no hostname or serial.
  await post({ checkins: [checkin({ venueId: null, vpuName: null, hostname: null, serialNumber: null })] });
  assert.equal(env.DB.raw.prepare("SELECT COUNT(*) n FROM units").get().n, 0);
});

test("a check-in the sheet relays is tagged sheet-relay and still counts as a launch", async () => {
  const a = checkin();
  let body = await (await post({ checkins: [a] }, { "X-Pulse-Relay": "sheet" })).json();
  assert.equal(body.results[0].status, "inserted");
  // The VPU's own retry later gets through: a duplicate, and the tag stays.
  body = await (await post({ checkins: [a] })).json();
  assert.equal(body.results[0].status, "duplicate");
  const row = env.DB.raw.prepare("SELECT source, country FROM checkins").get();
  assert.equal(row.source, "sheet-relay");
  assert.equal(row.country, null);                     // Google's country, not the school's
  assert.equal(env.DB.raw.prepare("SELECT run_count FROM units").get().run_count, 1);

  await post({ checkins: [checkin({ checkinId: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" })] });
  assert.equal(env.DB.raw.prepare(
    "SELECT source FROM checkins WHERE checkin_id = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'").get().source, "pulse");
});

test("views carry Eastern-time copies of their timestamps, EDT/EST by the US rules", async () => {
  const at = (iso) => env.DB.raw.prepare(
    "SELECT received_at_et AS et FROM checkins_et WHERE checkin_id = ?").get(iso).et;
  const edges = {
    "2026-10-14T14:33:34.000Z": "2026-10-14 10:33:34 EDT",
    "2026-11-01T05:59:59.000Z": "2026-11-01 01:59:59 EDT",   // last second of EDT
    "2026-11-01T06:00:00.000Z": "2026-11-01 01:00:00 EST",   // clocks fall back
    "2026-03-08T06:59:59.000Z": "2026-03-08 01:59:59 EST",
    "2026-03-08T07:00:00.000Z": "2026-03-08 03:00:00 EDT",   // clocks spring forward
    "2026-01-15T12:00:00.000Z": "2026-01-15 07:00:00 EST",
  };
  for (const iso of Object.keys(edges)) {
    env.DB.raw.prepare(
      "INSERT INTO checkins (checkin_id, received_at, venue_id, raw) VALUES (?, ?, 'V-ET', '{}')").run(iso, iso);
  }
  for (const [iso, want] of Object.entries(edges)) assert.equal(at(iso), want);

  await post({ checkins: [checkin({ sentAt: "2026-09-20T14:00:00Z" })] });
  const u = env.DB.raw.prepare("SELECT * FROM units WHERE venue_id = 'V42'").get();
  assert.equal(u.first_seen, "2026-09-20T14:00:00.000Z");     // UTC kept as is
  assert.equal(u.first_seen_et, "2026-09-20 10:00:00 EDT");
  assert.equal(u.last_launch_et, "2026-09-20 10:00:00 EDT");
});

test("a unit whose clock runs slow still reads as seen now", async () => {
  // NTP blocked at the venue: the VPU thinks it is three weeks ago.
  const slow = { reason: "heartbeat", venueId: "V42", vpuName: "Main Gym", status: "PASS" };
  await post({ checkins: [
    checkin({ checkinId: "slow-0000-0000-0000-000000000001", sentAt: "2026-09-01T10:00:00Z",
              telemetry: { schema: "pulse.telemetry/v1", status: "PASS" }, reason: "state-change" }),
    { ...slow, checkinId: "slow-0000-0000-0000-000000000002", sentAt: "2026-09-01T11:00:00Z" },
  ] });
  const heard = receivedAt("slow-0000-0000-0000-000000000002");
  const u = env.DB.raw.prepare("SELECT * FROM units").get();
  assert.equal(u.last_seen, heard);
  assert.equal(u.first_seen, "2026-09-01T10:00:00.000Z");     // event times stay the VPU's
  const s = env.DB.raw.prepare("SELECT * FROM unit_status").get();
  assert.equal(s.last_seen, heard);
  assert.equal(s.last_kind, "heartbeat");                       // ordering still follows sent_at
  assert.equal(s.last_full_report, "2026-09-01T10:00:00.000Z");
});

test("every reply carries fleet control, on by default", async () => {
  const body = await (await post({ checkins: [checkin()] })).json();
  assert.deepEqual(body.control, { mode: "on", skip: [] });
});

test("fleet control: a unit's row decides its mode, skip lists add up", async () => {
  env.DB.raw.exec(`UPDATE monitor_control SET skip = '["Get-S1Cameras.ps1"]' WHERE scope = 'fleet'`);
  env.DB.raw.exec(`INSERT INTO monitor_control (scope, mode, skip) VALUES ('V42', 'off', '["Get-PoePower.ps1"]')`);
  let body = await (await post({ checkins: [checkin()] })).json();           // venueId V42
  assert.equal(body.control.mode, "off");
  assert.deepEqual(body.control.skip.sort(), ["Get-PoePower.ps1", "Get-S1Cameras.ps1"]);

  body = await (await post({ checkins: [checkin({ checkinId: "aaaaaaaa-0000-0000-0000-00000000000b",
                                                  venueId: "V99" })] })).json();
  assert.equal(body.control.mode, "on");                                   // only the fleet row applies
  assert.deepEqual(body.control.skip, ["Get-S1Cameras.ps1"]);

  env.DB.raw.exec(`UPDATE monitor_control SET mode = 'off' WHERE scope = 'fleet'`);
  body = await (await post({ checkins: [checkin({ checkinId: "aaaaaaaa-0000-0000-0000-00000000000c",
                                                  venueId: "V99" })] })).json();
  assert.equal(body.control.mode, "off");
});

test("a failed control lookup leaves control out and still stores the check-in", async () => {
  env.DB.raw.exec("DROP TABLE monitor_control");
  const body = await (await post({ checkins: [checkin()] })).json();
  assert.equal(body.ok, true);
  assert.equal(body.results[0].status, "inserted");
  assert.equal(body.control, undefined);
});

test("the monitor's peak memory is stored, and a paused line is accepted", async () => {
  await post({ checkins: [checkin({ reason: "periodic", monitor: { pass: "full", cpuSeconds: 4.4, memoryPeakMb: 61.5 } })] });
  assert.equal(env.DB.raw.prepare("SELECT monitor_memory_peak_mb m FROM checkins").get().m, 61.5);
  await post({ checkins: [{ checkinId: "aaaaaaaa-0000-0000-0000-00000000000d", sentAt: "2026-09-20T14:00:00Z",
                            reason: "paused", venueId: "V42", vpuName: "Main Gym", pulseVersion: "1.5.0" }] });
  const row = env.DB.raw.prepare("SELECT reason FROM checkins WHERE checkin_id = 'aaaaaaaa-0000-0000-0000-00000000000d'").get();
  assert.equal(row.reason, "paused");
  const u = env.DB.raw.prepare("SELECT run_count, monitor_posts FROM units WHERE venue_id = 'V42'").get();
  assert.equal(u.run_count, 0);           // neither a launch nor a monitor report
});

test("an in-event post stores its event document, and the events view has one row per event", async () => {
  const base = { venueId: "V42", vpuName: "Main Gym", pulseVersion: "1.5.0" };
  const ev = (state, extra = {}) => ({ schema: "pulse.event/v1", eventId: "6ad018b2ec5d0313d04118a6",
                                       state, wentOnAir: state === "on-air", fails: 0, ...extra });
  await post({ checkins: [
    { ...base, checkinId: "eeeeeeee-0000-0000-0000-000000000001", sentAt: "2026-10-14T20:10:00Z",
      reason: "event-start", event: ev("connecting") },
    { ...base, checkinId: "eeeeeeee-0000-0000-0000-000000000002", sentAt: "2026-10-14T20:20:00Z",
      reason: "event-update", event: ev("on-air") },
    { ...base, checkinId: "eeeeeeee-0000-0000-0000-000000000003", sentAt: "2026-10-14T22:15:00Z",
      reason: "event-end", event: ev("ended", { wentOnAir: true, onAirSeconds: 7200 }) },
  ] });
  const rows = env.DB.raw.prepare("SELECT * FROM events").all();
  assert.equal(rows.length, 1);
  assert.equal(rows[0].state, "ended");
  assert.equal(rows[0].went_on_air, 1);
  assert.equal(rows[0].on_air_seconds, 7200);
  assert.equal(rows[0].started_at, "2026-10-14T20:10:00.000Z");
  const u = env.DB.raw.prepare("SELECT run_count, monitor_posts FROM units WHERE venue_id = 'V42'").get();
  assert.equal(u.run_count, 0);       // event posts are neither launches nor reports
});

test("an event document with a bad schema, id or size is dropped, the check-in kept", async () => {
  await post({ checkins: [
    { checkinId: "eeeeeeee-0000-0000-0000-000000000011", reason: "event-start", venueId: "V1",
      event: { schema: "nope", eventId: "6ad018b2ec5d0313d04118a6" } },
    { checkinId: "eeeeeeee-0000-0000-0000-000000000012", reason: "event-start", venueId: "V1",
      event: { schema: "pulse.event/v1", eventId: "../../etc", state: "on-air" } },
    { checkinId: "eeeeeeee-0000-0000-0000-000000000013", reason: "event-start", venueId: "V1",
      event: { schema: "pulse.event/v1", eventId: "6ad018b2ec5d0313d04118a6", pad: "x".repeat(5000) } },
  ] });
  const rows = env.DB.raw.prepare("SELECT event_id, event FROM checkins ORDER BY checkin_id").all();
  assert.equal(rows.length, 3);
  assert.equal(rows[0].event, null);
  assert.equal(rows[1].event_id, null);
  assert.equal(rows[2].event, null);
});

test("PV-59: telemetry.scoreboard.ocr and .scoreConnect are stored with the document, not stripped", async () => {
  const board = {
    source: "scoreconnect", ok: true, scoreLinkConnected: true,
    ocr: { configured: false, issue: null },
    scoreConnect: { version: "1.4.2.2", firmware: "2.4.1", scoreLinkModel: "ScoreLinkII", scoreLinkPort: "COM5",
                    serialPort: "COM3", eventType: "Live", botNumber: "02130" },
  };
  await post({ checkins: [checkin({
    checkinId: "eeeeeeee-0000-0000-0000-000000000059", reason: "periodic",
    telemetry: { schema: "pulse.telemetry/v1", status: "PASS", scoreboard: board } })] });
  const u = env.DB.raw.prepare("SELECT telemetry, json_extract(telemetry, '$.scoreboard.scoreConnect.botNumber') AS bot FROM unit_status").get();
  assert.deepEqual(JSON.parse(u.telemetry).scoreboard, board);
  assert.equal(u.bot, "02130");
});

test("0013: unit_status carries the scoreboard detail, events carry schedule, off-air time and warnings", async () => {
  await post({ checkins: [checkin({
    checkinId: "eeeeeeee-0000-0000-0000-000000000021", reason: "periodic",
    telemetry: { schema: "pulse.telemetry/v1", status: "PASS",
                 scoreboard: { source: "scoreconnect", ok: true, scoreLinkConnected: false, dataFlowing: false,
                               sport: "Fairplay Basketball Code 1" } } })] });
  const u = env.DB.raw.prepare("SELECT scoreboard_ok, score_link_connected, scoreboard_data_flowing, scoreconnect_sport FROM unit_status").get();
  assert.equal(u.scoreboard_ok, 1);
  assert.equal(u.score_link_connected, 0);
  assert.equal(u.scoreboard_data_flowing, 0);
  assert.equal(u.scoreconnect_sport, "Fairplay Basketball Code 1");

  await post({ checkins: [{ checkinId: "eeeeeeee-0000-0000-0000-000000000022", sentAt: "2026-10-14T21:55:00Z",
    reason: "event-end", venueId: "V42", vpuName: "Main Gym",
    event: { schema: "pulse.event/v1", eventId: "6ad018b2ec5d0313d04118a6", state: "ended", wentOnAir: true,
             eventName: "gam894328ce3f Middle School Boys Football Sample", nfhsGameKey: "gam894328ce3f",
             scheduledEnd: "2026-10-15T02:14:00.000Z", offAirSeconds: 175, path: "zixi-2088", kind: "event",
             scoreboard: { sportMatch: false, scoreConnectSport: "Fairplay Basketball Code 1" },
             warnings: ["scoreboard-sport-mismatch", "off-air-gaps"] } }] });
  const e = env.DB.raw.prepare("SELECT state, nfhs_game_key, off_air_seconds, scoreboard_sport_match, warnings FROM events").get();
  assert.equal(e.state, "ended");
  assert.equal(e.nfhs_game_key, "gam894328ce3f");
  assert.equal(e.off_air_seconds, 175);
  assert.equal(e.scoreboard_sport_match, 0);
  assert.deepEqual(JSON.parse(e.warnings), ["scoreboard-sport-mismatch", "off-air-gaps"]);
});

// ── The fleet agent's version, update outcome and pinned target (PV-49) ──────

const SHA_A = "a".repeat(64);
const SHA_B = "0123456789abcdef".repeat(4);

test("agentVersion and agentUpdate are stored, and kept in raw", async () => {
  await post({ checkins: [checkin({ reason: "periodic", agentVersion: "0.2.0",
                                    agentUpdate: { status: "rolled-back", version: "0.3.0",
                                                   error: "no post within 3 ticks" } })] });
  const row = env.DB.raw.prepare("SELECT * FROM checkins").get();
  assert.equal(row.agent_version, "0.2.0");
  assert.equal(row.agent_update_status, "rolled-back");
  assert.equal(row.agent_update_version, "0.3.0");
  assert.equal(row.agent_update_error, "no post within 3 ticks");
  const raw = JSON.parse(row.raw);
  assert.equal(raw.agentVersion, "0.2.0");
  assert.deepEqual(raw.agentUpdate, { status: "rolled-back", version: "0.3.0", error: "no post within 3 ticks" });
});

test("a launch check-in has no agent version, and junk agentUpdate is dropped", async () => {
  await post({ checkins: [checkin({ reason: "startup" })] });
  let row = env.DB.raw.prepare("SELECT * FROM checkins").get();
  assert.equal(row.agent_version, null);
  assert.equal(JSON.parse(row.raw).agentUpdate, undefined);
  for (const [i, junk] of [{ status: "exploded", version: "0.3.0" }, "applied", ["applied"], { version: "0.3.0" }].entries()) {
    const id = `aaaaaaaa-0000-0000-0000-00000000010${i}`;
    await post({ checkins: [checkin({ checkinId: id, reason: "periodic", agentVersion: "0.2.0", agentUpdate: junk })] });
    row = env.DB.raw.prepare("SELECT * FROM checkins WHERE checkin_id = ?").get(id);
    assert.equal(row.agent_version, "0.2.0");                 // the check-in still lands
    assert.equal(row.agent_update_status, null, JSON.stringify(junk));
  }
  await post({ checkins: [checkin({ checkinId: "aaaaaaaa-0000-0000-0000-000000000110", reason: "periodic",
                                    agentVersion: "x".repeat(200),
                                    agentUpdate: { status: "failed", error: "e".repeat(400) } })] });
  row = env.DB.raw.prepare("SELECT * FROM checkins WHERE checkin_id = 'aaaaaaaa-0000-0000-0000-000000000110'").get();
  assert.equal(row.agent_version.length, 64);
  assert.equal(row.agent_update_error.length, 256);
});

test("unit_latest keeps the agent's newest version and update outcome", async () => {
  const at = (n) => `2026-10-15T1${n}:00:00Z`;
  await post({ checkins: [
    checkin({ checkinId: "aaaaaaaa-0000-0000-0000-000000000201", sentAt: at(1), reason: "periodic", agentVersion: "0.1.0" }),
    checkin({ checkinId: "aaaaaaaa-0000-0000-0000-000000000202", sentAt: at(3), reason: "heartbeat", agentVersion: "0.2.0",
              agentUpdate: { status: "applied", version: "0.2.0" } }),
    // A replayed older post never outranks the newer one.
    checkin({ checkinId: "aaaaaaaa-0000-0000-0000-000000000203", sentAt: at(2), reason: "periodic", agentVersion: "0.1.0",
              agentUpdate: { status: "failed", version: "0.2.0", error: "hash mismatch" } }),
    checkin({ checkinId: "aaaaaaaa-0000-0000-0000-000000000204", sentAt: at(4), reason: "startup" }),
  ] });
  const l = env.DB.raw.prepare("SELECT * FROM unit_latest WHERE unit_key = 'V42'").get();
  assert.equal(l.agent_version, "0.2.0");                    // a launch after it doesn't clear it
  assert.equal(l.agent_at, "2026-10-15T13:00:00.000Z");
  assert.deepEqual([l.agent_update_status, l.agent_update_version, l.agent_update_error], ["applied", "0.2.0", null]);
});

test("no agent target unless one is set", async () => {
  const body = await (await post({ checkins: [checkin()] })).json();
  assert.equal(body.control.agent, undefined);
});

test("agent target: the fleet's pin, a unit's own pin wins, a unit row without one gets the fleet's", async () => {
  env.DB.raw.exec(`UPDATE monitor_control SET agent_version = '0.2.0', agent_sha256 = '${SHA_A}' WHERE scope = 'fleet'`);
  env.DB.raw.exec(`INSERT INTO monitor_control (scope, agent_version, agent_sha256) VALUES ('V42', '0.3.0', '${SHA_B}')`);
  env.DB.raw.exec(`INSERT INTO monitor_control (scope, mode) VALUES ('V7', 'off')`);
  const reply = async (venueId, n) => (await (await post({ checkins: [checkin({
    checkinId: `aaaaaaaa-0000-0000-0000-00000000030${n}`, venueId })] })).json()).control;
  assert.deepEqual((await reply("V42", 1)).agent, { version: "0.3.0", sha256: SHA_B });   // canary
  assert.deepEqual((await reply("V99", 2)).agent, { version: "0.2.0", sha256: SHA_A });   // no row of its own
  const v7 = await reply("V7", 3);
  assert.equal(v7.mode, "off");
  assert.deepEqual(v7.agent, { version: "0.2.0", sha256: SHA_A });                         // its row sets no version
});

test("a unit pin without its hash means no target, never the fleet's", async () => {
  env.DB.raw.exec(`UPDATE monitor_control SET agent_version = '0.2.0', agent_sha256 = '${SHA_A}' WHERE scope = 'fleet'`);
  env.DB.raw.exec(`INSERT INTO monitor_control (scope, agent_version) VALUES ('V42', '0.1.0')`);
  const body = await (await post({ checkins: [checkin()] })).json();
  assert.equal(body.control.agent, undefined);
  assert.equal(body.control.mode, "on");
});

test("monitor_control refuses a malformed pin", () => {
  const bad = [`agent_version = 'v0.2.0'`, `agent_version = '0.2'`, `agent_sha256 = '${SHA_A.toUpperCase()}'`,
               `agent_sha256 = 'abc'`];
  for (const set of bad) {
    assert.throws(() => env.DB.raw.exec(`UPDATE monitor_control SET ${set} WHERE scope = 'fleet'`), /CHECK constraint/, set);
  }
});

test("switching a unit off the way the README says keeps its agent pin", async () => {
  env.DB.raw.exec(`INSERT INTO monitor_control (scope, agent_version, agent_sha256) VALUES ('V42', '0.1.0', '${SHA_B}')`);
  env.DB.raw.exec(`INSERT INTO monitor_control (scope, mode, note, updated_at) VALUES ('V42', 'off', 'why', datetime('now'))
                   ON CONFLICT (scope) DO UPDATE SET mode=excluded.mode, note=excluded.note, updated_at=excluded.updated_at`);
  const body = await (await post({ checkins: [checkin()] })).json();
  assert.equal(body.control.mode, "off");
  assert.deepEqual(body.control.agent, { version: "0.1.0", sha256: SHA_B });
});
