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
  assert.equal(main.last_seen, "2026-09-22T10:00:00.000Z");
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

test("a heartbeat moves last_seen but keeps the last full reading", async () => {
  const full = checkin({ reason: "state-change", telemetry: telemetryDoc({ status: "PASS", blockers: [] }) });
  const beat = { checkinId: "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee", sentAt: "2026-09-20T15:00:00Z",
                 reason: "heartbeat", venueId: "V42", vpuName: "Main Gym", status: "PASS" };
  const r = await (await post({ secret: SECRET, checkins: [full, beat] })).json();
  assert.deepEqual(r.results.map((x) => x.status), ["inserted", "inserted"]);
  const u = env.DB.raw.prepare("SELECT * FROM unit_status").get();
  assert.equal(u.last_seen, "2026-09-20T15:00:00.000Z");
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
