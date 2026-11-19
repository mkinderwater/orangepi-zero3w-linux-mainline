#!/usr/bin/env bash
# Extract actual Zero 3W vendor display graph, not a guessed A733 DT overlay.
# Read-only. Does not alter proven RAM-B DTB or vendor kernel.
set -euo pipefail
VENDOR="${VENDOR:-/root/opi3w-vendor-6698-work/kernel}"
BASE_DTB="${BASE_DTB:-/home/ram-b-clock-test/sun60i-a733-orangepi-zero3w-ram-b-26mhz-test.dtb}"
OUT="${OUT:-/root/opi3w-m2-work/linux-618-hdmi-stage4/display-graph}"
for cmd in dtc fdtget sha256sum python3; do
  command -v "$cmd" >/dev/null || { echo "Missing $cmd" >&2; exit 1; }
done
[[ -f "$VENDOR/arch/arm64/boot/dts/allwinner/sun60i-a733-orangepi-zero3w.dts" && -f "$BASE_DTB" ]] || {
  echo "Missing board vendor DTS or baseline DTB" >&2; exit 1;
}
mkdir -p "$OUT"
sha256sum "$BASE_DTB" > "$OUT/baseline.sha256"
fdtget -t u "$BASE_DTB" /osc-clk clock-frequency | grep -qx 26000000 || {
  echo "STOP: baseline does not contain verified 26 MHz clock" >&2; exit 1;
}
dtc -q -I dtb -O dts -o "$OUT/ram-b.dts" "$BASE_DTB"
# Find vendor DTBs. Do not assume vendor production DTB is byte-for-byte
# equivalent to an image currently booted by the device.
find "${VENDOR%/}" /root/opi3w-vendor-6698-work -type f \
  \( -name 'sun60i-a733-orangepi-zero3w.dtb' -o -name 'sun60i-a733-orangepi-zero3w*.dtb' \) \
  -print 2>/dev/null | sort -u > "$OUT/candidate-vendor-dtbs.txt"
if [[ -n "${VENDOR_DTB:-}" ]]; then
  [[ -f "$VENDOR_DTB" ]] || { echo "Requested VENDOR_DTB missing" >&2; exit 1; }
  sha256sum "$VENDOR_DTB" > "$OUT/vendor-selected.sha256"
  dtc -q -I dtb -O dts -o "$OUT/vendor-selected.dts" "$VENDOR_DTB"
fi
python3 - "$VENDOR" "$OUT" <<'PY'
from pathlib import Path
import re
import sys

vendor, out = map(Path, sys.argv[1:])
root = vendor / "arch/arm64/boot/dts/allwinner"
sources = [
    root / "sun60i-a733-orangepi-zero3w.dts",
    root / "sun60iw2p1.dtsi",
]
terms = re.compile(r"hdmi|tcon|display.engine|display-engine|drm|gpu|de352|de35|phy",re.I)
with (out / "source-references.txt").open("w") as stream:
    for file in sources:
        stream.write(f"=== {file} ===\n")
        lines = file.read_text(errors="replace").splitlines()
        for index,line in enumerate(lines):
            if terms.search(line) and not line.lstrip().startswith("//"):
                start=max(index-3,0); end=min(index+7,len(lines))
                stream.write(f"-- Line {index+1} --\n")
                for j in range(start,end):
                    stream.write(f"{j+1}: {lines[j]}\n")
    stream.write("\n=== Source files do not prove runtime hardware-enabled status. ===\n")
# If a vendor DTB is supplied, use its resolved phandle version for definitive
# node/property inventory. Never transplant phandle integers into RAM-B DTB.
for name in ("ram-b.dts","vendor-selected.dts"):
    file=out / name
    if not file.exists():
        continue
    src=file.read_text(errors="replace")
    hits=[]
    for line in src.splitlines():
        if terms.search(line):
            hits.append(line)
    (out / (name+".display-lines.txt")).write_text("\n".join(hits)+"\n")
PY
echo "=== Vendor display graph candidates ==="
cat "$OUT/candidate-vendor-dtbs.txt"
echo "=== Runtime graph references ==="
grep -nE -m 30 'hdmi|tcon|display-engine|sunxi-drm' "$OUT/ram-b.dts" || :
echo "=== Vendor source references ==="
head -110 "$OUT/source-references.txt"
echo "Report: $OUT"
echo "No DTB edits performed; a board-exact vendor DTB is needed to stage the graph with clock/reset remapping."
