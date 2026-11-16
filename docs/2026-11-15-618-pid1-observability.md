# Linux 6.18: root-independent PID1 diagnostic

The HBI-027 initramfs is correctly packaged, but its FAT checkpoint expects partition 2 while HBI uses a single ext4 partition. Missing FAT markers are therefore inconclusive.

This C probe starts as PID1 without root discovery, FAT or MMC. It writes START/UNAME/HOLD and repeating ALIVE to /dev/console, /dev/kmsg and /dev/ttyS0 when accessible. It deliberately never exits, mounts the SD root, writes storage, or invokes switch_root. Its output is only proof of PID1 when captured on a validated console or UART.

## Build on Debian WSL

    apt install -y gcc-aarch64-linux-gnu binutils-aarch64-linux-gnu cpio
    cd /root/orangepi-zero3w-linux-mainline
    bash diagnostics/build-pid1-probe.sh /root/opi3w-m2-work/618-pid1-probe

This emits a gzip CPIO file, not a bootable image. Before installing into a disposable HBI-derived image, verify the exact U-Boot size/load and relocation, source/hashes, filesystem normalization and independent control. Do not change kernel, DTB, firmware, boot arguments or vendor FDT/env handling in the same experiment.

**Important:** Neither the published boot-firmware PB9/PB10 setting nor the splash establishes working Linux UART. First validate serial with vendor VBI on actual hardware. If no serial/GPIO signal is proven, absence of these markers remains inconclusive. A PID1 marker is not an earliest kernel-entry marker: Linux can fail before executing /init.

Status: SOURCE ONLY; no WSL compile, image assembly or hardware result yet.
