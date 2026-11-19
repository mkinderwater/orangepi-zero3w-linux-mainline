#!/usr/bin/env python3
"""Stage20: isolated page-table cache lifetime fix for A733 IOMMU v20.

Reads the SHA-pinned staged pgtable C file and emits a separate draft and
unified diff. Never edits kernel sources. Hardware activation remains blocked.
"""
from pathlib import Path
import argparse
import difflib
import hashlib

ART=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts")
SOURCE=ART/"iommu-v20-port-stage1-kcflags/linux/drivers/iommu/aw-v20/sunxi-iommu-pgtable.c"
SHA256="aacc30517e7101177d55f4c67bbeaa4ab6ae7f70a4d15eecf9ab81197fdd6017"
ALLOC_NAME="struct kmem_cache *sunxi_pgtable_alloc_pte_cache(void)"
FREE_NAME="void sunxi_pgtable_free_pte_cache(struct kmem_cache *iopte_cache)"
NEXT_NAME="void sunxi_pgtable_set_dma_dev(struct device *dma_dev)"

NEW_FUNCS='''struct kmem_cache *sunxi_pgtable_alloc_pte_cache(void)
{
\tstruct kmem_cache *cache;

\t/* A second allocation must not overwrite a live global cache. */
\tif (WARN_ON_ONCE(sunxi_pgtable_params.iopte_cache))
\t\treturn NULL;

\tcache = kmem_cache_create("sunxi-iopte-cache", PT_SIZE, PT_SIZE,
\t\t\t\t  SLAB_HWCACHE_ALIGN, NULL);
\tif (!cache)
\t\treturn NULL;

\tsunxi_pgtable_params.iopte_cache = cache;
\treturn cache;
}

void sunxi_pgtable_free_pte_cache(struct kmem_cache *iopte_cache)
{
\tif (!iopte_cache)
\t\treturn;

\t/* Fail closed if the caller does not own the published cache or a
\t * page directory is still alive. Both indicate unsafe teardown.
\t */
\tif (WARN_ON_ONCE(sunxi_pgtable_params.iopte_cache != iopte_cache))
\t\treturn;
\tif (WARN_ON_ONCE(sunxi_pgtable_params.pgtable))
\t\treturn;

\t/* Clear the internal reference before destroying the cache. */
\tsunxi_pgtable_params.iopte_cache = NULL;
\tkmem_cache_destroy(iopte_cache);
}

'''

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,default=SOURCE)
    p.add_argument("--out",type=Path,default=ART/"iommu-v20-stage20-cache-draft.c")
    p.add_argument("--patch",type=Path,default=ART/"iommu-v20-stage20-cache-draft.patch")
    a=p.parse_args()
    if a.out.exists() or a.patch.exists():
        p.error("Output already exists. Use new names, do not overwrite.")
    data=a.source.read_bytes()
    found=hashlib.sha256(data).hexdigest()
    if found!=SHA256:
        p.error(f"Source SHA256 mismatch {found}, expected {SHA256}")
    old=data.decode("utf-8")
    for marker in (ALLOC_NAME,FREE_NAME,NEXT_NAME):
        if old.count(marker)!=1:
            p.error(f"Missing/duplicate marker: {marker}")
    prefix,tail=old.split(ALLOC_NAME,1)
    discarded,after=tail.split(NEXT_NAME,1)
    original=ALLOC_NAME+discarded
    for marker in ("sunxi_pgtable_params.iopte_cache = cache;",
                   "kmem_cache_destroy(iopte_cache);"):
        if original.count(marker)!=1:
            p.error(f"Unexpected existing cache implementation: {marker}")
    new=prefix+NEW_FUNCS+NEXT_NAME+after
    if new.count(NEXT_NAME)!=1 or new.count("sunxi_pgtable_params.iopte_cache = NULL;")!=1:
        p.error("Generated source failed preservation / invalidation guards")
    if new.index("sunxi_pgtable_params.iopte_cache = NULL;",new.index(FREE_NAME)) > new.index("kmem_cache_destroy(iopte_cache);"):
        p.error("Destroy occurs before internal pointer invalidation")
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.patch.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(new)
    a.patch.write_text("".join(difflib.unified_diff(
        old.splitlines(True),new.splitlines(True),
        fromfile="a/drivers/iommu/aw-v20/sunxi-iommu-pgtable.c",
        tofile="b/drivers/iommu/aw-v20/sunxi-iommu-pgtable.c")))
    print("ORIGINAL_SHA256:",SHA256)
    print("DRAFT_SHA256:",hashlib.sha256(new.encode()).hexdigest())
    print("DRAFT:",a.out)
    print("PATCH:",a.patch)
    print("INTERNAL CACHE STALE POINTER FIX DRAFTED; hardware safety NOT established.")

if __name__=="__main__":
    main()
