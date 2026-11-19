# Stage 19 correction: generated patch removed PM and DT definitions

The operator supplied a 238-line Stage19 patch. Direct patch review revealed that the generator replaced the source from `sunxi_iommu_remove()` up to the later `sunxi_iommu_remove_618()` adapter, deleting several unrelated C definitions:
- `sunxi_iommu_suspend()`
- `sunxi_iommu_resume()`
- `sunxi_iommu_pm_ops`
- `sunxi_iommu_dt_ids[]`

This is **critical**: the original Stage19 patch must not be compiled or applied. The Stage19 generator was corrected to identify the remove function's first column-zero closing brace and preserve everything following it, including PM and DT declarations. Mandatory marker guards now fail closed if any are absent. Tests include preservation checks for the PM operations and device-tree table.

## Other issues still open

The patch also cannot prove that domain users have quiesced before `sunxi_pgtable_set_dma_dev(NULL)` or cache destruction. The reset-count reconstruction is not a reliable resource acquisition counter; IRQ/clock/resource teardown needs real compile checks and failure injection. `global_iommu_domain` lifetime, `attach_dev` correctness, page-table DMA synchronization, and MMIO initialization rollback remain unresolved. Stage19 is not a boot candidate.

## Regenerate to new filenames

```sh
cd /root/orangepi-zero3w-linux-mainline/orangepi-zero3w-linux-mainline
git pull --ff-only origin work/linux-6.18-full-integration
python3 -m py_compile scripts/draft-a733-iommu-v20-stage19-lifecycle.py
D=/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts
python3 scripts/draft-a733-iommu-v20-stage19-lifecycle.py \
  --out "$D/iommu-v20-stage19-lifecycle-draft-v2.c" \
  --patch "$D/iommu-v20-stage19-lifecycle-draft-v2.patch"
python3 scripts/test-a733-iommu-v20-stage19-lifecycle.py \
  --source "$D/iommu-v20-stage19-lifecycle-draft-v2.c"
cp "$D/iommu-v20-stage19-lifecycle-draft-v2.patch" /home/
```

Upload the resulting v2 patch and tests. The corrected source has not been AArch64 compiled or runtime-tested. No changes to production kernel, DTB, firmware, or boot images.
