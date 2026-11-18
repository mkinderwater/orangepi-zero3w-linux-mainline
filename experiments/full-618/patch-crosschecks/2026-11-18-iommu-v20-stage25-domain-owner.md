# A733 IOMMU v20 Stage 25: C domain ownership and operation-fencing contract

**Status:** C reference implementation compiled/tested only when operator executes local command. No kernel driver patch. Hardware activation BLOCKED.

## Verified prior work

- Stage24 Python ownership tests: 16/16 PASS, source patch reviewed.
- Stage24 page-directory registry matches page-table addresses but cannot recognize an address reused after a prior free (ABA), cannot validate domain ownership, and cannot fence a map operation already running while a directory is freed.
- The staged driver `sunxi_iommu_attach_dev()` returns success without selecting a hardware TTB and `global_iommu_domain` aliases repeated allocation requests.

## Stage25 C reference

`scripts/stage25-domain-ownership-model.c`, commit `7ac1fe7`, is a **standalone portable C** state machine with pthread synchronization that exercises these invariants:

1. Each allocation has a unique monotonically increasing **generation** and directory pointer.
2. A stale token for a reused address is rejected by comparing both pointer and generation.
3. Every map operation must acquire an operation reference before touching a directory and release it when finished.
4. Directory release is rejected while a map operation is outstanding or the domain is installed.
5. One active TTB owner is modelled across all clients. Switching owners does not model real TTB writes, DMA quiesce or rollback.
6. Cache destruction requires no live domains, no clients, and hence no outstanding map references.

Compile and run:

```sh
cd /root/orangepi-zero3w-linux-mainline/orangepi-zero3w-linux-mainline
git pull --ff-only origin work/linux-6.18-full-integration
gcc -std=c11 -Wall -Wextra -Werror -pedantic -pthread -O2 \
    scripts/stage25-domain-ownership-model.c \
    -o /tmp/stage25-domain-model
/tmp/stage25-domain-model | tee /home/iommu-v20-stage25-c-model.txt
```

## Kernel integration requirements

Do **not** copy the pthread model into a kernel driver. The next implementation must use kernel spinlocks/RCU/refcounts and appropriate sleepable synchronization, preserving map/unmap call context. Registry identity must be bound to the owning `struct sunxi_iommu_domain`, not a raw pointer caller can reuse. Domain free is a `void` IOMMU callback and cannot merely return an error while leaking resources under normal Linux core release. A safe release-domain or detach/identity path must ensure hardware stops using the table before free, and all map/unmap callers are fenced.

The current page-table synchronization calls pass `virt_to_phys` as DMA handles; no allocation-registration fix addresses this. The driver also permits hardware enable during domain allocation, so a compiler PASS cannot be interpreted as activation permission.

## Next integration

After the Stage25 C test succeeds on the Debian host, construct an isolated Linux 6.18 patch binding the page directory owner to its domain and protecting map/unmap entry and domain teardown. Make the first attachment and failure rollback explicit. Compile the affected driver and pgtable objects in a disposable kernel tree and audit before touching DTB/boot images.

**No Stage4 kernel, DTB, firmware, boot image or hardware changes.**
