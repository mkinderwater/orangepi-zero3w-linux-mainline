# Zero 3W 6.6.98 roadmap and failure handling

1. Clone the repository branch and run `scripts/prepare.sh` on WSL ext4. Verify the source commit and kernel version; do not trust a moving branch.
2. Run `scripts/build.sh control` and `scripts/build.sh identity` separately. Control source is untouched. Identity changes just one root DTS identifier and retains `arm,sun60iw2p1`.
3. Save build manifests and binary checksums to Windows Downloads. Record compiler/toolchain version and build logs in test evidence.
4. Compare newly built Image and DTB to the stock vendor artifacts (hashes, config, dependencies and board identity). Binary identity is NOT guaranteed by pinning source: original vendor build flags/toolchain and modifications may differ.
5. Next separate project stage: create a fail-closed installer for the original stock image, preserving Boot0/U-Boot and original boot-script behavior. Do not create an installer until payload size, module version and early initrd compatibility checks pass.
6. On hardware, test untouched control first. Then flash only one modified DTS identity test. Record SSH, Wi-Fi, Linux HDMI console, USB, PMIC, MMC, reboot and logs. Do not call vendor 6.6.98 'validated' from compiler output alone.
7. Investigate AXP515, RTC and DDR warnings separately; do not change regulator voltages or remove RTC nodes based only on probe errors.
8. When a functional 6.6.98 board baseline passes, port one proven driver/DT subsystem at a time to 6.18, keeping the ARM64 handoff and HDMI tests independent.

## Important proven historical controls

- Original stock Orange Pi Debian 13 Linux 6.6.98 image with HDMI was bootable in prior tests.
- F1: vendor kernel + **hybrid 6.18 DTB** booted to user login/SSH and expanded root ext4, but Linux HDMI driver returned 'check point match is err or null'.
- The HDMI core in vendor BSP matches root `arm,sun60iw2p1`; the hybrid DTB removed it. Hence the proposed board-identity correction is a necessary targeted change, not proof of complete HDMI function.
- Frozen boot splash does not imply Linux has not booted.
- F1 live FDT received full 1GiB RAM from U-Boot, so do not hardcode memory to 1GiB.

## GNU Make 4.4.1 configuration remake loop (Nov 15, 2026)

On WSL Debian, GNU Make 4.4.1 with GCC 14.2.0, the pinned kernel's original multi-target Kconfig sync rule repeatedly emitted `SYNC include/config/auto.conf` and `GEN Makefile` without compiling. All four generated Kconfig files existed, and both host/target GCC reported 14.2.0. The old Makefile comments explicitly recommend grouped targets for GNU Make >= 4.3. The build script now applies an exact **single Kbuild rule** replacement to each disposable kernel worktree, keeping the original pin unmodified and recording `kbuild-make-compat.patch` in the outputs. This is a **candidate fix, not hardware/build tested**. Test control from the interrupted tree, record whether the sync loop disappears, then separately evaluate compilation errors. Do not confuse host-build compatibility changes with board DTS changes.

## Root-cause candidate from GNU Make dependency debug (Nov 15)

The grouped-target Makefile patch failed to stop the loop. The bounded debug trace explicitly reports `bsp/drivers/input/ctp/gt9xx_secondary//Kconfig` as nonexistent, then remakes `include/config/auto.conf` and restarts. The exact vendor source contains that malformed double-slash `source` reference in `bsp/drivers/input/ctp/Kconfig`, and the target file exists with a single slash. The build script now restores the upstream Makefile and repairs **only that source path**, in disposable worktrees, with an exact Git diff check. This correction is pending a WSL control-build test. If Make still restarts, retain debug logs and investigate the next Kconfig dependency rather than changing the kernel. The previous grouped-target patch has been withdrawn.

## Cedar VE codec Makefile missing from O= build (Nov 15, 2026)

The first genuine compilation failure after repairing the GT9xx Kconfig reference was `No rule to make target 'bsp/drivers/ve/cedar-ve/codec/Makefile'`. Both pinned kernel and disposable source worktree **contain and track** this file, and the build is not sparse. The video config has `CONFIG_AW_VIDEO_ENCODER_DECODER=m` with encoder and decoder enabled. The vendor `bsp/drivers/ve/cedar-ve/Makefile` incorrectly includes `$(src)/codec/Makefile` relative to the O= object directory. The official `scripts/Makefile.build` sets `src := $(obj)`. Therefore the build now patches that include to `$(srctree)/$(src)/codec/Makefile` in the disposable worktree only. The patch and exact diff are checked and retained as `ve-include-path.patch`. This is a **source-backed candidate fix, not yet compiled to completion**. Do not disable the codec or manufacture a placeholder Makefile.

## November 15: baseline test gates now implemented

Following **successful offline builds** of both `control` and `identity`, the repository added two **read-only** validation tools.

**WSL preflight (before any image assembly):**

```bash
cd /root/orangepi-zero3w-linux-mainline
python3 vendor-6.6.98/scripts/preflight.py
```

Checks SHA256SUMS, pinned source revision, mode and vendor fixes, exact *single source-line* board identity DTS patch, kernel-release files, FDT headers and distinct DTBs. It reports the kernel Image SHA mismatch without presuming it is harmless. A PASS means only that the compiled artifacts meet these offline checks. **Do not flash the Image or DTB directly or declare stock-image compatibility based on it.**

**On-board observational capture (only after a separately audited, booting test SD image exists):**

```bash
# On the Orange Pi, copy capture-on-board.sh onto the device, then:
bash capture-on-board.sh control
# Or: bash capture-on-board.sh identity
```

This writes read-only observations in `~/opi3w-hw-control` or `~/opi3w-hw-identity`, including `uname`, `findmnt`, `lsblk`, cpufreq policy, DRM connector state, `dmesg`, FDT and checksums. Set `OUT` to a fresh location when repeating. Manually annotate real HDMI Linux output, Wi-Fi connectivity and reboot/power-cycle results. Review all files for identifiers before sharing. Linux dmesg may not be readable without root or appropriate permissions, so read access must be checked.

**Critical remaining blocker:** This repository still has **no approved assembler** that installs the rebuilt kernel, matching modules and DTB into a clone of proven stock donor media while preserving Boot0, monitor/SCP, U-Boot, first/second-stage scripts, root layout and UUID. Do not improvise replacing `uImage` with raw `Image` or `bootm` with `booti` in a single uncontrolled change. Preserve ext4 `/boot` dense-allocation audit and flash one isolated control at a time. Hardware acceptance has **not** been performed.

**Parallel 6.18 source audit:**

```bash
cd /root/orangepi-zero3w-linux-mainline
python3 scripts/audit-hybrid-027-source.py
```

Compare `bsp/` exactly against pinned Allwinner BSP. Outputs in `/mnt/c/Users/mkinderwater/Downloads/opi3w-hybrid-027-source-audit` include `summary.md`, `audit.json`, `bsp-differences.txt` and `hybrid-top-level.patch`. The 6.18 hybrid is **not** yet reproduced from Git until imported BSP changes, build config, source transformation, module stage and image assembly are audited and preserved.

Test as **two independent controlled cases**, not two unreviewed edits in one image. First test the unmodified vendor DTS with the new build; then separately test the corrected board-compatible property, keeping firmware, kernel payload, modules, root filesystem, root UUID and boot commands demonstrably constant. Because the two kernel Image SHA256 values currently differ, investigate them before asserting that the second case is a DTB-only experiment.
