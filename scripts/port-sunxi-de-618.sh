#!/usr/bin/env bash
# Incremental A733 DE API port to Linux 6.18. Stage4 sources only.
set -euo pipefail
ROOT=/root/opi3w-m2-work/linux-618-hdmi-stage4
DE="$ROOT/linux/drivers/gpu/drm/sunxi_vendor/sunxi_device/hardware/lowlevel_de"
[[ -f "$DE/sunxi_de.c" && -f "$DE/de_channel.c" ]] || exit 1
python3 - "$DE/sunxi_de.c" "$DE/de_channel.c" <<'PY'
from pathlib import Path
import re, sys
de, ch = map(Path, sys.argv[1:])
a, b = de.read_text(), ch.read_text()
oa, ob = a, b

pat = r'drm_framebuffer_plane_(width|height)\s*\(\s*(fb\[\d+\])->(width|height)\s*,\s*\2\s*,\s*(\d+)\s*\)'
def replace_plane(m):
    kind, fb, dimension, plane = m.groups()
    if kind != dimension:
        raise SystemExit("Unexpected framebuffer dimension")
    return f'drm_format_info_plane_{kind}({fb}->format, {fb}->{dimension}, {plane})'
b, n = re.subn(pat, replace_plane, b)
if n < 1:
    raise SystemExit("STOP: no remaining old framebuffer plane helpers found")
print("Framebuffer dimension helpers:", n)

m = re.search(r'static\s+int\s+sunxi_de_remove\s*\(\s*struct platform_device\s*\*\s*\w+\s*\)', a)
if not m:
    raise SystemExit("STOP: expected int sunxi_de_remove definition not found")
open_at = a.find('{', m.end())
if open_at < 0:
    raise SystemExit("STOP: remove body missing")
depth = 0
close_at = None
for i in range(open_at, len(a)):
    if a[i] == '{': depth += 1
    elif a[i] == '}':
        depth -= 1
        if depth == 0:
            close_at = i
            break
if close_at is None:
    raise SystemExit("STOP: remove body unmatched")
body = a[open_at+1:close_at]
if not re.search(r'\breturn\s+0\s*;\s*$', body):
    raise SystemExit("STOP: remove has nontrivial return; inspect manually")
other = re.sub(r'\breturn\s+0\s*;\s*$', '', body)
if re.search(r'\breturn\b', other):
    raise SystemExit("STOP: remove contains other return statements")
a = a[:open_at+1] + other + a[close_at:]
a = a.replace(m.group(0), m.group(0).replace('static int','static void',1), 1)
print("Platform remove callback updated")

# hrtimer_init was removed in Linux 6.15; setup takes function as third argument.
init = re.search(r'hrtimer_init\s*\(\s*&([A-Za-z_]\w*(?:(?:->|\.)[A-Za-z_]\w*)*)\s*,\s*(CLOCK_[A-Za-z0-9_]+)\s*,\s*(HRTIMER_MODE_[A-Za-z0-9_]+)\s*\)\s*;', a)
if not init:
    raise SystemExit("STOP: timer declaration not recognized; inspect sunxi_de.c around 1547")
timer, clock, mode = init.groups()
assignment = re.compile(re.escape(timer) + r'\.function\s*=\s*([A-Za-z_]\w*)\s*;')
hits = list(assignment.finditer(a))
if len(hits) != 1:
    raise SystemExit(f"STOP: callback for {timer} not uniquely identified")
cb = hits[0].group(1)
# Remove explicit callback assignment, convert initialization.
a = a[:hits[0].start()] + a[hits[0].end():]
a = a.replace(init.group(0), f'hrtimer_setup(&{timer}, {cb}, {clock}, {mode});',1)
print("hrtimer_setup callback:", cb)

de.with_suffix('.c.pre-618-de-api').write_text(oa)
ch.with_suffix('.c.pre-618-plane-api').write_text(ob)
de.write_text(a)
ch.write_text(b)
PY
LOG="$ROOT/build-de-api-618.log"
if ! make -C "$ROOT/linux" O="$ROOT/obj" ARCH=arm64 \
  CROSS_COMPILE=aarch64-linux-gnu- -j4 Image modules >"$LOG" 2>&1; then
  grep -n -m 35 -E 'fatal error:|error:|undefined reference|No rule to make target' "$LOG" || :
  tail -20 "$LOG"
  exit 1
fi
mkdir -p "$ROOT/artifacts"
cp "$ROOT/obj/arch/arm64/boot/Image" "$ROOT/artifacts/Image-618-vendor-hdmi"
sha256sum "$ROOT/artifacts/Image-618-vendor-hdmi"
