#!/usr/bin/env bash
# Import only vendor video/*.h dependencies referenced by the staged Sunxi DRM.
# Reuses stage4 build artifacts, does not alter boot files or original vendor tree.
set -euo pipefail
ROOT="${ROOT:-/root/opi3w-m2-work/linux-618-hdmi-stage4}"
VENDOR="${VENDOR:-/root/opi3w-vendor-6698-work/kernel}"
SRC="$ROOT/linux"
DRM="$SRC/drivers/gpu/drm/sunxi_vendor"
[[ -d "$DRM" && -d "$ROOT/obj" && -d "$VENDOR" ]] || {
  echo "Missing stage4 vendor DRM, build output, or vendor source" >&2; exit 1;
}
python3 - "$SRC" "$VENDOR" <<'PY'
from pathlib import Path
from collections import deque
import re, sys
src, vendor = map(Path, sys.argv[1:])
drm = src / "drivers/gpu/drm/sunxi_vendor"
inc = re.compile(r'^\s*#\s*include\s*[<"]video/([^>"]+)[>"]', re.M)
# Only search exact vendor video include locations. No generic kernel header substitution.
roots = [
    vendor / "include/video",
    vendor / "bsp/include/video",
    vendor / "bsp/drivers/drm/include/video",
]
queue = deque(p for p in drm.rglob("*") if p.suffix in (".c", ".h"))
seen = set()
imported = []
while queue:
    f = queue.popleft()
    if f in seen:
        continue
    seen.add(f)
    for rel in inc.findall(f.read_text(errors="replace")):
        if rel.startswith("/") or ".." in Path(rel).parts:
            raise SystemExit(f"STOP: unexpected header path {rel!r} in {f}")
        dest = src / "include/video" / rel
        if dest.exists():
            # An already-present header is the first choice. Follow its dependencies.
            queue.append(dest)
            continue
        candidates = [root / rel for root in roots if (root / rel).is_file()]
        if not candidates:
            raise SystemExit(f"STOP: missing vendor video/{rel}, referenced by {f}")
        if len(candidates) > 1 and any(p.read_bytes() != candidates[0].read_bytes() for p in candidates[1:]):
            raise SystemExit(f"STOP: conflicting vendor versions of video/{rel}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(candidates[0].read_bytes())
        imported.append((rel, str(candidates[0])))
        queue.append(dest)
for rel, origin in imported:
    print(f"Imported video/{rel} from {origin}")
print(f"Vendor display headers imported: {len(imported)}")
PY
LOG="$ROOT/build-headers-618.log"
echo "Incremental build; log: $LOG"
if ! make -C "$SRC" O="$ROOT/obj" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- \
    -j"${JOBS:-4}" Image modules >"$LOG" 2>&1; then
  echo "First real compiler errors:"
  grep -n -m 35 -E 'fatal error:|error:|undefined reference|No rule to make target' "$LOG" || :
  tail -25 "$LOG"
  exit 1
fi
mkdir -p "$ROOT/artifacts"
cp "$ROOT/obj/arch/arm64/boot/Image" "$ROOT/artifacts/Image-618-vendor-hdmi"
sha256sum "$ROOT/artifacts/Image-618-vendor-hdmi"
echo "Build succeeded. UART/HDMI hardware operation still untested."
