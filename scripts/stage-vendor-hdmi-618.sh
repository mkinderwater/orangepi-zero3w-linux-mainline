#!/usr/bin/env bash
# Stage vendor A733 DRM HDMI stack in a separate 6.18 source tree.
# First integration compile: no DTB changes, firmware changes or flashing.
set -euo pipefail

BASE="${BASE:-/root/opi3w-m2-work/a733-try9-ramoops-v2/linux}"
VENDOR="${VENDOR:-/root/opi3w-vendor-6698-work/kernel}"
CONFIG="${CONFIG:-/root/opi3w-m2-work/linux-618-full-integration/artifacts/kernel.config}"
OUT="${OUT:-/root/opi3w-m2-work/linux-618-hdmi-stage1}"
JOBS="${JOBS:-4}"

for exe in rsync make aarch64-linux-gnu-gcc sha256sum python3 grep; do
  command -v "$exe" >/dev/null || { echo "Missing: $exe" >&2; exit 1; }
done
for f in "$BASE/Makefile" "$BASE/bsp/drivers/Makefile" "$BASE/bsp/drivers/Kconfig" \
         "$VENDOR/bsp/drivers/drm/Makefile" "$VENDOR/bsp/drivers/drm/Kconfig" "$CONFIG"; do
  [[ -f "$f" ]] || { echo "Missing dependency: $f" >&2; exit 1; }
done
[[ "$OUT" != "$BASE" && "$OUT" != "$VENDOR" && "$OUT" != / ]] || exit 1
[[ ! -e "$OUT/linux" ]] || { echo "STOP: existing $OUT/linux; select new OUT" >&2; exit 1; }
mkdir -p "$OUT" "$OUT/artifacts"
rsync -a --exclude='.git' --exclude='*.o' --exclude='*.ko' \
  --exclude='*.cmd' --exclude='vmlinux' --exclude='Image' "$BASE/" "$OUT/linux/"
SRC="$OUT/linux"
# Only vendor DRM implementation, not the entire vendor source/BSP.
rsync -a "$VENDOR/bsp/drivers/drm/" "$SRC/bsp/drivers/drm/"
sha256sum "$VENDOR/bsp/drivers/drm/Kconfig" "$VENDOR/bsp/drivers/drm/Makefile" \
  > "$OUT/vendor-drm-hashes.txt"
python3 - "$SRC" <<'PY'
from pathlib import Path
import sys
src = Path(sys.argv[1])
kf = src / 'bsp/drivers/Kconfig'
mf = src / 'bsp/drivers/Makefile'
kc, mk = kf.read_text(), mf.read_text()
hook_k = 'source "bsp/drivers/drm/Kconfig"'
hook_m = 'obj-$(CONFIG_AW_DRM) += drm/'
if hook_k not in kc:
    # Add a single Kconfig source line, not a random third-party driver.
    kc += '\n' + hook_k + '\n'
    kf.write_text(kc)
if hook_m not in mk:
    # Vendor DRM/Makefile contains the actual sunxidrm object dependencies.
    mk += '\n' + hook_m + '\n'
    mf.write_text(mk)
PY

mkdir -p "$OUT/obj"
cp "$CONFIG" "$OUT/obj/.config"
cfg="$SRC/scripts/config"
for option in DRM DRM_KMS_HELPER DRM_DISPLAY_HELPER DRM_DISPLAY_HDMI_HELPER \
              DRM_DISPLAY_HDCP_HELPER DRM_GEM_DMA_HELPER \
              DRM_FBDEV_EMULATION FRAMEBUFFER_CONSOLE \
              AW_BSP AW_DRM AW_DRM_DE AW_DRM_TCON AW_DRM_TCON_TV \
              AW_DRM_TCON_TOP AW_DRM_HDMI_TX AW_DRM_HDMI20 AW_DRM_PHY; do
  "$cfg" --file "$OUT/obj/.config" -e "$option"
done
# Vendor Kconfig selects changed between 6.6 and 6.18. This is a first build
# attempt, not proof the vendor code is ready to compile.
make -C "$SRC" O="$OUT/obj" ARCH=arm64 \
  CROSS_COMPILE=aarch64-linux-gnu- olddefconfig \
  >"$OUT/configure.log" 2>&1 || {
    tail -100 "$OUT/configure.log"; exit 1;
  }
for required in DRM AW_DRM AW_DRM_DE AW_DRM_TCON AW_DRM_TCON_TV \
                AW_DRM_HDMI_TX AW_DRM_HDMI20; do
  if ! grep -qx "CONFIG_${required}=y" "$OUT/obj/.config"; then
    echo "STOP: CONFIG_${required} not enabled after dependency resolution"
    grep -E "^(CONFIG_|# CONFIG_)(AW_DRM|DRM)" "$OUT/obj/.config" | head -70
    exit 1
  fi
done
echo "Starting vendor HDMI 6.18 compile, output: $OUT/build.log"
if ! make -C "$SRC" O="$OUT/obj" ARCH=arm64 \
  CROSS_COMPILE=aarch64-linux-gnu- -j"$JOBS" Image modules \
  >"$OUT/build.log" 2>&1; then
  echo "Integration compile failed; first diagnostics:"
  grep -n -m 30 -E 'error:|undefined reference|No rule to make target|fatal error:|implicit declaration' \
    "$OUT/build.log" || :
  echo "Last build lines:"
  tail -60 "$OUT/build.log"
  exit 1
fi
cp "$OUT/obj/arch/arm64/boot/Image" "$OUT/artifacts/Image-618-vendor-hdmi"
cp "$OUT/obj/.config" "$OUT/artifacts/kernel.config"
sha256sum "$OUT/artifacts/"* > "$OUT/artifacts.sha256"
echo "Compile succeeded, hardware not tested. No DTB, GPU firmware or SD card was changed."
cat "$OUT/artifacts.sha256"
