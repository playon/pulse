#!/usr/bin/env bash
# gpu-triage.sh - decide whether an NVIDIA GPU on a Linux VPU is actually
# faulty silicon, or whether the "HwDetector failed to use the QSV or NVENC
# decoder or CUDA" error has a software / config / contention cause.
#
# Run as root for the full picture (dmesg + full PCIe config space):
#     sudo ./gpu-triage.sh
#
# Writes a human-readable report to stdout and a JSON summary next to it so
# results from several units can be diffed to find a common factor.
#
# Exit codes:  0 = NOT_HARDWARE   1 = SOFTWARE_FAULT
#              2 = HARDWARE_SUSPECT   3 = INCONCLUSIVE

VERSION="1.0"
OUTDIR="${GPU_TRIAGE_OUTDIR:-.}"
HOST="$(hostname 2>/dev/null || echo unknown)"
STAMP="$(date +%Y%m%d-%H%M%S)"
TS="$(date -Is 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)"
JSON="$OUTDIR/gpu-triage-$HOST-$STAMP.json"
LOG="$OUTDIR/gpu-triage-$HOST-$STAMP.log"

# --- findings accumulators -------------------------------------------------
HW_EVIDENCE=()    # points at dead/failing silicon or physical link
SW_EVIDENCE=()    # points at driver / config / contention
INFO=()           # neutral facts worth recording
IS_ROOT=0; [ "$(id -u)" -eq 0 ] && IS_ROOT=1
ENUM_OK=1   # 0 when the host lacks the tools to inspect the bus/driver at all

have() { command -v "$1" >/dev/null 2>&1; }
hw()   { HW_EVIDENCE+=("$1"); }
sw()   { SW_EVIDENCE+=("$1"); }
info() { INFO+=("$1"); }
sect() { printf '\n=== %s ===\n' "$1"; }
jesc() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g' | tr -d '\000-\037'; }

exec > >(tee "$LOG") 2>&1

echo "NVIDIA GPU triage v$VERSION"
echo "host: $HOST   date: $TS   root: $IS_ROOT"
[ "$IS_ROOT" -eq 0 ] && echo "WARNING: not root - dmesg and PCIe config space checks will be degraded."

# ===========================================================================
sect "1. HOST / FLEET CORRELATION FACTS"
# These are the fields to compare across every RMA'd unit. If eight units
# share a driver or kernel version, the GPUs are not the common factor.
# ===========================================================================
KERNEL="$(uname -r 2>/dev/null)"
DISTRO="$(. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME")"
BIOS_VER="$(cat /sys/class/dmi/id/bios_version 2>/dev/null)"
BIOS_DATE="$(cat /sys/class/dmi/id/bios_date 2>/dev/null)"
PRODUCT="$(cat /sys/class/dmi/id/product_name 2>/dev/null)"
UPTIME="$(uptime -p 2>/dev/null || cat /proc/uptime 2>/dev/null)"
echo "product     : $PRODUCT"
echo "distro      : $DISTRO"
echo "kernel      : $KERNEL"
echo "bios        : $BIOS_VER ($BIOS_DATE)"
echo "uptime      : $UPTIME"

# When did the NVIDIA packages last change? A cluster of failures right after
# a common package date is the signature of a rollout, not eight dead cards.
NV_PKG_DATE=""
if have dpkg-query; then
  echo "-- nvidia packages (dpkg) --"
  dpkg-query -W -f='${Package} ${Version}\n' '*nvidia*' 2>/dev/null | grep -v '^$'
  NV_PKG_DATE="$(ls -l --time-style=+%Y-%m-%d /var/lib/dpkg/info/*nvidia*.list 2>/dev/null | awk '{print $6}' | sort -u | tail -1)"
elif have rpm; then
  echo "-- nvidia packages (rpm) --"
  rpm -qa '*nvidia*' 2>/dev/null
fi
[ -n "$NV_PKG_DATE" ] && echo "nvidia pkg files last written: $NV_PKG_DATE"
if [ -f /var/log/apt/history.log ]; then
  echo "-- recent apt transactions touching nvidia/linux-image --"
  grep -E -A2 '^Start-Date' /var/log/apt/history.log 2>/dev/null \
    | grep -B1 -E 'nvidia|linux-image|linux-modules' | tail -20
fi

# ===========================================================================
sect "2. IS THE GPU ON THE PCIe BUS AT ALL?"
# Layer 0. If the device does not enumerate, nothing above it can work -
# and the cause is card seating / riser / BIOS just as often as dead silicon.
# ===========================================================================
PCI_PRESENT=0; SLOT=""; DEVID=""; GPU_NAME=""
if have lspci; then
  NV_LINES="$(lspci -D -nn 2>/dev/null | grep -iE '\[10de:|nvidia')"
  if [ -n "$NV_LINES" ]; then
    PCI_PRESENT=1
    echo "$NV_LINES"
    # First VGA/3D controller wins
    SLOT="$(echo "$NV_LINES" | grep -iE 'VGA|3D controller' | head -1 | awk '{print $1}')"
    [ -z "$SLOT" ] && SLOT="$(echo "$NV_LINES" | head -1 | awk '{print $1}')"
    DEVID="$(echo "$NV_LINES" | head -1 | grep -o '\[10de:[0-9a-f]*\]' | head -1)"
    GPU_NAME="$(echo "$NV_LINES" | head -1 | sed 's/.*controller[^:]*: //; s/ \[10de.*//')"
    info "NVIDIA device enumerates at $SLOT $DEVID"
  else
    echo "NO NVIDIA (vendor 10de) DEVICE FOUND ON THE PCIe BUS."
    hw "No NVIDIA device on the PCIe bus at all - card absent, unseated, or dead"
  fi
  echo "-- all display-class devices --"
  lspci -nn 2>/dev/null | grep -iE 'VGA|3D controller|Display controller'
else
  echo "lspci not installed - cannot enumerate PCI. Install pciutils."
  ENUM_OK=0
  info "lspci missing; bus enumeration skipped - this run cannot rule hardware in or out"
fi

# ===========================================================================
sect "3. PCIe LINK HEALTH"
# A card that enumerates but trained to a degraded width, or whose config
# space reads back all-ff, is a physical-layer problem: reseat before RMA.
# ===========================================================================
if [ "$PCI_PRESENT" -eq 1 ] && have lspci; then
  LNK="$(lspci -vv -s "$SLOT" 2>/dev/null | grep -E 'LnkCap|LnkSta' | sed 's/^\s*/  /')"
  if [ -n "$LNK" ]; then
    echo "$LNK"
    CAP_W="$(echo "$LNK" | grep LnkCap | grep -o 'Width x[0-9]*' | grep -o '[0-9]*$' | head -1)"
    STA_W="$(echo "$LNK" | grep LnkSta | grep -o 'Width x[0-9]*' | grep -o '[0-9]*$' | head -1)"
    if [ -n "$CAP_W" ] && [ -n "$STA_W" ] && [ "$STA_W" -lt "$CAP_W" ]; then
      hw "PCIe link trained DEGRADED: x$STA_W of x$CAP_W capable - reseat card/riser before RMA"
    fi
    echo "$LNK" | grep -qi 'LnkSta.*(downgraded)' && hw "PCIe link reported as downgraded by lspci"
  else
    [ "$IS_ROOT" -eq 0 ] && echo "  (link state needs root)"
  fi

  # All-ff config space == the device stopped responding (fell off the bus).
  if [ "$IS_ROOT" -eq 1 ]; then
    CFG="$(lspci -xxx -s "$SLOT" 2>/dev/null | sed -n '2p')"
    echo "  config space row 0: $CFG"
    if echo "$CFG" | grep -qiE 'ff ff ff ff ff ff ff ff'; then
      hw "PCIe config space reads all-ff - device has fallen off the bus (hard fault)"
    fi
  fi

  # Kernel-reported PCIe AER errors on the GPU's port.
  if have dmesg && [ "$IS_ROOT" -eq 1 ]; then
    AER="$(dmesg 2>/dev/null | grep -iE 'AER|pcieport.*error|Bus error|link is down|link training' | tail -15)"
    if [ -n "$AER" ]; then
      echo "-- PCIe error / AER lines --"; echo "$AER"
      echo "$AER" | grep -qi 'Uncorrected\|Fatal' && hw "Uncorrected/fatal PCIe AER errors present"
      echo "$AER" | grep -qi 'Corrected' && info "Corrected PCIe AER errors present (watch, not proof of failure)"
    fi
  fi
fi

# ===========================================================================
sect "4. KERNEL DRIVER STATE"
# The single most common cause of a whole batch failing at once: the kernel
# module did not rebuild or load after an update. That is not an RMA.
# ===========================================================================
DRIVER_BOUND=""
if [ "$PCI_PRESENT" -eq 1 ] && have lspci; then
  DRIVER_BOUND="$(lspci -k -s "$SLOT" 2>/dev/null | grep 'Kernel driver in use' | cut -d: -f2 | tr -d ' ')"
  echo "kernel driver in use: ${DRIVER_BOUND:-<none>}"
  if [ -z "$DRIVER_BOUND" ]; then
    sw "GPU is on the bus but NO kernel driver is bound to it - driver problem, not silicon"
  elif [ "$DRIVER_BOUND" = "nouveau" ]; then
    sw "nouveau is bound instead of the nvidia driver - NVENC/CUDA cannot work; blacklist nouveau"
  fi
fi

echo "-- loaded nvidia modules --"
lsmod 2>/dev/null | grep -E '^nvidia|^nouveau' || echo "  (none loaded)"
if lsmod 2>/dev/null | grep -q '^nvidia_uvm'; then
  info "nvidia_uvm loaded (CUDA prerequisite present)"
elif [ "$PCI_PRESENT" -eq 1 ]; then
  sw "nvidia_uvm NOT loaded - CUDA will fail even when NVENC works (modprobe nvidia_uvm)"
fi

if [ -r /proc/driver/nvidia/version ]; then
  echo "-- /proc/driver/nvidia/version --"; cat /proc/driver/nvidia/version
  RUNNING_DRV="$(grep -o 'Kernel Module *[0-9.]*' /proc/driver/nvidia/version | grep -o '[0-9.]*$')"
else
  echo "/proc/driver/nvidia/version absent - nvidia kernel module is not loaded"
  RUNNING_DRV=""
fi

# modprobe failure text is the most direct statement of why it will not load.
if [ -n "$(lsmod 2>/dev/null | grep '^nvidia ')" ]; then
  :
else
  if ! have modprobe; then
    echo "-- modprobe unavailable; skipping module load probe --"
    ENUM_OK=0
  elif [ "$IS_ROOT" -eq 0 ]; then
    echo "-- skipping modprobe probe (needs root) --"
  else
  echo "-- attempting modprobe nvidia (diagnostic) --"
  MODOUT="$(modprobe nvidia 2>&1)"
  echo "${MODOUT:-  (loaded without output)}"
  echo "$MODOUT" | grep -qi 'Key was rejected\|Required key not available' \
    && sw "Kernel module rejected by Secure Boot signing - config issue, not hardware"
  echo "$MODOUT" | grep -qi 'Module nvidia not found' \
    && sw "nvidia module not found for kernel $KERNEL - DKMS build missing after a kernel update"
  fi
fi

if have dkms; then
  echo "-- dkms status --"; dkms status 2>/dev/null | grep -i nvidia || echo "  (no nvidia dkms modules)"
  DKMS_NV="$(dkms status 2>/dev/null | grep -i nvidia)"
  if [ -n "$DKMS_NV" ] && ! echo "$DKMS_NV" | grep -q "$KERNEL"; then
    sw "DKMS has no nvidia build for the running kernel $KERNEL - module will not load until rebuilt"
  fi
fi

if have mokutil; then
  SB="$(mokutil --sb-state 2>/dev/null)"
  echo "secure boot  : ${SB:-unknown}"
  echo "$SB" | grep -qi 'enabled' && info "Secure Boot is enabled - unsigned/rebuilt modules will be refused"
fi

echo "-- device nodes --"
if ls -l /dev/nvidia* 2>/dev/null; then :; else
  echo "  (no /dev/nvidia* nodes)"
  [ "$PCI_PRESENT" -eq 1 ] && sw "No /dev/nvidia* device nodes - userspace cannot open the GPU"
fi

# ===========================================================================
sect "5. NVIDIA-SMI / NVML"
# ===========================================================================
SMI_OK=0; SMI_OUT=""
if have nvidia-smi; then
  SMI_OUT="$(nvidia-smi 2>&1)"; SMI_RC=$?
  echo "$SMI_OUT" | head -25
  if [ $SMI_RC -eq 0 ]; then
    SMI_OK=1
    GPU_NAME="$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)"
    echo "-- query --"
    nvidia-smi --query-gpu=name,serial,uuid,vbios_version,driver_version,pstate,temperature.gpu,power.draw,utilization.gpu,memory.total,memory.used --format=csv 2>/dev/null
  else
    # NVML error strings are highly diagnostic - each maps to a different cause.
    echo "$SMI_OUT" | grep -qi 'Driver/library version mismatch' \
      && sw "NVML driver/library version mismatch - packages updated without a reboot. Reboot, do not RMA."
    echo "$SMI_OUT" | grep -qi 'No devices were found' \
      && info "nvidia-smi ran but found no devices - correlate with the PCIe section above"
    echo "$SMI_OUT" | grep -qi 'couldn.t communicate with the NVIDIA driver\|NVIDIA-SMI has failed' \
      && sw "nvidia-smi cannot reach the driver - module not loaded/initialised"
    echo "$SMI_OUT" | grep -qi 'Unable to determine the device handle\|GPU is lost\|Unknown Error' \
      && hw "NVML reports the GPU handle is lost - device stopped responding (hard fault signature)"
  fi
else
  echo "nvidia-smi not installed"
  if [ "$PCI_PRESENT" -eq 1 ]; then
    sw "nvidia-smi not present - driver package incomplete; cannot judge the GPU from this host as-is"
  else
    ENUM_OK=0
  fi
fi

if [ "$SMI_OK" -eq 1 ]; then
  echo "-- thermal / throttle / errors --"
  nvidia-smi -q -d TEMPERATURE,PERFORMANCE,POWER,ECC 2>/dev/null \
    | grep -iE 'GPU Current Temp|Shutdown|Slowdown|Max Operating|Clocks (Event|Throttle) Reasons|HW Thermal|HW Power Brake|Sw Thermal|Pending|Volatile|Uncorrectable|Correctable|Retired|Remapped|Power Draw' \
    | sed 's/^\s*/  /' | head -30
  THROT="$(nvidia-smi -q 2>/dev/null | grep -A12 'Clocks Event Reasons\|Clocks Throttle Reasons' | grep -i 'HW Thermal Slowdown\|HW Power Brake Slowdown' | grep -i 'Active')"
  [ -n "$THROT" ] && hw "Hardware thermal/power-brake slowdown ACTIVE - thermal or power delivery fault"
  TEMP="$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader 2>/dev/null | head -1)"
  if [ -n "$TEMP" ] && [ "$TEMP" -ge 90 ] 2>/dev/null; then
    hw "GPU temperature ${TEMP}C at idle-to-light load - cooling fault"
  fi
  RETIRED="$(nvidia-smi -q 2>/dev/null | grep -iE 'Retired Pages|Remapped Rows' -A4 | grep -iE 'Double|Pending|Failure' | grep -vi 'N/A')"
  [ -n "$RETIRED" ] && info "Memory retirement/remap fields non-empty: $(echo $RETIRED | head -c 200)"
  REPLAY="$(nvidia-smi -q 2>/dev/null | grep -i 'Replay Counter' | head -1 | awk -F: '{print $2}' | tr -d ' ')"
  echo "  PCIe replay counter: ${REPLAY:-N/A}"
  if [ -n "$REPLAY" ] && [ "$REPLAY" -gt 100 ] 2>/dev/null; then
    hw "High PCIe replay counter ($REPLAY) - marginal physical link"
  fi

  echo "-- processes currently holding the GPU --"
  nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv 2>/dev/null
  nvidia-smi 2>/dev/null | sed -n '/Processes:/,$p' | head -12
  ENC_SESS="$(nvidia-smi --query-gpu=encoder.stats.sessionCount --format=csv,noheader 2>/dev/null | head -1)"
  echo "  active encoder sessions: ${ENC_SESS:-N/A}"
  if [ -n "$ENC_SESS" ] && [ "$ENC_SESS" -gt 0 ] 2>/dev/null; then
    info "NVENC sessions already open ($ENC_SESS) - HwDetector can fail on contention while the card is healthy"
  fi
fi

# ===========================================================================
sect "6. XID / KERNEL ERROR HISTORY"
# Xid codes are NVIDIA's own fault taxonomy. Some mean dead hardware, most
# mean an application or driver problem. Do not treat "an Xid appeared" as
# an RMA justification - the code matters.
# ===========================================================================
if have dmesg; then
  DM="$(dmesg -T 2>/dev/null || dmesg 2>/dev/null)"
  NVLINES="$(echo "$DM" | grep -iE 'NVRM|nvidia|Xid|nouveau' | tail -40)"
  if [ -n "$NVLINES" ]; then echo "$NVLINES"; else echo "  (no nvidia lines in the current dmesg buffer)"; fi
  echo "$NVLINES" | grep -qi 'probe.*failed\|RmInitAdapter failed' \
    && hw "NVRM: adapter initialisation / probe FAILED - driver could not bring the GPU up"
  for X in $(echo "$NVLINES" | grep -o 'Xid[^0-9]*[0-9]\+' | grep -o '[0-9]\+$' | sort -un); do
    case "$X" in
      79) hw "Xid 79 - GPU has fallen off the bus (hardware, power, or thermal)";;
      62) hw "Xid 62 - internal micro-controller halt (hardware)";;
      48|63|64|92|94|95) hw "Xid $X - memory/ECC fault (hardware)";;
      69) hw "Xid 69 - graphics engine class error (hardware)";;
      13|31|43|45) info "Xid $X - application-level fault (encoder client crash), NOT an RMA signal on its own";;
      *) info "Xid $X observed - look up the code before drawing a conclusion";;
    esac
  done
  # Persisted journal reaches back past the current boot.
  if have journalctl; then
    echo "-- prior boots (journal) --"
    journalctl -k -b -1 --no-pager 2>/dev/null | grep -iE 'NVRM|Xid' | tail -10 || echo "  (no prior boot journal)"
  fi
else
  echo "dmesg unavailable"
fi

# ===========================================================================
sect "7. FUNCTIONAL ENCODE/DECODE TEST - THE ACTUAL PROOF"
# If these pass, the silicon does the exact job HwDetector says it cannot,
# and the unit must not be RMA'd.
# ===========================================================================
NVENC_TEST="skipped"; NVDEC_TEST="skipped"; CUDA_TEST="skipped"
FFMPEG=""
for C in ffmpeg /opt/pixellot/bin/ffmpeg /usr/local/bin/ffmpeg; do
  if have "$C" || [ -x "$C" ]; then FFMPEG="$C"; break; fi
done
TMPF="$(mktemp -u /tmp/gputriage-XXXX.mp4)"
if [ -n "$FFMPEG" ] && [ "$SMI_OK" -eq 1 ]; then
  echo "using ffmpeg: $FFMPEG"
  echo "-- NVENC encode test (60 frames, 720p) --"
  if "$FFMPEG" -hide_banner -loglevel error -y -f lavfi -i testsrc2=size=1280x720:rate=30 \
       -frames:v 60 -c:v h264_nvenc "$TMPF" 2>&1 | tail -5; then
    if [ -s "$TMPF" ]; then NVENC_TEST="PASS"; echo "  NVENC: PASS"; else NVENC_TEST="FAIL"; echo "  NVENC: FAIL (no output)"; fi
  else
    NVENC_TEST="FAIL"; echo "  NVENC: FAIL"
  fi

  echo "-- NVDEC/CUDA decode test --"
  if [ "$NVENC_TEST" = "PASS" ]; then
    if "$FFMPEG" -hide_banner -loglevel error -hwaccel cuda -hwaccel_output_format cuda \
         -i "$TMPF" -f null - 2>&1 | tail -5; then
      NVDEC_TEST="PASS"; echo "  NVDEC/CUDA: PASS"
    else
      NVDEC_TEST="FAIL"; echo "  NVDEC/CUDA: FAIL"
    fi
  fi
  rm -f "$TMPF" 2>/dev/null
else
  echo "  (skipped: ffmpeg=${FFMPEG:-not found}, nvidia-smi ok=$SMI_OK)"
fi

# CUDA context creation, independent of ffmpeg.
if [ "$SMI_OK" -eq 1 ]; then
  if have nvidia-smi; then
    if nvidia-smi -q -d MEMORY >/dev/null 2>&1 && [ -e /dev/nvidia-uvm ]; then
      CUDA_TEST="LIKELY_OK"
    fi
  fi
  have python3 && python3 - <<'PY' 2>/dev/null
try:
    import ctypes
    cuda = ctypes.CDLL("libcuda.so.1")
    rc = cuda.cuInit(0)
    n = ctypes.c_int()
    if rc == 0:
        cuda.cuDeviceGetCount(ctypes.byref(n))
    print("  libcuda cuInit rc=%d device_count=%d" % (rc, n.value))
except Exception as e:
    print("  libcuda probe failed: %s" % e)
PY
fi

case "$NVENC_TEST" in
  PASS) info "FUNCTIONAL: NVENC encoded successfully on this GPU";;
  FAIL) info "FUNCTIONAL: NVENC failed - see ffmpeg output above for the reason";;
esac
[ "$NVDEC_TEST" = "PASS" ] && info "FUNCTIONAL: CUDA/NVDEC decode succeeded on this GPU"

# ===========================================================================
sect "8. INTEL QSV PATH (the other half of the HwDetector message)"
# ===========================================================================
if [ -d /dev/dri ]; then
  ls -l /dev/dri 2>/dev/null
  if have vainfo; then vainfo 2>&1 | grep -iE 'vainfo:|H264|HEVC' | head -12; fi
else
  echo "  /dev/dri absent - no VAAPI/QSV render node"
  info "No /dev/dri render node - the QSV half of HwDetector cannot work either"
fi

# ===========================================================================
sect "VERDICT"
# ===========================================================================
VERDICT=""; RC=3
if [ "$ENUM_OK" -eq 0 ] && [ "${#HW_EVIDENCE[@]}" -eq 0 ]; then
  # We could not inspect the bus or the driver, so no conclusion is honest.
  VERDICT="INCONCLUSIVE"; RC=3
elif [ "${#HW_EVIDENCE[@]}" -gt 0 ]; then
  VERDICT="HARDWARE_SUSPECT"; RC=2
elif [ "$NVENC_TEST" = "PASS" ] && { [ "$NVDEC_TEST" = "PASS" ] || [ "$NVDEC_TEST" = "skipped" ]; }; then
  VERDICT="NOT_HARDWARE"; RC=0
elif [ "${#SW_EVIDENCE[@]}" -gt 0 ]; then
  VERDICT="SOFTWARE_FAULT"; RC=1
else
  VERDICT="INCONCLUSIVE"; RC=3
fi

echo "$VERDICT"
echo
if [ "${#HW_EVIDENCE[@]}" -gt 0 ]; then
  echo "Hardware evidence:"; for e in "${HW_EVIDENCE[@]}"; do echo "  [HW] $e"; done; echo
fi
if [ "${#SW_EVIDENCE[@]}" -gt 0 ]; then
  echo "Software/config evidence:"; for e in "${SW_EVIDENCE[@]}"; do echo "  [SW] $e"; done; echo
fi
if [ "${#INFO[@]}" -gt 0 ]; then
  echo "Notes:"; for e in "${INFO[@]}"; do echo "  [--] $e"; done; echo
fi

case "$VERDICT" in
  NOT_HARDWARE)     echo "The GPU encoded and decoded on demand. DO NOT RMA. The HwDetector failure is software, timing, or encoder contention.";;
  SOFTWARE_FAULT)   echo "The GPU is present but the driver stack is broken. Fix in place; DO NOT RMA until it is repaired and retested.";;
  HARDWARE_SUSPECT) echo "Physical-layer evidence found. Reseat the card and retest FIRST - reseating clears most of these. RMA only if it survives a reseat.";;
  INCONCLUSIVE)     echo "No decisive evidence either way. Run again as root, with pciutils/nvidia-smi/ffmpeg available, and after reproducing the failure.";;
esac

# --- JSON summary ----------------------------------------------------------
{
  printf '{\n'
  printf '  "schema": "gpu-triage/1",\n'
  printf '  "host": "%s",\n' "$(jesc "$HOST")"
  printf '  "timestamp": "%s",\n' "$(jesc "$TS")"
  printf '  "platform": "linux",\n'
  printf '  "product": "%s",\n' "$(jesc "$PRODUCT")"
  printf '  "distro": "%s",\n' "$(jesc "$DISTRO")"
  printf '  "kernel": "%s",\n' "$(jesc "$KERNEL")"
  printf '  "bios": "%s",\n' "$(jesc "$BIOS_VER ($BIOS_DATE)")"
  printf '  "gpuName": "%s",\n' "$(jesc "$GPU_NAME")"
  printf '  "pciPresent": %s,\n' "$([ "$PCI_PRESENT" -eq 1 ] && echo true || echo false)"
  printf '  "pciSlot": "%s",\n' "$(jesc "$SLOT")"
  printf '  "pciId": "%s",\n' "$(jesc "$DEVID")"
  printf '  "kernelDriver": "%s",\n' "$(jesc "$DRIVER_BOUND")"
  printf '  "driverVersion": "%s",\n' "$(jesc "$RUNNING_DRV")"
  printf '  "nvidiaSmiOk": %s,\n' "$([ "$SMI_OK" -eq 1 ] && echo true || echo false)"
  printf '  "nvencTest": "%s",\n' "$NVENC_TEST"
  printf '  "nvdecTest": "%s",\n' "$NVDEC_TEST"
  printf '  "verdict": "%s",\n' "$VERDICT"
  printf '  "hardwareEvidence": ['
  for i in "${!HW_EVIDENCE[@]}"; do [ "$i" -gt 0 ] && printf ', '; printf '"%s"' "$(jesc "${HW_EVIDENCE[$i]}")"; done
  printf '],\n'
  printf '  "softwareEvidence": ['
  for i in "${!SW_EVIDENCE[@]}"; do [ "$i" -gt 0 ] && printf ', '; printf '"%s"' "$(jesc "${SW_EVIDENCE[$i]}")"; done
  printf '],\n'
  printf '  "notes": ['
  for i in "${!INFO[@]}"; do [ "$i" -gt 0 ] && printf ', '; printf '"%s"' "$(jesc "${INFO[$i]}")"; done
  printf ']\n}\n'
} > "$JSON"

echo
echo "JSON summary : $JSON"
echo "Full log     : $LOG"
exit $RC
