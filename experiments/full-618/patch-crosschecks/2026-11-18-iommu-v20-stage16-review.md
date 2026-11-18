# Stage 16 probe unwind: review and blockers

**Status:** source-only experiment. Not compiled or approved for boot or hardware activation.

## Proposed corrections

The Stage 16 draft adds IS_ERR/PTR_ERR for MMIO mapping, propagates IRQ, clock and reset failures, tracks successfully enabled clocks and deasserted resets for reverse cleanup, zero-initializes platform data, returns an error on controller version mismatch, and introduces sysfs cleanup guards. These are improvements to the original vendor probe.

## Unresolved findings

1. **DMA device global lifetime**: Probe sets `dma_dev = &pdev->dev` and `sunxi_pgtable_set_dma_dev(dma_dev)`. Stage 16 does not prove both pointers are reset on provider-registration failure or removal. Verify whether the setter has an inverse operation before writing a fix.
2. **Registration failure behavior**: `iommu_device_register()` may probe clients and allocate a default domain while registering. Audit its failure path and any cleanup it performs before assuming the provider can release controller resources.
3. **Vendor sysfs helper**: Verify return signature and partial-creation cleanup of `sunxi_iommu_sysfs_create()`. Setting `driver_sysfs = true` without checking actual helper behavior is insufficient.
4. **Successful removal**: Stage 15 still does not balance enabled clocks, reset lines, clock arrays, or allocated platform-data fields on normal remove.
5. **Domain and DMA safety**: The global domain alias, unconditional attach, hardware init rollback, page-table DMA sync/clearing, map failure rollback, and TLB/PTW ordering remain unresolved.
6. **Build evidence**: No AArch64 Stage 16 compile log has been submitted. Even a successful object build would only verify compile compatibility.

## Next gate

Inspect exact local `sunxi_pgtable_set_dma_dev`, `sunxi_iommu_sysfs_create`, `iommu_device_register`, core rollback and controller cleanup paths. Require source hashes, small complete function excerpts and a failure-path matrix. Draft probe/remove changes only after that review, outside the proven Stage4 tree.

**No production kernel, DTB, firmware or image changes. Hardware activation BLOCKED.**
