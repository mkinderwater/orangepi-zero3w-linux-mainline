# Additional Linux 7.x A733 assets and Zero 3W provenance audit

**Date:** 2026-11-16  
**Evidence status:** Public repository files and nested build metadata inspected. **No verified Linux 7.x userspace boot on Orange Pi Zero 3W located.** The first-boot LED anomaly remains deferred, as directed. Linux 6.18 hardware execution remains unverified.

## 1. Important distinction: A733 7.x support is not necessarily Zero 3W hardware support

| Source | Published kernel/target | Evidence | Relevance |
| --- | --- | --- | --- |
| [warpme/minimyth2](https://github.com/warpme/minimyth2) | Linux **7.3** A733 patch collection; configured board **Radxa Cubie A7A** | Patch source and build graph verified; **Zero 3W hardware boot not established** | **High** for modern SoC clock, pinctrl, MMC and DT architecture |
| [armbian/build](https://github.com/armbian/build) | Linux 7.x in the general Armbian framework, but Zero 3W `KERNEL_TARGET="vendor"` and family pins **6.6** | Exact Zero 3W board config, family config, firmware provenance and boot script verified | **High** for official board-specific firmware, VBI-compatible `booti`, boot scripts and BSP corrections |
| [cyber-zoo/meta-saha](https://github.com/cyber-zoo/meta-saha) | Orange Pi Zero 3W uses **6.6.98** Yocto/BSP | Build/WIC validation, **physical board qualification pending** | Medium: independent boot image packing and source pinning |
| [nickyg666/orangepi-zero3w-mainline](https://github.com/nickyg666/orangepi-zero3w-mainline) | **6.18.19+** hybrid Zero 3W | Reported actual 6.18 userspace boot, not ours | **Highest board-specific boot reference** |
| [jonas5/Allwinner-A733-kernel](https://github.com/jonas5/Allwinner-A733-kernel) | Linux 6.18.y on Orange Pi 4 Pro and Radxa A7 boards | Zero 3W listed platform ready, not fully validated | High for another A733 implementation |
| Public user comment on CNX, April 2026 | Claims 6.18 port can be adapted to **7.0** with minor changes | Claim only; no identified commit, image hash or Zero 3W boot log | Hypothesis, not evidence of boot |

Do not conflate **Armbian 7.1/7.2 edge support for other boards** with its sun60iw2 family, nor **Radxa ZERO 3W (RK3566)** with Orange Pi Zero 3W (A733).

## 2. MiniMyth2: real nested Linux 7.3 A733 source chain

Inspected:
- [`script/kernel/linux-7.3/Makefile`](https://github.com/warpme/minimyth2/blob/master/script/kernel/linux-7.3/Makefile): Linux 7.3 kernel source from kernel.org, explicit patch order.
- [`script/kernel/linux-7.3/files/`](https://github.com/warpme/minimyth2/tree/master/script/kernel/linux-7.3/files): A733 clock, reset, pinctrl, DMA, MMC, PCIe, power, DTS, display patch files.
- [`script/bootloaders/u-boot-a733/Makefile`](https://github.com/warpme/minimyth2/blob/master/script/bootloaders/u-boot-a733/Makefile): A733 U-Boot source.
- [`script/bootloaders/board-a733.cubie_a7a/Makefile`](https://github.com/warpme/minimyth2/blob/master/script/bootloaders/board-a733.cubie_a7a/Makefile): **radxa-cubie-a7a_defconfig**, not a Zero 3W defconfig.
- [`script/bootloaders/board-a733.cubie_a7a/files/extlinux.conf`](https://github.com/warpme/minimyth2/blob/master/script/bootloaders/board-a733.cubie_a7a/files/extlinux.conf): `/Image` + `sun60i-a733-cubie-a7a.dtb` via extlinux; no evidence this is the vendor Zero 3W A2V boot script.
- [`script/utils/kickstart-oe/files/a733-generic.conf`](https://github.com/warpme/minimyth2/blob/master/script/utils/kickstart-oe/files/a733-generic.conf): stages kernel Image, A733 DTBs, U-Boot and board boot-package, rather than our fixed stock HBI donor.

### Patch order and strongest assets

| Linux 7.3 patch group | Concrete finding | Question for our 6.18 BSP |
| --- | --- | --- |
| `6000–6025` clock/CCU | A733 PRCM, PLL, bus clocks, gates and reset lines, plus explicit critical fabric clocks | Does our vendor CCU keep equivalent paths enabled during startup? |
| **`6008` CPUS bus gate** | Marks `ahb-cpus` clock critical because gating may make firmware PSCI and reset calls hang | Does our vendor CCU gate this bus? We have not established it |
| **`6009` MSI-Lite bus gates** | Retains fabric gates before USB, DMA, GMAC/CE; disabled gates can make MMIO reads return zeros and DMA time out | Check clock-gate lifetime, not just that driver objects compiled |
| **`6010` USB fabric clock** | Keeps `ahb-usb-sys` critical, otherwise unused-clock shutdown may isolate controllers | Important for eventual USB, but our PID1-only probe intentionally does not initialize NIC |
| `6022` display-fabric gates | Keeps DE AHB and MBUS clocks critical | Potential HDMI issue, not yet evidence of no kernel entry |
| `6030–6039` pinctrl | New A733 register layout, set/clear, R bank, interrupt bank indexing; **two-bit voltage control** | Compare vendor pinctrl's implemented register semantics before borrowing changes |
| **`6038` empty leading IRQ banks** | Fixes EINT bank-index mismatch on A733, previously causing wrong parent interrupt/bank-B storm on other A733 hardware | Potential interrupt issue; does not itself explain absence of PID1 |
| **`6039` 2-bit GPIO bank voltage** | Uses a 2-bit bank voltage selector on A733 (3.3 V/1.8 V), including R pinctrl | Avoid raw register writes. Compare voltage configuration with vendor driver |
| `6045–6048` DMA | A733 channel/interrupt and address-width support | Stage only after core entry |
| `6065–6070` MMC | Polling, clocks, A523-v5p3x phases and sample-delay-chain tuning | Relevant to our different `AW_MMC` vs other project's `MMC_SUNXI`; likely post-entry/root-stage question |
| `6200–6201` A733 DTSI/OPP | Modern SoC description, 2 A76 + 6 A55, PSCI, clocks, pinctrl, power domains and MMC | Audit our compiled 0.2.7 DTB property-by-property |
| `6250` Cubie A7A board DTS | **Radxa-specific** regulators, GPIO, LED PJ26/PJ27, wireless switches | **Never** flash as Zero 3W DTB; ours physically verified LED PL7 |
| `6205–6209`, `6251–6253` | Display/HDMI and related DTS/board patches exist, but are **commented out** in inspected Linux 7.3 Makefile | File presence does not imply enabled DRM or a working HDMI target |

**Note:** The Linux 7.3 A733 patches are a newer *architecture*, not turnkey drop-ins for our 6.18 Allwinner vendor `bsp/` driver tree. A `CLK_IS_CRITICAL` patch against upstream `ccu-sun60i-a733.c` cannot be applied directly to a different vendor CCU implementation without checking address and gate semantics. Linux 7.3 build support is not a verified Zero 3W 7.3 userspace boot.

## 3. Armbian nested Zero 3W support: board-specific facts we should use

Inspected [`config/boards/orangepizero3w.conf`](https://github.com/armbian/build/blob/main/config/boards/orangepizero3w.conf):
- `BOARDFAMILY="sun60iw2"`, `KERNEL_TARGET="vendor"`, `KERNEL_TEST_TARGET="vendor"`
- `BOOT_FDT_FILE="allwinner/sun60i-a733-orangepi-zero3w.dtb"`
- **Explicit boot0 source:** `boot0_sdcard_orangepizero3w.fex`, comment says from Orange Pi Ubuntu 1.0.2 and supports **1 GB LPDDR4/4X** (important to our tested 1 GB variant).
- Board-specific boot0 differs from [4 Pro config](https://github.com/armbian/build/blob/main/config/boards/orangepi4pro.csc), although both share sun60iw2 family and AIC8800D80 UART Bluetooth configuration.

Inspected [`config/sources/families/sun60iw2.conf`](https://github.com/armbian/build/blob/main/config/sources/families/sun60iw2.conf):
- Pinned vendor kernel source `orangepi-xunlong/linux-orangepi` branch `orange-pi-6.6-sun60iw2`, not Linux 7.x.
- Pinned vendor U-Boot source `orangepi-xunlong/u-boot-orangepi` commit `b791be842935b27268ae3d00e943a9075495f30a`; ARM32 compiler and 2018-series bootloader.
- Firmware package data under `orangepi-xunlong/rk-rootfs-build` ref `7b6d78d4f5eaefd5456777fbea5057a0876e8f4d` with `sun60iw2_packages`; vendor packing tools obtained from `orangepi-build`.
- Offsets `boot0` at 8 KiB and boot-package at **16,400 KiB**; both match our stock 32 MiB-reserved layout. Do not overwrite with Radxa/Cubie packaging offsets.
- Bootloader packing `sys_config`, DT and monitor/SCP firmware must remain matched; not interchangeable with an arbitrary 7.x kernel project.

Inspected [`config/bootscripts/boot-sun60iw2.cmd`](https://github.com/armbian/build/blob/main/config/bootscripts/boot-sun60iw2.cmd):
- Uses **raw `Image` + `booti`**, but stages kernel at `0x41000000`, DTB at **`0x4a000000`**, ramdisk at **`0x4b000000`**, scratch at **`0x4d000000`**.
- Loads a `uInitrd` file with `booti kernel ramdisk fdt` (legacy-style, no explicit `:size`). This is a **third** meaningful handoff profile beyond our `0x44000000/0x45000000` raw `ramdisk:size` and nickyg's lower addresses + legacy-wrapped ramdisk.
- Preserves env import, root selection, FDT addr/resize, overlays; has fallback on overlay error to original DTB. Need independent no-fallback branch before using it as a kernel-identity test.
- It is vendor **6.6** support, so this does not prove `booti` with our 6.18 Image works.

### Nested Armbian Zero 3W DTS corrections

- `0008-orangepizero3w-keep-csi-camera-rail-always-on.patch`: BLDO2 camera rail and unreferenced regulator, later subsystem risk.
- `0009-orangepizero3w-use-soc-rtc-drop-phantom-hym8563.patch`: removes non-populated external RTC, enables working on-SoC RTC. This is a real board-DTS hardware bug fix, but does not establish 6.18 failure.
- `0010-orangepizero3w-gpu-clk-rate-and-voltage.patch`: GPU clock/power behavior; not a kernel-entry prerequisite.
- Mainline **7.x** work elsewhere in Armbian does not make `sun60iw2` a 7.x target; check the board and family configuration, not only the global build release.

## 4. Independent Yocto image packer (not Linux 7.x)

[`cyber-zoo/meta-saha`](https://github.com/cyber-zoo/meta-saha) has a Zero 3W BSP path with **vendor 6.6.98**, a 32 MiB reserved MBR layout, boot0 at 8 KiB, boot package at 16,400 KiB and a native ARM-header `uImage`. Its tests check output WIC packaging and boot payloads and distinguish isolated ARM64 software execution from **physical boot (still pending)**.

Nested assets include:
- `kas/targets/orangepi-zero3w.yml`
- `saha-layers/meta-allwinner-saha/conf/machine/include/orangepi-zero3w-microduck.inc`
- `saha-layers/meta-allwinner-saha/recipes-kernel/linux/linux-orangepi_%.bbappend`
- `tests/check-microduck-boot.py` verifying image offsets and MBR geometry.

Use its methodology for build provenance and precise offline validation, not as evidence of Linux 7.x hardware support.

## 5. New working hypotheses tied back to our actual 6.18 result

**H1: mismatched U-Boot handoff and relocated initrd.** We have **three** source-defined variations:
- our verified VBI/HBI: `0x41000000` kernel, `0x44000000` DTB, `0x45000000` raw gzip initrd with `:size`;
- nickyg666's reported successful Zero 3W: same nominal staging but **legacy-wrapped tiny uInitrd**, `booti kernel ramdisk fdt`;
- Armbian vendor `6.6`: `0x41000000` kernel, `0x4a000000` DTB, `0x4b000000` ramdisk, `0x4d000000` scratch, legacy-style `booti`.

A separate paired test can isolate the initrd interface from the kernel source, with an appropriate vendor control and exact payload/hash/BL31 relocation audit. Avoid changing addresses *and* initrd interface in the same image.

**H2: core clocks/PSCI and IRQ/fabric gates.** MiniMyth2 identifies A733-specific gates which can silently hang firmware-mediated operations or block MMIO when disabled. Our 0.2.7 vendor CCU may keep these enabled already; we have not compared its actual gate flags or initialization order. Targeted source audit of our kernel's compiled CCU and config should precede edits. This is now a stronger source-grounded hypothesis than speculative GPIO MMIO markers.

**H3: pinctrl and GPIO register programming.** The MiniMyth2 two-bit A733 bank-voltage fix and EINT bank mapping are concrete, but direct implementation belongs to its upstream-style driver. Our observed 6.18 LED failure can equally result from no PID1, no LED class initialization or incompatible pinctrl. Compare vendor source implementation; do not transplant raw writes.

**H4: SD/MMC runtime failure.** Modern `MMC_SUNXI` timing and voltage fixes and the nickyg final AW_TWI/AXP8191 `vmmc-supply` sequence suggest an important post-entry gate. Yet our **root-independent PID1 test does not require SD** once the initramfs is loaded. A root-mount failure alone cannot explain the absence of the PID1 diagnostic unless earlier driver initialization blocks or crashes.

**H5: HDMI.** MiniMyth2's HDMI patches exist, but are disabled in the inspected Makefile, and F1 proved a running 6.6 kernel can leave the bootloader splash displayed. Do not interpret the splash as a 7.x or 6.18 entry failure.

## 6. Priority read-only WSL comparison (before the next build)

Use the actual source/config pinned in our `/root/opi3w-hybrid-build-0.2.7`, not guessed source:

```bash
K=/root/opi3w-hybrid-build-0.2.7
grep -E '^(CONFIG_(ARM64|ARCH_SUNXI|AW_SUN60IW2_CCU|AW_PINCTRL_SUN60IW2_R|AW_TWI|AW_MMC|MMC_SUNXI|AW_UART_NG|CLK_IGNORE_UNUSED|LEDS_GPIO|GPIOLIB|OF_GPIO))=' "$K/build/.config"

grep -R -n -E 'ahb.cpus|ahb-cpus|msi.lite|usb.sys|CLK_IS_CRITICAL|0x5c0|0x594|0x59c|0x5a4' \
  "$K/linux/bsp/drivers" "$K/linux/drivers/clk" 2>/dev/null | head -100

grep -R -n -E 'PIO_POW_MOD_SEL|BIAS_VOLTAGE|pow_mod_sel|withstand|voltage' \
  "$K/linux/bsp/drivers/pinctrl" 2>/dev/null | head -80
```

**Beware:** `grep | head` with `pipefail` can exit 141; this is a read-only exploratory command and should not be used as a binary acceptance gate. The vendor source may name gates differently; absence of these strings alone is not proof of absence of equivalent logic.

Next research stage: compare actual clock gate register tables and dependency graph from our BSP against MiniMyth2's 7.3 A733 patches, then review finished U-Boot `booti` branch. No kernel-version jump until the effective differences are understood.

## 7. References

- [MiniMyth2 Linux 7.3 Makefile](https://github.com/warpme/minimyth2/blob/master/script/kernel/linux-7.3/Makefile)
- [MiniMyth2 A733 PRCM](https://github.com/warpme/minimyth2/blob/master/script/kernel/linux-7.3/files/6002-clk-sunxi-ng-a733-Add-PRCM-CCU.patch)
- [MiniMyth2 critical CPUS gate](https://github.com/warpme/minimyth2/blob/master/script/kernel/linux-7.3/files/6008-clk-sunxi-ng-a733-mark-the-CPUS-bus-gate-as-critical.patch)
- [MiniMyth2 MSI-Lite critical gates](https://github.com/warpme/minimyth2/blob/master/script/kernel/linux-7.3/files/6009-clk-sunxi-ng-a733-keep-the-MSI-Lite-bus-clocks-runni.patch)
- [MiniMyth2 GPIO voltage fix](https://github.com/warpme/minimyth2/blob/master/script/kernel/linux-7.3/files/6039-pinctrl-sunxi-a733-fix-the-GPIO-withstand-voltage-en.patch)
- [MiniMyth2 A733 IRQ fix](https://github.com/warpme/minimyth2/blob/master/script/kernel/linux-7.3/files/6038-pinctrl-sunxi-fix-EINT-bank-indexing-for-SoCs-with-e.patch)
- [MiniMyth2 MMC clock phases](https://github.com/warpme/minimyth2/blob/master/script/kernel/linux-7.3/files/6069-mmc-sunxi-Add-A523-clock-phases.patch)
- [MiniMyth2 Cubie A7A DTB](https://github.com/warpme/minimyth2/blob/master/script/kernel/linux-7.3/files/6250-arm64-dts-allwinner-add-radxa-ciube-a7a-initial-dts.patch)
- [Armbian board config](https://github.com/armbian/build/blob/main/config/boards/orangepizero3w.conf)
- [Armbian sun60iw2 sources](https://github.com/armbian/build/blob/main/config/sources/families/sun60iw2.conf)
- [Armbian vendor booti script](https://github.com/armbian/build/blob/main/config/bootscripts/boot-sun60iw2.cmd)
- [meta-saha Zero 3W reference](https://github.com/cyber-zoo/meta-saha/blob/main/docs/hardware/orangepi-zero3w.md)
- [April 2026 Linux 7.0 feasibility claim](https://www.cnx-software.com/2026/04/15/orange-pi-zero-3w-an-allwinner-a733-sbc-in-raspberry-pi-zero-form-factor/)

**Preserve provenance:** do not redistribute full vendor U-Boot/Boot0 firmware, nonredistributable blobs or someone else's proprietary assets. Copy individual license-compatible patches only after review.
