# A733 IOMMU v20 Stage 20: page-table cache stale-pointer correction

**Scope:** Fix the specific internal page-table-cache pointer lifetime defect discovered during Stage19 v2 review. **No kernel or hardware activation.**

## Confirmed defect

The audited `sunxi-iommu-pgtable.c` has a module-wide `sunxi_pgtable_params.iopte_cache` assigned in `sunxi_pgtable_alloc_pte_cache()`. PTE allocation/free calls reference this field. Its `sunxi_pgtable_free_pte_cache(cache)` destroys the slab cache but leaves `sunxi_pgtable_params.iopte_cache` pointing to freed memory. Stage19 v2 clears the different driver-level `iopte_cache` pointer, **not** the page-table subsystem's pointer. The stale pointer can cause UAF or invalid reuse on later calls.

## Source fix

`scripts/draft-a733-iommu-v20-stage20-cache.py`, commit `aba05f0`, generates a separate page-table C draft and unified patch from the **exact SHA256-pinned** original `sunxi-iommu-pgtable.c`. It refuses source hash mismatches and overwrites. It does not modify any kernel tree.

- Allocation refuses to overwrite an already published cache pointer.
- Allocation checks for failed cache creation before publishing a pointer.
- Destruction accepts NULL as a no-op and refuses to destroy a cache if the passed pointer differs from the internal published pointer.
- Destruction refuses while the tracked page directory remains allocated.
- **On a valid teardown path, the internal pointer is cleared before `kmem_cache_destroy()`.**
- The existing `sunxi_pgtable_set_dma_dev()` function and the rest of the page-table source remain intact.

`scripts/test-a733-iommu-v20-stage20-cache.py`, commit `c953979`, tests the above static invariants. No functional kernel cache-lifecycle, concurrent fault injection, or AArch64 object build has been run.

## Practical limits

This removes the confirmed stale-pointer bug **on valid serialized teardown**. It does not prove concurrent teardown safety or that the single global page-directory tracking always represents all allocated domains. `kmem_cache_destroy()` must only run after all outstanding page table allocations are freed. The Stage19 driver still requires domain ownership and callback lifecycle fixes. Do not assume a successful source check or compile proves DMA readiness.

## Debian commands

```sh
cd /root/orangepi-zero3w-linux-mainline/orangepi-zero3w-linux-mainline
git pull --ff-only origin work/linux-6.18-full-integration
python3 -m py_compile scripts/draft-a733-iommu-v20-stage20-cache.py
python3 scripts/draft-a733-iommu-v20-stage20-cache.py
python3 scripts/test-a733-iommu-v20-stage20-cache.py 2>&1 | tee /home/iommu-v20-stage20-cache-tests.txt
D=/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts
cp "$D/iommu-v20-stage20-cache-draft.patch" /home/
```

Next: compile both the revised `sunxi-iommu-pgtable.c` and Stage19 v2 driver source **in a separate disposable build tree**, then address the global domain alias/attach/DMA correctness defects. The proven Stage4 kernel, DTB, firmware and boot images must not change.
