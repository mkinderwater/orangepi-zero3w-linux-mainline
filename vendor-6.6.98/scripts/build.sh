#!/usr/bin/env bash
set -euo pipefail

# Builds only from the exact pinned vendor source, without touching images or SD cards.
PIN=2ac08e8c7cdc28abbdc5c9a9dd812f887ae9c79f
WORK_ROOT="${WORK_ROOT:-/root/opi3w-vendor-6698-work}"
RESULTS_DIR="${RESULTS_DIR:-/mnt/c/Users/mkinderwater/Downloads/opi3w-vendor-6698-results}"
SRC="$WORK_ROOT/kernel"
DTS_REL=arch/arm64/boot/dts/allwinner/sun60i-a733-orangepi-zero3w.dts
DTB_REL=arch/arm64/boot/dts/allwinner/sun60i-a733-orangepi-zero3w.dtb
OLD='compatible = "xunlong,orangepi-4-pro", "arm,sun60iw2p1";'
NEW='compatible = "xunlong,orangepi-zero3w", "arm,sun60iw2p1";'

usage() { echo "Usage: bash vendor-6.6.98/scripts/build.sh control|identity" >&2; exit 2; }
[[ $# -eq 1 ]] || usage
case "$1" in control|identity) MODE="$1";; *) usage;; esac
for cmd in git python3 make sha256sum aarch64-linux-gnu-gcc; do
  command -v "$cmd" >/dev/null || { echo "STOP: missing $cmd" >&2; exit 2; }
done
[[ -d "$SRC/.git" || -f "$SRC/.git" ]] || { echo 'STOP: first run scripts/prepare.sh' >&2; exit 3; }
[[ "$(git -C "$SRC" rev-parse HEAD)" == "$PIN" ]] || { echo 'STOP: kernel commit differs' >&2; exit 3; }
[[ -z "$(git -C "$SRC" status --porcelain)" ]] || { echo 'STOP: pinned source checkout modified' >&2; exit 3; }
[[ -f "$WORK_ROOT/vendor-a733.config" ]] || { echo 'STOP: missing pinned vendor config' >&2; exit 3; }
mkdir -p "$RESULTS_DIR"
TREE="$WORK_ROOT/tree-$MODE"
OBJ="$WORK_ROOT/obj-$MODE"

if [[ ! -e "$TREE" ]]; then
  git -C "$SRC" worktree add --detach "$TREE" "$PIN"
fi
[[ "$(git -C "$TREE" rev-parse HEAD)" == "$PIN" ]] || { echo 'STOP: unexpected worktree revision' >&2; exit 3; }
python3 - "$TREE/$DTS_REL" "$MODE" <<'PY'
import sys
from pathlib import Path
path,mode=Path(sys.argv[1]),sys.argv[2]
s=path.read_text()
old='compatible = "xunlong,orangepi-4-pro", "arm,sun60iw2p1";'
new='compatible = "xunlong,orangepi-zero3w", "arm,sun60iw2p1";'
if mode=='control':
    assert s.count(old)==1 and new not in s, 'STOP: control DTS not the original vendor source'
else:
    if s.count(old)==1 and new not in s:
        path.write_text(s.replace(old,new,1))
    elif s.count(new)!=1 or old in s:
        raise SystemExit('STOP: identity DTS unexpectedly changed')
print('DT_SOURCE_VALIDATED:'+mode)
PY
if [[ "$MODE" == control ]]; then
  [[ -z "$(git -C "$TREE" status --porcelain)" ]] || { echo 'STOP: control tree dirty' >&2; exit 3; }
else
  python3 - "$TREE" "$DTS_REL" <<'PY'
import subprocess,sys
root,path=sys.argv[1:]
changed=subprocess.check_output(['git','-C',root,'diff','--name-only'],text=True).splitlines()
assert changed==[path],f'STOP: unexpected changes: {changed}'
diff=subprocess.check_output(['git','-C',root,'diff','--',path],text=True)
assert diff.count('-	compatible = "xunlong,orangepi-4-pro", "arm,sun60iw2p1";')==1
assert diff.count('+	compatible = "xunlong,orangepi-zero3w", "arm,sun60iw2p1";')==1
print('ONE_PROPERTY_DTS_CHANGE_VERIFIED')
PY
fi
mkdir -p "$OBJ"
if [[ ! -f "$OBJ/.config" ]]; then
  cp "$WORK_ROOT/vendor-a733.config" "$OBJ/.config"
fi
make -C "$TREE" O="$OBJ" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- olddefconfig
python3 - "$OBJ/.config" <<'PY'
from pathlib import Path
import sys
cfg=Path(sys.argv[1]).read_text()
needed=['ARCH_SUN60IW2P1','AW_MMC','AW_TWI','AW_MFD_AXP2101','AW_MFD_AXP2101_I2C','AW_REGULATOR_AXP2101','AW_UART_NG']
bad=[k for k in needed if f'CONFIG_{k}=y' not in cfg.splitlines()]
assert not bad, f'STOP: required Kconfig differs: {bad}'
PY
JOBS="${JOBS:-$(nproc)}"
[[ "$JOBS" =~ ^[1-9][0-9]*$ ]] || { echo 'STOP: JOBS must be positive integer' >&2; exit 2; }
make -C "$TREE" O="$OBJ" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- -j"$JOBS" Image dtbs modules

IMAGE="$OBJ/arch/arm64/boot/Image"
DTB="$OBJ/$DTB_REL"
[[ -s "$IMAGE" && -s "$DTB" ]] || { echo 'STOP: missing Image/DTB' >&2; exit 4; }

# Disallow accidental cross-mode mixing. Publish metadata and binary hashes, not stock firmware.
OUT="$RESULTS_DIR/$MODE"
mkdir -p "$OUT"
cp "$IMAGE" "$OUT/Image"
cp "$DTB" "$OUT/sun60i-a733-orangepi-zero3w.dtb"
git -C "$TREE" diff -- "$DTS_REL" > "$OUT/dts.patch"
{
  echo "SOURCE_COMMIT=$PIN"
  echo "MODE=$MODE"
  echo "SOURCE=$TREE"
  echo "BUILD=$OBJ"
  echo "KERNEL_VERSION=$(make -s -C "$TREE" O="$OBJ" ARCH=arm64 kernelrelease)"
  sha256sum "$WORK_ROOT/vendor-a733.config" "$OBJ/.config" "$TREE/$DTS_REL" "$IMAGE" "$DTB"
} > "$OUT/build-manifest.txt"
(cd "$OUT" && sha256sum Image sun60i-a733-orangepi-zero3w.dtb dts.patch build-manifest.txt > SHA256SUMS)
echo "BUILT_OFFLINE_NOT_FLASHABLE_NOT_HARDWARE_TESTED: $OUT"
