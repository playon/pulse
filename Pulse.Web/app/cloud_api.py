"""Cloud-side lookups for the Event Streaming lane.

Chains the box's own identifiers through the NFHS cloud APIs (all public,
read-only GETs — verified 2026-08-04, no credentials required):

  venueId            -> search-api producers  (who am I in the cloud)
  venueId            -> search-api events     (my listed schedule)
  venueId            -> EQS venue             (did recent events actually air)
  pixellot key       -> Unity pixellots/{key} (live health metrics, proxied
                                               from Pixellot Club)
  pixellot event ids -> Unity pixellots/broadcasts/{id}
                        (box-driven: catches unlisted/test streams that the
                         search index never shows)

Every call is timeout-bounded and individually fail-soft: on a locked-down
school network (DPI / blocked domains) the lane degrades to a single
"cloud lookup unavailable" state — a failed lookup is never itself a finding.

All calls run server-side (this module), never from the browser and never
from PowerShell — no CORS, no PS 5.1 TLS landmines.
"""

import json
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from powershell import DEMO_MODE

SEARCH_BASE = "https://search-api.nfhsnetwork.com"
UNITY_BASE = "https://unity.nfhsnetwork.com"
EQS_BASE = "https://eqs.nfhsnetwork.com"

TIMEOUT_S = 6          # per-call; hostile networks hang, so keep this short
MAX_BOX_LOOKUPS = 6    # unity per-event lookups per request, newest first
LISTED_PAST_DAYS = 14  # listed-events window
LISTED_FUTURE_DAYS = 7

_UA = {"User-Agent": "Pulse-VPU-Diagnostics"}


def _get_json(url):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return json.load(resp)


def _try(fn, *args):
    """Run fn, returning (result, None) or (None, short error string)."""
    try:
        return fn(*args), None
    except Exception as exc:  # noqa: BLE001 — fail-soft by design
        return None, f"{type(exc).__name__}: {exc}"


def _parse_iso(ts):
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        # Naive timestamps come from box-local collectors (event-log parses,
        # Pixellot log lines). This server runs ON the box, so system-local
        # is the right zone — coerce so they compare against UTC-aware cloud
        # times instead of raising. (Field bug: web-v1.1.1 500'd on any box
        # with a parsed shutdown or process restart.)
        dt = dt.astimezone()
    return dt


# ── individual fetches ───────────────────────────────────────────


def _fetch_producer(venue_id):
    data = _get_json(f"{SEARCH_BASE}/v3/search/producers?venue_id={venue_id}")
    items = data.get("items") or []
    if not items:
        return None
    item = items[0]
    px = item.get("pixellot") or {}
    pubs = [
        {
            "key": p.get("publisher_key"),
            "name": p.get("publisher_name"),
            "type": p.get("publisher_type"),
            "city": p.get("city"),
            "state": p.get("state"),
        }
        for p in (item.get("related_publishers") or [])
    ]
    return {
        "name": item.get("formatted_name") or item.get("name"),
        "producerKey": item.get("key"),
        "pixellotKey": px.get("key"),
        "pixellotName": px.get("pixellot_name"),
        "internalStatus": px.get("internal_status"),
        "lastStatus": px.get("last_status"),
        "statusChangedAt": px.get("status_changed_at"),
        "broadcastStatusReason": px.get("broadcast_status_reason"),
        "currentSwVersion": px.get("current_sw_version"),
        "targetSwVersion": px.get("target_sw_version"),
        "targetSwVersionSetDate": px.get("target_sw_version_set_date"),
        "state": px.get("state"),
        "activationDate": px.get("activation_date"),
        "publishers": pubs,
        # deliberately NOT surfacing updated_by_user (employee email)
    }


def _fetch_listed_events(venue_id):
    data = _get_json(f"{SEARCH_BASE}/v3/search/events?venue_id={venue_id}&size=100")
    return data.get("items") or []


def _fetch_eqs(venue_id):
    data = _get_json(f"{EQS_BASE}/venue/{venue_id}?include_unlisted=true")
    by_event = {}
    for entry in data.get("included") or []:
        key = entry.get("eventKey")
        if key:
            by_event[key] = entry
    excluded = {
        e.get("eventKey") for e in (data.get("excluded") or []) if e.get("eventKey")
    }
    # EQS reports avgScore 0 for venues with no scored events — that's "no
    # data", not "0% quality"; don't let the UI render an orange zero.
    avg = data.get("avgScore") if by_event else None
    return {"avgScore": avg, "byEvent": by_event, "excluded": excluded}


def _fetch_venue_record(venue_id):
    """Unity's registry of Pixellot venues — knows units that were never
    onboarded as NFHS producers (name present, pixellot/producer keys null)."""
    data = _get_json(f"{UNITY_BASE}/v2/pixellot_venues/{venue_id}")
    if isinstance(data, list) and data:
        rec = data[0]
        return {
            "name": rec.get("name"),
            "pixellotKey": rec.get("pixellot_key"),
            "producerKey": rec.get("producer_key"),
        }
    return None


# The Unity pixellot record proxies Pixellot Club's live health indicators.
# Most of them are only meaningful while the VPU is actively streaming, so we
# keep just the cause-hint inputs and don't display raw values in the UI.
# Field truth (Loma Linda, 2026-08-04): with every camera down, `camera` still
# read Ok — the reliable camera signal is darkCourt + both bandwidths at Error,
# while `connection` distinguishes box-offline from box-online-but-dark.
_METRIC_KEYS = (
    "connection", "status", "status_severity",
    "darkCourt", "hdBandwidth", "panoBandwidth",
)


def _fetch_metrics(pixellot_key):
    data = _get_json(f"{UNITY_BASE}/v2/pixellots/{pixellot_key}")
    return {k: data.get(k) for k in _METRIC_KEYS}


def _fetch_broadcast_by_event_id(pixellot_event_id):
    data = _get_json(f"{UNITY_BASE}/v2/pixellots/broadcasts/{pixellot_event_id}")
    return {
        "broadcastKey": data.get("key"),
        "status": data.get("status"),
        "headline": data.get("headline"),
        "subheadline": data.get("subheadline"),
        "startTime": data.get("start_time"),
        "gameKey": data.get("game_key"),
        "vodKey": data.get("vod_key"),
        "unlisted": data.get("unlisted"),
        # scheduled length in HOURS (Unity's `duration` is the scheduled
        # window, not actual air time) — bounds the "unable to stream" phase
        "durationHours": data.get("duration"),
        "pixellotEventId": data.get("pixellot_event_id"),
        # broadcast can be registered to a different venue than the box that
        # ran it (seen with ops test fixtures) — surface so the UI can flag it
        "pixellotVenueId": data.get("pixellot_id"),
        "producerName": data.get("producer_name"),
    }


# ── verdict engine ───────────────────────────────────────────────

# ── time-anchored local signals (Get-EventWindowSignals.ps1) ────
# Boots/shutdowns, GPU faults, Pixellot service failures, and app crashes
# from the Windows event logs, intersected with each event's scheduled
# window — evidence anchored to the event itself.

import re as _re


def _off_periods(signals, now):
    """(start, end) spans where the box was off, from shutdown->boot pairs."""
    boots = sorted(b for b in (signals.get("boots") or []) if _parse_iso(b))
    boot_times = [_parse_iso(b) for b in boots]
    periods = []
    for sd in signals.get("shutdowns") or []:
        t = _parse_iso(sd.get("time"))
        if not t:
            continue
        nxt = next((b for b in boot_times if b > t), now)
        periods.append((t, nxt))
    return periods


def _service_name(detail):
    m = _re.search(r"The (.{1,60}?) service", detail or "")
    return m.group(1) if m else "Pixellot"


def _window_signal_markers(start, end, signals, now):
    """Markers for box-side trouble that overlapped [start, end]."""
    if not signals or not start:
        return []
    end = end or start
    markers = []

    boots = [_parse_iso(b) for b in (signals.get("boots") or [])]
    if any(b and start <= b <= end for b in boots):
        markers.append("Unit rebooted mid-event")
    elif any(s < end and e > start for s, e in _off_periods(signals, now)):
        markers.append("Unit was off during the event")

    def _in_window(items):
        hits = []
        for i in items or []:
            t = _parse_iso(i.get("time"))
            if t and start <= t <= end:
                hits.append(i)
        return hits

    gpu = _in_window(signals.get("gpuErrors"))
    if gpu:
        markers.append(f"GPU driver faults during the event ({len(gpu)})")

    svc = _in_window(signals.get("serviceEvents"))
    if svc:
        names = sorted({_service_name(s.get("detail")) for s in svc})
        markers.append(", ".join(names) + " service failed during the event")

    if _in_window(signals.get("appCrashes")):
        markers.append("Pixellot software crashed during the event")

    # Agent/Coordinator/KeepAgentUp are plain processes (not services) — a
    # "start new log" restart inside the window means one died and was
    # recovered. A restart within 5 min of a boot is just normal startup.
    names = set()
    for r in _in_window(signals.get("processRestarts")):
        t = _parse_iso(r.get("time"))
        if not t:
            continue
        # midnight "start new log" lines are daily log rotation, not crashes
        # (field truth: all three processes emit one at 00:00 local)
        if t.hour == 0 and t.minute <= 1:
            continue
        if not any(b and 0 <= (t - b).total_seconds() <= 300 for b in boots):
            names.add(r.get("process") or "Pixellot process")
    if names:
        markers.append(", ".join(sorted(names)) + " restarted mid-event")

    return markers


# A broadcast that hasn't gone on air is judged against its scheduled WINDOW
# (start .. start + duration): inside the window it's an active incident
# ("unable to stream" — the tech may be standing at the box right now);
# once the window has fully passed it's history ("did not stream"). Unity's
# broadcast `duration` is the scheduled length in hours; when we don't have
# it (listed events from the search index), assume a typical game window.
_DEFAULT_WINDOW_HOURS = 3.0


def _verdict_from_eqs(eqs_entry):
    """Verdict for an event EQS actually scored."""
    on_air = eqs_entry.get("onAir")
    duration = eqs_entry.get("eventDuration")
    score = eqs_entry.get("eventScore")
    reasons = []
    if on_air is False:
        return "failed", ["Never went on air"]
    comp_fails = [
        name
        for name in ("exposure", "calibration", "focus", "scoreboard")
        if eqs_entry.get(name) is False
    ]
    if eqs_entry.get("audio") in (0, False):
        comp_fails.append("audio")
    if duration is False and not eqs_entry.get("wasManuallyEnded"):
        # Short streams are common fleet-wide — only call it "died mid-event"
        # when the quality score corroborates something actually went wrong.
        if score is not None and score < 0.6:
            reasons.append("Ended early")
            if comp_fails:
                reasons.append("Failed: " + ", ".join(comp_fails))
            return "partial", reasons
        reasons.append("Ran short of schedule (often benign)")
    if comp_fails:
        reasons.append("Failed: " + ", ".join(comp_fails))
        return "quality", reasons
    return "streamed", reasons


def _verdict_for(entry, eqs, now):
    """Compute (verdict, reasons) for one timeline entry."""
    start = _parse_iso(entry.get("startTime"))
    status = (entry.get("status") or "").lower()
    game_key = entry.get("gameKey")

    if status == "on_air":
        return "live", ["On air now"]
    if start and start > now:
        return "upcoming", []

    scored = eqs["byEvent"].get(game_key) if game_key else None
    if scored:
        entry["eqs"] = {
            k: scored.get(k)
            for k in (
                "onAir", "eventDuration", "exposure", "calibration", "focus",
                "calibrationZoomSet", "audio", "scoreboard", "wasManuallyEnded",
                "eventScore",
            )
        }
        return _verdict_from_eqs(scored)

    if status == "scheduled" and start and start <= now:
        try:
            hours = float(entry.get("durationHours") or _DEFAULT_WINDOW_HOURS)
        except (TypeError, ValueError):
            hours = _DEFAULT_WINDOW_HOURS
        window_end = start + timedelta(hours=hours)
        if now <= window_end:
            mins = int((now - start).total_seconds() // 60)
            return "unable", [
                f"Event started {mins} min ago, not on air yet.",
            ]
        return "failed", ["Never went on air"]
    if status == "complete":
        return "streamed", ["Complete (not scored)"]
    return "unknown", []


# Event Success Rate over the venue's last N public events whose outcome is
# known. Success = the event went on air (a quality miss or early end still
# counts); a never-aired event is the failure. Live, upcoming, in-window and
# unknown events are not counted. Unlisted and test events stay out, matching
# how ops treats ESR (unlisting a doomed event keeps it off the number). This
# is Pulse's own count from the public API, not the Sigma dashboard figure.
ESR_WINDOW = 10
_ESR_JUDGED = ("streamed", "quality", "partial", "failed")


def esr_summary(entries, window=ESR_WINDOW):
    judged = [
        e for e in entries
        if not e.get("unlisted") and e.get("verdict") in _ESR_JUDGED
    ]
    judged.sort(key=lambda e: e.get("startTime") or "", reverse=True)
    recent = judged[:window]
    ok = sum(1 for e in recent if e["verdict"] != "failed")
    return {
        "window": window,
        "counted": len(recent),
        "succeeded": ok,
        "rate": ok / len(recent) if recent else None,
    }


def _esr_from_listed(listed_items, eqs, now):
    """ESR over the full listed history (not just the timeline's 14 days)."""
    entries = []
    for item in listed_items:
        if item.get("is_testing") or item.get("is_deleted"):
            continue
        entry = {
            "gameKey": item.get("key"),
            "startTime": item.get("start_time"),
            "status": item.get("status"),
            "durationHours": None,
        }
        entry["verdict"], _ = _verdict_for(entry, eqs, now)
        entries.append(entry)
    return esr_summary(entries)


def _merge_timeline(listed_items, box_broadcasts, local_events, eqs, now, signals=None):
    """Combine listed schedule + box-driven broadcasts into one timeline."""
    local_by_id = {e.get("eventId"): e for e in local_events if e.get("eventId")}
    past_cut = now - timedelta(days=LISTED_PAST_DAYS)
    future_cut = now + timedelta(days=LISTED_FUTURE_DAYS)

    timeline = {}

    for item in listed_items:
        start = _parse_iso(item.get("start_time"))
        if not start or start < past_cut or start > future_cut:
            continue
        key = item.get("key")
        timeline[key] = {
            "gameKey": key,
            "headline": item.get("headline") or item.get("sport") or "Event",
            "sport": item.get("sport"),
            "startTime": item.get("start_time"),
            "localStartTime": item.get("local_start_time"),
            "status": item.get("status"),
            "hasVod": item.get("has_vod"),
            "source": "listed",
            "unlisted": False,
            "durationHours": None,
            "pixellotEventId": None,
            "local": None,
            "eqs": None,
        }

    for bdc in box_broadcasts:
        if not bdc:
            continue
        key = bdc.get("gameKey") or bdc.get("broadcastKey")
        entry = timeline.get(key)
        if entry is None:
            headline = bdc.get("headline") or "Unlisted / test event"
            if bdc.get("subheadline"):
                headline += f" — {bdc['subheadline']}"
            entry = timeline[key] = {
                "gameKey": bdc.get("gameKey"),
                "headline": headline,
                "sport": None,
                "startTime": bdc.get("startTime"),
                "localStartTime": None,
                "status": bdc.get("status"),
                "hasVod": bool(bdc.get("vodKey")),
                "source": "box",
                "unlisted": bool(bdc.get("unlisted")),
                "local": None,
                "eqs": None,
            }
        else:
            entry["source"] = "listed+box"
        entry["durationHours"] = bdc.get("durationHours")
        entry["pixellotEventId"] = bdc.get("pixellotEventId")
        entry["broadcastKey"] = bdc.get("broadcastKey")
        entry["registeredVenueId"] = bdc.get("pixellotVenueId")
        loc = local_by_id.get(bdc.get("pixellotEventId"))
        if loc:
            entry["local"] = {
                "recorded": (loc.get("videoBytes") or 0) > 0,
                "videoBytes": loc.get("videoBytes"),
                "uploadedCount": loc.get("uploadedCount"),
                "name": loc.get("name"),
            }

    for entry in timeline.values():
        verdict, reasons = _verdict_for(entry, eqs, now)
        # Time-anchored box signals (reboots, GPU faults, service failures,
        # crashes) that overlapped this event's window.
        sig_markers = []
        if verdict in ("failed", "partial", "unable", "quality"):
            start = _parse_iso(entry.get("startTime"))
            if start:
                try:
                    hours = float(entry.get("durationHours") or _DEFAULT_WINDOW_HOURS)
                except (TypeError, ValueError):
                    hours = _DEFAULT_WINDOW_HOURS
                sig_markers = _window_signal_markers(
                    start, start + timedelta(hours=hours), signals, now
                )
        reasons.extend(sig_markers)
        # Local recording evidence sharpens a failed/partial verdict — unless
        # an off-period already explains why nothing was recorded.
        loc = entry.get("local")
        if loc and verdict in ("failed", "partial"):
            if loc["recorded"]:
                if not loc.get("uploadedCount"):
                    reasons.append("Box recorded, nothing uploaded — likely network block")
                else:
                    reasons.append("Box recorded video — issue in the streaming path")
            elif not any("off during" in m or "rebooted" in m for m in sig_markers):
                reasons.append("Box never recorded — camera/capture side")
        entry["verdict"] = verdict
        entry["verdictReasons"] = reasons

    ordered = sorted(
        timeline.values(), key=lambda e: e.get("startTime") or "", reverse=True
    )
    return ordered


# The camera/bandwidth metrics are only trustworthy while the VPU is
# streaming (or was, very recently) — on a long-idle box they can be stale.
# The hints derived from them are gated on an event window that is active
# or ended within this tail.
_METRICS_FRESH_TAIL = timedelta(hours=2)


def _metrics_fresh(timeline, now):
    """True if any event window is active or ended within the fresh tail —
    OR the most recent past event failed. A failed last event means the
    metrics' story is still the current story: the hint lingers until
    something streams successfully."""
    last_past_verdict = None
    for entry in timeline:  # timeline is sorted newest-first
        start = _parse_iso(entry.get("startTime"))
        if not start or start > now:
            continue
        if last_past_verdict is None:
            last_past_verdict = entry.get("verdict")
        try:
            hours = float(entry.get("durationHours") or _DEFAULT_WINDOW_HOURS)
        except (TypeError, ValueError):
            hours = _DEFAULT_WINDOW_HOURS
        if start + timedelta(hours=hours) >= now - _METRICS_FRESH_TAIL:
            return True
    return last_past_verdict in ("failed", "unable")


def _cause_hints(metrics, producer, metrics_fresh):
    """Unit-level hints from live metrics — current state, labeled as such."""
    hints = []
    if not metrics:
        return hints
    if metrics.get("connection") not in (None, "Ok"):
        hints.append({
            "severity": "critical",
            "text": "Pixellot Cloud cannot reach this VPU (connection "
                    f"{metrics.get('connection')}) — box offline or network blocked",
            "page": "network",
        })
    elif metrics_fresh:
        dark = metrics.get("darkCourt") == "Error"
        no_bw = (
            metrics.get("hdBandwidth") == "Error"
            and metrics.get("panoBandwidth") == "Error"
        )
        if dark and no_bw:
            hints.append({
                "severity": "critical",
                "text": "Box is online but no camera video is reaching the "
                        "cloud — check camera connections",
                "page": "cameras",
            })
        elif dark:
            hints.append({
                "severity": "warning",
                "text": "Cloud reports the camera picture is dark — camera "
                        "may be obstructed, powered off, or the room is dark",
                "page": "cameras",
            })
        elif no_bw:
            hints.append({
                "severity": "critical",
                "text": "Box is online and the camera picture looks OK, but "
                        "no video is reaching the cloud — the venue network "
                        "may be blocking the streaming ports",
                "page": "network",
            })
    if producer:
        cur, tgt = producer.get("currentSwVersion"), producer.get("targetSwVersion")
        if cur and tgt and cur != tgt:
            hints.append({
                "severity": "info",
                "text": f"Pixellot software is behind its target ({cur} installed, "
                        f"{tgt} assigned)",
                "page": None,
            })
        if producer.get("broadcastStatusReason"):
            hints.append({
                "severity": "warning",
                "text": "Cloud broadcast status reason: "
                        + str(producer["broadcastStatusReason"]),
                "page": None,
            })
    return hints


# ── entry point ──────────────────────────────────────────────────


def fetch_cloud(venue_id, local_events, signals=None):
    """Blocking; call via run_in_executor. Returns the `cloud` payload dict.

    local_events: the `events` list from Get-PixellotEvents.ps1 (may be []).
    signals: payload from Get-EventWindowSignals.ps1 (may be None).
    """
    if DEMO_MODE:
        import demo_data
        return demo_data.demo_cloud_events(venue_id, local_events)
    if not isinstance(signals, dict) or signals.get("error"):
        signals = None

    now = datetime.now(timezone.utc)
    if not venue_id:
        return {"available": False, "error": "no venue id", "events": []}

    with ThreadPoolExecutor(max_workers=4) as pool:
        f_producer = pool.submit(_try, _fetch_producer, venue_id)
        f_listed = pool.submit(_try, _fetch_listed_events, venue_id)
        f_eqs = pool.submit(_try, _fetch_eqs, venue_id)

        producer, err_producer = f_producer.result()
        listed, err_listed = f_listed.result()
        eqs, err_eqs = f_eqs.result()

        metrics, err_metrics = (None, None)
        if producer and producer.get("pixellotKey"):
            metrics, err_metrics = _try(_fetch_metrics, producer["pixellotKey"])

        # Box-driven lookups: newest local event ids first, capped.
        box_broadcasts = []
        ids = [e.get("eventId") for e in local_events if e.get("eventId")]
        futures = [
            pool.submit(_try, _fetch_broadcast_by_event_id, eid)
            for eid in ids[:MAX_BOX_LOOKUPS]
        ]
        for fut in futures:
            result, _err = fut.result()  # 404s (stale folders) are expected
            if result:
                box_broadcasts.append(result)

    errors = {
        k: v
        for k, v in (
            ("producer", err_producer), ("events", err_listed),
            ("eqs", err_eqs), ("metrics", err_metrics),
        )
        if v
    }

    # All primary calls failed -> the cloud is unreachable from here.
    if producer is None and listed is None and eqs is None:
        return {
            "available": False,
            "error": "Cloud APIs unreachable (network may block or intercept "
                     "outbound HTTPS)",
            "errors": errors,
            "events": [],
        }

    eqs = eqs or {"avgScore": None, "byEvent": {}, "excluded": set()}
    timeline = _merge_timeline(
        listed or [], box_broadcasts, local_events, eqs, now, signals
    )

    hints = _cause_hints(metrics, producer, _metrics_fresh(timeline, now))
    # No producer record: if Unity's venue registry still knows the unit, it
    # was installed on Pixellot's side but never onboarded into NFHS — a
    # cloud-side provisioning gap, not a box fault.
    venue_record = None
    if producer is None:
        venue_record, _e = _try(_fetch_venue_record, venue_id)
        if venue_record:
            hints.insert(0, {
                "severity": "warning",
                "text": "This unit is registered in Pixellot Club (as "
                        f"'{venue_record.get('name')}') but has no NFHS "
                        "producer mapping — events cannot be scheduled to it. "
                        "Confirm that this unit is properly activated in the "
                        "NFHS Console.",
                "page": None,
            })

    return {
        "available": True,
        "error": None,
        "errors": errors or None,
        "producer": producer,
        "metrics": metrics,
        "eqsAvgScore": eqs.get("avgScore"),
        # None when the events lookup failed, so the UI can say so.
        "esr": _esr_from_listed(listed, eqs, now) if listed is not None else None,
        "events": timeline,
        "venueRecord": venue_record,
        "causeHints": hints,
        "generatedAt": now.isoformat(),
    }
