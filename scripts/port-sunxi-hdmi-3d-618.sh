#!/usr/bin/env bash
# Restore the upstream HDMI 3D enum declaration for vendor HDMI frame composer.
# Stage4 source only, no magic numeric substitutions or disabled functionality.
set -euo pipefail
ROOT="${ROOT:-/root/opi3w-m2-work/linux-618-hdmi-stage4}"
SRC="$ROOT/linux"
FILE="$SRC/drivers/gpu/drm/sunxi_vendor/sunxi_device/hardware/lowlevel_hdmi20/dw_fc.c"
HDR="$SRC/include/linux/hdmi.h"
[[ -f "$FILE" && -f "$HDR" && -d "$ROOT/obj" ]] || {
  echo "Missing stage4 frame composer, upstream HDMI header, or build outputs" >&2; exit 1;
}
grep -q 'HDMI_3D_STRUCTURE_FRAME_PACKING' "$HDR" || {
  echo "STOP: upstream Linux header lacks HDMI 3D enumeration" >&2; exit 1;
}
python3 - "$FILE" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1])
s=p.read_text()
if s.count('HDMI_3D_STRUCTURE_FRAME_PACKING') < 1:
    raise SystemExit("STOP: expected HDMI frame-packing constant usage absent")
if re.search(r'^\s*#\s*include\s*<linux/hdmi\.h>',s,re.M):
    raise SystemExit("STOP: linux/hdmi.h already included; investigate collision")
includes=list(re.finditer(r'(?m)^#include\s+[<"][^>"]+[>"]\s*$',s))
if not includes:
    raise SystemExit("STOP: no include section in dw_fc.c")
anchor=includes[0]
updated=s[:anchor.start()]+'#include <linux/hdmi.h>\n'+s[anchor.start():]
backup=p.with_name(p.name+'.pre-hdmi-3d-618')
if backup.exists():
    raise SystemExit("STOP: existing backup, refusing repeated patch")
backup.write_text(s)
p.write_text(updated)
print("Imported upstream HDMI 3D structure enumeration with linux/hdmi.h")
PY
LOG="$ROOT/build-hdmi-3d-618.log"
echo "Incremental compile: $LOG"
if ! make -C "$SRC" O="$ROOT/obj" ARCH=arm64 \
   CROSS_COMPILE=aarch64-linux-gnu- -j"${JOBS:-4}" Image modules >"$LOG" 2>&1; then
  grep -n -m 35 -E 'fatal error:|error:|undefined reference|No rule to make target' "$LOG" || :
  tail -20 "$LOG"
  exit 1
fi
mkdir -p "$ROOT/artifacts"
cp "$ROOT/obj/arch/arm64/boot/Image" "$ROOT/artifacts/Image-618-vendor-hdmi"
sha256sum "$ROOT/artifacts/Image-618-vendor-hdmi"
echo "Compiled, physical HDMI validation pending."
