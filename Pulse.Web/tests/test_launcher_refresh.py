"""Unit tests for the installed-launcher refresh (_refresh_installed_launcher).

C:\\Pulse\\Pulse.bat is a frozen self-copy that the install never updates, so a
box that already has Pulse keeps its original outer launcher forever. The
refresh replaces it from the release zip's bundled copy. What these cover is
mostly what it must NOT do: never touch a dev/beta install (the bundled copy
is the PRODUCTION launcher, so writing it would move the box's channel),
never install a truncated launcher, never leave a .new temp file behind, and
above all never write while the launcher may still be running — cmd reads a
.bat by byte offset, so that garbles the launch in progress (it did, on the
bench, before run.bat started recording pulse-launch-done).

Standard library only, like the other suites here:

    cd Pulse.Web && .venv/bin/python -m unittest discover -s tests
"""

import asyncio
import hashlib
import os
import sys
import tempfile
import time
import unittest

_APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import main  # noqa: E402


OLD_LAUNCHER = b"@echo off\nrem old launcher\n" + b"x" * 2000
NEW_LAUNCHER = b"@echo off\nrem new launcher with :spin\n" + b"y" * 4000


class TestLauncherRefresh(unittest.TestCase):
    """Each test builds a throwaway C:\\Pulse-shaped tree and points main at it."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        os.makedirs(os.path.join(self.root, "launcher"))
        self.pulse_bat = os.path.join(self.root, "Pulse.bat")
        self.bundled = os.path.join(self.root, "launcher", "run_pulse.bat")

        self._saved = (main.DEMO_MODE, main._web_root, main._BUNDLED_PROD_LAUNCHER,
                       main._LAUNCH_DONE_MARKER, main._LAUNCHER_REFRESH_POLL_SECS,
                       main._LAUNCHER_REFRESH_MAX_WAIT_SECS,
                       main._LAUNCHER_REFRESH_SETTLE_SECS)
        main.DEMO_MODE = False
        main._web_root = self.root
        main._BUNDLED_PROD_LAUNCHER = self.bundled
        self.marker = os.path.join(self.root, "pulse-launch-done")
        main._LAUNCH_DONE_MARKER = self.marker
        # Don't make the suite wait on real launcher timing.
        main._LAUNCHER_REFRESH_POLL_SECS = 0.01
        main._LAUNCHER_REFRESH_MAX_WAIT_SECS = 0.05
        main._LAUNCHER_REFRESH_SETTLE_SECS = 0

        self.write(self.pulse_bat, OLD_LAUNCHER)
        self.write(self.bundled, NEW_LAUNCHER)
        self.write(os.path.join(self.root, "VERSION"), b"web-v1.2.3\n")
        self.write(os.path.join(self.root, "CHANNEL"), b"production\n")
        # The default fixture is a launch that finished: run.bat wrote the
        # marker, so the launcher is gone and Pulse.bat is safe to replace.
        self.started_at = time.time() - 5
        self.write(self.marker, b"17/09/2026 23:30:00.00\n")

    def tearDown(self):
        (main.DEMO_MODE, main._web_root, main._BUNDLED_PROD_LAUNCHER,
         main._LAUNCH_DONE_MARKER, main._LAUNCHER_REFRESH_POLL_SECS,
         main._LAUNCHER_REFRESH_MAX_WAIT_SECS,
         main._LAUNCHER_REFRESH_SETTLE_SECS) = self._saved
        self._tmp.cleanup()

    @staticmethod
    def write(path, data):
        with open(path, "wb") as f:
            f.write(data)

    @staticmethod
    def read(path):
        with open(path, "rb") as f:
            return f.read()

    def run_refresh(self):
        asyncio.run(main._refresh_installed_launcher(self.started_at))

    # ── the happy path ───────────────────────────────────────
    def test_replaces_a_stale_launcher(self):
        self.run_refresh()
        self.assertEqual(self.read(self.pulse_bat), NEW_LAUNCHER)

    def test_leaves_no_temp_file_behind(self):
        self.run_refresh()
        self.assertFalse(os.path.exists(self.pulse_bat + ".new"))

    def test_identical_launcher_is_left_alone(self):
        self.write(self.pulse_bat, NEW_LAUNCHER)
        before = os.stat(self.pulse_bat).st_mtime_ns
        self.run_refresh()
        self.assertEqual(os.stat(self.pulse_bat).st_mtime_ns, before)

    # ── the guards ───────────────────────────────────────────
    def test_dev_channel_install_is_never_touched(self):
        """The bundled copy is the PRODUCTION launcher: writing it over a dev
        install's Pulse.bat would silently move that box to production."""
        self.write(os.path.join(self.root, "CHANNEL"), b"dev\n")
        self.run_refresh()
        self.assertEqual(self.read(self.pulse_bat), OLD_LAUNCHER)

    def test_beta_channel_install_is_never_touched(self):
        self.write(os.path.join(self.root, "CHANNEL"), b"beta\n")
        self.run_refresh()
        self.assertEqual(self.read(self.pulse_bat), OLD_LAUNCHER)

    def test_channel_falls_back_to_the_installed_tag(self):
        """No CHANNEL file: a web-dev-v* tag still reads as the dev channel."""
        os.remove(os.path.join(self.root, "CHANNEL"))
        self.write(os.path.join(self.root, "VERSION"), b"web-dev-v1.3.0-dev-abc1234\n")
        self.run_refresh()
        self.assertEqual(self.read(self.pulse_bat), OLD_LAUNCHER)

    def test_from_source_checkout_is_not_a_managed_install(self):
        """No VERSION stamp - a git checkout must never be written to."""
        os.remove(os.path.join(self.root, "VERSION"))
        self.run_refresh()
        self.assertEqual(self.read(self.pulse_bat), OLD_LAUNCHER)

    def test_truncated_bundled_launcher_is_rejected(self):
        self.write(self.bundled, b"@echo off\n")
        self.run_refresh()
        self.assertEqual(self.read(self.pulse_bat), OLD_LAUNCHER)

    def test_missing_bundled_launcher_is_a_no_op(self):
        os.remove(self.bundled)
        self.run_refresh()
        self.assertEqual(self.read(self.pulse_bat), OLD_LAUNCHER)

    def test_demo_mode_is_a_no_op(self):
        main.DEMO_MODE = True
        self.run_refresh()
        self.assertEqual(self.read(self.pulse_bat), OLD_LAUNCHER)

    # ── the launch-in-progress gate ──────────────────────────
    def test_no_marker_means_no_write(self):
        """No pulse-launch-done at all: the launcher may still be running, and
        rewriting a .bat cmd is reading resumes it at a garbage byte offset."""
        os.remove(self.marker)
        self.run_refresh()
        self.assertEqual(self.read(self.pulse_bat), OLD_LAUNCHER)

    def test_marker_from_a_previous_launch_is_ignored(self):
        """A marker older than this server's start says nothing about the cmd
        running right now."""
        self.started_at = time.time() + 60  # every existing marker is now stale
        self.run_refresh()
        self.assertEqual(self.read(self.pulse_bat), OLD_LAUNCHER)

    def test_marker_written_late_still_counts(self):
        """The common case: run.bat finishes after the server is already up."""
        os.remove(self.marker)
        self.started_at = time.time()

        async def drive():
            task = asyncio.ensure_future(
                main._refresh_installed_launcher(self.started_at))
            await asyncio.sleep(0)
            self.write(self.marker, b"later\n")
            await task

        main._LAUNCHER_REFRESH_MAX_WAIT_SECS = 5
        asyncio.run(drive())
        self.assertEqual(self.read(self.pulse_bat), NEW_LAUNCHER)

    # ── failure containment ──────────────────────────────────
    def test_a_locked_target_fails_open(self):
        """os.replace raising (Windows: cmd still holds the running .bat open)
        must not raise out of the task, and must not leave a temp file."""
        real_replace = os.replace

        def boom(src, dst):
            raise PermissionError("target in use")

        os.replace = boom
        try:
            self.run_refresh()
        finally:
            os.replace = real_replace
        self.assertEqual(self.read(self.pulse_bat), OLD_LAUNCHER)
        self.assertFalse(os.path.exists(self.pulse_bat + ".new"))


class TestLauncherCopyRefresh(unittest.TestCase):
    """Old copies of the production launcher left on a desktop or in Downloads
    (_refresh_launcher_copies). The rule under test: replace a file only when
    it is byte-identical to a launcher we published, and only after the launch
    in progress has finished. Anything else - a newer launcher, a dev launcher,
    an edited copy - stays exactly as it is."""

    OLD = b"@echo off\nrem an old production launcher\n" + b"o" * 3000
    NEWER = b"@echo off\nrem a launcher from a later release\n" + b"n" * 5000

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = self._tmp.name
        self.root = os.path.join(base, "Pulse")
        self.users = os.path.join(base, "Users")
        os.makedirs(os.path.join(self.root, "launcher"))
        for d in ("tech\\Desktop", "tech\\Downloads", "Public\\Desktop", "Default\\Desktop"):
            os.makedirs(os.path.join(self.users, *d.split("\\")))
        self.desktop = os.path.join(self.users, "tech", "Desktop")
        self.bundled = os.path.join(self.root, "launcher", "run_pulse.bat")
        self.marker = os.path.join(self.root, "pulse-launch-done")

        self._saved = (main.DEMO_MODE, main._web_root, main._BUNDLED_PROD_LAUNCHER,
                       main._LAUNCH_DONE_MARKER, main._LAUNCHER_REFRESH_POLL_SECS,
                       main._LAUNCHER_REFRESH_MAX_WAIT_SECS,
                       main._LAUNCHER_REFRESH_SETTLE_SECS,
                       main._LAUNCHER_COPY_USERS_ROOT, main._SUPERSEDED_PROD_LAUNCHERS)
        main.DEMO_MODE = False
        main._web_root = self.root
        main._BUNDLED_PROD_LAUNCHER = self.bundled
        main._LAUNCH_DONE_MARKER = self.marker
        main._LAUNCHER_REFRESH_POLL_SECS = 0.01
        main._LAUNCHER_REFRESH_MAX_WAIT_SECS = 0.05
        main._LAUNCHER_REFRESH_SETTLE_SECS = 0
        main._LAUNCHER_COPY_USERS_ROOT = self.users
        main._SUPERSEDED_PROD_LAUNCHERS = frozenset({hashlib.sha256(self.OLD).hexdigest()})

        w = TestLauncherRefresh.write
        w(os.path.join(self.root, "Pulse.bat"), NEW_LAUNCHER)
        w(self.bundled, NEW_LAUNCHER)
        w(os.path.join(self.root, "VERSION"), b"web-v1.4.0\n")
        w(os.path.join(self.root, "CHANNEL"), b"production\n")
        self.started_at = time.time() - 5
        w(self.marker, b"done\n")

    def tearDown(self):
        (main.DEMO_MODE, main._web_root, main._BUNDLED_PROD_LAUNCHER,
         main._LAUNCH_DONE_MARKER, main._LAUNCHER_REFRESH_POLL_SECS,
         main._LAUNCHER_REFRESH_MAX_WAIT_SECS,
         main._LAUNCHER_REFRESH_SETTLE_SECS,
         main._LAUNCHER_COPY_USERS_ROOT, main._SUPERSEDED_PROD_LAUNCHERS) = self._saved
        self._tmp.cleanup()

    def put(self, *parts, data=None):
        path = os.path.join(self.users, *parts)
        TestLauncherRefresh.write(path, self.OLD if data is None else data)
        return path

    read = staticmethod(TestLauncherRefresh.read)

    def run_refresh(self):
        asyncio.run(main._refresh_launcher_copies(self.started_at))

    # ── what it replaces ─────────────────────────────────────
    def test_replaces_an_old_launcher_on_the_desktop(self):
        p = self.put("tech", "Desktop", "run_pulse.bat")
        self.run_refresh()
        self.assertEqual(self.read(p), NEW_LAUNCHER)
        self.assertFalse(os.path.exists(p + ".pulse-new"))

    def test_a_renamed_copy_is_recognised_by_its_bytes(self):
        """Browsers save a second download as 'run_pulse (1).bat'."""
        p = self.put("tech", "Downloads", "run_pulse (1).bat")
        self.run_refresh()
        self.assertEqual(self.read(p), NEW_LAUNCHER)

    def test_public_desktop_is_covered(self):
        p = self.put("Public", "Desktop", "Pulse.bat")
        self.run_refresh()
        self.assertEqual(self.read(p), NEW_LAUNCHER)

    def test_a_copy_with_rewritten_line_endings_still_counts(self):
        p = self.put("tech", "Desktop", "run_pulse.bat", data=self.OLD.replace(b"\n", b"\r\n"))
        self.run_refresh()
        self.assertEqual(self.read(p), NEW_LAUNCHER)

    # ── what it must never touch ─────────────────────────────
    def test_a_newer_or_unknown_launcher_is_left_alone(self):
        """A tech can bring a NEWER launcher to a box whose update failed; an
        older release must never downgrade it."""
        p = self.put("tech", "Desktop", "run_pulse.bat", data=self.NEWER)
        self.run_refresh()
        self.assertEqual(self.read(p), self.NEWER)

    def test_an_edited_copy_is_left_alone(self):
        p = self.put("tech", "Desktop", "run_pulse.bat", data=self.OLD + b"rem my tweak\n")
        self.run_refresh()
        self.assertEqual(self.read(p), self.OLD + b"rem my tweak\n")

    def test_only_bat_files_are_considered(self):
        p = self.put("tech", "Desktop", "run_pulse.txt")
        self.run_refresh()
        self.assertEqual(self.read(p), self.OLD)

    def test_template_profiles_are_skipped(self):
        p = self.put("Default", "Desktop", "run_pulse.bat")
        self.run_refresh()
        self.assertEqual(self.read(p), self.OLD)

    def test_subfolders_are_not_searched(self):
        os.makedirs(os.path.join(self.desktop, "tools"))
        p = self.put("tech", "Desktop", "tools", "run_pulse.bat")
        self.run_refresh()
        self.assertEqual(self.read(p), self.OLD)

    def test_dev_channel_install_is_never_touched(self):
        TestLauncherRefresh.write(os.path.join(self.root, "CHANNEL"), b"dev\n")
        p = self.put("tech", "Desktop", "run_pulse.bat")
        self.run_refresh()
        self.assertEqual(self.read(p), self.OLD)

    def test_demo_mode_is_a_no_op(self):
        main.DEMO_MODE = True
        p = self.put("tech", "Desktop", "run_pulse.bat")
        self.run_refresh()
        self.assertEqual(self.read(p), self.OLD)

    def test_truncated_bundled_launcher_is_rejected(self):
        TestLauncherRefresh.write(self.bundled, b"@echo off\n")
        p = self.put("tech", "Desktop", "run_pulse.bat")
        self.run_refresh()
        self.assertEqual(self.read(p), self.OLD)

    # ── the launch-in-progress gate ──────────────────────────
    def test_no_marker_means_no_write(self):
        """The desktop copy may be the launcher that is still running."""
        os.remove(self.marker)
        p = self.put("tech", "Desktop", "run_pulse.bat")
        self.run_refresh()
        self.assertEqual(self.read(p), self.OLD)

    def test_a_file_changed_during_the_wait_is_re_judged(self):
        """The tech drops a newer launcher over the old one while we wait."""
        os.remove(self.marker)
        self.started_at = time.time()
        p = self.put("tech", "Desktop", "run_pulse.bat")

        async def drive():
            task = asyncio.ensure_future(main._refresh_launcher_copies(self.started_at))
            await asyncio.sleep(0)
            TestLauncherRefresh.write(p, self.NEWER)
            TestLauncherRefresh.write(self.marker, b"later\n")
            await task

        main._LAUNCHER_REFRESH_MAX_WAIT_SECS = 5
        asyncio.run(drive())
        self.assertEqual(self.read(p), self.NEWER)

    # ── failure containment ──────────────────────────────────
    def test_one_unwritable_copy_does_not_stop_the_others(self):
        a = self.put("tech", "Desktop", "run_pulse.bat")
        b = self.put("Public", "Desktop", "run_pulse.bat")
        real_replace = os.replace

        def picky(src, dst):
            if dst == b:
                raise PermissionError("in use")
            return real_replace(src, dst)

        os.replace = picky
        try:
            self.run_refresh()
        finally:
            os.replace = real_replace
        self.assertEqual(self.read(a), NEW_LAUNCHER)
        self.assertEqual(self.read(b), self.OLD)
        self.assertFalse(os.path.exists(b + ".pulse-new"))


class TestSupersededLauncherList(unittest.TestCase):
    """The real hash list, against the launcher this release ships."""

    def test_entries_are_sha256_hex(self):
        for h in main._SUPERSEDED_PROD_LAUNCHERS:
            self.assertRegex(h, r"^[0-9a-f]{64}$")

    def test_the_current_launcher_is_not_listed_as_superseded(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(here, "launcher", "run_pulse.bat"), "rb") as f:
            self.assertFalse(main._is_superseded_launcher(f.read()))


if __name__ == "__main__":
    unittest.main()
