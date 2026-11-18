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
# Vendor's shared BSP API header is the consumer-facing DRM interface.
# The distinct drivers/iommu copy belongs to its implementation, not this DRM
# include. Preserve its identity and record both checksums.
python3 - "$VENDOR" "$TARGET" <<'PY'
from pathlib import Path
import hashlib
import sys
vendor, target = map(Path, sys.argv[1:])
shared = vendor / "bsp/include/sunxi-iommu.h"
internal = vendor / "bsp/drivers/iommu/sunxi-iommu.h"
if not shared.is_file():
    raise SystemExit(f"STOP: missing shared BSP header: {shared}")
data = shared.read_bytes()
if target.exists() and target.read_bytes() != data:
    raise SystemExit("STOP: existing staged header differs from vendor's shared API")
if not target.exists():
    target.write_bytes(data)
for label, file in (("shared BSP API", shared), ("driver-local implementation", internal)):
    if file.is_file():
        print(f"{label}: {file}: sha256={hashlib.sha256(file.read_bytes()).hexdigest()}")
print(f"Imported shared API header to: {target}")
PY
# An angle-bracket include does not search the current C file directory.
# Make the imported vendor header discoverable without replacing mainline IOMMU headers.
if grep -Eq '^[[:space:]]*#[[:space:]]*include[[:space:]]*<sunxi-iommu[.]h>' "$DRM/sunxi_drm_debug.c"; then
  MK="$DRM/Makefile"
  FLAG='ccflags-y += -I$(src)'
  if ! grep -Fqx "$FLAG" "$MK"; then
    printf '\n%s\n' "$FLAG" >> "$MK"
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
