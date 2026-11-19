# A733 IOMMU v20: Stage 8b focused topology findings

**State:** vendor translation model characterized, A733 device-tree routing unverified; hardware activation **BLOCKED**.

## Operator evidence

Uploaded `iommu-v20-stage8b-focused.txt`, read-only audit against staged driver SHA256 `aa78ce2829693be1c27e93647244f50dd86dc4f386930b2301ba8990b7d19b53`.

- Driver declares `IOMMU_HW_SET_COUNT 2`, `IOMMU_PER_SET_ADDR_SIZE 0x10000`, and `IOMMU_MIC_MAX_MASTER 6`: 12 master positions across two register sets.
- Translation-table base `IOMMU_TTB_REG = 0x0020`. `WRITE_EQUAL_REG` writes the same register value to the first and second hardware sets. In `sunxi_iommu_hw_init()`, `dte_addr = __pa(sunxi_domain->pgtable)` and `WRITE_EQUAL_REG(iommu, IOMMU_TTB_REG, dte_addr >> 14)`: the vendor implementation programs the **same page-table base** for both.
- `__sunxi_enable_device_iommu_unlocked()` converts global master ID into hardware set and master slot, then changes `IOMMU_MIC_BYP_REG`. This controls bypass, not a per-master page-table base.
- Initial hardware init also changes all masters' bypass settings before completing controller enablement. On timeout/error, partial hardware state remains an explicit rollback concern.
- This supports a **single translation address space in the BSP implementation**. It does NOT prove that undocumented A733 hardware modes lack additional contexts. Do not implement independent Linux paging domains without context-selection evidence.

## DTS scan gap

- Vendor DTS root `/root/opi3w-vendor-6698-work/kernel/bsp/arch/arm64/boot/dts`: **MISSING**.
- Mainline staged kernel `arch/arm64/boot/dts`: **2582** DTS/DTSI files scanned; **125** contained IOMMU-related strings. These broadly cover unrelated SoCs, not necessarily A733.
- No A733-specific node or explicit `allwinner,iommu-v20` consumer mapping was found in this report.
- Search the actual vendor image source, build output and DTS overlay directories, not general-purpose kernel DTS trees alone. No DTS must be invented from addresses.

## Design impact

A single hardware TTB with multiple IOMMU core domains requires explicit arbitration and lifecycle rules, not shared pointers returned from `domain_alloc_paging`. Linux 6.18 expects every allocated paging domain to be independently core-owned. The simplest plausible design is to support one active translation domain per controller with safe rejection of incompatible additional domains and an explicit master attachment table, **but this must be reconciled with Linux group creation and vendor master routing first**.

Still blocked:
1. Reliable domain ownership and concurrency.
2. DMA mapping/coherence and page-table buffer lengths.
3. Hardware init rollback, master enable and detach.
4. Map/unmap failure handling and TLB/PTW synchronization.
5. Real A733 DTS topology and full kernel linkage.

No original kernel, DTB, boot image or firmware changed.
