"""Run PowerShell scripts and capture JSON output."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from collections import deque
from datetime import datetime
from typing import Optional

# Mirror every script-log entry into the root logger so it also flows
# to pulse-server.log (the file handler is wired in main.py). Lets the
# Server Log pane in the UI show full PS execution history alongside
# uvicorn/fastapi output.
_file_log = logging.getLogger("pulse.ps")

SCRIPTS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")
)

DEMO_MODE = sys.platform != "win32"

# When the server runs under pythonw.exe (the hidden launcher) it has no
# console of its own. Spawning powershell.exe — a console-subsystem app —
# would then make Windows allocate a NEW visible console window for every
# script call (and the WebSocket poll fires several per cycle). CREATE_NO_WINDOW
# runs each child with no window while still letting us capture its piped
# stdout/stderr. 0 on non-Windows (where the real subprocess path never runs).
_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

LOG_BUFFER: deque[dict] = deque(maxlen=500)
RUNNING_TASKS: dict[str, dict] = {}

# Cap concurrent PowerShell processes to avoid CPU-starving VPU hardware.
# Dashboard scripts get priority; network/heavy tests queue behind them.
_PS_SEMAPHORE: Optional[asyncio.Semaphore] = None


def _get_semaphore() -> asyncio.Semaphore:
    global _PS_SEMAPHORE
    if _PS_SEMAPHORE is None:
        _PS_SEMAPHORE = asyncio.Semaphore(4)
    return _PS_SEMAPHORE


def _log(script: str, duration_ms: float, status: str, detail: str = "", size: int = 0):
    entry = {
        "ts": datetime.now().isoformat(timespec="milliseconds"),
        "script": script,
        "durationMs": round(duration_ms, 1),
        "status": status,
        "detail": detail,
        "bytes": size,
    }
    LOG_BUFFER.append(entry)
    # Mirror into pulse-server.log via the root logger. Pick the log
    # level from the status field so warnings and errors stand out.
    level = (
        logging.ERROR if status in ("error", "fail") else
        logging.WARNING if status in ("timeout", "warn", "cancelled") else
        logging.INFO
    )
    bytes_str = f" ({size}B)" if size else ""
    _file_log.log(level, f"{script} {duration_ms:.0f}ms [{status}]{bytes_str} {detail}")
    return entry


def get_running_tasks() -> list[dict]:
    now = time.monotonic()
    return [
        {"id": tid, "script": t["script"], "runningSec": round(now - t["started"], 1),
         # "queued" until the 4-slot semaphore admits it. The splash feed shows
         # the difference so a backed-up box reads as waiting, not as slow.
         "state": "running" if t.get("active") else "queued"}
        for tid, t in RUNNING_TASKS.items()
    ]


def cancel_task(task_id: str) -> bool:
    task = RUNNING_TASKS.get(task_id)
    if not task:
        return False
    handle = task.get("handle")
    if handle:
        try:
            handle.kill()
        except ProcessLookupError:
            pass
    cancel_evt = task.get("cancel")
    if cancel_evt:
        cancel_evt.set()
    return True


def cancel_all_tasks() -> int:
    count = 0
    for tid in list(RUNNING_TASKS):
        if cancel_task(tid):
            count += 1
    return count


# ── Short-TTL result cache + in-flight deduplication ─────────
# During Pulse's initial preload, several endpoints call the same scripts:
# /api/dashboard runs Get-NicAdapters; /api/cameras then runs it again
# moments later. With a small TTL on results and a registry of in-flight
# futures, the second caller either:
#   - awaits the same future the first call already kicked off, or
#   - returns the cached payload from the recently-completed first call.
#
# A 25-second TTL is long enough for an entire preload burst to share
# results, short enough that no stale snapshot ever appears in a real
# refresh action (the user's "Refresh" button clears the client cache
# and waits 25s+ between successive clicks in practice).
_RESULT_CACHE: dict = {}                         # cache_key -> (stored_at, result)
_INFLIGHT: dict = {}                             # cache_key -> asyncio.Future
_RESULT_TTL = 25.0                               # seconds


def _cache_key(script_name: str, args: Optional[dict], timeout: int) -> tuple:
    """Deterministic cache key. Args dicts must be hashable as a frozenset.

    The timeout is deliberately NOT part of the key: it shapes how long a run
    may take, not what it returns, and callers pass different budgets for the
    same script (dashboard 30s / network 45s / preload 40s for the port
    sweep). Keying on it made those calls miss each other's cache AND
    in-flight futures, so every cold start ran Test-NetworkPorts twice in
    parallel — two of the four PowerShell slots pinned for the sweep's whole
    duration. Whichever caller starts the run first sets its timeout; that is
    an acceptable wobble for identical-output scripts.
    """
    del timeout
    arg_items = tuple(sorted((args or {}).items()))
    return (script_name, arg_items)


def _extract_json(text: str):
    """Parse JSON from script stdout, tolerating leading non-JSON noise.

    Every Pulse PS script is supposed to emit exactly one compressed JSON
    object as its final stdout line. In practice a script can leak content
    ahead of that — a PowerShell warning/verbose record that escaped
    redirection, a module-load banner, a stray Write-Output. A naive
    json.loads(whole_blob) then fails and we lose otherwise-good data.

    Strategy, cheapest first:
      1. Parse the whole (stripped) string.
      2. Scan lines from the end for the first that parses as a JSON
         object/array — recovers the canonical "JSON on the last line" case.
      3. Substring from first '{' to last '}' as a last resort.
    Returns the parsed object, or None if nothing parses.

    All three stages parse with strict=False. Windows PowerShell 5.1's
    ConvertTo-Json (unlike PS 7's) leaves literal C0 control bytes
    unescaped inside string values — e.g. the STX/ETX framing in a raw
    Daktronics RTD scoreboard string, or a NUL scraped by findstr from a
    UTF-16 log. Python's default strict parse rejects those ("Invalid
    control character"), discarding otherwise-good data; strict=False
    accepts them. It only relaxes the in-string control-char rule, so
    valid JSON still parses identically — no downside.
    """
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        pass
    for line in reversed(text.splitlines()):
        candidate = line.strip()
        if candidate[:1] in ("{", "["):
            try:
                return json.loads(candidate, strict=False)
            except json.JSONDecodeError:
                continue
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1], strict=False)
        except json.JSONDecodeError:
            pass
    return None


async def run_ps(
    script_name: str, args: Optional[dict] = None, timeout: int = 30,
    use_cache: bool = True, cache_ttl: Optional[float] = None,
) -> dict:
    """Run a PowerShell script and return its parsed JSON.

    use_cache=False bypasses the result cache and in-flight dedup entirely,
    so the script always runs fresh. Used for point-in-time captures (e.g.
    camera frame grabs) where a 25s-old cached result would be wrong — a
    second 'Get Camera Frames' click must capture new frames, not replay
    the previous ones.

    cache_ttl overrides how old a cached result may be (in seconds) for THIS
    call to accept it, without changing what other callers see. The cache is
    age-based (it stores each result's timestamp), so a live poll can demand
    near-fresh data — e.g. cache_ttl=1.5 for NIC link state so a cable
    unplug shows up within a poll or two — while heavier callers keep reusing
    the default 25s window. They share the key but never serve each other
    stale data, because freshness is judged at read time, per caller.
    """
    key = _cache_key(script_name, args, timeout)

    if use_cache:
        # 1. Fresh cached result? Return it immediately — no semaphore, no PS.
        entry = _RESULT_CACHE.get(key)
        ttl = cache_ttl if cache_ttl is not None else _RESULT_TTL
        if entry and (time.monotonic() - entry[0]) < ttl:
            return entry[1]

        # 2. Same script already running? Await its future instead of duplicating.
        inflight = _INFLIGHT.get(key)
        if inflight and not inflight.done():
            return await inflight

    # 3. Cache miss (or cache bypassed) — actually invoke PowerShell.
    future: asyncio.Future = asyncio.get_event_loop().create_future()
    if use_cache:
        _INFLIGHT[key] = future

    task_id = uuid.uuid4().hex[:8]
    t0 = time.monotonic()
    cancel_evt = asyncio.Event()
    RUNNING_TASKS[task_id] = {
        "script": script_name,
        "started": t0,
        "handle": None,
        "cancel": cancel_evt,
    }

    try:
        async with _get_semaphore():
            RUNNING_TASKS[task_id]["active"] = True
            result = await _run_ps_inner(script_name, args, timeout, task_id, cancel_evt)
        # Only cache successful results. Errors should retry on next call.
        if use_cache and isinstance(result, dict) and not result.get("error"):
            _RESULT_CACHE[key] = (time.monotonic(), result)
        future.set_result(result)
        return result
    except Exception as e:
        if not future.done():
            future.set_exception(e)
        raise
    finally:
        RUNNING_TASKS.pop(task_id, None)
        # Free the in-flight slot once the future is resolved either way.
        if _INFLIGHT.get(key) is future:
            _INFLIGHT.pop(key, None)


def clear_ps_cache() -> int:
    """Drop all cached PS results. Used by the global Refresh action."""
    n = len(_RESULT_CACHE)
    _RESULT_CACHE.clear()
    return n


async def _run_ps_inner(script_name, args, timeout, task_id, cancel_evt):
    t0 = RUNNING_TASKS[task_id]["started"]

    if DEMO_MODE:
        from demo_data import get_demo

        try:
            await asyncio.wait_for(
                cancel_evt.wait(),
                timeout=0.05 + 0.15 * __import__("random").random(),
            )
            ms = (time.monotonic() - t0) * 1000
            _log(script_name, ms, "cancelled", "user cancelled")
            return {"error": True, "message": f"Cancelled: {script_name}"}
        except asyncio.TimeoutError:
            pass

        result = get_demo(script_name, args)
        ms = (time.monotonic() - t0) * 1000
        if result is not None:
            raw = json.dumps(result)
            _log(script_name, ms, "ok", "demo mode", len(raw))
            return result
        _log(script_name, ms, "error", "no demo data for this script")
        return {"error": True, "message": f"No demo data for {script_name}"}

    script_path = os.path.join(SCRIPTS_DIR, script_name)
    if not os.path.isfile(script_path):
        _log(script_name, (time.monotonic() - t0) * 1000, "error", "script not found")
        return {"error": True, "message": f"Script not found: {script_name}"}

    cmd = [
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", script_path,
    ]
    if args:
        for key, value in args.items():
            cmd.extend([f"-{key}", str(value)])

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            creationflags=_CREATE_NO_WINDOW,
        )
        RUNNING_TASKS[task_id]["handle"] = proc

        async def wait_cancel():
            await cancel_evt.wait()
            try:
                proc.kill()
            except ProcessLookupError:
                pass

        cancel_task_coro = asyncio.create_task(wait_cancel())
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        finally:
            cancel_task_coro.cancel()

        if cancel_evt.is_set():
            ms = (time.monotonic() - t0) * 1000
            _log(script_name, ms, "cancelled", "user cancelled")
            return {"error": True, "message": f"Cancelled: {script_name}"}

        ms = (time.monotonic() - t0) * 1000
        output = stdout.decode("utf-8", errors="replace").strip()
        stderr_text = stderr.decode("utf-8", errors="replace").strip()
        exit_code = proc.returncode

        # ── Empty stdout ─────────────────────────────────────────
        # The script died before emitting JSON (e.g. Add-Type / COM /
        # registry failure outside a try, missing cmdlet, early exit).
        # The reason is almost always in stderr — surface it instead of
        # the old useless "No output" so the field tester sees WHY.
        if not output:
            detail = (f"no stdout; exit={exit_code}; stderr: {stderr_text[:200]}"
                      if stderr_text else f"no stdout, no stderr; exit={exit_code}")
            _log(script_name, ms, "error", detail, 0)
            if stderr_text:
                msg = f"{script_name} produced no output. PowerShell error: {stderr_text[:500]}"
            else:
                msg = (f"{script_name} produced no output and no error text "
                       f"(exit code {exit_code}). The script may have failed to start "
                       f"or exited before emitting JSON.")
            return {
                "error": True,
                "message": msg,
                "stderr": stderr_text[:2000] or None,
                "exitCode": exit_code,
            }

        # ── Parse (tolerant of leading noise) ────────────────────
        result = _extract_json(output)
        if result is None:
            snippet = output[:200].replace("\n", " ")
            _log(script_name, ms, "error", f"unparseable stdout; head: {snippet}")
            return {
                "error": True,
                "message": (f"Invalid JSON from {script_name}. "
                            f"Output started with: {output[:300]}"),
                "stderr": stderr_text[:2000] or None,
                "rawHead": output[:500],
                "exitCode": exit_code,
            }

        # Recovered from noisy stdout? Log a warning so we notice the script
        # is leaking non-JSON, but still return the good data.
        recovered = output[:1] not in ("{", "[")
        if recovered:
            _log(script_name, ms, "warn", "recovered JSON from noisy stdout", len(output))
        else:
            detail = stderr_text[:200] if stderr_text else "ok"
            _log(script_name, ms, "ok", detail, len(output))
        return result

    except asyncio.TimeoutError:
        ms = (time.monotonic() - t0) * 1000
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        _log(script_name, ms, "timeout", f"after {timeout}s")
        return {"error": True, "message": f"Timeout after {timeout}s: {script_name}"}

    except FileNotFoundError:
        ms = (time.monotonic() - t0) * 1000
        _log(script_name, ms, "error", "powershell.exe not found")
        return {"error": True, "message": "powershell.exe not found — this tool requires Windows"}

    except Exception as e:
        ms = (time.monotonic() - t0) * 1000
        _log(script_name, ms, "error", str(e))
        return {"error": True, "message": str(e)}
