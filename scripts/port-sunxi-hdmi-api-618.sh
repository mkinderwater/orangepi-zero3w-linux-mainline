#!/usr/bin/env bash
set -euo pipefail
ROOT=/root/opi3w-m2-work/linux-618-hdmi-stage4
SRC="$ROOT/linux"
HDMI="$SRC/drivers/gpu/drm/sunxi_vendor/sunxi_drm_hdmi.c"
[[ -f "$HDMI" && -d "$ROOT/obj" ]] || { echo "Missing Stage4 source"; exit 1; }
python3 - "$HDMI" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1]); original=p.read_text(); s=original
def sub_once(pattern,replacement,label):
    global s
    s,n=re.subn(pattern,replacement,s,count=1,flags=re.M)
    if n!=1: raise SystemExit("STOP: "+label+" matched "+str(n))
    print("Updated:",label)
cb=re.search(r'(?m)^\s*\.mode_valid\s*=\s*(\w+)\s*,',s)
if not cb: raise SystemExit("STOP: mode_valid callback missing")
name=cb.group(1)
pattern=r'(\benum\s+drm_mode_status\s+'+re.escape(name)+r'\s*\([^)]*?,\s*)(struct\s+drm_display_mode\s*\*\s*\w+\s*\))'
sub_once(pattern,r'\g<1>const \g<2>',"mode_valid const")
if re.search(r'\benum\s+drm_mode_status\s+'+re.escape(name)+r'\s*\([^)]*?,\s*struct\s+drm_display_mode\s*\*',s):
    raise SystemExit("STOP: old mode_valid signature still present")
patterns=[
 r'^\s*\w+->class\s*=\s*I2C_CLASS_DDC\s*;\s*$',
 r'^\s*\.class\s*=\s*I2C_CLASS_DDC\s*,\s*$',
]
matches=sum(len(re.findall(pat,s,re.M)) for pat in patterns)
if matches!=1: raise SystemExit("STOP: I2C_CLASS_DDC uses: "+str(matches))
for pat in patterns: s=re.sub(pat,"",s,flags=re.M)
print("Removed obsolete DDC class; adapter retained")
sub_once(r'\bstrlcpy\s*\(','strscpy(',"strlcpy API")
m=re.search(r'\bstatic\s+int\s+sunxi_hdmi_remove\s*\(\s*struct\s+platform_device\s*\*\s*\w+\s*\)',s)
if not m: raise SystemExit("STOP: HDMI remove declaration missing")
start=s.find("{",m.end()); depth=0; end=None
for i in range(start,len(s)):
    if s[i]=="{": depth+=1
    elif s[i]=="}":
        depth-=1
        if depth==0: end=i; break
if end is None: raise SystemExit("STOP: unbalanced remove")
body=s[start+1:end]
clean,n=re.subn(r'\breturn\s+0\s*;\s*$','',body)
if n!=1 or re.search(r'\breturn\b',clean):
    raise SystemExit("STOP: nontrivial HDMI remove; inspect source first")
s=s[:start+1]+clean+s[end:]
s=s.replace(m.group(0),m.group(0).replace('static int','static void',1),1)
print("Updated platform remove")
backup=p.with_suffix(".c.pre-hdmi-618")
if backup.exists(): raise SystemExit("STOP: backup already exists")
backup.write_text(original);p.write_text(s)
PY
LOG="$ROOT/build-hdmi-api-618.log"
echo "Incremental build: $LOG"
if ! make -C "$SRC" O="$ROOT/obj" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- -j4 Image modules >"$LOG" 2>&1; then
  grep -n -m 35 -E 'error:|fatal error:|undefined reference|No rule to make target' "$LOG" || :
  tail -20 "$LOG"
  exit 1
fi
mkdir -p "$ROOT/artifacts"
cp "$ROOT/obj/arch/arm64/boot/Image" "$ROOT/artifacts/Image-618-vendor-hdmi"
sha256sum "$ROOT/artifacts/Image-618-vendor-hdmi"
