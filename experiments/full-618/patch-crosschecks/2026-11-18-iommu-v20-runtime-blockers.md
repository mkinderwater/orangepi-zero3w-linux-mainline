# A733 IOMMU v20: runtime safety review after source/link PASS

**Date:** 2026-11-18  
**State:** BLOCKED for hardware activation. Three AArch64 objects compile and `aarch64-linux-gnu-ld -r` succeeds. The relocatable combined object's SHA256 is `495096f27313a88a758d049832a65949dac5ae88e97338bc660c243eb93c0d84`. No full kernel link, device-tree IOMMU consumer enablement or hardware DMA test was performed.

## Source evidence

Operator-provided read-only `iommu-v20-lifecycle-dma-audit.txt` on the staged code:
- `sunxi-iommu-v2.c` SHA256 `aa78ce2829693be1c27e93647244f50dd86dc4f386930b2301ba8990b7d19b53`
- `sunxi-iommu-pgtable.c` SHA256 `aacc30517e7101177d55f4c67bbeaa4ab6ae7f70a4d15eecf9ab81197fdd6017`
- `sunxi-iommu-pgtable.h` SHA256 `93ff578b4632306c9403f1edd9c5e1841558d465ecc112caf07346d47373eba3`

The [public Allwinner BSP v20 reference](https://github.com/alexcaoys/allwinner-bsp/blob/656a550c826787e7e72fae58ca793df9e0988ac8/drivers/iommu/sunxi-iommu-v2.c) was separately inspected. It cannot be assumed to fix the exact operator-tree lifetime or DMA behavior.

## Activation blockers

### B1: Singleton domain lifetime, critical

The staged `sunxi_iommu_domain_alloc_paging()` returns `global_iommu_domain` if non-NULL, with no extra reference/lifetime tracking. `sunxi_iommu_domain_free()` frees its page tables, SG buffer and domain object but does **not** clear `global_iommu_domain`. A later allocation could return freed memory; a second free risks double-free. This is incompatible with a safe unproven multi-client domain lifecycle.

**Required evidence:** model the Linux 6.18 domain ownership and group contract. Select an architecture with one coherent controller/domain ownership strategy; prove alloc, attach, detach, free and device removal order. Do not paper over this with a refcount alone.

### B2: DMA page-table synchronization, critical

The staged page-table implementation passes `virt_to_phys()` of page-directory/table entries to `dma_sync_single_for_cpu` and `dma_sync_single_for_device`. The audited allocation/handling excerpts do not show corresponding `dma_map_single` (or persistent DMA mapping) for these buffers. The DMA API expects a valid mapped DMA handle and correct synchronization lifecycle. Physical addresses are not universally DMA handles, including when translation or offsets exist.

**Required evidence:** identify the IOMMU page-table walk address space, streaming/coherent DMA masks and cache-coherence requirements, page-table allocation alignment and sync policy. Use suitable DMA allocation/mapping with matching release, not an unverified physical-address cast. Check if the provider DMA API would create recursive IOMMU use.

### B3: Hardware init fails open, high

`sunxi_iommu_domain_alloc_paging()` logs `sunxi_iommu_hw_init()` failure but still returns the domain; the global pointer is assigned before init completes. The next user could see an apparently valid but unusable domain.

**Required:** propagate init errors and fully unwind allocated resources. Ensure no caller can attach during partial initialization.

### B4: Attach does not establish or verify ownership, high

The vendor `sunxi_iommu_attach_dev()` unconditionally returns 0. Probe/finalize enables the master separately. That may have worked with the vendor singleton assumptions but is not proof the selected Linux 6.18 domain and DMA attachments are consistent.

**Required:** audit master->domain binding, IOVA/TLB update paths and error ordering. Verify all enabled masters share exactly the intended translation domain.

### B5: Mapping and invalidation atomicity, high

The compile-only adapter multiplies `pgsize * pgcount`, but the vendor page-table update may partially allocate/write entries. Need prove `mapped` reflects exactly installed mappings or that errors roll back. The map code's `SPAGE_ALIGN(iova + size)` also needs overflow and bounds validation. The unmap path extends gather ranges by direct `start/end` mutation, with possible end-inclusive vs end-exclusive mismatch. TLB/PTW invalidation order must match hardware.

**Required:** focused mapping tests, error injection, address/range boundary checks, and comparison to Linux 6.18 IOMMU core requirements.

### B6: Page-directory sync length, high

In `sunxi_pgtable_clear()`, a sync call uses `virt_to_phys(dent)` with `PT_SIZE` before writing one directory entry. That could synchronize beyond the intended directory entry, potentially crossing allocation bounds depending on index. Verify intended size and whether the operation should be against the PTE table or PDE.

**Required:** exact buffer-length proof, cacheline alignment, and DMA API conversion.

### B7: Teardown, debug and PM safety

The Stage 3 `void` platform-remove wrapper only resolves an API signature. It does not guarantee correct `iommu_device_unregister`, sysfs, IRQ, clock, cache or group lifetime. Other paths dereference globals without checking for NULL, including suspend/resume and debug helpers.

**Required:** remove/unbind ordering, references to global group and domain, IRQ/cache ownership, concurrency with users and resume failure propagation.

## Next work and gates

1. Maintain the proven Stage 4 kernel/DTB unchanged. No enabling `iommus` consumer, module probe or live DMA test.
2. Run the repository's read-only activation gate against the exact staged source and combined artifact; it must fail while blockers remain.
3. Design and test a safe domain ownership implementation, then DMA-backed page-table allocation/sync, mapping and TLB correctness in *disposable* source trees.
4. Perform compile, relocatable link and full kernel link with exact config, plus negative/failure-injection cases.
5. Only after documented independent review of runtime safety consider an isolated hardware test using a separately recoverable image, never the known-good baseline.

**Do not mark a successful object compile or relocatable link as hardware ready.**
