#!/usr/bin/env bash
set -euo pipefail
PIN_KERNEL=2ac08e8c7cdc28abbdc5c9a9dd812f887ae9c79f
PIN_BUILD=7f24222b928eab94780f2af03289ce527e07241e
WORK_ROOT="${WORK_ROOT:-/root/opi3w-vendor-6698-work}"
RESULTS_DIR="${RESULTS_DIR:-/mnt/c/Users/mkinderwater/Downloads/opi3w-vendor-6698-results}"
mkdir -p "$WORK_ROOT" "$RESULTS_DIR"
for c in git curl python3 make sha256sum; do command -v "$c" >/dev/null || { echo "ERROR: missing $c" >&2; exit 2; }; done
if [[ ! -d "$WORK_ROOT/kernel/.git" ]]; then
  [[ ! -e "$WORK_ROOT/kernel" ]] || { echo 'ERROR: unexpected existing kernel directory' >&2; exit 3; }
  git clone --filter=blob:none https://github.com/orangepi-xunlong/linux-orangepi.git "$WORK_ROOT/kernel"
fi
git -C "$WORK_ROOT/kernel" fetch --no-tags origin "$PIN_KERNEL"
git -C "$WORK_ROOT/kernel" checkout --detach "$PIN_KERNEL"
[[ "$(git -C "$WORK_ROOT/kernel" rev-parse HEAD)" == "$PIN_KERNEL" ]]
[[ -z "$(git -C "$WORK_ROOT/kernel" status --porcelain)" ]] || { echo 'ERROR: kernel checkout dirty' >&2; exit 3; }
python3 - "$WORK_ROOT/kernel" <<'PY'
import sys,re
from pathlib import Path
root=Path(sys.argv[1])
m=(root/'Makefile').read_text()
v=[int(re.search(r'^'+k+r'\s*=\s*(\d+)',m,re.M).group(1)) for k in ('VERSION','PATCHLEVEL','SUBLEVEL')]
assert v==[6,6,98],v
p=root/'arch/arm64/boot/dts/allwinner/sun60i-a733-orangepi-zero3w.dts'
assert p.read_text().count('compatible = "xunlong,orangepi-4-pro", "arm,sun60iw2p1";')==1
print('PINNED_KERNEL_6_6_98_AND_VENDOR_DTS_VERIFIED')
PY
CFG="$WORK_ROOT/vendor-a733.config"
curl -fsSL "https://raw.githubusercontent.com/orangepi-xunlong/orangepi-build/$PIN_BUILD/external/config/kernel/linux-sun60iw2-current-a733.config" -o "$CFG.tmp"
mv "$CFG.tmp" "$CFG"
for k in AW_TWI AW_MMC AW_MFD_AXP2101 AW_MFD_AXP2101_I2C AW_REGULATOR_AXP2101; do
  grep -qx "CONFIG_${k}=y" "$CFG" || { echo "ERROR: missing $k" >&2; exit 3; }
done
{
echo "kernel_commit=$PIN_KERNEL"
echo "build_commit=$PIN_BUILD"
sha256sum "$WORK_ROOT/kernel/arch/arm64/boot/dts/allwinner/sun60i-a733-orangepi-zero3w.dts" "$CFG"
} | tee "$RESULTS_DIR/source-manifest.txt"
echo 'SOURCE_PREPARED_NOT_BUILT'
