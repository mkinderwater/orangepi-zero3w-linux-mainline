#!/usr/bin/env bash
# Stage vendor A733 DRM HDMI stack in a separate 6.18 source tree.
# First integration compile: no DTB changes, firmware changes or flashing.
set -euo pipefail

BASE="${BASE:-/root/opi3w-m2-work/a733-try9-ramoops-v2/linux}"
VENDOR="${VENDOR:-/root/opi3w-vendor-6698-work/kernel}"
CONFIG="${CONFIG:-/root/opi3w-m2-work/linux-618-full-integration/artifacts/kernel.config}"
OUT="${OUT:-/root/opi3w-m2-work/linux-618-hdmi-stage2}"
JOBS="${JOBS:-4}"

for exe in rsync make aarch64-linux-gnu-gcc sha256sum python3 grep; do
  command -v "$exe" >/dev/null || { echo "Missing: $exe" >&2; exit 1; }
done
for f in "$BASE/Makefile" "$BASE/drivers/gpu/drm/Makefile" "$BASE/drivers/gpu/drm/Kconfig" \
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
rsync -a "$VENDOR/bsp/drivers/drm/" "$SRC/drivers/gpu/drm/sunxi_vendor/"
sha256sum "$VENDOR/bsp/drivers/drm/Kconfig" "$VENDOR/bsp/drivers/drm/Makefile" \
  > "$OUT/vendor-drm-hashes.txt"
python3 - "$SRC" <<'PY'
from pathlib import Path
import sys
src = Path(sys.argv[1])
kf = src / 'drivers/gpu/drm/Kconfig'
mf = src / 'drivers/gpu/drm/Makefile'
kc, mk = kf.read_text(), mf.read_text()
hook_k = 'source "drivers/gpu/drm/sunxi_vendor/Kconfig"'
hook_m = 'obj-$(CONFIG_AW_DRM) += sunxi_vendor/'
# Keep AW_BSP dependency satisfiable only as a minimal integration selector.
# This does not introduce unrelated vendor drivers or claim complete BSP parity.
compat = '''
config AW_BSP
    bool "Allwinner A733 BSP integration hooks"
    depends on ARM64
    default y

'''
vendor_k = src / 'drivers/gpu/drm/sunxi_vendor/Kconfig'
vk = vendor_k.read_text()
# Vendor nested Kconfig references are absolute-to-srctree paths; after
# relocating DRM under drivers/gpu/drm/sunxi_vendor they must be rewritten.
# Rewrite every nested Kconfig's source/rsource path, never source outside
# the copied DRM subtree.
old_prefix = 'bsp/drivers/drm/'
new_prefix = 'drivers/gpu/drm/sunxi_vendor/'
for nested in (src / 'drivers/gpu/drm/sunxi_vendor').rglob('Kconfig*'):
    original = nested.read_text()
    updated = original
    for directive in ('source', 'rsource', 'osource', 'orsource'):
        for quote in ('"', "'"):
            updated = updated.replace(
                directive + ' ' + quote + old_prefix,
                directive + ' ' + quote + new_prefix
            )
    if updated != original:
        nested.write_text(updated)
vk = vendor_k.read_text()
if 'config AW_BSP' not in kc and 'config AW_BSP' not in vk:
    vk = compat + vk
    vendor_k.write_text(vk)
if hook_k not in kc:
    kc += '\n' + hook_k + '\n'
    kf.write_text(kc)
if hook_m not in mk:
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
for required in DRM AW_BSP AW_DRM AW_DRM_DE AW_DRM_TCON AW_DRM_TCON_TV \
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
