#!/usr/bin/env python3
"""Generate Stage23 page-directory count and guarded cache teardown draft.

Reads the Stage20 generated pgtable C file. Emits separate C and patch files.
Does not modify the kernel tree. Runtime IOMMU activation is prohibited.
"""
import argparse
import difflib
import hashlib
import re
from pathlib import Path

ART = Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts")
ALLOC = "unsigned int *sunxi_pgtable_alloc(void)"
FREE = "void sunxi_pgtable_free(unsigned int *pgtable)"
CACHE_ALLOC = "struct kmem_cache *sunxi_pgtable_alloc_pte_cache(void)"
CACHE_FREE = "void sunxi_pgtable_free_pte_cache(struct kmem_cache *iopte_cache)"
SETTER = "void sunxi_pgtable_set_dma_dev(struct device *dma_dev)"

def function_span(src, name):
    if src.count(name) != 1:
        raise ValueError("Nonunique function " + name)
    start = src.index(name)
    opening = src.find("{", start)
    if opening < 0 or opening - start > 260:
        raise ValueError("Missing function body " + name)
    depth = 0
    for i in range(opening, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if not depth:
                return start, i + 1
    raise ValueError("Unclosed function " + name)

def rewrite(src, name, replacement):
    start, end = function_span(src, name)
    return src[:start] + replacement + src[end:]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path,
        default=ART / "iommu-v20-stage20-cache-draft.c")
    ap.add_argument("--out", type=Path,
        default=ART / "iommu-v20-stage23-table-owners-draft.c")
    ap.add_argument("--patch", type=Path,
        default=ART / "iommu-v20-stage23-table-owners-draft.patch")
    a = ap.parse_args()
    if a.out.exists() or a.patch.exists():
        ap.error("Refusing to overwrite existing artifact")
    original = a.source.read_text()
    for name in (ALLOC, FREE, CACHE_ALLOC, CACHE_FREE, SETTER):
        function_span(original, name)
    if original.count("sunxi_pgtable_params.pgtable = pgtable;") != 1 or \
       original.count("sunxi_pgtable_params.pgtable = NULL;") != 1:
        ap.error("Expected legacy singleton page-directory writes missing")
    if original.count("WARN_ON_ONCE(sunxi_pgtable_params.pgtable)") != 1:
        ap.error("Expected Stage20 cache guard missing")

    lifetime = '''/* Stage23: page-directory live count and cache are serialized.
 * This count does not identify wrong/double frees or track live PTE users.
 */
static DEFINE_MUTEX(sunxi_pgtable_lifetime_lock);
static unsigned int sunxi_pgtable_live_directories;

'''
    new_alloc = '''unsigned int *sunxi_pgtable_alloc(void)
{
\tunsigned int *pgtable = NULL;

\tmutex_lock(&sunxi_pgtable_lifetime_lock);
\tif (WARN_ON_ONCE(!sunxi_pgtable_params.iopte_cache))
\t\tgoto out;
\tif (WARN_ON_ONCE(sunxi_pgtable_live_directories == UINT_MAX))
\t\tgoto out;
\tpgtable = (unsigned int *)__get_free_pages(GFP_KERNEL,
\t\t\t\t\t\t   get_order(PD_SIZE));
\tif (pgtable) {
\t\tmemset(pgtable, 0, PD_SIZE);
\t\tsunxi_pgtable_live_directories++;
\t}
out:
\tmutex_unlock(&sunxi_pgtable_lifetime_lock);
\treturn pgtable;
}'''
    new_free = '''void sunxi_pgtable_free(unsigned int *pgtable)
{
\tif (WARN_ON_ONCE(!pgtable))
\t\treturn;

\tmutex_lock(&sunxi_pgtable_lifetime_lock);
\tif (WARN_ON_ONCE(!sunxi_pgtable_live_directories)) {
\t\tmutex_unlock(&sunxi_pgtable_lifetime_lock);
\t\treturn;
\t}
\t/* Caller must guarantee this exact directory is still allocated.
\t * A count alone cannot prevent wrong-pointer or repeat-free bugs.
\t */
\tfree_pages((unsigned long)pgtable, get_order(PD_SIZE));
\tsunxi_pgtable_live_directories--;
\tmutex_unlock(&sunxi_pgtable_lifetime_lock);
}'''
    new_cache_alloc = '''struct kmem_cache *sunxi_pgtable_alloc_pte_cache(void)
{
\tstruct kmem_cache *cache;

\tmutex_lock(&sunxi_pgtable_lifetime_lock);
\tif (WARN_ON_ONCE(sunxi_pgtable_params.iopte_cache)) {
\t\tcache = NULL;
\t\tgoto out;
\t}
\tcache = kmem_cache_create("sunxi-iopte-cache", PT_SIZE, PT_SIZE,
\t\t\t\t  SLAB_HWCACHE_ALIGN, NULL);
\tif (cache)
\t\tsunxi_pgtable_params.iopte_cache = cache;
out:
\tmutex_unlock(&sunxi_pgtable_lifetime_lock);
\treturn cache;
}'''
    new_cache_free = '''void sunxi_pgtable_free_pte_cache(struct kmem_cache *iopte_cache)
{
\tif (!iopte_cache)
\t\treturn;

\tmutex_lock(&sunxi_pgtable_lifetime_lock);
\t/* Fail closed if the cache is unowned or ANY directory remains live. */
\tif (WARN_ON_ONCE(sunxi_pgtable_params.iopte_cache != iopte_cache) ||
\t    WARN_ON_ONCE(sunxi_pgtable_live_directories)) {
\t\tmutex_unlock(&sunxi_pgtable_lifetime_lock);
\t\treturn;
\t}
\t/* A separate guarantee is required: no PTE map/unmap may be in flight. */
\tsunxi_pgtable_params.iopte_cache = NULL;
\tkmem_cache_destroy(iopte_cache);
\tmutex_unlock(&sunxi_pgtable_lifetime_lock);
}'''
    rewritten = original
    for name, body in ((ALLOC, new_alloc), (FREE, new_free),
                       (CACHE_ALLOC, new_cache_alloc),
                       (CACHE_FREE, new_cache_free)):
        rewritten = rewrite(rewritten, name, body)
    at = rewritten.index(ALLOC)
    rewritten = rewritten[:at] + lifetime + rewritten[at:]
    for marker in (ALLOC, FREE, CACHE_ALLOC, CACHE_FREE, SETTER):
        function_span(rewritten, marker)
    if "sunxi_pgtable_params.pgtable =" in rewritten:
        ap.error("Old last-table global assignment remains")
    if rewritten.count("sunxi_pgtable_live_directories++;") != 1 or \
       rewritten.count("sunxi_pgtable_live_directories--;") != 1:
        ap.error("Live owner count not balanced structurally")
    if rewritten.count("kmem_cache_destroy(iopte_cache);") != 1:
        ap.error("Cache destroy was lost or duplicated")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.patch.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(rewritten)
    a.patch.write_text("".join(difflib.unified_diff(
        original.splitlines(True), rewritten.splitlines(True),
        fromfile="a/drivers/iommu/aw-v20/sunxi-iommu-pgtable.c",
        tofile="b/drivers/iommu/aw-v20/sunxi-iommu-pgtable.c")))
    print("INPUT_SHA256:", hashlib.sha256(original.encode()).hexdigest())
    print("DRAFT_SHA256:", hashlib.sha256(rewritten.encode()).hexdigest())
    print("C_DRAFT:", a.out)
    print("PATCH:", a.patch)
    print("OFFLINE DRAFT ONLY. Double-free, PTE lifetime, DMA safety unresolved.")

if __name__ == "__main__":
    main()
