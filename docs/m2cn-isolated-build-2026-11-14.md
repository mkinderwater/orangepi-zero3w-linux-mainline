# M2cn: isolated source reconstruction and build

Date: 2026-11-14. Target: Orange Pi Zero 3W (Allwinner A733), Linux 6.18.19 experimental.

## Result

M2cn completed with exit code 0. The script reconstructed the development kernel source in a separate checkout, then compiled an ARM64 `Image` and `sun60i-a733-orangepi-zero3w-m2by.dtb` with `JOBS=4`. Its source baseline was `908869c38e30ef03066387543f3ecf0212d15200`. This is an **isolated reconstruction test**, **not** a successful build solely from the files currently published in this repository, and not proof of physical Linux 6.18 boot.

| Check | Evidence |
| --- | --- |
| Isolated kernel and DTB | `run.log`, `isolated-build.log` |
| DTB SHA-256 | `577f128db2e67a7208451413bdd36b5280253e2e98d23382aa4a3bc8568243e2` |
| Isolated Image SHA-256 | `59877d59304bad5dc46f61e7f881eea5f4c8433248be4de1f4ce0dd1e2f5faf5` |
| Previous Image SHA-256 | `fbce9a31719eb2c140c240b2800531dfe4ba6e1dc9a69f29f7cdcce9614a5127` |

The DTB hash matched the preceding build. The Image hashes differed. We have not isolated why; possible differences in build metadata are a hypothesis, not a confirmed explanation.

## Reproducibility caveat

The script copied **841 untracked source candidates** into the reconstruction; **16 other entries were held for review**. These files include experimental DRM and vendor-derived material. The existing source patch and copied-untracked list need provenance and scope review before publication. In particular, do not blindly commit the raw M2cn patch or the copied vendor display sources. See `evidence/m2cn/` for sanitized audit logs and path inventories.

Verified built-in dependencies in `build-m2aa/.config`: `CONFIG_I2C_MV64XXX=y`, `CONFIG_MFD_AXP20X=y`, `CONFIG_MFD_AXP20X_I2C=y`, `CONFIG_REGULATOR_AXP20X=y`, `CONFIG_MMC_SUNXI=y`, `CONFIG_EXT4_FS=y`. These establish build configuration, not on-board probing.

## Boot status

The separate **M2cm unarmed control** booted the vendor kernel `6.6.98-sun60iw2` on the physical Zero 3W, with HDMI login, Wi-Fi (`wlan0`), and active SSH. The experimental 6.18.19 kernel has **not** been hardware-booted. The experimental raw ARM64 `Image` with `booti` remains a candidate; a boot-armed marker is not a one-shot recovery mechanism.

The 0.7.6 image's root partition starts at 96 MiB. The image builder's mounted-ext4 `/boot` normalization is mandatory. It produced hardware success, but its allocation and journal effects have not been isolated into a single root cause.

## Next acceptance steps

1. Publish a reviewed minimal patch series against a pinned upstream revision, without temporary DRM audit modules or copied vendor sources.
2. Demonstrate a fresh checkout applying only those published patches and compiling without dependence on extra local files.
3. Prepare a separate experimental image with the proven 0.7.6 filesystem assembly process, matching kernel modules, and a verified recovery plan.
4. Test Linux 6.18 kernel entry and subsequent boot stages on hardware. Do not call HDMI or PowerVR functional until tested.
