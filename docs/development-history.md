# Development record and current acceptance gates

| Stage | Key result | Evidence quality |
| --- | --- | --- |
| M2o | Draft Zero 3W DTB, initial MMC disabled | DTB compiled, not boot-ready |
| M2r | Limited AXP8191 regulator provider for DCDC1, CLDO5, DC1SW2 | Local source/build |
| M2bp-M2bx | Established board/MMC/PMIC supply map from vendor DTS | Static evidence |
| M2by | Four PMIC files integrated; board label error | Failed build |
| M2bz, M2ca | DTB and kernel compiled; R-I2C0 pinctrl PL0/PL1 corrected | Compile pass |
| M2cb | AXP8191 writable register list tightened to five | Compile and static verification |
| M2cf | Inspected 0.7.6 `boot.cmd`, env, partition layout and dense-file audit | Image inspection |
| M2cg | Reproduced kernel header format; resolved three WSL script bugs | Packaging pass, not boot test |
| M2ch | Installed 1,426 matching ARM64 `.ko` files; built-in MMC/ext4/PMIC checks | Installation pass |
| M2ci | Direct-root and matching-initramfs candidates generated separately | Offline preparation |
| M2ck | `CONFIG_I2C_MV64XXX=y`, compatible fallbacks already present; correct `m2by` DTB target built | Compile pass |
| M2cl | Built unarmed dual-path image, preserved boot area/UUID, passed ext4 normalization | Image assembly pass |
| M2cm | Added userspace marker, 11 PMIC checks, verified unarmed vendor boot through HDMI/Wi-Fi/SSH | **Physical vendor branch pass**, 6.18 untested |

## Acceptance gates to the first mainline boot

1. Reconstruct exact clean patch series from WSL changes against specified Linux upstream commit; clean cross-compile outside existing worktree.
2. Verify the R-I2C0/AXP8191 probe path and actual regulator-core behavior on real hardware; preserve safe rail limits.
3. Validate raw ARM64 `Image` / `booti` kernel entry on a spare card with a recovery procedure. Do not depend on vendor HDMI under Linux 6.18.
4. Prove MMC0 enumerates, root mounts, systemd starts, and an observable diagnostic marker or serial console confirms kernel version `6.18.19`.
5. Implement native display scanout; measure EDID/HPD, KMS connectors/planes and modesetting; then test PowerVR against **unmodified Mesa**. Vendor GPU compute alone is not mainline GPU validation.

No release tag should imply Linux 6.18 hardware boot. Experimental kernel branches must remain explicitly labeled.
