#!/usr/bin/env bash
# Compare A733 HDMI clock/reset implementation at source level, read-only.
set -euo pipefail
VENDOR="${VENDOR:-/root/opi3w-vendor-6698-work/kernel}"
LINUX="${LINUX:-/root/opi3w-m2-work/linux-618-hdmi-stage4/linux}"
OUT="${OUT:-/root/opi3w-m2-work/linux-618-hdmi-stage4/register-equivalence}"
[[ -f "$LINUX/drivers/clk/sunxi-ng/ccu-sun60i-a733.c" ]] || { echo "Missing 6.18 A733 CCU" >&2; exit 1; }
[[ -d "$VENDOR/bsp/drivers/clk" ]] || { echo "Missing vendor clock driver tree" >&2; exit 1; }
mkdir -p "$OUT"
{
  echo "=== New A733 clock implementation, register context ==="
  grep -nEi -B 8 -A 12 'hdmi|tcon|dpss|vid_out|pll_de|mbus_vo' \
    "$LINUX/drivers/clk/sunxi-ng/ccu-sun60i-a733.c" | head -540 || :
  echo "=== Vendor clock driver source filenames ==="
  find "$VENDOR/bsp/drivers/clk" -type f \( -name '*.c' -o -name '*.h' \) \
    | grep -Ei 'sun60|a733|ccu' | head -90 || :
  echo "=== Vendor matching clock/register definitions ==="
  grep -RInEi -B 3 -A 7 'CLK_HDMI_REF|CLK_HDMI_CEC_32K|CLK_TCONTV0|CLK_DPSS_TOP0|CLK_VID_OUT0_AHB_GATE|CLK_DE_AHB_GATE|CLK_BUS_HDMI|RST_BUS_HDMI' \
    "$VENDOR/bsp/drivers/clk" | head -450 || :
  echo "=== Vendor binding symbols ==="
  grep -nEi 'HDMI|TCON|DPSS|VID_OUT|DE_AHB' \
    "$VENDOR/bsp/include/dt-bindings/clock/sun60iw2-ccu.h" \
    "$VENDOR/bsp/include/dt-bindings/reset/sun60iw2-ccu.h" || :
  echo "=== Modern binding symbols ==="
  grep -nEi 'HDMI|TCON|DPSS|VID_OUT|DE_' \
    "$LINUX/include/dt-bindings/clock/allwinner,sun60i-a733-ccu.h" \
    "$LINUX/include/dt-bindings/reset/allwinner,sun60i-a733-ccu.h" || :
  echo "NO register mapping is presumed solely from a matching name."
} > "$OUT/summary.txt" 2>&1
cat "$OUT/summary.txt"
echo "Written $OUT/summary.txt"
