"""The agent release zip (build_agent_zip.py): what's in it, and that it's
reproducible, since fleet control pins its SHA-256."""

import hashlib
import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_agent_zip as b  # noqa: E402

WEB_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "Pulse.Web")


def _tree(root, version="1.2.3"):
    files = {
        "app/main.py": "m = 1\n", "app/monitor_once.py": "x = 1\n", "app/requirements.txt": "fastapi\n",
        "app/pulse_agent/__init__.py": "", "app/pulse_agent/VERSION": version + "\n",
        "app/pulse_agent/CHANGELOG.md": f"# Agent\n\n## [Unreleased]\n\n## [{version}] - 2026-10-16\n\n### Added\n- A thing.\n\n## [0.1.0] - 2026-10-15\n\n- Old.\n",
        "app/static/app.js": "1", "app/python/python.exe": "bin", "app/python/Lib/x.py": "1",
        "app/__pycache__/main.cpython-312.pyc": "c", "app/.DS_Store": "junk",
        "scripts/Get-X.ps1": "1", "deploy/Install-PulseMonitor.ps1": "1", "VERSION": "1.5.0-dev\n",
        "tests/test_x.py": "1", "run.bat": "1", "CHANGELOG.md": "1",
    }
    for rel, text in files.items():
        path = os.path.join(root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(text)


class Build(unittest.TestCase):
    def test_ships_what_the_monitor_runs_and_nothing_else(self):
        with tempfile.TemporaryDirectory() as d:
            _tree(d)
            zip_path, _ = b.build(d, "1.2.3", os.path.join(d, "dist"))
            names = zipfile.ZipFile(zip_path).namelist()
        self.assertEqual(names, ["VERSION", "app/main.py", "app/monitor_once.py", "app/pulse_agent/CHANGELOG.md",
                                 "app/pulse_agent/VERSION", "app/pulse_agent/__init__.py",
                                 "app/requirements.txt", "app/static/app.js",
                                 "deploy/Install-PulseMonitor.ps1", "scripts/Get-X.ps1"])

    def test_reproducible(self):
        with tempfile.TemporaryDirectory() as d:
            _tree(d)
            p1, sha1 = b.build(d, "1.2.3", os.path.join(d, "one"))
            os.utime(os.path.join(d, "app", "main.py"), (1, 1))          # mtimes don't matter
            p2, sha2 = b.build(d, "1.2.3", os.path.join(d, "two"))
            self.assertEqual(sha1, sha2)
            with open(p1, "rb") as fh:
                self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), sha1)
            with open(p1 + ".sha256") as fh:
                self.assertEqual(fh.read(), f"{sha1}  pulse-agent-1.2.3.zip\n")

    def test_refuses_a_version_the_package_doesnt_say(self):
        with tempfile.TemporaryDirectory() as d:
            _tree(d, version="1.2.3")
            with self.assertRaisesRegex(ValueError, "VERSION says 1.2.3"):
                b.build(d, "1.2.4", os.path.join(d, "dist"))
            for bad in ("v1.2.3", "1.2", "1.2.3-dev"):
                with self.assertRaisesRegex(ValueError, "isn't N.N.N"):
                    b.build(d, bad, os.path.join(d, "dist"))

    def test_notes_carry_the_changelog_and_the_pin(self):
        with tempfile.TemporaryDirectory() as d:
            _tree(d)
            _, sha = b.build(d, "1.2.3", os.path.join(d, "dist"))
            with open(os.path.join(d, "dist", "RELEASE_NOTES.md")) as fh:
                notes = fh.read()
        self.assertIn("- A thing.", notes)
        self.assertNotIn("Old.", notes)
        self.assertIn(f"'1.2.3', '{sha}'", notes)
        self.assertIn("INSERT INTO agent_target", notes)
        self.assertNotIn("monitor_control", notes)          # pins left it in migration 0020

    def test_the_real_tree_builds(self):
        version = b.agent_version(WEB_ROOT)
        with tempfile.TemporaryDirectory() as d:
            zip_path, _ = b.build(WEB_ROOT, version, d)
            names = set(zipfile.ZipFile(zip_path).namelist())
        self.assertIn("app/pulse_agent/checkin.py", names)
        self.assertIn("scripts/Get-SystemIdentity.ps1", names)
        self.assertFalse(any(n.startswith(("app/python/", "tests/")) for n in names))

    def test_enroll_hashes_a_tree_as_the_release_zip_would(self):
        # fleet_enroll records this for the slot it installs (PV-85).
        from pulse_agent.release_zip import tree_sha256
        with tempfile.TemporaryDirectory() as d:
            _tree(d)
            os.makedirs(os.path.join(d, "app", "__pycache__"), exist_ok=True)
            with open(os.path.join(d, "app", "__pycache__", "x.pyc"), "wb") as fh:
                fh.write(b"cache")                        # what a slot has after running
            _, sha = b.build(d, "1.2.3", os.path.join(d, "dist"))
            self.assertEqual(tree_sha256(d), sha)


if __name__ == "__main__":
    unittest.main()
