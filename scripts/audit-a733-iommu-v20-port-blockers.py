#!/usr/bin/env python3
"""Extract bounded, exact A733 vendor IOMMU port blockers (read only)."""
import argparse, pathlib,re,hashlib
V=pathlib.Path("/root/opi3w-vendor-6698-work/kernel/bsp/drivers/iommu")
L=pathlib.Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/linux")
O=pathlib.Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/iommu-v20-port-blockers.txt")
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def matched(path,expr,context=3,limit=15):
    rows=path.read_text(errors="replace").splitlines()
    ids=[i for i,l in enumerate(rows) if re.search(expr,l)]
    chosen=set()
    for i in ids[:limit]:
        chosen.update(range(max(0,i-context),min(len(rows),i+context+1)))
    out=[]
    last=-2
    for i in sorted(chosen):
        if i>last+1:out.append("  ...")
        out.append(f"  {i+1:4}: {rows[i][:180]}")
        last=i
    return f"{path} ({len(ids)} matches)\n"+"\n".join(out)
def main():
    a=argparse.ArgumentParser()
    a.add_argument("--vendor",type=pathlib.Path,default=V)
    a.add_argument("--linux",type=pathlib.Path,default=L)
    a.add_argument("--output",type=pathlib.Path,default=O)
    x=a.parse_args()
    if x.output.exists():raise SystemExit("STOP: report already exists; provide new --output")
    vf=["sunxi-iommu-pgtable.h","sunxi-iommu.h","sunxi-iommu-pgtable.c","sunxi-iommu-v2.c"]
    lf=["include/linux/iommu.h","drivers/iommu/dma-iommu.h",
        "drivers/iommu/sun50i-iommu.c"]
    for p in [*(x.vendor/n for n in vf),*(x.linux/n for n in lf)]:
        if not p.is_file():raise SystemExit("STOP: missing "+str(p))
    sections=["# A733 IOMMU v20 exact source blocker report",
              "Source-only review. No file modifications, no build or flash.",
              "## Hashes"]
    for n in vf:sections.append("Vendor "+n+" SHA256 "+sha(x.vendor/n))
    for n in lf:sections.append("Linux "+n+" SHA256 "+sha(x.linux/n))
    sections+=["\n## Vendor page-table header (COMPLETE, avoid guessed bit widths)",
               (x.vendor/vf[0]).read_text(errors="replace")[:16000],
               "\n## Vendor hardware constants, includes and preprocessing"]
    for n in vf[1:]:
        sections.append(matched(x.vendor/n,
             r"IOMMU_VA_BITS|IOMMU_PT_MASK|SPAGE_SIZE|SPD_SIZE|SPAGE_ALIGN|AW_IOMMU_PGTABLE|#include|#if|#define SEPERATE_DOMAIN_API|#define COOKIE_HANDLE_BY_CORE",1,28))
    sections+=["\n## Vendor API signatures and conditional implementation"]
    sections.append(matched(x.vendor/"sunxi-iommu-v2.c",
        r"sunxi_iommu_domain_alloc|sunxi_iommu_map\(|sunxi_iommu_unmap\(|sunxi_iommu_iotlb_sync_map\(|sunxi_iommu_of_xlate\(|sunxi_iommu_remove\(|sunxi_iommu_domain_ops|sunxi_iommu_ops|iommu_alloc_resv_region|dev_iommu_priv_",5,30))
    sections+=["\n## Target 6.18 API signatures and struct definitions"]
    sections.append(matched(x.linux/"include/linux/iommu.h",
        r"struct iommu_domain_ops \{|struct iommu_ops \{|struct iommu_iotlb_gather \{|iommu_alloc_resv_region|iommu_alloc_resv_region|dev_iommu_priv_|iommu_iotlb_gather_add_range",5,30))
    sections+=["\n## Relevant upstream-local reference methods"]
    sections.append(matched(x.linux/"drivers/iommu/sun50i-iommu.c",
         r"domain_alloc_paging\(|iommu_iotlb_sync_map\(|iommu_map\(|iommu_unmap\(|iommu_ops .*=",4,16))
    x.output.parent.mkdir(parents=True,exist_ok=True)
    x.output.write_text("\n".join(sections)+"\n")
    print("DONE:",x.output)
    print("Source and image unchanged. Upload report for exact API patch plan.")
if __name__=="__main__":main()
