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

## Failed compiler gate discovered from operator `build.log`

The first stage script's Kbuild call returned **0 without compiling any IOMMU objects**: `Nothing to be done for 'drivers/iommu/aw-v20/'`. Worse, Kbuild's default `ARCH=x86` produced x86 kernel headers, so that report was not an ARM64 compatibility test. It is an **invalid PASS**, not a valid driver build.

Corrected by commit `1adf58d`:
- Requires matching Stage4 ARM64 config and installed `aarch64-linux-gnu-gcc` (or explicit `--cross-compile` prefix).
- Sets `ARCH=arm64` and `CROSS_COMPILE` for every Kbuild call.
- Invokes explicit object targets rather than an unreferenced directory target.
- Requires that **all three** .o files exist and that `readelf -h` reports `AArch64`; only then records a compile PASS.
- Preserves old diagnostic path; use a fresh output directory.

```sh
cd /root/orangepi-zero3w-linux-mainline/orangepi-zero3w-linux-mainline
git pull --ff-only origin work/linux-6.18-full-integration
python3 scripts/stage-a733-iommu-v20-compile.py \
  --out /root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/iommu-v20-port-stage1-arm64
```

Collect a short diagnostic file even if `make` fails, without claiming success:

```sh
D=/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/iommu-v20-port-stage1-arm64
{
  cat "$D/manifest.txt"
  grep -nE 'fatal error:|error:|warning:|No rule to make target|Stop\.' "$D/build.log" | head -100 || true
  tail -60 "$D/build.log"
} > "$D/diagnostics.txt"
```

**Status:** corrected source-only ARM64 diagnostic script committed, awaiting operator execution. No target-board validation.

## Actual ARM64 compile results (operator diagnostics)

The corrected AArch64 build used `aarch64-linux-gnu-gcc`, exact Stage 4 config SHA256 `f98a84b103b7fb897f4bd962ac4f13a8d0b614cd8a3ec206eda80d18b3174be5`, and returned code **2** when compiling the actual vendor `sunxi-iommu-v2.o`. This is a valid initial compile failure, not a pass.

**Important confounding condition:** Stage 4 has `CONFIG_IOMMU_SUPPORT=n`. The initial build did not turn it on in the *isolated* tree; consequently Linux exposed stub/incomplete `iommu_ops` and `iommu_domain_ops`, producing misleading "no member" and incomplete-type errors. Commit `395e04a` fixes the diagnostic harness to enable `IOMMU_SUPPORT=y` and `IOMMU_DMA=y` **only within its copied worktree**, then assert both survive `olddefconfig`. Its output manifest records the modified diagnostic configuration SHA. The original validated config remains untouched.

Other visible compiler blockers may remain once the real IOMMU API is enabled:
- `IOMMU_VA_BITS`, `IOMMU_PT_MASK`, `SPAGE_SIZE`, `SPD_SIZE` and `SPAGE_ALIGN` unresolved. Investigate their definitions/config guards in exact vendor files, not generic guesses.
- `iommu_iotlb_gather.start/end` not available in the active configuration/target struct; use target-appropriate range operations only after examining the real header.
- `dev_iommu_priv_get/set` undeclared in active build, possibly from wrong configuration/header path; recheck after enabling core.
- `iommu_alloc_resv_region` undeclared; reconcile with 6.18 reserved-region semantics.
- `platform_driver.remove` expects `void (*)(struct platform_device *)` but vendor callback returns `int`.
- Earlier reviewed domain-ownership, error propagation and callback-type mismatches still require porting.

Use a **fresh directory**:

```sh
cd /root/orangepi-zero3w-linux-mainline/orangepi-zero3w-linux-mainline
git pull --ff-only origin work/linux-6.18-full-integration
python3 scripts/stage-a733-iommu-v20-compile.py \
  --out /root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/iommu-v20-port-stage1-iommu-enabled
```

This stage remains source-only and does not create any bootable image or enable the display DMA consumer. **Do not interpret disappearance of stub-type errors as a driver port PASS.**

## Exact vendor page-table geometry, verified from 6.6.98 source

Operator report `iommu-v20-port-blockers.txt`, SHA256 `93ff578b4632306c9403f1edd9c5e1841558d465ecc112caf07346d47373eba3` for `sunxi-iommu-pgtable.h`, establishes:

- `IS_ENABLED(CONFIG_AW_IOMMU_V2)` or `CONFIG_AW_IOMMU_V3` selects `AW_IOMMU_PGTABLE_V2`; without either symbol the header defines **none** of the page-table geometry macros. The previous isolated script had no vendor `AW_IOMMU_V2` Kconfig definition, so those errors were *missing test selection*, not evidence the constants had disappeared.
- V2: `IOMMU_VA_BITS=34`, `IOMMU_PD_SHIFT=22` (4 MiB regions), `IOMMU_PT_SHIFT=12` (4 KiB pages). `IOMMU_PT_MASK`, `SPAGE_SIZE`, `SPD_SIZE`, `SPAGE_ALIGN` follow those exact vendor definitions.
- V1, **not applicable to the A733 v20 driver**, has `IOMMU_VA_BITS=32`, `IOMMU_PD_SHIFT=20`. Do not substitute V1 definitions.
- Exact source defines `sunxi_iommu_domain_alloc(unsigned type)` and legacy `.map/.unmap` plus an `iotlb_sync_map` returning void. Those remain real Linux 6.18 ABI porting items.
- In the correct Linux 6.18 `CONFIG_IOMMU_API` path, `iommu_iotlb_gather` has `start/end`, `dev_iommu_priv_get/set` exist, and `iommu_alloc_resv_region` **requires GFP flags**. The previous unconfigured compile's stub-struct errors have been eliminated.

**Cross-check:** the publicly published [Allwinner BSP v2 header](https://github.com/alexcaoys/allwinner-bsp/blob/656a550c826787e7e72fae58ca793df9e0988ac8/drivers/iommu/sunxi-iommu-pgtable.h) also specifies 34/22/12-bit geometry. Independent source agreement supports the chosen v2 compile configuration, but no hardware DMA test is implied.

**Script fix:** commit `8f7d864` adds `ccflags-y += -DCONFIG_AW_IOMMU_V2=1` **only to the staged directory Makefile**, without defining nonexistent global Kconfig symbols or changing the preserved Stage 4 config. This is a *source compiler test selector*, not a runtime or DTB configuration. It is important for the next run to retain a new output directory and inspect the explicit `sunxi-iommu-v2.o` invocation for the `-DCONFIG_AW_IOMMU_V2=1` flag.

```sh
cd /root/orangepi-zero3w-linux-mainline/orangepi-zero3w-linux-mainline
git pull --ff-only origin work/linux-6.18-full-integration
python3 scripts/stage-a733-iommu-v20-compile.py \
  --out /root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/iommu-v20-port-stage1-v2layout
```

**No kernel image or DTB output.** The remaining API changes should only be made after the new compile log verifies geometry symbols are resolved.

## Correcting another false configuration assumption

The operator's `iommu-v20-port-stage1-v2layout` diagnostic still reports missing `IOMMU_VA_BITS`, `SPAGE_SIZE`, `SPD_SIZE`, `IOMMU_PT_MASK` despite the staged Makefile's `ccflags-y`. This indicates the *exact object target* is bypassing or not inheriting that subdirectory flag. The v2 geometry remains verified in the unchanged vendor header; **its use in the actual compiler was not verified**.

Commit `326155a` removes reliance on the `ccflags-y` setting and invokes each exact ARM64 object target with `KCFLAGS=-DCONFIG_AW_IOMMU_V2=1` and `V=1`. It scans the build log for an actual AArch64 compiler command with the define, refusing PASS if evidence is absent. This flag is confined to the isolated diagnostic build, not a source or boot-image patch. The following API errors are real but must be revisited only after this geometry-selector check passes: legacy map/unmap, `domain_alloc`, `pgsize_bitmap` location, `iotlb_sync_map` signature, `of_xlate const` and platform remove callback.

```sh
cd /root/orangepi-zero3w-linux-mainline/orangepi-zero3w-linux-mainline
git pull --ff-only origin work/linux-6.18-full-integration
python3 scripts/stage-a733-iommu-v20-compile.py \
  --out /root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/iommu-v20-port-stage1-kcflags
```

Upload a concise diagnostic with manifest, the first compiler errors, and the first command line containing `-DCONFIG_AW_IOMMU_V2=1`. **No boot/image actions.**

## Verified v2 selector success and stage-2 interface prototype

The user's `build(1).log` confirms the **actual** `aarch64-linux-gnu-gcc -c drivers/iommu/aw-v20/sunxi-iommu-v2.c` command contains `-DCONFIG_AW_IOMMU_V2=1`. All missing `IOMMU_VA_BITS`, `IOMMU_PT_MASK`, `SPAGE_SIZE`, `SPD_SIZE`, `SPAGE_ALIGN` failures disappear. This closes the vendor page-table config selection issue. The object still fails to compile due to **real** API mismatches: `.map`, `.unmap`, `iotlb_sync_map` return type, `pgsize_bitmap` moved to `iommu_domain`, legacy `.domain_alloc`, `of_xlate` const args and `platform_driver.remove` return type.

The upstream GitHub [Allwinner v20 source](https://github.com/alexcaoys/allwinner-bsp/blob/656a550c826787e7e72fae58ca793df9e0988ac8/drivers/iommu/sunxi-iommu-v2.c) has modern `domain_alloc_paging`, `map_pages/unmap_pages`, `iotlb_sync_map` int and void platform remove callbacks. **Do not cherry-pick it wholesale**: the reference is not the exact operator vendor tree and its global domain lifetime and DMA semantics have not been validated.

Commit `8563262` introduces `scripts/apply-a733-iommu-v20-api-stage2.py`, a **fail-closed, exact SHA256 checked, compile-only source transformer**. It writes a separate new source and unified diff, never overwriting the vendor copy. It changes interface signatures and page-size metadata only; deliberately **does not claim safe runtime behavior**. Unresolved are shared-domain ownership, hardware-init failures, default domain, mapping failure atomicity, TLB synchronization and full device-tree/stream validation. It also deliberately leaves the platform remove implementation unchanged pending full lifecycle inspection, so compilation may continue to fail.

To generate (without compiling) a source patch from the last staged tree:

```sh
cd /root/orangepi-zero3w-linux-mainline/orangepi-zero3w-linux-mainline
git pull --ff-only origin work/linux-6.18-full-integration
python3 scripts/apply-a733-iommu-v20-api-stage2.py \
 --source /root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/iommu-v20-port-stage1-kcflags/linux/drivers/iommu/aw-v20/sunxi-iommu-v2.c \
 --out /root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/iommu-v20-api-stage2.c
```

If an anchor differs the script **stops without generating output**. Review the emitted .patch rather than applying changes blindly; compile work requires a subsequent explicit copy into a disposable staged tree. No firmware or boot image is part of this step.

## Stage 2 actual compile and final callback signature

User's `iommu-v20-stage2-results.txt` shows compilation reached line 2246. The *only fatal diagnostic* was the Linux 6.18 `platform_driver.remove` type mismatch: the vendor's `int (*)(struct platform_device *)` does not match required `void (*)(struct platform_device *)`. There were 13 missing-prototype warnings; no other fatal errors in the v2 object. This is a **source-only compile diagnostic**, not a runtime pass.

Compared with pinned public Allwinner BSP `sunxi-iommu-v2.c`, which already declares `static void sunxi_iommu_remove(struct platform_device *)`. The exact vendor source uses an int callback and can require preserving old cleanup code. Added `scripts/apply-a733-iommu-v20-remove-stage3.py` (latest fix `7688147`), a fail-closed separate-output transformer: verifies Stage 2 markers and unique remove function/driver registration, adds a void callback wrapper calling the unmodified vendor cleanup routine, changes only the driver registration, emits a unified diff. It does not modify the kernel, original source, or firmware.

Do not claim compilation until the generated Stage 3 source is actually compiled. Compilation does not establish ownership, teardown, DMA safety or usable display output. Once Stage 3 object is built, explicitly compile remaining `sunxi-iommu-common.o` and `sunxi-iommu-pgtable.o`, inspect undefined cross-object references, then tackle domain/stream semantics.

## Stage 3 compiler gate: main v20 object compiles, companion header blocked

Operator's `iommu-v20-stage3-results.txt` shows that after the Stage 3 `.remove` adapter the **main** `sunxi-iommu-v2.o` has no fatal compiler diagnostics, with 13 missing-prototype warnings. The **next** target, `sunxi-iommu-common.o`, stops at its line 23 angle-bracket include `#include <sunxi-iommu.h>` because Kbuild does not search the staged driver directory for angle-bracket headers by default. The public Allwinner companion file contains both `"sunxi-iommu.h"` and `<sunxi-iommu.h>`, confirming why this target needs an include search path.

Commit `67b86d9` adds the staged absolute include directory to `KCFLAGS` in the compile-only staging harness for future fresh builds. No hardware files, global kernel Kconfig, boot image or driver ABI were changed. For the existing Stage 3 tree, retry **only** companion objects with `KCFLAGS="-DCONFIG_AW_IOMMU_V2=1 -I$K/drivers/iommu/aw-v20"`. Confirm actual `.o` files with `readelf -h` reporting AArch64. The compiler-stage status is **one object built, two unverified**, not a complete kernel/driver build.

After compiling all three object files, unresolved hardware safety issues remain: singleton-domain ownership, page-table DMA coherence and addresses, SG failure propagation, device removal, TLB/IOVA behavior and the IOMMU device-tree master connections.

## Companion compilation: duplicate vendor header include

The operator's `iommu-v20-stage3-companions-results.txt` confirms `sunxi-iommu-v2.o` is an **AArch64 ELF**, while `sunxi-iommu-common.o` stops with a duplicate definition of `struct dump_region` at `sunxi-iommu.h:55`. The source includes the same `sunxi-iommu.h` twice, once via `"sunxi-iommu.h"` and once via `<sunxi-iommu.h>`. The pinned [public Allwinner header](https://github.com/alexcaoys/allwinner-bsp/blob/656a550c826787e7e72fae58ca793df9e0988ac8/drivers/iommu/sunxi-iommu.h) has no include guard either. This failure surfaced after correcting the search path; it is **not** a failure of IOMMU v20 register or page-table logic.

Commit `b25faba` introduces `scripts/fix-a733-iommu-v20-header-guard.py` which SHA256-checks the exact staged vendor header (`1e156fd9cef40a7bebb8b95cb3141a510d60a6367c5ecedebb0e2dda79e1011a`), creates a backup inside the **disposable** staged source, and adds a unique include guard. It refuses reruns on changed source. It leaves vendor and original Linux trees untouched. Compile both companions afterward with explicit AArch64 compiler and vendor include path; a successful compile does not validate linkage or hardware behavior.

## Third object: DMA API include

The operator's `iommu-v20-companions-retry-results.txt` verifies both `sunxi-iommu-v2.o` and `sunxi-iommu-common.o` as AArch64 ELF. `sunxi-iommu-pgtable.o` fails on implicit `dma_sync_single_for_cpu` / `dma_sync_single_for_device` declarations and missing `DMA_TO_DEVICE`. Public pinned Allwinner `sunxi-iommu-pgtable.c` includes `linux/iommu.h` and `linux/slab.h` but not `linux/dma-mapping.h`. This matches the hypothesis of missing direct DMA mapping API header inclusion; it does not prove correct cache synchronization semantics.

Commit `8d09c4f` adds a guarded staged-only script `scripts/fix-a733-iommu-v20-dma-header.py`: verify SHA256 of exact vendor page-table source, preserve local backup, insert `#include <linux/dma-mapping.h>`, leave other code unchanged. Build only `sunxi-iommu-pgtable.o` afterward. Validate with `readelf -h`, do not confuse this compile check with a linked driver, IOMMU correctness or board readiness. Remaining issues include domain singleton lifecycle, DMA sync direction/address correctness, page-table management, TLB range behavior and complete built-in linkage.

## Stage 3 companion compile PASS, Stage 4 relocation gate

The operator-provided `iommu-v20-pgtable-results.txt` confirms all three vendor source objects compiled as AArch64 ELF: `sunxi-iommu-v2.o`, `sunxi-iommu-common.o` and `sunxi-iommu-pgtable.o`. The page-table retry has no recorded warnings or errors. This is a **three-object compile PASS**, not a linker, modpost, runtime or safety PASS.

Commit `d1fe6d7` adds `scripts/check-a733-iommu-v20-linkage.py`. It verifies all ELF architectures and input SHA256, runs `aarch64-linux-gnu-ld -r` to combine the three objects without producing any executable/boot image, and records the combined SHA256 plus `aarch64-linux-gnu-nm -u` output. Undefined external kernel references from the relocation stage are expected and **must not** be treated as proof of absent exports. This is an intermediate check only; full kernel linkage, address/coherence semantics, domain lifetime, and IOMMU/device-tree hardware attachment are unvalidated.

```sh
cd /root/orangepi-zero3w-linux-mainline/orangepi-zero3w-linux-mainline
git pull --ff-only origin work/linux-6.18-full-integration
python3 scripts/check-a733-iommu-v20-linkage.py
```

Report files:
- `/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/iommu-v20-linkage-stage4/results.txt`
- `/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/iommu-v20-linkage-stage4/undefined-symbols.txt`

Do not promote the relocatable object to the boot image. Verify whether the vendor `subsys_initcall` registration and driver dependency unresolved references correspond to configuration or missing source, rather than assuming linking three objects is a complete integration.
