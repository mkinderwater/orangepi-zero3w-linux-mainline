#!/usr/bin/env python3
"""Read-only A733 IOMMU v20 domain lifetime and DMA audit, evidence first.

No kernel source modifications. Extracts bounded function bodies from the
exact staged source and verifies Stage 4 combined relocatable ELF SHA256.
"""
from __future__ import annotations
import argparse,hashlib,pathlib,re,sys,subprocess

BASE=pathlib.Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts")
EXPECTED_COMBINED="495096f27313a88a758d049832a65949dac5ae88e97338bc660c243eb93c0d84"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def excerpt(path, regex, pre=6, post=42, limit=12):
    lines=path.read_text(errors="replace").splitlines()
    hits=[i for i,line in enumerate(lines) if re.search(regex,line)]
    out=["SOURCE: "+str(path),"PATTERN: "+regex,"MATCHES: "+str(len(hits))]
    indices=set()
    for i in hits[:limit]:
        indices.update(range(max(0,i-pre),min(len(lines),i+post+1)))
    last=-2
    for i in sorted(indices):
        if i>last+1:out.append("...")
        out.append(f"{i+1:5}: {lines[i][:240]}")
        last=i
    if len(hits)>limit:out.append("TRUNCATED matches "+str(len(hits)-limit))
    return "\n".join(out)+"\n"
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--stage",type=pathlib.Path,default=BASE/"iommu-v20-port-stage1-kcflags/linux")
    p.add_argument("--combined",type=pathlib.Path,default=BASE/"iommu-v20-linkage-stage4/iommu-v20-combined.o")
    p.add_argument("--out",type=pathlib.Path,default=BASE/"iommu-v20-lifecycle-dma-audit.txt")
    a=p.parse_args()
    if a.out.exists():sys.exit("STOP: destination exists; specify fresh --out")
    if not a.combined.is_file() or sha(a.combined)!=EXPECTED_COMBINED:
        sys.exit("STOP: combined Stage4 relocatable ELF differs from verified evidence")
    d=a.stage/"drivers/iommu/aw-v20"
    ptable=d/"sunxi-iommu-pgtable.c"
    driver=d/"sunxi-iommu-v2.c"
    header=d/"sunxi-iommu-pgtable.h"
    for source in (ptable,driver,header):
        if not source.is_file():sys.exit("STOP: source missing "+str(source))
    out=[
        "A733 IOMMU v20 domain/DMA audit, read only",
        "Verified combined object SHA256: "+sha(a.combined),
        "STAGED SOURCE SHA256:",
        *[str(f)+" "+sha(f) for f in (driver,ptable,header)],
        "No runtime activation, no firmware or boot-image changes.\n"
    ]
    checks=[
        (driver,r"global_iommu_domain|sunxi_iommu_domain_alloc_paging|sunxi_iommu_domain_free|iommu_hw_init_flag",8,35,25),
        (driver,r"sunxi_iommu_attach_dev\(|sunxi_iommu_release_device\(|sunxi_iommu_remove\(|sunxi_iommu_remove_618\(",7,55,15),
        (driver,r"sunxi_iommu_map\(|sunxi_iommu_unmap\(|sunxi_iommu_iotlb_sync_map\(|sunxi_iommu_iotlb_sync\(",6,45,14),
        (ptable,r"dma_sync_single_for_cpu|dma_sync_single_for_device|dma_map_|dma_unmap_|__pa\(|virt_to_phys|sunxi_pgtable_alloc\(|sunxi_pgtable_free\(",8,17,30),
        (header,r"IOMMU_VA_BITS|SUNXI_PHYS_OFFSET|IOMMU_PD_SHIFT|IOMMU_PT_SHIFT|iommu_phy_to_cpu_phy|cpu_phy_to_iommu_phy",4,10,20),
    ]
    for path,pattern,pre,post,limit in checks:
        out.append("\n=== CHECK ===\n"+excerpt(path,pattern,pre,post,limit))
    # Show symbol types as a lightweight signature of what the combined object defines.
    proc=subprocess.run(["aarch64-linux-gnu-nm","--defined-only",str(a.combined)],
                        text=True,capture_output=True)
    out.append("=== DEFINED SYMBOLS (first 150 lines) ===")
    out.extend(proc.stdout.splitlines()[:150])
    out.append("nm exit: "+str(proc.returncode))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text("\n".join(out)+"\n")
    print("READ-ONLY AUDIT:",a.out)
    print("LINES:",len(a.out.read_text().splitlines()))
    print("The report can be uploaded; no source files were changed.")
if __name__=="__main__":main()
