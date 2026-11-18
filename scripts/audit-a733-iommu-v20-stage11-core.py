#!/usr/bin/env python3
"""Read-only Linux 6.18 IOMMU group lifecycle contract audit for A733 v20.

Inspects the exact local staged core and vendor driver. Does not build or
modify source, DTBs, firmware, boot images or hardware.
"""
from pathlib import Path
import argparse,hashlib,re,sys

BASE=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts")
K=BASE/"iommu-v20-port-stage1-kcflags/linux"
EXPECTED_DRIVER="aa78ce2829693be1c27e93647244f50dd86dc4f386930b2301ba8990b7d19b53"
EXPECTED_CORE="f130ba36dcb140e3e749f3cb77ca7a2df15033843d4d15ae55b8803fa60f2082"
EXPECTED_ELF="495096f27313a88a758d049832a65949dac5ae88e97338bc660c243eb93c0d84"
checks=[
 ("per-group default allocation", "core",r"__iommu_group_alloc_default_domain\s*\(.*?__iommu_paging_domain_alloc_flags\(dev,\s*req_type",True),
 ("first attach cannot fail contract", "core",r"Drivers are not allowed to fail the first domain attach",True),
 ("core pre-attach direct mappings", "core",r"iommu_create_device_direct_mappings\(dom,\s*gdev->dev\)",True),
 ("core group domain changes", "core",r"static int __iommu_group_set_domain_internal\s*\(.*?if\s*\(group->domain\s*==\s*new_domain\)",True),
 ("core attach error revert", "core",r"err_revert:\s*.*?__iommu_device_set_domain\(",True),
 ("core previous domain restoration", "core",r"err_restore_domain:\s*.*?__iommu_group_set_domain_internal\(",True),
 ("core default domain free old", "core",r"out_free_old:\s*if\s*\(old_dom\)\s*iommu_domain_free\(old_dom\)",True),
 ("core driver per-domain free", "core",r"void iommu_domain_free\s*\(.*?domain->ops->free\(domain\)",True),
 ("vendor singleton return hazard", "vendor",r"if\s*\(global_iommu_domain\)\s*return\s+global_iommu_domain",True),
 ("vendor global TTB write", "vendor",r"WRITE_EQUAL_REG\(iommu,\s*IOMMU_TTB_REG,\s*dte_addr\s*>>\s*14\)",True),
 ("vendor unqualified attach", "vendor",r"static\s+int\s+sunxi_iommu_attach_dev\s*\(.*?return\s+0\s*;",True),
]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--kernel",type=Path,default=K)
    ap.add_argument("--out",type=Path,default=BASE/"iommu-v20-stage11-core.txt")
    args=ap.parse_args()
    if args.out.exists():ap.error("output already exists, use a fresh --out")
    core=args.kernel/"drivers/iommu/iommu.c"
    vendor=args.kernel/"drivers/iommu/aw-v20/sunxi-iommu-v2.c"
    elf=BASE/"iommu-v20-linkage-stage4/iommu-v20-combined.o"
    for p,expected in ((core,EXPECTED_CORE),(vendor,EXPECTED_DRIVER),(elf,EXPECTED_ELF)):
        if not p.is_file():ap.error("missing "+str(p))
        if digest(p)!=expected:ap.error("SHA256 mismatch: "+str(p))
    src={"core":core.read_text(),"vendor":vendor.read_text()}
    rows=["Stage 11 Linux 6.18 group lifecycle contract check","READ ONLY","core_sha256="+digest(core),
          "vendor_sha256="+digest(vendor),"combined_elf_sha256="+digest(elf)]
    failed=[]
    for label,which,pat,required in checks:
        match=re.search(pat,src[which],re.S)
        if not match and required:failed.append(label)
        line=src[which].count("\n",0,match.start())+1 if match else "n/a"
        rows.append(("PASS" if match else "FAIL")+" "+label+" "+which+":"+str(line))
    rows+=["ARCHITECTURE BLOCK: core default domains are allocated per group, with first attach required to succeed.",
           "ARCHITECTURE BLOCK: one active TTB cannot silently back independent simultaneously attached page-table domains.",
           "ARCHITECTURE BLOCK: mapping setup may precede attachment, so lazy incompatible domain binding is not safe.",
           "MANDATORY: inspect group callback and all consumer groups; evaluate explicit limited-support model or refactor.",
           "NO DRIVER PATCH; NO MMIO; ACTIVATION BLOCKED."]
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text("\n".join(rows)+"\n")
    print("\n".join(rows))
    if failed:sys.exit("FAIL CLOSED: missing markers: "+", ".join(failed))
if __name__=="__main__":main()
