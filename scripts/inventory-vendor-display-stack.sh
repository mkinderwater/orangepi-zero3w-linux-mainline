#!/usr/bin/env bash
# Identify actual vendor A733 display/HDMI/GPU source and Kconfig dependencies.
# Read-only: no changes to either kernel source, artifacts, or hardware.
set -euo pipefail
VENDOR="${VENDOR:-/root/opi3w-vendor-6698-work/kernel}"
MAINLINE="${MAINLINE:-/root/opi3w-m2-work/a733-try9-ramoops-v2/linux}"
VCONFIG="${VCONFIG:-/root/opi3w-vendor-6698-work/obj-control/.config}"
MCONFIG="${MCONFIG:-/root/opi3w-m2-work/linux-618-full-integration/artifacts/kernel.config}"
OUT="${OUT:-/root/opi3w-m2-work/linux-618-full-integration/vendor-display-inventory}"
for dir in "$VENDOR" "$MAINLINE"; do
  [[ -f "$dir/Makefile" ]] || { echo "Missing kernel source: $dir" >&2; exit 1; }
done
for config in "$VCONFIG" "$MCONFIG"; do
  [[ -f "$config" ]] || { echo "Missing kernel config: $config" >&2; exit 1; }
done
mkdir -p "$OUT"
{
  echo "Vendor: $VENDOR"
  echo "6.18: $MAINLINE"
  echo "=== Vendor display DRM HDMI GPU Kconfig selection ==="
  grep -E '^CONFIG_(AW_DRM|AW_FB_CONSOLE|DRM|FRAMEBUFFER_CONSOLE|AW_GPU|GPU|PVR|IMG|AW_DISP|G2D)' "$VCONFIG" || :
  echo "=== Current 6.18 DRM Kconfig selection ==="
  grep -E '^(# )?CONFIG_(DRM|DRM_POWERVR|DRM_SUN4I|FB|FRAMEBUFFER_CONSOLE|VT|VGA_CONSOLE|SYNC_FILE|DMA_SHARED_BUFFER)' "$MCONFIG" || :
  echo "=== Vendor driver directories ==="
  find "$VENDOR/bsp/drivers" "$VENDOR/drivers/gpu" -maxdepth 5 -type d 2>/dev/null |
    grep -Ei '/(drm|display|disp|hdmi|gpu|rgx|tcon|pvr|phy)(/|$)' | head -100 || :
  echo "=== Relevant vendor Kconfig entries ==="
  grep -RlE '^config (AW_DRM|AW_DRM_DE|AW_DRM_HDMI20|AW_DRM_HDMI_TX|AW_DRM_TCON|AW_DRM_PHY|AW_FB_CONSOLE)' \
    "$VENDOR/bsp" "$VENDOR/drivers/gpu" 2>/dev/null | head -80 || :
  echo "=== Vendor A733 HDMI/DRM compatible strings ==="
  grep -RIEh 'compatible[[:space:]]*=[[:space:]]*"[^"]*(hdmi|display|tcon|gpu)' \
    "$VENDOR/arch/arm64/boot/dts" "$VENDOR/bsp" 2>/dev/null | sort -u | head -80 || :
  echo "=== 6.18 display/gpu existing source ==="
  find "$MAINLINE/drivers/gpu/drm" -maxdepth 3 -type d 2>/dev/null |
    grep -Ei 'imagination|sun4i|bridge' | head -35 || :
  echo "=== 6.18 display source compile hooks ==="
  grep -RInE '(AW_DRM_HDMI20|AW_DRM_DE|CONFIG_AW_DRM)' "$MAINLINE/bsp" "$MAINLINE/drivers/gpu" 2>/dev/null | head -50 || :
  echo "NOTE: vendor DRM HDMI scanout and PVR GPU are separate dependencies."
  echo "NOTE: a Kconfig symbol alone does not establish feature parity."
} > "$OUT/summary.txt" 2>&1
cat "$OUT/summary.txt"
echo "READ-ONLY inventory: $OUT/summary.txt"
