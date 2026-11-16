# Boot0, U-Boot and ARM64 handoff: verified controls
Evidence cutoff 2026-11-15.

## Boot chain, vendor reference

Allwinner Zero 3W boots from board-sensitive Boot0/LPDDR initialization, a TOC/package containing U-Boot 2018 with monitor/SCP firmware, a distro boot script, a vendor `Image`/`uImage` and device tree, and then Linux. Do **not** replace Boot0/DRAM training with generic A733 binaries. Vendor build package enumerates `u-boot.fex`, `monitor.fex`, `scp.fex` and exposes distinct `boot0_sdcard_orangepizero3w.fex` variants. The `sys_config.fex` boot-debug UART declares PB9/PB10, **not** proof that the Linux UART pinmux uses them. A bundled `u-boot-current.dts` describes a T736 demo and is not authoritative Zero 3W board DTS.

Original stock 1.0.2 image has **one ext4 partition beginning at 32 MiB**, boot firmware in reserved earlier space. Separate `opi-3w-wbuild` 0.7.6 reference has FAT config beginning at 32 MiB and ext4 beginning at 96 MiB. Never conflate those disk layouts. The FAT CONFIG.TXT is a convenience for credentials, not established as a boot requirement.

## Script lineage and physical results

- Stock vendor second stage: import `orangepiEnv.txt`, construct root and console args, load `uInitrd` and `uImage`, load DTB, `fdt addr`, `fdt resize 65536`, apply overlays, `bootm`.
- A2P: untouched vendor script and normalized /boot allocation, HW PASS.
- A2V: exact vendor second-stage script loaded with first stage `ext4load mmc 0:1 0x46000000 /boot/mainline/stock-vendor-stage2.scr`; HW PASS.
- S1/S2: removal of FDT addr/resize or env import broke the tested boot; preserve both.
- VBN: vendor raw ARM64 Image via `booti ${kernel_addr_r} - ${fdt_addr_r}`, no fallback; board entered vendor Linux and panicked at VFS `unknown-block(0,0)`.
- VBI: vendor raw Image with vendor gzip initramfs via `booti ${kernel_addr_r} ${ramdisk_addr_r}:${opi3w_vendor_initrd_size} ${fdt_addr_r}`, HW PASS through Debian login.
- HBI-027: VBI-derived second stage changes kernel, DTB and initramfs payload paths to hybrid 0.2.7, but splash/solid LED and no 6.18 kernel proof.
- K2: HBI payload without initrd, did not restore boot.
- F1: vendor kernel + hybrid DTB + vendor initrd, boots userspace/USB Ethernet, despite frozen splash and HDMI driver failure.
- F2: hybrid kernel + vendor DTB, no initrd, does not reach proven Linux userspace, LED blinks once then off.

## Measured HBI-027 static layout

Verified original HBI assembler constants and finished-image audit:

| Region | Address range | Evidence |
| --- | --- | --- |
| Kernel raw Image | `0x41000000` to `0x418A0000` | Image file 8,591,368 B, header size 9,043,968 B, text offset 0 |
| First-stage original scriptaddr | `0x43100000` | Prior raw 41MiB experiments **overlapped** this; HBI 0.2.7 Image does not |
| Hybrid DTB plus FDT resize | `0x44000000` to `0x44039D49` | DTB 171,337 B, `fdt resize 65536` |
| Hybrid initramfs | `0x45000000` to `0x45042087` | 270,471 B; K2 omits it |
| Second-stage script | `0x46000000` to `0x46000B49` | A2V-derived script |
| Initrd -> script clearance | 16,506,745 B | No static overlap |

VBI and HBI firmware-prefix SHA256 both `10fe537251b4262236f54d729c258706ad41419c3411dd2201ffc57e4924a9b0`. Their `orangepiEnv.txt` hashes both `59c00b3ac7c4d5964ee7b3138a61060ab4d48d235a132f9b334444d308fcddab`. First stage hashes also identical. The three kernel/DTB/initrd file paths differ, not the underlying A2V control. Yet actual U-Boot memory relocation and environment values on failed HBI remain **unobserved**.

## F1 live firmware FDT: positive runtime evidence

Running `/sys/firmware/fdt` verified:

- Original DTB `/memory@40000000` reg = 512 MiB is changed to 1 GiB by U-Boot. Do not hardcode 1 GiB: multiple board RAM configurations exist.
- `/chosen/bootargs` becomes vendor arguments, root by UUID, `console=ttyS0`, `console=tty1`, loglevel 1.
- Relocated vendor initrd `0x493CC000..0x49FFF15B` (12,792,155 B).
- FDT reservations `0x43000000..0x43090000`, `0x493CC000..0x49FFF15B`, `0x73E02000..0x745EB000`.
- Display engine has added `sunxi-iova-premap` `0x73E02000` size `0x7E9000`.

Do not assume F1 runtime adjustments are necessarily the same for HBI, K2 or F2.

## Boot media allocation

The reference image's mounted-ext4 `/boot` normalization (after `mkfs.ext4 -d`, before final assembly) verifies SHA256 and symlinks, preallocates actual file data including zeros, preserves hardlinks/metadata, verifies again and runs fsck. Earlier image had 347 sparse 4KiB boot blocks; dense-file normalization was included in a successful image. Sparse holes implicated but not isolated from journal effects. Preserve source script in [opi-3w-wbuild](https://github.com/mkinderwater/opi-3w-wbuild) `scripts/boot_allocation.py` and boot-allocation audit. Do not confuse sparse outer `.img` with sparse internal ext4 files.

## Open requirements

Hardware U-Boot serial or an independently validated earliest kernel GPIO signal; read `printenv kernel_addr_r fdt_addr_r ramdisk_addr_r scriptaddr`; verify loaded artifact hashes and `fdt print` on hardware. E1 `pr_emerg` at `start_kernel()` was patch-prepared only, not compiled or tested; missing a log with an unproven UART cannot disprove execution.
