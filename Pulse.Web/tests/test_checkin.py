"""Unit tests for the launch check-in queue (_send_checkin and friends).

The old sink, an Apps Script sheet, lost four days of check-ins when its Google
account lapsed: Apps Script kept answering 200, Pulse never read the reply, and
nothing was kept locally. These pin the replacement contract. A check-in leaves
the on-disk queue only when the sink says ok:true and names it in results, and
anything else (a 5xx, a 200 without an ack, an HTML page, a dead network) keeps
it for the next launch with its original sentAt.

The sink here is a real local HTTP server, so urllib and the reply parsing are
exercised rather than mocked. Standard library only:

    cd Pulse.Web && .venv/bin/python -m unittest tests.test_checkin -v
"""

import asyncio
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import main  # noqa: E402


class FakeSink(BaseHTTPRequestHandler):
    mode = "ok"
    requests = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeSink.requests.append(body)
        if FakeSink.mode == "ok":
            self._reply(200, {"ok": True, "results": [
                {"checkinId": c["checkinId"], "status": "inserted"} for c in body["checkins"]]})
        elif FakeSink.mode == "invalid":
            self._reply(200, {"ok": True, "results": [
                {"checkinId": c["checkinId"], "status": "invalid"} for c in body["checkins"]]})
        elif FakeSink.mode == "storage":
            self._reply(500, {"ok": False, "error": "storage"})
        elif FakeSink.mode == "apps-script-lapsed":
            self._reply(200, {"result": "error", "message": "Exceeded storage quota"})
        elif FakeSink.mode == "html":
            data = b"<html><body>Sorry, unable to open the file</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif FakeSink.mode == "wrong-ids":
            self._reply(200, {"ok": True, "results": [{"checkinId": "someone-else", "status": "inserted"}]})

    def _reply(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class TestCheckinQueue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeSink)
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}/checkin"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state_path = os.path.join(self._tmp.name, "pulse-checkin-queue.json")
        self._saved = (main.DEMO_MODE, main._CHECKIN_STATE_PATH, main._build_checkin_entry,
                       main._checkin_configured, main._checkin_now, main._post_fallback_sync,
                       os.environ.get("PULSE_CHECKIN_URL"),
                       os.environ.get("PULSE_CHECKIN_FALLBACK_URL"))
        main.DEMO_MODE = False
        main._CHECKIN_STATE_PATH = self.state_path
        # The fake sink is plain http on loopback; production requires https.
        main._checkin_configured = lambda url: True
        os.environ["PULSE_CHECKIN_URL"] = self.url
        # Never reach the real sheet from a test: record what would be sent.
        os.environ["PULSE_CHECKIN_FALLBACK_URL"] = "https://fallback.test/exec"
        self.fallback_posts = []
        self.fallback_mode = "ok"

        def fake_fallback(url, body):
            self.fallback_posts.append(body)
            if self.fallback_mode != "ok":
                raise RuntimeError("fallback did not acknowledge")
        main._post_fallback_sync = fake_fallback
        self.clock = "2026-09-20T12:00:00Z"
        main._checkin_now = lambda: self.clock
        self.n = 0

        async def fake_entry():
            self.n += 1
            return {"checkinId": f"id-{self.n:08d}", "sentAt": self.clock,
                    "hostname": "PXLS2_10893", "pulseVersion": "1.4.0-dev"}
        main._build_checkin_entry = fake_entry
        FakeSink.mode = "ok"
        FakeSink.requests = []

    def tearDown(self):
        (main.DEMO_MODE, main._CHECKIN_STATE_PATH, main._build_checkin_entry,
         main._checkin_configured, main._checkin_now, main._post_fallback_sync,
         url, fallback) = self._saved
        for key, val in (("PULSE_CHECKIN_URL", url),
                         ("PULSE_CHECKIN_FALLBACK_URL", fallback)):
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val
        self._tmp.cleanup()

    def launch(self):
        asyncio.run(main._send_checkin())

    def state(self):
        with open(self.state_path, encoding="utf-8") as fh:
            return json.load(fh)

    def test_acknowledged_checkin_leaves_the_queue(self):
        self.launch()
        self.assertEqual(self.state()["queue"], [])
        self.assertEqual(self.state()["lastSentAt"], self.clock)
        sent = FakeSink.requests[0]
        self.assertNotIn("secret", sent)    # the Worker takes no write key
        self.assertEqual(sent["checkins"][0]["checkinId"], "id-00000001")
        self.assertEqual(sent["checkins"][0]["sentAt"], "2026-09-20T12:00:00Z")

    def test_every_unacknowledged_reply_keeps_the_checkin(self):
        for mode in ("storage", "apps-script-lapsed", "html", "wrong-ids"):
            with self.subTest(mode=mode):
                if os.path.exists(self.state_path):
                    os.remove(self.state_path)
                FakeSink.mode = mode
                self.launch()
                st = self.state()
                self.assertEqual(len(st["queue"]), 1, mode)
                self.assertTrue(st["lastError"], mode)
                self.assertNotIn("lastSentAt", st)

    def test_error_names_the_sink_reason(self):
        FakeSink.mode = "storage"
        self.launch()
        self.assertEqual(self.state()["lastError"], "HTTP 500: storage")

    def test_unreachable_sink_keeps_the_checkin(self):
        os.environ["PULSE_CHECKIN_URL"] = "http://127.0.0.1:9/checkin"
        self.launch()
        self.assertEqual(len(self.state()["queue"]), 1)
        self.assertTrue(self.state()["lastError"])

    def test_outage_replays_oldest_first_with_original_timestamps(self):
        FakeSink.mode = "storage"
        self.launch()
        self.clock = "2026-09-21T12:00:00Z"
        self.launch()
        FakeSink.mode = "ok"
        FakeSink.requests = []
        self.clock = "2026-09-24T09:00:00Z"
        self.launch()
        sent = FakeSink.requests[0]["checkins"]
        self.assertEqual([c["sentAt"] for c in sent],
                         ["2026-09-20T12:00:00Z", "2026-09-21T12:00:00Z", "2026-09-24T09:00:00Z"])
        self.assertEqual(self.state()["queue"], [])
        self.assertNotIn("lastError", self.state())

    def test_large_queue_goes_in_batches(self):
        queue = [{"checkinId": f"old-{i:08d}", "sentAt": self.clock} for i in range(120)]
        main._save_checkin_state({"queue": queue})
        self.launch()
        self.assertEqual([len(r["checkins"]) for r in FakeSink.requests], [50, 50, 21])
        self.assertEqual(self.state()["queue"], [])

    def test_invalid_entries_are_dropped_not_retried_forever(self):
        FakeSink.mode = "invalid"
        self.launch()
        self.assertEqual(self.state()["queue"], [])

    def test_queue_is_capped_and_ages_out(self):
        old = [{"checkinId": "ancient-0001", "sentAt": "2026-07-01T00:00:00Z"}]
        many = [{"checkinId": f"q-{i:08d}", "sentAt": self.clock} for i in range(250)]
        main._save_checkin_state({"queue": old + many})
        FakeSink.mode = "storage"
        self.launch()
        ids = [e["checkinId"] for e in self.state()["queue"]]
        self.assertEqual(len(ids), main._CHECKIN_MAX_QUEUED)
        self.assertNotIn("ancient-0001", ids)
        self.assertEqual(ids[-1], "id-00000001")

    def test_worker_up_never_touches_the_sheet(self):
        self.launch()
        self.assertEqual(self.fallback_posts, [])

    def test_worker_down_sends_the_new_checkin_to_the_sheet_and_keeps_it_queued(self):
        FakeSink.mode = "storage"
        self.launch()
        self.assertEqual(len(self.fallback_posts), 1)
        sent = self.fallback_posts[0]
        self.assertEqual(sent["checkinId"], "id-00000001")
        self.assertIn("secret", sent)           # the sheet takes a flat check-in
        self.assertNotIn("checkins", sent)
        st = self.state()
        self.assertEqual([e["checkinId"] for e in st["queue"]], ["id-00000001"])  # D1 still gets it
        self.assertTrue(st.get("lastFallbackAt"))

    def test_sheet_gets_only_the_newest_checkin_not_the_backlog(self):
        FakeSink.mode = "storage"
        for _ in range(3):
            self.launch()
        self.assertEqual([b["checkinId"] for b in self.fallback_posts],
                         ["id-00000001", "id-00000002", "id-00000003"])
        self.assertEqual(len(self.state()["queue"]), 3)

    def test_failing_sheet_changes_nothing_else(self):
        FakeSink.mode = "storage"
        self.fallback_mode = "down"
        self.launch()
        st = self.state()
        self.assertEqual(len(st["queue"]), 1)
        self.assertTrue(st.get("lastFallbackError"))
        FakeSink.mode = "ok"
        self.launch()
        self.assertEqual(self.state()["queue"], [])

    def test_empty_fallback_url_turns_it_off(self):
        os.environ["PULSE_CHECKIN_FALLBACK_URL"] = ""
        FakeSink.mode = "storage"
        self.launch()
        self.assertEqual(self.fallback_posts, [])

    def test_corrupt_state_file_is_recovered(self):
        with open(self.state_path, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        self.launch()
        self.assertEqual(self.state()["queue"], [])
        self.assertEqual(len(FakeSink.requests), 1)

    def test_demo_mode_never_sends_or_writes(self):
        main.DEMO_MODE = True
        self.launch()
        self.assertEqual(FakeSink.requests, [])
        self.assertFalse(os.path.exists(self.state_path))

    def test_unconfigured_build_queues_but_does_not_send(self):
        main._checkin_configured = lambda url: False
        self.launch()
        self.assertEqual(FakeSink.requests, [])
        self.assertEqual(len(self.state()["queue"]), 1)

    def test_production_requires_https_and_real_values(self):
        configured = self._saved[3]
        self.assertFalse(configured("PASTE_WORKER_URL_HERE"))
        self.assertFalse(configured("http://example.test/checkin"))
        self.assertFalse(configured(""))
        self.assertTrue(configured("https://w.test/checkin"))


class TestCheckinStatus(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._saved = (main.DEMO_MODE, main._CHECKIN_STATE_PATH, main._checkin_now, main._CHECKIN_URL)
        main.DEMO_MODE = False
        main._CHECKIN_STATE_PATH = os.path.join(self._tmp.name, "q.json")
        main._checkin_now = lambda: "2026-09-23T12:00:00Z"
        main._CHECKIN_URL = "https://pulse-checkin.example.workers.dev/checkin"
        os.environ.pop("PULSE_CHECKIN_URL", None)

    def tearDown(self):
        main.DEMO_MODE, main._CHECKIN_STATE_PATH, main._checkin_now, main._CHECKIN_URL = self._saved
        self._tmp.cleanup()

    def test_fresh_install_has_never_sent(self):
        self.assertEqual(main._checkin_status()["status"], "never")

    def test_placeholder_url_reads_not_configured(self):
        main._CHECKIN_URL = "PASTE_WORKER_URL_HERE"
        self.assertEqual(main._checkin_status()["status"], "not-configured")

    def test_unconfigured_build_never_claims_a_failed_send(self):
        main._CHECKIN_URL = "PASTE_WORKER_URL_HERE"
        main._save_checkin_state({"queue": [{"checkinId": "a-00000001", "sentAt": "2026-09-01T09:00:00Z"}]})
        st = main._checkin_status()
        self.assertEqual((st["status"], st["queued"], st["notice"]), ("not-configured", 1, False))

    def test_demo_mode_with_no_state(self):
        main.DEMO_MODE = True
        self.assertEqual(main._checkin_status()["status"], "demo")

    def test_sent(self):
        main._save_checkin_state({"queue": [], "lastSentAt": "2026-09-23T10:00:00Z"})
        st = main._checkin_status()
        self.assertEqual((st["status"], st["notice"]), ("sent", False))

    def test_recent_failure_is_queued_without_a_notice(self):
        main._save_checkin_state({"queue": [{"checkinId": "a-00000001", "sentAt": "2026-09-23T02:00:00Z"}],
                                  "lastError": "HTTP 500: storage"})
        st = main._checkin_status()
        self.assertEqual((st["status"], st["queued"], st["notice"]), ("queued", 1, False))

    def test_failure_older_than_a_day_raises_the_notice(self):
        main._save_checkin_state({"queue": [
            {"checkinId": "b-00000002", "sentAt": "2026-09-22T09:00:00Z"},
            {"checkinId": "a-00000001", "sentAt": "2026-09-20T09:00:00Z"},
        ], "lastSentAt": "2026-09-19T09:00:00Z"})
        st = main._checkin_status()
        self.assertEqual(st["status"], "queued")
        self.assertEqual(st["oldestQueued"], "2026-09-20T09:00:00Z")
        self.assertTrue(st["notice"])




class TestCheckinEntryShape(unittest.TestCase):
    def test_no_hostname_or_serial(self):
        # Ian, 2026-10-13: a unit is its venue id and VPU name.
        powershell_sem_reset()
        e = asyncio.run(main._build_checkin_entry())
        self.assertIsNotNone(e)
        self.assertNotIn("hostname", e)
        self.assertNotIn("serialNumber", e)
        for key in ("venueId", "vpuName", "model", "pulseVersion"):
            self.assertIn(key, e)


def powershell_sem_reset():
    import powershell
    powershell._PS_SEMAPHORE = None


if __name__ == "__main__":
    unittest.main()
