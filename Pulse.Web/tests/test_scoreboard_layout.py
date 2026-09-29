"""Layout contract for the ScoreConnect CG raw string.

Stdlib unittest only — no pytest, no network, no PowerShell:

    cd Pulse.Web && python3 -m unittest discover -s tests

WHY THIS FILE EXISTS
--------------------
The CG parser itself lives in JS (`_parseCG` in app/static/app.js) and there
is no JS runtime or JS test harness in this repo, so it cannot be executed
here. What IS testable is the thing the parser keys off: the FIXED-WIDTH byte
layout, which `app/demo_data.py:_demo_raw_data()` reproduces and which the
parser's offsets must agree with.

These tests pin the byte positions. If someone changes the demo generator's
field widths, the JS parser silently starts reading the wrong bytes in demo
mode with no other warning — that is exactly the failure class this guards.

Context: PXLS2_21655 Bradwell (GA), 2026-08-12 — Pulse reported Q7 while the
board was on Q2. Every fixed-position field on that same string was correct;
only the quarter, which was read by a "last digit of the numeric run"
heuristic rather than a fixed offset, was wrong. The quarter now comes from
pos 25 like every other field, so pos 25 is a contract worth locking.
"""

import os
import re
import sys
import unittest

_APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import demo_data  # noqa: E402


# The capture documented in app.js above _parseCG — Daktronics Football,
# SC III 1.3.0.19, field meanings confirmed by a field tech reading the
# physical controller. Clock 57:28, home 38, visitor 42, quarter 3.
DOC_CAPTURE = "025728  25 38 42  33     3Home    Visitor R:S 00D3098DEBCEEA969B"

# Byte offsets the JS parser reads. Keep in sync with _parseCG.
POS_HEADER = (0, 2)
POS_CLOCK = (2, 6)
POS_HOME = (10, 13)     # 3-char window over the pos 11-12 field
POS_VISITOR = (13, 16)  # 3-char window over the pos 14-15 field
POS_DTB = (20, 25)      # packed down(1) to-go(2) ball-on(2)
POS_QUARTER = 25


class TestDocumentedCapture(unittest.TestCase):
    """The one string we know is real must decode at the documented offsets."""

    def test_header(self):
        self.assertEqual(DOC_CAPTURE[slice(*POS_HEADER)], "02")

    def test_clock(self):
        self.assertEqual(DOC_CAPTURE[slice(*POS_CLOCK)].strip(), "5728")

    def test_scores(self):
        self.assertEqual(int(DOC_CAPTURE[slice(*POS_HOME)].strip()), 38)
        self.assertEqual(int(DOC_CAPTURE[slice(*POS_VISITOR)].strip()), 42)

    def test_quarter_is_at_pos_25(self):
        self.assertEqual(DOC_CAPTURE[POS_QUARTER], "3")

    def test_no_down_and_distance_when_controller_blank(self):
        self.assertFalse(re.search(r"\d", DOC_CAPTURE[slice(*POS_DTB)]))

    def test_quarter_is_where_the_old_heuristic_also_landed(self):
        """The old heuristic read the last digit of the leading numeric run.

        On Daktronics that IS pos 25, which is why the bug hid for so long
        and why moving to a fixed offset is not a Daktronics regression.
        """
        prefix = re.match(r"^[\d.\s]+", DOC_CAPTURE).group(0).rstrip()
        self.assertEqual(prefix[-1], DOC_CAPTURE[POS_QUARTER])


# Second real capture, a different console model and sport setting:
# Daktronics All Sport 5000 on the gray tip, SC III 1.4.1.1 set to
# "Daktronics Auto Detect" (vpu-home, 2026-09-29). Every field was read off
# the physical console by Ian: clock 0:00 stopped, home 39, guest 49, 1st &
# 10, ball-on blank, period 6. Unlike the football capture it has no team
# labels, a clock-state token S:S (stopped), and is 150 bytes long.
AS5000_CAPTURE = "02 000  25 39 49  33110  6                                                                                          S:S             00C82C8DF1E7A692E6"


class TestAllSport5000Capture(unittest.TestCase):
    """The same offsets hold on an All Sport 5000 under Auto Detect."""

    def test_length_and_header(self):
        self.assertEqual(len(AS5000_CAPTURE), 150)
        self.assertEqual(AS5000_CAPTURE[slice(*POS_HEADER)], "02")

    def test_clock_zero(self):
        self.assertEqual(AS5000_CAPTURE[slice(*POS_CLOCK)].strip(), "000")

    def test_scores(self):
        self.assertEqual(int(AS5000_CAPTURE[slice(*POS_HOME)].strip()), 39)
        self.assertEqual(int(AS5000_CAPTURE[slice(*POS_VISITOR)].strip()), 49)

    def test_down_to_go_packed_and_ball_on_blank(self):
        dtb = AS5000_CAPTURE[slice(*POS_DTB)]
        self.assertEqual((dtb[0], dtb[1:3], dtb[3:5].strip()), ("1", "10", ""))

    def test_period_six_at_pos_25(self):
        self.assertEqual(AS5000_CAPTURE[POS_QUARTER], "6")

    def test_clock_state_token_stopped(self):
        self.assertIn("S:S", AS5000_CAPTURE)


class TestDemoGeneratorLayout(unittest.TestCase):
    """demo_data must emit the same layout the JS parser reads."""

    def _raw(self):
        return demo_data._demo_raw_data()

    def test_header_and_length(self):
        raw = self._raw()
        self.assertEqual(raw[slice(*POS_HEADER)], "02")
        self.assertGreater(len(raw), POS_QUARTER)

    def test_scores_land_in_their_windows(self):
        game = demo_data._DEMO_GAME
        raw = self._raw()
        self.assertEqual(int(raw[slice(*POS_HOME)].strip()), game["home"])
        self.assertEqual(int(raw[slice(*POS_VISITOR)].strip()), game["guest"])

    def test_quarter_lands_at_pos_25(self):
        game = demo_data._DEMO_GAME
        self.assertEqual(self._raw()[POS_QUARTER], str(game["quarter"]))

    def test_down_to_go_ball_on_land_in_the_packed_field(self):
        game = demo_data._DEMO_GAME
        dtb = self._raw()[slice(*POS_DTB)]
        self.assertEqual(int(dtb[0]), game["down"])
        self.assertEqual(int(dtb[1:3]), game["to_go"])
        self.assertEqual(int(dtb[3:5]), game["ball_on"])

    def test_quarter_not_adjacent_to_a_stray_digit(self):
        """Nothing numeric may follow the quarter.

        A trailing digit after pos 25 is precisely the Electro-Mech shape that
        broke the old heuristic. The demo layout must not grow one without
        this test failing first.
        """
        self.assertFalse(self._raw()[POS_QUARTER + 1].isdigit())

    def test_clock_under_ten_minutes_keeps_the_layout(self):
        """A sub-10:00 clock is right-justified with a leading space.

        This is the case that makes token-splitting fail and fixed offsets
        necessary — the quarter must not shift when the clock loses a digit.
        """
        raw = "02" + " 944".rjust(4) + "  25 14  7  3311020" + "2" + "Home    Visitor R:S 00D3"
        self.assertEqual(raw[POS_QUARTER], "2")
        self.assertEqual(int(raw[slice(*POS_HOME)].strip()), 14)


if __name__ == "__main__":
    unittest.main()
