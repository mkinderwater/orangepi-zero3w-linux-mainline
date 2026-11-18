# Linux 6.18.19 Full Integration: Orange Pi Zero 3W

**Status:** Build procedure committed, **not executed on the user's Debian host**. Hardware validation pending. This is not a release.

## Why now

RAM-B proved eight-CPU Linux kernel entry, corrected oscillator modeling (actual firmware-selected 26 MHz DCXO yields 24 MHz PLL_REF), native UART input and output, AArch64 initramfs shell, and >12 minutes observed uptime. This justifies moving from diagnostic-only to a full kernel configuration. The kernel with script support was SHA-256 `67a0a073950bb6c92e2a06e61235e90509ad5d3964703dec70cb4f53e4a339c8`. Corrected test DTB SHA-256 `1ff786ed912df7d4b4d19e366b3c968a5e0552c39f58d61a8414514eba141d9d`.

## References

- [nickyg666 Zero 3W 6.18 work](https://github.com/nickyg666/orangepi-zero3w-mainline/blob/master/AGENTS.md): independently reports systemd userspace, regulator-backed MMC root, AIC8800 SDIO Wi-Fi, GPU kernel and Mesa Vulkan experiments. Their 6.18 integration is a BSP hybrid and is **not our hardware proof**.
- [jonas5 A733 kernel support matrix](https://github.com/jonas5/Allwinner-A733-kernel/blob/main/boards.md): three A733 boards fully validated, Zero 3W listed **Platform Ready**, not fully validated.
- [RAM-B clock test and proof](../ram-b/CLOCK-TEST-01.md).
- [Original bootloader research](../../docs/2026-11-15-boot-chain.md).

## Build

From a Git checkout of this branch, on the Debian cross-build machine:

```bash
JOBS=4 bash scripts/build-linux-618-full-integration.sh
```

The script uses `/root/opi3w-m2-work/a733-try9-ramoops-v2/linux` as the **existing hardware-booted modified A733 source**, copies RAM-B's working `.config` into a separate output tree, enables normal OS filesystems/process and network interfaces, and builds `Image modules`. It does **not** pretend these existing local source modifications are a reviewed clean patch series; source culling/provenance is subsequent work.

The output is under `/root/opi3w-m2-work/linux-618-full-integration/`. Kernel, current clock-corrected DTB and config are copied into `artifacts/` with SHA-256 and a manifest. Modules remain in `obj/` until a separately validated modules installation. No SD card, Boot0, firmware, boot scripts, RAM-A, or RAM-B binaries are overwritten.

**Note:** the current minimal DTB does not declare all devices needed for full userspace (MMC rails, wireless SDIO, USB, audio, GPU/NPU). A successful kernel compile is **not** successful hardware integration.

## Staged hardware integration

| Stage | Requirements |
|---|---|
| F0 | Image + modules compile with verified config, source provenance and hashes |
| F1 | RAM-based boot using unchanged vendor bootloader and 26 MHz root clock, native UART and procfs/sysfs |
| F2 | AXP8191, R-I2C, regulator-backed MMC0, card enumerate, read-only ext4 |
| F3 | Copy-on-write test media persistence, then rootfs/systemd/network/SSH |
| F4 | USB, AIC8800 SDIO Wi-Fi with correct vendor driver and firmware |
| F5 | I²S, DMA, ALSA and real microphone PCM capture |
| F6 | GPU/NPU driver presence and measured workload support |
| F7 | Long uptime and multiple cold/warm boots without unexpected resets |

Do not enable real device nodes in a DTB until driver, supply, pinmux, interrupt and clock dependencies are reviewed. Especially do not blindly remove `vmmc-supply`, replace Boot0 or borrow bootloaders from Orange Pi 4 Pro. Other projects' hardware variant, RAM, U-Boot and GPU reports must not be assumed to match ours.

## Current blockers, not reasons to revert

- The full source tree currently has untracked A733 CCU, R-CCU, pinctrl and header additions. Preserve them in the source audit and reconstruct into a reviewable patch series before any release.
- RTC DCXO should ultimately use hardware detection, not a fixed 26 MHz board assumption.
- The existing CCU probe writes to 14 PLL control registers; audit these actions before a stable release.
- Procfs/sysfs were missing in the minimal kernel; this configuration enables them.
- Existing initramfs shell lacks controlling tty, has minimal commands, and `keep_bootcon` duplicates serial lines. These need separate test changes.
- The exact 2 GiB flashable disk control has not been pinned by SHA-256. Do not assemble from an arbitrary historical image.

## Promotion rule

Only label full integration **last known good** once the hardware boots, root filesystem and key interfaces function, no spurious resets occur across 10 cold boots + 10 warm boots and a 24-hour endurance run, and exact source/config/kernel/DTB/rootfs/firmware hashes are recorded.

## Build result and SD clock guard

Operator reports full kernel Image/modules build finished. Image SHA-256 `97c98f2cc6135e938c664936674936ece49a3257935395441f4ceacdb8fb406d`, `.config` SHA-256 `aaad20e5df200caae35dc8e58faaf6e843211d3a4b316ccf24bf55ebaf945351`, DTB SHA-256 `1ff786ed912df7d4b4d19e366b3c968a5e0552c39f58d61a8414514eba141d9d`. This original DTB keeps MMC0 disabled. `scripts/stage-25mhz-mmc-dtb.sh` creates a separate copy that retains 26 MHz root input and MMC0 disabled but adds `max-frequency=25000000` for subsequent integration. It does **not** prove a functional or measured SD bus; restore proper PMIC and vmmc supply before enabling MMC0. OCR mismatch remains unverified with corrected clocks. No SD image produced by this kernel build.

### Verified MMC staging result from Debian host

Operator ran `scripts/stage-25mhz-mmc-dtb.sh` successfully after pulling the branch. It reported the original corrected-clock DTB SHA-256 `1ff786ed912df7d4b4d19e366b3c968a5e0552c39f58d61a8414514eba141d9d` and distinct capped DTB SHA-256 `c3286ee33e46b0f2792b1cad47da5f4307660092e275ade5bdb762336f818ee0`, with `MMC0 remains DISABLED`. The script verified 26,000,000 Hz oscillator input, 25,000,000 Hz `max-frequency`, and disabled MMC0 status. **Actual MMC bus frequency and card OCR negotiation have not been tested.**

### MMC0 dependency audit from built DTB and config

Operator queried the 25 MHz capped DTB and the full kernel config:

```text
compatible: allwinner,sun60i-a733-mmc allwinner,sun20i-d1-mmc
status: disabled
max-frequency: 25000000
bus-width: absent
clocks: 2 141 2 140
clock-names: ahb mmc
resets: 2 34
pinctrl-0: 5
vmmc-supply: absent
vqmmc-supply: absent
CONFIG_I2C=y
CONFIG_MFD_AXP20X=y
CONFIG_REGULATOR=y
CONFIG_MMC=y
CONFIG_MMC_BLOCK=y
CONFIG_MMC_SUNXI=y
```

**Interpretation:** clock cap staged but no active MMC clock or card enumeration yet. DTB does not specify SD bus width, vmmc or vqmmc. MFD/REGULATOR generic frameworks alone do not prove AXP8191 bindings or correct voltage rail. Do not enable MMC until board pinctrl, card supply, and compatible PMIC/R-I2C wiring are grounded in proven vendor DTB and source. The primary concern is repeating `no support for card's volts`, which can arise from an empty host OCR mask; fixed clock rates alone do not resolve voltage negotiation.

### Correction: SD controller capability is up to 150 MHz

The 25 MHz cap documented above was an *initial conservative diagnostic speed*, **not** the vendor maximum. The A733 base device-tree reference by Andre Przywara specifies `max-frequency = <150000000>` for MMC0 (see https://gist.github.com/apritzel/60fd7379b9560a15b8b352986b69d39f). For the full integration branch, `scripts/stage-150mhz-mmc-dtb.sh` now produces a separate DTB with `max-frequency=150000000`, retaining the measured 26 MHz oscillator model and **leaving MMC0 disabled**. The script preserves the known-good DTB. 150 MHz is the controller's configured maximum, **not a guarantee of a 150 MHz card bus**. Linux sets the negotiated clock for the card's speed mode and signal voltage. At 3.3 V, conventional SD High Speed is nominally 50 MHz; faster UHS modes need correct 1.8 V switching, signal/pin timing, and controller support. The source's mainline `sunxi-mmc` compatibility and card voltage/OCR failures remain separately unverified on this particular full-build kernel. Do not treat the earlier 25 MHz as a permanent setting.

### SD/MMC controller roles and card-detect semantics

User-supplied baseline DTS for MMC0:

```dts
&mmc0 {
    bus-width = <4>;
    cd-gpios = <&pio 5 6 GPIO_ACTIVE_LOW>;
    no-sdio;
    no-mmc;
    max-frequency = <25000000>;
};
```

This **25 MHz setting is a conservative initial card-test value**, not the 150 MHz vendor MMC0 host ceiling. Other controller roles: sdmmc0 `0x04020000` removable microSD 150 MHz maximum; sdmmc1 `0x04021000` AIC8800 SDIO Wi-Fi 208 MHz reported maximum; sdmmc2 `0x04022000` optional eMMC, max not established.

`no-sdio` and `no-mmc` describe the removable SD memory-card slot protocol; **do not** apply `no-sdio` to Wi-Fi's MMC1. `&pio 5 6` addresses **PF6** and `GPIO_ACTIVE_LOW` is active-low card detection. Confirm this exact board routing and phandle before enabling; DDR/MMC0 pinmux group is PF0-PF5, separate from PF6. A November 2026 upstream Linux pinctrl correction describes PF6 interrupt/card-detect failures caused by `irq_read_needs_mux` on another A733 board: https://lists.openwall.net/linux-kernel/2026/11/10/2385 . Audit the A733 pinctrl driver's IRQ mux handling if removable-card events fail. Test 25 MHz initialization first and then negotiate higher card modes, measuring `actual clock` and signal voltage rather than assuming `max-frequency=150000000` means the card is running at 150 MHz.

Until regulator wiring is correct, keep both staged clock DTBs disabled; they are intermediate artifacts and not boot-ready storage configs.
