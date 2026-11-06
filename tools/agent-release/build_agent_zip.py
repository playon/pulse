"""Build the fleet agent's release zip (PV-49).

    python tools/agent-release/build_agent_zip.py <version> <out-dir>

Writes <out-dir>/pulse-agent-<version>.zip and a .sha256 file beside it. The
zip is what the agent's runner unpacks into a slot on the VPU: the Pulse.Web
tree the monitor runs (app, scripts, deploy, VERSION), without the embedded
Python runtime, which stays on the unit, shared by both slots. The engine in
app/main.py ships inside it, frozen at this tag.

The zip is reproducible: entries are sorted, every timestamp and mode is
fixed, and nothing is compressed (deflate output differs between zlib
builds; compressing saves only 8.2 MB -> 6.7 MB). So anyone can rebuild it
from the tag, on any machine, and get the SHA-256 that fleet control pins.

Refuses to build unless <version> matches Pulse.Web/app/pulse_agent/VERSION,
so a tag can't publish a zip that reports another version.
"""

import os
import re
import sys

_WEB_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "Pulse.Web")
sys.path.insert(0, os.path.join(_WEB_ROOT, "app"))
# The zip format itself lives with the agent, so enrolling a unit can hash
# its tree exactly as this builds it (pulse_agent/release_zip.py).
from pulse_agent.release_zip import FIXED_TIME, INCLUDE, SKIP_DIRS, SKIP_PATHS, collect, write_zip  # noqa: E402,F401

VERSION_RE = re.compile(r"^\d{1,4}\.\d{1,4}\.\d{1,6}$")


def agent_version(web_root: str) -> str:
    with open(os.path.join(web_root, "app", "pulse_agent", "VERSION"), "r", encoding="utf-8") as fh:
        return fh.read().strip()


def build(web_root: str, version: str, out_dir: str) -> tuple:
    """Write the zip and its .sha256; return (zip path, sha256 hex)."""
    if not VERSION_RE.match(version):
        raise ValueError(f"{version!r} isn't N.N.N")
    found = agent_version(web_root)
    if found != version:
        raise ValueError(f"the tag says {version} but Pulse.Web/app/pulse_agent/VERSION says {found}")
    files = collect(web_root)
    for required in ("app/monitor_once.py", "app/pulse_agent/VERSION", "app/main.py", "app/requirements.txt"):
        if required not in files:
            raise ValueError(f"{required} is missing from the build")
    os.makedirs(out_dir, exist_ok=True)
    zip_path = os.path.join(out_dir, f"pulse-agent-{version}.zip")
    sha = write_zip(web_root, files, zip_path)
    with open(zip_path + ".sha256", "w", encoding="utf-8") as fh:
        fh.write(f"{sha}  {os.path.basename(zip_path)}\n")
    with open(os.path.join(out_dir, "RELEASE_NOTES.md"), "w", encoding="utf-8") as fh:
        fh.write(release_notes(web_root, version, sha))
    return zip_path, sha


def changelog_section(web_root: str, version: str) -> str:
    """The `## [version]` section of the agent changelog, without its heading."""
    with open(os.path.join(web_root, "app", "pulse_agent", "CHANGELOG.md"), "r", encoding="utf-8") as fh:
        text = fh.read()
    m = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)", text, re.S | re.M)
    return m.group(1).strip() if m else ""


def release_notes(web_root: str, version: str, sha: str) -> str:
    notes = changelog_section(web_root, version) or "_No changelog section for this version._"
    return f"""Fleet agent {version} (PV-49). Units move to it only when fleet control pins it.

{notes}

**SHA-256** of `pulse-agent-{version}.zip`:

```
{sha}
```

Pin it from Pulse Vitals, which sets it through the admin Worker's
`POST /agent-target` after checking this release's hash (PV-85). By hand, as a
last resort (check-in Worker README, "which agent build a unit runs"):

```sql
-- one unit first
INSERT INTO agent_target (scope, version, sha256, note, set_at)
VALUES ('<venue id>', '{version}', '{sha}', 'canary', datetime('now'))
ON CONFLICT (scope) DO UPDATE SET version = excluded.version, sha256 = excluded.sha256,
  note = excluded.note, set_by = NULL, set_at = excluded.set_at;
-- then the fleet
INSERT INTO agent_target (scope, version, sha256, note, set_at)
VALUES ('fleet', '{version}', '{sha}', 'by hand', datetime('now'))
ON CONFLICT (scope) DO UPDATE SET version = excluded.version, sha256 = excluded.sha256,
  note = excluded.note, set_by = NULL, set_at = excluded.set_at;
```
"""


def main(argv) -> int:
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[2].strip(), file=sys.stderr)
        return 2
    version, out_dir = argv
    web_root = _WEB_ROOT
    try:
        zip_path, sha = build(web_root, version, out_dir)
    except (ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"{zip_path}\n{sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
