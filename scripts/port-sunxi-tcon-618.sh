#!/usr/bin/env bash
# Linux 6.18 TCON platform driver compatibility. Stage4 source only.
set -euo pipefail
ROOT="${ROOT:-/root/opi3w-m2-work/linux-618-hdmi-stage4}"
SRC="$ROOT/linux"
TCON="$SRC/drivers/gpu/drm/sunxi_vendor/sunxi_device/sunxi_tcon.c"
[[ -f "$TCON" && -d "$ROOT/obj" ]] || { echo "Missing staged TCON or object tree" >&2; exit 1; }
python3 - "$TCON" <<'PY'
from pathlib import Path
import re
import sys
path = Path(sys.argv[1])
original = path.read_text()
s = original

if '#include <linux/platform_device.h>' not in s:
    matches = list(re.finditer(r'(?m)^#include\s+[<"][^>"]+[>"]\s*$', s))
    if not matches:
        raise SystemExit("STOP: no include section")
    first = matches[0]
    s = s[:first.start()] + '#include <linux/platform_device.h>\n' + s[first.start():]
    print("Added linux/platform_device.h")
else:
    print("linux/platform_device.h already present")

# If the callback still returns int, change only a trivial return-zero cleanup
# implementation. Nontrivial return paths stop rather than being discarded.
match = re.search(r'\b(?:static\s+)?int\s+sunxi_tcon_remove\s*\(\s*struct\s+platform_device\s*\*\s*\w+\s*\)', s)
if match:
    opening = s.find('{', match.end())
    if opening < 0:
        raise SystemExit("STOP: TCON remove function body not found")
    level = 0
    closing = None
    for i in range(opening, len(s)):
        if s[i] == '{':
            level += 1
        elif s[i] == '}':
            level -= 1
            if level == 0:
                closing = i
                break
    if closing is None:
        raise SystemExit("STOP: TCON remove braces not balanced")
    body = s[opening+1:closing]
    stripped, count = re.subn(r'\breturn\s+0\s*;\s*$', '', body)
    if count != 1 or re.search(r'\breturn\b', stripped):
        raise SystemExit("STOP: TCON remove has other return paths; inspect before porting")
    s = s[:opening+1] + stripped + s[closing:]
    old = match.group(0)
    s = s.replace(old, re.sub(r'\bint\b', 'void', old, count=1), 1)
    print("Converted sunxi_tcon_remove to void, preserved cleanup")
else:
    print("No int sunxi_tcon_remove definition detected; checking compiler")

if s != original:
    backup = path.with_name(path.name + '.pre-tcon-618')
    if backup.exists():
        raise SystemExit("STOP: existing source backup, refusing repeat edit")
    backup.write_text(original)
    path.write_text(s)
PY

LOG="$ROOT/build-tcon-618.log"
echo "Incremental compile log: $LOG"
if ! make -C "$SRC" O="$ROOT/obj" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- -j"${JOBS:-4}" Image modules >"$LOG" 2>&1; then
  echo "First compiler errors:"
  grep -n -m 35 -E 'fatal error:|error:|undefined reference|No rule to make target' "$LOG" || :
  tail -25 "$LOG"
  exit 1
fi
mkdir -p "$ROOT/artifacts"
cp "$ROOT/obj/arch/arm64/boot/Image" "$ROOT/artifacts/Image-618-vendor-hdmi"
sha256sum "$ROOT/artifacts/Image-618-vendor-hdmi"
echo "Compiled successfully; UART/HDMI hardware validation pending."
