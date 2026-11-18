# A733 IOMMU v20 Stage 16: probe failure unwind draft

**Status:** source-only draft. No AArch64 compilation yet. No hardware activation.

## Source basis

This stage uses the operator-reviewed Stage 15 generated file at
`/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/iommu-v20-stage15-teardown-draft.c`.
It preserves the Stage 14 shared-group reference patch and Stage 15 unregister-first teardown patch.
The Stage 12 callback audit exposed the original probe ordering and cleanup labels.

## Proposed error-path changes

- Treat `devm_ioremap_resource()` failure using `IS_ERR/PTR_ERR`.
- Propagate negative IRQ, reset, clock and controller-version errors instead of returning undefined/stale `ret`.
- Initialize the count of requested IRQs; use device-managed IRQ/MMIO release on failure without manually freeing them a second time.
- Track successfully deasserted resets and enabled clocks, unwind in reverse order.
- Allocate and initialize a sentinel-terminated clock list with `kcalloc`; free it on failure, retaining it on success.
- Zero-initialize controller platform data before partial parse so error cleanup can safely check its master pointers.
- Track vendor sysfs and core sysfs registration and pair removal with the completed stages.
- Clear `global_iommu_dev` after a failed probe, free platform data and the page-table cache, clear drvdata.
- Retain existing core registration workflow for now; do **not** assume that probe error cleanup automatically makes core client registration safe.

## Scope limits that still block runtime

This draft **does not** fix:

1. Existing global domain allocation, attach_dev without domain selection, domain free and double-free/UAF hazards.
2. Valid DMA mapping handles and page-table sync/clear bounds.
3. Partial IOMMU hardware initialization rollback, bypass master enabling, TLB/PTW ordering and mapping error rollback.
4. Successful removal's missing clock disable/reset assert and platform-data release, alongside possible sysfs IRQ ordering defects.
5. Stale DMA-device globals after a failed register/remove and possible external domain users.
6. Lifetime and concurrency of the shared group during registration/removal and failures; the group ref fix remains a draft.
7. The vendor master distribution callback's ownership and failure unwind before page-table cache allocation.

**This is not a boot candidate.**

## Artifacts and commands

- `scripts/draft-a733-iommu-v20-stage16-probe.py`: guarded generator for `.c` and unified diff; does not modify input.
- `scripts/test-a733-iommu-v20-stage16-probe.py`: ten structural checks for error propagation, resource cleanup and preservation of blockers. Passing them is not compilation or runtime proof.

```sh
cd /root/orangepi-zero3w-linux-mainline/orangepi-zero3w-linux-mainline
git pull --ff-only origin work/linux-6.18-full-integration
python3 scripts/draft-a733-iommu-v20-stage16-probe.py
python3 scripts/test-a733-iommu-v20-stage16-probe.py
D=/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts
cp "$D/iommu-v20-stage16-probe-draft.patch" /home/
```

If a marker mismatch occurs, stop and audit the actual staged C source rather than relaxing the guard or editing the proven kernel. **Do not activate or boot.**
