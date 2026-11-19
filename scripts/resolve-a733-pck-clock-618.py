#!/usr/bin/env python3
"""Resolve the PCK-600 clock from vendor R-CCU numeric ID 19.

Read-only. Trace vendor ID -> binding name -> R-CCU onecell variable ->
register definition. Compare source register offsets to Linux 6.18 A733
R-CCU. Do not assume matching numeric IDs mean matching clock functions.
"""
import argparse
from pathlib import Path
import re

VENDOR = Path("/root/opi3w-vendor-6698-work/kernel")
MAIN = Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/linux")
RE_DEFINE = re.compile(r"^\s*#define\s+(CLK_[A-Za-z0-9_]+)\s+(0x[0-9A-Fa-f]+|\d+)\b", re.M)
RE_ONECELL = re.compile(r"\[\s*(CLK_[A-Za-z0-9_]+)\s*\]\s*=\s*&\s*([A-Za-z0-9_]+)\s*\.", re.M)

def bindings(path):
    return {name: int(value, 0) for name,value in RE_DEFINE.findall(path.read_text(errors="replace"))}

def definitions(path):
    lines=path.read_text(errors="replace").splitlines()
    cells=dict(RE_ONECELL.findall("\n".join(lines)))
    details={}
    for name,var in cells.items():
        # Variable declaration can span multiple lines. Capture its initializer
        # only, avoiding the unrelated adjacent register definitions.
        for index,line in enumerate(lines):
            if (re.search(r"\b" + re.escape(var) + r"\b", line)
                    and ("static " in line or "SUNXI_CCU_" in line)):
                chunk="\n".join(lines[index:index+18])
                # Stop after first semicolon (typically end of clock declaration).
                chunk=chunk.split(";",1)[0]+";"
                offsets=re.findall(r"0x[0-9a-fA-F]{3,}",chunk)
                bits=re.findall(r"BIT\(\s*\d+\s*\)",chunk)
                details[name]=(var,offsets,bits,chunk)
                break
    return cells,details

def report_side(title,bind,driver,focus,output):
    output.append("=== "+title+" ===")
    output.append("Binding: "+str(bind))
    output.append("Driver: "+str(driver))
    symbols=bindings(bind)
    cells,defs=definitions(driver)
    output.append(f"Binding symbols={len(symbols)}; onecell assignments={len(cells)}")
    reverse={v:k for k,v in symbols.items()}
    focus_name=reverse.get(focus)
    output.append(f"Clock ID {focus} symbol: {focus_name or 'NO SYMBOL'}")
    relevant=set()
    if focus_name: relevant.add(focus_name)
    relevant.update(n for n in symbols if
        re.search(r"PCK|BUS_R|AHB|APB|SYS_?24|PCK600|PLL_PERI",n,re.I))
    for name in sorted(relevant, key=lambda n:(n!=focus_name,n)):
        value=symbols[name]
        output.append(f"\n{name} = {value}")
        if name not in cells:
            output.append("  NOT IN onecell assignments")
            continue
        var=cells[name]
        output.append("  onecell = "+var)
        if name not in defs:
            output.append("  CLOCK DEFINITION NOT LOCATED: inspect driver")
            continue
        _,offsets,bits,chunk=defs[name]
        output.append("  offsets="+repr(offsets)+" bits="+repr(bits))
        output.append("  definition: "+chunk.replace("\n"," ")[:650])
    return symbols,cells,defs,focus_name

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--vendor",type=Path,default=VENDOR)
    ap.add_argument("--mainline",type=Path,default=MAIN)
    ap.add_argument("--output",type=Path,default=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/provider-compat/pck-clock-register-map.txt"))
    a=ap.parse_args()
    vendor_bind=a.vendor/"bsp/include/dt-bindings/clock/sun60iw2-r-ccu.h"
    main_bind=a.mainline/"include/dt-bindings/clock/allwinner,sun60i-a733-r-ccu.h"
    vendor_drv=a.vendor/"bsp/drivers/clk/sunxi-ng/ccu-sun60iw2-r.c"
    main_drv=a.mainline/"drivers/clk/sunxi-ng/ccu-sun60i-a733-r.c"
    for file in (vendor_bind,main_bind,vendor_drv,main_drv):
        if not file.is_file(): ap.error(f"Missing required clock source: {file}")
    result=["Vendor PCK-600 clock mapping (READ ONLY)", "PCK child clocks=<R-CCU 0x13> in vendor DTB", ""]
    vs,vc,vd,vname=report_side("VENDOR",vendor_bind,vendor_drv,19,result)
    ms,mc,md,mname=report_side("LINUX 6.18",main_bind,main_drv,19,result)
    result.append("\n=== register-offset comparisons for vendor PCK clock ===")
    if not vname:
        result.append("STOP: vendor binding has no symbol for ID 19.")
    elif vname not in vd:
        result.append("STOP: vendor onecell definition for ID 19 not resolved.")
    else:
        name,offsets,bits,_=vd[vname]
        result.append(f"Vendor ID 19 = {vname} -> {name}, offsets={offsets}, bits={bits}")
        matched=[]
        for k,(var,registers,gates,chunk) in md.items():
            common={int(x, 16) for x in offsets} & {int(x, 16) for x in registers}
            if common:
                matched.append((k,ms.get(k),var,[hex(x) for x in sorted(common)],gates))
        for k,value,var,common,gates in matched:
            result.append(f"Candidate: {k} id={value}, variable={var}, shared offsets={common}, gate bits={gates}")
        if not matched:
            result.append("STOP: no equivalent modern R-CCU clock register found by offset.")
        else:
            result.append("Candidates require matching register gate bits and acknowledgement of parent-clock differences.")
    result.append("Never change working RAM-B DTB or firmware during clock investigation.")
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text("\n".join(result)+"\n")
    print("\n".join(result))
    print("\nReport: "+str(a.output))
if __name__=="__main__":
    main()
