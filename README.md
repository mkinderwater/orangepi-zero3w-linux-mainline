> **CURRENT ENGINEERING STATUS (UART verified November 2026):** Our hybrid Linux **6.18.19-opi3w-hybrid-0.2.7 physically entered PID1** on the 1 GiB Orange Pi Zero 3W. The same boot recorded an MMC UHS-II null callback Oops caused by an incompatible vendor CAP2 bit-9 definition and a separate PF voltage-switching panic. **This is a kernel/PID1 hardware execution PASS, not a stable root or product boot.** The older history below is dated and retained. See the [complete trial reconciliation](docs/2026-11-17-full-history-after-uart-mmc-panic.md).

> **DEPLOYMENT DIRECTION:** [Package-managed, low-vendor-lock-in Debian ARM64 architecture](docs/2026-11-17-upgradeable-low-vendor-lock-in-deployment.md). Use upstream Linux LTS, tracked small A733 patches, versioned kernel/DTB/modules packages and staged reversible kernel slots. Preserve the known-good boot firmware until upstream replacements are physically validated. **No automatic rollback or distributable 6.18 image exists yet.**

> **Independent project comparison:** [What counterparts report versus what we measured](docs/2026-11-15-counterpart-evidence-review.md). Another Zero 3W developer documents a successful **hybrid** Linux 6.18.19 boot, Wi-Fi and GPU. Those are **their reported hardware results**, not our own. Our hybrid 6.18 kernel is still not confirmed executing on our board. A separate A733 project lists Zero 3W as *Platform Ready*, not *Fully Validated*.

> **Current development records (Nov 15, 2026):** The original 2026-11-14 statements below reflect the M2 stage. For the newer VBI/HBI/K2/F1/F2 hardware evidence, the verified 6.6.98 control and identity builds, all source pins and bootloader/PMIC/HDMI investigations, start at **[2026-11-15 engineering index](docs/2026-11-15-engineering-index.md)**. This repository still does **not** contain a hardware-booted Linux 6.18 kernel. The two rebuilt vendor 6.6.98 variants have compiled but have not been hardware tested. Use [WSL inventory script](scripts/audit-wsl-resource-inventory.sh) to identify remaining local artifacts that require a tracked export. Do not infer 6.18 kernel failure from the frozen HDMI splash; F1 booted with that symptom.

# Orange Pi Zero 3W: upstream-oriented Linux bring-up

**Status: experimental source and compile evidence, NOT a bootable release.**

Board: Orange Pi Zero 3W, Allwinner A733 (1 GB tested with the separate vendor image project).
Target: Linux 6.18.19, upstream-oriented drivers, native DRM HDMI, PowerVR GPU with unmodified Mesa.

## Latest hardware findings (2026-11-14)

**Linux 6.18.19 still has no confirmed hardware boot.** M2cv CONTROL (vendor Linux 6.6.98) reached Debian login, while M2cv DIAG, M2cv DIRECT and M2cx DIRECT remained at the Orange Pi "initializing boot loader" splash. The M2cx DTB corrections (24 MHz root oscillator and UART0 PB9/PB10 pinctrl) are build-verified but did not change the hardware outcome.

**M2da vendor-kernel handoff experiment:** the vendor 6.6.98 kernel produced a photographed Linux VFS panic at ~3.8 s: `VFS: Unable to mount root fs on unknown-block(0,0)`. This proves vendor Linux executes in that test image, but a retained vendor `bootm` fallback means it does not conclusively prove that `booti` was responsible. See the [searchable M2da boot/panic investigation](docs/orange-pi-zero-3w-uboot-booti-kernel-panic-m2da.md) and [bootloader history](docs/boot-handoff-and-failures.md).

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
