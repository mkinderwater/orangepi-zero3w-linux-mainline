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
# Undo the unsuccessful GNU Make grouped-target experiment in the disposable
# worktree. Preserve pinned vendor source. Fix the verified malformed Kconfig
# reference instead; this avoids the phantom auto.conf dependency.
python3 - "$TREE" "$MODE" "$DTS_REL" <<'PY'
import subprocess,sys
from pathlib import Path
root,mode,dts=Path(sys.argv[1]),sys.argv[2],sys.argv[3]
mk=root/'Makefile'
original='%/config/auto.conf %/config/auto.conf.cmd %/generated/autoconf.h %/generated/rustc_cfg: $(KCONFIG_CONFIG)'
grouped='%/config/auto.conf %/config/auto.conf.cmd %/generated/autoconf.h %/generated/rustc_cfg &: $(KCONFIG_CONFIG)'
s=mk.read_text()
if s.count(grouped)==1 and original not in s:
    mk.write_text(s.replace(grouped,original,1))
elif s.count(original)!=1 or grouped in s:
    raise SystemExit('STOP: unexpected kernel Makefile state')
kpath='bsp/drivers/input/ctp/Kconfig'
kp=root/kpath
bad='source "bsp/drivers/input/ctp/gt9xx_secondary//Kconfig"'
good='source "bsp/drivers/input/ctp/gt9xx_secondary/Kconfig"'
s=kp.read_text()
if s.count(bad)==1 and good not in s:
    kp.write_text(s.replace(bad,good,1))
elif s.count(good)!=1 or bad in s:
    raise SystemExit('STOP: unexpected touchscreen Kconfig source')
assert (root/'bsp/drivers/input/ctp/gt9xx_secondary/Kconfig').is_file(), 'STOP: target Kconfig absent'
# This include is relative to the object tree under O= builds. Point it at
# the pinned source tree without touching codec sources or configurations.
vepath='bsp/drivers/ve/cedar-ve/Makefile'
ve=root/vepath
wrong='include $(src)/codec/Makefile'
right='include $(srctree)/$(src)/codec/Makefile'
txt=ve.read_text()
if txt.count(wrong)==1 and right not in txt:
    ve.write_text(txt.replace(wrong,right,1))
elif txt.count(right)!=1 or wrong in txt:
    raise SystemExit('STOP: unexpected VE Makefile include')
assert (root/'bsp/drivers/ve/cedar-ve/codec/Makefile').is_file(), 'STOP: VE codec source Makefile absent'
changed=subprocess.check_output(['git','-C',str(root),'diff','--name-only'],text=True).splitlines()
expected=[kpath,vepath] if mode=='control' else [kpath,vepath,dts]
if sorted(changed)!=sorted(expected):
    raise SystemExit(f'STOP: unexpected tracked changes: {changed}')
diff=subprocess.check_output(['git','-C',str(root),'diff','--',kpath],text=True)
removed=[x for x in diff.splitlines() if x.startswith('-') and not x.startswith('---')]
added=[x for x in diff.splitlines() if x.startswith('+') and not x.startswith('+++')]
if removed!=['-'+bad] or added!=['+'+good]:
    raise SystemExit('STOP: Kconfig repair diff differs')
ve_diff=subprocess.check_output(['git','-C',str(root),'diff','--',vepath],text=True)
ve_removed=[x for x in ve_diff.splitlines() if x.startswith('-') and not x.startswith('---')]
ve_added=[x for x in ve_diff.splitlines() if x.startswith('+') and not x.startswith('+++')]
if ve_removed!=['-'+wrong] or ve_added!=['+'+right]:
    raise SystemExit('STOP: VE Makefile patch differs')
if mode=='identity':
    diff=subprocess.check_output(['git','-C',str(root),'diff','--',dts],text=True)
    old='compatible = "xunlong,orangepi-4-pro", "arm,sun60iw2p1";'
    new='compatible = "xunlong,orangepi-zero3w", "arm,sun60iw2p1";'
    if diff.count('-\t'+old)!=1 or diff.count('+\t'+new)!=1:
        raise SystemExit('STOP: identity DTS diff differs')
print('KCONFIG_PATH_AND_VE_INCLUDE_REPAIRED_EXACT_DIFF_VERIFIED')
PY
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
git -C "$TREE" diff -- bsp/drivers/input/ctp/Kconfig > "$OUT/kconfig-path.patch"
git -C "$TREE" diff -- bsp/drivers/ve/cedar-ve/Makefile > "$OUT/ve-include-path.patch"
{
  echo "SOURCE_COMMIT=$PIN"
  echo "MODE=$MODE"
  echo "SOURCE=$TREE"
  echo "BUILD=$OBJ"
  echo "KCONFIG_REPAIR=gt9xx_secondary_double_slash"
  echo "VE_KBUILD_REPAIR=source_tree_codec_include"
  echo "KERNEL_VERSION=$(make -s -C "$TREE" O="$OBJ" ARCH=arm64 kernelrelease)"
  sha256sum "$WORK_ROOT/vendor-a733.config" "$OBJ/.config" "$TREE/$DTS_REL" "$IMAGE" "$DTB"
} > "$OUT/build-manifest.txt"
(cd "$OUT" && sha256sum Image sun60i-a733-orangepi-zero3w.dtb dts.patch kconfig-path.patch ve-include-path.patch build-manifest.txt > SHA256SUMS)
echo "BUILT_OFFLINE_NOT_FLASHABLE_NOT_HARDWARE_TESTED: $OUT"
