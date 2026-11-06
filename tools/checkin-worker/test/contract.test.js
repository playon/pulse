// PV-42: shared synthetic payloads, exercised through the real ingest Worker
// and real migrations. Vitals seeds from the stored projections certified here.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import worker from "../src/index.js";
import { fakeD1 } from "./fake-d1.js";

const golden = JSON.parse(readFileSync(new URL("../contract/golden-checkins.json", import.meta.url), "utf8"));
const project = (row, expected) => Object.fromEntries(Object.keys(expected).map((key) => [key, row[key]]));

for (const example of golden.examples) {
  test(`golden contract: ${example.name}`, async () => {
    const env = { ROLE: "ingest", DB: fakeD1() };
    try {
      const response = await worker.fetch(new Request("https://contract.test/checkin", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ checkins: [example.checkin] }),
      }), env);
      assert.equal(response.status, 200);
      const reply = await response.json();
      assert.equal(reply.ok, true);
      assert.deepEqual(reply.results, [{ checkinId: example.checkin.checkinId, status: example.expected.ingest }]);
      const row = env.DB.raw.prepare("SELECT * FROM checkins").get();
      if (example.expected.ingest === "invalid") {
        assert.equal(row, undefined);
        for (const view of ["units", "unit_status", "transitions", "unit_latest"]) {
          assert.equal(env.DB.raw.prepare(`SELECT COUNT(*) n FROM ${view}`).get().n, 0);
        }
        return;
      }
      assert.deepEqual(project(row, example.expected.stored), example.expected.stored);
      assert.deepEqual(row.telemetry ? JSON.parse(row.telemetry) : null, example.checkin.telemetry ?? null);
      assert.ok(Number.isFinite(Date.parse(row.received_at)));
      // Every field used by the Vitals read tests must be certified above;
      // telemetry is passed through verbatim, not reconstructed by a second mapper.
      for (const [view, expected] of Object.entries(example.expected.views)) {
        const rows = env.DB.raw.prepare(`SELECT * FROM ${view}`).all();
        assert.equal(rows.length, expected.length, view);
        assert.deepEqual(rows.map((r, i) => project(r, expected[i])), expected, view);
      }
      const latest = env.DB.raw.prepare("SELECT * FROM unit_latest").get();
      assert.equal(latest.unit_key, example.checkin.venueId);
      assert.equal(latest.last_kind, example.checkin.reason);
    } finally {
      env.DB.raw.close();
    }
  });
}

test("golden batch accepts the good entries without sinking them with the bad one", async () => {
  const env = { ROLE: "ingest", DB: fakeD1() };
  try {
    const response = await worker.fetch(new Request("https://contract.test/checkin", {
      method: "POST", body: JSON.stringify({ checkins: golden.examples.map((e) => e.checkin) }),
    }), env);
    assert.deepEqual((await response.json()).results.map((r) => r.status), golden.examples.map((e) => e.expected.ingest));
    assert.equal(env.DB.raw.prepare("SELECT COUNT(*) n FROM checkins").get().n, 4);
  } finally {
    env.DB.raw.close();
  }
});
