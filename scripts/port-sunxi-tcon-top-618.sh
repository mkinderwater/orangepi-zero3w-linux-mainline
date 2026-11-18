#!/usr/bin/env bash
# Linux 6.18 platform .remove API for vendor TCON_TOP in existing Stage4.
set -euo pipefail
ROOT="${ROOT:-/root/opi3w-m2-work/linux-618-hdmi-stage4}"
SRC="$ROOT/linux"
FILE="$SRC/drivers/gpu/drm/sunxi_vendor/sunxi_device/sunxi_tcon_top.c"
[[ -f "$FILE" && -d "$ROOT/obj" ]] || { echo "Missing Stage4 source or objects" >&2; exit 1; }

python3 - "$FILE" <<'PY'
from pathlib import Path
import re
import sys

p = Path(sys.argv[1])
original = p.read_text()
s = original

driver = re.search(r'\.remove\s*=\s*(\w+)\s*,', s)
if not driver:
    raise SystemExit("STOP: TCON_TOP remove assignment not found")
name = driver.group(1)
definition = re.search(
    r'(?m)^\s*(?:static\s+)?int\s+' + re.escape(name) +
    r'\s*\(\s*struct\s+platform_device\s*\*\s*\w+\s*\)',
    s)
if not definition:
    raise SystemExit("STOP: expected int remove callback definition missing")
opening = s.find('{', definition.end())
if opening < 0:
    raise SystemExit("STOP: remove body missing")
depth = 0
closing = None
for i in range(opening, len(s)):
    if s[i] == '{':
        depth += 1
    elif s[i] == '}':
        depth -= 1
        if depth == 0:
            closing = i
            break
if closing is None:
    raise SystemExit("STOP: unbalanced remove function")
body = s[opening+1:closing]
clean, count = re.subn(r'\breturn\s+0\s*;\s*$', '', body)
if count != 1 or re.search(r'\breturn\b', clean):
    raise SystemExit("STOP: remove has nontrivial return paths; review manually")
s = s[:opening+1] + clean + s[closing:]
decl = definition.group(0)
s = s.replace(decl, re.sub(r'\bint\b', 'void', decl, count=1), 1)
backup = p.with_name(p.name + '.pre-tcon-top-618')
if backup.exists():
    raise SystemExit("STOP: backup already exists; patch likely repeated")
backup.write_text(original)
p.write_text(s)
print("Updated TCON_TOP remove callback:", name)
PY

LOG="$ROOT/build-tcon-top-618.log"
echo "Incremental build: $LOG"
if ! make -C "$SRC" O="$ROOT/obj" ARCH=arm64 \
    CROSS_COMPILE=aarch64-linux-gnu- -j"${JOBS:-4}" Image modules >"$LOG" 2>&1; then
  echo "First compiler errors:"
  grep -n -m 40 -E 'fatal error:|error:|undefined reference|No rule to make target' "$LOG" || :
  tail -25 "$LOG"
  exit 1
fi
mkdir -p "$ROOT/artifacts"
cp "$ROOT/obj/arch/arm64/boot/Image" "$ROOT/artifacts/Image-618-vendor-hdmi"
sha256sum "$ROOT/artifacts/Image-618-vendor-hdmi"
echo "Compile complete. UART and HDMI hardware validation pending."
