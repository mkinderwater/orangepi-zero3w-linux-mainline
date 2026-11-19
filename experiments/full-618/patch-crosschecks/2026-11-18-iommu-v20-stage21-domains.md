# Stage 21: A733 IOMMU v20 domain ownership before cache destruction

**Status:** architecture and offline model. No C driver changes, compilation or hardware activation.

## Why Stage 20 is not sufficient

The Stage 20 page-table cache helper clears its global cache pointer before destruction, and rejects teardown when `sunxi_pgtable_params.pgtable` is non-null. However, a single last-published page directory pointer **cannot count all outstanding domains**. The existing vendor-derived staged driver returns `global_iommu_domain` to repeated allocations, frees it without invalidating that global, initializes hardware from domain allocation, and allows `attach_dev()` to return 0 without establishing the requested translation domain.

Linux 6.18 requires independently owned `struct iommu_domain` lifetimes. The default domain is group-owned, but other domains may be allocated for a domain switch. One shared group does not authorize returning the same allocation for each request.

## Required architecture

1. **Each allocation owns a distinct domain and page table**. No pointer alias from `global_iommu_domain`. Track outstanding domains with a controller-owned count/list under a lock that also guards teardown and domain-state transitions.
2. **Never program hardware in `domain_alloc_paging()`**. Linux may map reserved regions on a domain before attachment. Prepare a complete per-domain page table without publishing it to the hardware.
3. **`attach_dev()` must verify controller, domain membership, required mappings and transitions**. The physical A733 v20 driver writes the same TTB to both hardware sets. Its existing per-master bypass registers do not provide independent translation contexts. A domain replacement is a controller-wide operation requiring safe clock/power handling, table visibility and TLB/PTW flush. A new domain may not be reported attached if any step fails.
4. **A domain may not be freed while the hardware still points at its TTB.** Before final domain release, DMA masters must be quiesced and hardware must be detached/blocked or switched to another valid table. Linux core behavior for normal default-domain teardown must be checked against this rule. The current `release_device` bypass call needs proof that no masters still access the TTB.
5. **Cache destruction requires zero outstanding domain allocations**, zero page-table users, and no in-flight map/unmap, not merely `sunxi_pgtable_params.pgtable == NULL`. The Stage 20 guard is useful but insufficient.
6. The page-table subsystem has module-global `sunxi_pgtable_params.pgtable` and `iopte_cache`. Refactor this state or establish fully serialized one-domain-only operation with explicit rejection and Linux-compatible switch behavior. Do not treat a mutex around only global pointers as a sufficient fix.
7. A failed hardware switch must leave a provably valid prior domain or a blocked/identity state, never an unspecified TTB. Linux's group rollback attempts to reattach the previous domain and expects that operation to succeed.

## Offline acceptance model

`scripts/test-a733-iommu-v20-stage21-domains.py`, commit `3ec42e5`, covers 13 cases: independent allocations, mapping before attachment, rejection of unmapped attachment, failed switches, old-domain release after switch, active-domain free refusal, retained inactive domain cache block, group-client cache block, shared-table multi-client behavior, wrong-controller free, removal, double free and active-domain removal block.

**Important model limitation:** `Controller.attach()` abstracts the hardware TTB rewrite and TLB/PTW flush as one atomic step. This is deliberately stricter than the current C driver and does **not prove** that Linux group transitions, DMA mapping coherence, safe failover or actual A733 MMIO operations are implementable.

## Decision gate

First test the model. Next, produce a read-only audit of every existing `sunxi_pgtable_params.pgtable`, `global_iommu_domain`, map/unmap and TTB write reference in the **audited staged C files**, then decide whether to rewrite table ownership for distinct domains or constrain the exposed driver to one valid group/domain model. Do not apply Stage 19 or Stage 20 to a boot image. Any isolated C draft must later compile and pass lifecycle tests.

```sh
cd /root/orangepi-zero3w-linux-mainline/orangepi-zero3w-linux-mainline
git pull --ff-only origin work/linux-6.18-full-integration
python3 scripts/test-a733-iommu-v20-stage21-domains.py 2>&1 | tee /home/iommu-v20-stage21-domains.txt
```

The proven Stage4 kernel, DTB, firmware, boot images and real hardware are untouched.
