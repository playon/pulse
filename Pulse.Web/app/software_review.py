"""Which installed applications are expected on a VPU.

Every installed application lands in one of three classes:

  approved       expected on a VPU. Nothing to say about it.
  risk           known to hurt a VPU (the `_CONCERNING_SOFTWARE` lists in
                 main.py: antivirus, miners, cleaners, torrent, games...).
  informational  everything else: not reviewed yet, or not approved but not
                 harmful. Shown to the tech, never a finding, never blocks.

Risk wins over approved, so a deny-list hit can't be hidden by an allow entry.

Matching is by application NAME only, as a case-insensitive substring of the
installed displayName. Versions drift (Chrome, NVIDIA, VC++), so they are never
compared. The one version rule that exists, the NVIDIA driver floor, is a
separate finding and not part of this list.

The list grows as new installs turn up: add a line, nothing else changes.
First seed: the base-image list from 15125 Marist (GA), 2026-10-19.
"""
from typing import Optional

# (pattern, group). `group` says why it is approved and is not used for the
# verdict:
#   core      every VPU has it
#   hardware  only where that hardware is fitted (GPU, PoE card, cameras,
#             scoreboard and audio gear)
#   image     OEM / chipset extras that ride along on the base image
APPROVED_APPS = (
    # core
    ("Google Chrome", "core"),
    ("LogMeIn", "core"),                      # also matches "LogMeIn Client"
    ("Notepad++", "core"),
    ("Bonjour", "core"),
    ("Microsoft Visual C++", "core"),         # every year / arch of the redistributable
    ("Microsoft .NET Framework", "core"),     # SDK and targeting packs

    # hardware: GPU
    ("NVIDIA Graphics Driver", "hardware"),
    ("NVIDIA HD Audio Driver", "hardware"),
    ("NVIDIA PhysX", "hardware"),
    ("NVIDIA USBC Driver", "hardware"),
    ("NVIDIA FrameView SDK", "hardware"),
    ("NVIDIA App", "hardware"),
    # hardware: PoE card
    ("GIE Series SmartPoE", "hardware"),
    ("ADLINK Vision Software SDK", "hardware"),  # AVS SDK, reads the PoE card
    # hardware: cameras and capture
    ("Basler pylon", "hardware"),
    ("FlyCapture", "hardware"),
    ("JAI SDK", "hardware"),
    ("Blackmagic", "hardware"),                # "Desktop Video" vs "Design Desktop Video" by version,
    ("DCViewer", "hardware"),
    # hardware: scoreboard
    ("ScoreConnect", "hardware"),
    ("SUNIX Multi-IO", "hardware"),
    ("TUSB3410", "hardware"),
    # hardware: audio
    ("UMC v", "hardware"),                    # Behringer UMC interface driver

    # image
    ("HP Support Solutions Framework", "image"),
    ("HP USB Fingerprint Mouse", "image"),
    ("Intel(R) Chipset Device Software", "image"),
    ("Intel(R) Dynamic Tuning", "image"),
    ("Intel(R) Management Engine Components", "image"),
    ("Ext2Fsd", "image"),
    ("Dell Peripheral Manager", "image"),
)


# Reviewed and deliberately NOT approved. They classify as informational (the
# same as an unreviewed app) but beat any approved pattern, so a broad entry
# above can never approve them by accident. Promote one to a risk by adding
# its name to a `_CONCERNING_SOFTWARE` category in main.py.
NOT_APPROVED_APPS = (
    ("TeamViewer", "remote access; only LogMeIn is approved"),
    ("Datto", "remote management / backup agent (datto.com)"),
)


def not_approved_match(name: str) -> Optional[str]:
    name_lc = (name or "").strip().lower()
    for pattern, _why in NOT_APPROVED_APPS:
        if name_lc and pattern.lower() in name_lc:
            return pattern
    return None


def approved_match(name: str) -> Optional[str]:
    """The APPROVED_APPS pattern `name` matches, or None."""
    name_lc = (name or "").strip().lower()
    if not name_lc or not_approved_match(name):
        return None
    for pattern, _group in APPROVED_APPS:
        if pattern.lower() in name_lc:
            return pattern
    return None


def classify(name: str, concern: Optional[dict] = None) -> str:
    """'risk' | 'approved' | 'informational' for one installed application."""
    if concern:
        return "risk"
    return "approved" if approved_match(name) else "informational"
