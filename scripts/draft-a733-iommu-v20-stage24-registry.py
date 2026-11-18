#!/usr/bin/env python3
"""Stage24 offline C draft: tracked page-directory pointers, not only a count.

Input is the Stage23 generated pgtable .c. Output only new .c/.patch artifacts.
No edits to kernel source or boot files; hardware activation BLOCKED.
"""
import argparse
import difflib
import hashlib
from pathlib import Path

ART = Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts")
DEFAULT = ART / "iommu-v20-stage23-table-owners-draft.c"
ALLOC = "unsigned int *sunxi_pgtable_alloc(void)"
FREE = "void sunxi_pgtable_free(unsigned int *pgtable)"
CACHE_FREE = "void sunxi_pgtable_free_pte_cache(struct kmem_cache *iopte_cache)"
LOCK = "static DEFINE_MUTEX(sunxi_pgtable_lifetime_lock);"
COUNT = "static unsigned int sunxi_pgtable_live_directories;"

def span(src, marker):
    if src.count(marker) != 1:
        raise ValueError("Missing/duplicate function: " + marker)
    start = src.index(marker)
    op = src.find("{", start)
    if op < 0 or op - start > 250:
        raise ValueError("Missing body: " + marker)
    depth = 0
    for pos in range(op, len(src)):
        if src[pos] == "{":
            depth += 1
        elif src[pos] == "}":
            depth -= 1
            if depth == 0:
                return start, pos + 1
    raise ValueError("Unclosed function: " + marker)

def replace_function(src, marker, new):
    start, stop = span(src, marker)
    return src[:start] + new + src[stop:]

NEW_ALLOC = '''unsigned int *sunxi_pgtable_alloc(void)
{
\tstruct sunxi_pgtable_directory *record;
\tunsigned int *pgtable = NULL;

\t/* Preallocate metadata; never publish an untracked directory. */
\trecord = kzalloc(sizeof(*record), GFP_KERNEL);
\tif (!record)
\t\treturn NULL;

\tmutex_lock(&sunxi_pgtable_lifetime_lock);
\tif (WARN_ON_ONCE(!sunxi_pgtable_params.iopte_cache))
\t\tgoto out;

\tpgtable = (unsigned int *)__get_free_pages(GFP_KERNEL,
\t\t\t\t\t\t   get_order(PD_SIZE));
\tif (!pgtable)
\t\tgoto out;

\tmemset(pgtable, 0, PD_SIZE);
\trecord->addr = pgtable;
\tlist_add(&record->node, &sunxi_pgtable_directories);
\trecord = NULL; /* Registry now owns the record. */
out:
\tmutex_unlock(&sunxi_pgtable_lifetime_lock);
\tkfree(record);
\treturn pgtable;
}'''

NEW_FREE = '''void sunxi_pgtable_free(unsigned int *pgtable)
{
\tstruct sunxi_pgtable_directory *record, *found = NULL;

\tif (WARN_ON_ONCE(!pgtable))
\t\treturn;

\tmutex_lock(&sunxi_pgtable_lifetime_lock);
\tlist_for_each_entry(record, &sunxi_pgtable_directories, node) {
\t\tif (record->addr == pgtable) {
\t\t\tfound = record;
\t\t\tbreak;
\t\t}
\t}
\tif (WARN_ON_ONCE(!found)) {
\t\tmutex_unlock(&sunxi_pgtable_lifetime_lock);
\t\treturn;
\t}
\t/* Remove ownership before freeing, so a repeat free cannot match. */
\tlist_del(&found->node);
\tfree_pages((unsigned long)found->addr, get_order(PD_SIZE));
\tmutex_unlock(&sunxi_pgtable_lifetime_lock);
\tkfree(found);
}'''

NEW_CACHE_FREE = '''void sunxi_pgtable_free_pte_cache(struct kmem_cache *iopte_cache)
{
\tif (!iopte_cache)
\t\treturn;

\tmutex_lock(&sunxi_pgtable_lifetime_lock);
\tif (WARN_ON_ONCE(sunxi_pgtable_params.iopte_cache != iopte_cache) ||
\t    WARN_ON_ONCE(!list_empty(&sunxi_pgtable_directories))) {
\t\tmutex_unlock(&sunxi_pgtable_lifetime_lock);
\t\treturn;
\t}
\t/* Separate domain/map fencing is needed before actual hardware use. */
\tsunxi_pgtable_params.iopte_cache = NULL;
\tkmem_cache_destroy(iopte_cache);
\tmutex_unlock(&sunxi_pgtable_lifetime_lock);
}'''

REGISTRY = '''/* Stage24: pointer identity and cache lifetime protected by one mutex.
 * Protecting this registry does NOT serialize PTE map/unmap or HW DMA.
 */
struct sunxi_pgtable_directory {
\tstruct list_head node;
\tunsigned int *addr;
};

static LIST_HEAD(sunxi_pgtable_directories);
'''

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, default=DEFAULT)
    ap.add_argument("--out", type=Path,
                    default=ART / "iommu-v20-stage24-registry-draft.c")
    ap.add_argument("--patch", type=Path,
                    default=ART / "iommu-v20-stage24-registry-draft.patch")
    a = ap.parse_args()
    if a.out.exists() or a.patch.exists():
        ap.error("Output exists; choose new --out/--patch, never overwrite")
    original = a.source.read_text()
    for m in (ALLOC, FREE, CACHE_FREE):
        span(original, m)
    if original.count(LOCK) != 1 or original.count(COUNT) != 1:
        ap.error("Input must be the unmodified Stage23 count-based draft")
    if "sunxi_pgtable_live_directories++;" not in original or \
       "sunxi_pgtable_live_directories--;" not in original:
        ap.error("Expected Stage23 counter operations missing")
    if "sunxi_pgtable_params.pgtable =" in original:
        ap.error("Singleton pgtable assignment unexpectedly present")
    result = original.replace(COUNT, REGISTRY, 1)
    for marker, body in ((ALLOC, NEW_ALLOC), (FREE, NEW_FREE),
                         (CACHE_FREE, NEW_CACHE_FREE)):
        result = replace_function(result, marker, body)
    # Put direct header dependencies next to existing includes. Missing headers
    # here must not be silently supplied by unrelated transitive includes.
    inc = '#include <linux/slab.h>'
    if result.count(inc) != 1:
        ap.error("Cannot uniquely locate include section")
    result = result.replace(inc, inc + '\n#include <linux/list.h>\n#include <linux/mutex.h>', 1)
    for marker in (ALLOC, FREE, CACHE_FREE,
                   "struct kmem_cache *sunxi_pgtable_alloc_pte_cache(void)",
                   "void sunxi_pgtable_set_dma_dev(struct device *dma_dev)"):
        span(result, marker)
    for forbidden in ("sunxi_pgtable_live_directories", "sunxi_pgtable_params.pgtable ="):
        if forbidden in result:
            ap.error("Legacy singleton/counter still referenced: " + forbidden)
    if result.count("list_add(&record->node") != 1 or \
       result.count("list_del(&found->node)") != 1 or \
       result.count("list_empty(&sunxi_pgtable_directories)") != 1:
        ap.error("Registry publication/removal/teardown invariant failed")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.patch.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(result)
    a.patch.write_text("".join(difflib.unified_diff(
        original.splitlines(True), result.splitlines(True),
        fromfile="a/drivers/iommu/aw-v20/sunxi-iommu-pgtable.c",
        tofile="b/drivers/iommu/aw-v20/sunxi-iommu-pgtable.c")))
    print("INPUT_SHA256:", hashlib.sha256(original.encode()).hexdigest())
    print("DRAFT_SHA256:", hashlib.sha256(result.encode()).hexdigest())
    print("SOURCE:", a.out)
    print("PATCH:", a.patch)
    print("REGISTRY OWNERSHIP DRAFTED; PTE DMA/CONCURRENCY STILL BLOCKS ACTIVATION.")

if __name__ == "__main__":
    main()
