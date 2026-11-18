#!/usr/bin/env bash
# Restore Linux 6.18 DRM client library required by vendor fbdev driver.
# Stage4 object configuration only; no source/boot firmware changes.
set -euo pipefail
ROOT="${ROOT:-/root/opi3w-m2-work/linux-618-hdmi-stage4}"
SRC="$ROOT/linux"
CONFIG="$ROOT/obj/.config"
[[ -f "$SRC/drivers/gpu/drm/clients/Kconfig" && -f "$CONFIG" ]] || {
  echo "STOP: missing Stage4 DRM client Kconfig or configuration" >&2; exit 1;
}
for symbol in DRM DRM_CLIENT DRM_CLIENT_LIB DRM_CLIENT_SELECTION DRM_FBDEV_EMULATION; do
  grep -Eq "(^CONFIG_${symbol}=|^# CONFIG_${symbol} is not set)" "$CONFIG" || {
    echo "NOTE: ${symbol} not represented in prior config"
  }
done
cp "$CONFIG" "$ROOT/obj/.config.pre-drm-client-618"
CFG="$SRC/scripts/config"
"$CFG" --file "$CONFIG" -e DRM_CLIENT_SELECTION -e DRM_FBDEV_EMULATION
make -C "$SRC" O="$ROOT/obj" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- olddefconfig  >"$ROOT/config-drm-client-618.log" 2>&1 || {
   tail -80 "$ROOT/config-drm-client-618.log"; exit 1;
 }
for symbol in DRM DRM_CLIENT_LIB DRM_CLIENT_SELECTION DRM_FBDEV_EMULATION; do
  grep -qx "CONFIG_${symbol}=y" "$CONFIG" || {
    echo "STOP: CONFIG_${symbol} not built-in after dependency resolution" >&2
    grep -E '^(# )?CONFIG_DRM_(CLIENT|FBDEV)' "$CONFIG" || :
    exit 1
  }
done
echo "=== Resolved DRM client configurations ==="
grep -E '^CONFIG_(DRM_CLIENT|DRM_FBDEV_EMULATION)=' "$CONFIG"
LOG="$ROOT/build-drm-client-618.log"
echo "Incremental compile/link: $LOG"
if ! make -C "$SRC" O="$ROOT/obj" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu-  -j"${JOBS:-4}" Image modules >"$LOG" 2>&1; then
 echo "First compiler/linker failures:"
 grep -n -m 40 -E 'fatal error:|error:|undefined reference|No rule to make target' "$LOG" || :
 tail -30 "$LOG"
 exit 1
fi
mkdir -p "$ROOT/artifacts"
cp "$ROOT/obj/arch/arm64/boot/Image" "$ROOT/artifacts/Image-618-vendor-hdmi"
cp "$CONFIG" "$ROOT/artifacts/kernel.config"
sha256sum "$ROOT/artifacts/"* > "$ROOT/artifacts.sha256"
cat "$ROOT/artifacts.sha256"
echo "Compiled, not yet hardware validated."
