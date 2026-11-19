# A733 v20 IOMMU Stage 11: Linux 6.18 group lifecycle gate

**Status:** Stage 10 offline state machine passed 10/10. Stage 11 has identified a structural conflict between that model and the actual IOMMU core. Runtime hardware use **BLOCKED**.

## Source evidence (Linux v6.18, drivers/iommu/iommu.c)

- `__iommu_group_alloc_default_domain()` obtains a domain from `__iommu_paging_domain_alloc_flags(dev, req_type,...)` for each IOMMU group. The resulting domain is individually core-owned.
- `iommu_setup_default_domain()` establishes DMA cookie and required direct mappings before attachment and may replace an existing default domain. Initial attachment cannot be rejected as a normal fallback: the core explicitly states, “Drivers are not allowed to fail the first domain attach.”
- `__iommu_group_set_domain_internal()` iterates all devices in a group. On failure, it attempts rollback to the former domain. `err_restore_domain` also reattaches the old domain when changing the default.
- `iommu_domain_free()` uses each domain's free callback. Reusing one global `struct iommu_domain *` for separately allocated groups is invalid.
- The A733 vendor IOMMU v20 source `sunxi_iommu_hw_init()` writes the same page-table base to both HW sets through `WRITE_EQUAL_REG(IOMMU_TTB_REG)`. Per-master bypass controls alone cannot select independent page tables.

Reference source: https://github.com/torvalds/linux/blob/v6.18/drivers/iommu/iommu.c

## Consequence for Stage 10 proposal

The Stage 10 offline model rejected a second domain but did not simulate the Linux core attaching two separately-created groups. It is an acceptance sketch, **not a compatible implementation**. Rejecting a second group by default may cause group probe or DMA setup to fail. Likewise, merely sharing a table pointer across domains while claiming independent mapping ownership is unsafe because map/unmap and free are per domain.

### Competing designs for review

**A. Single globally shared default domain through sanctioned IOMMU core facilities**: Determine whether an existing Linux API allows a shared default paging domain across distinct IOMMU groups with well-defined lifetime. The legacy `ops->default_domain` is explicitly constrained in the Linux v6.18 core to IDENTITY/BLOCKED/PLATFORM types, **not a newly implemented DMA paging domain**. Do not use it as a shortcut.

**B. Separate core-owned group domains with one hardware context**: Only viable if all attached groups are guaranteed to share exactly the same translation mappings and can never race on mapping/free, which is not guaranteed by generic DMA domains. Without a fundamental group/interface constraint, this is **not safe**.

**C. Restrict the driver to one supported client group**: A narrowly scoped first implementation might bind only DE0 with verified master 8, and reject unrelated clients before IOMMU registration and first-domain creation. Requires evidence that default-domain allocation for DE0 happens once and that all other consumers remain unbound. A second domain allocation for the same group (e.g. domain switch) still requires a sound transition and rollback. The vendor's original DT includes many other master consumers, so this requires a strictly isolated experimental DT design, NOT editing the proven DTB.

**Decision now:** No runtime source patch. First collect the exact `device_group`, `probe_device`, `probe_device_finalize`, `release_device`, `domain_alloc_paging`, `domain_free`, and `attach_dev` code and model their full interaction with the Linux v6.18 group logic. Verify the expected DE-only or multi-group environment before choosing design C or undertaking a larger upstream-style refactor.

## Read-only gate

Script: `scripts/audit-a733-iommu-v20-stage11-core.py`, commit `2e8748f`. It verifies SHA256 for the staged core, vendor driver and combined ELF and checks the specific code paths above. It produces an evidence report but **must not** be interpreted as a runtime readiness PASS.

```sh
cd /root/orangepi-zero3w-linux-mainline/orangepi-zero3w-linux-mainline
git pull --ff-only origin work/linux-6.18-full-integration
python3 scripts/audit-a733-iommu-v20-stage11-core.py
cp /root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/iommu-v20-stage11-core.txt /home/
```

## Security and preservation

Do not alter original Stage4 kernel, DTB, image or firmware. Do not enable A733 IOMMU masters, write MMIO, or boot this draft driver. Existing DMA, failure-unwind, and TLB/PTW concerns remain open.
