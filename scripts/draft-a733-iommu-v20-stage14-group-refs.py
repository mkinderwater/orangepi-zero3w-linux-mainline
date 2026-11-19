#!/usr/bin/env python3
"""Generate an OFFLINE Stage14 group-lifetime patch, never modify kernel tree.

Experimental Linux6.18-only source draft. This patch does NOT fix the other
IOMMU v20 lifecycle, DMA or MMIO safety faults. Never boot it.
"""
import argparse
import difflib
import hashlib
from pathlib import Path

BASE=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts")
SRC=BASE/"iommu-v20-port-stage1-kcflags/linux/drivers/iommu/aw-v20/sunxi-iommu-v2.c"
EXPECTED="aa78ce2829693be1c27e93647244f50dd86dc4f386930b2301ba8990b7d19b53"
ORIGINAL_START="struct iommu_group *sunxi_iommu_device_group(struct device *dev)"
ORIGINAL_NEXT="static int sunxi_iommu_of_xlate(struct device *dev,"
REPLACEMENT='''/* Stage14 experimental Linux 6.18 group reference accounting. */
static DEFINE_MUTEX(sunxi_iommu_group_lock);

struct iommu_group *sunxi_iommu_device_group(struct device *dev)
{
    struct iommu_group *group;

    mutex_lock(&sunxi_iommu_group_lock);
    if (!global_group) {
        group = iommu_group_alloc();
        if (IS_ERR(group)) {
            mutex_unlock(&sunxi_iommu_group_lock);
            return group;
        }
        /* Retain the allocation reference while the controller is registered. */
        global_group = group;
    }
    /* Linux core consumes one reference for each probed client. */
    group = iommu_group_ref_get(global_group);
    mutex_unlock(&sunxi_iommu_group_lock);
    return group;
}

'''
OLD_REMOVE='''	iommu_device_unregister(&sunxi_iommu->iommu);
	global_iommu_dev = NULL;'''
NEW_REMOVE='''	iommu_device_unregister(&sunxi_iommu->iommu);
	/* Drop the controller-held reference after core client teardown. */
	mutex_lock(&sunxi_iommu_group_lock);
	if (global_group) {
		struct iommu_group *group = global_group;
		global_group = NULL;
		mutex_unlock(&sunxi_iommu_group_lock);
		iommu_group_put(group);
	} else {
		mutex_unlock(&sunxi_iommu_group_lock);
	}
	global_iommu_dev = NULL;'''

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",type=Path,default=SRC)
    ap.add_argument("--out",type=Path,default=BASE/"iommu-v20-stage14-group-refs-draft.c")
    ap.add_argument("--patch",type=Path,default=BASE/"iommu-v20-stage14-group-refs-draft.patch")
    a=ap.parse_args()
    if a.out.exists() or a.patch.exists():
        ap.error("refusing to overwrite an existing artifact")
    source=a.source.read_bytes()
    if hashlib.sha256(source).hexdigest()!=EXPECTED:
        ap.error("source SHA256 mismatch, refusing to patch")
    old=source.decode("utf-8")
    if old.count(ORIGINAL_START)!=1 or old.count(ORIGINAL_NEXT)!=1 or old.count(OLD_REMOVE)!=1:
        ap.error("cannot uniquely locate group callback or remove cleanup")
    before,remaining=old.split(ORIGINAL_START,1)
    discarded,after=remaining.split(ORIGINAL_NEXT,1)
    if "global_group = iommu_group_alloc();" not in discarded:
        ap.error("unexpected group implementation")
    new=before+REPLACEMENT+ORIGINAL_NEXT+after
    new=new.replace(OLD_REMOVE,NEW_REMOVE,1)
    if new==old:ap.error("no changes produced")
    patch="".join(difflib.unified_diff(old.splitlines(keepends=True),new.splitlines(keepends=True),
                                      fromfile="a/drivers/iommu/aw-v20/sunxi-iommu-v2.c",
                                      tofile="b/drivers/iommu/aw-v20/sunxi-iommu-v2.c"))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.patch.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(new)
    a.patch.write_text(patch)
    print("SOURCE_SHA256:",EXPECTED)
    print("DRAFT_SHA256:",hashlib.sha256(new.encode()).hexdigest())
    print("DRAFT:",a.out)
    print("PATCH:",a.patch)
    print("EXPERIMENT ONLY; no activation approval.")
if __name__=="__main__":
    main()
