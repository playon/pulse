#!/usr/bin/env python3
"""Wait for every other check on a commit to finish, then pass or fail.

Pulse's CI guards are path-filtered, so a given pull request runs some of
them and not others. A branch rule can only require a check that ALWAYS
reports, and a required check that never starts leaves the PR waiting
forever. This is the one check that always runs: it waits for whatever
checks did start on the commit and mirrors their result, so "CI gate" is the
single name to require.

How it decides what to wait for: it does not know the path filters. It waits
a grace period for the filtered workflows to appear, then polls until every
check run on the commit (other than itself) has completed and the set of
runs has stopped growing. A workflow skipped by its path filter never
appears, which is correct.

Run locally:   python3 tools/ci-gate/ci_gate.py --self-test
In CI:         python3 tools/ci-gate/ci_gate.py --repo OWNER/NAME --sha SHA

Pure ASCII on purpose, like the other committed guards.
"""
import argparse
import json
import subprocess
import sys
import time

GATE_NAME = "CI gate"
# Conclusions that mean "this check did not pass". success, neutral and
# skipped are fine: a skipped job inside a running workflow is not a failure.
BAD = {"failure", "cancelled", "timed_out", "action_required",
       "startup_failure", "stale"}


def classify(runs, gate_name=GATE_NAME):
    """Return (pending, failed, passed) lists of check names, gate excluded."""
    pending, failed, passed = [], [], []
    for r in runs:
        name = r.get("name", "")
        if name == gate_name:
            continue
        if r.get("status") != "completed":
            pending.append(name)
        elif r.get("conclusion") in BAD:
            failed.append("%s (%s)" % (name, r.get("conclusion")))
        else:
            passed.append(name)
    return pending, failed, passed


def fetch_runs(repo, sha):
    out = subprocess.run(
        ["gh", "api", "--paginate",
         "repos/%s/commits/%s/check-runs?per_page=100" % (repo, sha),
         "--jq", ".check_runs[]"],
        check=True, capture_output=True, text=True).stdout
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def wait(repo, sha, grace, poll, timeout, fetch=fetch_runs, sleep=time.sleep,
         now=time.monotonic):
    start = now()
    print("Waiting %ss for path-filtered workflows to start..." % grace)
    sleep(grace)
    last_ids, stable = None, 0
    while True:
        runs = fetch(repo, sha)
        ids = sorted(r.get("id", 0) for r in runs if r.get("name") != GATE_NAME)
        pending, failed, passed = classify(runs)
        print("checks: %d passed, %d failed, %d pending" %
              (len(passed), len(failed), len(pending)))
        if failed:
            print("FAILED:")
            for f in failed:
                print("  " + f)
            return 1
        # Done only when nothing is pending AND the set of runs has held
        # still for two polls, so a workflow that was slow to start is not
        # missed by a single quiet moment.
        stable = stable + 1 if (not pending and ids == last_ids) else 0
        last_ids = ids
        if not pending and stable >= 2:
            print("All %d checks passed." % len(passed) if passed
                  else "No other checks ran for this change. Nothing to wait for.")
            return 0
        if now() - start > timeout:
            print("TIMED OUT with pending: " + ", ".join(pending or ["(none)"]))
            return 1
        sleep(poll)


def self_test():
    def run(name, status="completed", conclusion="success", id_=1):
        return {"name": name, "status": status, "conclusion": conclusion,
                "id": id_}

    p, f, ok = classify([run("a"), run(GATE_NAME), run("b", "in_progress", None)])
    assert (p, f, ok) == (["b"], [], ["a"]), (p, f, ok)
    p, f, ok = classify([run("a", conclusion="failure"), run("b", conclusion="skipped")])
    assert f == ["a (failure)"] and ok == ["b"], (f, ok)
    p, f, ok = classify([run("a", conclusion="cancelled")])
    assert f == ["a (cancelled)"]

    clock = [0.0]
    sleep = lambda s: clock.__setitem__(0, clock[0] + s)
    now = lambda: clock[0]

    # nothing else ever ran -> pass
    assert wait("r", "s", 0, 1, 60, lambda *a: [run(GATE_NAME)], sleep, now) == 0
    # one check, finishes on the third poll -> pass
    seq = iter([[run("a", "queued", None)], [run("a", "in_progress", None)]])
    def fetch(*a):
        try:
            return next(seq)
        except StopIteration:
            return [run("a")]
    assert wait("r", "s", 0, 1, 60, fetch, sleep, now) == 0
    # a failure -> fail immediately
    assert wait("r", "s", 0, 1, 60, lambda *a: [run("a", conclusion="failure")], sleep, now) == 1
    # a late workflow appears after the first quiet poll -> still waited for
    state = {"n": 0}
    def late(*a):
        state["n"] += 1
        if state["n"] == 1:
            return [run("a", id_=1)]
        return [run("a", id_=1), run("b", "in_progress", None, id_=2)] if state["n"] < 4 \
            else [run("a", id_=1), run("b", conclusion="failure", id_=2)]
    assert wait("r", "s", 0, 1, 60, late, sleep, now) == 1
    # never finishes -> timeout fails
    assert wait("r", "s", 0, 1, 5, lambda *a: [run("a", "in_progress", None)], sleep, now) == 1
    print("self-test OK")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo")
    ap.add_argument("--sha")
    ap.add_argument("--grace", type=int, default=45)
    ap.add_argument("--poll", type=int, default=15)
    ap.add_argument("--timeout", type=int, default=1200)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not (a.repo and a.sha):
        ap.error("--repo and --sha are required")
    return wait(a.repo, a.sha, a.grace, a.poll, a.timeout)


if __name__ == "__main__":
    sys.exit(main())
