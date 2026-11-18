# A733 v20 IOMMU Stage 15: staged controller teardown

**Status: offline source-only draft. Not tested on target, not runtime safe. Activation BLOCKED.**

## Evidence

The staged `sunxi_iommu_remove()` frees the page-table cache, per-device IRQs, and MMIO mapping **before** `iommu_device_unregister()`. Linux v6.18's `iommu_device_unregister()` traverses device buses to release each associated client; the final client's `iommu_deinit_device()` frees the group's default domain through `iommu_domain_free()`. The vendor domain free callback accesses the page-table cache, IOMMU controller and TLB-flush path. Freeing infrastructure first therefore creates a use-after-free risk even after group references are fixed.

## Isolated draft

`scripts/draft-a733-iommu-v20-stage15-teardown.py` requires the generated Stage14 draft `iommu-v20-stage14-group-refs-draft.c`. It rewrites **only the remove function body**, preserving the PM callbacks and rest of the driver. It generates a new `.c` and unified diff in `artifacts`, and refuses to overwrite outputs.

New removal sequence: `iommu_device_unregister` (all clients released) -> clear and put retained global group -> free page-table cache -> release reserved regions -> free IRQs -> remove sysfs -> iounmap -> clear global controller. Note that even this sequence needs further validation of IRQ vs sysfs teardown and devm resource ownership before using the code.

`scripts/test-a733-iommu-v20-stage15-teardown.py` performs seven textual ordering/guard checks on the generated draft. The seventh deliberately checks that probe cleanup faults remain, to prevent a false readiness conclusion. No compilation is claimed.

## Critical outstanding probe failures

The original probe has unhandled error unwinds:
- `devm_ioremap_resource()` is checked against NULL instead of `IS_ERR()`; a returned error pointer can later reach hardware routines.
- Several reset/clock acquisition failures jump without initializing `ret`.
- `clk_prepare_enable()` results are ignored and corresponding enabled clocks are not disabled on subsequent failure.
- Global `global_iommu_dev` is published before all probe stages succeed; failure paths do not clear it.
- `iommu_device_sysfs_add()` is not consistently paired with cleanup if later registration fails.
- The vendor `sunxi_iommu_domain_free()` still dereferences global controller and performs TLB flush; domain ownership and DMA are unresolved.

These require an independent fail-closed probe redesign before any runtime patch can be approved. The Stage 15 source draft **does not** implement them.

## Local operator commands

```sh
cd /root/orangepi-zero3w-linux-mainline/orangepi-zero3w-linux-mainline
git pull --ff-only origin work/linux-6.18-full-integration
python3 scripts/draft-a733-iommu-v20-stage15-teardown.py
python3 scripts/test-a733-iommu-v20-stage15-teardown.py
D=/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts
cp "$D/iommu-v20-stage15-teardown-draft.patch" /home/
```

**No changes to the audited source kernel, Stage4 production kernel, DTB, images or firmware. Do not boot the generated driver.**
