# Zero 3W PMIC source decision: AXP8191 vendor name vs upstream AXP318W

Date: 2026-11-17. **Static research and source intake only.** No PMIC voltage, clock, MMC, boot media or kernel source changes.

## Actual hardware evidence from operator

Pinned 6.18 clean build has no AXP8191 or AXP515 references in upstream `drivers/mfd`, `drivers/regulator` or `include/linux/mfd`. The vendor BSP filename search only found AXP8191 temperature helpers and AXP515 USB/battery files. **That filename search does not identify the vendor PMIC core**: its implementation may be in generic AXP files without `8191` in the filename.

The source hybrid Zero 3W board DTSI contains:
- `/soc@3000000/twi@7083000/pmu@36` with `compatible="x-powers,axp8191"`.
- MMC0 `vmmc-supply`, `vqmmc33sw-supply`, `vdmmc33sw-supply` all reference AXP8191 `dc1sw2`.
- MMC0 `vqmmc18sw-supply`, `vdmmc18sw-supply` reference AXP8191 `cldo5`.
- Additional CLDO5 references include SerDes, so avoid turning this rail off or assigning it speculatively.
- MMC0 SD controller register `0x04020000`, IRQ GIC_SPI 161, CCU module `CLK_SMHC0` plus bus/store/MBUS clocks, `RST_BUS_SMHC0`, and main PIO PF pins. Vendor-specific supply and pinctrl properties cannot be mechanically transplanted to the upstream driver.

## Upstream PMIC candidate

Jerome Brunet and Andre Przywara's **2026-09-10 v8 five-patch series**: `[PATCH v8 0/5] regulator: Add X-Powers AXP318W PMIC support` (Message-ID `20260910-axp318-regulator-v8-0-e906a61a7f3d@baylibre.com`). Public [v8 cover letter](https://lists.openwall.net/linux-kernel/2026/09/10/1334), [5/5 regulator patch](https://lists.openwall.net/linux-kernel/2026/09/10/1331). The A733-focused PMIC has 9 DCDCs, many LDOs, and upstream regulator descriptions include **CLDO5**. U-Boot A733 work says AXP318W is also known as **AXP819** in vendor code ([2025 U-Boot patch](https://lore-kernel.gnuweeb.org/linux-sunxi/20251130-01-a733-soc-support-v2-8-18bdd4376fad%40gentoo.org/t/)). **Do not claim AXP8191 == AXP318W without confirming its silicon ID/register map and behavior.** DC1SW2 in particular must be located in the upstream v8 regulator descriptions or proven equivalent from documented switch register behavior; CLDO5 presence alone is not sufficient.

## Source acquisition

```bash
cd /root/orangepi-zero3w-linux-mainline
git pull --ff-only
bash scripts/fetch-axp318w-upstream-v8.sh /root/opi3w-m2-work/axp318w-upstream-v8
```

The script downloads the exact upstream 5-patch series through `b4`, records files and checksums and does not change the pinned Linux source.

After download, compare vendor and upstream descriptions in a scratch tree only. Verify the precise chip ID at I2C address `0x36`, PMIC interrupt/mfd registration, DC1SW2 enable path, CLDO5 voltage selector and enable bits, parent rails, and whether the board requires the secondary AXP515 for MMC0. No physical rail writes before exact electrical behavior is reconciled.

## Minimum boot target

The product kernel remains vendor-free in its source: small upstream 6.18 with A733 CCU/pinctrl compiled and linked, upstream `MMC_SUNXI` D1-compatible MMC0, minimal upstream PMIC driver, and verified board DTS. Keep MMC1/2 optional and MMC3 disabled. Current clean ARM64 Image is **4,429,832 bytes**, SHA256 `24f58c911c8f382ee48c63952280d504ebe8f1412786fa37fb8af5a38dd8247e`. Not yet bootable on Zero 3W.
