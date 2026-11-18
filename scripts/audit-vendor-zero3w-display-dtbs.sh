#!/usr/bin/env bash
# Compare two compiled vendor Zero 3W DTBs and extract HDMI display topology.
# Read-only, no writes to boot media or original vendor files.
set -euo pipefail
ROOT=/root/opi3w-vendor-6698-work
NAME=arch/arm64/boot/dts/allwinner/sun60i-a733-orangepi-zero3w.dtb
A="$ROOT/obj-control/$NAME"
B="$ROOT/obj-identity/$NAME"
BASE=/home/ram-b-clock-test/sun60i-a733-orangepi-zero3w-ram-b-26mhz-test.dtb
OUT=/root/opi3w-m2-work/linux-618-hdmi-stage4/vendor-dtb-topology
for cmd in dtc fdtget sha256sum diff python3; do
  command -v "$cmd" >/dev/null || { echo "Missing $cmd" >&2; exit 1; }
done
for f in "$A" "$B" "$BASE"; do
  [[ -r "$f" ]] || { echo "Missing $f" >&2; exit 1; }
done
mkdir -p "$OUT"
sha256sum "$A" "$B" "$BASE" | tee "$OUT/SHA256SUMS"
dtc -q -I dtb -O dts -o "$OUT/vendor-control.dts" "$A"
dtc -q -I dtb -O dts -o "$OUT/vendor-identity.dts" "$B"
dtc -q -I dtb -O dts -o "$OUT/ram-b.dts" "$BASE"
diff -u "$OUT/vendor-control.dts" "$OUT/vendor-identity.dts" > "$OUT/vendor-difference.patch" || :
python3 - "$OUT" <<'PY'
from pathlib import Path
import re, sys
out=Path(sys.argv[1])
key=re.compile(r'(?:allwinner,sunxi-drm|display-engine-v352|allwinner,tcon-(?:top|tv)|allwinner,sunxi-hdmi|img,gpu|img,img-rogue)',re.I)
def parse(text):
    # dtc-produced DTS only; brace accounting keeps nodes and property lines.
    blocks=[]
    stack=[]
    for no,line in enumerate(text.splitlines(),1):
        stripped=line.strip()
        if stripped.endswith('{'):
            title=stripped[:-1].strip()
            if title and title != '/':
                stack.append((title,no,[]))
            elif not stack:
                stack.append(('/',no,[]))
            continue
        if stripped.startswith('};'):
            if stack:
                title,start,lines=stack.pop()
                block=(title,start,lines)
                blocks.append(block)
                if stack:
                    stack[-1][2].append(f'child: {title}')
            continue
        if stack:
            stack[-1][2].append(stripped)
    return blocks

with (out/'display-nodes.txt').open('w') as log:
    for label in ('vendor-control','vendor-identity','ram-b'):
        text=(out/(label+'.dts')).read_text()
        blocks=parse(text)
        log.write(f'=== {label} ===\n')
        matches=[(title,start,lines) for title,start,lines in blocks
                 if any(key.search(x) for x in lines)]
        if not matches:
            log.write('No matching compatible node found\n')
        for title,start,lines in matches:
            log.write(f'node {title} (DTS line {start})\n')
            for x in lines:
                if x.startswith(('compatible =','status =','reg =','clocks =','clock-names =','resets =','reset-names =','power-domains =','phys =','phy-names =','ports','port@','remote-endpoint','phandle =','assigned-clocks =','assigned-clock-rates =','pinctrl-0 =')) or 'child: ' in x:
                    log.write('  '+x+'\n')
        log.write('\n')
PY
echo "Vendor DTS diff lines: $(wc -l < "$OUT/vendor-difference.patch")"
echo "=== display nodes ==="
cat "$OUT/display-nodes.txt"
echo "Analysis only. No DTB has been changed or made bootable."
