#!/usr/bin/env python3
"""Read-only vendor vs 6.18 A733 CCU clock source correlation.

Extracts clock binding -> provider variable from each driver onecell table,
then prints the variable's definition and nearby register expressions.
Output is evidence for manual equivalence checks, NOT an automatic mapping.
"""
from pathlib import Path
import argparse, re
DEFAULT_VENDOR=Path("/root/opi3w-vendor-6698-work/kernel/bsp/drivers/clk/sunxi-ng/ccu-sun60iw2.c")
DEFAULT_MAIN=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/linux/drivers/clk/sunxi-ng/ccu-sun60i-a733.c")
FOCUS = ("HDMI", "DPSS", "TCON", "VID_OUT", "DE_AHB", "MBUS_VO")
CLOCK_LOOKUP=re.compile(r'\[\s*(CLK_[A-Za-z0-9_]+)\s*\]\s*=\s*&\s*([A-Za-z0-9_]+)\s*\.\s*common\s*\.\s*hw')
def summarize(path):
    lines=path.read_text(errors="replace").splitlines()
    mapping={}
    for line in lines:
        m=CLOCK_LOOKUP.search(line)
        if m and any(token in m.group(1) for token in FOCUS):
            mapping[m.group(1)]=m.group(2)
    output=[f"=== {path} ===",f"Relevant onecell assignments: {len(mapping)}"]
    for symbol,var in sorted(mapping.items()):
        output.append(f"\n{symbol} -> {var}")
        matches=[i for i,line in enumerate(lines) if re.search(r'\b'+re.escape(var)+r'\b',line) and
                 (re.search(r'^\s*static\b',line) or re.search(r'\bSUNXI_CCU\b|\bSUNXI_CCU_GATE\b|\bSUNXI_CCU_M\b|\bSUNXI_CCU_MP\b',line))]
        if not matches:
            output.append("  NO obvious variable definition: inspect manually")
            continue
        i=matches[0]
        # Print only initialization context, typically holds register, gate and parents.
        output.extend(f"  {j+1}: {lines[j].strip()}" for j in range(i,min(len(lines),i+25))
                      if lines[j].strip() and not lines[j].strip().startswith("/*"))
    return output
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--vendor",type=Path,default=DEFAULT_VENDOR)
    ap.add_argument("--mainline",type=Path,default=DEFAULT_MAIN)
    ap.add_argument("--output",type=Path,default=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/register-equivalence/clock-definitions.txt"))
    args=ap.parse_args()
    for f in (args.vendor,args.mainline):
        if not f.is_file(): ap.error(f"Missing: {f}")
    rows=summarize(args.vendor)+["\n"]+summarize(args.mainline)
    rows+=["\nIMPORTANT: Same clock names/IDs are not proof of identical register programming.",
           "Compare CCU register offsets, mux parents, gates and resets before DTB staging."]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text("\n".join(rows)+"\n")
    print("Wrote",args.output)
    print("First relevant definitions:")
    for line in rows:
        if line.startswith("CLK_") or line.startswith("Relevant onecell") or line.startswith("==="):
            print(line)
if __name__=="__main__": main()
