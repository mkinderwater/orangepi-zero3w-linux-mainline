# Stage 24: A733 v20 page-directory allocation registry

**Status:** isolated C draft only. Build and runtime verification pending; hardware activation BLOCKED.

## Stage23 defect addressed

The Stage23 count tracked how many page directories were allocated but did **not** know which pointer belonged to an allocation. With two directories live, freeing one twice could free the same address twice while decrementing the other's count. The cache might then be destroyed with another directory still alive.

Stage24 replaces the count with a registry containing each allocated page-directory pointer. The registry and cache creation/destruction share a mutex. The generator reads the Stage23 generated page-table draft and writes a new C source and diff without touching the staged kernel.

### C design

- Preallocate a `struct sunxi_pgtable_directory` record before acquiring the lock.
- On successful directory allocation, initialize it, publish its pointer and list node under the lock, and transfer record ownership to the registry.
- A directory is freed only if its **exact pointer** is found in the registry; remove it before freeing its pages. Unknown or repeat frees are rejected, even if other directories remain.
- Cache teardown checks that the registry is empty, not merely that a count is zero or that the last-published directory pointer is NULL.
- Internal cache pointer is still cleared before `kmem_cache_destroy()`, retaining Stage20's stale-pointer correction.
- The original DMA-device setter and other page-table functions remain unchanged.

### Known limitations

This pointer registry does not prove that a caller is authorized to free a domain's page directory, and it cannot resolve an **address-reuse/ABA** case if a freed page address is allocated again and a stale caller later uses that same address. A per-domain lifetime handle or generation-bound identity may be needed. Holding the registry mutex during allocation/release does not protect `sunxi_pgtable_prepare_l1_tables()`, `prepare_l2_tables()`, unmap, or other PTE users, nor does it make DMA synchronization valid. Existing domain aliases, attachment without TTB selection, and hardware translation enablement remain blocking.

The C draft uses explicit `linux/list.h` and `linux/mutex.h` includes. It requires isolated AArch64 compilation and review of kernel-relevant concurrency before any integration.

## Commits

- `scripts/draft-a733-iommu-v20-stage24-registry.py`: Stage24 standalone C and patch generator
- `scripts/test-a733-iommu-v20-stage24-registry.py`: sixteen structural/offline identity checks

## Debian instructions

```sh
cd /root/orangepi-zero3w-linux-mainline/orangepi-zero3w-linux-mainline
git pull --ff-only origin work/linux-6.18-full-integration
python3 -m py_compile scripts/draft-a733-iommu-v20-stage24-registry.py
python3 scripts/draft-a733-iommu-v20-stage24-registry.py
python3 scripts/test-a733-iommu-v20-stage24-registry.py 2>&1 | tee /home/iommu-v20-stage24-tests.txt
D=/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts
cp "$D/iommu-v20-stage24-registry-draft.patch" /home/
```

**No production kernel, DTB, firmware, or boot image modifications. Do not boot or enable the experimental IOMMU.**
