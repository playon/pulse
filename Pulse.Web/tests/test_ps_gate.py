"""The PowerShell slot gate admits longest-job-first, never exceeds its cap,
and lets neither actions nor short scripts starve."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
import powershell as ps  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


def test_admits_longest_first_and_caps_concurrency():
    async def go():
        gate = ps._SlotGate(2)
        order, live, peak = [], 0, 0

        async def job(name, cost):
            nonlocal live, peak
            await gate.acquire(cost)
            live += 1; peak = max(peak, live); order.append(name)
            await asyncio.sleep(0.02)
            live -= 1
            gate.release()

        await gate.acquire(0); await gate.acquire(0)   # fill both slots
        tasks = [asyncio.create_task(job(n, c)) for n, c in
                 [("fast", 0.4), ("slow", 3.5), ("mid", 1.5)]]
        await asyncio.sleep(0)
        gate.release(); gate.release()
        await asyncio.gather(*tasks)
        return order, peak
    order, peak = _run(go())
    assert order == ["slow", "mid", "fast"]
    assert peak <= 2


def test_unhinted_script_outranks_every_collector():
    assert ps._UNHINTED_COST > max(ps._COST_HINTS.values())
    assert "Restart-Service.ps1" not in ps._COST_HINTS


def test_cancelled_waiter_does_not_leak_a_slot():
    async def go():
        gate = ps._SlotGate(1)
        await gate.acquire(1)
        t = asyncio.create_task(gate.acquire(1))
        await asyncio.sleep(0)
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass
        gate.release()
        await asyncio.wait_for(gate.acquire(1), 0.5)   # slot is free again
    _run(go())


def test_waiting_job_ages_past_a_slow_one():
    async def go():
        gate = ps._SlotGate(1)
        await gate.acquire(1)
        short = asyncio.create_task(gate.acquire(0.4))
        await asyncio.sleep(0)
        gate._waiters[0][1] -= 10          # short has waited 10 s
        slow = asyncio.create_task(gate.acquire(3.5))
        await asyncio.sleep(0)
        gate.release()
        await asyncio.wait_for(short, 0.5)
        assert not slow.done()
        slow.cancel()
    _run(go())
