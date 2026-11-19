# A733 IOMMU v20: Stage 12 callback findings and Stage 13 gate

**Status: offline evidence, hardware activation BLOCKED.**

## Verification

The operator uploaded `iommu-v20-stage12-callbacks.txt`. All **16** named vendor/core callbacks were extracted (`MISSING_CALLBACKS 0`). Local vendor SHA256 `aa78ce2829693be1c27e93647244f50dd86dc4f386930b2301ba8990b7d19b53`; Linux 6.18 `iommu.c` SHA256 `f130ba36dcb140e3e749f3cb77ca7a2df15033843d4d15ae55b8803fa60f2082`.

### Central new finding

Vendor `sunxi_iommu_device_group()` allocates `global_group` only once, then returns the same group for all vendor IOMMU clients. The Linux core allocates a default paging domain **per group**. Therefore, the vendor source intentionally presents all clients as one IOMMU group, rather than one default domain per master. **This weakens the Stage 11 assumption that all masters must necessarily cause multiple default-domain allocations.**

A shared group and single TTB can be conceptually compatible for ordinary initial group setup; it is a **coarse isolation policy** and it does not solve arbitrary later `iommu_paging_domain_alloc`, domain switching, or the lifetime of externally allocated domains. Do not treat this as a Linux v6.18 runtime PASS.

### Evident source hazards

- `sunxi_iommu_domain_alloc_paging` returns the same `global_iommu_domain` pointer to repeat calls; the global is set before hardware init, and init errors are only logged. `sunxi_iommu_domain_free` frees the object without clearing the global. Risk: aliasing, stale pointer, UAF/double free.
- `sunxi_iommu_attach_dev` returns 0 with no ownership verification, master programming, or domain switch.
- `sunxi_iommu_probe_device_finalize` calls `sunxi_enable_device_iommu(owner->tlbid, owner->flag)`. This is a **separate core phase**; determine exact ordering and guarantee initialization and domain installation before enablement.
- `sunxi_iommu_device_group` constructs one `iommu_group` but no explicit per-device group-get in the function. Review how Linux core manages references for callback-returned groups; avoid speculative refcount fixes.
- `sunxi_iommu_of_xlate` reads `args[0]` and `args[1]` without explicit count check; an existing owner is returned unconditionally with no conflict detection. `of_find_device_by_node` reference lifecycle must be checked.
- Probe error paths may return uninitialized `ret`, do not unwind all enabled clocks/resets/global pointers, and do not always clean up controller registration.
- `sunxi_iommu_remove` frees PTE cache and other resources while teardown ordering and outstanding clients are unproven.
- Existing unsafe DMA sync addresses, page-table clearing sizes and map rollback defects remain independently blocking.

## Stage 13 follow-up

Read-only script `scripts/audit-a733-iommu-v20-stage13-group.py` extracts local Linux 6.18 group reference and registration call sites beside vendor group and lifecycle callbacks. The output supports an explicit design decision for **single-group-first** vs **DE-only**.

```sh
cd /root/orangepi-zero3w-linux-mainline/orangepi-zero3w-linux-mainline
git pull --ff-only origin work/linux-6.18-full-integration
python3 scripts/audit-a733-iommu-v20-stage13-group.py
cp /root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/iommu-v20-stage13-group.txt /home/
```

Keep the Stage4 kernel, DTB, original image and firmware unchanged. Do not enable IOMMU translation or attempt a boot.
