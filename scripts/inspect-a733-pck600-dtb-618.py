#!/usr/bin/env python3
"""Check vendor A733 PCK-600 DT topology before the first provider smoke test.

Read-only: inspect vendor DTB decompilation, RAM-B DTS, and 6.18 driver.
Never copy raw vendor phandles to the RAM-B tree.
"""
import argparse
from pathlib import Path
import re

def parse_dts(path):
    nodes = {}
    stack = []
    acc = None
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if acc is not None:
            acc += " " + line
            if ";" not in line:
                continue
            line = acc
            acc = None
        opening = re.match(r"^([^{};]+?)\s*\{\s*$", line)
        if opening:
            stack.append(opening.group(1).strip())
            node = "/" + "/".join(x for x in stack if x != "/")
            nodes[node] = {}
            continue
        if line in ("};", "}") or line.startswith("};"):
            if stack:
                stack.pop()
            continue
        if not stack:
            continue
        if "=" in line and ";" not in line:
            acc = line
            continue
        m = re.match(r"^([\w,#.+-]+)\s*=\s*(.+);\s*$", line)
        if m:
            node = "/" + "/".join(x for x in stack if x != "/")
            nodes[node][m.group(1)] = m.group(2)
        elif line.endswith(";"):
            m = re.match(r"^([\w,#.+-]+);$", line)
            if m:
                node = "/" + "/".join(x for x in stack if x != "/")
                nodes[node][m.group(1)] = "(boolean)"
    return nodes

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--vendor",type=Path,default=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/vendor-dtb-topology/vendor-control.dts"))
    ap.add_argument("--baseline",type=Path,default=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/vendor-dtb-topology/ram-b.dts"))
    ap.add_argument("--driver",type=Path,default=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/linux/drivers/pmdomain/sunxi/sun55i-pck600.c"))
    ap.add_argument("--config",type=Path,default=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/obj/.config"))
    ap.add_argument("--output",type=Path,default=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/provider-compat/pck600-test-readiness.txt"))
    args=ap.parse_args()
    for p in (args.vendor,args.baseline,args.driver,args.config):
        if not p.is_file(): ap.error("Missing "+str(p))
    v,b=map(parse_dts,(args.vendor,args.baseline))
    lines=["A733 PCK-600 provider smoke-test readiness (READ ONLY)"]
    for label,tree in (("VENDOR",v),("RAM-B",b)):
        lines.append("\n=== "+label+" matching nodes and their parent nodes ===")
        targets=[path for path,props in tree.items() if
            ("pck-600" in props.get("compatible","").lower() or
             "pck-600" in path.lower() or
             "power-controller" in path.lower() or
             "rtc_ccu@" in path.lower() or
             "ccu@" in path.lower() or
             "clock-controller@" in path.lower())]
        displayed=set()
        for path in targets:
            for node in (path.rsplit("/",1)[0] or "/",path):
                if node in displayed or node not in tree: continue
                displayed.add(node)
                lines.append(node)
                for k,val in tree[node].items():
                    if k in ("compatible","reg","ranges","clock-names","clocks","resets",
                             "reset-names","#address-cells","#size-cells",
                             "#power-domain-cells","phandle","status","power-domains"):
                        lines.append("  "+k+" = "+val)
    driver=args.driver.read_text()
    conf=args.config.read_text()
    lines+=["\n=== Linux 6.18 driver contract ===",
            "CONFIG_SUN55I_PCK600=y: "+str("CONFIG_SUN55I_PCK600=y" in conf),
            "A733 compatible present: "+str("allwinner,sun60iw2-pck-600" in driver),
            "A733 11-domain descriptor present: "+str("sun60i_a733_pck600_desc" in driver),
            "Driver maps DT node resource 0 via devm_platform_ioremap_resource().",
            "Driver requires an accessible clock via devm_clk_get_enabled().",
            "Vendor hierarchical power-controller nodes may use a syscon parent, which",
            "is NOT automatically equivalent to a direct reg resource. Check this before",
            "binding the 6.18 driver; do not assume it will probe.",
            "STOP: no DTB staging or hardware writes performed."]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text("\n".join(lines)+"\n")
    print("\n".join(lines))

if __name__=="__main__":
    main()
