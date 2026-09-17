"""Unit tests for the installed-launcher refresh (_refresh_installed_launcher).

C:\\Pulse\\Pulse.bat is a frozen self-copy that the install never updates, so a
box that already has Pulse keeps its original outer launcher forever. The
refresh replaces it from the release zip's bundled copy. What these cover is
mostly what it must NOT do: never touch a dev/beta install (the bundled copy
is the PRODUCTION launcher, so writing it would move the box's channel),
never install a truncated launcher, and never leave a .new temp file behind.

Standard library only, like the other suites here:

    cd Pulse.Web && .venv/bin/python -m unittest discover -s tests
"""

import asyncio
import os
import sys
import tempfile
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
                       main._LAUNCHER_REFRESH_DELAY_SECS)
        main.DEMO_MODE = False
        main._web_root = self.root
        main._BUNDLED_PROD_LAUNCHER = self.bundled
        main._LAUNCHER_REFRESH_DELAY_SECS = 0  # don't make the suite wait

        self.write(self.pulse_bat, OLD_LAUNCHER)
        self.write(self.bundled, NEW_LAUNCHER)
        self.write(os.path.join(self.root, "VERSION"), b"web-v1.2.3\n")
        self.write(os.path.join(self.root, "CHANNEL"), b"production\n")

    def tearDown(self):
        (main.DEMO_MODE, main._web_root, main._BUNDLED_PROD_LAUNCHER,
         main._LAUNCHER_REFRESH_DELAY_SECS) = self._saved
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
        asyncio.run(main._refresh_installed_launcher())

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


if __name__ == "__main__":
    unittest.main()
