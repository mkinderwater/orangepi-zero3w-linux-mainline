#!/usr/bin/env python3
"""Read-only investigation of Allwinner A733 U-Boot HDMI init before autoboot.

Locate the *actual* U-Boot source, extract callsites for display init,
hotplug detection and disabling firmware scanout. No patches or register writes.
"""
import argparse
import os
from pathlib import Path
import re

ROOTS=[Path("/root/opi3w-vendor-6698-work"),Path("/root/opi3w-m2-work"),
       Path("/root/orangepi-zero3w-linux-mainline"),Path("/root")]
KEYWORDS=[
    ("preprompt entry",r"board_late_init|board_init|main_loop|init_sequence|display_init|disp_init|sunxi.*hdmi.*init"),
    ("HDMI detection",r"hdmi.*(hpd|hotplug|detect|plug)|(?:hpd|hotplug).*hdmi|edid|drm_hdmi_get_mode"),
    ("HDMI clock",r"clk_set_rate|tcon.*hdmi.*set.rate|hdmi.*clk|hdmi.*pll|sunxi_de_add_kernel_iova_premap"),
    ("display controls",r"disp_mode|disp.*(disable|enable|off)|hdmi.*(disable|off)|boot.*logo|boot.*splash|disp_mode|boot_disp"),
    ("handoff",r"sunxi_drm_kernel_para_flush|fdt_add_subnode|sunxi.*display.*fixup|sunxi.*drm.*kernel"),
]
SOURCES={".c",".h",".S",".dts",".dtsi",".mk",".cfg",".env",".txt",".cmd"}
SKIP={"linux","kernel","node_modules",".git","build","obj","output","artifacts","vendor-6.6.98"}
MAX_DEPTH=9
def probable_tree(p):
    return (p/"common/main.c").is_file() and (p/"include/configs").is_dir() and (p/"drivers").is_dir()
def locate():
    found=[]
    checked=set()
    # User-host vendor source may be nested beneath an image-building tree.
    for base in ROOTS:
        if not base.is_dir():continue
        for root,dirs,files in os.walk(base):
            here=Path(root)
            try:depth=len(here.relative_to(base).parts)
            except ValueError:continue
            if depth>MAX_DEPTH:
                dirs[:]=[]
                continue
            dirs[:]=[d for d in dirs if d not in SKIP and not d.startswith(".")]
            if here.name in ("u-boot","uboot","u-boot-2018","uboot2018") or "u-boot" in here.name.lower():
                if probable_tree(here) and str(here) not in checked:
                    found.append(here);checked.add(str(here))
                if probable_tree(here):
                    dirs[:]=[]
    return found

def relevant_files(tree):
    # Only actual U-Boot source. Exclude binaries and huge generated config.
    prefixes=["board","common","cmd","drivers","arch/arm","include/configs","include"]
    seen=set()
    for prefix in prefixes:
        path=tree/prefix
        if not path.is_dir():continue
        for root,dirs,files in os.walk(path):
            here=Path(root)
            dirs[:]=[d for d in dirs if d not in SKIP and not d.startswith(".")]
            for name in files:
                p=here/name
                if p in seen or p.suffix not in SOURCES:continue
                seen.add(p)
                try:
                    if p.stat().st_size>2_500_000:continue
                except OSError:continue
                yield p

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,help="Exact vendor U-Boot 2018 source root")
    p.add_argument("--output",type=Path,default=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/uboot-hdmi-preprompt-audit.txt"))
    args=p.parse_args()
    candidates=[args.source] if args.source else locate()
    results=["A733 vendor U-Boot HDMI pre-prompt source audit (READ ONLY)",
             "Searches are code references, not proof of executed hardware path."]
    if not candidates:
        results+=["NO SOURCE TREE located automatically.",
                  "Find vendor U-Boot 2018 tree and rerun with --source /absolute/path/to/u-boot.",
                  "Do not infer firmware has no display-disable option from missing source."]
    for tree in candidates:
        results.append("\n=== U-Boot tree: "+str(tree)+" ===")
        if not probable_tree(tree):
            results.append("STOP: not an identifiable U-Boot source (common/main.c/include/configs/drivers absent)")
            continue
        files=list(relevant_files(tree))
        results.append(f"Source files searched: {len(files)}")
        matches={key:[] for key,_ in KEYWORDS}
        for file in files:
            try:lines=file.read_text(errors="replace").splitlines()
            except OSError:continue
            for n,line in enumerate(lines,1):
                for key,pattern in KEYWORDS:
                    if re.search(pattern,line,re.I):
                        matches[key].append((str(file.relative_to(tree)),n,line.strip()))
        for key,_ in KEYWORDS:
            results.append("\n--- "+key+f": {len(matches[key])} matches ---")
            for file,n,line in matches[key][:65]:
                results.append(f"{file}:{n}: {line[:250]}")
            if len(matches[key])>65:
                results.append(f"... {len(matches[key])-65} additional matches omitted")
        results+=["\nNEXT: trace board_init/late_init -> HDMI HPD -> framebuffer/splash setup",
                  "Locate a documented config option or environment flag checked BEFORE display initialization.",
                  "Do not disable clock/PHY or change Boot0/BL31 based on these grep matches alone."]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text("\n".join(results)+"\n")
    print("\n".join(results))
    print("\nReport:",args.output)
if __name__=="__main__":
    main()
