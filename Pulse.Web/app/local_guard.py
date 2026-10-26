"""Keep a web page from driving Pulse's loopback API.

Pulse binds to 127.0.0.1 only, but a browser on the VPU is a bridge to it: any
page the tech visits can make that browser send requests to localhost. The API
has no login, and its routes reboot the VPU, restart services, enroll the unit
and apply updates, so "who sent this request" has to be checked here.

Three checks, applied to every HTTP request and WebSocket handshake:

1. Host must name loopback (127.0.0.1 or localhost). A page that reaches Pulse
   by DNS rebinding sends its own domain as Host, so it is refused. This is
   what protects the read routes, such as /api/reports/export.
2. Origin, when the browser sends one, must be the origin Pulse itself was
   reached at (http:// plus the Host header). That refuses a hostile page at
   any other origin, including another localhost port. Browsers add Origin to
   cross-origin and form POSTs, and answer a CORS preflight with it, so the
   body-less and text/plain POSTs that skip preflight are still caught.
3. Sec-Fetch-Site, when sent, must be same-origin or none (the tech typed the
   URL). cross-site and same-site are refused, which also covers a GET that
   carries no Origin.

A request with none of those headers is let through: curl, a script and a test
send none, and a browser that predates Sec-Fetch-Site (before Chrome/Edge 76)
sends no Origin on a cross-origin GET either, so it passes too. For that case
only the Host check and the browser's own cross-origin read block apply, so a
GET must never do anything: the routes that run a capture, traceroute or ping
on the VPU are POST-only (tests/test_local_guard.py keeps them that way). A
browser that also omits Origin on a cross-origin POST (IE11 on a form POST is
suspected, not tested) would get past the check; a per-launch token would
close that, at the cost of changing every client call.
Anything already running on the VPU can reach the API regardless.

Port is deliberately not compared with the server's: an SSH or Tailscale port
forward that remaps it still sends Host and Origin that agree with each other.
"""

import logging
from typing import Optional

_log = logging.getLogger("pulse")

LOOPBACK_NAMES = frozenset({"127.0.0.1", "localhost"})
_FETCH_SITES_OK = frozenset({"same-origin", "none"})


def _hostname(authority: str) -> str:
    """The name part of a Host header value ("localhost:8765" -> "localhost")."""
    return authority.rsplit(":", 1)[0] if authority.count(":") == 1 else authority


def refusal(headers: dict) -> Optional[str]:
    """Why a request is refused, or None to let it through. `headers` maps
    lower-case names to values."""
    host = (headers.get("host") or "").strip().lower()
    if _hostname(host) not in LOOPBACK_NAMES:
        return "host"
    origin = headers.get("origin")
    if origin is not None and origin.strip().lower() != "http://" + host:
        return "origin"
    site = headers.get("sec-fetch-site")
    if site is not None and site.strip().lower() not in _FETCH_SITES_OK:
        return "fetch-site"
    return None


class LocalOnlyGuard:
    """ASGI middleware. Pure ASGI rather than @app.middleware("http"), which
    never sees WebSocket handshakes."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        headers = {}
        for name, value in scope.get("headers") or ():
            # A repeated header is a smuggling signal, not a convenience: keep
            # the first value and mark the clash so it is refused below.
            key = name.decode("latin-1").lower()
            val = value.decode("latin-1")
            headers[key] = val if key not in headers else "\x00duplicate"
        why = refusal(headers)
        if why is None:
            await self.app(scope, receive, send)
            return
        _log.warning("Refused a %s request to %s: %s header was %r", scope["type"],
                     scope.get("path"), why, headers.get(
                         {"host": "host", "origin": "origin", "fetch-site": "sec-fetch-site"}[why]))
        if scope["type"] == "websocket":
            # Closing before accept makes the server answer 403.
            await send({"type": "websocket.close", "code": 1008})
            return
        body = b'{"error":"Pulse only answers requests from its own page on this VPU."}'
        await send({"type": "http.response.start", "status": 403, "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
            (b"cache-control", b"no-store"),
        ]})
        await send({"type": "http.response.body", "body": body})
