#!/usr/bin/env python3
"""Stage 13 A733 v20 single-group ownership audit, READ ONLY.

Extract the actual Linux v6.18 group-reference contracts, as well as vendor
group callbacks and registration. Fail closed on source/hash mismatch.
"""
from pathlib import Path
import argparse,hashlib,re,sys
ROOT=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts")
K=ROOT/"iommu-v20-port-stage1-kcflags/linux"
HASHES={"core":"f130ba36dcb140e3e749f3cb77ca7a2df15033843d4d15ae55b8803fa60f2082",
        "vendor":"aa78ce2829693be1c27e93647244f50dd86dc4f386930b2301ba8990b7d19b53"}
CORE_NAMES=("iommu_init_device","iommu_deinit_device","iommu_group_get","iommu_group_put",
            "iommu_group_alloc","iommu_group_add_device","iommu_group_alloc_default_domain",
            "__iommu_group_alloc_default_domain","iommu_setup_default_domain",
            "iommu_probe_device",
            "iommu_release_device")
VENDOR_NAMES=("sunxi_iommu_device_group","sunxi_iommu_probe_device",
              "sunxi_iommu_probe_device_finalize","sunxi_iommu_release_device",
              "sunxi_iommu_domain_alloc_paging","sunxi_iommu_domain_free",
              "sunxi_iommu_attach_dev","sunxi_iommu_remove")
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def occurrences(src,name,context=4,limit=12):
    lines=src.splitlines()
    ids=[i for i,l in enumerate(lines) if re.search(r"\b"+re.escape(name)+r"\s*\(",l)]
    out=["REFERENCE "+name+" count="+str(len(ids))]
    for i in ids[:limit]:
        out.extend(str(j+1)+": "+lines[j][:200] for j in range(max(0,i-context),min(len(lines),i+context+1)))
        out.append("...")
    if len(ids)>limit:out.append("OMITTED "+str(len(ids)-limit)+" extra occurrences")
    return out, bool(ids)
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--kernel",type=Path,default=K)
    ap.add_argument("--out",type=Path,default=ROOT/"iommu-v20-stage13-group.txt")
    a=ap.parse_args()
    if a.out.exists():ap.error("output exists, specify a fresh --out")
    paths={"core":a.kernel/"drivers/iommu/iommu.c",
           "vendor":a.kernel/"drivers/iommu/aw-v20/sunxi-iommu-v2.c"}
    for k,p in paths.items():
        if not p.is_file() or digest(p)!=HASHES[k]:
            ap.error("missing or unaudited "+k+" file: "+str(p))
    out=["Stage13 A733 v20 Linux6.18 single-group lifetime audit",
         "READ ONLY; compile and activation NOT authorized"]
    missing=[]
    for k,names in (("core",CORE_NAMES),("vendor",VENDOR_NAMES)):
        text=paths[k].read_text()
        out.extend(["",k.upper()+" PATH "+str(paths[k]),"SHA256 "+digest(paths[k])])
        for name in names:
            lines,ok=occurrences(text,name)
            out.extend([""]+lines)
            if not ok:missing.append(k+":"+name)
    out.extend(["","MISSING "+str(len(missing)),*missing,
                "CHECK: Does group callback obtain one reference per device?",
                "CHECK: Is global_group reset only after the final group reference?",
                "CHECK: Is page-table/domain ownership valid across DMA->new domain changes?",
                "CHECK: Does finalize enable translation only AFTER verified attach?",
                "CHECK: Do controller removal and client release quiesce DMA and clear globals?",
                "IMPORTANT: Source inventory, NOT a runtime safety verdict.",
                "Hardware activation BLOCKED."])
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text("\n".join(out)+"\n")
    print("REPORT:",a.out,"MISSING:",len(missing))
    if missing:sys.exit("Missing named symbols: inspect report (some symbols may have been renamed)")
if __name__=="__main__":main()
