# Re-audit of successful A733 Linux 6.18 sources versus our Zero 3W 0.2.7

**Date:** 2026-11-16  
**Status:** GitHub source/document audit; local HBI compilation differences not yet fully reconciled. No new 6.18 hardware PASS. The first-boot LED phenomenon remains deliberately deferred.

## Executive determination

There are **not two independently demonstrated 6.18 boots on our exact Zero 3W board** in the inspected sources.

1. **[nickyg666/orangepi-zero3w-mainline](https://github.com/nickyg666/orangepi-zero3w-mainline)** reports and documents a *Zero 3W* 6.18.19+ hybrid boot to Ubuntu 26.04, later AIC8800 Wi-Fi and GPU. This is other-project hardware evidence, not ours. See `AGENTS.md` §§3.1–3.7, 4–5 and `README.md` dated Aug 13–16.
2. **[jonas5/Allwinner-A733-kernel](https://github.com/jonas5/Allwinner-A733-kernel)** demonstrates 6.18.y on **Orange Pi 4 Pro**, Radxa Cubie A7A/A7S; its `boards.md` lists Zero 3W as **Platform Ready**, not **Fully Validated**. Its current `README.md` says Zero 3W awaits hardware. Do not count it as a second verified Zero 3W boot.

**Our completed controls:** A2V and VBI boot vendor 6.6.98; F1 boots vendor kernel + hybrid 0.2.7 DTB via SSH while HDMI stays at splash; the *same static PID1 and LED diagnostic* runs on vendor 6.6.98 and physically blinks PL7. Hybrid 6.18 images HBI/K2/F2/PID1-LED still have **no identified 6.18 kernel-entry evidence**. Every experiment's splash and LED alone are inconclusive.

## 1. Critical: we have not reproduced nickyg666's actual successful kernel binary

| Feature | Other project's documented successful build | Our 0.2.7 HBI |
| --- | --- | --- |
| Base Linux | 6.18.19+ hybrid | 6.18.19 hybrid |
| Raw ARM64 `Image` | **26,114,056 bytes**, kernel #8 from their Aug 13 test | **8,591,368 bytes**, header image-size 9,043,968 |
| Compiled configuration | Recovered using kernel `scripts/extract-ikconfig`, saved outside repo as `true-arm64.config` | `/root/opi3w-hybrid-build-0.2.7/build/.config`; build-id `e07cb060...` |
| BSP | Selected Allwinner vendor source grafted into `bsp/`, plus kfifo/UART adaptation | Selected vendor source under `bsp/`, top-level Kbuild/Kconfig edited |
| Target board | Actual Zero 3W, different RAM variant as described in AGENTS | Our physically tested 1 GB Zero 3W |

**Interpretation:** A 3× size difference by itself proves **only different kernel builds**, not an invalid kernel. But any statement that we reproduced their working build is false until configs, linked early drivers, source selections and header semantics are matched. Their exact known-good `Image`, working `.config`, deployed `DTB` and original transformation source are **not fully supplied by that repository**. The documents refer to local paths and on-device edits. A text-only comparison cannot fill those gaps.

**Next audit:** on our WSL host extract compiled `CONFIG_ARM64`, `CONFIG_ARM64_4K_PAGES`, `CONFIG_ARCH_SUN50IW10`, `CONFIG_ARCH_SUNXI`, `CONFIG_AW_BSP`, `CONFIG_AW_SUN60IW2_CCU`, `CONFIG_AW_PINCTRL_SUN60IW2`, `CONFIG_AW_PINCTRL_SUN60IW2_R`, `CONFIG_AW_TWI`, `CONFIG_AW_MFD_AXP2101`, `CONFIG_MMC_SUNXI`, `CONFIG_AW_MMC`, `CONFIG_SERIAL_EARLYCON`, `CONFIG_AW_UART_NG`, `CONFIG_BLK_DEV_INITRD`, `CONFIG_RD_GZIP`, `CONFIG_DEVTMPFS`, `CONFIG_DEVTMPFS_MOUNT`, `CONFIG_TMPFS`, `CONFIG_EXT4_FS`, `CONFIG_LEDS_GPIO`; compare the *effective* kernel config, not Kconfig fragments. Treat absent counterpart config as UNKNOWN, not as a mismatch.

## 2. Critical: U-Boot `booti`, initrd format and BL31 relocation

Nickyg666 `reference/boot.cmd` and `AGENTS.md` §3.1 describe vendor U-Boot 2018.07 as a 32-bit implementation with legacy `booti` behaviour. They report a legacy initrd relocation ending near `0x4a000000`; a ~32 MiB payload may overlap the **BL31** monitor at `0x48000000..0x49000000`, silently killing early execution. They use:
- raw ARM64 `Image` at `0x41000000`
- FDT at `0x44000000`
- initrd staged at `0x45000000`
- environment/overlay staging at `0x46000000`
- **`booti ${kernel_addr_r} ${ramdisk_addr_r} ${fdt_addr_r}`** (no explicit `:size` in the published script)
- a **legacy-wrapped tiny `uInitrd`**: `mkimage -A arm -T ramdisk -C gzip` from a ~1.53 MiB gzip archive, as described in `AGENTS.md` §§3.1 and 4.

Our finished HBI uses the same nominal staging addresses but **`booti kernel ramdisk:size fdt`** with a **raw gzip initramfs** of 270,471 bytes (later PID1 probe 291,637 bytes). This form works under our vendor **6.6.98** VBI boot test, including when the PID1 control runs. Thus it is *not universally broken*. It is also **not the exact successful 6.18 handoff variant** and the HBI's **actual** post-`booti` relocated initrd addresses/BL31 integrity were never observed. Do not claim a confirmed collision merely from nominal addresses.

**Controlled A/B to prepare after preflight:** keep our exact kernel/DTB/first stage/vendor env/overlays/root layout, change only initrd wrapping + matching `booti` operand, and inspect its legacy header / relocation logic. Compare against a vendor-kernel control using the same handoff. Two edits required for a coherent alternate encoding are treated as *one interface change*, not falsely independent individual causes. No fallback `bootm`.

## 3. Boot script semantics must be preserved

Our A2V hardware PASS and S1/S2 hardware failures prove that omitting vendor environment import and FDT setup breaks the vendor reference. Our HBI final decoded second stage preserves env import, `fdt addr`, `fdt resize 65536`, root selection and overlays. Repeating S1/S2/A2M tests or removing those commands is counterproductive.

The nickyg script has its own `mainline/armed` gate and a vendor fallback; *their* documented runtime proof is the 6.18 login, not the existence of this fallback. Do not copy a fallback into our tests: it would contaminate the kernel identity.

**Risk:** another U-Boot implementation's arm64 `booti` may parse `addr`, `addr:size`, `uInitrd` and relocations differently. Inspect the **exact retained U-Boot binary** or its matching source, not generic contemporary U-Boot documentation.

## 4. Device-tree and regulator/MMC chain (post-entry risk)

Nickyg666 records a real causal sequence: missing `CONFIG_AW_TWI` prevented AXP8191 regulator registration and deferred the SD host. After enabling AW_TWI, a temporarily removed `vmmc-supply` caused `no support for card's volts`, so they restored `vmmc-supply = <&dc1sw2>` once the regulator bound. Their deployed DTB was patched *on-device*, not simply copied verbatim from an untouched vendor tree.

Our hybrid .config already documented `AW_TWI=y`, `AW_MMC=y`, AXP MFD/I2C/regulator built in, and compiled sunxi-mmc-v5p3x objects. Thus the simplistic claim that AW_TWI is *missing* in our build is unsupported. **Runtime PMIC/rail/MMC initialization is unverified**; after positive kernel entry, check exact match strings, `vmmc-supply`, `vqmmc`, valid `ocr_avail`, driver selected and actual binding. Do not omit a supply or write PMIC rails speculatively.

## 5. Important architecture difference: MMC host driver

Nickyg666's successful implementation documents **`CONFIG_MMC_SUNXI`**, compatible-patched nodes, `reset-names = "ahb"`, and expressly notes `CONFIG_AW_MMC` **not set**. Our 0.2.7 uses `CONFIG_AW_MMC=y` with vendor v5p3x objects. These are **different implementations**, not interchangeable boards or configs.

Jonas5's current nested `patch/0001-allwinner-a733-orangepi-4-pro-6.18-mainline.patch` modifies `drivers/mmc/host/Kconfig` so `MMC_SUNXI` depends on `SUNXI_CCU || AW_CCU`. It also adds a fallback OCR mask when `ocr_avail == 0`. This is a different mitigation from nickyg's final regulator supply approach. Do not apply the OCR fallback to our vendor MMC without proving its relevance; it is not proof of early kernel execution.

## 6. Important architecture difference: power domains

Jonas5's nested patch changes `drivers/pmdomain/sunxi/sun55i-pck600.c` to add `allwinner,sun60i-a733-pck-600` and descriptors with **`has_rst_clk=false`**, while the older A523 descriptor requires reset acquisition. This is an actual kernel-source difference and a plausible boot/peripheral issue if our DTB enables A733 PCK-600 devices that fail to register. Audit our compiled kernel config, exact `compatible`, driver source and object linkage. But do not assume it caused a pre-PID1 failure without logs.

## 7. DTB: Zero 3W, Orange Pi 4 Pro and boot firmware are not interchangeable

Jonas5 `dts/sun60i-a733-orangepi-4-pro.dts` uses board identity `xunlong,orangepi-4-pro`, its own GPIO LED **PB6**, dedicated peripherals and aliases. Our actual Zero 3W LED is **PL7**, physically verified on vendor Linux. Replacing our DTB with 4 Pro DTB, or our Boot0 with their `bootloader/u-boot-mainline` output, would invalidate controls and may break DRAM training.

Their bootloader builder separately clones `dlan17/trusted-firmware-a` branch `A733`, builds BL31, and clones `dlan17/u-boot` branch `allwinner/A733/next`. We deliberately retain the working Zero 3W vendor Boot0/U-Boot/monitor/SCP, so **their bootloader success is not a matched kernel control**.

## 8. Nested build-system patch is not a proven stand-alone Zero 3W reproduction

Reviewed `jonas5` paths:
- `patch/0001-...6.18-mainline.patch`: DTS, CPU frequency table, SoC DTSI, MMC host Kconfig/source, Motorcomm PHY, A733 PCK-600 and binding headers.
- `config/orangepi_4pro_defconfig`: current document says generated for **6.18.56**, not our 6.18.19.
- `boot/boot.cmd`: vendor-style `bootm` loading `uImage`, `uInitrd` and a 4 Pro DTB, **not** nickyg's raw `booti` route.
- `boot/orangepiEnv.txt`: 4 Pro settings, explicit `cma=256M`, serial and framebuffer assumptions.
- `scripts/build-os-image.sh` and `.github/workflows/daily.yml`: copy additional patches, use the Orange Pi build harness, and follow moving `linux-6.18.y`. The live pipeline is **not pinned to the exact 6.18.19 commit** in our hybrid.
- `bootloader/u-boot-mainline/build-uboot-allwinner.sh`: builds separate TF-A/BL31 and dlan17 U-Boot branch.
- `dts/sun60iw2p1.dtsi`: A733 power domain, clock/pinctrl, arm GIC, MMC, UART and reserved-memory graph, not a Zero 3W validation result.

These nested dependencies matter. A successful build badge is not proof that a 4 Pro DTB boots a Zero 3W. Do not import a full patch or compiled firmware before compatibility and license review.

## 9. What our experiments already eliminate

- Two-stage U-Boot per se (A2V boots).
- Vendor `booti` as a universal impossibility (VBI boots 6.6 to Debian; vendor PID1 diagnostic + LED works).
- Wrong/missing vendor environment import or FDT setup as *our current HBI script difference* (preserved).
- A bad/absent AArch64 static `/init` archive (gzip/CPIO/ELF validated and runs under vendor kernel).
- Sparse boot-file holes in the PID1-DIAG versus normalized controls (neither contains holes).
- HDMI splash as definitive proof of no Linux execution (F1 reached SSH while splash remained).
- An unlit NIC as PID1 failure evidence (PID1 probe intentionally does not start networking).

**Not eliminated:** correct kernel entry and headless early init, U-Boot relocation/arm64 header compatibility, kernel-config divergence, runtime clock/irq/power-domain binding, memory reservations, DTB compatibility and GPIO registration.

## 10. Priority actions, not speculative rebuilds

1. **Preflight actual 6.18 ARM64 Image**: exact kernel source and `.config`, Image header magic, text offset, header `image_size`, flags, bytes and overlapping `scriptaddr`, secure BL31, FDT and initrd relocation region. Confirm that HBI handoff script loads it exactly, and find the actual compiled kernel release and built-in early drivers.
2. **Resolve two competing hypotheses against vendor control**: (A) alternate `booti` initrd interface/legacy wrapping, with no fallback; (B) 6.18 early-platform/core config and driver differences, initially with no PMIC changes. Do not combine them in a single experiment.
3. **Kernel-entry observability**: prepare a *separate* earliest-kernel marker with a genuinely proven output device or safe GPIO/pinctrl implementation. `pr_emerg` alone without proven early console is not measurement; LED class may initialize only after kernel core and pinctrl.
4. **Only after entry proof**: isolate AW MMC vs MMC_SUNXI with exact DTB/regulator binding and platform power-domain registration, then HDMI fbcon, then GPU.
5. Preserve first-boot LED anomaly as deferred evidence; do not reflash merely to investigate it.

**Publication state:** External projects' results are accurately attributed; our 6.18 kernel remains hardware-unverified. Missing exact external build artifacts and any lack of WSL source reproducibility are explicit limitations.

## Source locations

- [nickyg666 AGENTS.md](https://github.com/nickyg666/orangepi-zero3w-mainline/blob/master/AGENTS.md)
- [nickyg666 reference/boot.cmd](https://github.com/nickyg666/orangepi-zero3w-mainline/blob/master/reference/boot.cmd)
- [nickyg666 README](https://github.com/nickyg666/orangepi-zero3w-mainline/blob/master/README.md)
- [jonas5 boards.md](https://github.com/jonas5/Allwinner-A733-kernel/blob/main/boards.md)
- [jonas5 mainline patch](https://github.com/jonas5/Allwinner-A733-kernel/blob/main/patch/0001-allwinner-a733-orangepi-4-pro-6.18-mainline.patch)
- [jonas5 defconfig](https://github.com/jonas5/Allwinner-A733-kernel/blob/main/config/orangepi_4pro_defconfig)
- [jonas5 boot/boot.cmd](https://github.com/jonas5/Allwinner-A733-kernel/blob/main/boot/boot.cmd)
- [jonas5 bootloader builder](https://github.com/jonas5/Allwinner-A733-kernel/blob/main/bootloader/u-boot-mainline/build-uboot-allwinner.sh)
- [jonas5 daily workflow](https://github.com/jonas5/Allwinner-A733-kernel/blob/main/.github/workflows/daily.yml)
- [our 2026-11-15 boot-chain and hybrid notes](https://github.com/mkinderwater/orangepi-zero3w-linux-mainline/blob/main/docs/2026-11-15-boot-chain.md)

**Security:** Do not copy operating credentials, Wi-Fi passwords, serialized identifiers or other private network records from upstream development notes into our report or commits.
