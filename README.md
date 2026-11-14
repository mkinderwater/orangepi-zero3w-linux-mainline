# Orange Pi Zero 3W: upstream-oriented Linux bring-up

**Status: experimental source and compile evidence, NOT a bootable release.**

Board: Orange Pi Zero 3W, Allwinner A733 (1 GB tested with the separate vendor image project).
Target: Linux 6.18.19, upstream-oriented drivers, native DRM HDMI, PowerVR GPU with unmodified Mesa.

## Verified

- The [vendor-kernel Debian 13 image builder](https://github.com/mkinderwater/opi-3w-wbuild) produced a working image, including hardware-tested Wi-Fi, SSH and GPU compute.
- Linux 6.18.19 and an experimental Zero 3W board DTB compiled in M2ca and M2cb. The M2cb result recorded `KERNEL=0` and `DTB=0`.
- An experimental AXP8191 MFD/regulator driver registers DCDC1, CLDO5 and DC1SW2. Its regmap permits writes only to verified low-bank addresses. **No rail-state safety validation on hardware has been done.**
- The 0.7.6 reference boot path is `boot.scr` -> `uImage` + `uInitrd` + `dtb/allwinner/sun60i-a733-orangepi-zero3w.dtb` -> `bootm`.
- The vendor image's boot-file normalization was tested on hardware. See [boot investigation](docs/boot-allocation.md).

## Not yet established

- Linux 6.18.19 successfully booting on the Zero 3W.
- Regulator startup behavior, 1.8V switching or reliable MMC access under Linux 6.18.19.
- HDMI scanout, registered functional DRM/KMS, accelerated PowerVR on mainline or stock Mesa on this board.
- A reproducible *standalone* kernel build directly from this starter archive. Additional A733 CCU, pinctrl, UART, R-I2C, MMC changes from the WSL worktrees must be exported and reviewed.

## Included

- `dts/`: exact M2ca board DTS snapshot (build-tested, not hardware-tested).
- `patches/experimental/`: M2cb PMIC diff as captured against a local kernel worktree. It may require preceding platform changes; **do not assume clean upstream apply**.
- `config/`: earlier M2av kernel configuration snapshot, **not** guaranteed to match the final M2cb configuration.
- `scripts/export-from-wsl.sh`: exports current WSL kernel tree state and manifest into a separate review directory without including vendor sources or binaries.
- `docs/`: hardware, bootloader, test results, blockers and publication criteria.

## Reproduce the next source review

On the original Debian WSL host:

```bash
bash scripts/export-from-wsl.sh /root/opi3w-m2-work /root/opi3w-mainline-source-review
```

Inspect the generated diff and file manifest. Integrate only audited kernel changes, remove absolute host paths and confirm the exact kernel commit and build config. Never flash a candidate solely because it compiles.

## Current next milestone

Build a self-contained, reviewable kernel patch set; preserve the vendor 0.7.6 image as control; make a separate boot test image using the [proven boot-file allocation normalization](https://github.com/mkinderwater/opi-3w-wbuild/blob/main/scripts/boot_allocation.py); obtain hard evidence of successful kernel boot before promoting the release.

See [project limits](docs/status-and-limits.md) and [release checklist](docs/release-checklist.md).
