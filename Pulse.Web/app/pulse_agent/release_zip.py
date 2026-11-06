"""The fleet agent's release zip, byte for byte (PV-49, PV-85).

tools/agent-release/build_agent_zip.py builds the published
pulse-agent-<version>.zip with write_zip(). Enrolling a unit (fleet_enroll.py)
hashes the tree it installs the same way, so a unit enrolled from exactly a
released build records that release's SHA-256 and doesn't download it again
when fleet control pins it. A tree that differs in any file (a dev build)
hashes differently and is replaced by the pinned bytes, as before.

The zip is reproducible: entries are sorted, every timestamp and mode is
fixed, and nothing is compressed (deflate output differs between zlib builds).
Stdlib only.
"""

import hashlib
import os
import tempfile
import zipfile

# The parts of Pulse.Web the monitor runs. Everything else (tests, docs, the
# launchers, the changelog) stays out.
INCLUDE = ("app", "scripts", "deploy", "VERSION")
# The embedded runtime lives on the unit, outside the slots.
SKIP_DIRS = {"__pycache__", ".pytest_cache"}
SKIP_PATHS = {"app/python"}
# 1980-01-01, the earliest time a zip can hold.
FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def collect(web_root: str) -> list:
    """The files to ship, as sorted paths relative to web_root with / separators."""
    files = []
    for top in INCLUDE:
        path = os.path.join(web_root, top)
        if os.path.isfile(path):
            files.append(top)
            continue
        for dirpath, dirnames, names in os.walk(path):
            rel_dir = os.path.relpath(dirpath, web_root).replace(os.sep, "/")
            dirnames[:] = sorted(d for d in dirnames
                                 if d not in SKIP_DIRS and f"{rel_dir}/{d}" not in SKIP_PATHS)
            for name in names:
                if name.endswith((".pyc", ".pyo")) or name.startswith("."):
                    continue
                files.append(f"{rel_dir}/{name}")
    return sorted(files)


def write_zip(web_root: str, files: list, zip_path: str) -> str:
    """Write the zip of `files` (from collect) and return its SHA-256."""
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as zf:
        for rel in files:
            info = zipfile.ZipInfo(rel, date_time=FIXED_TIME)
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o644 << 16
            info.create_system = 3          # the same on every build machine
            with open(os.path.join(web_root, rel), "rb") as fh:
                zf.writestr(info, fh.read())
    h = hashlib.sha256()
    with open(zip_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_sha256(web_root: str):
    """The SHA-256 the release zip of this tree would have, or None if it
    can't be worked out. The zip is written to a temporary file and removed."""
    fd, path = tempfile.mkstemp(suffix=".zip")
    os.close(fd)
    try:
        return write_zip(web_root, collect(web_root), path)
    except (OSError, ValueError):
        return None
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
