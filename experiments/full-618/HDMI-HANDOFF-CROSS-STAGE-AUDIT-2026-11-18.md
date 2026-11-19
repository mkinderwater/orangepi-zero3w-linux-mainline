# A733 HDMI handoff: source and hardware evidence review

**Date:** 2026-11-18. **Status:** read-only audit prepared; operator run pending. No firmware or kernel changes authorized by this report.

## Question

Why does an Orange Pi Zero 3W with HDMI connected **before power-on** stop emitting UART output after BL31 when Linux 6.18 starts, when the *same* kernel/DTB/initramfs reaches BusyBox if HDMI is connected at the U-Boot prompt or after boot?

## Observed hardware matrix

| HDMI timing | Linux UART outcome | Notes |
| --- | --- | --- |
| Connected before power-on | Silent after BL31 | **Linux CPU progress not independently established** |
| Disconnected until U-Boot prompt, then attached | BusyBox reached | Same PCK600 kernel/DTB/initramfs |
| Disconnected through kernel boot | BusyBox reached | PCK600 DE_SYS/VO/VO1 probes PASS |
| Attached or removed after BusyBox | Shell remains responsive | No evidence of a running-system hotplug lockup |

These tests **do not prove** the vendor DRM logo function is responsible. The temporary `setenv drm_debug 1` was only set after bootloader initialization, while the CRC-valid ext4 `/uboot.env` was not imported on cold boot. No early DRM bypass was actually tested.

## Source-controlled anchors

- Vendor U-Boot `v2018.05-sun60iw2`, T736 defconfig `CONFIG_AW_DRM=y`. Installed firmware reports **2018.07-orangepi-config-dirty**, so source/binary equivalence is unproven.
- `common/board_r.c`: `initr_sunxi_plat` precedes `initr_env`, which precedes `board_env_late_init` in the observed source sequence.
- `board/sunxi/board_common.c`: `board_env_late_init` can execute `sunxi_show_logo` under `CONFIG_AW_DRM`.
- `drivers/video/drm/sunxi_drm_drv.c`: `sunxi_drm_device_get` returns NULL when `drm_debug=1`; `sunxi_drm_kernel_para_flush` modifies the working FDT and calls `sunxi_de_add_kernel_iova_premap`, which looks up `/soc/de`.
- The test RAM-B PCK600 DTB deliberately lacks a complete DE/TCON/HDMI graph. The vendor 6.6.98 DTB contains that graph. U-Boot reported `sunxi_de_add_kernel_iova_premap fail ret-4` and a related FDT subnode error. Establish if identical errors occur on both PASS and FAIL boots before assigning causality.
- Vendor T736 `CONFIG_ENV_IS_IN_EXT4=y` does not establish actual compiled environment device/partition. The installed boot region contains `uboot.env` and `drm_debug` strings, not a proved import location.

## Independent public evidence

1. [Same-board Zero 3W HDMI clock report](https://github.com/aricshow/orangepi-zero3w-armbian-cyberdeck-mods): vendor DTB TCON3 lacked the `CLK_HDMI_TV` pixel clock consumer; Linux video depended on gates initialized by U-Boot. This is **strong evidence of inherited firmware clock state on the same board**, but its observed failure was missing/unstable video, not our UART silence.
2. [A733 CCU/PRCM v7, November 12, 2026](https://lists.openwall.net/linux-kernel/2026/11/12/989): corrected HDMI CEC/SFR mux widths, video/DE clock children and PLL handling; the series is rebased to 7.4-rc1. **Not an HDMI cold-boot fix** and should not be copied wholesale to our 6.18 tree.
3. [A733 Linux 6.18 project](https://github.com/jonas5/Allwinner-A733-kernel): claims HDMI support on Orange Pi 4 Pro, a *different board*. Its [mainline U-Boot/FEL instructions](https://github.com/jonas5/Allwinner-A733-kernel/tree/main/bootloader/u-boot-mainline) illustrate a non-legacy firmware path, but are not validation for the Zero 3W.
4. [Allwinner vendor U-Boot source](https://github.com/orangepi-xunlong/u-boot-orangepi/tree/v2018.05-sun60iw2): exact legacy DRM functions and FDT handoff available for static analysis. Installed build identity differs.

## New reproducible offline audit

Run from the integration repository on the Debian builder:

```sh
python3 scripts/audit-a733-hdmi-handoff-offline.py
```

Default report:

`/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/hdmi-handoff-offline/report.txt`

The audit:
- Verifies hashes of host inputs and preserves exact source identities
- Extracts relevant U-Boot source context for pre-prompt init, persistent env, DRM probe and FDT handoff
- Decompiles the PCK600 test DTB into a new evidence directory and compares named display and power nodes to the vendor DTS
- Reports selected kernel Kconfig functions while distinguishing compiled drivers from **active device consumers**
- Records the existing hardware test matrix separately from source and internet claims
- **Does not** write to any input image, installed firmware, kernel, DTB, MMC or register

The audit may report missing vendor DTS if the local pathname differs. Pass it explicitly via `--vendor-dts` rather than assuming a particular file.

## Decision gates

1. Resolve exactly which `/soc/de`, `sunxi-drm`, HDMI, TCON and IOMMU nodes are missing from the Linux handoff DTB and whether firmware's corresponding FDT errors also occur during PASS boots.
2. Compare the *compiled* Linux 6.18 A733 CCU clock registers/parents to v7 source, particularly HDMI-TV/SFR/CEC, video/DE PLL children, oscillator normalization, and secure switch constraints. Mark missing upstream fixes as candidates, not causes.
3. Before changing U-Boot, use the original binary's disassembly or exact build configuration to establish which early display path and environment backend are in use. Source-only (2018.05) conclusions cannot certify behavior of the installed modified (2018.07) binary.
4. Before firmware replacement, choose an independent marker capable of proving Linux execution despite UART silence. Do not confuse a blank HDMI screen with halted Linux.
5. Continue the experimental no-logo U-Boot compile only as a separate research artifact. **Do not flash it**. Its source differs from installed firmware, and recent GCC compatibility fixes change more than the intended DRM function.

**Current decision:** hold new flash builds; finish offline comparison and evidence trace. Then choose one isolated hardware test with a falsifiable prediction and a preserved recovery image.
