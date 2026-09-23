// The write secret ships inside a public repo, so it only keeps out casual noise.
// Real protection is the shape/size validation and the per-IP rate limit.

const MAX_BODY_BYTES = 64 * 1024;
const MAX_BATCH = 50;
const MAX_FIELD = 128;
const MAX_CODES = 50;
const FUTURE_SKEW_MS = 10 * 60 * 1000;
const CHECKIN_ID_RE = /^[A-Za-z0-9-]{8,64}$/;

const INSERT_SQL = `
INSERT INTO checkins (
  checkin_id, received_at, sent_at, hostname, serial_number, venue_id, vpu_name,
  model, pulse_version, channel, readiness_status, readiness_policy,
  readiness_blockers, readiness_risks, country, source, raw
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pulse', ?)
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
  if (!env.CHECKIN_SECRET) {
    return Response.json({ ok: false, error: "not-configured" }, { status: 503 });
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
  if (!(await secretMatches(body.secret, env.CHECKIN_SECRET))) {
    return Response.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }
  if (!Array.isArray(body.checkins) || body.checkins.length === 0) return badRequest("checkins");
  if (body.checkins.length > MAX_BATCH) return badRequest("batch-too-large");

  const receivedAt = new Date().toISOString();
  const country = (request.cf && request.cf.country) || null;
  const results = [];
  const statements = [];
  const slots = [];

  for (const item of body.checkins) {
    const row = normalize(item, receivedAt);
    if (!row) {
      results.push({ checkinId: idOf(item), status: "invalid" });
      continue;
    }
    slots.push(results.length);
    results.push({ checkinId: row.checkinId, status: null });
    statements.push(
      env.DB.prepare(INSERT_SQL).bind(
        row.checkinId, receivedAt, row.sentAt, row.hostname, row.serialNumber,
        row.venueId, row.vpuName, row.model, row.pulseVersion, row.channel,
        row.readinessStatus, row.readinessPolicy, row.blockers, row.risks,
        country, row.raw,
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
  }

  return Response.json({ ok: true, results });
}

function normalize(item, receivedAt) {
  if (!item || typeof item !== "object" || Array.isArray(item)) return null;
  const checkinId = typeof item.checkinId === "string" ? item.checkinId : "";
  if (!CHECKIN_ID_RE.test(checkinId)) return null;

  const readiness = item.readiness && typeof item.readiness === "object" ? item.readiness : {};
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
    readinessStatus: str(readiness.status),
    readinessPolicy: str(readiness.policyVersion),
    blockers: codes(readiness.blockers),
    risks: codes(readiness.risks),
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
    channel: clean.channel,
    readiness: {
      status: clean.readinessStatus,
      policyVersion: clean.readinessPolicy,
      blockers: clean.blockers && JSON.parse(clean.blockers),
      risks: clean.risks && JSON.parse(clean.risks),
    },
  });
  return clean;
}

function str(v) {
  if (typeof v === "number" && Number.isFinite(v)) v = String(v);
  if (typeof v !== "string") return null;
  const t = v.trim();
  return t ? t.slice(0, MAX_FIELD) : null;
}

function codes(v) {
  if (!Array.isArray(v)) return null;
  const out = v.map(str).filter(Boolean).slice(0, MAX_CODES);
  return JSON.stringify(out);
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

async function secretMatches(given, expected) {
  if (typeof given !== "string" || !given) return false;
  const enc = new TextEncoder();
  const [a, b] = await Promise.all([
    crypto.subtle.digest("SHA-256", enc.encode(given)),
    crypto.subtle.digest("SHA-256", enc.encode(expected)),
  ]);
  const x = new Uint8Array(a);
  const y = new Uint8Array(b);
  let diff = 0;
  for (let i = 0; i < x.length; i++) diff |= x[i] ^ y[i];
  return diff === 0;
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
