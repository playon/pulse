// POST /agent-target on the admin Worker (PV-85): Pulse Vitals' one write.
import { test, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { generateKeyPairSync, createSign } from "node:crypto";
import worker from "../src/index.js";
import { fakeD1 } from "./fake-d1.js";

const TEAM = "pulse-test.cloudflareaccess.com";
const ADMIN_AUD = "aud-admin";
const VITALS_AUD = "aud-vitals";
const EDITOR = "ian.moore@playonsports.com";
const SHA = "a".repeat(64);
const { privateKey, publicKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
const JWK = { ...publicKey.export({ format: "jwk" }), kid: "k1", alg: "RS256" };

let env;
let realFetch;
let calls;
let releases;        // tag -> release JSON (or a status number)
let hashFiles;       // tag -> text (or a status number)

beforeEach(() => {
  env = {
    ROLE: "admin", DB: fakeD1(), ACCESS_TEAM_DOMAIN: TEAM, ACCESS_AUD: `${ADMIN_AUD}, ${VITALS_AUD}`,
    FLEET_CONTROL_EDITORS: `${EDITOR},someone@playonsports.com`,
  };
  calls = [];
  releases = { "agent-v0.2.0": release("0.2.0", { digest: `sha256:${SHA}` }) };
  hashFiles = { "agent-v0.2.0": `${SHA}  pulse-agent-0.2.0.zip\n` };
  realFetch = globalThis.fetch;
  globalThis.fetch = async (input, init = {}) => {
    const url = String(input);
    calls.push({ url, headers: init.headers || {} });
    if (url === `https://${TEAM}/cdn-cgi/access/certs`) return Response.json({ keys: [JWK] });
    let m = url.match(/^https:\/\/api\.github\.com\/repos\/playon\/pulse\/releases\/tags\/(agent-v[\d.]+)$/);
    if (m) {
      const r = releases[m[1]];
      if (r === undefined) return new Response("{}", { status: 404 });
      return typeof r === "number" ? new Response("x", { status: r }) : Response.json(r);
    }
    m = url.match(/^https:\/\/github\.com\/playon\/pulse\/releases\/download\/(agent-v[\d.]+)\/pulse-agent-[\d.]+\.zip\.sha256$/);
    if (m) {
      const t = hashFiles[m[1]];
      if (t === undefined) return new Response("Not Found", { status: 404 });
      return typeof t === "number" ? new Response("x", { status: t }) : new Response(t);
    }
    throw new Error(`unexpected fetch ${url}`);
  };
  seenUnit("V42", "Main Gym");
  seenUnit(null, "Gym Two");
});
afterEach(() => {
  globalThis.fetch = realFetch;
});

function release(version, { digest, sha256File = true, draft = false } = {}) {
  const assets = [{ name: `pulse-agent-${version}.zip`, state: "uploaded", digest }];
  if (sha256File) assets.push({ name: `pulse-agent-${version}.zip.sha256`, state: "uploaded" });
  return { tag_name: `agent-v${version}`, draft, assets };
}

function seenUnit(venue, name) {
  env.DB.raw.prepare("INSERT INTO unit_latest (unit_key, venue_id, vpu_name) VALUES (?, ?, ?)")
    .run(venue || name, venue, name);
}

function b64url(buf) {
  return Buffer.from(buf).toString("base64url");
}
function token(extra = {}) {
  const now = Math.floor(Date.now() / 1000);
  const claims = { aud: [VITALS_AUD], iss: `https://${TEAM}`, exp: now + 600, iat: now, email: EDITOR, ...extra };
  const head = b64url(JSON.stringify({ alg: "RS256", kid: "k1" }));
  const body = b64url(JSON.stringify(claims));
  return `${head}.${body}.${b64url(createSign("RSA-SHA256").update(`${head}.${body}`).sign(privateKey))}`;
}

// What Vitals does: env.CHECKIN_ADMIN.fetch(...) with its viewer's token.
async function call(body, { jwt = token(), type = "application/json", method = "POST", e = env } = {}) {
  const headers = { "Content-Type": type };
  if (jwt) headers["Cf-Access-Jwt-Assertion"] = jwt;
  const r = await worker.fetch(new Request("https://pulse-checkin-admin/agent-target", {
    method, headers, body: method === "GET" ? undefined : (typeof body === "string" ? body : JSON.stringify(body)),
  }), e);
  return { status: r.status, body: await r.json(), headers: r.headers };
}

function row(scope) {
  return env.DB.raw.prepare("SELECT * FROM monitor_control WHERE scope = ?").get(scope);
}
function log() {
  return env.DB.raw.prepare("SELECT * FROM agent_target_log ORDER BY id").all();
}
const SET = { scope: "fleet", target: { version: "0.2.0", sha256: SHA }, note: "canary went well" };

// ── who may call it ──

test("no token, a forged token, the wrong audience: 403 and nothing written", async () => {
  const forged = token().replace(/\.[^.]+$/, ".AAAA");
  for (const jwt of [null, forged, token({ aud: ["someone-else"] }), token({ exp: 1 })]) {
    const r = await call(SET, { jwt });
    assert.equal(r.status, 403);
    assert.equal(r.body.error, "forbidden");
  }
  assert.equal(row("fleet").agent_version, null);
  assert.equal(log().length, 0);
});

test("Access not configured: 403 even with a good token", async () => {
  for (const e of [{ ...env, ACCESS_AUD: "" }, { ...env, ACCESS_AUD: `${VITALS_AUD},REPLACE_ME` }]) {
    assert.equal((await call(SET, { e })).status, 403);
  }
});

test("only listed editors may write, and no list means nobody", async () => {
  let r = await call(SET, { jwt: token({ email: "viewer@playonsports.com" }) });
  assert.equal(r.status, 403);
  assert.equal(r.body.error, "not-an-editor");
  r = await call(SET, { e: { ...env, FLEET_CONTROL_EDITORS: undefined } });
  assert.equal(r.status, 403);
  r = await call(SET, { jwt: token({ email: undefined }) });
  assert.equal(r.status, 403);
  assert.equal(log().length, 0);
});

test("the admin app's own token works too, and the email is matched case-blind", async () => {
  const r = await call(SET, { jwt: token({ aud: ADMIN_AUD, email: "Ian.Moore@PlayOnSports.com" }) });
  assert.equal(r.status, 200);
  assert.equal(r.body.setBy, EDITOR);
});

// ── setting and clearing ──

test("sets the fleet target after checking the release, and records who and when", async () => {
  const r = await call(SET);
  assert.equal(r.status, 200, JSON.stringify(r.body));
  assert.equal(r.headers.get("Cache-Control"), "no-store");
  assert.deepEqual(
    { ...r.body, setAt: undefined },
    { ok: true, scope: "fleet", target: { version: "0.2.0", sha256: SHA }, previous: null,
      setBy: EDITOR, setAt: undefined, note: "canary went well" },
  );
  const f = row("fleet");
  assert.equal(f.agent_version, "0.2.0");
  assert.equal(f.agent_sha256, SHA);
  assert.equal(f.agent_set_by, EDITOR);
  assert.equal(f.agent_set_at, r.body.setAt);
  assert.equal(f.agent_note, "canary went well");
  assert.equal(f.mode, "on");                       // the mode and its note are left alone
  assert.equal(f.note, "default");
  const [entry] = log();
  assert.equal(entry.scope, "fleet");
  assert.equal(entry.version, "0.2.0");
  assert.equal(entry.set_by, EDITOR);
  assert.ok(calls.some((c) => c.url.includes("/releases/tags/agent-v0.2.0")));
});

test("the ingest hands the new target to units", async () => {
  await call(SET);
  const ingestEnv = { ...env, ROLE: "ingest" };
  const r = await worker.fetch(new Request("https://w.test/checkin", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ checkins: [{ checkinId: "11111111-2222-3333-4444-555555555555",
      sentAt: new Date().toISOString(), venueId: "V42", vpuName: "Main Gym", readiness: { status: "PASS" } }] }),
  }), ingestEnv);
  assert.deepEqual((await r.json()).control.agent, { version: "0.2.0", sha256: SHA });
});

test("a unit row: created for a known unit, keyed by venue id, else VPU name; mode untouched", async () => {
  let r = await call({ scope: "V42", target: { version: "0.2.0", sha256: SHA } });
  assert.equal(r.status, 200);
  assert.equal(row("V42").agent_version, "0.2.0");
  assert.equal(row("V42").mode, "on");
  r = await call({ scope: "Gym Two", target: { version: "0.2.0", sha256: SHA } });
  assert.equal(r.status, 200);
  r = await call({ scope: "Main Gym", target: { version: "0.2.0", sha256: SHA } });   // has a venue id: not its key
  assert.equal(r.status, 404);
  assert.equal(r.body.error, "unknown-scope");
  r = await call({ scope: "V99", target: { version: "0.2.0", sha256: SHA } });
  assert.equal(r.status, 404);
  assert.equal(row("V99"), undefined);
});

test("a held-back unit keeps its mode when its pin changes", async () => {
  env.DB.raw.exec("INSERT INTO monitor_control (scope, mode, note) VALUES ('V42', 'off', 'leak hunt')");
  await call({ scope: "V42", target: { version: "0.2.0", sha256: SHA } });
  const v = row("V42");
  assert.deepEqual([v.mode, v.note, v.agent_version], ["off", "leak hunt", "0.2.0"]);
});

test("clearing: the unit follows the fleet again; the fleet stops moving anyone", async () => {
  await call(SET);
  await call({ scope: "V42", target: { version: "0.2.0", sha256: SHA } });
  let r = await call({ scope: "V42", target: null, note: "back with the fleet" });
  assert.equal(r.status, 200);
  assert.deepEqual(r.body.previous, { version: "0.2.0", sha256: SHA });
  assert.equal(r.body.target, null);
  assert.equal(row("V42").agent_version, null);
  r = await call({ scope: "fleet", target: null });
  assert.equal(r.status, 200);
  assert.equal(row("fleet").agent_version, null);
  assert.equal(row("fleet").agent_sha256, null);
  assert.deepEqual(log().map((l) => [l.scope, l.version, l.previous_version]),
    [["fleet", "0.2.0", null], ["V42", "0.2.0", null], ["V42", null, "0.2.0"], ["fleet", null, "0.2.0"]]);
  // Clearing needs no release check.
  assert.equal(calls.filter((c) => c.url.includes("api.github.com")).length, 2);
});

test("clearing a unit with no row creates none", async () => {
  const r = await call({ scope: "V42", target: null });
  assert.equal(r.status, 200);
  assert.equal(row("V42"), undefined);
});

// ── the release check ──

test("no such release, a draft, no zip asset: 422 and nothing saved", async () => {
  releases["agent-v0.3.0"] = release("0.3.0", { digest: `sha256:${SHA}`, draft: true });
  releases["agent-v0.4.0"] = { tag_name: "agent-v0.4.0", draft: false, assets: [{ name: "other.zip", state: "uploaded" }] };
  for (const version of ["0.9.9", "0.3.0", "0.4.0"]) {
    const r = await call({ scope: "fleet", target: { version, sha256: SHA } });
    assert.equal(r.status, 422, version);
    assert.equal(r.body.error, "release-not-found");
  }
  assert.equal(row("fleet").agent_version, null);
  assert.equal(log().length, 0);
});

test("a hash that isn't the release's: 422 hash-mismatch", async () => {
  const r = await call({ scope: "fleet", target: { version: "0.2.0", sha256: "b".repeat(64) } });
  assert.equal(r.status, 422);
  assert.equal(r.body.error, "hash-mismatch");
  assert.equal(row("fleet").agent_version, null);
});

test("GitHub's digest and the .sha256 file must agree; either alone is enough", async () => {
  hashFiles["agent-v0.2.0"] = `${"c".repeat(64)}  pulse-agent-0.2.0.zip\n`;
  assert.equal((await call(SET)).body.error, "hash-mismatch");
  releases["agent-v0.2.0"] = release("0.2.0", { digest: undefined });       // only the file
  hashFiles["agent-v0.2.0"] = `${SHA}  pulse-agent-0.2.0.zip\n`;
  assert.equal((await call(SET)).status, 200);
  releases["agent-v0.2.0"] = release("0.2.0", { digest: `sha256:${SHA}`, sha256File: false });  // only the digest
  assert.equal((await call(SET)).status, 200);
  releases["agent-v0.2.0"] = release("0.2.0", { digest: undefined, sha256File: false });        // neither
  assert.equal((await call(SET)).body.error, "release-has-no-hash");
});

test("GitHub down or rate-limited: 502 and nothing saved (fail closed)", async () => {
  releases["agent-v0.2.0"] = 403;
  let r = await call(SET);
  assert.equal(r.status, 502);
  assert.equal(r.body.error, "release-check-failed");
  releases["agent-v0.2.0"] = release("0.2.0", { digest: `sha256:${SHA}` });
  hashFiles["agent-v0.2.0"] = 500;
  r = await call(SET);
  assert.equal(r.status, 502);
  globalThis.fetch = async (url) => {
    if (String(url).includes("cloudflareaccess")) return Response.json({ keys: [JWK] });
    throw new TypeError("network down");
  };
  r = await call(SET);
  assert.equal(r.status, 502);
  assert.equal(row("fleet").agent_version, null);
  assert.equal(log().length, 0);
});

test("the release lookups are built from the version, never from the caller", async () => {
  env.GITHUB_TOKEN = "gh-test";
  await call(SET);
  const gh = calls.filter((c) => !c.url.includes("cloudflareaccess"));
  assert.deepEqual(gh.map((c) => c.url), [
    "https://api.github.com/repos/playon/pulse/releases/tags/agent-v0.2.0",
    "https://github.com/playon/pulse/releases/download/agent-v0.2.0/pulse-agent-0.2.0.zip.sha256",
  ]);
  assert.equal(gh[0].headers.Authorization, "Bearer gh-test");
  assert.equal(gh[1].headers.Authorization, undefined);     // the token only goes to the API
});

// ── what the caller sends is untrusted ──

test("anything but the documented shape is refused, and a URL is never accepted", async () => {
  const bad = [
    { ...SET, url: "https://evil.example/agent.zip" },
    { ...SET, target: { ...SET.target, url: "https://evil.example/agent.zip" } },
    { ...SET, target: { version: "v0.2.0", sha256: SHA } },
    { ...SET, target: { version: "0.2.0", sha256: SHA.toUpperCase() } },
    { ...SET, target: { version: "0.2.0" } },
    { ...SET, target: "0.2.0" },
    { scope: "fleet" },
    { ...SET, scope: "" },
    { ...SET, scope: " V42" },
    { ...SET, scope: "V42\n" },
    { ...SET, scope: "x".repeat(129) },
    { ...SET, note: 5 },
    [SET],
    "not json",
  ];
  for (const body of bad) {
    const r = await call(body);
    assert.equal(r.status, 400, JSON.stringify(body));
    assert.equal(r.body.error, "bad-request");
  }
  assert.equal(calls.filter((c) => c.url.includes("github")).length, 0);
  assert.equal(log().length, 0);
});

test("wrong method, wrong content type, too big", async () => {
  assert.equal((await call(SET, { method: "GET" })).status, 405);
  assert.equal((await call(SET, { type: "text/plain" })).status, 415);
  assert.equal((await call(SET, { type: "application/x-www-form-urlencoded" })).status, 415);
  assert.equal((await call({ ...SET, note: "n".repeat(5000) })).status, 413);
});

test("the note is cleaned and capped", async () => {
  const r = await call({ ...SET, note: "  a‮b\u0000c\n\td  " + "z".repeat(400) });
  assert.equal(r.status, 200);
  assert.ok(r.body.note.startsWith("a b c d z"));
  assert.equal(r.body.note.length, 200);
  assert.equal(row("fleet").agent_note, r.body.note);
});

test("the read-only admin pages still refuse writes", async () => {
  const r = await worker.fetch(new Request("https://a.test/units.csv", {
    method: "POST", headers: { "Cf-Access-Jwt-Assertion": token({ aud: ADMIN_AUD }) },
  }), env);
  assert.equal(r.status, 405);
});
