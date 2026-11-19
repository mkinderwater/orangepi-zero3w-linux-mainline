#!/usr/bin/env bash
# Linux 6.18 API port for vendor framebuffer vmalloc and plane dimensions.
# Reuses stage4 source and incremental objects, never touches proven boot files.
set -euo pipefail
ROOT="${ROOT:-/root/opi3w-m2-work/linux-618-hdmi-stage4}"
SRC="$ROOT/linux"
DRM="$SRC/drivers/gpu/drm/sunxi_vendor"
[[ -f "$DRM/sunxi_fbdev_platform.c" && -f "$DRM/sunxi_device/hardware/lowlevel_de/de_channel.c" && -d "$ROOT/obj" ]] || {
  echo "Missing stage4 source or objects" >&2; exit 1;
}
# Verify the upstream DRM API exists in the exact kernel source being built.
grep -Rq 'drm_format_info_plane_width' "$SRC/include/drm" || {
  echo "STOP: drm_format_info_plane_width unavailable in current headers" >&2; exit 1;
}
grep -Rq 'drm_format_info_plane_height' "$SRC/include/drm" || {
  echo "STOP: drm_format_info_plane_height unavailable in current headers" >&2; exit 1;
}
python3 - "$DRM/sunxi_fbdev_platform.c" "$DRM/sunxi_device/hardware/lowlevel_de/de_channel.c" <<'PY'
from pathlib import Path
import re
import sys
fb, de = map(Path, sys.argv[1:])
fb_old, de_old = fb.read_text(), de.read_text()
if '#include <linux/vmalloc.h>' in fb_old:
    raise SystemExit("STOP: vmalloc header already added; cannot repeat patch")
# Insert next to other includes, preserving source logic.
match = re.search(r'(?m)^#include\s+[<"][^>"]+[>"]\s*$', fb_old)
if not match:
    raise SystemExit("STOP: no include section in sunxi_fbdev_platform.c")
fb_new = fb_old[:match.start()] + '#include <linux/vmalloc.h>\n' + fb_old[match.start():]
# These legacy functions take (plane_width_or_height, framebuffer, plane)
# 6.18 DRM uses (format_info, framebuffer_dimension, plane).
patterns = (
    (r'drm_framebuffer_plane_width\s*\(\s*fb\[0\]->width\s*,\s*fb\[0\]\s*,\s*0\s*\)',
     'drm_format_info_plane_width(fb[0]->format, fb[0]->width, 0)'),
    (r'drm_framebuffer_plane_height\s*\(\s*fb\[0\]->height\s*,\s*fb\[0\]\s*,\s*0\s*\)',
     'drm_format_info_plane_height(fb[0]->format, fb[0]->height, 0)'),
)
de_new = de_old
for pattern, replacement in patterns:
    de_new, count = re.subn(pattern, replacement, de_new)
    if count != 1:
        raise SystemExit(f"STOP: expected exactly one vendor dimension helper call, found {count}: {pattern}")
# Check current file includes DRM format helpers, as normally found transitively
# through DRM framebuffer headers; explicitly include stable public API.
if '#include <drm/drm_fourcc.h>' not in de_new:
    m = re.search(r'(?m)^#include\s+[<"][^>"]+[>"]\s*$', de_new)
    if not m:
        raise SystemExit("STOP: no includes in de_channel.c")
    de_new = de_new[:m.start()] + '#include <drm/drm_fourcc.h>\n' + de_new[m.start():]
fb.with_suffix('.c.pre-vmalloc-618').write_text(fb_old)
de.with_suffix('.c.pre-planes-618').write_text(de_old)
fb.write_text(fb_new)
de.write_text(de_new)
print('Added vmalloc.h; converted exactly one width and height helper to 6.18 DRM API.')
PY
LOG="$ROOT/build-vmalloc-planes-618.log"
echo "Incremental build; log: $LOG"
if ! make -C "$SRC" O="$ROOT/obj" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- \
     -j"${JOBS:-4}" Image modules >"$LOG" 2>&1; then
  grep -n -m 40 -E 'fatal error:|error:|undefined reference|No rule to make target' "$LOG" || :
  tail -25 "$LOG"
  exit 1
fi
mkdir -p "$ROOT/artifacts"
cp "$ROOT/obj/arch/arm64/boot/Image" "$ROOT/artifacts/Image-618-vendor-hdmi"
sha256sum "$ROOT/artifacts/Image-618-vendor-hdmi"
echo "Compile succeeded, HDMI hardware validation pending."
