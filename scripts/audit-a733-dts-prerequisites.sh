#!/usr/bin/env bash
# A733 DTS prerequisites, source-only inventory, no image or hardware changes.
set -euo pipefail
K="${1:-/root/opi3w-m2-work/a733-clean-with-axp318w-v1/linux}"
OUT="${2:-/root/opi3w-m2-work/a733-dts-prerequisites-v1.txt}"
[[ -f "$K/Makefile" ]] || { echo "No kernel Makefile: $K" >&2; exit 2; }
[[ ! -e "$OUT" ]] || { echo "Output exists: $OUT" >&2; exit 2; }
mkdir -p "$(dirname "$OUT")"
{
  echo "A733 DTS prerequisites: static inventory"
  echo "Kernel: $K"
  echo "=== A733 PATCHED CLOCK/RESET BINDING FILENAMES ==="
  find "$K/include/dt-bindings/clock" "$K/include/dt-bindings/reset" -maxdepth 1 -type f \
    \( -iname '*a733*' -o -iname '*sun60*' \) -print | sort
  echo "=== ALL FILES WITH A733 SMHC / UART / TWI SYMBOLS ==="
  grep -RlnE 'CLK_(BUS_)?(SMHC0|MMC0)|RST_(BUS_)?SMHC0|CLK_(BUS_)?UART0|CLK_(BUS_)?TWI' \
    "$K/include/dt-bindings/clock" "$K/include/dt-bindings/reset" \
    "$K/drivers/clk/sunxi-ng/ccu-sun60i-a733.c" 2>/dev/null | sort || :
  echo "=== ACTUAL CLOCK AND RESET SYMBOLS ==="
  grep -RnsE '^#define[[:space:]]+[^[:space:]]*(SMHC|MMC|UART|TWI|I2C)[^[:space:]]*[[:space:]]+' \
    "$K/include/dt-bindings/clock" "$K/include/dt-bindings/reset" \
    --include='*a733*' --include='*sun60*' 2>/dev/null || :
  echo "=== A733 CCU SOURCE MATCHES ==="
  grep -nE -C 2 'smhc0|smhc1|mmc0|uart0|twi0|sun60i-a733-ccu' \
    "$K/drivers/clk/sunxi-ng/ccu-sun60i-a733.c" 2>/dev/null | head -170 || :
  echo "=== PRESENT A733 DT SOURCE ==="
  find "$K/arch/arm64/boot/dts/allwinner" -maxdepth 1 -type f \
    \( -iname '*a733*' -o -iname '*sun60*' \) -print | sort
  echo "=== EXISTING A523 DTS REFERENCES ==="
  grep -nE -C 2 'mmc0|mmc@|uart0|i2c0|pinctrl@|ccu@|syscon@' \
    "$K/arch/arm64/boot/dts/allwinner/sun55i-a523.dtsi" 2>/dev/null | head -130 || :
  echo "=== A733 PINCTRL COMPATIBLE STRINGS ==="
  grep -RnsE 'allwinner,sun60i-a733|pinctrl-sun60i-a733' \
    "$K/drivers/pinctrl/sunxi" "$K/drivers/clk/sunxi-ng" \
    --include='*.c' | tail -45 || :
  echo "=== MMC CONTROLLER MATCHES ==="
  grep -nE -C 3 'sun20i-d1-mmc|sun55i-a523-mmc' \
    "$K/drivers/mmc/host/sunxi-mmc.c" | head -75 || :
  echo "=== CONCLUSION ==="
  echo "Static evidence only. No board DTS yet; PMIC chip identity and 1.8V switching remain unproven."
} > "$OUT"
echo "REPORT: $OUT"
