# GPU triage — is this NVIDIA card actually dead?

Built for the current RMA wave: eight-plus units in two weeks all failing with
`HwDetector failed to use the QSV or NVENC decoder or CUDA` /
`gpu type is: N/A`, all being sent back as hardware faults on Pixellot's word.

These scripts exist to answer one question with evidence instead of inference:
**can this GPU still encode and decode, right now, on this box?** If it can,
the HwDetector failure is not a dead card and the unit should not be RMA'd.

| File | Runs on | What it does |
|---|---|---|
| `gpu-triage.sh` | Linux VPU | Full bottom-up triage, JSON + log out |
| `Get-GpuTriage.ps1` | Windows VPU (PS 5.1) | Same triage, Windows sources |
| `compare-units.py` | Your laptop | Diffs the JSON from several units, finds shared factors |

## Run it (Windows)

Copy the folder to the VPU, open an **elevated** PowerShell, and run:

```bash
powershell -ExecutionPolicy Bypass -File .\Get-GpuTriage.ps1
```

The Linux script is parked until command access to those units exists:

```bash
sudo ./gpu-triage.sh
```

Run elevated/root — without it, dmesg, PCIe config space and the Windows event
log are all degraded, and the script will (correctly) refuse to reach a verdict
rather than guess. Each run writes `gpu-triage-<host>-<stamp>.json` plus a full
log next to it. Collect the JSON from every unit, then:

```bash
python3 compare-units.py gpu-triage-*.json
```

## What the verdicts mean

| Verdict | Exit | Meaning | Action |
|---|---|---|---|
| `NOT_HARDWARE` | 0 | The GPU encoded with NVENC and decoded with CUDA during the test | **Do not RMA.** The failure is software, timing, or encoder contention |
| `SOFTWARE_FAULT` | 1 | GPU is on the bus, driver stack is broken (mismatch, unloaded module, WU driver, Secure Boot, missing uvm) | Fix in place, retest. **Do not RMA** until repaired |
| `HARDWARE_SUSPECT` | 2 | Physical-layer evidence: fell off the bus, degraded link, fatal WHEA/AER, hardware Xid, thermal shutdown | **Reseat and retest first** — reseating clears most of these. RMA only if it survives |
| `INCONCLUSIVE` | 3 | The run could not see enough to judge | Re-run root/elevated, with `pciutils`, `nvidia-smi` and `ffmpeg` present |

`HARDWARE_SUSPECT` is deliberately not "RMA it". Card seating, riser contact,
PCIe slot and BIOS settings produce the same evidence as dead silicon, and they
cost a reseat rather than a chassis swap.

## What it checks, in order

1. **Fleet-correlation facts** — driver version, kernel/OS build, BIOS, recent
   package or hotfix installs. These are the fields `compare-units.py` diffs.
2. **Is the GPU on the PCI bus at all?** Vendor `10DE` enumeration, plus
   whether the OS has a *record* of a device that is no longer present (a card
   that dropped out looks different from one that was never fitted).
3. **PCIe link health** — trained width vs capable width, all-`ff` config
   space, AER / WHEA errors, replay counter.
4. **Driver state** — module bound, nouveau vs nvidia, DKMS built for the
   running kernel, Secure Boot rejection, `/dev/nvidia*` nodes, `nvidia_uvm`
   loaded, PnP problem codes, whether Windows Update swapped in its own driver.
5. **NVML health** — thermals, hardware slowdown, memory retirement, and who
   already holds the encoder.
6. **Xid / event-log history** — Xid codes are classified individually: 79, 62,
   69 and the ECC family count as hardware; 13, 31, 43, 45 are application-level
   faults and are explicitly *not* treated as RMA evidence.
7. **Functional NVENC + CUDA test** — 60 frames of 720p through `h264_nvenc`,
   then decoded back with `-hwaccel cuda`. This is the decisive step.
8. **Intel QSV path** — the other half of the HwDetector message.

## Reading the two failures that started this

- **Windows unit** — `gpu type is: N/A, intelGpu: UHD Graphics 770` says the
  detector found the Intel iGPU and no NVIDIA device. On a *newly RMA'd* box,
  check first that a discrete card is physically fitted and enumerating before
  accepting "hardware fault" — section 2 answers that in one line, and it
  distinguishes "no card" from "WMI could not look", which look identical in
  the HwDetector message.
- **Linux unit** — `HwDetector failed to use the QSV or NVENC decoder or CUDA`
  names three separate paths. All three failing at once points upstream of any
  one of them: driver not loaded, `nvidia_uvm` missing, or the device not
  enumerated. A dead encoder block alone would not take Intel QSV down with it.

## Capture order on the Windows unit

Run the script **while the unit is still failing** — a reboot can clear the
evidence, and a failure that clears on reboot is itself the finding.

1. Elevated PowerShell, run the script, keep the JSON and the log.
2. Note the `HwDetector failure present in logs back to ...` line (section 7)
   and compare it against the driver date and hotfix dates in section 1.
3. Reboot, run it again. Same verdict twice is a real state; a verdict that
   changes on reboot is a software fault.
4. If it says `HARDWARE_SUSPECT`, reseat the card and run a third time before
   anything goes back to Pixellot.

The Linux unit's logs can be dropped in later — `compare-units.py` takes both
platforms' JSON in the same run.

## Limits — what this cannot see

- It cannot prove a card is good under a full multi-hour event load; it proves
  the encode and decode paths work on demand.
- Intermittent faults need the script run *at the moment of failure*, which is
  why it goes on the unit rather than being read off after the fact.
- It reads Pixellot's HwDetector result second-hand. If HwDetector fails while
  this script passes, the disagreement itself is the finding — take that to
  Pixellot rather than the chassis to the RMA pile.
