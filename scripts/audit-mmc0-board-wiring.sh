#!/usr/bin/env bash
# Read-only, fails-closed MMC0 board wiring audit. Does not alter any DTB.
set -euo pipefail
DTB="${DTB:-/root/opi3w-m2-work/linux-618-full-integration/artifacts/sun60i-a733-orangepi-zero3w-26mhz-mmc-150mhz.dtb}"
VENDOR_DTB="${VENDOR_DTB:-}" # optional known-good original Zero 3W board DTB
OUT="${OUT:-/root/opi3w-m2-work/linux-618-full-integration/mmc0-audit}"
for cmd in dtc fdtget sha256sum grep sed awk find; do
  command -v "$cmd" >/dev/null || { echo "Missing $cmd" >&2; exit 1; }
done
[[ -f "$DTB" ]] || { echo "Missing $DTB" >&2; exit 1; }
mkdir -p "$OUT"
sha256sum "$DTB" > "$OUT/input-dtb.sha256"
dtc -q -I dtb -O dts -o "$OUT/current.dts" "$DTB"
if [[ -n "$VENDOR_DTB" ]]; then
  [[ -f "$VENDOR_DTB" ]] || { echo "Vendor DTB missing: $VENDOR_DTB" >&2; exit 1; }
  sha256sum "$VENDOR_DTB" > "$OUT/vendor-dtb.sha256"
  dtc -q -I dtb -O dts -o "$OUT/vendor.dts" "$VENDOR_DTB"
fi
{
 echo "=== oscillator ==="
 fdtget -t u "$DTB" /osc-clk clock-frequency || :
 echo "=== mmc0 ==="
 for prop in compatible status max-frequency bus-width cd-gpios no-sdio no-mmc    pinctrl-0 pinctrl-names clocks clock-names resets reset-names    vmmc-supply vqmmc-supply vqmmc33sw-supply vqmmc18sw-supply; do
   printf '%-24s : ' "$prop"
   if [[ "$prop" == no-sdio || "$prop" == no-mmc ]]; then
     if fdtget "$DTB" /soc/mmc@4020000 "$prop" >/dev/null 2>&1; then echo present; else echo absent; fi
   else fdtget "$DTB" /soc/mmc@4020000 "$prop" 2>/dev/null || echo absent; fi
 done
 echo "=== firmware PMIC/regulators/pinctrl references ==="
 grep -nEi -C 4 'axp8191|dc1sw2|cldo5|regulator-name|sdmmc|mmc@|pins = "PF|gpio.*PF6|card.detect' "$OUT/current.dts" || :
 if [[ -f "$OUT/vendor.dts" ]]; then
   echo "=== vendor reference (NOT authoritative until board variant confirmed) ==="
   grep -nEi -C 5 'axp8191|dc1sw2|cldo5|regulator-name|sdmmc|mmc@|pins = "PF|gpio.*PF6|card.detect' "$OUT/vendor.dts" || :
 fi
} > "$OUT/summary.txt"
echo "Audit written: $OUT/summary.txt"
cat "$OUT/summary.txt"
echo "READ ONLY. No MMC node enabled and no card power/clock altered."
