# A733 IOMMU v20 Stage 7: ownership contract and design gate

**State:** source-contract verification, no runtime implementation or boot approval.

## Verified source comparison

- Linux **v6.18**, `drivers/iommu/iommu.c`, [pinned kernel source](https://github.com/torvalds/linux/blob/v6.18/drivers/iommu/iommu.c): `__iommu_paging_domain_alloc_flags()` calls `ops->domain_alloc_paging(dev)`, initializes the returned domain using `iommu_domain_init(domain, type, ops)`, and `iommu_domain_free()` invokes `domain->ops->free(domain)`. `__iommu_attach_device()` delegates to `domain->ops->attach_dev(domain, dev)` and rejects errors.
- Vendor A733 staged `sunxi-iommu-v2.c` SHA256 `aa78ce2829693be1c27e93647244f50dd86dc4f386930b2301ba8990b7d19b53` returns the same `global_iommu_domain` to repeated allocator calls, frees the object without clearing the global, and has unconditional attach success.
- Pinned public [Allwinner v20 reference](https://github.com/alexcaoys/allwinner-bsp/blob/656a550c826787e7e72fae58ca793df9e0988ac8/drivers/iommu/sunxi-iommu-v2.c) allocates fresh domain structs but still assumes a global controller/page-table subsystem and does not establish the full A733 master/domain and DMA correctness contract. Do not cherry-pick its allocator alone.

## Decision: do not extend Stage 6 as a runtime fix

A mutex around `global_iommu_domain` is insufficient: Linux tracks individual domain ownership and may allocate/free per group. Returning NULL for a second request prevents pointer aliasing but may break otherwise valid multi-group setup. Publishing the global after init prevents early observation but does not prove hardware init does not require it internally; hardware state may not roll back on error.

For the current A733 revision, the proposed implementation approach is a **single hardware translation context with explicit ownership**, only if the actual v20 register interface and DE/master topology confirm one context. If the hardware supports multiple domains, implement per-domain state and translation selection instead. Neither assumption is established yet.

## Required state transitions before coding runtime activation

| Transition | Safety property |
|---|---|
| controller probe -> ready | registers, clocks, reset, IRQ, DMA device and caches valid; no client enabled |
| request domain | return a **unique core-owned** domain instance or an explicit error; never alias one allocation across owners |
| initialize page tables | allocate valid DMA-backed/coherent memory, no raw physical addresses as DMA handles |
| attach master to domain | select supported context; validate stream/master IDs and old domain; no unbound master enabled |
| map / unmap | checked ranges, rollback or exact partial map reporting; sync page tables and invalidate PTW/TLB correctly |
| detach master | disable translation safely, quiesce in-flight DMA and revoke attachment before domain free |
| free domain | only after all attached masters detach; reclaim DMA mappings and tables exactly once |
| failure/remove/suspend | no dangling global pointers; no partially enabled devices; restore state only if fully valid |

## Mandatory tests

1. One client allocates/maps/unmaps/frees, including repeated recreation.
2. Two concurrent groups allocate/attach. Verify unique ownership or deliberate failure **without** shared pointers or hardware cross-talk.
3. Inject allocation failures at each buffer, mapping and hardware-init step. Ensure cleanup and retry.
4. Detach/remove during outstanding mapping, with proper serialization.
5. Validate 34-bit IOVA and page-table physical addressing, DMA masks, physical address remap below 0x40000000.
6. Validate IOTLB gather end semantics and PTW invalidate ordering, including failed and partial maps.
7. Full disposable kernel link with the exact config and verified DT bindings, then independent review before hardware.

## Stage 7 tool

`scripts/check-a733-iommu-v20-stage7-contract.py`, commit `8f53fc7`, checks the local Linux `iommu.c` for the expected contract and verifies the exact staged vendor and combined ELF hashes. It is strictly read-only. Its successful completion means **the contract was detected, not that runtime blockers were fixed**.

```sh
cd /root/orangepi-zero3w-linux-mainline/orangepi-zero3w-linux-mainline
git pull --ff-only origin work/linux-6.18-full-integration
python3 scripts/check-a733-iommu-v20-stage7-contract.py
cp /root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/iommu-v20-stage7-contract.txt /home/
```

## Status

B1, B2, B3, B4, B5, B6 and B7 remain open. Activation gate remains BLOCKED. Known-good Linux 6.18 kernel, DTB and boot images untouched.

## Stage 7 operator contract result

The operator provided `iommu-v20-stage7-contract.txt`, which reports all expected Linux 6.18 core contract markers present. Audited vendor hash `aa78ce2829693be1c27e93647244f50dd86dc4f386930b2301ba8990b7d19b53`, local `drivers/iommu/iommu.c` hash `f130ba36dcb140e3e749f3cb77ca7a2df15033843d4d15ae55b8803fa60f2082`, relocatable combined object hash `495096f27313a88a758d049832a65949dac5ae88e97338bc660c243eb93c0d84`.

**Contract check PASS; design compatibility FAIL.** The tool confirms core alloc/free/attach delegation and unsafe vendor shared-domain aliasing. No resolution is implied.

## Stage 8 topology source inventory

Commit `1b3501c` adds `scripts/audit-a733-iommu-v20-topology.py`, a fail-closed read-only inventory for the exact staged driver, vendor IOMMU headers and likely A733/sun60 device trees. It extracts line-numbered register definitions, master ID usage, global translation programming and IOMMU consumer references, with source hashes, for topology review. This does NOT establish the translation register semantics or permit enabling the hardware.

Run:
```sh
cd /root/orangepi-zero3w-linux-mainline/orangepi-zero3w-linux-mainline
git pull --ff-only origin work/linux-6.18-full-integration
python3 scripts/audit-a733-iommu-v20-topology.py
cp /root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/iommu-v20-stage8-topology.txt /home/
```

Next compare the captured registers and IOMMU DTS master IDs with the vendor A733 hardware description before selecting either one shared controller context with controlled group attachment or multiple isolated domain instances. No runtime patch yet.
