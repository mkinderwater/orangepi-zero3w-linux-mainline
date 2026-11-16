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
