#!/usr/bin/env python3
"""Draft conservative A733 IOMMU v20 lifecycle changes in a NEW source file.

Stage 6 is NOT hardware-safe: it addresses only obvious fail-open paths.
DMA coherency, domain concurrency, controller teardown and real device binding
remain unresolved. No kernel files or boot images are modified.
"""
from pathlib import Path
import argparse,difflib,hashlib,sys

BASE=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts")
SOURCE_SHA="aa78ce2829693be1c27e93647244f50dd86dc4f386930b2301ba8990b7d19b53"

def once(s,old,new,label):
    count=s.count(old)
    if count != 1:
        raise ValueError(f"{label}: expected one exact match, got {count}")
    return s.replace(old,new,1)

def scope(s,first,last,old,new,label):
    if s.count(first)!=1 or s.count(last)!=1:
        raise ValueError(f"{label}: ambiguous section anchors")
    start=s.index(first)
    end=s.index(last,start+len(first))
    seg=once(s[start:end],old,new,label)
    return s[:start]+seg+s[end:]

def transform(s):
    # Deliberately keep one-controller/one-active-domain architecture.
    # A second allocation must not return the same pointer to IOMMU core,
    # which could otherwise free the object twice.
    s=scope(s,"static struct iommu_domain *sunxi_iommu_domain_alloc_paging(",
            "static void sunxi_iommu_domain_free(",
            "\tif (global_iommu_domain)\n\t\treturn global_iommu_domain;",
            "\t/* One active hardware domain; reject duplicate core ownership. */\n"
            "\tif (global_iommu_domain)\n\t\treturn NULL;",
            "B1 duplicate domain")

    # The existing source assigns the global pointer before hardware init.
    # Failure must not return a live-looking domain, and must release sg_buf.
    s=scope(s,"static struct iommu_domain *sunxi_iommu_domain_alloc_paging(",
            "static void sunxi_iommu_domain_free(",
            "\tif (!iommu_hw_init_flag) {\n"
            "\t\tif (sunxi_iommu_hw_init(&sunxi_domain->domain))\n"
            "\t\t\tpr_err(\"sunxi iommu hardware init failed\\n\");\n"
            "\t}\n\n\treturn &sunxi_domain->domain;",
            "\tif (!global_iommu_dev ||\n"
            "\t    (!iommu_hw_init_flag &&\n"
            "\t     sunxi_iommu_hw_init(&sunxi_domain->domain))) {\n"
            "\t\tpr_err(\"sunxi iommu hardware init failed\\n\");\n"
            "\t\tglobal_iommu_domain = NULL;\n"
            "\t\tgoto err_hw_init;\n"
            "\t}\n\n\treturn &sunxi_domain->domain;",
            "B3 propagate init failure")
    s=scope(s,"static struct iommu_domain *sunxi_iommu_domain_alloc_paging(",
            "static void sunxi_iommu_domain_free(",
            "\treturn &sunxi_domain->domain;\n\n#ifndef COOKIE_HANDLE_BY_CORE",
            "\treturn &sunxi_domain->domain;\n\n"
            "err_hw_init:\n"
            "\tfree_pages((unsigned long)sunxi_domain->sg_buffer,\n"
            "\t\t   get_order(MAX_SG_TABLE_SIZE));\n"
            "\tsunxi_domain->sg_buffer = NULL;\n"
            "#ifndef COOKIE_HANDLE_BY_CORE",
            "B3 init unwind")

    s=scope(s,"static void sunxi_iommu_domain_free(",
            "static int sunxi_iommu_attach_dev(",
            "\tkfree(sunxi_domain);",
            "\t/* Prevent recycling a freed singleton in a later allocation. */\n"
            "\tif (global_iommu_domain == domain)\n"
            "\t\tglobal_iommu_domain = NULL;\n"
            "\tkfree(sunxi_domain);",
            "B1 clear freed global")

    # This is a *limited* consistency guard, NOT actual attach hardware binding.
    s=scope(s,"static int sunxi_iommu_attach_dev(",
            "static void sunxi_iommu_probe_device_finalize(",
            "\treturn 0;",
            "\tstruct sunxi_iommu_owner *owner;\n\n"
            "\tif (!dev || !domain || domain != global_iommu_domain ||\n"
            "\t    !global_iommu_dev || !iommu_hw_init_flag)\n"
            "\t\treturn -ENODEV;\n"
            "\towner = dev_iommu_priv_get(dev);\n"
            "\tif (!owner || !owner->data ||\n"
            "\t    owner->data != global_iommu_dev)\n"
            "\t\treturn -EINVAL;\n"
            "\t/* Hardware domain/master binding still requires independent proof. */\n"
            "\treturn 0;",
            "B4 attach consistency")
    return s

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,default=BASE/"iommu-v20-port-stage1-kcflags/linux/drivers/iommu/aw-v20/sunxi-iommu-v2.c")
    p.add_argument("--out",type=Path,default=BASE/"iommu-v20-domain-stage6-draft.c")
    a=p.parse_args()
    if not a.source.is_file():p.error("staged input missing")
    if a.out.exists() or a.out.resolve()==a.source.resolve():p.error("output exists or would overwrite source")
    src=a.source.read_bytes()
    if hashlib.sha256(src).hexdigest()!=SOURCE_SHA:p.error("input SHA mismatch; stop and re-audit")
    original=src.decode("utf-8")
    staged=transform(original)
    diff="".join(difflib.unified_diff(original.splitlines(True),
         staged.splitlines(True),fromfile="stage5-staged-v2.c",tofile="stage6-DRAFT-v2.c"))
    if not diff:p.error("no changes")
    a.out.parent.mkdir(parents=True,exist_ok=True)
    patch=Path(str(a.out)+".patch")
    if patch.exists():p.error("patch exists")
    a.out.write_text(staged)
    patch.write_text(diff)
    print("CREATED DRAFT:",a.out)
    print("PATCH:",patch)
    print("NOTE: not tested on hardware; singleton ownership, concurrency, DMA and attach semantics unresolved")
    print("DO NOT INSTALL INTO A BOOTABLE KERNEL")
if __name__=="__main__":
    main()
