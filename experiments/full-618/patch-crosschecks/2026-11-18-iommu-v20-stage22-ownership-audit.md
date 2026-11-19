# Stage 22: exact C ownership inventory before domain rewrite

**Status:** read-only source evidence. No kernel patch. No hardware activation.

## Stage 21 acceptance

The operator ran all **13 offline ownership tests successfully**. Those tests model allocation, attachment, domain switches, rollback, shared-group consumers, and cache-lifetime constraints, but do not establish the C driver or hardware behavior.

## Why the next patch cannot safely be a simple pointer edit

The staged A733 IOMMU v20 driver has three coupled ownership layers:

1. **Linux IOMMU core:** Each domain allocation is individually owned and may be freed independently. One group can request a replacement domain while still holding the old domain.
2. **A733 hardware:** The vendor driver programs one common TTB across both IOMMU hardware sets. `attach_dev()` currently returns success without selecting or validating a domain. It cannot safely promise multiple independently mapped groups simultaneously.
3. **Page-table helper:** `sunxi_pgtable_params.pgtable` is a last-published pointer, not a domain count. The cache helper uses a global `sunxi_pgtable_params.iopte_cache`, and PTE operations use a separate global DMA device. Thus fixing `global_iommu_domain` alone will not establish correct last-owner teardown.

A correct patch needs **per-domain table ownership**, **controller-wide domain activation**, and **explicit tracking of live allocations and map/unmap users**. The table cache must remain alive until the final domain is freed and work is quiesced. It must also address the Linux core's first-attach and rollback expectations. A naive `return NULL` on a second allocation breaks domain replacement and potentially initial client setup.

## Stage 22 deliverable

`scripts/audit-a733-iommu-v20-stage22-ownership.py`, commit `e2c8d32`, is an exact SHA-pinned read-only inventory for the original staged driver and page-table source, plus separately generated Stage19 v2 and Stage20 draft files. It extracts the complete function bodies for domain alloc/free, attach, hardware TTB initialization, map/unmap, IOTLB sync, provider lifecycle, page-table allocation/free and cache lifecycle. It indexes every reference to ownership globals and DMA synchronization. It writes the evidence file but **always states that runtime activation is blocked**.

This is an input to a carefully bounded C patch, not a runtime test.

```sh
cd /root/orangepi-zero3w-linux-mainline/orangepi-zero3w-linux-mainline
git pull --ff-only origin work/linux-6.18-full-integration
python3 -m py_compile scripts/audit-a733-iommu-v20-stage22-ownership.py
python3 scripts/audit-a733-iommu-v20-stage22-ownership.py
cp /root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/iommu-v20-stage22-ownership.txt /home/
```

**Hard gate:** Inspect the resulting function inventory and design a controller lock, ownership count, domain activation protocol and page-table-global removal before coding. Preserve the known-good Stage4 source, DTB, firmware and boot images.
