# T1000 Off-Bus Tally

**Fault:** NVIDIA T1000 not enumerating on the PCI bus ("off-bus")
**Platform:** Intel Core i5-12500 (12th gen / Alder Lake) + UHD Graphics 770 + NVIDIA T1000
**Prepared:** 2026-08-28 · Ian Moore · companion to *The Phantom GPU Failures* report

## Confirmed — 5 of 5 checked

| # | Unit | OS / Version | Evidence | RMA status |
|---|------|--------------|----------|------------|
| 1 | PXLS2_33748 Aurora Christian (IL) Field | Windows 10 IoT LTSC 19044 | No VEN_10DE device on PCI bus; ghost PnP record of "NVIDIA T1000" proves it was fitted. Verified on-box (`Get-GpuTriage.ps1`), 2026-08-27 | In RMA queue (opened Aug 27) |
| 2 | PXLS2L_36960 Tomales (CA) Field | Linux (BalenaOS), 5.37.0 | Pixellot's own diagnostics: `Expected 2 GPU cards and found 1 instead!` (lspci). Verified via Aug 22 + Aug 27 log bundles | In RMA queue (opened Aug 25) |
| 3 | PXLS3_61320 Seminole (Sanford, FL) Whigham Stadium | Linux (BalenaOS), 5.37.0 | Same diagnostics line, Aug 18 + Aug 19 bundles; broken **13 h before** its venue upgrade | In RMA queue (opened Aug 21) |
| 4 | PXLS2_33669 Cold Spring Harbor Jr/Sr (NY) Lower Turf | Windows, 5.27.6 | No VEN_10DE on bus; driver also absent; 0 TDR / 0 WHEA. Verified on-box (one-paste check), 2026-08-28 | **Not yet RMA'd** (backoffice health: "Camera failure") |
| 5 | PXLS3_70757 Sussex Academy (DE) Turf Field | Linux (BalenaOS), 5.27.6 | Full lspci ×3 in POEControler log: iGPU, NVMe, PoE switch, 4 NICs all present; **zero NVIDIA devices**; x16 PEG root port absent = slot failed link training at boot. Verified via Aug 27 bundle | **Not yet RMA'd** |

## Common to all five

- Same CPU/GPU platform (i5-12500 + T1000), both operating systems, four states
- Every other PCI device enumerates normally
- Zero hardware-error events (no TDR, no WHEA, no hardware Xids)
- Backoffice shows Nvidia GPU `N/A` / driver `NONE`, or the nvidia-smi error string
- Misreported downstream as GPU or camera failure by the catch-all error message

## Predicted, not yet checked (same platform, same NONE status)

| # | Unit | OS / Version |
|---|------|--------------|
| 6 | PXLS2_34551 Healdsburg (CA) Field | Windows, 5.27.6 |
| 7 | PXLS2_71696 Northwest Yeshiva (WA) Gym | Windows, 5.37.0 |

## Not this fault (same-looking backoffice status, different cause)

- **Probable off-bus but unconfirmed:** PXLS2_33516 Maui Prep (HI) — i5-12500/T1000, log collection broken, needs on-site look
- **Driver-wipe fault (card confirmed ON the bus):** Mill River, Big Horn, and the other GTX 1650 / i5-8500/10500 units — see the driver-campaign evidence

## Open question: recoverable or dead?

No unit in this class has had a **cold power cycle** (mains off 30 s) yet.
That one test, on any of the five, decides whether this is a recoverable
re-enumeration fault or genuine hardware failure.

## Triage shortcuts

- **Windows:** one-paste PCI check (`Get-GpuTriage.ps1` section 2, or the short block) over LogMeIn
- **Linux (no shell — BalenaOS):** grep any daily bundle — `diagnostics_*.log` for `found 1 instead`, or `POEControler_*.log` for the full lspci dump
