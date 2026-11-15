# Orange Pi Zero 3W Linux 6.18.19 hybrid 0.2.7: DTB, PMIC and early-boot audit

**Date:** 2026-11-15  
**Scope:** Actual user-supplied decompiled `hybrid-027.dts` (241 KiB), the 0.2.7 hardware audit, pinned vendor Zero 3W DTS and pinned Allwinner BSP sources. **No new kernel or image is built.**

## Bottom line

- **Confirmed static discrepancy:** The compiled 0.2.7 FDT advertises **512 MiB** at `/memory@40000000`, despite the tested board being the 1 GiB variant. This is a **fallback DTS value**, not proof that Linux saw only 512 MiB. We have **not captured the actual FDT after U-Boot fixups**. This deserves top priority in an early-handoff audit.
- **Confirmed PMIC topology:** `twi@7083000` is enabled and contains both AXP515 (`0x34`) and AXP8191 (`0x36`). The SD controller is enabled, with `vmmc` and both 3.3 V switched supply phandles pointing to DC1SW2 and both 1.8 V switched supply phandles pointing to CLDO5. These phandles **exist**; their presence does **not** prove that the 6.18 regulators probe.
- **Confirmed driver availability in pinned upstream reference:** Allwinner BSP contains `allwinner,sunxi-twi-v101` matching, `x-powers,axp8191` I2C match, `axp8191_cells` with an `axp2101-regulator` child, and regulator descriptors for DCDC1, DC1SW2 and CLDO5. The compiled hybrid still needs its **actual build `.config`, linked objects and logs** verified.
- **Concrete driver weakness:** The vendor MMC driver helper `sunxi_mmc_regulator_get_supply()` performs optional regulator lookups and prints an error for missing values, but returns `0`; an unresolved supplier can therefore be misreported downstream. Verify whether the 0.2.7 MMC object uses this function and ensure `-EPROBE_DEFER` is propagated before attempting a runtime fix.
- **The Boot0 UART setting is not Linux pinmux evidence:** `sys_config.fex` names PB9/PB10 as the boot-debug UART; the compiled Linux pinctrl definition uses an **empty `pins` list** for UART0, while PB9/PB10 also occur under TWI8. Do not silently change UART pins without a same-board validation.
- **Linux entry is still unconfirmed:** HBI-027 and K2 both stay at the U-Boot splash with the LED solid. VBI with vendor 6.6.98 boots and blinks the LED. This is evidence of a stage difference, not proof of which early kernel or driver failed.

## Evidence table: actual compiled FDT

| Node/property | User-provided 0.2.7 DTS | Relevance |
| --- | --- | --- |
| `/memory@40000000/reg` | `<0 0x40000000 0 0x20000000>` | **512 MiB fallback**. Find out whether U-Boot rewrites it for 1/2/4/12 GiB variants. |
| `/chosen/bootargs` | `earlycon=uart0,0x02500000 console=ttyS0,115200n8 loglevel=7` | DTB defaults may be overwritten by U-Boot `bootargs`. Capture actual final bootargs; this value does not prove a functioning early console. |
| `twi@7083000` | `allwinner,sunxi-twi-v101`, `status=okay`, `clock-frequency=400000`, `twi_drv_used=1` | Exact BSP `of_match` exists; verify clock/reset/DMA/pinctrl and regulator calls at runtime. |
| `pmu@34`, `pmu@36` | `x-powers,axp515`, `x-powers,axp8191` | Both devices need the matching I2C MFD drivers. |
| `pmu@36/regulators@0/dcdc1` | phandle `0x65`, always-on | Supplies DC1SW2 through `swin-supply` (0x65). |
| `pmu@36/regulators@0/dc1sw2` | phandle `0x54`, always-on | MMC `vmmc`, `vqmmc33sw`, `vdmmc33sw` all use 0x54. |
| `pmu@36/regulators@0/cldo5` | phandle `0x78`, always-on | MMC `vqmmc18sw`, `vdmmc18sw` use 0x78. |
| `sdmmc@4020000` | `allwinner,sunxi-mmc-v5p3x`, enabled, high-speed/UHS modes, max 150 MHz | The vendor SD driver matches this; its 6.18 integration must be verified. Conservative 3.3 V/25 MHz testing can isolate runtime power switching **only after** kernel entry is proved. |
| `uart@2500000` | `allwinner,uart-v100`, enabled, uses pinctrl phandle `0x37` | Pinctrl target defines empty `pins`. An early console may remain unavailable. |
| `hdmi0@5520000` | `allwinner,sunxi-hdmi`, enabled, DCDC2 `0x66`, CLDO2 `0x75` | Correct-looking supply links do not demonstrate modesetting. HDMI may not show output before DRM initializes. |
| `/leds/led-0` | `status_led`, R_PIO PL7, active-high, `heartbeat` | The status LED should blink only if the Linux GPIO LED driver and its pinctrl are functional. |

## High-priority review: 512 MiB and FDT fixups

The official U-Boot A733 source `arch/arm/lib/bootm.c` contains a conditional memory fixup guarded by a lookup of `/memory`. Our supplied FDT contains `/memory@40000000`, not a literal `/memory` node. **That mismatch merits verification**, but U-Boot may also apply memory fixups elsewhere. Do not claim that this particular guard is the only fixup path without tracing the exact compiled vendor bootloader and actual in-memory DTB.

**Test M (memory hypothesis):** Capture the FDT passed to Linux at the `booti` handoff (or trustworthy U-Boot FDT print commands), including `/memory*`, memory-bank size and reservations. Compare with the same board under VBI. If Linux's 6.18 FDT remains 512 MiB, correct the **runtime handoff mechanism** rather than shipping separate RAM-specific DTBs. **Do not hardcode 1 GiB** as a release fix: the same image should support 1, 2, 4, 12 GiB and other board variants once firmware supports them.

## High-priority review: PMIC and MMC probe sequence

The pinned BSP has these stages:

1. A733 R_PIO/CCU bring up `twi@7083000` (`allwinner,sunxi-twi-v101`). The TWI driver uses `regulator_get(dev, "twi")` and may defer if the supply is unavailable. The vendor board DTS has `twi-supply` commented out. Verify its *actual* behavior with the 6.18 regulator framework, not merely the DTS.
2. The driver must register the I2C bus and detect `x-powers,axp8191` at address `0x36`; AXP515 at `0x34` is separate.
3. The MFD registers `axp2101-regulator`; its AXP8191 variant must register the **correct** DC1SW2 and CLDO5 regulator providers from the DTS.
4. MMC0 must successfully resolve `vmmc` (DC1SW2) and negotiate valid OCR voltage before enumerating the SD card. The pinned vendor MMC helper can log missing regulator lookups but return success. Do not use `regulator-always-on` as proof of a working provider; do not remove `vmmc-supply` as a speculative fix.
5. Only after the card enumerates can initramfs discover its root volume and write ext4 logs. No root logs cannot prove stage 1 to 4 failed unless Linux entry itself is established.

**Test P (competing PMIC hypothesis):** Compare the actual 0.2.7 `.config` and compiled BSP source, then instrument distinct read-only PMIC/TWI/MMC probe breadcrumbs before creating a new image. Avoid any change that enables/disables critical voltage rails or introduces unknown PMIC register writes.

## Required checks before kernel changes

1. Run included `audit.py` against the compiled 0.2.7 DTB. Save all results to **Windows Downloads**. It resolves known phandles and reads effective `.config` values without mounting or modifying a card.
2. Compare the resulting `audit.json` with the known-good VBI kernel DTB, remembering that different kernel driver bindings are expected; a vendor DTB need not be suitable for 6.18.
3. Capture exact final U-Boot `bootargs`, `booti` addresses, raw Image header and input DTB hash. Distinguish the file DTB from the DTB modified in U-Boot RAM.
4. Complete memory-handoff test M and PMIC-probe test P as **two independent hypotheses**. Do not change both at once.
5. Use the K2 no-initramfs failure as evidence that the initramfs is not the sole cause, not proof that Linux never executes.
6. Retain existing 0.2.7 HDMI support and the VBI vendor control. Any display success still requires a working modeset/scanout on the actual board.

## What is **not** established

- A broken PMIC register map or wrong rail voltage in the actual 0.2.7 kernel.
- U-Boot's final RAM fixup state, Linux 6.18 early entry, or whether the framebuffer failed before or after MMC.
- That the TWI optional regulator failure occurs in this particular build.
- That the vendor UART debug PB9/PB10 are safe for the Linux UART0 pinctrl under all DT overlays.

## Source provenance

- Uploaded `hybrid-027.dts`, which is a decompile of the 0.2.7 staged boot DTB; exact source DTS build provenance is separate.
- [Pinned vendor Zero 3W DTS](https://github.com/orangepi-xunlong/linux-orangepi/blob/2ac08e8c7cdc28abbdc5c9a9dd812f887ae9c79f/arch/arm64/boot/dts/allwinner/sun60i-a733-orangepi-zero3w.dts)
- [Pinned BSP TWI driver](https://github.com/alexcaoys/allwinner-bsp/blob/656a550c826787e7e72fae58ca793df9e0988ac8/drivers/twi/twi-sunxi.c)
- [Pinned BSP PMIC MFD](https://github.com/alexcaoys/allwinner-bsp/blob/656a550c826787e7e72fae58ca793df9e0988ac8/drivers/power/mfd/axp2101.c)
- [Pinned BSP PMIC I2C](https://github.com/alexcaoys/allwinner-bsp/blob/656a550c826787e7e72fae58ca793df9e0988ac8/drivers/power/mfd/axp2101-i2c.c)
- [Pinned BSP AXP8191 regulators](https://github.com/alexcaoys/allwinner-bsp/blob/656a550c826787e7e72fae58ca793df9e0988ac8/drivers/power/regulator/axp2101-regulator.c)
- [Pinned BSP MMC](https://github.com/alexcaoys/allwinner-bsp/blob/656a550c826787e7e72fae58ca793df9e0988ac8/drivers/mmc/sunxi-mmc.c)
- [Official Orange Pi Boot0 and boot-package reference](https://github.com/orangepi-xunlong/orangepi-build/tree/next/external/packages/pack-uboot/sun60iw2)
- [Vendor U-Boot ARM64 boot implementation](https://github.com/orangepi-xunlong/u-boot-orangepi/blob/v2018.05-sun60iw2/arch/arm/lib/bootm.c)

**Publication policy:** This report contains no full vendor binaries, credentials, or SD-card images. Treat these as source and static-audit findings, not a certified bootable kernel.
