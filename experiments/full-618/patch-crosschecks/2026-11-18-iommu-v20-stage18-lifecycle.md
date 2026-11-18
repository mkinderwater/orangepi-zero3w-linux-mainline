# A733 IOMMU v20 Stage 18: provider cleanup contract

**Status:** offline failure-injection specification. No kernel patch or hardware activation.

## Evidence from operator's Stage17 report

Audited source hashes:
- v20 driver `aa78ce2829693be1c27e93647244f50dd86dc4f386930b2301ba8990b7d19b53`
- Linux 6.18 IOMMU core `f130ba36dcb140e3e749f3cb77ca7a2df15033843d4d15ae55b8803fa60f2082`
- page table driver `aacc30517e7101177d55f4c67bbeaa4ab6ae7f70a4d15eecf9ab81197fdd6017`

The report resolves three questions:

1. `sunxi_pgtable_set_dma_dev(struct device *)` simply assigns `sunxi_pgtable_params.dma_dev`; no dedicated reset callback exists. The same setter can accept `NULL`, **but only after all page-table operations and outstanding DMA users are quiesced**. The vendor global `dma_dev` must also be cleared if this provider owns it.
2. `sunxi_iommu_sysfs_create` returns `void` and ignores the return values of three `device_create_file` operations. A caller boolean cannot prove complete sysfs creation. Change to error-returning helper with reversal of successful creates; assess optional debugfs creation independently. `sysfs_remove` must be paired only with successful creation.
3. Linux 6.18 `iommu_device_register()` adds the provider to a list and calls `bus_iommu_probe()`. On error it **already invokes `iommu_device_unregister()`**, which traverses buses to release clients and removes the provider. Therefore, probe error cleanup must not call unregister again. This does **not** prove that every core partial error path is leak-free, nor that external domains are absent.

The normal vendor remove path does not free its clock array or parsed platform data and does not balance clock enables or deasserted resets. Those operations must be paired after IOMMU client/domain shutdown and when no active interrupt or other user can touch the controller.

## Required order for next C draft

1. Allocate controller-owned cache and resources. Track successful acquisition, not merely attempted acquisition.
2. Set up reset and clocks. Check every return code. On failure, unwind only completed operations in reverse order.
3. Create sysfs entries one at a time, return on first failure and undo successful entries.
4. Set DMA pointer only when page-table operations can safely use it and before any client callbacks; establish precise point when clearing is safe.
5. Register provider; if registration returns an error, assume the core has already unregistered the provider. Do not unregister twice.
6. Successful removal: unregister provider and quiesce all registered clients and domain users **before** clearing DMA pointer or freeing cache, then unwind resources in reverse order. Verify IRQ/sysfs/debugfs and clock/reset ordering.
7. Global group/domain pointer lifetime must be proved independently; neither the Stage 18 model nor Stage 14 draft proves it.

## Offline acceptance model

`scripts/test-a733-iommu-v20-stage18-lifecycle.py` covers 12 scenarios: normal removal, core registration failure, partial sysfs failure for each entry, cache/reset/clock faults, registration ordering, reverse sysfs removal, DMA-pointer clearing, refusal to free cache while clients are active, repeat cleanup and per-stage failure invariants.

The model is **not** a kernel test. It intentionally represents the expected cleanup contract and avoids claiming that the current C implementation meets it.

```sh
cd /root/orangepi-zero3w-linux-mainline/orangepi-zero3w-linux-mainline
git pull --ff-only origin work/linux-6.18-full-integration
python3 scripts/test-a733-iommu-v20-stage18-lifecycle.py |& tee /home/iommu-v20-stage18-model.txt
```

## Outstanding hardware blockers

Global domain alias/UAF, unconstrained attach, invalid DMA sync handles/bounds, partial mapping rollback, TLB/PTW lifecycle, MMIO initialization failure, and unknown external-domain usage. **No production kernel, DTB, firmware, boot image or IOMMU enablement changes.**
