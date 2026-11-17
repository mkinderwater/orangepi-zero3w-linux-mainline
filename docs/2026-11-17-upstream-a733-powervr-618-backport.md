# Upstream-only A733 PowerVR bring-up on Linux 6.18.19

**Decision (2026-11-17):** Do not use the Allwinner legacy `AW_PCK600_DOMAINS` or `AW_GPU_PM_DOMAINS` driver as the GPU target. Backport A733 support to the **upstream** `drivers/pmdomain/sunxi/sun55i-pck600.c`, then use `CONFIG_DRM_POWERVR` against a vetted upstream-compatible A733 DTB and OPP table.

**Status:** Source backport patches and config fragment staged in GitHub only. Mechanical patch-hunk verification against the official `torvalds/linux` **v6.18** source passed all 7 hunks. Neither patches nor new GPU DTB have been built or hardware-tested against the operator's **6.18.19** source. Current 0.2.7 PID1 image unchanged.

## Evidence and upstream basis

- Upstream A733 PCK600 patch series from Yuanshen Cao, March 2026: [PCK600 v2 driver support](https://lkml.iu.edu/hypermail/linux/kernel/2603.0/07901.html). A733 differs from A523 in register delay values and **does not require a reset**. It uses 11 domains, GPU_TOP=5, GPU_CORE=6.
- Follow-on GPU_CORE stability fix, May 2026: [GPU_CORE always-on domain proposal](https://patchwork.armbian.eu/project/patchwork/patch/20260510-pck600-a733-gpu-v1-1-d6393646d714%40gmail.com/). During A733 PowerVR GPU testing, GPU_CORE had to be tagged `GENPD_FLAG_ALWAYS_ON`. The upstream mainline driver now contains this guard. We include it in our backport rather than ignore it.
- Linux 7.1 and later drivers list the A733 compatible, while the pinned Linux 6.18 driver only handles A523. Preserve this feature as a tiny, reviewable backport rather than importing the BSP PM domain system.
- A733 donor GPU DTS in `bsp/configs/linux-6.18/sun60iw2p1.dtsi`: `img,img-bxm-4-64`, `img,img-rogue`, GIC SPI 63, three clocks named core/mem/sys, reset GPU0, and **two** power domains `<&pck600 PD_GPU_CORE>`, `<&pck600 PD_GPU_TOP>`.
- Hybrid board DTS has *different* incompatible legacy GPU and nested power-domain definitions; DO NOT independently enable the upstream driver against the unchanged hybrid DTB.
- GPU OPPs declared by hybrid: 400/600/800/1008 MHz. 800 MHz default 840000 µV, 1008 MHz default 960000 µV. 400/600 MHz default voltage must be **read as raw big-endian cells**, not inferred from `dtc` string-looking text. The legacy vendor OPP compatible `allwinner, img-operating-points` is **not** the standard `operating-points-v2` table compatible. Do not claim upstream OPP operation until translated and validated.
- The hybrid GPU regulator points to AXP8191 DCDC4, and hybrid DCDC4 range is 500000..1540000 µV; vendor DTB fixed at 960000 µV. Keep voltage changes out of this patch.

## Files staged

```text
patches/linux-6.18/0002-pmdomain-sunxi-a733-upstream-pck600.patch
patches/linux-6.18/0003-dt-bindings-a733-pck600-ids.patch
configs/a733-upstream-gpu-experimental.fragment
scripts/audit-a733-upstream-gpu.sh
```

Patch 0002 updates the upstream A523 driver with:
- optional reset on A733, required reset retained for A523;
- A733-specific timing values and domain names;
- the exact A733 compatible `allwinner,sun60i-a733-pck-600`;
- `GPU_CORE` flagged `GENPD_FLAG_ALWAYS_ON`.

Patch 0003 adds A733 domain indices to `include/dt-bindings/power/allwinner,sun60i-a733-pck-600.h`.

## Operator preflight, without modification

```bash
cd /root/orangepi-zero3w-linux-mainline
git pull --ff-only

bash scripts/audit-a733-upstream-gpu.sh /root/opi3w-hybrid-build-0.2.7
```

This runs `git apply --check` against the actual hybrid Linux source, reads the effective GPU config and prints 400/600/800/1008 MHz OPP raw 32-bit voltage values. It never changes kernel sources, the device tree, the boot media or regulators.

## Apply only to a separate experimental Linux source checkout

**Only after preflight passes.** The following is a source-only example, not a bootable GPU build. Do not run against the verified `/root/opi3w-hybrid-build-0.2.7/linux` directory or mutate its source.

```bash
# Point this to an existing separate, disposable copy of the 6.18.19 hybrid Linux source.
GPU_TREE=/root/opi3w-gpu-upstream-experimental/linux
REPO=/root/orangepi-zero3w-linux-mainline
test -d "$GPU_TREE/drivers/pmdomain/sunxi" || exit 1

git -C "$GPU_TREE" apply --check "$REPO/patches/linux-6.18/0002-pmdomain-sunxi-a733-upstream-pck600.patch" || exit 1
git -C "$GPU_TREE" apply --check "$REPO/patches/linux-6.18/0003-dt-bindings-a733-pck600-ids.patch" || exit 1

git -C "$GPU_TREE" apply "$REPO/patches/linux-6.18/0002-pmdomain-sunxi-a733-upstream-pck600.patch"
git -C "$GPU_TREE" apply "$REPO/patches/linux-6.18/0003-dt-bindings-a733-pck600-ids.patch"
```

The experimental config fragment is **not** included in a production kernel. Validate its symbols and dependencies in the effective `.config` after merging and `olddefconfig`.

## GPU DTS integration blockers, not hidden

Before using the experimental config and firmware, construct a distinct, reviewable Zero 3W upstream GPU DTS from the pinned donor with all of these requirements:

1. Use **one** `power-controller@7060000` with `compatible = "allwinner,sun60i-a733-pck-600"`, `reg=<0x0 0x07060000 0x0 0xb000>`, `<&r_ccu CLK_R_PPU>`, `#power-domain-cells=<1>`. The old nested `pck/pd` provider must not bind/own the same registers. Validate all existing domain consumers before removing it.
2. Use A733 domain header `PD_GPU_CORE=6` and `PD_GPU_TOP=5`, and the donor upstream GPU three clocks (core/mem/sys), SPI 63, reset and appropriate power-domain names. No legacy `img,gpu` fallback in this isolated GPU variant. Do not copy the reference while silently discarding the DCDC4 `gpu-supply` connection.
3. Rebuild the GPU OPP table to the **standard binding** and verify every frequency's raw 32-bit voltage including silicon VF bins; reject any implausible voltage. Do not turn default 400/600 MHz data into guessed values.
4. Confirm exact BXM-4-64 BVNC/revision and PowerVR firmware compatibility. A matching `img,img-rogue` does not prove the firmware will boot. Ensure all required files and redistributable rights are handled.
5. Compare compiled experimental DTB against the baseline binary, specifically registers, supplies, clocks, resets, GPU power domain, HDMI, MMC and the root compatibles. Ensure no unexpected pinctrl or PMIC voltage changes.
6. Test GPU only **after** the independent MMC CAP2 bit collision and PF voltage-switching panic are resolved. Keep the known-good PID1 image and existing U-Boot firmware untouched.

### Acceptance gates

- `git apply --check` passes for both patches on actual 6.18.19 source.
- Separate kernel build and module/DTB validation pass, and a diff verifies only intended GPU/PM changes.
- DTB binding checks pass and no duplicate PCK600 register owner remains.
- GPU driver probes with compatible firmware, 400/600/800/1008 MHz OPPs and DCDC4 voltage table validated, without forcing clocks or voltages.
- GPU render, suspend/resume, power and temperature are measured on physical Zero 3W without compromising SD/MMC boot.

**Bottom line:** upstream-first is feasible with a small 6.18 backport. The driver backport is staged. An actual GPU-enabled image is blocked on *safe DTB + OPP + firmware* integration and independently stable MMC/PF.
