#!/usr/bin/env bash
# Read-only physical-boot evidence collector, on Orange Pi only.
# Never adjusts CPU clocks, PMIC voltages or partitions.
set -euo pipefail
LABEL="${1:-}"
case "$LABEL" in stock|control|identity) ;; *) echo "Usage: bash capture-on-board.sh stock|control|identity" >&2; exit 2;; esac
OUT="${OUT:-$HOME/opi3w-hw-$LABEL}"
[[ ! -e "$OUT" ]] || { echo "STOP: output exists. Choose a new OUT to preserve evidence" >&2; exit 3; }
mkdir -p "$OUT"
capture() { local file="$1"; shift; { "$@" || true; } > "$OUT/$file" 2>&1; }
capture uname.txt uname -a
capture os-release.txt cat /etc/os-release
capture cmdline.txt cat /proc/cmdline
capture mount.txt findmnt -o SOURCE,TARGET,FSTYPE,OPTIONS
capture memory.txt cat /proc/meminfo
capture partitions.txt lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS
capture devices.txt sh -c 'find /sys/bus/i2c/devices/ -maxdepth 1 -type l -printf "%f\n" 2>/dev/null | sort'
capture cpu-frequency.txt sh -c 'for f in /sys/devices/system/cpu/cpufreq/policy*/scaling_*_freq; do [ ! -f "$f" ] || { printf "%s " "$f"; cat "$f"; }; done'
capture wifi-device.txt sh -c 'for d in /sys/class/net/wlan*; do [ ! -e "$d" ] || printf "%s\n" "$d"; done'
capture drm-status.txt sh -c 'for f in /sys/class/drm/card*-*/status; do [ ! -f "$f" ] || { printf "%s " "$f"; cat "$f"; }; done'
capture hdmi-connector.txt sh -c 'for f in /sys/class/drm/card*-*/enabled; do [ ! -f "$f" ] || { printf "%s " "$f"; cat "$f"; }; done'
capture uptime.txt cat /proc/uptime
capture dmesg.txt dmesg
capture fdt-status.txt sh -c 'test -r /sys/firmware/fdt && echo PRESENT || echo NOT_READABLE'
if [[ -r /sys/firmware/fdt ]]; then cp /sys/firmware/fdt "$OUT/running.dtb"; fi
if [[ -r /sys/kernel/debug/clk/clk_summary ]]; then
  cp /sys/kernel/debug/clk/clk_summary "$OUT/clk-summary.txt"
else
  echo "NOT_READABLE_OR_NOT_MOUNTED" > "$OUT/clk-summary.txt"
fi
{
  echo "LABEL=$LABEL"
  echo "CAPTURE_ONLY_NOT_A_BOOT_PASS"
  echo "IMAGE_OR_MEDIA_SHA256=MUST_RECORD_SEPARATELY"
  echo "HDMI_LINUX_CONSOLE_OBSERVED=OPERATOR_MUST_RECORD"
  echo "ONBOARD_WIFI_OBSERVED=OPERATOR_MUST_RECORD"
  echo "USB_ETHERNET_OBSERVED=OPERATOR_MUST_RECORD"
  echo "REBOOT_AND_SHUTDOWN=OPERATOR_MUST_RECORD"
  echo "POWER_AND_PMIC_REGULATOR_VALIDATION=NOT_MEASURED"
} > "$OUT/operator-findings.txt"
(
  cd "$OUT"
  find . -maxdepth 1 -type f ! -name SHA256SUMS -print0 |
  sort -z | xargs -0 -r sha256sum > SHA256SUMS
)
echo "HW_EVIDENCE_CAPTURED_NOT_REVIEWED: $OUT"
echo "Review dmesg, cmdline and running DTB for sensitive identifiers before sharing."
