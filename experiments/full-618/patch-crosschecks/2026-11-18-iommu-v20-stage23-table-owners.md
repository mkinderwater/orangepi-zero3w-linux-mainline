# A733 IOMMU v20 Stage 23: live directory count instead of last-table pointer

**Status:** generated C draft and offline checks, not compile or runtime approval.

## Confirmed from Stage 22

The user's Stage22 report found all required function definitions and verified staged SHA256s. Original page-table source:
- `sunxi_pgtable_alloc()` unconditionally assigns `sunxi_pgtable_params.pgtable = pgtable` on every call.
- `sunxi_pgtable_free()` sets it to NULL no matter which directory is freed.
- Stage20 cache destruction checks this **one last-published pointer**. A second allocation followed by freeing the first can bypass the guard while another directory remains live.
- In the driver, repeated allocation returns `global_iommu_domain`, free does not invalidate it, `attach_dev()` returns success without selecting a table, and TTB initialization happens during allocation. These remain independent blockers.

## Stage 23 source change

`scripts/draft-a733-iommu-v20-stage23-table-owners.py` uses the previously generated Stage20 page-table C draft. It emits a new source and unified diff without touching the kernel tree.

- Removes writes to `sunxi_pgtable_params.pgtable`.
- Adds `sunxi_pgtable_live_directories`, protected by `sunxi_pgtable_lifetime_lock`.
- Serializes cache creation, page-directory creation, page-directory release and cache destruction on that same lock.
- Refuses cache destruction whenever the directory count is nonzero.
- Checks missing cache, count overflow, invalid pointer and count underflow.
- Invalidates the internal `iopte_cache` pointer before destruction, preserving the Stage20 stale-cache fix.

`scripts/test-a733-iommu-v20-stage23-table-owners.py` contains 12 structural and model checks. The **live count is necessary but not sufficient**: it cannot detect a wrong pointer, an already-freed directory when others still exist, in-flight PTE operations or external users. Do not regard it as an ownership registry. The next iteration must address per-domain allocation membership, active TTB and map/unmap fencing.

## Operator commands

```sh
cd /root/orangepi-zero3w-linux-mainline/orangepi-zero3w-linux-mainline
git pull --ff-only origin work/linux-6.18-full-integration
python3 -m py_compile scripts/draft-a733-iommu-v20-stage23-table-owners.py
python3 scripts/draft-a733-iommu-v20-stage23-table-owners.py
python3 scripts/test-a733-iommu-v20-stage23-table-owners.py 2>&1 | tee /home/iommu-v20-stage23-tests.txt
D=/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts
cp "$D/iommu-v20-stage23-table-owners-draft.patch" /home/
```

## Runtime safety blockers

Existing driver has invalid global domain aliasing, unconditional attach, hardware initialization during allocation, incomplete domain-switch/rollback and invalid DMA sync handles. No changes have been made to the known-good Stage4 kernel, DTB, image or firmware. Do not activate or boot the draft.
