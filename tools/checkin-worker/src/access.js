// Verify the Cloudflare Access JWT ourselves so a misconfigured or disabled
// Access policy fails closed instead of publishing the fleet list.

let certCache = { team: null, keys: null, fetchedAt: 0 };
const CERT_TTL_MS = 60 * 60 * 1000;

export async function accessIdentity(request, env) {
  if (env.DEV_ALLOW_UNAUTHENTICATED === "true") return { email: "local-dev" };

  const team = env.ACCESS_TEAM_DOMAIN;
  const aud = env.ACCESS_AUD;
  if (!team || !aud || team.startsWith("REPLACE") || aud.startsWith("REPLACE")) return null;

  const token = request.headers.get("Cf-Access-Jwt-Assertion");
  if (!token) return null;
  const parts = token.split(".");
  if (parts.length !== 3) return null;

  let header, payload;
  try {
    header = JSON.parse(b64urlText(parts[0]));
    payload = JSON.parse(b64urlText(parts[1]));
  } catch {
    return null;
  }
  if (header.alg !== "RS256") return null;

  const jwk = (await teamKeys(team)).find((k) => k.kid === header.kid);
  if (!jwk) return null;
  const key = await crypto.subtle.importKey(
    "jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"],
  );
  const valid = await crypto.subtle.verify(
    "RSASSA-PKCS1-v1_5", key, b64urlBytes(parts[2]),
    new TextEncoder().encode(`${parts[0]}.${parts[1]}`),
  );
  if (!valid) return null;

  const now = Math.floor(Date.now() / 1000);
  const auds = Array.isArray(payload.aud) ? payload.aud : [payload.aud];
  if (!auds.includes(aud)) return null;
  if (payload.iss !== `https://${team}`) return null;
  if (typeof payload.exp !== "number" || payload.exp < now) return null;
  if (typeof payload.nbf === "number" && payload.nbf > now + 60) return null;
  return { email: payload.email || null };
}

async function teamKeys(team) {
  const fresh = certCache.team === team && Date.now() - certCache.fetchedAt < CERT_TTL_MS;
  if (fresh && certCache.keys) return certCache.keys;
  const resp = await fetch(`https://${team}/cdn-cgi/access/certs`);
  if (!resp.ok) throw new Error(`Access certs fetch returned ${resp.status}`);
  const { keys } = await resp.json();
  certCache = { team, keys: keys || [], fetchedAt: Date.now() };
  return certCache.keys;
}

function b64urlBytes(s) {
  const b64 = s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4);
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function b64urlText(s) {
  return new TextDecoder().decode(b64urlBytes(s));
}
