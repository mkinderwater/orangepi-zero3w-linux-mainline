# A733 IOMMU v20 Stage 9: vendor device-tree topology

**State:** Vendor routing established. Hardware activation remains **BLOCKED**.

## Provenance

Read-only operator extraction `iommu-v20-stage9-vendor-dts.txt` from `/root/opi3w-vendor-6698-work/tree-identity`:

| Source | SHA256 |
|---|---|
| `arch/arm64/boot/dts/allwinner/sun60iw2p1.dtsi` | `1c7313f655bdc4d018201664adcb1fa1d100280388b8975e193ebbfc6ad4ddfa` |
| `arch/arm64/boot/dts/allwinner/sun60i-a733-orangepi-zero3w.dts` | `90d4f68ecb901370d2772f96af18b7f2da6ae7d2f9611481b06bdb23cf924f10` |
| `bsp/configs/linux-6.6/sun60iw2p1.dtsi` | `d68616db1d2755fbf13730d34e1edadb474cf7e5deb93ca982295b6e2a5edba4` |

The board-specific DTS had no IOMMU-related grep matches. It likely inherits the SoC nodes; verify full include chain and generated DTB before assuming a runtime setting.

## Actual IOMMU provider

```dts
mmu_aw: iommu@3900000 {
    compatible = "allwinner,iommu-v20";
    reg = <0x0 0x03900000 0x0 0x20000>;
    interrupts = <GIC_SPI 170 IRQ_TYPE_LEVEL_HIGH>,
                 <GIC_SPI 171 IRQ_TYPE_LEVEL_HIGH>;
    #iommu-cells = <2>;
    version = <0x16>;
    tlb_prefetch = <0x3007f>;
    tlb_invalid_mode = <0x1>;
    ptw_invalid_mode = <0x1>;
};
```

Six clocks (IOMMU0 H/P/MBUS, IOMMU1 H/P/MBUS) and two resets `RST_BUS_IOMMU0_SY`, `RST_BUS_IOMMU1_SY`.

Per-master numbers correspond to two sets with six positions each:
- 0 USB, 1 CSI, 2 ISP, 3 VE_ENC
- 4, 5 dummy/skipped
- 6 VE_DEC0, 7 VE_DEC1
- 8 DE0, 9 DI, 10 G2D, 11 EINK
- `DEBUG_MODE` occurs in the `masters` string array after EINK; not a configured 12th numbered hardware master in the child list.

The DE block is `compatible = "allwinner,display-engine-v352"` at `0x05000000`, with `iommus = <&mmu_aw 8 1>` and `SUN60IW2_PCK_DE_SYS` power-domain binding. The second cell is the vendor's per-master flag. Other consumers have flag 0 or 1; **do not treat it as a Linux domain selector** without evidence from `sunxi_iommu_of_xlate`. DI/G2D/EINK share DE's power domain.

The vendor driver defines `IOMMU_HW_SET_COUNT = 2`, `IOMMU_MIC_MAX_MASTER = 6`, `IOMMU_PER_SET_ADDR_SIZE = 0x10000`; ID 8 maps to hardware set 1, slot 2, bypass register `0x03910000 + 0x400 + (2 * 0x200) + 0x4 = 0x03910804`. **Derived from vendor register offset macros, not a tested register access.** Do not touch MMIO.

## Translation architecture evidence

In the audited driver, `sunxi_iommu_hw_init()` writes `__pa(sunxi_domain->pgtable) >> 14` via `WRITE_EQUAL_REG(IOMMU_TTB_REG)` at the same offset in both hardware sets. Per-master bypass only enables/disables translation; it does not select page-table bases. This strongly supports a **single shared translation address space in the vendor driver**. The DTS confirms master routing but does **not** itself prove the silicon cannot support other modes.

## Implementation decision

Do **not** return a shared `global_iommu_domain` pointer from multiple Linux 6.18 `domain_alloc_paging` calls. Do not allocate multiple independent page tables and bind them to masters until hardware context selection is demonstrated.

Design gate: controller-owned *single active hardware translation context* with a verified Linux core group/domain ownership scheme, explicit master membership and bypass state, one valid page-table DMA handle, serialized transitions and fail-closed second incompatible domain requests. Check Linux 6.18 group assignment semantics so rejecting a second domain does not break the intended DE path. No runtime patch until lifecycle and DMA design are validated.

## Remaining blockers

- Multiple Linux-owned domain requests vs one hardware TTB
- DMA-safe page table allocation, sync and free, including 34-bit IOVA and address conversion
- Device attachment/teardown, init rollback, concurrency, mapping rollback and TLB/PTW ordering
- Board-specific DTS inheritance and DTB settings; full kernel link, runtime validation

**No source, DTB, image, firmware or MMIO modifications.**

## Operator verification: compiled Zero 3W DTBs and `of_xlate`

The operator confirmed two compiled board DTBs:

- `/root/opi3w-vendor-6698-work/obj-control/arch/arm64/boot/dts/allwinner/sun60i-a733-orangepi-zero3w.dtb`
- `/root/opi3w-vendor-6698-work/obj-identity/arch/arm64/boot/dts/allwinner/sun60i-a733-orangepi-zero3w.dtb`

Their contents and hashes have **not yet** been compared. The audited driver `sunxi_iommu_of_xlate()`, lines 1142-1168, reads `args->args[0]` as `owner->tlbid`, `args->args[1]` as `owner->flag`, records the IOMMU controller and device pointers, and caches the owner in `dev_iommu_priv_set`. For the DE, `<&mmu_aw 8 1>` therefore means master 8, master flag 1, **not** Linux domain 1.

Additional source-level checks before runtime:
- Verify `args->args_count == 2` and `tlbid < 12` before reading or using the IDs.
- Existing `owner` returns success without checking whether a repeated translation declaration contradicts the first (master, flag, controller).
- Balance `of_find_device_by_node` reference ownership, confirm device and controller lifetime, and inspect failure unwind.
- Defer enabling master translation until successful domain attachment and DMA page-table synchronization.

Follow-up: compare both compiled Zero3W DTBs read-only, inspect decompiled IOMMU provider and DE0 consumer nodes, and record hashes. No DTB modifications or MMIO access.
