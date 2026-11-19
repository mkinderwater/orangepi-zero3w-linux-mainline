#!/usr/bin/env bash
# Read-only: check whether boot-proven DTB can bind compiled vendor DRM HDMI.
set -euo pipefail
DTB="${DTB:-/home/ram-b-clock-test/sun60i-a733-orangepi-zero3w-ram-b-26mhz-test.dtb}"
VENDOR="${VENDOR:-/root/opi3w-vendor-6698-work/kernel}"
OUT="${OUT:-/root/opi3w-m2-work/linux-618-hdmi-stage4/hdmi-dtb-readiness}"
[[ -f "$DTB" && -d "$VENDOR" ]] || { echo "Missing verified DTB or vendor kernel" >&2; exit 1; }
for cmd in dtc fdtget grep find sha256sum; do
  command -v "$cmd" >/dev/null || { echo "Missing $cmd" >&2; exit 1; }
done
mkdir -p "$OUT"
dtc -q -I dtb -O dts -o "$OUT/ram-b.dts" "$DTB"
sha256sum "$DTB" > "$OUT/ram-b.dtb.sha256"
{
 echo "=== Boot-proven oscillator ==="
 fdtget -t u "$DTB" /osc-clk clock-frequency || :
 echo "=== Current RAM-B display/gpu compatibles, clock and status nodes ==="
 grep -nEi -C 5 'sunxi-drm|display-engine|hdmi|tcon|gpu@|img,gpu|clock-frequency|power-domain' "$OUT/ram-b.dts" || :
 echo "=== Candidate original Zero3W vendor DTS nodes ==="
 find "$VENDOR/arch/arm64/boot/dts" -type f \( -iname '*zero3w*.dts' -o -iname '*zero3w*.dtsi' -o -iname '*sun60iw2*.dtsi' \) -print 2>/dev/null | sort || :
 echo "=== Candidate vendor display graph definitions ==="
 grep -RInE -m 8 'allwinner,sunxi-drm|allwinner,display-engine-v35|allwinner,sunxi-hdmi|allwinner,tcon-tv|allwinner,tcon-top' \
   "$VENDOR/arch/arm64/boot/dts" 2>/dev/null | head -100 || :
 echo "=== Current kernel DRM/GPU target ==="
 grep -E '^(CONFIG_(DRM|AW_DRM|AW_DRM_HDMI_TX|AW_DRM_HDMI20|AW_DRM_TCON|DRM_POWERVR|FRAMEBUFFER_CONSOLE)=|# CONFIG_DRM_POWERVR)' \
   /root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/kernel.config 2>/dev/null || :
 echo "NOTE: no DTB edits or boot staging performed."
} > "$OUT/summary.txt"
cat "$OUT/summary.txt"
