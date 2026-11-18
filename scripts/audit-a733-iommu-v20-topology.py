#!/usr/bin/env python3
"""Read-only A733 IOMMU v20 master, context and DT topology audit.

Source inventory only. Does not make register/boot/DTB changes.
"""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import re
import sys

BASE=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts")
DEFAULT_KERNEL=BASE/"iommu-v20-port-stage1-kcflags/linux"
DEFAULT_VENDOR=Path("/root/opi3w-vendor-6698-work/kernel/bsp")
DRIVER_SHA="aa78ce2829693be1c27e93647244f50dd86dc4f386930b2301ba8990b7d19b53"
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def append_matches(output, path, patterns, context=5, limit=36):
    lines=path.read_text(errors="replace").splitlines()
    hits=[i for i,line in enumerate(lines) if any(re.search(pattern,line,re.I) for pattern in patterns)]
    output.extend(["FILE "+str(path),"SHA256 "+digest(path),"MATCH COUNT "+str(len(hits))])
    indices=set()
    for i in hits[:limit]:
        indices.update(range(max(0,i-context),min(len(lines),i+context+1)))
    last=-2
    for i in sorted(indices):
        if i>last+1:output.append("...")
        output.append(str(i+1)+": "+lines[i][:230])
        last=i
    if len(hits)>limit:output.append("TRUNCATED "+str(len(hits)-limit)+" matches")
    output.append("")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--kernel",type=Path,default=DEFAULT_KERNEL)
    p.add_argument("--vendor",type=Path,default=DEFAULT_VENDOR)
    p.add_argument("--out",type=Path,default=BASE/"iommu-v20-stage8-topology.txt")
    a=p.parse_args()
    if a.out.exists():sys.exit("STOP: report already exists, specify a fresh --out")
    driver=a.kernel/"drivers/iommu/aw-v20/sunxi-iommu-v2.c"
    if not driver.is_file() or digest(driver)!=DRIVER_SHA:
        sys.exit("STOP: staged driver does not match the audited SHA256")
    output=["A733 IOMMU v20 Stage 8 topology audit","READ ONLY; activation BLOCKED",
            "Kernel root "+str(a.kernel),"Vendor root "+str(a.vendor),""]
    paths=[driver]
    for f in ("sunxi-iommu.h","sunxi-iommu-pgtable.h"):
        pth=driver.parent/f
        if pth.is_file():paths.append(pth)
    vendor_iommu=a.vendor/"drivers/iommu"
    if vendor_iommu.exists():
        paths += [f for f in sorted(vendor_iommu.glob("*.h")) if f.name.startswith("sunxi")][:10]
    patterns=[r"IOMMU.*(TTB|TTBR|PGTABLE|MASTER|ENABLE|BYPASS|TLB|PTW|REG|ASID|DOMAIN|STREAM)",
              r"master_id|tlbid|skip_mask|iommus\s*=|iommu-map|iommu-cells",
              r"sunxi_iommu_(?:hw_init|enable_device_iommu|of_xlate|probe_device|probe)",
              r"\bWRITE_EQUAL_REG\b|\bwrite[lq]\("]
    for path in dict.fromkeys(paths):
        append_matches(output,path,patterns,3,46)
    dt_roots=[a.vendor/"arch/arm64/boot/dts",a.kernel/"arch/arm64/boot/dts"]
    dt_files=[]
    for root in dt_roots:
        if root.is_dir():
            dt_files.extend(p for p in root.rglob("*") if
                p.is_file() and p.suffix in (".dts",".dtsi") and
                any(word in p.name.lower() for word in ("a733","sun60","sunxi","orangepi")))
    dt_files=sorted(dict.fromkeys(dt_files))
    output.append("CANDIDATE DT FILES: "+str(len(dt_files)))
    scanned=0
    for path in dt_files[:150]:
        try:
            content=path.read_text(errors="replace")
        except OSError:
            continue
        if ("iommu" in content.lower() or "03900000" in content):
            append_matches(output,path,[r"iommu",r"03900000",r"de[0-9]?\s*:",r"display",r"\bmasters\b"],3,28)
            scanned+=1
    output.append("DT files containing IOMMU evidence: "+str(scanned))
    output.extend(["NO HARDWARE CONCLUSIONS: compare register programming to A733 manual/vendor DTS.",
        "NO SOURCE, DTB, IMAGE OR FIRMWARE MODIFICATIONS."])
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text("\n".join(output)+"\n")
    print("REPORT:",a.out)
    print("LINES:",len(output))
    print("READ ONLY: hardware activation remains BLOCKED")
if __name__=="__main__":main()
