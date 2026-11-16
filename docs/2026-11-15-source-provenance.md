# Source provenance: pinned revisions and external resources

## Primary source pins

| Role | Source | Pinned revision / status |
| --- | --- | --- |
| Stock vendor 6.6.98 kernel | [orangepi-xunlong/linux-orangepi](https://github.com/orangepi-xunlong/linux-orangepi) `orange-pi-6.6-sun60iw2` | `2ac08e8c7cdc28abbdc5c9a9dd812f887ae9c79f` verified `Makefile` = 6.6.98 |
| Orange Pi build framework | [orangepi-xunlong/orangepi-build](https://github.com/orangepi-xunlong/orangepi-build) `next` | `7f24222b928eab94780f2af03289ce527e07241e` |
| Linux mainline target 6.18.19 | [kernel.org Linux](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git) | Existing hybrid pinned `4aea1dc4cad17cd146072e13b1fd404f32b8b3ef`; verify source tag/commit in host checkout |
| Allwinner BSP modules for 6.18 hybrid | [alexcaoys/allwinner-bsp](https://github.com/alexcaoys/allwinner-bsp) | `656a550c826787e7e72fae58ca793df9e0988ac8` |
| A733 engineering reference | [jonas5/Allwinner-A733-kernel](https://github.com/jonas5/Allwinner-A733-kernel) | `fc71840a8b5bb17a73ed42cc00e46838a97c8aa1` |
| Vendor 6.6.98 DTS reference | [vendor Zero 3W DTS](https://github.com/orangepi-xunlong/linux-orangepi/blob/2ac08e8c7cdc28abbdc5c9a9dd812f887ae9c79f/arch/arm64/boot/dts/allwinner/sun60i-a733-orangepi-zero3w.dts) | Same pinned vendor commit |
| Independent 6.18 bring-up report | [nickyg666/orangepi-zero3w-mainline](https://github.com/nickyg666/orangepi-zero3w-mainline) | Reported successful 6.18.19 and PMIC/MMC findings; **independent report, not our HW proof** |
| Developer's working vendor image builder | [mkinderwater/opi-3w-wbuild](https://github.com/mkinderwater/opi-3w-wbuild) | Proven 0.7.6 vendor image with dense ext4 /boot normalization |
| Developer's mainline evidence repo | [this repository](https://github.com/mkinderwater/orangepi-zero3w-linux-mainline) | M2 historical records and new 6.6.98 work branch |

## Exact vendor files

- [Zero 3W board config](https://github.com/orangepi-xunlong/orangepi-build/blob/7f24222b928eab94780f2af03289ce527e07241e/external/config/boards/orangepizero3w.conf): `sun60iw2` family; Zero 3W DTB.
- [sun60iw2 family](https://github.com/orangepi-xunlong/orangepi-build/blob/7f24222b928eab94780f2af03289ce527e07241e/external/config/sources/families/sun60iw2.conf): `orange-pi-6.6-sun60iw2`, `linux-sun60iw2-current-a733`.
- [A733 kernel config](https://github.com/orangepi-xunlong/orangepi-build/blob/7f24222b928eab94780f2af03289ce527e07241e/external/config/kernel/linux-sun60iw2-current-a733.config): PMIC, R-TWI, DMA, MMC, CCU, pinctrl, UART.
- [Boot script](https://github.com/orangepi-xunlong/orangepi-build/blob/7f24222b928eab94780f2af03289ce527e07241e/external/config/bootscripts/boot-sun60iw2.cmd): env import, root UUID/PARTUUID, FDT addr/resize, overlays, `bootm`.
- [Board Boot0 packages](https://github.com/orangepi-xunlong/orangepi-build/tree/7f24222b928eab94780f2af03289ce527e07241e/external/packages/pack-uboot/sun60iw2/bin): `boot0_sdcard_orangepizero3w.fex`, `boot0_sdcard_orangepizero3w_1800M.fex`, `monitor.fex`, `scp.fex`, `boot_package.cfg`, `sys_config.fex`.
- [Vendor DRM HDMI glue](https://github.com/alexcaoys/allwinner-bsp/blob/656a550c826787e7e72fae58ca793df9e0988ac8/drivers/drm/sunxi_drm_hdmi.c): core call and bind failure.
- [HDMI SoC platform selector](https://github.com/alexcaoys/allwinner-bsp/blob/656a550c826787e7e72fae58ca793df9e0988ac8/drivers/drm/sunxi_device/sunxi_hdmi.c): root `arm,sun60iw2p1` matching.
- [PMIC I2C / regulator sources](https://github.com/alexcaoys/allwinner-bsp/tree/656a550c826787e7e72fae58ca793df9e0988ac8/drivers/power): AXP8191 and AXP515 match and regulator descriptors.
- [MMC source](https://github.com/alexcaoys/allwinner-bsp/blob/656a550c826787e7e72fae58ca793df9e0988ac8/drivers/mmc/sunxi-mmc.c): v5p3x controller match and supply lookup.

## Reconstruction discipline

Git records **scripts, patches, hashes, decisions, and sanitized evidence**. It does not contain the original ~4.4 GiB stock image, all WSL worktree contents, proprietary boot firmware or complete compiled binaries. A clean reproduce requires separately acquiring stock media and obtaining matching compiler and boot firmware. Record exact `git rev-parse HEAD`, final `.config`, binary checksums, tool versions and SD image hashes. Pinned revision is not proof of byte-identical vendor release binary.

The two 6.6.98 builds are now OFFLINE PASS; not a hardware-confirmed 6.6.98 rebuild. All 6.18 kernel builds remain NOT HW VERIFIED.
