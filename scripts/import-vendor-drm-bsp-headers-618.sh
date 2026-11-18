#!/usr/bin/env bash
# Import missing shared Allwinner BSP headers actually referenced by staged DRM.
# Exact vendor header copies; no stub definitions, no altered kernel configuration.
set -euo pipefail
ROOT="${ROOT:-/root/opi3w-m2-work/linux-618-hdmi-stage4}"
VENDOR="${VENDOR:-/root/opi3w-vendor-6698-work/kernel}"
SRC="$ROOT/linux"
DRM="$SRC/drivers/gpu/drm/sunxi_vendor"
[[ -d "$DRM" && -d "$ROOT/obj" && -d "$VENDOR/bsp/include" ]] || {
  echo "Missing stage4 source/build or vendor BSP includes" >&2; exit 1;
}
python3 - "$DRM" "$VENDOR" <<'PY'
from pathlib import Path
from collections import deque
import hashlib
import re
import sys
drm, vendor = map(Path, sys.argv[1:])
shared = vendor / "bsp/include"
# Scan all staged vendor DRM C/H files and recursively scan imported headers.
queue = deque(f for f in drm.rglob("*") if f.suffix in (".c", ".h"))
seen = set()
imported = []
rx = re.compile(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]', re.M)
while queue:
    file = queue.popleft()
    if file in seen:
        continue
    seen.add(file)
    for name in rx.findall(file.read_text(errors="replace")):
        if "/" in name or not name.endswith(".h") or not name.startswith("sunxi-"):
            continue
        # Only shared vendor headers; do not copy driver-local implementations.
        choices = [shared / name, shared / "linux" / name]
        candidate = next((p for p in choices if p.is_file()), None)
        if candidate is None:
            continue
        dest = drm / name
        if dest.exists():
            if dest.read_bytes() != candidate.read_bytes():
                # Existing local header may legitimately be an implementation header.
                # Do not overwrite it.
                continue
        else:
            dest.write_bytes(candidate.read_bytes())
            imported.append((candidate, dest))
        queue.append(dest)
for src, dest in imported:
    print(f"Imported {src} -> {dest} sha256={hashlib.sha256(dest.read_bytes()).hexdigest()}")
print(f"Imported {len(imported)} shared BSP headers.")
PY
# Angle-bracket includes require an explicit -I path.
MK="$DRM/Makefile"
FLAG='ccflags-y += -I$(src)'
if ! grep -Fqx "$FLAG" "$MK"; then
  printf '\n%s\n' "$FLAG" >> "$MK"
fi
LOG="$ROOT/build-bsp-headers-618.log"
echo "Incremental build; log: $LOG"
if ! make -C "$SRC" O="$ROOT/obj" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- \
    -j"${JOBS:-4}" Image modules >"$LOG" 2>&1; then
  grep -n -m 35 -E 'fatal error:|error:|undefined reference|No rule to make target' "$LOG" || :
  tail -25 "$LOG"
  exit 1
fi
mkdir -p "$ROOT/artifacts"
cp "$ROOT/obj/arch/arm64/boot/Image" "$ROOT/artifacts/Image-618-vendor-hdmi"
sha256sum "$ROOT/artifacts/Image-618-vendor-hdmi"
echo "Build succeeded; HDMI remains untested on physical hardware."
