// Daily heartbeat: if the sink received too few check-ins in the window, tell
// Slack. This is what would have caught the lapsed-sheet outage on day one.

export async function runAlertCheck(env, now = new Date()) {
  const hours = positiveInt(env.ALERT_WINDOW_HOURS, 24);
  const min = positiveInt(env.ALERT_MIN_CHECKINS, 1);
  const since = new Date(now.getTime() - hours * 3600 * 1000).toISOString();

  let text = null;
  try {
    const recent = await env.DB.prepare(
      "SELECT COUNT(*) AS n, COUNT(DISTINCT COALESCE(serial_number,'') || '|' || COALESCE(hostname,'')) AS units FROM checkins WHERE received_at >= ?",
    ).bind(since).first();
    if ((recent && recent.n) >= min) return { alerted: false, count: recent.n };

    const last = await env.DB.prepare("SELECT MAX(received_at) AS at FROM checkins").first();
    const lastText = last && last.at ? `last one received ${formatUtc(last.at)}` : "none received yet";
    text =
      `:warning: *Pulse check-ins:* ${recent ? recent.n : 0} received in the last ${hours} h ` +
      `(expected at least ${min}; ${lastText}). ` +
      "Either nobody launched Pulse, or VPUs can't reach the check-in Worker. " +
      "Unsent check-ins stay queued on each VPU and replay on its next launch.";
  } catch (e) {
    text = `:rotating_light: *Pulse check-ins:* the daily check could not read the database (${e && e.message ? e.message : e}).`;
  }

  await postSlack(env, text);
  return { alerted: true, text };
}

async function postSlack(env, text) {
  if (!env.SLACK_WEBHOOK_URL) {
    console.error("SLACK_WEBHOOK_URL not set; alert not sent:", text);
    return;
  }
  const resp = await fetch(env.SLACK_WEBHOOK_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!resp.ok) throw new Error(`Slack webhook returned ${resp.status}`);
}

function positiveInt(v, fallback) {
  const n = Number.parseInt(v, 10);
  return Number.isFinite(n) && n > 0 ? n : fallback;
}

function formatUtc(iso) {
  return iso.replace("T", " ").replace(/:\d\d(\.\d+)?Z$/, " UTC");
}
