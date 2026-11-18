# A733 IOMMU v20: isolated source-only compile checkpoint

**2026-11-18. Status:** stage script committed; host compile not run or validated. No kernel images, boot firmware, DTB, baseline or existing kernel source altered by script's design.

## GitHub cross-comparison

- The exact vendor 6.6.98 BSP at `/root/opi3w-vendor-6698-work/kernel/bsp/drivers/iommu` was audited using the operator's `iommu-v20-domain-review.txt`. It has `sunxi_iommu_domain_alloc(unsigned type)` returning a shared `global_iommu_domain`, legacy `sunxi_iommu_map/unmap` signature and `void` `iotlb_sync_map`.
- The [public Allwinner BSP snapshot](https://github.com/alexcaoys/allwinner-bsp/blob/656a550c826787e7e72fae58ca793df9e0988ac8/drivers/iommu/sunxi-iommu-v2.c) already includes new `.domain_alloc_paging`, `.map_pages` and `.unmap_pages` callbacks. It is a useful **candidate reference implementation** but is **not** byte-identical to the operator's proven vendor kernel, and its register/table layout and lifecycle changes require individual review before adoption.
- The [upstream H6/H616 sun50i IOMMU](https://github.com/torvalds/linux/blob/308e4087bbda07814fe06e5ee9450ace0d89e15c/drivers/iommu/sun50i-iommu.c) demonstrates 6.18-style IOMMU ops, safe per-domain allocation and TLB APIs, but is **not a direct substitute** for A733 `allwinner,iommu-v20`.
- Prior cross-check classifications remain: `NEEDS_PORT` for v20 domain, mapping and TLB callbacks; `ALREADY_PRESENT` for the three-argument `iommu_device_register`; `UNVERIFIED` for shared-domain safety, compiled vendor Kconfig, stream wiring and actual DMA.

## Stage 1 procedure

Run:

```sh
cd /root/orangepi-zero3w-linux-mainline/orangepi-zero3w-linux-mainline
git pull --ff-only origin work/linux-6.18-full-integration
python3 scripts/stage-a733-iommu-v20-compile.py
```

The script copies the **exact** local staged 6.18 kernel with `cp -a --reflink=auto` into a unique output directory, stages five local vendor IOMMU implementation files under `drivers/iommu/aw-v20`, and invokes a **compile-only** directory make target. It intentionally does **not** register a Kconfig symbol, modify the real tree's Makefile, create a DTB, enable IOMMU on hardware, or output a bootable image. Source manifest and complete build output are saved as:

- `/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/iommu-v20-port-stage1/manifest.txt`
- `/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/iommu-v20-port-stage1/build.log`

Only the staged copy is modified. The mainline IOMMU `dma-iommu.h` include, vendor-specific includes and different callback signatures will probably produce compiler errors; that is **diagnostic evidence**, not a failure of the protected baseline.

To share manageable diagnostics without flooding the terminal:

```sh
D=/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/iommu-v20-port-stage1
{
  cat "$D/manifest.txt"
  echo "=== first 100 errors and warnings ==="
  grep -nE 'fatal error:|error:|warning:|No rule to make target|Stop\.' "$D/build.log" | head -100
  echo "=== build log tail ==="
  tail -80 "$D/build.log"
} > "$D/diagnostics.txt"
wc -l "$D/diagnostics.txt"
```

Upload `diagnostics.txt` for source/API remediation. Do not attempt to boot any output from this compile checkpoint.

## Before stage 2

1. Inspect the public BSP's newer v20 callbacks against **the exact operator's vendor code** and Linux 6.18 API. Avoid transplanting API names without checking semantics.
2. Fix errors in the isolated copy only, then recompile and record a reproducible source patch plus build log.
3. Address global-domain ownership and hardware-init failure propagation before allowing any device to attach. A compile PASS is insufficient.
4. Validate provider DT clocks/resets, IRQs, per-master streams and page-table physical addresses.
5. Preserve existing HDMI-at-boot diagnostics and known-good PCK600 control baseline. No firmware flashing or mainline image promotion.
