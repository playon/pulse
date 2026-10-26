// POST /agent-target on the admin Worker (PV-85): Pulse Vitals' one write.
import { test, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { generateKeyPairSync, createSign } from "node:crypto";
import worker from "../src/index.js";
import { forgetReleaseChecks } from "../src/agent-target.js";
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
let listing;         // GET /releases: an array (or a status number)

beforeEach(() => {
  env = {
    ROLE: "admin", DB: fakeD1(), ACCESS_TEAM_DOMAIN: TEAM, ACCESS_AUD: `${ADMIN_AUD}, ${VITALS_AUD}`,
    FLEET_CONTROL_EDITORS: `${EDITOR},someone@playonsports.com`, GITHUB_TOKEN: "gh-test",
  };
  forgetReleaseChecks();
  calls = [];
  releases = { "agent-v0.2.0": release("0.2.0", { digest: `sha256:${SHA}` }) };
  listing = [release("0.2.0", { digest: `sha256:${SHA}` })];
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
    if (url.startsWith("https://api.github.com/repos/playon/pulse/releases?")) {
      return typeof listing === "number" ? new Response("x", { status: listing }) : Response.json(listing);
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

function pin(scope) {
  return env.DB.raw.prepare("SELECT * FROM agent_target WHERE scope = ?").get(scope);
}
function control(scope) {
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
  assert.equal(pin("fleet"), undefined);
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
  const f = pin("fleet");
  assert.deepEqual([f.version, f.sha256, f.set_by, f.set_at, f.note],
                   ["0.2.0", SHA, EDITOR, r.body.setAt, "canary went well"]);
  const c = control("fleet");                       // the mode row is left alone
  assert.deepEqual([c.mode, c.note, c.agent_version], ["on", "default", null]);
  const [entry] = log();
  assert.equal(entry.scope, "fleet");
  assert.equal(entry.version, "0.2.0");
  assert.equal(entry.set_by, EDITOR);
  assert.ok(calls.some((c) => c.url.includes("/releases/tags/agent-v0.2.0")));
});

// What a unit hears back from the ingest Worker.
async function reply(venueId = "V42", vpuName = "Main Gym") {
  const r = await worker.fetch(new Request("https://w.test/checkin", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ checkins: [{ checkinId: crypto.randomUUID(),
      sentAt: new Date().toISOString(), venueId, vpuName, readiness: { status: "PASS" } }] }),
  }), { ...env, ROLE: "ingest" });
  return (await r.json()).control;
}

test("the ingest hands the new target to units", async () => {
  await call(SET);
  assert.deepEqual((await reply()).agent, { version: "0.2.0", sha256: SHA });
});

test("a unit pin: for a known unit, keyed by venue id, else VPU name; no mode row is made", async () => {
  let r = await call({ scope: "V42", target: { version: "0.2.0", sha256: SHA } });
  assert.equal(r.status, 200);
  assert.equal(pin("V42").version, "0.2.0");
  assert.equal(control("V42"), undefined);
  r = await call({ scope: "Gym Two", target: { version: "0.2.0", sha256: SHA } });
  assert.equal(r.status, 200);
  r = await call({ scope: "Main Gym", target: { version: "0.2.0", sha256: SHA } });   // has a venue id: not its key
  assert.equal(r.status, 404);
  assert.equal(r.body.error, "unknown-scope");
  r = await call({ scope: "V99", target: { version: "0.2.0", sha256: SHA } });
  assert.equal(r.status, 404);
  assert.equal(pin("V99"), undefined);
});

test("fleet OFF: setting and clearing a unit's pin leaves the unit off", async () => {
  env.DB.raw.exec("UPDATE monitor_control SET mode = 'off', note = 'leak hunt' WHERE scope = 'fleet'");
  assert.deepEqual(await reply(), { mode: "off", skip: [] });
  let r = await call({ scope: "V42", target: { version: "0.2.0", sha256: SHA } });
  assert.equal(r.status, 200);
  assert.deepEqual(await reply(), { mode: "off", skip: [], agent: { version: "0.2.0", sha256: SHA } });
  r = await call({ scope: "V42", target: null });
  assert.equal(r.status, 200);
  assert.deepEqual(await reply(), { mode: "off", skip: [] });
  assert.equal(control("V42"), undefined);          // no stray mode row left behind
  // The fleet's own pin doesn't touch its mode either.
  await call(SET);
  assert.deepEqual(await reply(), { mode: "off", skip: [], agent: { version: "0.2.0", sha256: SHA } });
  await call({ scope: "fleet", target: null });
  assert.deepEqual(await reply(), { mode: "off", skip: [] });
  assert.equal(control("fleet").mode, "off");
});

test("a held-back unit keeps its mode, skip and note when its pin changes", async () => {
  env.DB.raw.exec(`INSERT INTO monitor_control (scope, mode, skip, note) VALUES ('V42', 'off', '["Get-PoePower.ps1"]', 'leak hunt')`);
  await call({ scope: "V42", target: { version: "0.2.0", sha256: SHA } });
  await call({ scope: "V42", target: null });
  const v = control("V42");
  assert.deepEqual([v.mode, v.skip, v.note], ["off", '["Get-PoePower.ps1"]', "leak hunt"]);
});

test("clearing: the unit follows the fleet again; the fleet stops moving anyone", async () => {
  await call(SET);
  await call({ scope: "V42", target: { version: "0.2.0", sha256: SHA } });
  let r = await call({ scope: "V42", target: null, note: "back with the fleet" });
  assert.equal(r.status, 200);
  assert.deepEqual(r.body.previous, { version: "0.2.0", sha256: SHA });
  assert.equal(r.body.target, null);
  assert.equal(pin("V42"), undefined);
  r = await call({ scope: "fleet", target: null });
  assert.equal(r.status, 200);
  assert.equal(pin("fleet"), undefined);
  assert.deepEqual(log().map((l) => [l.scope, l.version, l.previous_version]),
    [["fleet", "0.2.0", null], ["V42", "0.2.0", null], ["V42", null, "0.2.0"], ["fleet", null, "0.2.0"]]);
  // Clearing needs no release check, and the second set reused the first's.
  assert.equal(calls.filter((c) => c.url.includes("api.github.com")).length, 1);
});

test("clearing what isn't pinned writes nothing, not even a log row", async () => {
  for (const scope of ["V42", "fleet"]) {
    const r = await call({ scope, target: null });
    assert.equal(r.status, 200);
    assert.equal(r.body.previous, null);
    assert.equal(pin(scope), undefined);
  }
  assert.equal(control("V42"), undefined);
  assert.equal(log().length, 0);
  assert.equal((await call({ scope: "V99", target: null })).status, 404);
});

test("clearing works without GITHUB_TOKEN; setting refuses to run without it", async () => {
  await call(SET);
  delete env.GITHUB_TOKEN;
  forgetReleaseChecks();
  const r = await call(SET);
  assert.equal(r.status, 500);
  assert.equal(r.body.error, "not-configured");
  assert.equal(calls.filter((c) => c.url.includes("api.github.com")).length, 1);
  assert.equal((await call({ scope: "fleet", target: null })).status, 200);
  assert.equal(pin("fleet"), undefined);
});

test("a 100-unit rollout asks GitHub once", async () => {
  for (let i = 0; i < 100; i++) seenUnit(`U${i}`, `Unit ${i}`);
  for (let i = 0; i < 100; i++) {
    assert.equal((await call({ scope: `U${i}`, target: { version: "0.2.0", sha256: SHA } })).status, 200);
  }
  assert.equal(calls.filter((c) => c.url.includes("api.github.com")).length, 1);
  assert.equal(env.DB.raw.prepare("SELECT COUNT(*) AS n FROM agent_target").get().n, 100);
});

test("a failed check isn't remembered", async () => {
  releases["agent-v0.2.0"] = 503;
  assert.equal((await call(SET)).status, 502);
  releases["agent-v0.2.0"] = release("0.2.0", { digest: `sha256:${SHA}` });
  assert.equal((await call(SET)).status, 200);
  assert.equal(calls.filter((c) => c.url.includes("api.github.com")).length, 2);
});

test("a pin set by hand in monitor_control moves to agent_target in the migration", async () => {
  const { DatabaseSync } = await import("node:sqlite");
  const { readdirSync, readFileSync } = await import("node:fs");
  const dir = new URL("../migrations/", import.meta.url).pathname;
  const db = new DatabaseSync(":memory:");
  for (const f of readdirSync(dir).filter((n) => n.endsWith(".sql")).sort()) {
    if (f.startsWith("0020")) {
      db.exec(`UPDATE monitor_control SET agent_version = '0.1.0', agent_sha256 = '${SHA}' WHERE scope = 'fleet'`);
      db.exec("INSERT INTO monitor_control (scope, mode) VALUES ('V42', 'off')");
    }
    db.exec(readFileSync(`${dir}${f}`, "utf8"));
  }
  assert.deepEqual(db.prepare("SELECT scope, version, sha256 FROM agent_target").all().map((r) => ({ ...r })),
                   [{ scope: "fleet", version: "0.1.0", sha256: SHA }]);
  assert.equal(db.prepare("SELECT COUNT(*) AS n FROM monitor_control WHERE agent_version IS NOT NULL").get().n, 0);
  assert.equal(db.prepare("SELECT mode FROM monitor_control WHERE scope = 'V42'").get().mode, "off");
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
  assert.equal(pin("fleet"), undefined);
  assert.equal(log().length, 0);
});

test("a hash that isn't the release's: 422 hash-mismatch", async () => {
  const r = await call({ scope: "fleet", target: { version: "0.2.0", sha256: "b".repeat(64) } });
  assert.equal(r.status, 422);
  assert.equal(r.body.error, "hash-mismatch");
  assert.equal(pin("fleet"), undefined);
});

test("GitHub's digest and the .sha256 file must agree; either alone is enough", async () => {
  hashFiles["agent-v0.2.0"] = `${"c".repeat(64)}  pulse-agent-0.2.0.zip\n`;
  assert.equal((await call(SET)).body.error, "hash-mismatch");
  releases["agent-v0.2.0"] = release("0.2.0", { digest: undefined });       // only the file
  hashFiles["agent-v0.2.0"] = `${SHA}  pulse-agent-0.2.0.zip\n`;
  assert.equal((await call(SET)).status, 200);
  forgetReleaseChecks();                                                                     // each case asks afresh
  releases["agent-v0.2.0"] = release("0.2.0", { digest: `sha256:${SHA}`, sha256File: false });  // only the digest
  assert.equal((await call(SET)).status, 200);
  forgetReleaseChecks();
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
  assert.equal(pin("fleet"), undefined);
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
  assert.equal(pin("fleet").note, r.body.note);
});

test("the read-only admin pages still refuse writes", async () => {
  const r = await worker.fetch(new Request("https://a.test/units.csv", {
    method: "POST", headers: { "Cf-Access-Jwt-Assertion": token({ aud: ADMIN_AUD }) },
  }), env);
  assert.equal(r.status, 405);
});

// ── GET /agent-releases: the builds the target dialog offers, and their hashes ──

async function get(path, { jwt = token(), e = env } = {}) {
  const headers = {};
  if (jwt) headers["Cf-Access-Jwt-Assertion"] = jwt;
  const r = await worker.fetch(new Request(`https://pulse-checkin-admin${path}`, { method: "GET", headers }), e);
  return { status: r.status, body: await r.json(), headers: r.headers };
}

test("the list is the published agent builds, newest first, and nothing else", async () => {
  const other = (tag, extra = {}) => ({ tag_name: tag, draft: false, assets: [], ...extra });
  listing = [
    { ...release("0.3.0", { digest: `sha256:${SHA}` }), published_at: "2026-10-22T12:00:00Z" },
    release("0.2.5", { digest: `sha256:${SHA}`, draft: true }),                  // a draft isn't published
    other("web-v1.4.1"),                                                         // Pulse.Web's own releases
    other("agent-v0.2.4", { assets: [{ name: "notes.txt", state: "uploaded" }] }),  // no zip
    other("agent-v0.2.3", { assets: [{ name: "pulse-agent-0.2.3.zip", state: "starter" }] }), // upload unfinished
    other("agent-v../etc"),
    release("0.2.0", { digest: `sha256:${SHA}` }),
  ];
  const r = await get("/agent-releases");
  assert.equal(r.status, 200);
  assert.deepEqual(r.body.releases, [
    { version: "0.3.0", publishedAt: "2026-10-22T12:00:00Z" },
    { version: "0.2.0", publishedAt: null },
  ]);
  assert.equal(r.headers.get("cache-control"), "no-store");
});

test("the list is capped", async () => {
  listing = Array.from({ length: 25 }, (_, i) => release(`0.${100 - i}.0`, { digest: `sha256:${SHA}` }));
  const r = await get("/agent-releases");
  assert.equal(r.body.releases.length, 10);
  assert.equal(r.body.releases[0].version, "0.100.0");
});

test("GitHub down or answering with something else: 502, never an empty list that reads as 'none published'", async () => {
  listing = 500;
  assert.equal((await get("/agent-releases")).body.error, "release-check-failed");
  listing = { message: "rate limited" };
  const r = await get("/agent-releases");
  assert.equal(r.status, 502);
  assert.equal(r.body.error, "release-check-failed");
});

test("a build's hash comes from GitHub: the digest, the .sha256 file, or both when they agree", async () => {
  assert.deepEqual((await get("/agent-releases/0.2.0")).body, { ok: true, version: "0.2.0", sha256: SHA });
  releases["agent-v0.2.0"] = release("0.2.0", { digest: undefined });             // only the .sha256 file
  assert.equal((await get("/agent-releases/0.2.0")).body.sha256, SHA);
  releases["agent-v0.2.0"] = release("0.2.0", { digest: `sha256:${SHA}`, sha256File: false });  // only the digest
  assert.equal((await get("/agent-releases/0.2.0")).body.sha256, SHA);
});

test("a hash is never guessed: disagreement, none published, no such release, GitHub down", async () => {
  hashFiles["agent-v0.2.0"] = `${"b".repeat(64)}  pulse-agent-0.2.0.zip\n`;      // the file disagrees with the digest
  let r = await get("/agent-releases/0.2.0");
  assert.equal(r.status, 422);
  assert.equal(r.body.error, "hash-mismatch");
  assert.equal(r.body.sha256, undefined);

  releases["agent-v0.2.0"] = release("0.2.0", { digest: undefined, sha256File: false });
  assert.equal((await get("/agent-releases/0.2.0")).body.error, "release-has-no-hash");
  assert.equal((await get("/agent-releases/9.9.9")).body.error, "release-not-found");
  releases["agent-v0.2.0"] = 503;
  assert.equal((await get("/agent-releases/0.2.0")).status, 502);
});

test("only a plain version is looked up", async () => {
  for (const v of ["0.2", "0.2.0.1", "latest", "0.2.0%2F..%2Fx", "v0.2.0"]) {
    const r = await get(`/agent-releases/${v}`);
    assert.equal(r.status, 400, v);
  }
  assert.equal(calls.filter((c) => c.url.includes("github")).length, 0);
});

test("the list and the hash need an editor: no token, a forged one, someone else, no GITHUB_TOKEN", async () => {
  const forged = token().replace(/\.[^.]+$/, ".AAAA");
  for (const path of ["/agent-releases", "/agent-releases/0.2.0"]) {
    for (const jwt of [null, forged, token({ aud: ["someone-else"] })]) {
      const r = await get(path, { jwt });
      assert.equal(r.status, 403, path);
      assert.equal(r.body.error, "forbidden");
    }
    const r = await get(path, { jwt: token({ email: "stranger@example.com" }) });
    assert.equal(r.status, 403);
    assert.equal(r.body.error, "not-an-editor");
  }
  assert.equal(calls.filter((c) => c.url.includes("github")).length, 0);

  const bare = { ...env, GITHUB_TOKEN: undefined };
  assert.equal((await get("/agent-releases", { e: bare })).body.error, "not-configured");
  assert.equal((await get("/agent-releases/0.2.0", { e: bare })).body.error, "not-configured");
});

test("the release endpoints only read", async () => {
  for (const method of ["POST", "PUT", "DELETE"]) {
    const r = await worker.fetch(new Request("https://pulse-checkin-admin/agent-releases", {
      method, headers: { "Cf-Access-Jwt-Assertion": token() },
    }), env);
    assert.equal(r.status, 405);
  }
});

test("what the dialog was shown is what gets saved, or refused if the release changed since", async () => {
  const shown = (await get("/agent-releases/0.2.0")).body;
  const saved = await call({ scope: "fleet", target: { version: shown.version, sha256: shown.sha256 } });
  assert.equal(saved.status, 200);
  assert.equal(pin("fleet").sha256, shown.sha256);

  forgetReleaseChecks();
  hashFiles["agent-v0.2.0"] = `${"c".repeat(64)}  pulse-agent-0.2.0.zip\n`;      // the release moved after the editor looked
  releases["agent-v0.2.0"] = release("0.2.0", { digest: `sha256:${"c".repeat(64)}` });
  const stale = await call({ scope: "fleet", target: { version: shown.version, sha256: shown.sha256 } });
  assert.equal(stale.status, 422);
  assert.equal(stale.body.error, "hash-mismatch");
  assert.equal(pin("fleet").sha256, shown.sha256);                                 // the old pin is untouched
});
