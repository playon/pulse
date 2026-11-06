"""Unit tests for the proactive-monitoring engine (PULSEDEV-50/51/52).

Pure-Python, standard-library only — these import `monitor` directly (it has no
FastAPI/PowerShell dependency) so they run anywhere:

    cd Pulse.Web && .venv/bin/python -m unittest discover -s tests -v

They cover the state diff, the severity gate, the recording-aware out-of-scope
carry-forward, the file-backed state round-trip, the full-recompute
orchestration with mocked collectors, and the scheduled tick's cadence.
"""

import asyncio
import json
import os
import sys
import tempfile
import unittest

_APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

from pulse_agent import monitor  # noqa: E402


def _verdict(status="PASS", blockers=(), risks=(), info=()):
    def mk(codes):
        return [{"code": c, "title": f"{c} title", "category": "Cat",
                 "recommendation": f"fix {c}"} for c in codes]
    return {"status": status, "policyVersion": "v1",
            "blockers": mk(blockers), "risks": mk(risks), "info": mk(info)}


class TestCodesFromVerdict(unittest.TestCase):
    def test_flattens_with_class(self):
        v = _verdict("FAIL", blockers=["agent-down"], risks=["nic-slow"], info=["tz-non-us"])
        codes = monitor.codes_from_verdict(v)
        self.assertEqual(codes["agent-down"]["class"], "blocker")
        self.assertEqual(codes["nic-slow"]["class"], "risk")
        self.assertEqual(codes["tz-non-us"]["class"], "info")
        self.assertEqual(codes["agent-down"]["title"], "agent-down title")

    def test_empty_and_none(self):
        self.assertEqual(monitor.codes_from_verdict(None), {})
        self.assertEqual(monitor.codes_from_verdict({}), {})

    def test_skips_codeless_entries(self):
        v = {"blockers": [{"title": "no code"}], "risks": [], "info": []}
        self.assertEqual(monitor.codes_from_verdict(v), {})


class TestRouting(unittest.TestCase):
    def test_route_for(self):
        self.assertEqual(monitor.route_for("blocker"), "alert")
        self.assertEqual(monitor.route_for("risk"), "digest")
        self.assertEqual(monitor.route_for("info"), "log")
        self.assertEqual(monitor.route_for("nonsense"), "log")


class TestComputeDelta(unittest.TestCase):
    def _codes(self, verdict):
        return monitor.codes_from_verdict(verdict)

    def test_opened_blocker_sets_alert(self):
        prev = {}
        cur = self._codes(_verdict("FAIL", blockers=["agent-down"]))
        new_open, delta = monitor.compute_delta(prev, cur, "PASS", "SN1", now="T0")
        self.assertEqual([e["code"] for e in delta["opened"]], ["agent-down"])
        self.assertEqual(delta["opened"][0]["fingerprint"], "SN1:agent-down")
        self.assertEqual(delta["opened"][0]["route"], "alert")
        self.assertTrue(delta["alert"])
        self.assertEqual(delta["status"], "FAIL")       # derived from the open set
        self.assertTrue(delta["statusChanged"])         # PASS → FAIL
        self.assertEqual(new_open["agent-down"]["since"], "T0")

    def test_resolved_when_code_absent(self):
        prev = {"agent-down": {"class": "blocker", "title": "t", "category": "Services",
                               "recommendation": "r", "since": "T0"}}
        cur = self._codes(_verdict("PASS"))
        new_open, delta = monitor.compute_delta(prev, cur, "FAIL", "SN1", now="T1")
        self.assertEqual([e["code"] for e in delta["resolved"]], ["agent-down"])
        self.assertTrue(delta["alert"])
        self.assertEqual(delta["status"], "PASS")       # nothing left open
        self.assertEqual(new_open, {})

    def test_persisting_is_silent_and_keeps_since(self):
        prev = {"nic-slow": {"class": "risk", "title": "t", "category": "Network",
                             "recommendation": "r", "since": "T0"}}
        cur = self._codes(_verdict("WARN", risks=["nic-slow"]))
        new_open, delta = monitor.compute_delta(prev, cur, "WARN", "SN1", now="T9")
        self.assertEqual(delta["opened"], [])
        self.assertEqual(delta["resolved"], [])
        self.assertEqual(delta["persisting"], ["nic-slow"])
        self.assertEqual(delta["status"], "WARN")
        self.assertFalse(delta["statusChanged"])
        self.assertEqual(new_open["nic-slow"]["since"], "T0")  # carried forward, not reset

    def test_info_only_transition_does_not_alert(self):
        prev = {}
        cur = self._codes(_verdict("PASS", info=["tz-non-us"]))
        _, delta = monitor.compute_delta(prev, cur, "PASS", "SN1", now="T0")
        self.assertEqual([e["code"] for e in delta["opened"]], ["tz-non-us"])
        self.assertFalse(delta["alert"])            # info never sets the blocker alert flag
        self.assertEqual(delta["status"], "PASS")   # info never gates the verdict
        self.assertFalse(delta["statusChanged"])
        self.assertFalse(monitor.should_alert_now(delta))   # info-only → wait for periodic

    def test_risk_transition_alerts_now_without_blocker_flag(self):
        prev = {}
        cur = self._codes(_verdict("WARN", risks=["nic-slow"]))
        _, delta = monitor.compute_delta(prev, cur, "PASS", "SN1", now="T0")
        self.assertFalse(delta["alert"])            # alert flag is blocker-only
        self.assertEqual(delta["status"], "WARN")
        self.assertTrue(monitor.should_alert_now(delta))    # but a risk still warrants an immediate beacon

    def test_out_of_scope_code_carried_forward_not_resolved(self):
        # Recording-aware backoff: the port probe was skipped, so its blocker is
        # absent from the current verdict. It must NOT be reported resolved, and
        # the status must stay FAIL (the carried blocker still counts).
        prev = {"stream-blocked": {"class": "blocker", "title": "t",
                                        "category": "Network", "recommendation": "r", "since": "T0"}}
        cur = self._codes(_verdict("PASS"))  # port probe skipped → no port codes
        new_open, delta = monitor.compute_delta(
            prev, cur, "FAIL", "SN1",
            out_of_scope=frozenset({"stream-blocked"}), now="T1")
        self.assertEqual(delta["resolved"], [])
        self.assertIn("stream-blocked", new_open)
        self.assertEqual(new_open["stream-blocked"]["since"], "T0")
        self.assertEqual(delta["status"], "FAIL")       # carried blocker keeps it FAIL
        self.assertFalse(delta["statusChanged"])        # no FAIL→WARN flap mid-recording

    def test_out_of_scope_still_resolves_non_port_codes(self):
        prev = {
            "stream-blocked": {"class": "blocker", "since": "T0"},
            "agent-down": {"class": "blocker", "title": "t", "category": "Services",
                           "recommendation": "r", "since": "T0"},
        }
        cur = self._codes(_verdict("PASS"))
        new_open, delta = monitor.compute_delta(
            prev, cur, "FAIL", "SN1",
            out_of_scope=frozenset({"stream-blocked"}), now="T1")
        self.assertEqual([e["code"] for e in delta["resolved"]], ["agent-down"])
        self.assertIn("stream-blocked", new_open)   # carried
        self.assertNotIn("agent-down", new_open)         # resolved


class TestDebounce(unittest.TestCase):
    """Two passes to open, two to resolve (the vpu-home nic-slow flap)."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "state.json")

    def run_pass(self, verdict, recording=False):
        deps = _FakeDeps({"readiness": verdict})
        return asyncio.run(monitor.run_full_recompute(deps, self.path, recording=recording))

    def test_one_sighting_does_not_open(self):
        d = self.run_pass(_verdict("WARN", risks=["nic-slow"]))
        self.assertEqual(d["opened"], [])
        self.assertEqual(d["status"], "PASS")
        self.assertEqual(d["pending"], ["nic-slow"])

    def test_second_sighting_opens_dated_from_the_first(self):
        first = self.run_pass(_verdict("WARN", risks=["nic-slow"]))
        st = monitor.load_state(self.path)
        seen = st["pending"]["open"]["nic-slow"]["firstSeen"]
        d = self.run_pass(_verdict("WARN", risks=["nic-slow"]))
        self.assertEqual([e["code"] for e in d["opened"]], ["nic-slow"])
        self.assertEqual(d["opened"][0]["since"], seen)
        self.assertEqual(d["status"], "WARN")
        self.assertEqual(d["pending"], [])
        del first

    def test_flapping_finding_never_alerts(self):
        transitions = 0
        for i in range(6):
            v = _verdict("WARN", risks=["nic-slow"]) if i % 2 == 0 else _verdict("PASS")
            d = self.run_pass(v)
            transitions += len(d["opened"]) + len(d["resolved"])
        self.assertEqual(transitions, 0)

    def test_resolve_needs_two_misses(self):
        for _ in range(2):
            self.run_pass(_verdict("FAIL", blockers=["agent-down"]))
        d = self.run_pass(_verdict("PASS"))
        self.assertEqual(d["resolved"], [])
        self.assertEqual(d["status"], "FAIL")
        d = self.run_pass(_verdict("PASS"))
        self.assertEqual([e["code"] for e in d["resolved"]], ["agent-down"])
        self.assertEqual(d["status"], "PASS")

    def test_reappearing_cancels_a_pending_resolve(self):
        for _ in range(2):
            self.run_pass(_verdict("FAIL", blockers=["agent-down"]))
        self.run_pass(_verdict("PASS"))
        d = self.run_pass(_verdict("FAIL", blockers=["agent-down"]))
        self.assertEqual(d["resolved"], [])
        self.assertNotIn("agent-down", monitor.load_state(self.path).get("pending", {}).get("resolve", {}))

    def test_pending_makes_the_next_tick_due(self):
        self.run_pass(_verdict("WARN", risks=["nic-slow"]))
        st = monitor.load_state(self.path)
        self.assertEqual(monitor.plan_tick(st, st["lastFullAt"] + monitor.CONFIRM_SECONDS, False), "full")


class TestStatePersistence(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "pulse-monitor-state.json")

    def test_missing_file_is_empty(self):
        s = monitor.load_state(self.path)
        self.assertEqual(s["open"], {})
        self.assertIsNone(s["status"])

    def test_round_trip(self):
        open_map = {"agent-down": {"class": "blocker", "title": "t",
                                   "category": "Services", "recommendation": "r", "since": "T0"}}
        monitor.save_state(self.path, open_map, "FAIL", "SN1")
        s = monitor.load_state(self.path)
        self.assertEqual(s["status"], "FAIL")
        self.assertEqual(s["serial"], "SN1")
        self.assertEqual(s["open"], open_map)

    def test_version_mismatch_resets(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"version": 999, "open": {"x": {}}, "status": "FAIL"}, f)
        s = monitor.load_state(self.path)
        self.assertEqual(s["open"], {})

    def test_corrupt_file_resets(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("{not json")
        self.assertEqual(monitor.load_state(self.path)["open"], {})


class _FakeDeps(monitor.MonitorDeps):
    """In-memory deps for orchestration tests — records what the loop did."""
    def __init__(self, dashboard):
        self._dash = dashboard
        self.beacons = []
        self.cache_cleared = 0
        self.collected_with = []

        async def collect(skip_intrusive):
            self.collected_with.append(skip_intrusive)
            return self._dash

        async def send(dashboard=None, delta=None, reason=None):
            self.beacons.append({"reason": reason, "delta": delta})

        super().__init__(
            collect_dashboard=collect, send_checkin=send, get_serial=lambda d: "SN1",
            clear_cache=self._clear,
        )

    def _clear(self):
        self.cache_cleared += 1


class TestFullRecompute(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "state.json")

    async def test_opened_blocker_fires_state_change_beacon(self):
        deps = _FakeDeps({"readiness": _verdict("FAIL", blockers=["agent-down"])})
        await monitor.run_full_recompute(deps, self.path, recording=False)   # first sighting
        delta = await monitor.run_full_recompute(deps, self.path, recording=False)  # confirmed
        self.assertEqual(deps.cache_cleared, 2)
        self.assertEqual(deps.collected_with, [False, False])
        self.assertEqual(len(deps.beacons), 2)
        self.assertEqual(deps.beacons[1]["reason"], "state-change")
        self.assertEqual([e["code"] for e in delta["opened"]], ["agent-down"])
        # State persisted so the next run sees it as persisting (no re-alert).
        self.assertIn("agent-down", monitor.load_state(self.path)["open"])

    async def test_steady_state_is_periodic_not_state_change(self):
        deps = _FakeDeps({"readiness": _verdict("WARN", risks=["nic-slow"])})
        await monitor.run_full_recompute(deps, self.path, recording=False)   # first sighting
        await monitor.run_full_recompute(deps, self.path, recording=False)   # opens
        deps.beacons.clear()
        await monitor.run_full_recompute(deps, self.path, recording=False)   # persists
        self.assertEqual(deps.beacons[0]["reason"], "periodic")
        self.assertEqual(deps.beacons[0]["delta"]["opened"], [])

    async def test_recording_skips_cache_clear_and_intrusive_probe(self):
        deps = _FakeDeps({"readiness": _verdict("PASS")})
        await monitor.run_full_recompute(deps, self.path, recording=True)
        self.assertEqual(deps.cache_cleared, 0)        # don't disturb a live encode
        self.assertEqual(deps.collected_with, [True])  # skip_intrusive passed through


    async def test_recording_pass_resolves_nothing(self):
        deps = _FakeDeps({"readiness": _verdict("FAIL", blockers=["stream-blocked", "agent-down"])})
        await monitor.run_full_recompute(deps, self.path, recording=False)
        await monitor.run_full_recompute(deps, self.path, recording=False)
        deps._dash = {"readiness": _verdict("PASS")}      # port probe skipped -> nothing reported
        delta = await monitor.run_full_recompute(deps, self.path, recording=True)
        self.assertEqual(delta["resolved"], [])
        self.assertEqual(delta["status"], "FAIL")
        self.assertEqual(set(monitor.load_state(self.path)["open"]), {"stream-blocked", "agent-down"})


class TestPlanTick(unittest.TestCase):
    """Whether a tick runs a pass. Cadence comes from lastFullAt and what's open."""

    def plan(self, state, now, live=False):
        return monitor.plan_tick(state, now, live)

    def test_first_tick_is_full(self):
        self.assertEqual(self.plan({}, 1000.0), "full")

    def test_healthy_waits_the_full_interval(self):
        self.assertIsNone(self.plan({"lastFullAt": 1000.0}, 1000.0 + 600))
        self.assertEqual(self.plan({"lastFullAt": 1000.0}, 1000.0 + monitor.FULL_SECONDS), "full")

    def test_blocker_or_risk_uses_incident_cadence(self):
        st = {"lastFullAt": 1000.0, "open": {"nic-slow": {"class": "risk"}}}
        self.assertIsNone(self.plan(st, 1000.0 + 300))
        self.assertEqual(self.plan(st, 1000.0 + monitor.INCIDENT_SECONDS), "full")

    def test_info_only_does_not_speed_checks_up(self):
        # TeamViewer (sw-alt-remote) kept vpu-home on 5-minute passes all day.
        st = {"lastFullAt": 1000.0, "open": {"sw-alt-remote": {"class": "info"}}}
        self.assertIsNone(self.plan(st, 1000.0 + monitor.INCIDENT_SECONDS))
        self.assertEqual(self.plan(st, 1000.0 + monitor.FULL_SECONDS), "full")

    def test_unconfirmed_finding_rechecks_next_tick(self):
        st = {"lastFullAt": 1000.0, "pending": {"open": {"nic-slow": {}}, "resolve": {}}}
        self.assertEqual(self.plan(st, 1000.0 + monitor.CONFIRM_SECONDS), "full")

    def test_nothing_runs_during_an_event(self):
        self.assertIsNone(self.plan({}, 1000.0, live=True))
        st = {"lastFullAt": 0.0, "open": {"agent-down": {"class": "blocker"}}}
        self.assertIsNone(self.plan(st, 99_999.0, live=True))

    def test_tick_jitter_does_not_slip_a_whole_tick(self):
        st = {"lastFullAt": 1000.0, "open": {"cam-none": {"class": "blocker"}}}
        self.assertEqual(self.plan(st, 1000.0 + monitor.INCIDENT_SECONDS - 22), "full")

    def test_clock_stepped_back_is_due(self):
        self.assertEqual(self.plan({"lastFullAt": 10_000.0}, 5_000.0), "full")


class TestPlanPost(unittest.TestCase):
    """Post on change; repost unchanged FAIL/WARN on schedule; PASS heartbeats hourly."""

    def post(self, posts, fp, status, now):
        return monitor.plan_post(posts, fp, status, now)

    def test_first_post_is_full(self):
        self.assertEqual(self.post({}, "a", "PASS", 1000.0), "full")

    def test_any_change_posts_at_once(self):
        posts = {"fingerprint": "a", "lastPostAt": 1000.0}
        self.assertEqual(self.post(posts, "b", "PASS", 1001.0), "full")

    def test_unchanged_pass_is_an_hourly_heartbeat(self):
        posts = {"fingerprint": "a", "lastPostAt": 1000.0}
        self.assertIsNone(self.post(posts, "a", "PASS", 1000.0 + 1200))
        self.assertEqual(self.post(posts, "a", "PASS", 1000.0 + monitor.HEARTBEAT_SECONDS), "heartbeat")

    def test_unchanged_fail_reposts_every_15_min(self):
        posts = {"fingerprint": "a", "lastPostAt": 1000.0}
        self.assertIsNone(self.post(posts, "a", "FAIL", 1000.0 + 300))
        self.assertEqual(self.post(posts, "a", "FAIL", 1000.0 + 900), "full")

    def test_unchanged_warn_reposts_every_30_min(self):
        posts = {"fingerprint": "a", "lastPostAt": 1000.0}
        self.assertIsNone(self.post(posts, "a", "WARN", 1000.0 + 900))
        self.assertEqual(self.post(posts, "a", "WARN", 1000.0 + 1800), "full")

    def test_posts_record_round_trip(self):
        path = os.path.join(tempfile.mkdtemp(), "posts.json")
        self.assertEqual(monitor.load_posts(path), {})
        monitor.save_posts(path, {"fingerprint": "a", "lastPostAt": 5.0})
        self.assertEqual(monitor.load_posts(path)["fingerprint"], "a")


class TestRunOnce(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "state.json")

    async def test_full_pass_records_last_full_at(self):
        deps = _FakeDeps({"readiness": _verdict("PASS")})
        await monitor.run_once(deps, self.path, "full", wall_now=1000.0)
        self.assertEqual(monitor.load_state(self.path)["lastFullAt"], 1000.0)
        self.assertEqual(deps.collected_with, [False])

    async def test_partial_pass_skips_port_probe(self):
        deps = _FakeDeps({"readiness": _verdict("PASS")})
        await monitor.run_once(deps, self.path, "partial", wall_now=1000.0)
        self.assertEqual(deps.collected_with, [True])


if __name__ == "__main__":
    unittest.main()


class TestFleetControl(unittest.TestCase):
    """The remote off switch (Leaf lesson: one row in D1 stops a bad monitor)."""

    def test_missing_or_garbled_control_means_on(self):
        for qs in (None, {}, {"control": "off"}, {"control": {"mode": "maybe"}}, []):
            self.assertEqual(monitor.read_control(qs), {"mode": "on", "skip": []})

    def test_off_and_skip_are_read(self):
        ctl = monitor.read_control({"control": {"mode": "off", "skip": ["Get-S1Cameras.ps1", 7, ""]}})
        self.assertEqual(ctl, {"mode": "off", "skip": ["Get-S1Cameras.ps1"]})

    def test_paused_line_is_hourly_and_never_during_an_event(self):
        now = 100_000.0
        self.assertTrue(monitor.plan_paused({}, now, event_live=False))
        self.assertFalse(monitor.plan_paused({}, now, event_live=True))
        self.assertFalse(monitor.plan_paused({"lastPausedAt": now - 600}, now, False))
        self.assertTrue(monitor.plan_paused({"lastPausedAt": now - 3600}, now, False))


class TestSkippedCollector(unittest.IsolatedAsyncioTestCase):
    async def test_a_skipped_collector_never_starts(self):
        import powershell
        names = ("_PS_CONCURRENCY", "_PS_LOW_PRIORITY", "_PS_SEMAPHORE", "_DISK_CACHE_PATH",
                 "_DISK_CACHE_TTLS", "_PS_BATCH", "_PS_SKIP")
        saved = {n: getattr(powershell, n) for n in names}
        try:
            powershell.configure_background(skip_scripts=["Get-S1Cameras.ps1"])
            result = await powershell.run_ps("Get-S1Cameras.ps1")
            self.assertTrue(result.get("skipped"))
            self.assertIn("error", result)    # its part of the report reads as unknown
        finally:
            for n, v in saved.items():
                setattr(powershell, n, v)


class TestEventEndGrace(unittest.TestCase):
    """A VPU.exe restart gap must not end the event or start a full pass."""

    def setUp(self):
        import monitor_once
        self.mo = monitor_once
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = (monitor_once.EVENT_PATH, monitor_once.QUEUE_PATH, monitor_once.POSTS_PATH)
        monitor_once.EVENT_PATH = os.path.join(self.tmp.name, "event.json")
        monitor_once.QUEUE_PATH = os.path.join(self.tmp.name, "queue.json")
        monitor_once.POSTS_PATH = os.path.join(self.tmp.name, "posts.json")
        self.sent = []
        self.saved_send = monitor_once.checkin_lite.send
        monitor_once.checkin_lite.send = lambda q, e, user_agent="": self.sent.append(e) or True
        with open(monitor_once.EVENT_PATH, "w") as fh:
            json.dump({"event": {"startedAt": 1000.0, "eventId": "6ad018b2ec5d0313d04118a6"}}, fh)

    def tearDown(self):
        self.mo.EVENT_PATH, self.mo.QUEUE_PATH, self.mo.POSTS_PATH = self.saved
        self.mo.checkin_lite.send = self.saved_send
        self.tmp.cleanup()

    def test_first_tick_without_vpu_is_pending_second_ends(self):
        self.assertEqual(self.mo._event_end(2000.0), "pending")
        self.assertEqual(self.sent, [])
        note = self.mo._event_end(2300.0)
        self.assertTrue(note.startswith("event-end"))
        self.assertEqual(self.sent[0]["reason"], "event-end")
        self.assertIsNone(self.mo._event_end(2600.0))      # forgotten after the end

    def test_event_posts_carry_the_agent_version(self):
        import pulse_agent
        self.mo._event_end(2000.0)
        self.mo._event_end(2300.0)
        self.assertTrue(pulse_agent.AGENT_VERSION)
        self.assertEqual(self.sent[0]["agentVersion"], pulse_agent.AGENT_VERSION)

    def test_vpu_back_clears_the_pending_end(self):
        self.assertEqual(self.mo._event_end(2000.0), "pending")
        with open(self.mo.EVENT_PATH) as fh:
            rec = json.load(fh)
        rec["event"].pop("goneAt")                        # what _event_tick does on return
        with open(self.mo.EVENT_PATH, "w") as fh:
            json.dump(rec, fh)
        self.assertEqual(self.mo._event_end(2300.0), "pending")   # a fresh gap, not an end


class TestEventKeepAlive(unittest.TestCase):
    """A steady event posts once an hour, so Vitals never reads it as Silent."""

    def setUp(self):
        import monitor_once
        self.mo = monitor_once
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = (monitor_once.EVENT_PATH, monitor_once.QUEUE_PATH, monitor_once.POSTS_PATH,
                      monitor_once.event_watch.observe, monitor_once.event_watch.verdict)
        monitor_once.EVENT_PATH = os.path.join(self.tmp.name, "event.json")
        monitor_once.QUEUE_PATH = os.path.join(self.tmp.name, "queue.json")
        monitor_once.POSTS_PATH = os.path.join(self.tmp.name, "posts.json")
        monitor_once.event_watch.observe = lambda ev, pid, now, **kw: ev.update(eventId="6ad018b2ec5d0313d04118a6") or {"bytes": 0, "skipped": False}
        monitor_once.event_watch.verdict = lambda ev, now: "on-air"
        self.sent = []
        self.saved_send = monitor_once.checkin_lite.send
        monitor_once.checkin_lite.send = lambda q, e, user_agent="": self.sent.append(e["reason"]) or True

    def tearDown(self):
        (self.mo.EVENT_PATH, self.mo.QUEUE_PATH, self.mo.POSTS_PATH,
         self.mo.event_watch.observe, self.mo.event_watch.verdict) = self.saved
        self.mo.checkin_lite.send = self.saved_send
        self.tmp.cleanup()

    def test_start_then_silence_then_hourly(self):
        t = 1_000_000.0
        self.mo._event_tick(t)                       # start
        for k in range(1, 12):                       # 55 minutes of steady on air: nothing
            self.mo._event_tick(t + 300 * k)
        self.assertEqual(self.sent, ["event-start"])
        self.mo._event_tick(t + 3600)                # the hour: one keep-alive
        for k in range(13, 24):
            self.mo._event_tick(t + 300 * k)
        self.assertEqual(self.sent, ["event-start", "event-update"])
