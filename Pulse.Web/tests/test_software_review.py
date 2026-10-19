"""Approved / risk / informational classification of installed applications.

Seeded from the base-image list on 15125 Marist (GA). Names only: versions are
deliberately ignored because they drift.

Stdlib unittest, run from Pulse.Web:  python3 -m unittest tests.test_software_review
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
import software_review as sr  # noqa: E402

MARIST = [
    "Basler pylon GEV Driver", "Blackmagic Desktop Video", "Bonjour", "Ext2Fsd 0.69",
    "FlyCapture 2.12 Release 2 (x64)", "GIE Series SmartPoE", "Google Chrome",
    "HP Support Solutions Framework", "HP USB Fingerprint Mouse",
    "Intel(R) Chipset Device Software", "Intel(R) Dynamic Tuning",
    "Intel(R) Management Engine Components", "JAI SDK x64 Version 3.0.4.1",
    "LogMeIn", "LogMeIn Client", "Microsoft .NET Framework 4.7.2 SDK",
    "Microsoft .NET Framework 4.7.2 Targeting Pack",
    "Microsoft .NET Framework 4.7.2 Targeting Pack (ENU)",
    "Microsoft Visual C++ 2012 Redistributable (x64) - 11.0.61030",
    "Microsoft Visual C++ 2013 Redistributable (x64) - 12.0.21005",
    "Microsoft Visual C++ 2015-2019 Redistributable (x86) - 14.22.27821",
    "Microsoft Visual C++ 2015-2022 Redistributable (x64) - 14.36.32532",
    "Notepad++ (32-bit x86)", "NVIDIA App 11.0.3.232",
    "NVIDIA FrameView SDK 1.5.10920.35420203", "NVIDIA Graphics Driver 576.28",
    "NVIDIA HD Audio Driver 1.4.3.2", "NVIDIA PhysX System Software 9.23.1019",
    "NVIDIA USBC Driver 1.52.831.832", "ScoreConnectII", "SUNIX Multi-IO Controller",
    "TUSB3410 Driver 6.7.5.0", "UMC v2.23.0",
    # vpu-home spellings
    "Blackmagic Design Desktop Video", "ADLINK Vision Software SDK", "ScoreConnectIII",
]


class SoftwareReview(unittest.TestCase):
    def test_every_marist_app_except_teamviewer_is_approved(self):
        for name in MARIST:
            self.assertEqual(sr.classify(name), "approved", name)

    def test_teamviewer_host_is_not_approved(self):
        for n in ("TeamViewer Host", "TeamViewer"):
            self.assertEqual(sr.classify(n), "informational", n)

    def test_datto_is_not_approved(self):
        for name in ("Datto RMM", "Datto Windows Agent", "Datto Backup Agent"):
            self.assertEqual(sr.classify(name), "informational", name)

    def test_not_approved_beats_approved(self):
        # "LogMeIn" is approved; a name matching both must not be.
        self.assertEqual(sr.classify("Datto LogMeIn bridge"), "informational")

    def test_unknown_app_is_informational(self):
        self.assertEqual(sr.classify("Some New Vendor Tool"), "informational")

    def test_risk_beats_approved(self):
        self.assertEqual(sr.classify("Google Chrome", {"severity": "warning"}), "risk")

    def test_version_does_not_matter(self):
        self.assertEqual(sr.classify("Google Chrome"), sr.classify("Google Chrome 99.0"))

    def test_blank_name_is_informational(self):
        self.assertEqual(sr.classify(""), "informational")
        self.assertEqual(sr.classify(None), "informational")


if __name__ == "__main__":
    unittest.main()
