import { handleIngest } from "./ingest.js";
import { handleAdmin } from "./admin.js";
import { runAlertCheck } from "./alert.js";

export default {
  async fetch(request, env) {
    try {
      if (env.ROLE === "admin") return await handleAdmin(request, env);
      return await handleIngest(request, env);
    } catch (e) {
      console.error("unhandled", e && e.stack ? e.stack : e);
      return Response.json({ ok: false, error: "internal" }, { status: 500 });
    }
  },

  async scheduled(_event, env, ctx) {
    if (env.ROLE === "admin") return;
    ctx.waitUntil(runAlertCheck(env));
  },
};
