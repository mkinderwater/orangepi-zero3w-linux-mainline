#!/usr/bin/env bash
# Stage only the vendor sunxi-iommu.h dependency requested by sunxi_drm_debug.c.
# Uses the existing Stage 4 kernel tree and preserves vendor source/boot images.
set -euo pipefail
ROOT="${ROOT:-/root/opi3w-m2-work/linux-618-hdmi-stage4}"
VENDOR="${VENDOR:-/root/opi3w-vendor-6698-work/kernel}"
SRC="$ROOT/linux"
DRM="$SRC/drivers/gpu/drm/sunxi_vendor"
TARGET="$DRM/sunxi-iommu.h"
[[ -d "$DRM" && -d "$ROOT/obj" && -d "$VENDOR" ]] || {
  echo "Missing staged DRM, build objects, or vendor source" >&2; exit 1;
}
grep -Eq '^[[:space:]]*#[[:space:]]*include[[:space:]]*[<"]sunxi-iommu[.]h[>"]' "$DRM/sunxi_drm_debug.c" || {
  echo "STOP: sunxi-iommu.h include not found in expected source; actual includes:" >&2
  grep -n -E 'iommu|^[[:space:]]*#[[:space:]]*include' "$DRM/sunxi_drm_debug.c" | head -45 >&2 || :
  exit 1
}
# No guessing at header contents. Select a single distinct vendor file and
# fail if conflicting versions exist in different vendor directories.
python3 - "$VENDOR" "$TARGET" <<'PY'
from pathlib import Path
import sys
vendor, target = map(Path, sys.argv[1:])
found = [p for p in vendor.rglob('sunxi-iommu.h') if p.is_file()]
if not found:
    raise SystemExit('STOP: sunxi-iommu.h not found in original vendor tree')
payloads = {p.read_bytes() for p in found}
if len(payloads) != 1:
    for p in found: print(p)
    raise SystemExit('STOP: conflicting vendor sunxi-iommu.h variants')
data = found[0].read_bytes()
if target.exists() and target.read_bytes() != data:
    raise SystemExit('STOP: staged header already exists and differs')
if not target.exists():
    target.write_bytes(data)
print('Imported original header from:', found[0])
PY
# An angle-bracket include does not search the current C file directory.
# Make the imported vendor header discoverable without replacing mainline IOMMU headers.
if grep -Eq '^[[:space:]]*#[[:space:]]*include[[:space:]]*<sunxi-iommu[.]h>' "$DRM/sunxi_drm_debug.c"; then
  MK="$DRM/Makefile"
  FLAG='ccflags-y += -I$(src)'
  if ! grep -Fqx "$FLAG" "$MK"; then
    printf '\\n%s\\n' "$FLAG" >> "$MK"
  fi
fi
LOG="$ROOT/build-iommu-header-618.log"
echo "Incremental compile; log: $LOG"
if ! make -C "$SRC" O="$ROOT/obj" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- \
  -j"${JOBS:-4}" Image modules >"$LOG" 2>&1; then
  grep -n -m 35 -E 'fatal error:|error:|undefined reference|No rule to make target' "$LOG" || :
  echo "--- Last lines ---"
  tail -25 "$LOG"
  exit 1
fi
mkdir -p "$ROOT/artifacts"
cp "$ROOT/obj/arch/arm64/boot/Image" "$ROOT/artifacts/Image-618-vendor-hdmi"
sha256sum "$ROOT/artifacts/Image-618-vendor-hdmi"
echo "Compiled successfully. HDMI/UART hardware validation remains pending."
