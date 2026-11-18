#!/usr/bin/env python3
"""Fail-closed activation gate for experimental A733 v20 IOMMU.

This checks provenance and known source hazards. It DOES NOT prove safety.
Never invoke this as a substitute for board-level safety review.
"""
from __future__ import annotations
import argparse,hashlib,pathlib,re,sys

BASE=pathlib.Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts")
EXPECTED={
    "sunxi-iommu-v2.c":"aa78ce2829693be1c27e93647244f50dd86dc4f386930b2301ba8990b7d19b53",
    "sunxi-iommu-pgtable.c":"aacc30517e7101177d55f4c67bbeaa4ab6ae7f70a4d15eecf9ab81197fdd6017",
}
COMBINED="495096f27313a88a758d049832a65949dac5ae88e97338bc660c243eb93c0d84"

def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):h.update(block)
    return h.hexdigest()

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--source-dir",type=pathlib.Path,default=BASE/"iommu-v20-port-stage1-kcflags/linux/drivers/iommu/aw-v20")
    a.add_argument("--linked-object",type=pathlib.Path,default=BASE/"iommu-v20-linkage-stage4/iommu-v20-combined.o")
    a.add_argument("--report",type=pathlib.Path,default=BASE/"iommu-v20-activation-gate.txt")
    args=a.parse_args()
    if args.report.exists():
        sys.exit("STOP: report already exists; use a fresh --report")
    lines=["A733 v20 IOMMU activation gate","RESULT: BLOCKED (fail-closed; no runtime validation)"]
    failures=[]
    for name,expected in EXPECTED.items():
        p=args.source_dir/name
        if not p.is_file():
            failures.append(name+" missing")
            continue
        actual=sha(p)
        lines.append(name+": "+actual)
        if actual!=expected:
            failures.append(name+" source hash changed; re-audit required")
    if not args.linked_object.is_file():
        failures.append("combined relocatable object missing")
    else:
        actual=sha(args.linked_object)
        lines.append("combined SHA256: "+actual)
        if actual!=COMBINED:
            failures.append("combined artifact differs from audited baseline")
    if not failures:
        driver=(args.source_dir/"sunxi-iommu-v2.c").read_text(errors="replace")
        pg=(args.source_dir/"sunxi-iommu-pgtable.c").read_text(errors="replace")
        checks={
            "B1 singleton global domain allocation":bool(re.search(r"if\s*\(global_iommu_domain\)\s*return\s+global_iommu_domain",driver)),
            "B3 init error logged without unwind":bool(re.search(r"if\s*\(sunxi_iommu_hw_init\(&sunxi_domain->domain\)\)\s*pr_err",driver)),
            "B4 attach always succeeds":bool(re.search(r"static\s+int\s+sunxi_iommu_attach_dev\([^}]+return\s+0;",driver,re.S)),
            "B2 physical address passed as DMA handle":bool(re.search(r"dma_sync_single_for_(?:cpu|device)\s*\([^;]*virt_to_phys\(",pg,re.S)),
            "B6 page-directory pointer synchronized for PT_SIZE":bool(re.search(r"dma_sync_single_for_cpu\s*\([^;]*virt_to_phys\(dent\)\s*,\s*PT_SIZE",pg,re.S)),
        }
        for key,detected in checks.items():
            lines.append(("CONFIRMED" if detected else "NOT DETECTED, MANUAL REVIEW STILL REQUIRED")+": "+key)
        failures.append("No approved domain lifetime/DMA design or hardware safety validation")
    else:
        lines += ["PROVENANCE FAILURE: "+x for x in failures]
    lines += [
      "ACTIVATION PROHIBITED: source-only compile/link tests are not sufficient.",
      "The gate intentionally never returns an activation PASS.",
      "No boot image, DTB, firmware or Linux kernel sources changed."
    ]
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text("\n".join(lines)+"\n")
    print("\n".join(lines))
    print("REPORT:",args.report)
    sys.exit(2)
if __name__=="__main__":
    main()
