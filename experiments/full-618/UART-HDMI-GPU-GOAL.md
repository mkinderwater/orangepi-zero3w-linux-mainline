# Goal: Vendor-equivalent Linux 6.18, UART plus HDMI GPU

**Priority:** Match the actual Orange Pi Zero 3W vendor Linux 6.6.98 hardware feature set on Linux 6.18. No speculative features, no omissions of relevant vendor hardware, no arbitrary new add-ons.

## Target acceptance
- Keep vendor Boot0, BL31, SCP and U-Boot unchanged.
- Preserve measured 26 MHz DCXO correction feeding the effective 24 MHz PLL reference.
- Native UART0 serial console, readable 115200-baud output and interactive RX.
- Reproduce the **vendor HDMI/display pipeline** on a connected monitor, including mode detection and visible console/framebuffer output.
- Reproduce the **vendor PowerVR GPU support**, establish 6.18 kernel/firmware/userspace compatibility, and verify hardware acceleration on HDMI. Do not confuse GPU rendering with HDMI scanout.
- Preserve supported vendor hardware facilities (SD, Wi-Fi, audio, PMIC, clocks, DMA etc.) as part of parity, but do not make unrelated peripheral bring-up prerequisites for the first UART+HDMI demo when the boot arrangement does not require them.
- Make no board hardware additions or unrelated drivers merely because they are available in Linux 6.18.

## Kernel configuration rule
The vendor 6.6.98 `.config` is the baseline. Compare it against the actual generated 6.18 `.config`. Resolve version-specific Kconfig names, driver dependencies and BSP-to-mainline substitutions by *function*. Document every deviation. A single identical Kconfig symbol does not prove feature parity and absent names may represent renamed options.

Use:

```bash
python3 scripts/audit-vendor-kernel-parity.py \
  /root/opi3w-vendor-6698-work/obj-control/.config \
  /root/opi3w-m2-work/linux-618-full-integration/artifacts/kernel.config
```

Verify both paths exist first. Audit writes `vendor-parity/summary.txt` and full `diff.tsv`; it does not change a kernel configuration or boot files.

## Reference baseline
- Existing live working RAM-B `Image`: SHA-256 `67a0a073950bb6c92e2a06e61235e90509ad5d3964703dec70cb4f53e4a339c8`.
- Corrected 26 MHz RAM-B DTB: SHA-256 `1ff786ed912df7d4b4d19e366b3c968a5e0552c39f58d61a8414514eba141d9d`.
- Existing 6.18 full build: Image SHA-256 `97c98f2cc6135e938c664936674936ece49a3257935395441f4ceacdb8fb406d`; config SHA-256 `aaad20e5df200caae35dc8e58faaf6e843211d3a4b316ccf24bf55ebaf945351`.
- Other Zero 3W projects are useful implementation references, not substitutes for vendor parity or our own hardware testing.

## Do not do
- Do not add generic unrelated Kconfig drivers, extra interfaces or optional dependencies just to make a bigger kernel.
- Do not consider a PowerVR DRM device equivalent to working HDMI output. Both need tested.
- Do not replace vendor firmware as part of this kernel-only parity effort.
- Do not promote builds solely on compilation.

## Initial vendor config comparison

The operator ran the two-version comparison and reported:

- 1,523 vendor-enabled options missing or renamed in Linux 6.18
- 192 Linux 6.18 options enabled but not in the vendor config
- 2,848 other Kconfig value/version differences
- 4,563 total differences

These are symbol differences and cannot be equated to missing driver functions. The next step is the targeted `scripts/report-vendor-hardware-parity.py` report, which groups mismatches by hardware domain and prints UART/display/DRM vendor-enabled gap candidates first. **Do not enable all missing vendor options automatically.** The comparison keeps both `y` and `m` meaningful and records all selected hardware rows for manual mapping; it does not modify configurations or hardware.

```bash
python3 scripts/report-vendor-hardware-parity.py \
 /root/opi3w-vendor-6698-work/obj-control/.config \
 /root/opi3w-m2-work/linux-618-full-integration/artifacts/kernel.config
```

Report: `/root/opi3w-m2-work/linux-618-full-integration/vendor-parity/hardware-focus/summary.txt` and `hardware-differences.tsv`.

## Targeted parity result, first pass

Operator report counted 1,698 hardware-related Kconfig symbol differences: 561 vendor-enabled missing/renamed, 56 newly enabled, 1,081 other. This is **not** proof of 561 missing drivers. Critical confirmed symbols: vendor `CONFIG_DRM=y`, current 6.18 `CONFIG_DRM=n`; vendor A733 BSP modules `CONFIG_AW_DRM=y`, `AW_DRM_DE=y`, `AW_DRM_HDMI20=y`, `AW_DRM_HDMI_TX=y`, `AW_DRM_TCON=y`, `AW_DRM_TCON_TV=y`, `AW_DRM_PHY=y` are not present in the selected 6.18 config. The existing booted 6.18 native UART works despite `AW_UART_NG` being absent, so do not replace it unless hardware behavior requires it.

**Next task:** Inventory *actual* 6.6 vendor source paths and compatible strings for display engine, TCON, HDMI TX, PHY and GPU, then implement this same board's display function on 6.18 (port minimal vendor driver pieces if no equivalent), rather than toggling arbitrary DRM config flags. The candidate 6.18 build cannot be called HDMI-capable until the display engine, HDMI mode setting and PowerVR hardware path have each been proven. Run `bash scripts/inventory-vendor-display-stack.sh` to generate `vendor-display-inventory/summary.txt`. The script is read-only. Maintain the corrected 26 MHz DTB model and known-working ttyS0.

## Vendor display inventory, operator result

Vendor kernel config proves `CONFIG_AW_DRM=y`, `CONFIG_AW_DRM_DE=y`, `CONFIG_AW_DRM_TCON=y`, `CONFIG_AW_DRM_TCON_TV=y`, `CONFIG_AW_DRM_TCON_TOP=y`, `CONFIG_AW_DRM_HDMI_TX=y`, `CONFIG_AW_DRM_HDMI20=y`, `CONFIG_AW_DRM_PHY=y`, plus `CONFIG_AW_FB_CONSOLE=y`, `CONFIG_FRAMEBUFFER_CONSOLE=y` and `CONFIG_DRM=y`. Vendor GPU type is `bxm`. In our 6.18 config, `CONFIG_DRM`, `CONFIG_FB`, `CONFIG_SYNC_FILE` are disabled; `CONFIG_VT=y`, `CONFIG_VT_CONSOLE=y`. Vendor display source confirmed at `/root/opi3w-vendor-6698-work/kernel/bsp/drivers/drm` including `sunxi_device/hardware/lowlevel_de`, `lowlevel_tcon`, `lowlevel_hdmi20` and `phy`. Existing 6.18 contains mainline DRM sun4i and imagination directories, but their presence is **not** proof of A733-compatible display pipeline.

**Immediate implementation work:** map vendor-specific Kconfig dependencies, Makefile-selected sources and A733 board DT nodes to produce a *minimal actual port* of the vendor DE/TCON/HDMI20/PHY. Keep working UART driver and 26 MHz root clock. Use `scripts/map-vendor-hdmi-port.sh` for a read-only extraction into `linux-618-full-integration/hdmi-port-map/`. Only add vendor functions required on the Zero 3W, not every enabled peripheral interface in generic vendor config. Confirm HDMI scanout separately from PowerVR compute/render acceleration.

## Stage 4: First complete vendor HDMI DRM kernel build

Operator reports successful `JOBS=4 bash scripts/port-sunxi-fb-dsi-notifier-618.sh` incremental `Image modules` build. Output kernel `/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/Image-618-vendor-hdmi` SHA-256 `9a4605cea00f1af2596095285162d7c270e35ae33563cc0a8b1b4ee7e1470a98`; build `.config` SHA-256 `a70c49e15c4e7ef684f39965d1e192743e4b2387e283127beefa5788655de290`. DSI old fbdev notifier calls conditionally excluded only with DSI disabled; DSI parity remains unimplemented. Compiling the vendor display engine, TCON, HDMI transmitter and DRM is **not yet** a hardware HDMI result, and the 26 MHz minimal RAM-B DTB lacks known complete display nodes. Next: extract and compare exact original vendor Zero 3W live display graph and dependencies, stage a separately named test DTB, verify boot-time UART and HDMI independently, then GPU rendering. Never overwrite RAM-B LKG.

## Vendor compiled Zero 3W DTB comparison

Operator compared `obj-control` and `obj-identity` compiled vendor 6.6.98 DTBs; DTS diff was 11 lines. Both include enabled `allwinner,sunxi-drm`, DE v352 at `0x05000000`, TCON_TOP0/1 at `0x05500000`/`0x05510000`, TCON3/4 at `0x05730000`/`0x05731000`, and HDMI0 at `0x05520000`. Vendor also describes `img,gpu` at `0x01800000` but the current Linux 6.18 test config has `CONFIG_DRM_POWERVR` disabled.

Vendor HDMI references clock provider phandles `0x12` and `0x2e` and power-domain provider `0x13`; those are **not transferable numeric IDs** into the tiny RAM-B DTB. DE and TCON have related reset and power dependencies. The current RAM-B DTB does not contain the vendor display graph.

Run `python3 scripts/resolve-vendor-hdmi-dependencies.py /root/opi3w-m2-work/linux-618-hdmi-stage4/vendor-dtb-topology/vendor-control.dts /root/opi3w-m2-work/linux-618-hdmi-stage4/vendor-dtb-topology/ram-b.dts --output /root/opi3w-m2-work/linux-618-hdmi-stage4/vendor-dtb-topology/phandle-dependencies.txt` to resolve providers. This is read-only; a boot DTB has **not** been constructed or verified. Retain vendor firmware, proven 26 MHz oscillator and UART.

## Provider compatibility findings from Stage4

The operator's `provider-compat/summary.txt` confirms `CONFIG_SUN60I_A733_CCU=y`, `CONFIG_SUN60I_A733_R_CCU=y`, and source matches `allwinner,sun60i-a733-ccu` and `allwinner,sun60i-a733-r-ccu`. The former provider lookup's `NO MATCH` for vendor `sun60iw2` strings was **not proof of no CCU support**. A driver for PCK-600 exists, but the inspected `sun55i-pck600.c` matches `allwinner,sun55i-a523-pck-600`, not the vendor A733 `allwinner,sun60iw2-pck-600`; its domain ordering/equivalence has not been established. The running full-build config has `# CONFIG_IOMMU_SUPPORT is not set`. DE v352's vendor node declares `iommus = <&vendor_iommu 8 1>`, so IOMMU is an unresolved functional dependency. `CONFIG_SUN6I_RTC_CCU=y` does **not** by itself establish support for the vendor RTC clock provider `allwinner,sun60iw2-rtc-ccu` or its DCXO clock ID 12.

**Critical clock/reset warning:** Vendor and 6.18 A733 clock/reset binding numbering differ. Example, vendor HDMI resets main/sub/HDCP IDs 108/107/106, while the examined 6.18 bindings identify RST_BUS_HDMI_MAIN=107, SUB=108, HDCP=109. Never inject vendor numerical IDs into modern 6.18 DTB. A clock ID match must be by semantic name and implemented gate, not integer equality. `scripts/check-hdmi-clock-power-618.sh` now gathers exact 6.18 clock/reset symbols and PCK-600 domain source for the next mapping. No HDMI DTB has been staged or tested.

## Provider implementation gate after clock/power audit

Operator's 6.18 report establishes `CONFIG_PM_GENERIC_DOMAINS=y`, `CONFIG_PM_GENERIC_DOMAINS_OF=y`, `CONFIG_SUN60I_A733_CCU=y` and `CONFIG_SUN60I_A733_R_CCU=y`. `CONFIG_IOMMU_SUPPORT` and `CONFIG_SUN55I_PCK600` are disabled. The source has `drivers/pmdomain/sunxi/sun55i-pck600.c` for A523, but it **does not yet** show a compatible match for vendor `allwinner,sun60iw2-pck-600`. Vendor domain source: `bsp/drivers/pm_domain/pck600_domains.c`; clock and reset binding source: `bsp/include/dt-bindings/clock/sun60iw2-ccu.h`, `bsp/include/dt-bindings/reset/sun60iw2-ccu.h`.

Next work: map vendor clock/reset *symbols* to 6.18 A733 definitions using `scripts/compare-a733-display-bindings.py`, then inspect implementation registers for names changed, port A733 PCK-600 domain layout, enable the vendor-equivalent IOMMU only if required by the display path, and stage a new HDMI DTB with explicit translated references. Do not add PCK A523 compatible without validating the A733 power-domain layout. This source report alone does not prove graphics providers probe on hardware. Continue to preserve RAM-B boot payloads and UART.

## A733 PCK-600 integration staged (source only)

The vendor PCK-600 implementation establishes **11 domains**, unlike the mainline A523 driver's 8: indices 0 VI, 1 DE_SYS, 2 VE_DEC, 3 VE_ENC, 4 NPU, 5 GPU_TOP, 6 GPU_CORE, 7 PCIE, 8 USB2, 9 VO, 10 VO1. Vendor A733 delay register values `0x1f1f1f` / `0x1f1f` differ from A523 `0xffffff` / `0xffff`. Both use delay offsets `0x170/0x174/0xc00/0xc04/0xc10` and common switch values `0x8080808`, `0x808`, `0x8`. Vendor `sun60iw2_pck600_pmu.has_rst_clk=false`; preserve this board-specific reset policy.

Committed `scripts/integrate-a733-pck600-618.py` and `scripts/build-a733-pck600-618.sh` apply the domain descriptor only to isolated Stage 4 sources and compile the modified provider. This is **not yet host-run or hardware-proven**. Existing A523 behavior is retained. Build does not create an HDMI-enabled DTB. After successful build, verify PCK parent clock and nested `power-controller` provider topology before enabling DE and VO domains. Keep the working UART and 26 MHz baseline unchanged.

## 2026-11-18 hardware discovery: HDMI cable affects Linux 6.18 UART visibility

Operator booted the VBI-based RAM-B automatic-image control using the SHA-verified RAM-B Linux 6.18.19 kernel (`67a0a073950bb6c92e2a06e61235e90509ad5d3964703dec70cb4f53e4a339c8`), RAM-B 26 MHz DTB (`1ff786ed912df7d4b4d19e366b3c968a5e0552c39f58d61a8414514eba141d9d`) and diagnostic initramfs. With an HDMI cable connected, UART logging stopped after `BL3-1: Next image spsr = 0x3c5`. After removing the HDMI cable, the operator immediately observed Linux initcalls, `Run /init as init process`, BusyBox shell and an interactive `uname -a` yielding `Linux (none) 6.18.19+ #1 SMP Tue Nov 17 18:54:09 CST 2026 aarch64 GNU/Linux`.

**Interpretation:** the no-output symptom cannot be claimed to be a generic Linux 6.18 failure or a BL31 handoff failure. An HDMI connection is correlated with the silent-console symptom. Exactly whether disconnect was before or during the boot and whether the same-boot system was running silently is not proven; repeat controlled HDMI connected/disconnected cold boots with otherwise identical payloads, serial logging and power conditions before ascribing root cause. Vendor U-Boot's display-path clock failure (`clk_set_rate: <NULL> has NULL parent`, `suxni tcon hdmi set rate`) is a plausible lead, not proof of the mechanism. `keep_bootcon` causes duplicate logs; treat duplicate kernel printk as console overlap, separately from HDMI interaction. RAM-B `CONFIG_PROC_FS=n` explains the proc mount error.

**Immediate actions:** freeze known-good VBI-based RAM-B control image and hashes; compare HDMI connected/disconnected cold boots of that exact image; independently verify UART output and shell responsiveness on both; then test the isolated PCK-600 kernel with the same 26MHz baseline DTB, and finally the PCK-600 DTB. Restore the original priority of delivering simultaneous UART + HDMI, then PowerVR. Do not alter firmware, CCU clock values, or reboot logic based solely on this single observation.

## 2026-11-18 A733 PCK-600 hardware probe verified

Operator booted `opi3w-618-pck600-ram-shell.img` with HDMI disconnected. Its Linux 6.18 kernel is `Image-618-vendor-hdmi-pck600-syscon` (SHA256 `9f8c4af6f7f3d5ff604aac29bd7553e04dc3a41c0c8a5000308594c49ab5cb1c`), with verified PCK probe DTB SHA256 `c5cc45413f4be4efbf80a1c26c061462e2a9b2e3649a49bf055b008d5209f697` and a RAM-only BusyBox initramfs. The source image `opi3w-618-pck600-fat-probe.img` previously reached userspace with an M2cr initramfs but waited 90 seconds for a nonexistent root UUID.

Observed UART:
```text
PCK600-RAM-SHELL: /init entered
PCK600-RAM-SHELL: no MMC/PMIC root discovery
PCK600-RAM-SHELL: interactive BusyBox follows
probe of 7060000.pck-600 returned 19 after 15 usecs
probe of 2002000.clock-controller returned 0 after 691 usecs
probe of 7010000.clock-controller returned 0 after 429 usecs
probe of DE_SYS returned 0 after 17 usecs
probe of VO returned 0 after 11 usecs
probe of VO1 returned 0 after 11 usecs
probe of 7060000.pck-600:power-controller returned 0 after 11160 usecs
probe of 7025000.pinctrl returned -517 after 3 usecs
probe of 2000000.pinctrl returned -517 after 2 usecs
probe of 7025000.pinctrl returned 0 after 28496 usecs
probe of 2000000.pinctrl returned 0 after 31674 usecs
PM: genpd: Disabling unused power domains
```
`/sys/bus/platform/drivers/sunxi-pck-600/` contains a bound symlink to `7060000.pck-600:power-controller`. BusyBox uptime output: **13m23s** with no reset observed. Note the parent `7060000.pck-600` probe diagnostic `19` is not a negative error code; verify context only if it becomes relevant. Pin controllers initially deferred (`-517`), later initialized.

**Milestone reached:** PCK-600 genpd provider and all three declared A733 display domains register successfully on hardware. This does not demonstrate domain power transitions, display scanout, IOMMU success, HDMI electrical signaling or PowerVR acceleration. The current probe DTB intentionally lacks DE, TCON and HDMI graph nodes. Next controlled experiment: check reproducible UART with HDMI physically connected on the exact same image; if stable, integrate the vendor display graph with translated A733 CCU reset/clock bindings and validate provider dependencies before building another DTB. Retain current kernel and verified power-domain setup.

## 2026-11-18 hardware hotplug result: running RAM-shell survives HDMI changes

Operator independently confirmed the same Linux 6.18 RAM-shell remains responsive when an HDMI cable is **connected or removed after Linux has already booted**, including BusyBox uptime checks after connection. This is a separate positive observation from the existing evidence that starting the kernel with HDMI already connected produces no observed UART output after BL31.

**Interpretation:** post-boot HDMI hotplug does not by itself stop the RAM-shell or UART in the tested configuration. Boot-time behavior with HDMI present is the focus; do not claim hotplug lockup. This observation does not distinguish a genuine early Linux hang from UART silence on an otherwise running kernel. The test DTB still omits DE/TCON/HDMI nodes, so it is not a display scanout test.

**Next isolation:** compare cold boots with cable connected/disconnected while keeping all binaries fixed, and investigate vendor U-Boot's HDMI display setup (clock parent, splash/scanout, FDT mutations) versus kernel entry. Preserve the verified PCK-600 probe, RAM-shell initramfs and 26MHz clock baseline. Do not disable HDMI at the hardware or change firmware based only on this correlation.
