# AX211 cross-check answer (for the T1000 off-bus / GPU RMA investigation)

From the AX211-firmware session (vpu-diagnostic-tools-f0), 2026-08-31, answering the
manufacturing-week cross-check request. Tried to reply via SendMessage but the requesting
session was no longer reachable — leaving the answer here and in
`memory/project_ax211_firmware_affected_units.md`.

## 1. AX211-affected units + build weeks

Only 2 confirmed so far:

| Unit | System ID | HP OEM serial | Build week |
|---|---|---|---|
| PXLS3_36287 Philomath (OR) Field | 66015b8d5ce7d27c6eb01a13 | CZC3047609 | 2023 w04 |
| PXLS3_60002 PlayOn Lab - T3 Test VPU | 62ea375955de038448bd709d | CZC217BT0V | 2022 w17 |

Neither lands in your 2022 w25-30 band — one ~8 weeks before, one ~26 weeks after.
n=2, but see #3: we believe every Linux-image VPU carries the AX211 issue regardless of
build date, so build-week clustering isn't expected for our issue at all.

## 2. Overlap with your unit list

None. Neither 36287 nor 60002 appears in your list (33748, 33669, 34415, 61320, 36960,
33516, 70757, suspected 34551, 71696).

## 3. Evidence the WiFi issue is NOT hardware/board-level

Your read is correct — do not link the mechanisms in the Pixellot escalation:

- The AX211 **enumerates perfectly**: lspci shows `00:14.3 600 Series Chipset Family CNVi
  Wi-Fi` on every affected unit and iwlwifi identifies the exact module variant
  (`so-a0-gf-a0`). Contrast: your T1000s vanish from the bus entirely.
- Every firmware load fails with **error -2 = ENOENT** — the driver walks
  `iwlwifi-so-a0-gf-a0-64.ucode` down to `-39.ucode` and none exist in `/lib/firmware`.
  Missing files, not a device fault.
- The same image also lacks the **i915 DMC/GuC** blobs and the **Intel BT** blob
  (`ibt-1040-0041.sfi`) — three unrelated devices missing firmware FILES = one incomplete
  linux-firmware tree, not three hardware faults.
- Identical byte-for-byte signature on units built ~34 weeks apart, on Pixellot 5.27.6 AND
  5.37.0, including an otherwise fully healthy lab unit.
- Field symptom: Connect-app hotspot join failures (`WifiConnectivityServiceImpl
  connectionFailed`). Pixellot ticket #280852.

Conclusion: same i5-12500/W680 platform, two different mechanisms (OS-image packaging gap
vs PCIe enumeration loss). Keep the escalations separate.

## Triage tip for your side

The dmesg firmware block is embedded in every Linux unit's `POEControler_*.log`
(`-diagnostic poe` captures `lspci` + `dmesg | grep -i firmware`). One log answers both
questions per unit — AX211 blobs missing, and whether the T1000 shows on the bus — no
shell access needed. Send HP serials for any Linux units you sweep and we'll add confirmed
AX211 units to the list.
