#!/usr/bin/env python3
"""Read-only Stage 12 A733 v20 IOMMU callback audit for Linux 6.18.

Extracts complete C callback bodies using brace matching and includes
short kernel-core group lifecycle excerpts. No source, DTB or boot mutation.
"""
import argparse
import hashlib
import re
import sys
from pathlib import Path

BASE=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts")
DEFAULT_KERNEL=BASE/"iommu-v20-port-stage1-kcflags/linux"
DRIVER_SHA="aa78ce2829693be1c27e93647244f50dd86dc4f386930b2301ba8990b7d19b53"
CORE_SHA="f130ba36dcb140e3e749f3cb77ca7a2df15033843d4d15ae55b8803fa60f2082"
VENDOR_CALLBACKS=(
    "sunxi_iommu_domain_alloc_paging",
    "sunxi_iommu_domain_free",
    "sunxi_iommu_attach_dev",
    "sunxi_iommu_device_group",
    "sunxi_iommu_of_xlate",
    "sunxi_iommu_probe_device",
    "sunxi_iommu_probe_device_finalize",
    "sunxi_iommu_release_device",
    "sunxi_iommu_probe",
    "sunxi_iommu_remove",
    "sunxi_iommu_hw_init",
)
CORE_CALLBACKS=(
    "__iommu_probe_device",
    "iommu_setup_default_domain",
    "__iommu_group_set_domain_internal",
    "__iommu_device_set_domain",
    "__iommu_group_remove_device",
)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def function_body(source,name):
    # Return only C definitions, not calls/prototypes. Exclude comment matches
    # by requiring a signature followed by an opening brace, within 600 chars.
    patt=re.compile(r"(?m)^[ \t]*(?:static\s+)?(?:[A-Za-z_][\w\s*]*?\s+)?\**"+re.escape(name)+r"\s*\(")
    for match in patt.finditer(source):
        start=match.start()
        paren=source.find("(",match.start())
        level=0
        pos=paren
        while pos<len(source):
            ch=source[pos]
            if ch=="(":level+=1
            elif ch==")":
                level-=1
                if level==0:break
            pos+=1
        if pos>=len(source) or pos-paren>650:continue
        brace=re.match(r"\s*\{",source[pos+1:])
        if not brace:continue
        open_at=pos+1+brace.start()+len(brace.group(0))-1
        level=0
        for end in range(open_at,len(source)):
            if source[end]=="{":level+=1
            if source[end]=="}":
                level-=1
                if level==0:
                    lo=source.rfind("\n",0,start)+1
                    hi=end+1
                    return (source.count("\n",0,lo)+1,
                            source.count("\n",0,hi)+1,
                            source[lo:hi])
    return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--kernel",type=Path,default=DEFAULT_KERNEL)
    ap.add_argument("--out",type=Path,default=BASE/"iommu-v20-stage12-callbacks.txt")
    args=ap.parse_args()
    if args.out.exists():ap.error("report exists, use another --out")
    sources={
        "vendor":args.kernel/"drivers/iommu/aw-v20/sunxi-iommu-v2.c",
        "core":args.kernel/"drivers/iommu/iommu.c",
    }
    for key,expected in (("vendor",DRIVER_SHA),("core",CORE_SHA)):
        if not sources[key].is_file() or sha(sources[key])!=expected:
            ap.error("incorrect or missing "+key+" file: "+str(sources[key]))
    sections=["Stage12 A733 v20 Linux6.18 callback lifecycle evidence",
              "READ ONLY; NO DRIVER PATCH; ACTIVATION BLOCKED"]
    missing=[]
    for key,names in (("vendor",VENDOR_CALLBACKS),("core",CORE_CALLBACKS)):
        src=sources[key].read_text()
        sections.extend(["","SOURCE "+str(sources[key]),"SHA256 "+sha(sources[key])])
        for name in names:
            got=function_body(src,name)
            if not got:
                missing.append(key+":"+name)
                sections.extend(["","MISSING "+name])
            else:
                start,end,body=got
                sections.extend(["","=== "+key+" "+name+" lines "+str(start)+"-"+str(end)+" ===",body])
    sections.extend(["","MISSING_CALLBACKS "+str(len(missing)),*missing,
                     "Review group sharing, first attach, fallback, release, and multi-master ownership.",
                     "DO NOT ENABLE HARDWARE."])
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text("\n".join(sections)+"\n")
    print("REPORT:",args.out)
    print("CALLBACKS:",len(VENDOR_CALLBACKS)+len(CORE_CALLBACKS))
    print("MISSING:",len(missing))
    if missing:sys.exit("FAIL CLOSED: missing callbacks; audit report for naming differences")
if __name__=="__main__":main()
