# Stage 19: A733 IOMMU v20 consolidated lifecycle C draft

**State:** Generated-source experiment only. Not built or boot-tested. IOMMU activation prohibited.

## Basis

Stage 18 operator evidence: twelve offline model scenarios passed (12/12). This verifies only expected resource transitions. Stage 17 verified actual Linux 6.18 registration behavior and A733 vendor source.

`scripts/draft-a733-iommu-v20-stage19-lifecycle.py` transforms the Stage 16 generated C draft to a new standalone Stage 19 C draft and unified patch. The input is not changed. It fails closed when expected signatures or intermediate edits are absent, and refuses to overwrite existing output.

Changes in the proposed C draft:

1. Replace the void sysfs helper with an int-returning helper. Check three device_create_file() results and remove already-created entries on failure.
2. Propagate sysfs errors in probe. Only invoke full vendor sysfs removal if creation completely succeeded.
3. Track whether `iommu_device_register()` was attempted. On a returned error, Linux 6.18 already executed provider unregister; the draft releases its **controller-held** global IOMMU group reference and must not call unregister again.
4. On error, clear both `dma_dev` and the page-table DMA pointer using `sunxi_pgtable_set_dma_dev(NULL)`, after core registration failure unwinding.
5. On successful remove, unregister client devices first, release global group owner reference, clear DMA pointers, disable IRQ handlers before freeing page-table cache, remove sysfs, disable clocks in reverse order, reassert resets, free the clock array and platform data.
6. Preserve devres-managed MMIO release and Stage 14 one-reference-per-device group design.

`scripts/test-a733-iommu-v20-stage19-lifecycle.py` checks twelve structural properties. This is not a C compiler, fault-injection kernel, or runtime test.

## Remaining critical defects and limitations

**Do not enable hardware based on this draft.**

- No synchronization or proof that externally allocated domains and concurrent DMA mapping operations have ceased before clearing `sunxi_pgtable_params.dma_dev` or destroying the page-table cache.
- `sunxi_pgtable_params.iopte_cache` is assigned by its allocator but is not cleared by the existing cache-free helper. The generated draft still inherits this stale cache pointer.
- Domain allocation returns `global_iommu_domain` across independent requests and `attach_dev` reports success without binding. Free leaves a stale global and can destroy active page tables.
- The successful-remove reset count is reconstructed from the device tree; any mismatch with actual completed deassertions requires correction by storing explicit per-controller acquisition counters.
- The debugfs creation helper's internal failure handling, vendor sysfs interactions and master distribution ownership need audit.
- Pre-registration failures inside `sunxi_iommu_probe_distribute_masters()`, caches, hardware global state, and provider-registration concurrency are not comprehensively resolved.
- Page-table DMA synchronization uses unsafe physical-address handles and mismatched extents; IOMMU mapping rollback, TLB/PTW ordering and hardware enable/disable remain unverified.
- Stage 19 has not yet been checked for C compilation, compiler warnings, or failure-injection behavior.

## Operator commands (no modifications to working kernel)

```sh
cd /root/orangepi-zero3w-linux-mainline/orangepi-zero3w-linux-mainline
git pull --ff-only origin work/linux-6.18-full-integration
python3 scripts/draft-a733-iommu-v20-stage19-lifecycle.py
python3 scripts/test-a733-iommu-v20-stage19-lifecycle.py 2>&1 | tee /home/iommu-v20-stage19-tests.txt
D=/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts
cp "$D/iommu-v20-stage19-lifecycle-draft.patch" /home/
```

Stop on any source-layout failure or test failure and report the exact traceback and patch. Do not disable guards merely to get PASS. Do not overwrite known-good kernel/DTB/firmware/image. Do not boot.
