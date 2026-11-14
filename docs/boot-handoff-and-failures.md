# Bootloader, image layout and failures

## Hardware control image

- Reference: [opi-3w-wbuild 0.7.6](https://github.com/mkinderwater/opi-3w-wbuild/releases/tag/0.7.6), bootloader/reserved first 32 MiB, FAT partition starting at 32 MiB, ext4 root starting at 96 MiB (LBA 196608).
- Vendor script imports `orangepiEnv.txt`; loads `/boot/uInitrd`, `/boot/uImage`, and DTB from `/boot/dtb/allwinner/sun60i-a733-orangepi-zero3w.dtb`; invokes `bootm`.
- Legacy vendor uImage uses load and entry `0x41000000`, uncompressed ARM image header, payload equal to vendor `vmlinux` bytes. Header compatibility does not prove 6.18 boot.
- An independent Zero 3W developer reported that the older 32-bit vendor U-Boot rejects a conventional `IH_ARCH_ARM64` legacy header through `bootm`. Their functional experimental handoff uses a *raw* ARM64 `Image` and `booti` with a suitable legacy-wrapped initramfs. Our M2cl image includes the raw-image branch but it is **not hardware-tested**.

## Boot allocation incident

A 0.7.0 image stopped at the Orange Pi splash despite matching file hashes and matching reserved boot bytes. Compared with working 0.5.0, the failed kernel had 347 sparse 4KiB blocks and substantially more extents. The established repair mounts the newly created ext4 filesystem, rewrites and preallocates every regular `/boot` file, checks for holes, preserves metadata and links, then unmounts and runs fsck. The working diagnostic image booted with Wi-Fi, SSH and compute tests. Because normalization also initializes journal state and a mount-only control has no reported board result, sparse holes are **strongly implicated, not proved the sole cause**. Outer `.img` sparsity is unrelated.

## Build and investigation failures

| Stage | Finding / correction |
| --- | --- |
| M2by | `r_i2c0_pins` label missing; correct reference `&r_i2c0_pl_pins` |
| M2bz / M2ca | Corrected R-I2C pinctrl, PMIC and board DTS built |
| M2cg | Missing `mkimage`; installed `u-boot-tools` |
| M2cg | `find | head` with `pipefail` returned 141; saved full file first |
| M2cg | WSL loop partition lookup failed; use explicit readonly offset for ref image |
| M2ch | `INSTALL_MOD_STRIP=0` triggers stripping using host tool; use `INSTALL_MOD_STRIP=` |
| M2ck | Wrong DTB target `m2ca`; registered Makefile target is `m2by` |
| M2cl / M2cm | Offline image assembly passes, unarmed vendor control booted on board |

## Repeated test requirements

Two independent hypotheses per batch, retain both outcomes. Do not infer cause from one marker. `BOOT-STATUS.TXT=BUILD-ONLY` does not separate bootloader, kernel, initramfs, systemd or mount failures. The M2cm systemd marker can prove successful experimental userspace if written but its absence says nothing about early execution. A static `armed` marker does not provide one-shot fallback if Linux crashes before clearing it. Use a spare card.

## M2ct/M2cv: U-Boot script address overlaps the experimental kernel (2026-11-14)

**Evidence status: address overlap confirmed, root cause not hardware-proven.** Linux 6.18.19 has not yet produced a verified boot log on this board.

### Hardware observations

| Image | HDMI observation | Linux 6.18 proof |
| --- | --- | --- |
| M2cm UNARMED | Vendor 6.6.98 booted with HDMI login, Wi-Fi and SSH | Vendor control only |
| M2cp direct-root | Orange Pi logo and "initializing boot loader" | None |
| M2cr diagnostic | Same logo and text | Diagnostic files absent |
| M2ct LEGACY | Orange Pi logo only | Diagnostic files absent |
| M2ct RAW | Orange Pi logo only | Diagnostic files absent |

The retained splash screen cannot prove the stage of failure. The diagnostic initramfs writes its files only after finding and mounting the microSD root.

### The image-normalization question was answered

M2cs inspected the **finished M2cr ext4 image**, comparing all 121 regular boot files against 121 embedded allocation records. **No sparse holes were found.** The image used the existing mounted-ext4 normalization from [opi-3w-wbuild](https://github.com/mkinderwater/opi-3w-wbuild/blob/main/scripts/boot_allocation.py). The audited kernel was 41,064,960 bytes; the Zero 3W DTB 12,038 bytes; tiny legacy-wrapped initramfs 1,016,749 bytes; boot.scr 3,472 bytes. The persistent armed marker was present. This supports excluding the earlier sparse-boot-file failure in the audited image, not excluding physical SD write errors.

### Vendor U-Boot memory addresses

The archived hardware bundle contains boot-prefix.bin. String inspection of that bootloader identified U-Boot 2018.07-orangepi-config-dirty and defaults:

| Address | Purpose |
| --- | --- |
| 0x41000000 | Kernel staging |
| 0x43000000 | Default DTB staging |
| 0x43100000 | scriptaddr, boot script loading/execution |
| 0x43300000 | Default ramdisk staging |

The vendor's distro boot command loads boot.scr at **scriptaddr** and then calls **source scriptaddr**. The experimental raw kernel loads from 0x41000000 and its 41,064,960 bytes occupy **[0x41000000, 0x43729A00)**. Thus 0x43100000, the script address, is inside the experimental kernel load range.

**This proves an address overlap, not yet that U-Boot actually loses required script memory or that this caused the observed boot failure.** U-Boot's nested source/copy semantics have not been verified on hardware.

### Why M2ct did not resolve the potential conflict

Both finished M2ct boot scripts were decoded and checked. They set kernel=0x41000000, DTB=0x44000000, ramdisk=0x45000000, load_addr=0x46000000. But these are assigned **inside the boot script already executing from 0x43100000**. Changing load_addr does not move that script. Both images share this issue. The LEGACY variant used a small legacy-wrapped initramfs with a compression header marked none; RAW used a gzip initramfs and address:size argument. Neither generated persistent logs.

The M2cr diagnostic initramfs separately called an absent BusyBox blkid applet. The source was corrected to use findfs by UUID. A later M2ct validation false positive came from extracting ./init instead of init from the CPIO archive. See [M2cr root discovery](m2cr-initramfs-root-discovery.md). These bugs do not account for M2cp, which used no initramfs.

### M2cv: isolated two-stage test

The proposed M2cv images use a **tiny first-stage script** at the vendor script address. It loads and invokes a **full second-stage script at 0x46000000 before loading the 40 MiB kernel**. The first stage must not load the experimental kernel. Verify that nested U-Boot source execution is safe, including any return to a first-stage script whose bytes may be overwritten.

1. **CONTROL:** unarmed two-stage script with vendor kernel 6.6.98. Require HDMI, Wi-Fi and SSH success first.
2. **DIAG:** same layout with ARM64 6.18.19 raw Image, corrected minimal initramfs and root-by-UUID diagnostics.
3. **DIRECT:** same layout with raw Image, no initramfs.

Keep the exact bootloader, original vendor recovery image, 96 MiB root partition start, MMC/PMIC DTB and kernel inputs, and ext4 boot-file normalization constant. Do not change PowerVR or HDMI code in this test. Use disposable microSD media. The fallback path only runs if U-Boot regains control; an armed marker is not automatic one-shot recovery.

**As of this documentation update M2cv has been packaged but not hardware-tested.** No Linux 6.18.19 boot success is claimed.

External references: [Zero 3W working boot script](https://github.com/nickyg666/orangepi-zero3w-mainline/blob/main/reference/boot.cmd), [Zero 3W bring-up notes](https://github.com/nickyg666/orangepi-zero3w-mainline/blob/main/AGENTS.md), [Jonas A733 boot guide](https://github.com/jonas5/Allwinner-A733-kernel/blob/main/A733_BOOT_FIX.md).
