#!/usr/bin/env python3
"""Read-only A733 IOMMU v20 source/API/DT cross-check before any kernel port.

Inputs: existing vendor BSP, local 6.18 source, full vendor DTS and config.
Does not copy vendor code, enable DTB nodes, compile, or write to input trees.
"""
from pathlib import Path
import argparse,hashlib,re,subprocess
VENDOR_BASE=Path("/root/opi3w-vendor-6698-work/kernel")
LINUX_BASE=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/linux")
DTS_DEFAULT=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/vendor-dtb-topology/vendor-control.dts")
CONFIG_DEFAULT=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/Image-618-vendor-hdmi-pck600-syscon.config")
OUTPUT_DEFAULT=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/iommu-v20-source-crosscheck")
VENDOR_FILES=["bsp/drivers/iommu/Kconfig","bsp/drivers/iommu/Makefile",
"bsp/drivers/iommu/sunxi-iommu-v2.c","bsp/drivers/iommu/sunxi-iommu-common.c",
"bsp/drivers/iommu/sunxi-iommu-pgtable.c",
"bsp/drivers/iommu/sunxi-iommu-pgtable.h",
"bsp/drivers/iommu/sunxi-iommu.h"]
# Some standalone GitHub BSP checkouts locate this subtree under drivers/iommu;
# the local vendor kernel uses bsp/drivers/iommu. Validate paths explicitly.
LINUX_FILES=["drivers/iommu/sun50i-iommu.c","drivers/iommu/Kconfig",
"drivers/iommu/Makefile","drivers/iommu/dma-iommu.c","include/linux/iommu.h"]
SYMBOLS=["iommu_ops","iommu_domain_ops","domain_alloc_paging","domain_alloc",
"of_xlate","probe_device","release_device","def_domain_type","device_group",
"iommu_device_register","iommu_device_sysfs_add",
"iommu_dma_init_domain","iommu_get_dma_cookie","iommu_fwspec","map_pages","unmap_pages"]
def digest(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for data in iter(lambda:f.read(1024*1024),b""):h.update(data)
    return h.hexdigest()
def read(p):return p.read_text(errors="replace") if p.is_file() else ""
def run(*args):
    return subprocess.run(args,text=True,capture_output=True)
def pattern_lines(p,pattern,maxhits=15):
    rex=re.compile(pattern,re.I)
    hits=[f"{i}: {line.strip()[:180]}" for i,line in enumerate(read(p).splitlines(),1) if rex.search(line)]
    return hits[:maxhits],len(hits)
def main():
    a=argparse.ArgumentParser()
    a.add_argument("--vendor",type=Path,default=VENDOR_BASE)
    a.add_argument("--linux",type=Path,default=LINUX_BASE)
    a.add_argument("--vendor-dts",type=Path,default=DTS_DEFAULT)
    a.add_argument("--config",type=Path,default=CONFIG_DEFAULT)
    a.add_argument("--output",type=Path,default=OUTPUT_DEFAULT)
    x=a.parse_args()
    if x.output.exists():raise SystemExit("STOP: output exists; choose another --output")
    if not (x.vendor/"Makefile").is_file() or not (x.linux/"Makefile").is_file():
        raise SystemExit("STOP: vendor or Linux kernel source missing")
    # Verify the relevant local subtrees before generating a report.
    for item in VENDOR_FILES:
        if not (x.vendor/item).is_file():raise SystemExit("STOP: vendor file missing "+str(x.vendor/item))
    for item in LINUX_FILES:
        if not (x.linux/item).is_file():raise SystemExit("STOP: Linux file missing "+str(x.linux/item))
    if not x.vendor_dts.is_file():raise SystemExit("STOP: full vendor DTS missing")
    if not x.config.is_file():raise SystemExit("STOP: kernel config missing")
    x.output.mkdir(parents=True)
    report=[
        "# A733 IOMMU v20 integration cross-check",
        "",
        "STATUS: read-only source investigation; no driver integrated or run on hardware.",
        f"Vendor source root: {x.vendor}",
        f"Linux 6.18 source root: {x.linux}",
        "Upstream comparison: Linux 7.4 A733 CCU accepted commit 308e4087bbda.",
        "Mainline sun50i-iommu binds H6/H616; not an established compatible A733 v20 replacement.",
        "",
        "## Input source hashes",
    ]
    for rel in VENDOR_FILES:
        p=x.vendor/rel
        report.append(f"- Vendor {rel}: SHA256 {digest(p)}")
    for rel in LINUX_FILES:
        p=x.linux/rel
        report.append(f"- Linux {rel}: SHA256 {digest(p)}")
    report+=["","## Vendor Kconfig and build links"]
    for rel in VENDOR_FILES[:2]:
        hits,total=pattern_lines(x.vendor/rel,r"AW_IOMMU|IOMMU_SUPPORT|IOMMU_DMA|sunxi-iommu")
        report.append(f"### {rel} ({total} matches)")
        report.extend("- "+z for z in hits)
    report+=["","## Kernel config (actual compiled stage4)"]
    cfg=read(x.config)
    for item in ["IOMMU_SUPPORT","IOMMU_API","IOMMU_DMA","SUN50I_IOMMU",
                 "AW_IOMMU","AW_DRM","DRM","DRM_GEM_DMA_HELPER"]:
        match=re.search(r"^CONFIG_"+item+r"=(.+)$|^# CONFIG_"+item+r" is not set$",cfg,re.M)
        report.append("- CONFIG_"+item+": "+(match.group(0) if match else "not defined"))
    report+=["","## Vendor IOMMU API versus Linux 6.18 IOMMU framework"]
    v=x.vendor/"bsp/drivers/iommu/sunxi-iommu-v2.c"
    linux=x.linux/"include/linux/iommu.h"
    for term in SYMBOLS:
        ptn=r"\b"+re.escape(term)+r"\b"
        a_hits,a_total=pattern_lines(v,ptn,5)
        b_hits,b_total=pattern_lines(linux,ptn,3)
        report.append(f"### {term}: vendor {a_total} / Linux header {b_total} text matches")
        report.extend("- vendor "+z for z in a_hits)
        report.extend("- 6.18 header "+z for z in b_hits)
        if a_total and not b_total:
            report.append("- FLAG: vendor API reference not found in Linux public header; inspect function signature and replacements.")
    report+=["","## DT provider and display DMA consumers"]
    dts=read(x.vendor_dts).splitlines()
    terms=("iommu@3900000","iommu-v20","iommus =","iommu-master","sunxi-drm","de@5000000")
    for term in terms:
        idx=[i for i,line in enumerate(dts) if term in line]
        report.append(f"### {term}: {len(idx)} matches")
        for i in idx[:15]:
            report.extend(f"{k+1}: {dts[k][:200].strip()}" for k in range(max(0,i-1),min(len(dts),i+2)))
        if len(idx)>15:report.append(f"... {len(idx)-15} further matches")
    report+=["","## Mainline driver mismatch"]
    h=x.linux/"drivers/iommu/sun50i-iommu.c"
    hits,total=pattern_lines(h,r"\.compatible",20)
    report.extend("- "+s for s in hits)
    if "allwinner,iommu-v20" not in read(h):
        report.append("- Mainline driver lacks exact allwinner,iommu-v20 compatible. NOT_APPLICABLE without substantive hardware validation.")
    report+=["","## Evidence gates before port",
        "1. Verify vendor IOMMU v20 IRQ, 0x03900000 register layout, clocks/resets, 2-cell stream IDs, page-table address constraints.",
        "2. Inspect each vendor IOMMU API call against exact Linux 6.18 implementation (signatures and behavior), not name presence alone.",
        "3. Resolve DE352's iommus reference including its per-master specifiers and DMA-buf/GEM mapping semantics.",
        "4. Cross-check current A733 forks, upstream GitHub commits and mailing-list/Patchwork queues for later v20 drivers before patching.",
        "5. Do not automatically enable IOMMU or copy vendor numeric phandles, clocks or reset IDs.",
        "6. Prepare isolated kernel source changes with separate config, DTB and rollback controls, after review.",
        "",
        "SOURCE-ONLY; no device-tree or kernel modifications performed."]
    out=x.output/"summary.md"
    out.write_text("\n".join(report)+"\n")
    print("DONE:",out)
    print("Inputs verified:",len(VENDOR_FILES)+len(LINUX_FILES)+2)
    print("No source, DTB, image or firmware modified.")
if __name__=="__main__":
    main()
