#!/usr/bin/env bash
# Read-only A733 HDMI clock/reset and power-domain mapping evidence.
# Never infer equivalent hardware from equal numeric indices.
set -euo pipefail
SRC="${SRC:-/root/opi3w-m2-work/linux-618-hdmi-stage4/linux}"
VENDOR="${VENDOR:-/root/opi3w-vendor-6698-work/kernel}"
OUT="${OUT:-/root/opi3w-m2-work/linux-618-hdmi-stage4/hdmi-clock-power-map}"
CCU="$SRC/include/dt-bindings/clock/allwinner,sun60i-a733-ccu.h"
RST="$SRC/include/dt-bindings/reset/allwinner,sun60i-a733-ccu.h"
PCK="$SRC/drivers/pmdomain/sunxi/sun55i-pck600.c"
for file in "$CCU" "$RST" "$PCK" "$SRC/drivers/clk/sunxi-ng/ccu-sun60i-a733.c"; do
  [[ -f "$file" ]] || { echo "Missing $file" >&2; exit 1; }
done
mkdir -p "$OUT"
{
  echo "=== Linux 6.18 A733 CCU display/HDMI clock names and values ==="
  grep -nEi '^#define[[:space:]]+CLK_.*(HDMI|TCON|DE_|DPSS|MBUS_VO|VID_OUT)' "$CCU" || :
  echo "=== Linux 6.18 A733 reset names and values ==="
  grep -nEi '^#define[[:space:]]+RST_.*(HDMI|TCON|DE_|DPSS|VID_OUT)' "$RST" || :
  echo "=== Source-defined clock/reset implementation references ==="
  grep -nEi 'CLK_.*(HDMI|TCON|DE_|DPSS|MBUS_VO|VID_OUT)|RST_.*(HDMI|TCON|DE_|DPSS)' \
    "$SRC/drivers/clk/sunxi-ng/ccu-sun60i-a733.c" | head -160 || :
  echo "=== Current A523 PCK-600 domain description and match ==="
  sed -n '188,233p' "$PCK"
  echo "=== Vendor A733 power domains and provider source references ==="
  grep -RInE -m 8 'sun60iw2-pck-600|PD_DE|PD_VO|PD_GPU|PD_HDMI|PD_TCON|PD_DPSS' \
    "$VENDOR/include/dt-bindings/power" "$VENDOR/arch/arm64/boot/dts/allwinner" \
    "$VENDOR/bsp/drivers" 2>/dev/null | head -120 || :
  echo "=== Kernel configuration ==="
  grep -E '^(CONFIG_|# CONFIG_)(IOMMU_SUPPORT|SUN55I_PCK600|PM_GENERIC_DOMAINS|SUN60I_A733_CCU|SUN60I_A733_R_CCU|DRM_POWERVR)' \
    /root/opi3w-m2-work/linux-618-hdmi-stage4/obj/.config || :
  echo "=== Original vendor display clock/reset bindings ==="
  find "$VENDOR" -path '*dt-bindings*' -type f \( -iname '*sun60iw2*ccu*.h' -o -iname '*sun60iw2*reset*.h' \) \
    -print 2>/dev/null | head -25 || :
} > "$OUT/summary.txt"
cat "$OUT/summary.txt"
echo "Read-only report: $OUT/summary.txt"
