"""One word and one colour per machine state, from collector to badge.

The display layer hard-codes a status vocabulary the collectors were never
told about, and nothing checked that the two agree. The cost, verified end to
end on dev@f594640:

    Get-DiskHealth.ps1:94   level = Critical | Error | Warning
    app.js:5719             <td>${statusBadge(e.level)}</td>
    statusBadge (app.js:314) has cases for critical, warning -- and none for
                            "error", so it falls through to badge(cap,
                            "muted") = grey.

So a disk ERROR event renders grey, calmer than the amber WARNING beside it:
severity inverted in the middle tier, on a table a tech reads to decide
whether a drive is dying. severityChip, forty lines away in the same file,
does map "error" to red -- two helpers in one file disagreeing about one word.

Worse, severityChip's fallback arm is `sev-chip-ok`: an unrecognised severity
renders GREEN. A collector that starts emitting a new word does not degrade to
neutral, it degrades to healthy.

Neither was reachable in demo mode -- demo_data emits no disk events at all --
so no amount of clicking around would have found either.

These tests are the agreement check. They parse the real helpers out of app.js
and the real literals out of the collectors, so they fail when the two drift
rather than when someone forgets to update a doc.

Stdlib unittest, no pytest -- same as the rest of this suite:

    cd Pulse.Web && python3 -m unittest discover -s tests
"""

import os
import re
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_WEB = os.path.dirname(_HERE)
_APP_JS = os.path.join(_WEB, "app", "static", "app.js")
_SCRIPTS = os.path.join(_WEB, "scripts")


# ── The canonical vocabulary ─────────────────────────────────
# One row per distinct CONDITION. Synonyms collapse onto one display word so
# a tech never sees the same machine state called two things on two tabs.
#
# "badge" is the severity statusBadge must render it at. A word listed here
# and absent from statusBadge is a silent grey pill.
CANONICAL = {
    # healthy
    "running": "pass",
    "up": "pass",
    "pass": "pass",
    "ok": "pass",
    "healthy": "pass",
    # broken
    "stopped": "fail",
    "down": "fail",
    "fail": "fail",
    "critical": "fail",
    "error": "fail",      # <- the missing one
    # degraded
    "warning": "warn",
    "warn": "warn",
    "degraded": "warn",
    # genuinely neutral
    "notfound": "muted",
    "unknown": "muted",
}

# Severity words shared by statusBadge and severityChip. Both must agree:
# a word cannot be red in one helper and grey in the other.
SHARED = {
    "critical": "fail",
    "error": "fail",
    "warning": "warn",
    "unknown": "muted",
}

# Exactly which collector field feeds each statusBadge() call. Derived by
# reading the five call sites, NOT by guessing from field names:
#
#   app.js:1990  statusBadge(s.status)                dashboard service rows
#   app.js:4098  statusBadge(d.status)                Network domain rows
#   app.js:5349  statusBadge(s.status)                Service Status tiles
#   app.js:5703  statusBadge(d.healthStatus)          Disks table
#   app.js:5719  statusBadge(e.level)                 Disk event log
#
# Scanning every `status =` in every collector instead produces a wall of
# false positives: Test-TlsInspection emits blocked/filtered/intercepted,
# Get-PixellotDependencies emits outdated/current, Remove-CanopyLeaf emits
# removed/partial. Those are real vocabularies with their OWN renderers and
# never touch a badge. Narrow beats noisy -- a check nobody trusts is a
# check nobody reads.
BADGE_FED = {
    "Get-Services.ps1": ("status",),
    "Test-NetworkDomains.ps1": ("status",),
    "Get-DiskHealth.ps1": ("healthStatus", "level"),
}

# Values those fields may carry that are not severities.
NOT_BADGED = {
    "automatic", "manual", "disabled", "auto",   # service start types
    "true", "false", "null",
}

EXPECTED_BADGE_CALL_SITES = 5


def _read(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _fn_body(js, name):
    """Brace-matched body of a top-level `function name(...) {...}`."""
    m = re.search(r"function %s\s*\([^)]*\)\s*\{" % re.escape(name), js)
    if not m:
        return None
    i, depth = m.end(), 1
    while i < len(js) and depth:
        if js[i] == "{":
            depth += 1
        elif js[i] == "}":
            depth -= 1
        i += 1
    return js[m.end():i - 1]


def _status_badge_map(js):
    """{word: severity} that statusBadge has an EXPLICIT case for.

    statusBadge is a chain of `if (s === "a" || s === "b") return badge(cap,
    "sev");`, so each return's severity applies to the words tested in the
    condition that precedes it.
    """
    body = _fn_body(js, "statusBadge")
    if body is None:
        raise AssertionError("statusBadge not found in app.js -- has it been renamed?")
    out = {}
    for cond, sev in re.findall(
        r"if\s*\((.*?)\)\s*\n?\s*return badge\([^,]+,\s*\"(\w+)\"\)", body, re.S
    ):
        for word in re.findall(r's === "([\w-]+)"', cond):
            out[word] = sev
    return out


def _severity_chip_map(js):
    """({word: class}, fallback_class) for severityChip's ternary chain."""
    body = _fn_body(js, "severityChip")
    if body is None:
        raise AssertionError("severityChip not found in app.js -- has it been renamed?")
    out = {}
    # Each arm is: <conditions> ? "sev-chip-x" :
    for cond, cls in re.findall(r"([^?:]*?)\?\s*\"(sev-chip-[\w-]+)\"", body, re.S):
        for word in re.findall(r's === "([\w-]+)"', cond):
            out[word] = cls
    classes = re.findall(r"\"(sev-chip-[\w-]+)\"", body)
    return out, (classes[-1] if classes else None)


_CHIP_TO_SEVERITY = {
    "sev-chip-crit": "fail",
    "sev-chip-warn": "warn",
    "sev-chip-muted": "muted",
    "sev-chip-ok": "pass",
}


class TestStatusBadgeCoverage(unittest.TestCase):
    """Every canonical word must render at its real severity."""

    def setUp(self):
        self.js = _read(_APP_JS)
        self.badge = _status_badge_map(self.js)

    def test_every_canonical_word_has_an_explicit_case(self):
        # A word the fallback already renders at the right severity is fine
        # implicitly -- "unknown" wants muted and muted IS the fallback.
        missing = sorted(
            w for w, want in CANONICAL.items()
            if w not in self.badge and want != "muted"
        )
        self.assertEqual(
            missing, [],
            "statusBadge has no case for %s, so it renders grey/muted. A state "
            "that is broken must not read calmer than one that is merely "
            "degraded. Add it to the matching branch in app.js." % missing,
        )

    def test_no_word_renders_at_the_wrong_severity(self):
        wrong = {
            w: (self.badge[w], want)
            for w, want in CANONICAL.items()
            if w in self.badge and self.badge[w] != want
        }
        self.assertEqual(
            wrong, {},
            "statusBadge renders these at the wrong severity "
            "{word: (actual, expected)}: %s" % wrong,
        )

    def test_unknown_input_is_neutral_not_healthy(self):
        """The fallback must never be the healthy colour."""
        body = _fn_body(self.js, "statusBadge")
        tail = body.strip().splitlines()[-1]
        self.assertIn(
            '"muted"', tail,
            "statusBadge's fallback must be muted. An unrecognised status is "
            "an unknown one, and unknown is not healthy. Got: %s" % tail.strip(),
        )


class TestHelpersAgree(unittest.TestCase):
    """Two helpers in one file must not disagree about one word."""

    def setUp(self):
        self.js = _read(_APP_JS)
        self.badge = _status_badge_map(self.js)
        self.chip, self.chip_fallback = _severity_chip_map(self.js)

    def test_shared_words_map_to_the_same_severity(self):
        disagree = {}
        for word, want in SHARED.items():
            b = self.badge.get(word)
            c = _CHIP_TO_SEVERITY.get(self.chip.get(word))
            if b and c and b != c:
                disagree[word] = {"statusBadge": b, "severityChip": c}
        self.assertEqual(
            disagree, {},
            "statusBadge and severityChip render the same word at different "
            "severities: %s. One state, one colour." % disagree,
        )

    def test_severity_chip_fallback_is_not_healthy(self):
        self.assertNotEqual(
            self.chip_fallback, "sev-chip-ok",
            "severityChip's fallback arm is sev-chip-ok, so an unrecognised "
            "severity renders GREEN. A word nobody taught it must degrade to "
            "neutral, never to healthy.",
        )


class TestCollectorsEmitKnownWords(unittest.TestCase):
    """A badge-fed collector must not invent a word the UI has never heard of."""

    def test_badge_fed_fields_emit_only_canonical_words(self):
        unknown = {}
        for script, fields in sorted(BADGE_FED.items()):
            found = self._literals(script, fields)
            # A scan that matches NOTHING is worse than a scan that fails: it
            # passes silently forever. The first version of this test used
            # `field = 'value'` and so never saw Get-DiskHealth's
            # `level = switch (...) { 1 { 'Critical' } ... }` -- the exact
            # script this whole check exists for. It reported OK while
            # measuring nothing.
            self.assertTrue(
                found,
                "no status literals found in %s for %s -- the extraction has "
                "stopped matching, so this check is passing vacuously. Fix the "
                "parser, do not relax the assertion." % (script, list(fields)),
            )
            for word in found:
                if word in CANONICAL or word in NOT_BADGED:
                    continue
                unknown.setdefault(word, []).append(script)
        self.assertEqual(
            unknown, {},
            "These badge-fed collector fields emit words statusBadge has no "
            "case for {word: scripts}: %s. An unmapped word renders as a grey "
            "pill whatever it means. Add it to CANONICAL and to statusBadge, "
            "or emit an existing word." % unknown,
        )

    def _literals(self, script, fields):
        """Lowercased quoted literals assigned to `fields` in a collector.

        Takes the whole assignment expression, not just a bare `= 'x'`,
        because PowerShell writes these as one-line switch blocks:
            level = switch ($_.Level) { 1 { 'Critical' } 2 { 'Error' } ... }
        """
        path = os.path.join(_SCRIPTS, script)
        if not os.path.isfile(path):
            self.fail("%s is gone -- update BADGE_FED and the call sites it "
                      "was derived from" % script)
        text = _read(path)
        out = set()
        for field in fields:
            for m in re.finditer(r"\b%s\s*=\s*(.*)$" % re.escape(field),
                                 text, re.I | re.M):
                for raw in re.findall(r"'([^']{1,24})'", m.group(1)):
                    word = raw.strip().lower()
                    if word and re.fullmatch(r"[\w-]+", word):
                        out.add(word)
        return out

    def test_no_unregistered_status_badge_call_site(self):
        """A new call site means a new producer field to register."""
        js = _read(_APP_JS)
        calls = len(re.findall(r"\$\{statusBadge\(", js))
        self.assertEqual(
            calls, EXPECTED_BADGE_CALL_SITES,
            "statusBadge is now called %d times, not %d. BADGE_FED is derived "
            "by reading each call site, so a new one has to be registered "
            "there (or an old one removed) -- otherwise its collector can "
            "emit an unmapped word and nothing will notice."
            % (calls, EXPECTED_BADGE_CALL_SITES),
        )


if __name__ == "__main__":
    unittest.main()
