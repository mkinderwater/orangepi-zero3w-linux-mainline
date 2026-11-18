#!/usr/bin/env bash
# Build isolated stage4 Linux 6.18 with A733 PCK-600 provider enabled.
set -euo pipefail
ROOT="${ROOT:-/root/opi3w-m2-work/linux-618-hdmi-stage4}"
SRC="$ROOT/linux"
OBJ="$ROOT/obj"
ART="$ROOT/artifacts"
[[ -f "$SRC/drivers/pmdomain/sunxi/sun55i-pck600.c" ]] || exit 1
grep -q 'sun60i_a733_pck600_desc' "$SRC/drivers/pmdomain/sunxi/sun55i-pck600.c" || {
  echo "STOP: A733 PCK descriptor not staged" >&2; exit 1;
}
[[ -f "$OBJ/.config" ]] || { echo "Missing .config" >&2; exit 1; }
cp "$OBJ/.config" "$ROOT/obj/.config.pre-pck600-618"
"$SRC/scripts/config" --file "$OBJ/.config" -e SUN55I_PCK600
make -C "$SRC" O="$OBJ" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- olddefconfig \
  >"$ROOT/config-a733-pck600-618.log" 2>&1 || {
    tail -50 "$ROOT/config-a733-pck600-618.log"; exit 1;
  }
grep -qx 'CONFIG_SUN55I_PCK600=y' "$OBJ/.config" || {
  echo "STOP: PCK600 cannot be built in" >&2; exit 1;
}
LOG="$ROOT/build-a733-pck600-618.log"
if ! make -C "$SRC" O="$OBJ" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- \
  -j"${JOBS:-4}" Image modules >"$LOG" 2>&1; then
  grep -n -m 35 -E 'fatal error:|error:|undefined reference|No rule to make target' "$LOG" || :
  tail -25 "$LOG"
  exit 1
fi
mkdir -p "$ART"
cp "$OBJ/arch/arm64/boot/Image" "$ART/Image-618-vendor-hdmi-pck600"
cp "$OBJ/.config" "$ART/kernel-pck600.config"
sha256sum "$ART/Image-618-vendor-hdmi-pck600" "$ART/kernel-pck600.config"
echo "Compiled, PCK-600 is untested on hardware. No boot DTB staged."
