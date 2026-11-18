#!/usr/bin/env bash
# Pin down the vendor A733 HDMI pipeline port, without touching either source.
set -euo pipefail
VENDOR="${VENDOR:-/root/opi3w-vendor-6698-work/kernel}"
LINUX="${LINUX:-/root/opi3w-m2-work/a733-try9-ramoops-v2/linux}"
OUT="${OUT:-/root/opi3w-m2-work/linux-618-full-integration/hdmi-port-map}"
[[ -f "$VENDOR/bsp/drivers/drm/Kconfig" ]] || { echo "Vendor BSP DRM Kconfig missing" >&2; exit 1; }
[[ -f "$LINUX/drivers/gpu/drm/Kconfig" ]] || { echo "6.18 DRM Kconfig missing" >&2; exit 1; }
mkdir -p "$OUT"
cp "$VENDOR/bsp/drivers/drm/Kconfig" "$OUT/vendor-drm-Kconfig"
cp "$VENDOR/bsp/drivers/drm/Makefile" "$OUT/vendor-drm-Makefile"
{
  echo "=== Vendor BSP display selected Kconfig definitions/dependencies ==="
  grep -nE -A 16 '^[[:space:]]*(config|menuconfig) AW_DRM($|_DE$|_HDMI20$|_HDMI_TX$|_TCON$|_TCON_TV$|_TCON_TOP$|_PHY$)' "$VENDOR/bsp/drivers/drm/Kconfig" || :
  echo "=== Vendor recursive Makefile entries ==="
  find "$VENDOR/bsp/drivers/drm" -maxdepth 4 -name Makefile -print | sort |
    while IFS= read -r p; do
      echo "--- ${p#"$VENDOR/"}"
      grep -E 'AW_DRM|HDMI|TCON|DE|PHY|sunxi' "$p" | head -45 || :
    done
  echo "=== Board display nodes from real vendor dts (candidate references) ==="
  find "$VENDOR/arch/arm64/boot/dts" -type f \( -name '*zero3w*.dts' -o -name '*sun60iw2*.dtsi' -o -name '*a733*.dtsi' \) 2>/dev/null | sort |
    while IFS= read -r p; do
      echo "--- $p"
      grep -Ein -C 3 'hdmi|display.engine|display-engine|tcon|gpu|phy|de35|de352' "$p" | head -100 || :
    done
  echo "=== Existing Linux 6.18 display source ==="
  find "$LINUX/drivers/gpu/drm/imagination" "$LINUX/drivers/gpu/drm/sun4i" -maxdepth 1 -type f 2>/dev/null | sort
  echo "=== Existing Linux 6.18 selected configs ==="
  grep -E '^(CONFIG_|# CONFIG_).*(DRM|POWERVR|SUN4I|FRAMEBUFFER_CONSOLE|FBDEV)' \
    /root/opi3w-m2-work/linux-618-full-integration/artifacts/kernel.config 2>/dev/null || :
  echo "NO PATCHES APPLIED. Vendor source remains unchanged."
} > "$OUT/summary.txt"
sha256sum "$OUT/vendor-drm-Kconfig" "$OUT/vendor-drm-Makefile" > "$OUT/source-hashes.txt"
echo "Created $OUT/summary.txt"
cat "$OUT/summary.txt"
