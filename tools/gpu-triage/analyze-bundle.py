#!/usr/bin/env python3
"""Analyze a Pixellot VPU log bundle and decide GPU-fault vs QSV/Intel-fault.

Built from the 2026-08-26 bundle for host 651711c, where the VPU Manager
message "HwDetector failed to use the QSV or NVENC decoder or CUDA" turned out
to mean QSV only - the NVIDIA GPU passed every probe it was given.

The message is a generic concatenation. The coordinator log carries the
specific verdict, and HwDetector logs each probe's DetectedResult separately.
This reads both and reports which accelerator actually failed.

Usage:
    python3 analyze-bundle.py /path/to/log_vpu_YYYY_MM_DD_HHMMSS [...]
    python3 analyze-bundle.py /path/to/bundle.zip
"""
import os
import re
import sys
import zipfile
import tempfile
from collections import Counter

# DetectedResult is a bitmask of the accelerators a given probe found.
# Observed: 24 = NVENC+CUDA probe succeeded; 0 = the probe found nothing.
RE_RESULT = re.compile(r"DetectedResult=(\d+)")
RE_COORD_RESULT = re.compile(r"HwDetection result=(\d+)")
RE_FPS = re.compile(r"Camera #(\d+): Real FPS = ([\d.]+), Expected FPS = ([\d.]+)")
RE_NVDRIVER = re.compile(r"Installed NVIDIA driver:\s*([\d.]+)")
RE_CC = re.compile(r"Nvidia Compute Capability Major:\s*(\d+)\s*;\s*Minor\s*:\s*(\d+)")


def read(path):
    try:
        with open(path, "r", errors="replace") as fh:
            return fh.read()
    except Exception:
        return ""


def find_logs(root):
    """All log paths in the bundle, flat."""
    out = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            if fn.lower().endswith((".log", ".csv")):
                out.append(os.path.join(dirpath, fn))
    return out


def pick(paths, *needles):
    """Select logs whose filename contains any needle.

    Linux bundles name these linuxcoordinator_/linuxagent_; Windows bundles use
    Coordinator_/agent_. Substring matching covers both without a per-platform
    table that would silently miss a renamed log.
    """
    hits = []
    for p in paths:
        base = os.path.basename(p).lower()
        if any(n in base for n in needles):
            hits.append(p)
    return hits


def analyze(root):
    logs = find_logs(root)
    r = {
        "bundle": os.path.basename(root.rstrip("/")),
        "nvenc_ok": 0, "cuda_ok": 0, "qsv_fail": 0, "sdi_fail": 0,
        "results": Counter(), "coord_results": Counter(),
        "nv_driver": "", "compute_cap": "",
        "qsv_decode_errors": 0, "fps_readings": [],
        "coord_verdicts": [], "intel_driver_status": [],
        "coord_nvenc_found": 0, "coord_cuda_found": 0,
        "restart_venue": 0, "rtsp_hosts": set(),
        "reader_decoders": Counter(), "decoder_type_cfg": Counter(),
        "qsv_enabled_later": 0, "restart_cmds": [],
        "nvml_not_loaded": 0, "no_nvidia_gpu": 0, "nvidia_version_none": 0,
        "hwinfo": "", "qsv_enabled_probe": 0,
        "venue": "", "driver_pushes": Counter(),
    }

    for path in pick(logs, "hwdetector"):
        txt = read(path)
        r["nvenc_ok"] += txt.count("NVENC Encoding is enabled")
        r["cuda_ok"] += txt.count("Cuda is enabled")
        r["qsv_fail"] += txt.count("QSV Encoding is disabled")
        r["qsv_enabled_probe"] += txt.count("QSV Encoding is enabled")
        r["sdi_fail"] += txt.count("SDI Encoding is disabled")
        for m in RE_RESULT.finditer(txt):
            r["results"][int(m.group(1))] += 1

    for path in pick(logs, "coordinator"):
        txt = read(path)
        for m in RE_COORD_RESULT.finditer(txt):
            r["coord_results"][int(m.group(1))] += 1
        r["coord_nvenc_found"] += txt.count("NVENC is Found")
        r["coord_cuda_found"] += txt.count("Cuda is Found")
        for line in txt.splitlines():
            if "CheckHwDetectorStatus" in line and ("not properly installed" in line or "failed" in line):
                r["coord_verdicts"].append(line.split("|")[-1].strip())
            if "Local status of Intel load driver" in line:
                r["intel_driver_status"].append(line.split("|")[-1].strip())
            if "Coordinator->Agent RestartVenue" in line:
                r["restart_venue"] += 1
                parts = line.split("|")
                if len(parts) > 1:
                    r["restart_cmds"].append(parts[1].strip())
            if "QSV HW is enabled" in line:
                r["qsv_enabled_later"] += 1

    for path in pick(logs, "camerastester"):
        txt = read(path)
        r["qsv_decode_errors"] += len(re.findall(r"VideoDecoderQSVImpl.*Error in MFX", txt))
        for m in RE_FPS.finditer(txt):
            r["fps_readings"].append((int(m.group(1)), float(m.group(2)), float(m.group(3))))
        for m in re.finditer(r"rtsp://([\d.]+)", txt):
            r["rtsp_hosts"].add(m.group(1))
        for m in re.finditer(r"Creating RTSP reader with decoder type = (\w+)", txt):
            r["reader_decoders"][m.group(1)] += 1

    for path in pick(logs, "coordinator", "agent", "vpu"):
            txt = read(path)
            for m in re.finditer(r"/RTSP/DECODER_TYPE[^A-Za-z]{0,20}([A-Z]{3,10})", txt):
                r["decoder_type_cfg"][m.group(1)] += 1
            for m in re.finditer(r"Creating RTSP reader with decoder type = (\w+)", txt):
                r["reader_decoders"][m.group(1)] += 1

    for path in pick(logs, "vpu", "agent", "coordinator"):
        txt = read(path)
        r["nvml_not_loaded"] += len(re.findall(
            r"Unable to initialize NVML: error code 9", txt))
        r["no_nvidia_gpu"] += txt.count("Failed to find an NVIDIA GPU")
        r["nvidia_version_none"] += len(re.findall(
            r"Nvidia version after hw update:\s*NONE", txt))
        if not r["hwinfo"]:
            m = re.search(r"(Intel \[CPU:[^\]]{0,200}\])", txt)
            if m:
                r["hwinfo"] = m.group(1)
        if not r["venue"]:
            m = re.search(r"(PXLS2[A-Z]?_\d+ [^\"]{0,45})", txt)
            if m:
                r["venue"] = m.group(1).strip()
        # A cloud-pushed GPU driver install is a prime suspect whenever the GPU
        # goes invisible: -clean removes the working driver first.
        for m in re.finditer(
                r"Drivers/([0-9.]+)[^\"]*\.exe.{0,400}?\"args\",\"value\":\"([^\"]*)\""
                r".{0,120}?\"initiator\",\"value\":\"([^\"]*)\"", txt, re.S):
            r["driver_pushes"][(m.group(1), m.group(2).lstrip("|"), m.group(3))] += 1
        m = RE_NVDRIVER.search(txt)
        if m and not r["nv_driver"]:
            r["nv_driver"] = m.group(1)
        m = RE_CC.search(txt)
        if m and not r["compute_cap"]:
            r["compute_cap"] = "%s.%s" % (m.group(1), m.group(2))

    # Record what the bundle actually contained - an absent HwDetector log is
    # itself a finding (the venue stack never ran), not a clean bill of health.
    r["has_hwdetector"] = bool(pick(logs, "hwdetector"))
    r["has_camerastester"] = bool(pick(logs, "camerastester"))
    r["file_count"] = len(logs)
    return r


def verdict(r):
    """Return (verdict, [reasons]). NVIDIA is only implicated by NVIDIA evidence."""
    reasons = []
    gpu_proven = (r["nvenc_ok"] > 0 and r["cuda_ok"] > 0) or \
                 (r["coord_nvenc_found"] > 0 and r["coord_cuda_found"] > 0)
    qsv_broken = r["qsv_fail"] > 0 or r["qsv_decode_errors"] > 0

    if r["coord_nvenc_found"] or r["coord_cuda_found"]:
        reasons.append('coordinator logged "NVENC is Found" %d time(s) and '
                       '"Cuda is Found" %d time(s)'
                       % (r["coord_nvenc_found"], r["coord_cuda_found"]))
    if r["nvenc_ok"] or r["cuda_ok"]:
        reasons.append("HwDetector reported NVENC enabled %d time(s) and CUDA %d time(s)"
                       % (r["nvenc_ok"], r["cuda_ok"]))
    if r["nv_driver"]:
        reasons.append("NVIDIA driver %s loaded" % r["nv_driver"])
    if r["compute_cap"]:
        reasons.append("compute capability %s read off the card (7.5 = Turing / T1000)"
                       % r["compute_cap"])
    if qsv_broken:
        reasons.append("QSV failed: %d encoder probe failure(s), %d decoder MFX error(s)"
                       % (r["qsv_fail"], r["qsv_decode_errors"]))
    if r["intel_driver_status"]:
        reasons.append("coordinator reported on the Intel driver: %s"
                       % r["intel_driver_status"][0])

    readers = set(r["reader_decoders"])
    configured = set(r["decoder_type_cfg"])
    if readers:
        reasons.append("camera self-test created its RTSP readers with decoder(s): %s"
                       % ", ".join(sorted(readers)))
    if configured:
        reasons.append("production decoder configured as: %s" % ", ".join(sorted(configured)))
    if "QSV" in readers and configured and "QSV" not in configured:
        reasons.append("MISMATCH: the self-test decodes via QSV while production is set "
                       "to %s - the unit can stream while failing its own camera test"
                       % ", ".join(sorted(configured)))

    if r["restart_venue"]:
        span = ""
        if len(r["restart_cmds"]) > 1:
            span = " between %s and %s" % (r["restart_cmds"][0], r["restart_cmds"][-1])
        reasons.append("coordinator issued %d venue restart(s)%s because the hardware "
                       "check failed" % (r["restart_venue"], span))
    if r["qsv_enabled_later"]:
        reasons.append('QSV later reported "QSV HW is enabled" %d time(s) on this SAME unit '
                       "- the fault cleared without any hardware change"
                       % r["qsv_enabled_later"])

    gpu_invisible = (r["no_nvidia_gpu"] > 0 or r["nvml_not_loaded"] > 0
                     or r["nvidia_version_none"] > 0)
    if gpu_invisible and not gpu_proven:
        if r["no_nvidia_gpu"]:
            reasons.append('platform logged "Failed to find an NVIDIA GPU" %d time(s)'
                           % r["no_nvidia_gpu"])
        if r["nvml_not_loaded"]:
            reasons.append("NVML init failed with error code 9 (driver not loaded) %d time(s)"
                           % r["nvml_not_loaded"])
        if r["nvidia_version_none"]:
            reasons.append('hardware inventory reports "Nvidia version ... NONE" %d time(s)'
                           % r["nvidia_version_none"])
        if r["hwinfo"]:
            reasons.append("hwInfo string is Intel-only: %s" % r["hwinfo"][:120])
        if r["qsv_enabled_probe"]:
            reasons.append("QSV encoding IS enabled here (%d probe(s)) - the encoder path "
                           "on this unit works" % r["qsv_enabled_probe"])
        for (ver, args, init), n in r["driver_pushes"].most_common():
            reasons.append("CLOUD PUSHED NVIDIA DRIVER %s with args '%s' (initiator=%s) - "
                           "'-clean' removes the working driver first and '-noreboot' can "
                           "leave the new one not loaded, which is exactly NVML error 9"
                           % (ver, args, init))
        reasons.append("LOGS CANNOT SETTLE THIS: 'no NVIDIA GPU' reads identically whether "
                       "the card is absent by design, unseated, or its driver is not loaded. "
                       "Run Get-GpuTriage.ps1 on the unit to read the PCI bus.")
        return "GPU_NOT_VISIBLE__CHECK_ON_BOX", reasons

    if gpu_proven and qsv_broken and r["qsv_enabled_later"]:
        return "GPU_HEALTHY__QSV_TRANSIENT", reasons
    if gpu_proven and qsv_broken:
        return "GPU_HEALTHY__QSV_FAULT", reasons
    if gpu_proven:
        return "GPU_HEALTHY", reasons
    if not gpu_proven and r["results"] and max(r["results"]) == 0:
        reasons.append("no probe ever reported NVENC or CUDA enabled")
        return "GPU_SUSPECT", reasons
    if not r.get("has_hwdetector"):
        return "INCONCLUSIVE", reasons + [
            "NO HwDetector LOG IN THIS BUNDLE (%d log files total) - the venue stack "
            "never ran in this window, so the GPU was never probed. This is NOT a pass."
            % r.get("file_count", 0)]
    return "INCONCLUSIVE", reasons + ["no HwDetector NVENC/CUDA probe found in this bundle"]


def report(r):
    v, reasons = verdict(r)
    print("=" * 70)
    print("BUNDLE: %s" % r["bundle"])
    print("=" * 70)
    print("VERDICT: %s" % v)
    for x in reasons:
        print("   - %s" % x)
    print()
    if r.get("venue"):
        print("VENUE: %s" % r["venue"])
    if r.get("driver_pushes"):
        print("Cloud driver pushes seen")
        for (ver, args, init), n in r["driver_pushes"].most_common():
            print("  NVIDIA %s  args='%s'  initiator=%s  (x%d)" % (ver, args, init, n))
    print("Bundle contents: %d log file(s), HwDetector=%s, CamerasTester=%s"
          % (r.get("file_count", 0),
             "yes" if r.get("has_hwdetector") else "MISSING",
             "yes" if r.get("has_camerastester") else "MISSING"))
    print("NVIDIA path")
    print("  NVENC enabled ........ %d probe(s)" % r["nvenc_ok"])
    print("  CUDA enabled ......... %d probe(s)" % r["cuda_ok"])
    print("  driver ............... %s" % (r["nv_driver"] or "not reported"))
    print("  compute capability ... %s" % (r["compute_cap"] or "not reported"))
    print('  coordinator says ..... "NVENC is Found" x%d, "Cuda is Found" x%d'
          % (r["coord_nvenc_found"], r["coord_cuda_found"]))
    if r["hwinfo"]:
        print("  platform hwInfo ...... %s" % r["hwinfo"][:110])
    if r["no_nvidia_gpu"] or r["nvml_not_loaded"] or r["nvidia_version_none"]:
        print('  "Failed to find an NVIDIA GPU" x%d, NVML err9 x%d, "version NONE" x%d'
              % (r["no_nvidia_gpu"], r["nvml_not_loaded"], r["nvidia_version_none"]))
    print("Intel QSV path")
    print("  QSV encoder failures . %d" % r["qsv_fail"])
    print("  QSV encoder ENABLED .. %d probe(s)" % r["qsv_enabled_probe"])
    print("  QSV decoder MFX errs . %d" % r["qsv_decode_errors"])
    print("  SDI/DeckLink absent .. %d" % r["sdi_fail"])
    if r["reader_decoders"] or r["decoder_type_cfg"]:
        print("Decoder selection")
        for k, n in sorted(r["reader_decoders"].items()):
            print("  self-test readers ... %-8s x%d" % (k, n))
        for k, n in sorted(r["decoder_type_cfg"].items()):
            print("  configured (/RTSP) .. %-8s x%d" % (k, n))
    print("HwDetector DetectedResult tally")
    for val, n in sorted(r["results"].items()):
        note = "NVENC+CUDA probe OK" if val == 24 else ("nothing detected" if val == 0 else "")
        print("  result=%-4s %d time(s)   %s" % (val, n, note))
    if r["coord_results"]:
        print("Coordinator HwDetection tally")
        for val, n in sorted(r["coord_results"].items()):
            print("  result=%-4s %d time(s)" % (val, n))
    if r["coord_verdicts"]:
        print("Coordinator's own verdict text")
        for x in r["coord_verdicts"][:3]:
            print("  %s" % x)
    if r["restart_venue"]:
        print("Venue restarts triggered by the hardware check: %d" % r["restart_venue"])
        if len(r["restart_cmds"]) > 1:
            print("  from %s to %s" % (r["restart_cmds"][0], r["restart_cmds"][-1]))
    if r["qsv_enabled_later"]:
        print('QSV later reported "QSV HW is enabled": %d time(s)' % r["qsv_enabled_later"])
    if r["fps_readings"]:
        zero = [x for x in r["fps_readings"] if x[1] == 0.0]
        print("Camera FPS: %d reading(s), %d at 0.00 fps" % (len(r["fps_readings"]), len(zero)))
        if r["rtsp_hosts"]:
            print("  cameras reached over RTSP: %s" % ", ".join(sorted(r["rtsp_hosts"])))
        if zero and r["qsv_decode_errors"]:
            print("  NOTE: 0 fps here is a DECODE failure, not a dark camera - the RTSP")
            print("        stream connected and every frame died in the QSV decoder.")
    print()


def main(paths):
    tmpdirs = []
    roots = []
    for p in paths:
        if p.lower().endswith(".zip"):
            td = tempfile.mkdtemp(prefix="vpubundle-")
            tmpdirs.append(td)
            try:
                with zipfile.ZipFile(p) as z:
                    z.extractall(td)
                roots.append(td)
            except Exception as exc:
                print("cannot read zip %s: %s" % (p, exc), file=sys.stderr)
        elif os.path.isdir(p):
            roots.append(p)
        else:
            print("skip %s (not a directory or zip)" % p, file=sys.stderr)

    results = []
    for root in roots:
        r = analyze(root)
        report(r)
        results.append((r, verdict(r)[0]))

    if len(results) > 1:
        print("=" * 70)
        print("ACROSS %d BUNDLES" % len(results))
        print("=" * 70)
        for v, n in Counter(x[1] for x in results).most_common():
            print("  %-24s %d" % (v, n))
        healthy = [x for x in results if x[1].startswith("GPU_HEALTHY")]
        if healthy:
            print()
            print("  %d of %d units have a GPU that passed its NVENC/CUDA probe."
                  % (len(healthy), len(results)))
            print("  Those units have no NVIDIA evidence supporting an RMA.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))
