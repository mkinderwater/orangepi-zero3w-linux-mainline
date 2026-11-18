#!/usr/bin/env bash
# Inspect the exact built 6.18 DTB/config for UART, PowerVR, DRM and HDMI.
# Read-only, no writes to kernel, card, DTB or hardware.
set -euo pipefail
ROOT="${ROOT:-/root/opi3w-m2-work/linux-618-full-integration}"
DTB="${DTB:-$ROOT/artifacts/sun60i-a733-orangepi-zero3w-26mhz.dtb}"
CONFIG="${CONFIG:-$ROOT/artifacts/kernel.config}"
OUT="${OUT:-$ROOT/uart-hdmi-gpu-audit}"
for c in dtc grep sha256sum; do command -v "$c" >/dev/null || { echo "Missing $c" >&2; exit 1; }; done
[[ -f "$DTB" && -f "$CONFIG" ]] || { echo "Missing DTB or kernel config" >&2; exit 1; }
mkdir -p "$OUT"
dtc -q -I dtb -O dts -o "$OUT/current.dts" "$DTB"
sha256sum "$DTB" "$CONFIG" > "$OUT/SHA256SUMS"
{
 echo '=== Build artifacts ==='
 cat "$OUT/SHA256SUMS"
 echo '=== DRM/display/GPU kernel config ==='
 grep -E '^(CONFIG_|# CONFIG_).*(DRM|POWERVR|IMAGINATION|SUN4I|SUN8I|HDMI|DISPLAY|FB_|FRAMEBUFFER|DMA_SHARED_BUFFER|CMA|VT|SERIAL_8250)' "$CONFIG" || :
 echo '=== UART / GPU / HDMI / display engine / PHY nodes ==='
 grep -Ein -C 7 'gpu@|hdmi@|display-engine|display@|tcon@|mixer@|de@|phy@|dphy|dw-hdmi|sunxi.*hdmi|img-rogue|img,gpu|2500000|chosen \{|aliases \{' "$OUT/current.dts" || :
 echo '=== explicit GPU and DRM source matches (if build source provided) ==='
 if [[ -n "${SRC:-}" && -d "$SRC" ]]; then
   grep -RIlE 'img,img-rogue|allwinner,sun.*hdmi|sun60i.*hdmi' "$SRC/arch/arm64/boot/dts" "$SRC/drivers/gpu/drm" 2>/dev/null | head -80 || :
 fi
} > "$OUT/summary.txt"
cat "$OUT/summary.txt"
echo "Read-only diagnostic complete: $OUT/summary.txt"
