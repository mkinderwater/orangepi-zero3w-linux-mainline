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

## Stage 6 source-only draft: B1/B3/B4

**Status: design experiment only, NOT a resolution of the critical blockers.**

Commits `95ca823` and `207a3e4` add:

- `scripts/draft-a733-iommu-v20-domain-stage6.py`: verifies exact audited Stage 5 source hash `aa78ce2829693be1c27e93647244f50dd86dc4f386930b2301ba8990b7d19b53` and exact source anchors, then writes a **separate** draft C file and unified patch, never altering the staged input.
- `scripts/test-a733-iommu-v20-domain-stage6.py`: tests fail-closed single-anchor transformations and (if available) the exact audited source.

The draft explores conservative containment, not true ownership redesign:
1. Return `NULL` rather than give the same domain pointer to a second core allocator invocation.
2. On hardware init failure, clear the global pointer, release the SG buffer and unwind the existing page-table allocation. Refuse to publish a valid domain on a failed init.
3. Clear `global_iommu_domain` before releasing its allocation.
4. Require a non-NULL verified device owner, controller and previously initialized global domain in `attach_dev()`. **Still does not implement hardware domain binding.**

**Known unresolved problems:** no locking or safe concurrent lifetime; global pgtable parameter state and shared `global_group` remain, and the IOMMU HW init and teardown side effects are not rolled back; device release may race mapping; DMA mapping/coherence B2 and length B6, map rollback B5, error propagation and full Linux 6.18 IOMMU core ownership contract are not solved. Need full source-level inspection, fault-injection tests and hardware documentation before selecting a final design. `NULL` for a second allocation may simply cause Linux's core to fail default-domain setup. Do not enable the device-tree `iommus` property or boot a modified image.

Run only offline tests and generate source:
```sh
cd /root/orangepi-zero3w-linux-mainline/orangepi-zero3w-linux-mainline
git pull --ff-only origin work/linux-6.18-full-integration
python3 -m unittest -v scripts/test-a733-iommu-v20-domain-stage6.py
python3 scripts/draft-a733-iommu-v20-domain-stage6.py
```

Review the generated `iommu-v20-domain-stage6-draft.c.patch` and run a clean, separate compile only after verifying the source. Never promote the draft into the operational kernel tree.

## Stage 6 generated patch review

The operator supplied `iommu-v20-domain-stage6-draft.c.patch` (63 lines). It makes only the four intended classes of changes: duplicate allocation returns NULL, failed HW init unwinds software buffers, domain_free clears global pointer, and attach_dev checks pointers/owner/controller. It does **not** change DMA, page tables, runtime device programming or core locking.

The patch must NOT be merged as a runtime fix:
- No synchronization protects the `global_iommu_domain` check/store/clear, so competing allocations/frees can race.
- The pointer is published **before** `sunxi_iommu_hw_init()` finishes. On error it is cleared, but another path can observe a partially initialized domain.
- On failed `sunxi_iommu_hw_init()`, only software buffer rollback is attempted. Hardware/controller side effects and `iommu_hw_init_flag` must be independently tracked and undone where possible.
- A second Linux IOMMU core paging-domain allocation will return `NULL`, which might prevent group setup. This containment is not a verified multi-device domain design.
- `attach_dev()` pointer checks still do not bind a hardware master to the correct translation context or validate lifetime.
- `global_iommu_dev`, `global_group` and static page-table parameters remain global; DMA sync/IOVA mapping B2/B5/B6 remain unresolved.

Recommendation: permit **compile-only** evaluation on a disposable source copy, but design a coherent ownership and hardware activation state machine before further runtime changes. Do not mark B1, B3 or B4 fixed based only on successful compilation.

## Stage 6 isolated object compilation result

The operator uploaded `iommu-v20-stage6-build.log`: `make` compiled `drivers/iommu/aw-v20/sunxi-iommu-v2.o` and exited normally, with no reported errors and 13 `-Wmissing-prototypes` warnings, matching the earlier vendor baseline warnings. The build log does not contain the separate shell-printed `RC`, so this is log-based evidence, not an independently captured exit status. **Stage 6 draft compile PASS; no lifecycle or DMA safety sign-off.**

**Artifact contamination precaution:** The previous compile steps restored the staged `sunxi-iommu-v2.c`, but left the *Stage 6 draft* `sunxi-iommu-v2.o` inside the disposable build directory. Do not report a fresh three-object/relocatable-link result or reuse the old combined-object hash without rebuilding the v2 object from the intended source. Verify SHA256 `aa78ce2829693be1c27e93647244f50dd86dc4f386930b2301ba8990b7d19b53` of the restored staged source, remove the stale v2 object, and recompile it using the existing `-DCONFIG_AW_IOMMU_V2=1` and vendor include path. For Stage 6 linkage, use a *separately saved* Stage 6 object and unique output filenames, rather than altering the established Stage 4 linkage evidence.

Remaining acceptance gates: concurrently safe lifecycle with correct core domain ownership; hardware-init unwind; real device/domain attach and detach; DMA-backed/coherent page tables; bounds/rollback and TLB invalidation; integrated kernel link. Activation gate remains BLOCKED.
