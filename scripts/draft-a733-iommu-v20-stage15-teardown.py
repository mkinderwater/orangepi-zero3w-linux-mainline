#!/usr/bin/env python3
"""Create OFFLINE stage15 v20 teardown ordering draft from stage14 draft.

Never modifies the kernel tree; not sufficient for runtime or boot.
"""
from pathlib import Path
import argparse,difflib,hashlib,re

ART=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts")
OLD=ART/"iommu-v20-stage14-group-refs-draft.c"
OLD_REMOVE="static int sunxi_iommu_remove(struct platform_device *pdev)"
END_REMOVE="/* Diagnostic API adapter: Linux 6.18 platform_driver.remove is void. */"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,default=OLD)
    p.add_argument("--out",type=Path,default=ART/"iommu-v20-stage15-teardown-draft.c")
    p.add_argument("--patch",type=Path,default=ART/"iommu-v20-stage15-teardown-draft.patch")
    a=p.parse_args()
    if a.out.exists() or a.patch.exists():p.error("refusing to overwrite existing output")
    src=a.source.read_text()
    if src.count(OLD_REMOVE)!=1 or src.count(END_REMOVE)!=1:
        p.error("Expected exact Stage14 remove and adapter markers")
    if "iommu_group_ref_get(global_group)" not in src or "iommu_group_put(group);" not in src:
        p.error("Missing expected Stage14 group-lifetime draft")
    before,rem=src.split(OLD_REMOVE,1)
    # Preserve every subsequent function (PM callbacks, registration and adapter).
    # The first column-zero closing brace ends the remove callback.
    match=re.search(r"(?m)^}\\s*\\n",rem)
    if not match:p.error("Cannot isolate remove callback body")
    removal=rem[:match.end()]
    after=rem[match.end():]
    old=OLD_REMOVE+removal
    # The callback must not release underlying infrastructure until all clients
    # have been removed by iommu_device_unregister().
    starts=old.find("\tsunxi_pgtable_free_pte_cache(iopte_cache);")
    unregister=old.find("\tiommu_device_unregister(&sunxi_iommu->iommu);")
    if starts<0 or unregister<0 or starts>unregister:
        p.error("Unknown remove function layout")
    head=old[:starts]
    cleaned='''\t/* Remove clients and free their domains before tearing down DMA/cache/MMIO. */
\tiommu_device_unregister(&sunxi_iommu->iommu);
\t/* Clear the controller group only after the core has released clients. */
\tmutex_lock(&sunxi_iommu_group_lock);
\t{
\t\tstruct iommu_group *group = global_group;
\t\tglobal_group = NULL;
\t\tmutex_unlock(&sunxi_iommu_group_lock);
\t\tif (group)
\t\t\tiommu_group_put(group);
\t}
\t/* Core no longer references page tables or the IOMMU's registers. */
\tsunxi_pgtable_free_pte_cache(iopte_cache);
\tiopte_cache = NULL;
\tif (!list_empty(&sunxi_iommu->rsv_list)) {
\t\tlist_for_each_entry_safe(entry, next, &sunxi_iommu->rsv_list, list) {
\t\t\tlist_del(&entry->list);
\t\t\tkfree(entry);
\t\t}
\t}
\tfor (i = 0; i < IOMMU_HW_SET_COUNT; i++)
\t\tdevm_free_irq(sunxi_iommu->dev, sunxi_iommu->irq[i],
\t\t\t      sunxi_iommu);
\tsunxi_iommu_sysfs_remove(pdev);
\tiommu_device_sysfs_remove(&sunxi_iommu->iommu);
\tdevm_iounmap(sunxi_iommu->dev, sunxi_iommu->base);
\tglobal_iommu_dev = NULL;

\treturn 0;
}

'''
    # Do not hide structural drift: assert expected teardown operations occur once
    for needle in ('sunxi_pgtable_free_pte_cache(iopte_cache);',
                   'iommu_device_unregister(&sunxi_iommu->iommu);',
                   'devm_iounmap(sunxi_iommu->dev, sunxi_iommu->base);',
                   'global_group = NULL;'):
        if old.count(needle)!=1:p.error("Unexpected old teardown occurrence: "+needle)
    new=before+head+cleaned+after
    assert new.count("iommu_device_unregister(&sunxi_iommu->iommu);")==1
    assert new.count("sunxi_pgtable_free_pte_cache(iopte_cache);")>=1
    for marker in ("static int sunxi_iommu_suspend(", "static int sunxi_iommu_resume(", END_REMOVE):
        if marker not in new:p.error("Required post-remove code was lost: "+marker)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(new)
    a.patch.write_text("".join(difflib.unified_diff(src.splitlines(True),new.splitlines(True),
                fromfile="a/drivers/iommu/aw-v20/sunxi-iommu-v2.c",
                tofile="b/drivers/iommu/aw-v20/sunxi-iommu-v2.c")))
    print("INPUT_SHA256:",hashlib.sha256(src.encode()).hexdigest())
    print("OUTPUT_SHA256:",hashlib.sha256(new.encode()).hexdigest())
    print("DRAFT:",a.out)
    print("PATCH:",a.patch)
    print("WARNING: other probe/domain/DMA faults remain. DO NOT BOOT.")
if __name__=="__main__":main()
