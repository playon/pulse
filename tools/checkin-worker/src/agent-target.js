// POST /agent-target on the admin Worker (PV-85): set or clear the fleet
// agent build for the fleet or one unit. Pulse Vitals calls it over a service
// binding, forwarding the viewer's Cloudflare Access token; Vitals itself never
// writes pulse-checkins.
//
// Fail closed at every step: no verified Access identity, an identity not in
// FLEET_CONTROL_EDITORS, a body that isn't exactly the documented shape, a
// unit nobody has heard from, or a release that can't be checked all leave
// agent_target (migration 0020) as it was. A target is saved only when the
// playon/pulse release agent-v<version> exists and its
// pulse-agent-<version>.zip has that SHA-256. Pins never touch
// monitor_control, whose unit rows decide a unit's mode.
// There is no URL in the request: the agent builds it from the version.

import { accessIdentity } from "./access.js";

const REPO = "playon/pulse";
const VERSION_RE = /^\d{1,4}\.\d{1,4}\.\d{1,6}$/;   // ingest.js TARGET_VERSION_RE, runner.py VERSION_RE
const SHA256_RE = /^[0-9a-f]{64}$/;
const SCOPE_RE = /^[\x20-\x7E]{1,128}$/;
const MAX_BODY_BYTES = 4 * 1024;
const MAX_NOTE = 200;
const MAX_HASH_FILE_BYTES = 1024;
const GITHUB_TIMEOUT_MS = 10_000;
const TAG_RE = /^agent-v(\d{1,4}\.\d{1,4}\.\d{1,6})$/;
const MAX_LISTED = 10;        // newest published builds the target dialog offers

// Who may use the fleet-control endpoints: a verified Access identity whose
// email is in FLEET_CONTROL_EDITORS (unset: nobody). Returns { email } or { response }.
async function requireEditor(request, env) {
  const who = await accessIdentity(request, env);
  if (!who) return { response: fail(403, "forbidden", "no valid Access identity") };
  const email = (who.email || "").toLowerCase();
  const editors = String(env.FLEET_CONTROL_EDITORS || "")
    .split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
  if (!email || !editors.includes(email)) {
    return { response: fail(403, "not-an-editor", "this identity can't change fleet control") };
  }
  return { email };
}

export async function handleAgentTarget(request, env) {
  if (request.method !== "POST") return fail(405, "method-not-allowed", "POST only");
  const gate = await requireEditor(request, env);
  if (gate.response) return gate.response;
  const { email } = gate;

  if (!/^application\/json\b/i.test(request.headers.get("Content-Type") || "")) {
    return fail(415, "unsupported-media-type", "send application/json");
  }
  if (Number(request.headers.get("Content-Length") || 0) > MAX_BODY_BYTES) return fail(413, "too-large", "body over 4 KB");
  const text = await request.text();
  if (new TextEncoder().encode(text).length > MAX_BODY_BYTES) return fail(413, "too-large", "body over 4 KB");
  let body;
  try {
    body = JSON.parse(text);
  } catch {
    return fail(400, "bad-request", "body is not JSON");
  }
  const parsed = parse(body);
  if (parsed.error) return fail(400, "bad-request", parsed.error);
  const { scope, target, note } = parsed;
  // Workers share egress IPs and GitHub allows 60 anonymous calls an hour per
  // IP, so without a token a set fails at random. Refuse up front instead.
  if (target && !env.GITHUB_TOKEN) {
    return fail(500, "not-configured", "the admin Worker has no GITHUB_TOKEN secret, so it can't check releases");
  }

  // Pins live in agent_target (migration 0020), never in monitor_control:
  // a monitor_control row would decide the unit's mode.
  const current = await env.DB.prepare(
    "SELECT version, sha256 FROM agent_target WHERE scope = ?",
  ).bind(scope).first();
  if (scope !== "fleet" && !current) {
    // A new unit pin only for a unit the ingest would match: its key is the
    // venue id, else the VPU name (ingest.js controlFor).
    const known = await env.DB.prepare(
      "SELECT 1 AS ok FROM unit_latest WHERE unit_key = ?1 AND (venue_id = ?1 OR vpu_name = ?1) LIMIT 1",
    ).bind(scope).first();
    if (!known) return fail(404, "unknown-scope", "no unit has checked in with that venue id or VPU name");
  }

  const previous = current ? { version: current.version, sha256: current.sha256 } : null;
  if (!target && !previous) {
    // Nothing pinned, nothing to clear: no write, no log row.
    return Response.json({ ok: true, scope, target: null, previous: null, setBy: email, setAt: null, note },
                         { headers: { "Cache-Control": "no-store" } });
  }

  if (target) {
    const check = await checkRelease(env, target.version, target.sha256);
    if (!check.ok) return fail(check.status, check.error, check.message);
  }

  const at = new Date().toISOString();
  const v = target ? target.version : null;
  const h = target ? target.sha256 : null;
  const statements = [];
  if (target) {
    statements.push(env.DB.prepare(
      `INSERT INTO agent_target (scope, version, sha256, note, set_by, set_at) VALUES (?, ?, ?, ?, ?, ?)
       ON CONFLICT (scope) DO UPDATE SET version = excluded.version, sha256 = excluded.sha256,
         note = excluded.note, set_by = excluded.set_by, set_at = excluded.set_at`,
    ).bind(scope, v, h, note, email, at));
  } else {
    // Clearing: a unit follows the fleet's pin again; the fleet stops moving anyone.
    statements.push(env.DB.prepare("DELETE FROM agent_target WHERE scope = ?").bind(scope));
  }
  statements.push(env.DB.prepare(
    `INSERT INTO agent_target_log (at, scope, version, sha256, previous_version, previous_sha256, set_by, note)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
  ).bind(at, scope, v, h, previous ? previous.version : null, previous ? previous.sha256 : null, email, note));
  try {
    await env.DB.batch(statements);
  } catch (e) {
    console.error("agent target write failed", e && e.message);
    return fail(500, "storage", "couldn't save the target");
  }
  return Response.json({ ok: true, scope, target, previous, setBy: email, setAt: at, note },
                       { headers: { "Cache-Control": "no-store" } });
}

// Exactly { scope, target, note? }: anything else is refused, not ignored.
function parse(body) {
  if (!body || typeof body !== "object" || Array.isArray(body)) return { error: "body must be an object" };
  for (const k of Object.keys(body)) {
    if (!["scope", "target", "note"].includes(k)) return { error: `unknown field ${JSON.stringify(k.slice(0, 32))}` };
  }
  const scope = body.scope;
  if (typeof scope !== "string" || !SCOPE_RE.test(scope) || scope !== scope.trim()) {
    return { error: "scope must be \"fleet\" or a unit's venue id (else VPU name)" };
  }
  if (!("target" in body)) return { error: "target is required: { version, sha256 } to set, null to clear" };
  let target = null;
  if (body.target !== null) {
    const t = body.target;
    if (!t || typeof t !== "object" || Array.isArray(t)) return { error: "target must be an object or null" };
    for (const k of Object.keys(t)) {
      if (!["version", "sha256"].includes(k)) return { error: `unknown target field ${JSON.stringify(k.slice(0, 32))}` };
    }
    if (typeof t.version !== "string" || !VERSION_RE.test(t.version)) return { error: "target.version must be N.N.N" };
    if (typeof t.sha256 !== "string" || !SHA256_RE.test(t.sha256)) {
      return { error: "target.sha256 must be 64 lowercase hex characters" };
    }
    target = { version: t.version, sha256: t.sha256 };
  }
  let note = null;
  if (body.note !== undefined && body.note !== null) {
    if (typeof body.note !== "string") return { error: "note must be a string" };
    // Control and bidi-override characters out; whitespace collapsed.
    note = body.note.replace(/[\p{Cc}​-‏‪-‮⁦-⁩]/gu, " ")
      .replace(/\s+/g, " ").trim().slice(0, MAX_NOTE) || null;
  }
  return { scope, target, note };
}

// Is there a published agent-v<version> release whose zip has this hash?
// The hash GitHub computed for the asset (asset.digest) and the .sha256 file
// the release workflow published must both agree when present, and at least
// one must be.
//
// A good answer is remembered for an hour (here and in the colo's cache):
// agent-v* releases are never replaced (agent-release.yml refuses an existing
// tag), and Vitals pins up to 100 units one request at a time, which would
// otherwise be 100 lookups of the same release. Failures are never remembered.
export async function checkRelease(env, version, sha256) {
  const key = `${version}/${sha256}`;
  if ((checked.get(key) || 0) > Date.now()) return { ok: true };
  const cacheUrl = `https://pulse-checkin-admin.cache/release-check/${key}`;
  const cache = typeof caches !== "undefined" && caches.default ? caches.default : null;
  try {
    if (cache && await cache.match(cacheUrl)) {
      checked.set(key, Date.now() + CHECK_TTL_MS);
      return { ok: true };
    }
  } catch {
    // no cache: ask GitHub
  }
  const result = await lookUpRelease(env, version, sha256);
  if (result.ok) {
    checked.set(key, Date.now() + CHECK_TTL_MS);
    if (checked.size > 64) checked.delete(checked.keys().next().value);
    try {
      if (cache) {
        await cache.put(cacheUrl, new Response("ok", {
          headers: { "Cache-Control": `max-age=${CHECK_TTL_MS / 1000}` },
        }));
      }
    } catch {
      // remembering is only a saving
    }
  }
  return result;
}

const CHECK_TTL_MS = 60 * 60 * 1000;
const checked = new Map();     // "version/sha256" -> ms until which it's known good

export function forgetReleaseChecks() {
  checked.clear();
}

function githubHeaders(env) {
  const headers = { "User-Agent": "pulse-checkin-admin", Accept: "application/vnd.github+json" };
  if (env.GITHUB_TOKEN) headers.Authorization = `Bearer ${env.GITHUB_TOKEN}`;
  return headers;
}

// The SHA-256s a published release states for its zip: GitHub's own digest of
// the asset and the .sha256 file the release workflow published. Every one
// found goes in `hashes`; the callers decide what disagreement means.
async function releaseHashes(env, version) {
  const tag = `agent-v${version}`;
  const asset = `pulse-agent-${version}.zip`;
  const headers = githubHeaders(env);
  let release;
  try {
    const r = await timed(`https://api.github.com/repos/${REPO}/releases/tags/${tag}`, { headers });
    if (!r.ok) await r.body?.cancel();
    if (r.status === 404) return bad(422, "release-not-found", `no published release ${tag}`);
    if (!r.ok) return bad(502, "release-check-failed", `GitHub answered ${r.status}`);
    release = await r.json();
  } catch (e) {
    return bad(502, "release-check-failed", "couldn't reach GitHub");
  }
  if (!release || release.draft || release.tag_name !== tag) {
    return bad(422, "release-not-found", `no published release ${tag}`);
  }
  const zip = (release.assets || []).find((a) => a && a.name === asset && a.state === "uploaded");
  if (!zip) return bad(422, "release-not-found", `${tag} has no ${asset}`);

  const hashes = [];
  if (typeof zip.digest === "string" && zip.digest.startsWith("sha256:")) hashes.push(zip.digest.slice(7).toLowerCase());
  if ((release.assets || []).some((a) => a && a.name === `${asset}.sha256` && a.state === "uploaded")) {
    // Built from the tag, like the agent's own URL; not taken from the reply.
    const url = `https://github.com/${REPO}/releases/download/${tag}/${asset}.sha256`;
    try {
      const r = await timed(url, { headers: { "User-Agent": "pulse-checkin-admin" }, redirect: "follow" });
      if (!r.ok) {
        await r.body?.cancel();
        return bad(502, "release-check-failed", `the .sha256 file answered ${r.status}`);
      }
      const text = (await r.text()).slice(0, MAX_HASH_FILE_BYTES);
      const first = text.trim().split(/\s+/)[0].toLowerCase();
      if (!SHA256_RE.test(first)) return bad(422, "release-has-no-hash", `${asset}.sha256 isn't a SHA-256`);
      hashes.push(first);
    } catch {
      return bad(502, "release-check-failed", "couldn't fetch the .sha256 file");
    }
  }
  if (!hashes.length) return bad(422, "release-has-no-hash", `${tag} publishes no SHA-256 for ${asset}`);
  return { ok: true, hashes, tag, asset };
}

async function lookUpRelease(env, version, sha256) {
  const found = await releaseHashes(env, version);
  if (!found.ok) return found;
  if (found.hashes.some((h) => h !== sha256)) {
    return bad(422, "hash-mismatch", `${found.asset} in ${found.tag} doesn't have that SHA-256`);
  }
  return { ok: true };
}

// GET /agent-releases: the published agent builds the target dialog offers.
// GET /agent-releases/<version>: that build's SHA-256, taken from GitHub, so an
// editor never types or pastes one. Same gate as POST /agent-target (a verified
// Access identity in FLEET_CONTROL_EDITORS) and the same fail-closed reading of
// the release: no hash, or a digest and a .sha256 file that disagree, is an
// error and never a guess. Read-only. POST /agent-target still checks the pair
// it is sent, so what the editor was shown is what gets saved or refused.
export async function handleAgentReleases(request, env) {
  if (request.method !== "GET") return fail(405, "method-not-allowed", "GET only");
  const gate = await requireEditor(request, env);
  if (gate.response) return gate.response;
  if (!env.GITHUB_TOKEN) {
    return fail(500, "not-configured", "the admin Worker has no GITHUB_TOKEN secret, so it can't read releases");
  }
  const rest = new URL(request.url).pathname.slice("/agent-releases".length).replace(/^\//, "");
  if (!rest) return listReleases(env);
  if (!VERSION_RE.test(rest)) return fail(400, "bad-request", "version must be N.N.N");
  const found = await releaseHashes(env, rest);
  if (!found.ok) return fail(found.status, found.error, found.message);
  const unique = [...new Set(found.hashes)];
  if (unique.length !== 1) {
    return fail(422, "hash-mismatch", `GitHub's digest and the .sha256 file for ${found.asset} disagree`);
  }
  return Response.json({ ok: true, version: rest, sha256: unique[0] }, { headers: { "Cache-Control": "no-store" } });
}

async function listReleases(env) {
  let list;
  try {
    const r = await timed(`https://api.github.com/repos/${REPO}/releases?per_page=30`, { headers: githubHeaders(env) });
    if (!r.ok) {
      await r.body?.cancel();
      return fail(502, "release-check-failed", `GitHub answered ${r.status}`);
    }
    list = await r.json();
  } catch {
    return fail(502, "release-check-failed", "couldn't reach GitHub");
  }
  if (!Array.isArray(list)) return fail(502, "release-check-failed", "GitHub's release list wasn't a list");
  const releases = [];
  for (const rel of list) {
    const m = rel && !rel.draft && typeof rel.tag_name === "string" ? rel.tag_name.match(TAG_RE) : null;
    if (!m) continue;
    const version = m[1];
    const zipped = (rel.assets || []).some((a) => a && a.name === `pulse-agent-${version}.zip` && a.state === "uploaded");
    if (!zipped) continue;
    releases.push({ version, publishedAt: typeof rel.published_at === "string" ? rel.published_at : null });
  }
  return Response.json({ ok: true, releases: releases.slice(0, MAX_LISTED) }, { headers: { "Cache-Control": "no-store" } });
}

async function timed(url, init) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), GITHUB_TIMEOUT_MS);
  try {
    return await fetch(url, { ...init, signal: ctl.signal });
  } finally {
    clearTimeout(t);
  }
}

function bad(status, error, message) {
  return { ok: false, status, error, message };
}

function fail(status, error, message) {
  return Response.json({ ok: false, error, message }, { status, headers: { "Cache-Control": "no-store" } });
}
