#!/usr/bin/env python3
"""Compare vendor sun60iw2 vs 6.18 A733 display clock/reset *names*.

This is a semantic name-mapping aid, not proof that CCU programming matches.
Never transfer raw vendor IDs to an A733 DTB.
"""
from pathlib import Path
import argparse
import re

DEFAULT_VENDOR="/root/opi3w-vendor-6698-work/kernel/bsp/include/dt-bindings"
DEFAULT_MAIN="/root/opi3w-m2-work/linux-618-hdmi-stage4/linux/include/dt-bindings"
PAT = re.compile(r"^\s*#define\s+(CLK_[A-Za-z0-9_]+|RST_[A-Za-z0-9_]+)\s+(\d+|0x[0-9a-fA-F]+)\s*(?:/\*.*)?$")
TERMS=re.compile(r"HDMI|TCON|DE_|DPSS|VID_OUT|MBUS_VO|PLL_DE|VO_SYS",re.I)

def symbols(file):
    data={}
    for line in file.read_text(errors="replace").splitlines():
        match=PAT.match(line)
        if match:
            data[match.group(1)]=int(match.group(2),0)
    return data

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--vendor",type=Path,default=Path(DEFAULT_VENDOR))
    ap.add_argument("--mainline",type=Path,default=Path(DEFAULT_MAIN))
    ap.add_argument("--output",type=Path,default=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/display-binding-map.tsv"))
    a=ap.parse_args()
    pairs=[
      ("clock",a.vendor/"clock/sun60iw2-ccu.h",a.mainline/"clock/allwinner,sun60i-a733-ccu.h"),
      ("reset",a.vendor/"reset/sun60iw2-ccu.h",a.mainline/"reset/allwinner,sun60i-a733-ccu.h")
    ]
    rows=["kind\tsymbol\tvendor_id\tmainline_id\tstatus"]
    for kind,vfile,mfile in pairs:
        if not vfile.is_file() or not mfile.is_file():
            raise SystemExit(f"Missing binding: {vfile} or {mfile}")
        v,m=symbols(vfile),symbols(mfile)
        for name in sorted(set(v)|set(m)):
            if not TERMS.search(name): continue
            vi,mi=v.get(name),m.get(name)
            if vi is None: state="NEW_IN_618"
            elif mi is None: state="VENDOR_ONLY_REQUIRES_MAPPING"
            elif vi==mi: state="SAME_NUMBER_CHECK_IMPLEMENTATION"
            else: state="RENUMBERED_VERIFY_CLOCK_OR_RESET"
            rows.append(f"{kind}\t{name}\t{'' if vi is None else vi}\t{'' if mi is None else mi}\t{state}")
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text("\n".join(rows)+"\n")
    print("\n".join(rows))
    print(f"\nWrote: {a.output}")
    print("Next: map nonidentical names through CCU source registers; do not assume renumbered values are equivalent.")

if __name__=="__main__":
    main()
