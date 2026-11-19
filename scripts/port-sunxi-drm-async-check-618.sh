#!/usr/bin/env bash
# Port vendor DRM plane atomic_async_check function-pointer signature to 6.18.
# This is a compatibility wrapper; original vendor validation is preserved.
set -euo pipefail
ROOT="${ROOT:-/root/opi3w-m2-work/linux-618-hdmi-stage4}"
FILE="$ROOT/linux/drivers/gpu/drm/sunxi_vendor/sunxi_drm_crtc.c"
[[ -f "$FILE" && -d "$ROOT/obj" ]] || { echo "Missing stage4 build source" >&2; exit 1; }
python3 - "$FILE" <<'PY'
from pathlib import Path
import re, sys
p = Path(sys.argv[1])
s = p.read_text()
old = s
anchor = '.atomic_async_check = sunxi_plane_atomic_async_check,'
if s.count(anchor) != 1:
    raise SystemExit(f'STOP: expected one callback initializer, got {s.count(anchor)}')
# Confirm the actual vendor definition uses the old two-argument signature.
pat = r'(?s)static\s+int\s+sunxi_plane_atomic_async_check\s*\(\s*struct drm_plane\s*\*\s*\w+\s*,\s*struct drm_atomic_state\s*\*\s*\w+\s*\)'
matches = list(re.finditer(pat, s))
if len(matches) != 1:
    raise SystemExit(f'STOP: expected exactly one two-argument callback definition, got {len(matches)}')
# Place wrapper after old vendor callback and before the funcs table.
table = re.search(r'(?m)^static const struct drm_plane_helper_funcs\s+\w+\s*=\s*\{', s)
if not table or table.start() <= matches[0].end():
    raise SystemExit('STOP: cannot locate plane helper table after vendor callback')
wrapper = '''
/* Linux 6.18 provides a third 'flip' argument to atomic_async_check.
 * The original vendor check is retained for both call sites. Revisit the
 * flip distinction when validating asynchronous page flips on hardware.
 */
static int sunxi_plane_atomic_async_check_618(struct drm_plane *plane,
                                              struct drm_atomic_state *state,
                                              bool flip)
{
    (void)flip;
    return sunxi_plane_atomic_async_check(plane, state);
}

'''
s = s[:table.start()] + wrapper + s[table.start():]
s = s.replace(anchor, '.atomic_async_check = sunxi_plane_atomic_async_check_618,')
p.with_suffix('.c.pre-async-618').write_text(old)
p.write_text(s)
print('Adapted async check via wrapper; original validation unchanged.')
PY
LOG="$ROOT/build-async-618.log"
echo "Incremental Linux 6.18 build; log: $LOG"
if ! make -C "$ROOT/linux" O="$ROOT/obj" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- -j"${JOBS:-4}" Image modules >"$LOG" 2>&1; then
  grep -n -m 35 -E 'error:|fatal error:|undefined reference|No rule to make target' "$LOG" || :
  tail -25 "$LOG"
  exit 1
fi
mkdir -p "$ROOT/artifacts"
cp "$ROOT/obj/arch/arm64/boot/Image" "$ROOT/artifacts/Image-618-vendor-hdmi"
sha256sum "$ROOT/artifacts/Image-618-vendor-hdmi"
echo 'Compile completed; no HDMI hardware test performed.'
