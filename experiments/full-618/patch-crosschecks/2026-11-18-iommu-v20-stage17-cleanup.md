# Stage 17: A733 IOMMU provider lifecycle evidence gate

**Scope:** Read-only audit of Linux 6.18 IOMMU v20 probe, remove, sysfs and DMA-device globals. No driver patch or boot approval.

## Why this gate is necessary

The Stage 16 probe error cleanup draft addresses error pointers, clocks, resets and sysfs partially. Independent review still identified missing or unverified lifetime contracts:

- `dma_dev` and the page-table subsystem's DMA-device pointer may outlive a failed provider registration or controller removal.
- The vendor sysfs create helper may have a partial-failure path; the Stage 16 draft assumes that creating sysfs entries always reaches a complete state.
- `iommu_device_register()` can trigger core device probing, so its failure behavior must be checked before freeing any controller resource.
- Successful `sunxi_iommu_remove()` in Stage 15 does not balance clock enables, reset deassertions, clock allocation and platform-data lifetime.
- Shared group references and externally held domain pointers may still outlive unregister.

These are hypotheses or known source concerns, **not** reasons to assert the Stage 16 patch is runtime safe.

## Focused artifact

`scripts/audit-a733-iommu-v20-stage17-cleanup.py`, commit `c3495b9`, records SHA256 for exact local source files, extracts named function definitions with line numbers, and indexes all references to DMA-device pointers, sysfs helpers, IOMMU registration, globals, and clock/reset cleanup.

It checks the audited staged `sunxi-iommu-v2.c` SHA256 `aa78ce2829693be1c27e93647244f50dd86dc4f386930b2301ba8990b7d19b53`, Linux `iommu.c` SHA256 `f130ba36dcb140e3e749f3cb77ca7a2df15033843d4d15ae55b8803fa60f2082`, and page-table source SHA256 `aacc30517e7101177d55f4c67bbeaa4ab6ae7f70a4d15eecf9ab81197fdd6017`. If any differ, stop and re-audit. The `sunxi-iommu-common.c` source is inventoried without an asserted hash.

### Run

```sh
cd /root/orangepi-zero3w-linux-mainline/orangepi-zero3w-linux-mainline
git pull --ff-only origin work/linux-6.18-full-integration
python3 scripts/audit-a733-iommu-v20-stage17-cleanup.py
cp /root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/iommu-v20-stage17-cleanup.txt /home/
```

## Acceptance sequence

1. Inspect actual DMA-device setter and ownership, and sysfs helper return/error semantics.
2. Confirm core `iommu_device_register` rollback for all clients after partial probe.
3. Design one shared, symmetric resource-release path for both probe failure and normal remove, preserving core unregister-before-domain-free safety.
4. Build and test revised C source **only** in a separate disposable clone after the callback contract is confirmed.
5. Continue to block hardware activation pending domain ownership, DMA map/sync, and TLB/PTW validation.

The proven Stage4 kernel, DTB, firmware and boot images remain untouched.
