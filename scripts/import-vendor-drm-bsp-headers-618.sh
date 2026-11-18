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
destination = drm / "_vendor_shared"
rx = re.compile(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]', re.M)
queue = deque(f for f in drm.rglob("*") if f.suffix in (".c", ".h"))
seen = set()
imported = []

while queue:
    file = queue.popleft()
    if file in seen:
        continue
    seen.add(file)
    for name in rx.findall(file.read_text(errors="replace")):
        rel = Path(name)
        if rel.is_absolute() or ".." in rel.parts or rel.suffix != ".h":
            continue
        # Do not shadow upstream Linux, DRM, or architecture headers.
        if rel.parts[0] in {"linux", "drm", "asm", "asm-generic", "uapi", "generated"}:
            continue
        # Quoted includes in a staged vendor header resolve relative to
        # that header first: errcode/sunxi-err.h includes sunxi-err-audio.h.
        candidates = []
        if file.is_relative_to(destination):
            relative_parent = file.parent.relative_to(destination)
            candidates.append(relative_parent / rel)
        candidates.append(rel)
        chosen = None
        for relative_path in candidates:
            possible = shared / relative_path
            if possible.is_file():
                chosen = (possible, relative_path)
                break
        if chosen is None:
            continue
        candidate, target_rel = chosen
        target = destination / target_rel
        if target.exists():
            if target.read_bytes() != candidate.read_bytes():
                raise SystemExit(f"STOP: shared-header mismatch for {rel}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(candidate.read_bytes())
            imported.append((candidate, target))
        # Includes can be nested, e.g. sunxi-log.h -> errcode/sunxi-err.h.
        queue.append(target)

for origin, target in imported:
    print(f"Imported {origin} -> {target} sha256={hashlib.sha256(target.read_bytes()).hexdigest()}")
print(f"Imported {len(imported)} additional transitive vendor BSP headers.")
PY
# Only the copied vendor header tree is visible to the vendor DRM driver.
# Keep original Linux include paths authoritative.
MK="$DRM/Makefile"
FLAG='ccflags-y += -I$(src)/_vendor_shared'
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
