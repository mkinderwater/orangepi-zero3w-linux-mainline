#!/usr/bin/env python3
"""Read-only Linux 6.18 A733 v20 domain contract check.

Checks the exact audited staged driver against the local Linux IOMMU core,
and refuses to treat a compile pass as a runtime lifecycle pass.
"""
from pathlib import Path
import argparse,hashlib,re,sys

D=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts")
K=D/"iommu-v20-port-stage1-kcflags/linux"
EXPECTED_DRIVER="aa78ce2829693be1c27e93647244f50dd86dc4f386930b2301ba8990b7d19b53"
EXPECTED_COMBINED="495096f27313a88a758d049832a65949dac5ae88e97338bc660c243eb93c0d84"
def hash_file(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def require(source, pattern, desc):
    if not re.search(pattern,source,re.S):
        raise ValueError("Contract marker absent: "+desc)
def main():
    a=argparse.ArgumentParser()
    a.add_argument("--kernel",type=Path,default=K)
    a.add_argument("--report",type=Path,default=D/"iommu-v20-stage7-contract.txt")
    args=a.parse_args()
    if args.report.exists():sys.exit("STOP: output exists; select new --report")
    iommu=args.kernel/"drivers/iommu/iommu.c"
    driver=args.kernel/"drivers/iommu/aw-v20/sunxi-iommu-v2.c"
    combined=D/"iommu-v20-linkage-stage4/iommu-v20-combined.o"
    for p in (iommu,driver,combined):
        if not p.is_file():sys.exit("STOP: missing "+str(p))
    if hash_file(driver)!=EXPECTED_DRIVER or hash_file(combined)!=EXPECTED_COMBINED:
        sys.exit("STOP: known source/ELF changed, re-audit required")
    core=iommu.read_text()
    v=driver.read_text()
    try:
        require(core,r"__iommu_paging_domain_alloc_flags\s*\(.*?domain\s*=\s*ops->domain_alloc_paging\(dev\)", "core allocates via domain_alloc_paging")
        require(core,r"void\s+iommu_domain_free\s*\(.*?domain->ops->free\(domain\)", "core frees each domain via callback")
        require(core,r"iommu_domain_init\(domain,\s*type,\s*ops\)", "core initializes returned domain")
        require(core,r"__iommu_attach_device\s*\(.*?domain->ops->attach_dev\(domain,\s*dev\)", "core calls attach_dev")
        require(v,r"if\s*\(global_iommu_domain\)\s*return\s+global_iommu_domain", "staged vendor aliasing")
        require(v,r"static\s+void\s+sunxi_iommu_domain_free\s*\(.*?kfree\(sunxi_domain\)", "vendor frees shared domain")
        require(v,r"static\s+int\s+sunxi_iommu_attach_dev\s*\(.*?return\s+0;", "vendor unconditional attach")
    except ValueError as e:
        sys.exit("STOP: "+str(e))
    report=[
      "A733 v20 Stage7: Linux 6.18 domain contract evidence",
      "Audited vendor SHA256: "+hash_file(driver),
      "Linux iommu.c SHA256: "+hash_file(iommu),
      "Combined ELF SHA256: "+hash_file(combined),
      "CORE: paging domain allocation delegates to ops->domain_alloc_paging(dev)",
      "CORE: each allocated domain receives core initialization and can be freed through domain->ops->free",
      "CORE: attach operation delegates to domain->ops->attach_dev",
      "VENDOR: same global_iommu_domain pointer can be returned to multiple allocations",
      "VENDOR: free path releases that allocation without core ownership awareness",
      "VENDOR: attach returns success without real domain binding",
      "DECISION: Do not repurpose a shared domain as multiple independent core-owned objects.",
      "DESIGN CANDIDATE: one owner per controller with per-group tracking, only after verification that hardware supports it.",
      "NEEDS: master-to-domain assignment register semantics, active domain arbitration, locking and init rollback.",
      "STATUS: BLOCKED. Stage 6 draft only compiles; not safe for runtime.",
      "No modifications to kernel source, DTB, firmware or boot image."
    ]
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text("\n".join(report)+"\n")
    print("\n".join(report))
    print("REPORT:",args.report)
if __name__=="__main__":main()
