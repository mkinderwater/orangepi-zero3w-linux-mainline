# Orange Pi Zero 3W: reproducible vendor Linux 6.6.98 baseline

Status: **workflow published, no new kernel compiled or flashed**.

## Pinned sources

- Kernel: `orangepi-xunlong/linux-orangepi@2ac08e8c7cdc28abbdc5c9a9dd812f887ae9c79f`, Makefile declares 6.6.98.
- Build definitions: `orangepi-xunlong/orangepi-build@7f24222b928eab94780f2af03289ce527e07241e`.
- Board: `external/config/boards/orangepizero3w.conf`.
- Config: `external/config/kernel/linux-sun60iw2-current-a733.config`.
- DTS: `arch/arm64/boot/dts/allwinner/sun60i-a733-orangepi-zero3w.dts`.

Vendor Zero 3W DTS surprisingly has `compatible = "xunlong,orangepi-4-pro", "arm,sun60iw2p1";`. The **only candidate correction** changes the first identifier to `xunlong,orangepi-zero3w`, while retaining `arm,sun60iw2p1`. The latter is necessary for vendor HDMI platform selection.

## WSL commands

```bash
git clone https://github.com/mkinderwater/orangepi-zero3w-linux-mainline.git
cd orangepi-zero3w-linux-mainline
git switch work/zero3w-vendor-6.6.98-baseline
bash vendor-6.6.98/scripts/prepare.sh
bash vendor-6.6.98/scripts/build.sh control
bash vendor-6.6.98/scripts/build.sh identity
```

Needs git, curl, make, Python 3, `aarch64-linux-gnu-gcc` and standard kernel build dependencies. The scripts fail closed on unexpected source revisions, DT changes and Kconfig mismatches. Build may need additional BSP dependencies; do not silently patch around compiler errors.

Output directory: `/mnt/c/Users/mkinderwater/Downloads/opi3w-vendor-6698-results`; build trees stay on WSL ext4 at `/root/opi3w-vendor-6698-work`.

**control** compiles unchanged vendor kernel source and DTB; **identity** compiles a separate worktree with one property change. Neither creates a flash image.

## Hardware evidence and limits

- Stock vendor 6.6.98 image booted with HDMI, Wi-Fi, and SSH.
- F1: vendor 6.6.98 kernel plus earlier hybrid DTB boots Debian, resizes ext4 and supports SSH over USB-C Ethernet, but Linux HDMI fails.
- HBI-027, K2, F2: 6.18 boot still unproven. Frozen splash can persist on a successfully booted kernel.
- F1 live FDT: vendor U-Boot fixed RAM declaration from 512 MiB to 1 GiB.
- F1 AXP8191/MMC working, AXP515 I2C errors unresolved.

See [acceptance](docs/acceptance.md) and [provenance](docs/provenance.md). Before flashing a newly built kernel: compare artifacts to stock, retain proven boot firmware and write a single-change test-image builder with a finished-image manifest.

Do not commit SD/card images, stock firmware binaries, credentials, machine IDs or non-redacted logs. Capture local SHA256 checksums and redacted evidence instead.
