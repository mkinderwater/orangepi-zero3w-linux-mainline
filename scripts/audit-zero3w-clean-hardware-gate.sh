#!/usr/bin/env bash
# Read-only A733 minimal-kernel hardware support inventory.
# Exit 4 until required platform support is verified. No BSP inheritance.
set -euo pipefail
SRC="${1:-/root/opi3w-hybrid-sources-0.1.0/linux}"
CFG="${2:-/root/opi3w-clean-618-config-v3/.config}"
if [[ ! -d "$SRC/drivers" || ! -f "$CFG" ]]; then
  echo "Missing Linux source or .config" >&2; exit 2
fi

option() {
  local key="$1"
  if grep -q "^CONFIG_${key}=y$" "$CFG"; then printf 'y'
  elif grep -q "^CONFIG_${key}=m$" "$CFG"; then printf 'm'
  elif grep -q "^# CONFIG_${key} is not set$" "$CFG"; then printf 'n'
  else printf 'ABSENT'; fi
}
matches() {
  local pat="$1"; shift
  grep -RIlE --include='*.c' --include='*.h' "$pat" "$@" 2>/dev/null || :
}
printf '=== CLEAN KCONFIG ===\n'
for key in ARM64 ARCH_SUNXI SUNXI_CCU SERIAL_8250 PINCTRL MMC MMC_BLOCK MMC_SUNXI REGULATOR EXT4_FS BLK_DEV_INITRD; do
  printf '%-23s %s\n' "$key" "$(option "$key")"
done
echo
echo '=== A733 DRIVER MATCHES (source references, NOT proof of functionality) ==='
for item in \
  'CCU|sun60i-a733|sun60iw2|drivers/clk' \
  'PINCTRL|sun60i-a733|sun60iw2|drivers/pinctrl' \
  'MMC|sun60i-a733|sun60iw2|drivers/mmc' \
  'PMIC|axp8191|axp515|drivers/mfd' \
  'REGULATORS|axp8191|axp515|drivers/regulator' \
  'UART|sun60i-a733|sun60iw2|drivers/tty/serial'; do
  IFS='|' read -r label a b directory <<< "$item"
  printf '\n%s: ' "$label"
  found="$(matches "$a|$b" "$SRC/$directory")"
  if [[ -n "$found" ]]; then
    printf 'SOURCE REFERENCES FOUND (review binding and Kconfig)\n%s\n' "$found"
  else
    echo 'NO A733 SOURCE REFERENCES'
  fi
done
echo
echo '=== ACTUAL UPSTREAM MMC MATCH TABLE ==='
if [[ -f "$SRC/drivers/mmc/host/sunxi-mmc.c" ]]; then
  sed -n '/static const struct of_device_id sunxi_mmc_of_match\[\]/,/MODULE_DEVICE_TABLE(of, sunxi_mmc_of_match)/p' "$SRC/drivers/mmc/host/sunxi-mmc.c"
fi
echo
echo '=== BOARD DTS FILES IN PINNED UPSTREAM ==='
find "$SRC/arch/arm64/boot/dts" -type f \( -iname '*a733*' -o -iname '*zero3w*' \) -print
echo
echo '=== GATE ==='
echo 'A generic SUNXI_CCU/MMC_SUNXI selection does not prove A733 compatibility.'
echo 'BLOCKED: missing hardware-proven CCU, pinctrl, MMC, PMIC and board DTS.'
echo 'No files changed. No build or flash performed.'
exit 4
