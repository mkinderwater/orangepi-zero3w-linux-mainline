# A733 IOMMU v20 Stage 14: controller-held group + per-client references

**Scope:** Linux 6.18, source-only draft and offline model. **Not runtime safe.**

## Stage 13 operator result

Operator uploaded `iommu-v20-stage13-group.txt`, reporting `MISSING 0`. Audited core SHA256 `f130ba36dcb140e3e749f3cb77ca7a2df15033843d4d15ae55b8803fa60f2082`, vendor driver SHA256 `aa78ce2829693be1c27e93647244f50dd86dc4f386930b2301ba8990b7d19b53`. This confirms all searched symbols exist, **not** that reference counts are safe.

## Verified Linux v6.18 group reference rules

Upstream `drivers/iommu/iommu.c`:
- `iommu_init_device()` obtains the driver's `ops->device_group(dev)` pointer and assigns it to `dev->iommu_group`. It does **not** get an additional reference.
- `__iommu_group_remove_device()` executes `iommu_group_put(group)`, explicitly paired with the reference from `iommu_init_device()` or `iommu_group_add_device()`.
- `iommu_group_alloc()` returns one initial reference intended to hold the group while devices are added, with `iommu_group_put()` required when finished.
- `generic_single_device_group()` retains its allocated group pointer and **returns `iommu_group_ref_get(iommu->singleton_group)` for each client**, proving the expected ownership pattern.
- `iommu_device_unregister()` first removes all clients referencing that IOMMU, then removes the provider registration. Only after this should the controller release its retained group reference.

A733 vendor `sunxi_iommu_device_group()` caches `global_group` but returns it directly, **without one reference per client**, causing premature reclaim/stale global pointer or double put when multiple clients exist.

Source: https://github.com/torvalds/linux/blob/v6.18/drivers/iommu/iommu.c

## Two independently tested approaches

**A. Recommended:** one controller-held reference plus a reference per client. Serialize group creation and controller-held reference removal. Return `iommu_group_ref_get(global_group)` on every callback, including the first. After `iommu_device_unregister()` has removed all clients, clear `global_group` and put its initial controller-held reference.

**B. Rejected:** hand the initial `iommu_group_alloc()` reference to the first device and reuse the raw pointer for all subsequent devices. Linux frees that first device's ref on removal, leaving later devices and `global_group` with a possibly freed pointer. This cannot be repaired by a mutex alone.

## Artifacts

- `scripts/test-a733-iommu-v20-stage14-group-refs.py` is an offline seven-scenario test model. Tests ownership for single/multiple clients, failed probe cleanup, duplicate callback, busy unregister, reprobe and double-release.
- `scripts/draft-a733-iommu-v20-stage14-group-refs.py` generates a C draft plus unified diff **outside** the kernel source tree. It requires the exact Stage 5 source SHA256, and refuses to overwrite outputs. The proposed change takes one group reference per client and drops the controller-held ref following provider unregister. **The draft still needs AArch64 compile and independent lifecycle review before integration.**

```sh
cd /root/orangepi-zero3w-linux-mainline/orangepi-zero3w-linux-mainline
git pull --ff-only origin work/linux-6.18-full-integration
python3 scripts/test-a733-iommu-v20-stage14-group-refs.py
python3 scripts/draft-a733-iommu-v20-stage14-group-refs.py
D=/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts
cp "$D/iommu-v20-stage14-group-refs-draft.patch" /home/
```

## Hard blockers

This group reference patch does **not** fix unsafe global domain aliasing; attach success without binding; device-core first attachment; controller MMIO init rollback; DMA-synced page tables and DMA mapping; TLB and PTW consistency; release ordering before freeing the page-table cache; or all concurrent registration/remove interleavings. The patch must **not** be merged into a bootable image simply because it compiles.

Never modify the proven Stage4 kernel, DTB, firmware, or images. Hardware activation remains blocked.
