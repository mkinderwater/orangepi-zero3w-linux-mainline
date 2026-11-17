#!/usr/bin/env bash
# Source-only AXP8191 versus AXP318W regulator mapping review.
# Never reads live I2C/PMIC registers or changes voltage.
set -euo pipefail
V="${1:-/root/opi3w-hybrid-build-0.2.7/linux/bsp}"
U="${2:-/root/opi3w-m2-work/axp318w-clean-compile-v1/linux}"
OUT="${3:-/root/opi3w-m2-work/axp8191-axp318w-register-audit-v1.txt}"
VH="$V/drivers/power/include/axp2101.h"
VR="$V/drivers/power/regulator/axp2101-regulator.c"
VM="$V/drivers/power/mfd/axp2101.c"
UR="$U/drivers/regulator/axp20x-regulator.c"
UH="$U/include/linux/mfd/axp20x.h"
UM="$U/drivers/mfd/axp20x.c"
for file in "$VH" "$VR" "$VM" "$UR" "$UH" "$UM"; do
  [[ -f "$file" ]] || { echo "MISSING: $file" >&2; exit 2; }
done
[[ ! -e "$OUT" ]] || { echo "Output already exists: $OUT" >&2; exit 2; }
{
  echo "AXP8191 vs AXP318W source register review (NO hardware I/O)"
  echo "=== SHA256 SOURCES ==="
  sha256sum "$VH" "$VR" "$VM" "$UR" "$UH" "$UM"
  echo "=== VENDOR SWITCH DESCRIPTORS ==="
  sed -n '1345,1363p' "$VR"
  echo "=== VENDOR CLDO5 DESCRIPTORS ==="
  sed -n '1396,1412p' "$VR"
  echo "=== VENDOR IDENTIFIER AND REGISTER DEFINITIONS ==="
  sed -n '970,1035p' "$VH"
  echo "=== VENDOR REGISTER/ENABLE REFERENCES ==="
  grep -nE 'AXP8191_(DCDC_CTL2|CLDO5OUT_VOL|LDO_POWER_ON_OFF_CTL2|CHIP_ID|IC_TYPE)|AXP8191_ID' "$VH" "$VR" "$VM" | head -90 || :
  echo "=== UPSTREAM AXP318 SWITCH AND CLDO5 DEFINITIONS ==="
  grep -nEi -C 5 'AXP318_(SWOUT1|SWOUT2|CLDO5|DCDC_OUTPUT_CONTROL2|LDO_OUTPUT_CONTROL2|IC_TYPE|CHIP_ID)|swout2|cldo5' "$UR" "$UH" "$UM" | head -220 || :
  echo "=== VENDOR PMIC ID MATCHING ==="
  grep -nEi -C 5 'axp8191.*(chip|id|type)|AXP8191_CHIP_ID|AXP8191_IC_TYPE' "$VM" | head -140 || :
  echo "=== OUTCOME ==="
  echo "STATIC SOURCE ONLY. Bit masks, chip ID and rail compatibility require review."
  echo "Never alias x-powers,axp8191 to x-powers,axp318w until proven."
} > "$OUT"
echo "REPORT: $OUT"
