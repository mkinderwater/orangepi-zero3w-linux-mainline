#!/usr/bin/env bash
# Source and runtime-compatible provider inventory for A733 HDMI integration.
# Never infer a missing driver solely from an unmatched vendor compatible.
set -euo pipefail
SRC="${SRC:-/root/opi3w-m2-work/linux-618-hdmi-stage4/linux}"
DTB="${DTB:-/home/ram-b-clock-test/sun60i-a733-orangepi-zero3w-ram-b-26mhz-test.dtb}"
OUT="${OUT:-/root/opi3w-m2-work/linux-618-hdmi-stage4/provider-compat}"
[[ -f "$SRC/Makefile" && -f "$DTB" ]] || { echo "Missing kernel tree or DTB" >&2; exit 1; }
for cmd in grep find dtc sha256sum; do command -v "$cmd" >/dev/null || exit 1; done
mkdir -p "$OUT"
dtc -q -I dtb -O dts -o "$OUT/ram-b.dts" "$DTB"
sha256sum "$DTB" > "$OUT/SHA256SUMS"
{
  echo "=== Active RAM-B clock and provider nodes ==="
  grep -nEi -C 4 'sun60|a733|clock-controller|reset-controller|power-domain|iommu|rtc|ccu|pck' "$OUT/ram-b.dts" | head -220 || :
  echo "=== Provider-compatible strings in A733 source ==="
  grep -RInE 'allwinner,(sun60iw2|sun60i-a733|sunxi).*?(ccu|rtc|iommu|pck)|pck.?600|iommu-v20' \
    "$SRC/drivers/clk" "$SRC/drivers/pmdomain" "$SRC/drivers/iommu" "$SRC/arch/arm64/boot/dts" 2>/dev/null | head -180 || :
  echo "=== A733 clock source files, independent of naming ==="
  find "$SRC/drivers/clk" "$SRC/drivers/pmdomain" "$SRC/drivers/iommu" \
    -type f \( -iname '*a733*' -o -iname '*sun60*' -o -iname '*pck*600*' -o -iname '*sunxi*iommu*' \) -print 2>/dev/null | head -100 || :
  echo "=== Clock bindings for HDMI/DE/TCON ==="
  grep -nEi 'HDMI|TCON|DE_|DPSS|VO_|VID_OUT|MBUS_VO|DCXO' \
    "$SRC/include/dt-bindings/clock/allwinner,sun60i-a733-ccu.h" \
    "$SRC/include/dt-bindings/clock/allwinner,sun60i-a733-r-ccu.h" 2>/dev/null || :
  echo "=== Reset bindings for HDMI/DE/TCON ==="
  grep -nEi 'HDMI|TCON|DE_|DPSS|VO_|VID_OUT' \
    "$SRC/include/dt-bindings/reset/allwinner,sun60i-a733-ccu.h" 2>/dev/null || :
  echo "=== Existing provider configuration ==="
  grep -Ei '^(CONFIG_|# CONFIG_).*(SUNXI|A733|GENPD|PM_DOMAIN|IOMMU|RTC|COMMON_CLK)' \
    "/root/opi3w-m2-work/linux-618-hdmi-stage4/obj/.config" 2>/dev/null | head -120 || :
  echo "NOTE: vendor numeric ID to modern binding mapping requires semantic verification."
} > "$OUT/summary.txt"
cat "$OUT/summary.txt"
echo "Read-only report: $OUT/summary.txt"
