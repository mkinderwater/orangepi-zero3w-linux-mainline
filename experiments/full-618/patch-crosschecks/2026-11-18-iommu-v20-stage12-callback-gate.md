# A733 IOMMU v20 Stage 12: group callback and ownership gate

**Status:** read-only evidence collection. Activation **BLOCKED**.

## Stage 11 operator result

The operator's `iommu-v20-stage11-core.txt` reports all 11 expected source markers present. SHA256: Linux 6.18 `iommu.c` `f130ba36dcb140e3e749f3cb77ca7a2df15033843d4d15ae55b8803fa60f2082`, staged A733 driver `aa78ce2829693be1c27e93647244f50dd86dc4f386930b2301ba8990b7d19b53`, linked object `495096f27313a88a758d049832a65949dac5ae88e97338bc660c243eb93c0d84`.

**11 source checks PASS. Runtime lifecycle safety FAIL / unresolved.** The Linux 6.18 core allocates default paging domains per group, requires first attach to succeed, can map before attach, and may reattach old domains on errors. The vendor returns a singleton pointer and acknowledges attachment without ownership selection.

## Stage 12 callback inventory

Read-only script `scripts/audit-a733-iommu-v20-stage12-callbacks.py`, commit `8c8d5d5`, extracts whole relevant callbacks from the exact staged C source and core. It intentionally reports any functions missing by name and exits nonzero when extraction is incomplete. Review the report even if a function is absent due to naming/API drift.

Vendor targets: `domain_alloc_paging`, `domain_free`, `attach_dev`, `device_group`, `of_xlate`, `probe_device`, `probe_device_finalize`, `release_device`, controller `probe`, `remove` and `hw_init`.

Core targets: `__iommu_probe_device`, `iommu_setup_default_domain`, `__iommu_group_set_domain_internal`, `__iommu_device_set_domain` and `__iommu_group_remove_device`.

This stage is to decide whether DE0 can be supported without allocating conflicting independent translation domains for other clients. The two alternative paths remain (a) a correctly integrated restricted DE-only group/probe model or (b) a fuller controller-aware implementation with proven multiple-group semantics. **Neither design is yet approved for hardware.**

```sh
cd /root/orangepi-zero3w-linux-mainline/orangepi-zero3w-linux-mainline
git pull --ff-only origin work/linux-6.18-full-integration
python3 scripts/audit-a733-iommu-v20-stage12-callbacks.py
cp /root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/iommu-v20-stage12-callbacks.txt /home/
```

No DTB, kernel, firmware, boot image or MMIO writes.
