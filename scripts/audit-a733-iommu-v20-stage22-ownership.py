#!/usr/bin/env python3
"""A733 IOMMU v20 Stage22 source ownership audit.

Read-only; SHA-pins the staged driver and pgtable, also inspects the
independently generated Stage19 v2 and Stage20 page-table draft.
Outputs all ownership references, function bodies, and a no-false-pass gate.
Never changes source, compiled objects, device trees, boot images or MMIO.
"""
from pathlib import Path
import argparse
import hashlib
import re
import sys

ART=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts")
SRC=ART/"iommu-v20-port-stage1-kcflags/linux/drivers/iommu/aw-v20"
PIN={
    "driver":"aa78ce2829693be1c27e93647244f50dd86dc4f386930b2301ba8990b7d19b53",
    "pgtable":"aacc30517e7101177d55f4c67bbeaa4ab6ae7f70a4d15eecf9ab81197fdd6017",
}
NAMES={
    "driver":(
        "sunxi_iommu_domain_alloc_paging","sunxi_iommu_domain_free",
        "sunxi_iommu_attach_dev","sunxi_iommu_probe_device_finalize",
        "sunxi_iommu_release_device","sunxi_iommu_hw_init",
        "sunxi_iommu_map","sunxi_iommu_unmap","sunxi_iommu_iotlb_sync",
        "sunxi_iommu_probe","sunxi_iommu_remove"
    ),
    "pgtable":(
        "sunxi_pgtable_alloc","sunxi_pgtable_free",
        "sunxi_pgtable_alloc_pte_cache","sunxi_pgtable_free_pte_cache",
        "sunxi_pgtable_prepare_l1_tables","sunxi_pgtable_clear",
        "sunxi_pgtable_set_dma_dev"
    )
}
TOKENS={
    "driver":(
        "global_iommu_domain","global_iommu_dev",
        "iommu_hw_init_flag","global_group","sunxi_pgtable_alloc(",
        "sunxi_pgtable_free(","sunxi_iommu_hw_init(",
        "sunxi_tlb_flush(","IOMMU_TTB_REG","attach_dev",
        "domain_alloc_paging","domain_free","sunxi_iommu_map(",
        "sunxi_iommu_unmap(","sunxi_iommu_domain_ops",
    ),
    "pgtable":(
        "sunxi_pgtable_params.pgtable","sunxi_pgtable_params.iopte_cache",
        "sunxi_pgtable_params.dma_dev","kmem_cache_zalloc(",
        "kmem_cache_free(","kmem_cache_destroy(",
        "dma_sync_single_for_cpu(","dma_sync_single_for_device("
    )
}

def hashfile(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def definition(source,name):
    # Find function definitions with balanced parentheses and opening brace.
    # This is source extraction only; no correctness proof.
    rx=re.compile(r"(?m)^[ \t]*(?:(?:static|inline|const)[ \t]+)*"
                  r"[\w \t*]+?\b"+re.escape(name)+r"\s*\(")
    found=[]
    for m in rx.finditer(source):
        par=source.find("(",m.start())
        depth=0
        after=None
        for i in range(par,min(len(source),par+1500)):
            if source[i]=="(":depth+=1
            elif source[i]==")":
                depth-=1
                if depth==0:
                    after=i+1
                    break
        if after is None:continue
        q=re.match(r"\s*\{",source[after:])
        if not q:continue
        start=after+q.end()-1
        level=0
        for i in range(start,len(source)):
            if source[i]=="{":level+=1
            elif source[i]=="}":
                level-=1
                if not level:
                    lo=source.count("\n",0,m.start())+1
                    hi=source.count("\n",0,i)+1
                    found.append((lo,hi))
                    break
    return found

def inspect(key,path,report):
    src=path.read_text(errors="replace")
    lines=src.splitlines()
    report.extend(["",f"SOURCE {key} {path}",f"SHA256 {hashfile(path)}"])
    missing=[]
    for name in NAMES[key]:
        sections=definition(src,name)
        report.append(f"FUNCTION {name}: {len(sections)} definitions")
        if not sections:missing.append(name)
        for a,b in sections:
            report.append(f"BEGIN {name} L{a}-L{b}")
            report.extend(f"{n}: {lines[n-1]}" for n in range(a,b+1))
            report.append(f"END {name}")
    report.append("ALL GLOBAL/OPERATION REFERENCES")
    for token in TOKENS[key]:
        matches=[f"{i+1}: {line.strip()}" for i,line in enumerate(lines) if token in line]
        report.append(f"TOKEN {token} matches={len(matches)}")
        report.extend(matches)
    return missing

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source-dir",type=Path,default=SRC)
    ap.add_argument("--stage19",type=Path,
                    default=ART/"iommu-v20-stage19-lifecycle-draft-v2.c")
    ap.add_argument("--stage20",type=Path,
                    default=ART/"iommu-v20-stage20-cache-draft.c")
    ap.add_argument("--out",type=Path,default=ART/"iommu-v20-stage22-ownership.txt")
    a=ap.parse_args()
    if a.out.exists():ap.error("Refusing to overwrite evidence")
    paths={"driver":a.source_dir/"sunxi-iommu-v2.c",
           "pgtable":a.source_dir/"sunxi-iommu-pgtable.c"}
    for key,p in paths.items():
        if not p.is_file():ap.error(f"Missing {key} {p}")
        if hashfile(p)!=PIN[key]:ap.error(f"{key} SHA mismatch, audit baseline changed")
    for name,p in (("stage19",a.stage19),("stage20",a.stage20)):
        if not p.is_file():ap.error(f"Missing generated draft {name}: {p}")
    report=["Stage22 A733 v20 IOMMU domain/page-table ownership",
            "READ ONLY; NOT A HARDWARE OR COMPILE PASS",
            "Staged source SHA pinned, independent draft SHA reported"]
    missing=[]
    for key,path in paths.items():
        missing.extend(key+":"+n for n in inspect(key,path,report))
    for key,path in (("stage19",a.stage19),("stage20",a.stage20)):
        src=path.read_text(errors="replace")
        report.extend(["",f"DRAFT {key} {path}",f"SHA256 {hashfile(path)}"])
        report.append("MARKERS")
        for marker in ("global_iommu_domain","sunxi_pgtable_params.pgtable",
                       "sunxi_pgtable_params.iopte_cache",
                       "sunxi_iommu_attach_dev","sunxi_pgtable_free_pte_cache",
                       "sunxi_pgtable_set_dma_dev(NULL)"):
            report.append(f"{marker}: {src.count(marker)}")
    report.extend(["","DOMAIN RUNTIME SAFETY: BLOCKED",
                   "REASON: global domain aliasing and shared hardware TTB remain",
                   "REASON: table allocation/free global metadata does not count all owners",
                   "REASON: attach accepts requests without selecting a domain",
                   "REASON: cache destructor lacks verified all-domain quiescence",
                   "REASON: DMA sync addresses and page-table concurrency unresolved",
                   f"MISSING FUNCTION DEFINITIONS: {len(missing)}",*missing])
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text("\n".join(report)+"\n")
    print(f"Report: {a.out}; lines={len(report)}; missing definitions={len(missing)}")
    print("Runtime safety: BLOCKED; this is source evidence, not a PASS")
    if missing:sys.exit("Missing definitions; inspect source evidence before drafting")

if __name__=="__main__":main()
