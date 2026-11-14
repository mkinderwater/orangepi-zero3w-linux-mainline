# Orange Pi Zero 3W: Linux 6.6.98 kernel panic in raw `booti` test (M2da)

**Hardware observation: 2026-11-14 | Board: Orange Pi Zero 3W | SoC: Allwinner A733 (sun60iw2) | Status: reproducible observation from one reported M2da test, not an upstream Linux 6.18 boot.**

## Problem and searchable symptoms

A Linux 6.18.19 experiment on the **Orange Pi Zero 3W** repeatedly remained at the HDMI message **"Orange Pi, initializing boot loader"**. A working Debian 13/vendor Linux **6.6.98-sun60iw2** control image booted to a login screen. To isolate the bootloader handoff from experimental early A733 drivers, we tested the vendor kernel in a raw ARM64 Image / U-Boot `booti` experiment (M2da).

The M2da **BOOTI-RAW-INITRD** image reached a visible Linux 6.6.98 kernel panic:

```text
[    3.792147] Kernel panic - not syncing: VFS: Unable to mount root fs on unknown-block(0,0)
[    3.801436] CPU: 7 PID: 1 Comm: swapper/0 Not tainted 6.6.98-sun60iw2 #1.0.2
[    3.809358] Hardware name: sun60iw2 (DT)
[    3.813785] Call trace:
...
[    3.835781] mount_root_generic+0x24c/0x320
[    3.840511] mount_root+0x190/0x25c
[    3.844554] prepare_namespace+0x6c/0x238
[    3.848989] kernel_init_freeable+0x24c/0x294
...
[    3.879784] ---[ end Kernel panic - not syncing: VFS: Unable to mount root fs on unknown-block(0,0) ]---
```

Transcribed from a **photograph of the attached monitor**, not a saved serial/dmesg capture. A complete early boot log is not available. Timestamp and wording are from that observed screen.

### What this proves

- An ARM64 Linux **6.6.98 vendor kernel** actually executed on the M2da card, initialized a visible console, and reached the VFS root-mount attempt after approximately 3.8 seconds.
- The board, HDMI output and vendor kernel can progress far beyond the U-Boot splash in this experimental image family.
- `unknown-block(0,0)` means the kernel did **not obtain a usable root block device** at mount time. It does **not by itself** distinguish a missing/malformed initramfs, wrong `root=`, storage enumeration or driver failure.

### What this does NOT prove

- **Do not claim `booti` is conclusively proven solely from the panic photo.** M2da was described as retaining a vendor `bootm` fallback if `booti` returns. Without a captured U-Boot command trace or an image that unambiguously disables fallback, the observed vendor-kernel panic may be from `booti` or from fallback `bootm`. Inspect the *finished* M2da boot script and control flow before making a definitive claim.
- It does **not** show Linux **6.18.19** entering the kernel or producing any printk.
- It does **not** establish whether a ramdisk was recognized, whether MMC initialized, or whether the vendor DTB received the correct RAM fixups.
- A retained splash is simply the last HDMI frame; it does **not** by itself localize a U-Boot, kernel-entry or early-console failure.

## Hardware test matrix

| Test | Kernel / method | Observed HDMI | Evidence |
| --- | --- | --- | --- |
| M2cv CONTROL | Vendor 6.6.98, `bootm` | Debian login screen | Hardware pass |
| M2cv DIAG | Linux 6.18.19, raw `booti` plus diagnostic initramfs | "Orange Pi, initializing boot loader" | No confirmed Linux entry |
| M2cv DIRECT | Linux 6.18.19, raw `booti` without initramfs | Same bootloader splash | No confirmed Linux entry |
| M2cx DIRECT | Linux 6.18.19, corrected 24 MHz oscillator and UART0 pinctrl | Same bootloader splash | DT corrections not sufficient |
| M2da BOOTI-RAW-INITRD | Vendor 6.6.98 in raw-`booti` experiment | Linux VFS kernel panic at ~3.8 s | **Vendor Linux executes; actual handoff branch still requires verification** |
| M2da BOOTI-DIRECT | Vendor 6.6.98 without initramfs | Not reported | No result claimed |

## Bootloader and image context

- Hardware: **Allwinner A733 / sun60iw2**; bootloader is vendor **U-Boot 2018.07**.
- Known working control: `opi-3w-wbuild` v0.7.6, `boot.scr` -> vendor `uImage` and `uInitrd` -> `bootm`.
- Two-stage M2cv boot-script layout: tiny first-stage script executed at vendor `scriptaddr=0x43100000`, second-stage script moved to `0x46000000` before loading the larger Linux 6.18.19 raw Image.
- Linux 6.18.19 candidate raw Image: **41,064,960 bytes**, staged at `0x41000000`; ARM64 header declared **41,877,504 bytes**, ending at `0x437F0000`. Experimental DTB staged at `0x44000000`. These ranges do not directly overlap.
- The original direct-load script location `0x43100000` *was* inside the 6.18.19 file-load interval. The two-stage arrangement removes the obvious execution-address overlap; it was not sufficient to boot experimental Linux.
- M2cx fixed two actual board-DTB omissions: `/osc-clk/clock-frequency = <24000000>` (verified against the vendor CCU 24 MHz `hosc` input), and `&uart0` pinctrl pointing at `uart0_pb_pins` (PB9/PB10). Both properties were verified in the compiled DTB. M2cx still showed the same splash.
- Finished-image audit M2cy found the expected root filesystem command-line construction; an earlier suspicion that `root=` was missing was **not supported**.

## Working-reference comparison

A separate project reports booting a hybrid Linux 6.18.19 kernel on Orange Pi Zero 3W:

- [nickyg666/orangepi-zero3w-mainline](https://github.com/nickyg666/orangepi-zero3w-mainline)
- [Working-reference boot script](https://github.com/nickyg666/orangepi-zero3w-mainline/blob/main/reference/boot.cmd)
- [Early-driver and root-mount history](https://github.com/nickyg666/orangepi-zero3w-mainline/blob/main/AGENTS.md)

That reference uses the vendor-derived **UART-NG, A733 clock/pinctrl, TWI/I2C and PMIC** stack in a Linux 6.18 hybrid, with an approximately 26 MB raw Image. Our experimental build instead uses upstream-oriented clock/pinctrl, `i2c-mv64xxx`, an experimental limited AXP8191 regulator provider, and a ~41 MB raw Image. Our relevant drivers **are present in System.map**, but their actual runtime functionality is not proven. Configuration differences are investigative leads, **not demonstrated root causes**.

## Next decisive checks

1. **Audit the finished M2da `boot.scr` and U-Boot control flow.** Determine whether `booti` could have returned and launched vendor `bootm`; explicitly prevent fallback in a subsequent *isolated* test if the final script shows ambiguity.
2. **Collect early U-Boot output** (3.3V UART if available), or use a uniquely observable diagnostic marker that cannot be reached on the fallback branch. Only then promote the result to confirmed raw `booti` execution.
3. Keep vendor boot success as the control and investigate Linux 6.18.19 entry/early platform initialization separately. Avoid attributing the silent 6.18 screen to I2C/MMC until kernel execution is demonstrated.
4. For the M2da VFS panic itself, inspect effective `bootargs`, actual ramdisk header and U-Boot ramdisk handling, and whether the kernel enumerates a microSD root block device. Do not infer missing `root=` without extracting the actual finished script.
5. Preserve the **original working recovery microSD**. Use a separate experimental card; there is no guaranteed one-shot fallback after Linux starts.

## Related evidence

- [Bootloader layout and prior failures](boot-handoff-and-failures.md)
- [Earlier initramfs root-discovery bug](m2cr-initramfs-root-discovery.md)
- [Working vendor Debian 13 image builder](https://github.com/mkinderwater/opi-3w-wbuild)

**Search terms:** Orange Pi Zero 3W mainline boot, Allwinner A733, sun60iw2, U-Boot 2018.07, `booti` versus `bootm`, `VFS: Unable to mount root fs on unknown-block(0,0)`, Linux 6.6.98-sun60iw2, Linux 6.18.19, ARM64 raw Image, initramfs, sunxi MMC, AXP8191, "initializing boot loader".
