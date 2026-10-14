"""Unit tests for the Event Streaming ESR count (cloud_api.esr_summary).

    cd Pulse.Web && python3 -m unittest discover -s tests
"""

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

_APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import cloud_api  # noqa: E402

NOW = datetime(2026, 10, 5, 18, 0, tzinfo=timezone.utc)
NO_EQS = {"avgScore": None, "byEvent": {}, "excluded": set()}


def _ev(days_ago, verdict, unlisted=False):
    start = (NOW - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return {"startTime": start, "verdict": verdict, "unlisted": unlisted}


def _listed(days_ago, status, **flags):
    start = (NOW - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return {"key": f"gam{days_ago}", "start_time": start, "status": status, **flags}


class EsrSummary(unittest.TestCase):
    def test_on_air_with_quality_miss_counts_as_success(self):
        r = cloud_api.esr_summary([_ev(1, "streamed"), _ev(2, "quality"), _ev(3, "partial"), _ev(4, "failed")])
        self.assertEqual((r["succeeded"], r["counted"]), (3, 4))
        self.assertAlmostEqual(r["rate"], 0.75)

    def test_unjudged_and_unlisted_are_not_counted(self):
        r = cloud_api.esr_summary([
            _ev(0, "live"), _ev(-1, "upcoming"), _ev(0, "unable"), _ev(5, "unknown"),
            _ev(2, "failed", unlisted=True), _ev(3, "streamed"),
        ])
        self.assertEqual((r["succeeded"], r["counted"]), (1, 1))

    def test_window_keeps_the_most_recent(self):
        old_failures = [_ev(30 + i, "failed") for i in range(5)]
        recent = [_ev(i, "streamed") for i in range(1, 11)]
        r = cloud_api.esr_summary(old_failures + recent)
        self.assertEqual((r["succeeded"], r["counted"], r["rate"]), (10, 10, 1.0))

    def test_no_judged_events_has_no_rate(self):
        r = cloud_api.esr_summary([_ev(-2, "upcoming")])
        self.assertEqual(r["counted"], 0)
        self.assertIsNone(r["rate"])


class EsrFromListed(unittest.TestCase):
    def test_never_aired_past_window_is_a_failure(self):
        items = [_listed(1, "complete"), _listed(2, "scheduled"), _listed(-3, "scheduled")]
        r = cloud_api._esr_from_listed(items, NO_EQS, NOW)
        self.assertEqual((r["succeeded"], r["counted"]), (1, 2))

    def test_testing_and_deleted_events_are_skipped(self):
        items = [_listed(1, "complete"), _listed(2, "scheduled", is_testing=True),
                 _listed(3, "scheduled", is_deleted=True)]
        r = cloud_api._esr_from_listed(items, NO_EQS, NOW)
        self.assertEqual((r["succeeded"], r["counted"]), (1, 1))


if __name__ == "__main__":
    unittest.main()
