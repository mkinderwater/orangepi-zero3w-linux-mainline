# A733 IOMMU v20 Stage 10: offline shared-TTB ownership model

**Scope:** state-machine requirements and negative-path scenarios only. This is not kernel driver code. Hardware activation remains BLOCKED.

## Grounded inputs

- Vendor A733 provider `iommu@3900000`, 0x20000 register span, two interrupt lines, two sets with six master slots each.
- Vendor display engine `de@5000000` has `iommus = <&mmu_aw 8 1>`. Flag 1 is a vendor translation-enable flag, not an isolated domain ID.
- Vendor IOMMU driver programs the same TTB through `WRITE_EQUAL_REG` in both hardware sets and controls each master with a bypass register. It does not establish per-master context selection.
- Operator DTB comparison: control SHA256 `116f9c900d75bfae64fc24653c03108dc1cff56bbe3fdbbb9b291bbd25a49fc6`; identity SHA256 `5868cc38042c7de3d9a714f45215e90083223e2b0e2ec7eb3af87a064fb5e443`. IOMMU/DE0 excerpts match, **the full DTBs differ**.
- Linux 6.18 IOMMU core allocates/free domains independently. An identical global domain returned on multiple allocations is unsafe.

## Proposed state invariants

1. One controller-owned active translation context for this experimental A733 BSP model, pending full hardware manual verification.
2. A paging-domain allocation cannot alias an existing core-owned domain. A second incompatible allocation fails explicitly; whether Linux group setup tolerates this is **unverified**.
3. Failed initialization cannot publish a domain or enable any master, and must unwind software and actual hardware state.
4. Device-master ownership is explicit: IDs 0-11 exist, IDs 4-5 are skipped; master 8 belongs to DE0.
5. Master translation cannot be enabled before a verified context exists. Separate ownership required for each master, but several masters may share the *same* context only where core group/ownership semantics allow.
6. Reject stale domain generation, conflicting owners, out-of-range or skipped master IDs, and inconsistent translation flags.
7. Refuse domain free while any master remains attached, and refuse controller remove while a domain or client is active.
8. Actual serialization of alloc/attach/free/remove, device quiescence and DMA page-table correctness must be implemented and tested in kernel code before activation.

## Test artifact

`scripts/test-a733-iommu-v20-stage10-model.py`, commit `0a9782c`, defines a minimal **offline** model with ten positive/negative tests covering DE0, repeated allocation, initialization failure and retry, stale domain handles, duplicate master assignment, invalid and skipped IDs, unsupported flag, attached domain free, foreign detach, and shared display-system membership.

Run:

```sh
cd /root/orangepi-zero3w-linux-mainline/orangepi-zero3w-linux-mainline
git pull --ff-only origin work/linux-6.18-full-integration
python3 scripts/test-a733-iommu-v20-stage10-model.py
```

These tests do not simulate concurrent execution or call Linux IOMMU core, and passing them is **not** evidence of a correctly synchronized implementation. They are an acceptance-specification starting point.

## Unresolved

- Does the IOMMU core allocate more than one independent paging domain during the intended DE0 initialization, and how do multiple groups share the controller?
- Implementing one table or separate tables without violating Linux's per-domain ownership contract.
- Controller mutex and lock ordering, probe/readiness, hardware init rollback, interrupts, suspend, reset and device detach.
- DMA API use and physical/bus addresses, page-table alignment, clearing bounds, map rollback and TLB/PTW consistency.
- Exact DTB canonical diff and full kernel link with experimental changes.

**No kernel source, DTB, firmware, boot image or MMIO access performed by these tools.**
