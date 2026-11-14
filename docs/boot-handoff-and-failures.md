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
