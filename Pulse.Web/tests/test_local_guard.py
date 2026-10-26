"""A web page on the VPU must not be able to drive Pulse's loopback API.

Pulse's API has no login and its routes reboot the VPU, restart services and
enroll the unit. Measured 2026-10-26 (Chromium 150): a form POST and a
text/plain POST from another origin reached the handlers, and a request with a
foreign Host (DNS rebinding) was answered. local_guard.py refuses both.
"""

import asyncio
import os
import sys
import unittest

_WEB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_APP_DIR = os.path.join(_WEB, "app")
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import main  # noqa: E402  (before any asyncio.run: it creates an asyncio.Lock at import)
from local_guard import LocalOnlyGuard, refusal  # noqa: E402


def headers(host="127.0.0.1:8765", **extra):
    h = {"host": host}
    h.update({k.replace("_", "-"): v for k, v in extra.items()})
    return h


class RefusalTests(unittest.TestCase):
    def test_pulses_own_page_is_let_through_on_either_loopback_name(self):
        for host in ("127.0.0.1:8765", "localhost:8765"):
            self.assertIsNone(refusal(headers(host, origin="http://" + host, sec_fetch_site="same-origin")), host)

    def test_typing_the_url_has_no_origin_and_is_let_through(self):
        self.assertIsNone(refusal(headers(sec_fetch_site="none")))

    def test_a_non_browser_sends_none_of_it_and_is_let_through(self):
        self.assertIsNone(refusal(headers()))

    def test_dns_rebinding_is_refused_even_for_a_read(self):
        # The rebound page is same-origin with its own domain, so it sends
        # Origin and Sec-Fetch-Site that look fine. Only Host gives it away.
        h = headers("evil.example:8765", origin="http://evil.example:8765", sec_fetch_site="same-origin")
        self.assertEqual(refusal(h), "host")

    def test_a_host_that_only_starts_with_a_loopback_name_is_refused(self):
        for host in ("localhost.evil.example:8765", "127.0.0.1.evil.example", "", "[::1]:8765"):
            self.assertEqual(refusal(headers(host)), "host", host)

    def test_a_page_at_another_origin_is_refused(self):
        self.assertEqual(refusal(headers(origin="https://evil.example")), "origin")

    def test_a_page_on_another_localhost_port_is_refused(self):
        # Same site, so SameSite cookies would not have stopped it.
        self.assertEqual(refusal(headers("127.0.0.1:8765", origin="http://localhost:9999")), "origin")
        self.assertEqual(refusal(headers("127.0.0.1:8765", origin="http://127.0.0.1:9999")), "origin")

    def test_opaque_origin_is_refused(self):
        self.assertEqual(refusal(headers(origin="null")), "origin")

    def test_cross_site_and_same_site_fetches_are_refused_even_with_no_origin(self):
        for site in ("cross-site", "same-site"):
            self.assertEqual(refusal(headers(sec_fetch_site=site)), "fetch-site", site)

    def test_a_remapped_port_is_fine_while_host_and_origin_agree(self):
        # ssh -L 18765:localhost:8765 from a laptop: the browser reaches it at 18765.
        self.assertIsNone(refusal(headers("localhost:18765", origin="http://localhost:18765")))


class Recorder:
    """Drives an ASGI app by hand: records what it sent and whether it ran."""

    def __init__(self):
        self.sent = []
        self.ran = False

    async def inner(self, scope, receive, send):
        self.ran = True
        if scope["type"] == "http":
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

    async def call(self, app, scope):
        async def receive():
            return {"type": "http.disconnect"}

        async def send(message):
            self.sent.append(message)
        await app(scope, receive, send)

    @property
    def status(self):
        return next(m["status"] for m in self.sent if m["type"] == "http.response.start")


def scope(kind="http", method="GET", path="/api/x", **hdrs):
    return {"type": kind, "method": method, "path": path,
            "headers": [(k.replace("_", "-").encode(), v.encode()) for k, v in hdrs.items()]}


class MiddlewareTests(unittest.TestCase):
    def run_scope(self, sc):
        rec = Recorder()
        asyncio.run(rec.call(LocalOnlyGuard(rec.inner), sc))
        return rec

    def test_a_refused_request_never_reaches_the_app(self):
        rec = self.run_scope(scope(method="POST", path="/api/maintenance/reboot-vpu",
                                   host="127.0.0.1:8765", origin="https://evil.example"))
        self.assertFalse(rec.ran)
        self.assertEqual(rec.status, 403)

    def test_an_allowed_request_reaches_the_app(self):
        rec = self.run_scope(scope(host="localhost:8765", origin="http://localhost:8765"))
        self.assertTrue(rec.ran)
        self.assertEqual(rec.status, 200)

    def test_a_repeated_host_header_is_refused(self):
        sc = scope(host="127.0.0.1:8765")
        sc["headers"].append((b"host", b"evil.example"))
        rec = self.run_scope(sc)
        self.assertFalse(rec.ran)
        self.assertEqual(rec.status, 403)

    def test_a_websocket_from_another_origin_is_closed_before_accept(self):
        rec = self.run_scope(scope("websocket", path="/ws", host="127.0.0.1:8765",
                                   origin="https://evil.example"))
        self.assertFalse(rec.ran)
        self.assertEqual([m["type"] for m in rec.sent], ["websocket.close"])

    def test_pulses_own_websocket_is_let_through(self):
        rec = self.run_scope(scope("websocket", path="/ws", host="127.0.0.1:8765",
                                   origin="http://127.0.0.1:8765"))
        self.assertTrue(rec.ran)

    def test_lifespan_is_not_inspected(self):
        rec = self.run_scope({"type": "lifespan"})
        self.assertTrue(rec.ran)


class RealAppTests(unittest.TestCase):
    """The assembled app, not just the middleware: the routes that matter are
    behind it, for a read, a body-less POST and a static file."""

    app = main.app

    def call(self, **kw):
        rec = Recorder()
        sc = scope(**kw)
        sc["query_string"] = b""
        sc["server"] = ("127.0.0.1", 8765)
        asyncio.run(rec.call(self.app, sc))
        return rec

    def test_a_rebound_read_of_the_full_report_is_refused(self):
        rec = self.call(path="/api/reports/export", host="evil.example:8765")
        self.assertEqual(rec.status, 403)

    def test_a_cross_origin_bodyless_post_is_refused(self):
        rec = self.call(method="POST", path="/api/maintenance/reboot-vpu",
                        host="127.0.0.1:8765", origin="https://evil.example")
        self.assertEqual(rec.status, 403)

    def test_a_cross_site_static_file_request_is_refused(self):
        rec = self.call(path="/static/app.js", host="127.0.0.1:8765", sec_fetch_site="cross-site")
        self.assertEqual(rec.status, 403)

    def test_diagnostics_that_run_on_the_vpu_do_not_answer_a_get(self):
        # A browser too old to send Origin or Sec-Fetch-Site gets past the
        # guard on a GET, so a GET must never start a capture, traceroute or
        # ping. Headers here are exactly what such a browser sends.
        for path in ("/api/network/capture", "/api/network/traceroute", "/api/network/local-ping"):
            rec = self.call(path=path, host="127.0.0.1:8765")
            self.assertEqual(rec.status, 405, path)

    def test_pulses_own_page_still_works(self):
        rec = self.call(path="/api/version", host="127.0.0.1:8765",
                        origin="http://127.0.0.1:8765", sec_fetch_site="same-origin")
        self.assertEqual(rec.status, 200)


if __name__ == "__main__":
    unittest.main()
