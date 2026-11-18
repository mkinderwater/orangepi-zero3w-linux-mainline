#!/usr/bin/env python3
"""Stage a PCK-600-only DTB from the proven RAM-B DTB (never edit baseline).

Requires a named PCK clock in the modern A733 R-CCU binding. Refuses to
guess vendor R-CCU specifier 0x13 or phandle 0x27. No HDMI/DE consumers.
"""
import argparse
from pathlib import Path
import re
import shutil
import subprocess

def cmd(*args):
    return subprocess.check_output([str(x) for x in args],text=True).strip()

def put(*args):
    subprocess.check_call([str(x) for x in args])

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--baseline",type=Path,default=Path("/home/ram-b-clock-test/sun60i-a733-orangepi-zero3w-ram-b-26mhz-test.dtb"))
    p.add_argument("--root",type=Path,default=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4"))
    p.add_argument("--clock-symbol",help="Explicit R-CCU PCK binding symbol; verified by header")
    p.add_argument("--output",type=Path,default=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/ram-b-26mhz-pck600-probe.dtb"))
    a=p.parse_args()
    for executable in ("fdtget","fdtput","dtc","sha256sum"):
        if not shutil.which(executable): p.error(f"Missing {executable} (install device-tree-compiler)")
    bindings=a.root/"linux/include/dt-bindings/clock/allwinner,sun60i-a733-r-ccu.h"
    driver=a.root/"linux/drivers/clk/sunxi-ng/ccu-sun60i-a733-r.c"
    pck=a.root/"linux/drivers/pmdomain/sunxi/sun55i-pck600.c"
    for file in (a.baseline,bindings,driver,pck):
        if not file.is_file(): p.error(f"Missing {file}")
    if a.output.exists(): p.error(f"Refusing to overwrite existing DTB: {a.output}")
    expected="1ff786ed912df7d4b4d19e366b3c968a5e0552c39f58d61a8414514eba141d9d"
    import hashlib
    actual=hashlib.sha256(a.baseline.read_bytes()).hexdigest()
    if actual != expected: p.error(f"STOP: DTB is not the SHA-verified RAM-B baseline: {actual}")
    if 'a733_parent_syscon_resource' not in pck.read_text():
        p.error("STOP: updated A733 parent-syscon driver not present")
    rx=re.compile(r'^\s*#define\s+(CLK_[A-Za-z0-9_]*PCK[A-Za-z0-9_]*)\s+(0x[0-9a-fA-F]+|\d+)\b',re.M)
    symbols={n:int(v,0) for n,v in rx.findall(bindings.read_text())}
    if not symbols:
        p.error("No modern R-CCU PCK clock symbol exists. STOP. Inspect vendor clock register and integrate before DTB staging.")
    if a.clock_symbol:
        if a.clock_symbol not in symbols: p.error(f"Unknown --clock-symbol; candidates: {symbols}")
        selected=a.clock_symbol
    elif len(symbols)==1:
        selected=next(iter(symbols))
    else:
        p.error(f"Ambiguous PCK clock symbols, supply verified --clock-symbol: {symbols}")
    if selected not in driver.read_text():
        p.error(f"STOP: {selected} not referenced in R-CCU driver. Not a proven clock provider.")
    soc="/soc@0"
    rccu="/soc@0/clock-controller@7010000"
    parent=soc+"/pck-600@7060000"
    child=parent+"/power-controller"
    try: phandle=int(cmd("fdtget","-t","x",a.baseline,rccu,"phandle"),16)
    except Exception as e: p.error(f"Unable to resolve modern R-CCU phandle from baseline: {e}")
    a.output.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(a.baseline,a.output)
    try:
        put("fdtput","-c",a.output,parent)
        put("fdtput","-t","s",a.output,parent,"compatible","allwinner,sun60iw2-pck","syscon","simple-mfd")
        put("fdtput","-t","x",a.output,parent,"reg","0x7060000","0xb000")
        put("fdtput","-c",a.output,child)
        put("fdtput","-t","s",a.output,child,"compatible","allwinner,sun60iw2-pck-600")
        put("fdtput","-t","x",a.output,child,"clocks",hex(phandle),hex(symbols[selected]))
        put("fdtput","-t","s",a.output,child,"clock-names","pck")
        put("fdtput","-t","x",a.output,child,"#power-domain-cells","0x1")
        put("fdtput","-t","x",a.output,child,"#address-cells","0x1")
        put("fdtput","-t","x",a.output,child,"#size-cells","0x0")
        # Only display-facing domains. Do not initialize undeclared GPU_CORE.
        for name,num in (("pd_de_sys@1",1),("pd_vo@9",9),("pd_vo1@a",10)):
            path=child+"/"+name
            put("fdtput","-c",a.output,path)
            put("fdtput","-t","x",a.output,path,"reg",hex(num))
        cmd("dtc","-q","-I","dtb","-O","dtb","-o","/dev/null",a.output)
    except Exception:
        a.output.unlink(missing_ok=True)
        raise
    sha=hashlib.sha256(a.output.read_bytes()).hexdigest()
    print(f"BASELINE SHA256: {actual}")
    print(f"CANDIDATE SHA256: {sha}")
    print(f"PCK clock: {selected} id={symbols[selected]} provider phandle=0x{phandle:x}")
    print(f"PCK-only DTB: {a.output}")
    print("CAUTION: Clock symbol exists but hardware register equivalence is unverified.")
    print("This DTB may cause PCK probe writes to display power-domain delay registers.")
    print("Do not use until the R-CCU PCK clock register is compared to vendor source.")
    print("No firmware, bootloader, baseline DTB, or display graph altered.")

if __name__=="__main__":
    main()
