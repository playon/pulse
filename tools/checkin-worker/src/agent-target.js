// POST /agent-target on the admin Worker (PV-85): set or clear the fleet
// agent build for the fleet or one unit. Pulse Vitals calls it over a service
// binding, forwarding the viewer's Cloudflare Access token; Vitals itself never
// writes pulse-checkins.
//
// Fail closed at every step: no verified Access identity, an identity not in
// FLEET_CONTROL_EDITORS, a body that isn't exactly the documented shape, a
// unit nobody has heard from, or a release that can't be checked all leave the
// table as it was. A target is saved only when the playon/pulse release
// agent-v<version> exists and its pulse-agent-<version>.zip has that SHA-256.
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

export async function handleAgentTarget(request, env) {
  if (request.method !== "POST") return fail(405, "method-not-allowed", "POST only");
  const who = await accessIdentity(request, env);
  if (!who) return fail(403, "forbidden", "no valid Access identity");
  const email = (who.email || "").toLowerCase();
  const editors = String(env.FLEET_CONTROL_EDITORS || "")
    .split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
  if (!email || !editors.includes(email)) return fail(403, "not-an-editor", "this identity can't change fleet control");

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

  const current = await env.DB.prepare(
    "SELECT agent_version, agent_sha256 FROM monitor_control WHERE scope = ?",
  ).bind(scope).first();
  if (scope !== "fleet" && !current) {
    // A new unit row only for a unit the ingest would match: its key is the
    // venue id, else the VPU name (ingest.js controlFor).
    const known = await env.DB.prepare(
      "SELECT 1 AS ok FROM unit_latest WHERE unit_key = ?1 AND (venue_id = ?1 OR vpu_name = ?1) LIMIT 1",
    ).bind(scope).first();
    if (!known) return fail(404, "unknown-scope", "no unit has checked in with that venue id or VPU name");
  }

  if (target) {
    const check = await checkRelease(env, target.version, target.sha256);
    if (!check.ok) return fail(check.status, check.error, check.message);
  }

  const at = new Date().toISOString();
  const previous = current && current.agent_version
    ? { version: current.agent_version, sha256: current.agent_sha256 } : null;
  const v = target ? target.version : null;
  const h = target ? target.sha256 : null;
  const statements = [];
  if (target || scope === "fleet") {
    statements.push(env.DB.prepare(
      `INSERT INTO monitor_control (scope, agent_version, agent_sha256, agent_note, agent_set_by, agent_set_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?)
       ON CONFLICT (scope) DO UPDATE SET agent_version = excluded.agent_version, agent_sha256 = excluded.agent_sha256,
         agent_note = excluded.agent_note, agent_set_by = excluded.agent_set_by,
         agent_set_at = excluded.agent_set_at, updated_at = excluded.updated_at`,
    ).bind(scope, v, h, note, email, at, at));
  } else {
    // Clearing a unit: it follows the fleet row again. No row, nothing to clear.
    statements.push(env.DB.prepare(
      `UPDATE monitor_control SET agent_version = NULL, agent_sha256 = NULL, agent_note = ?,
         agent_set_by = ?, agent_set_at = ?, updated_at = ? WHERE scope = ?`,
    ).bind(note, email, at, at, scope));
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
export async function checkRelease(env, version, sha256) {
  const tag = `agent-v${version}`;
  const asset = `pulse-agent-${version}.zip`;
  const headers = { "User-Agent": "pulse-checkin-admin", Accept: "application/vnd.github+json" };
  if (env.GITHUB_TOKEN) headers.Authorization = `Bearer ${env.GITHUB_TOKEN}`;
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
  if (hashes.some((h) => h !== sha256)) {
    return bad(422, "hash-mismatch", `${asset} in ${tag} doesn't have that SHA-256`);
  }
  return { ok: true };
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
