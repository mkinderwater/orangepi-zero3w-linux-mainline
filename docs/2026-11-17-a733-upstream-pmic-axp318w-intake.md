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

## 2026-11-17: uploaded v8 mailbox contents verified and switch ambiguity identified

Actual uploaded archive `axp318w-upstream-v8.tar.gz` inspected as a mailbox. It contains **exactly five ordered patches**, the v8 cover, fetch logs and an inventory. Mailbox SHA256 from operator: `1fe1f5834851b10d6fe3be4236adbcaa47815dae122f5aa44a94ae1189f6b22a`.

| Patch | Subject | Files |
| --- | --- | --- |
| 1/5 | Constify axp313 and axp717 cells | `drivers/mfd/axp20x.c` |
| 2/5 | Fix i2c instantiation | `drivers/mfd/axp20x-i2c.c`, `axp20x-rsb.c`, `axp20x.c`, `include/linux/mfd/axp20x.h` |
| 3/5 | Document AXP318W binding | `Documentation/devicetree/bindings/mfd/x-powers,axp152.yaml` |
| 4/5 | Add AXP318W MFD/regmap/IRQs | `axp20x-i2c.c`, `axp20x.c`, `axp20x.h` |
| 5/5 | Add AXP318W regulator definitions | `drivers/regulator/axp20x-regulator.c` |

**Crucial MMC0 supply comparison:**
- Upstream v8 **CLDO5 is explicitly present**: `AXP318_CLDO5_CONTROL=0x33`, enabled by `AXP318_LDO_OUTPUT_CONTROL2` bit 7. Its supply name is `cldoin`. This is driver source evidence, not proof the vendor AXP8191's CLDO5 has the same register address.
- Upstream v8 defines **SWOUT1 and SWOUT2**, both described as switched outputs downstream of DCDC1. SWOUT1 is enabled through `AXP318_DCDC_OUTPUT_CONTROL2` bit 3, SWOUT2 through bit 4. **There is no regulator named DC1SW2 in the v8 driver.** The vendor board's `reg_dc1sw2` *could* correspond to SWOUT2, but that must be proven from vendor PMIC register definitions and the board's physical wiring. **Do not automatically alias `dc1sw2` to `swout2` or switch it in software.**
- No direct matching driver for `x-powers,axp8191` is defined by this series; its MFD compatible is `x-powers,axp318w`. Similar naming is insufficient to establish same-chip identity and register compatibility.
- Patch 4 includes the AXP318W MFD writable ranges, interrupt map and register address definitions. Patch 5 describes 9 DCDC regulators, 28 LDOs, two switches and RTC LDO. This isn't a two-regulator stand-alone patch, so stage the complete upstream series for compiling first, then use only required regulator consumers in the Zero 3W DTS.
- The b4 fetch log reports **DKIM BADSIG** and unavailable OpenPGP key for the five messages. Preserve hashes and independently verify the published upstream source before release. This is an attestation caveat, not proof of compromised code.

### Source-only applicability test

A new checker has been committed: `scripts/check-axp318w-upstream-backport.py`. It unpacks the single mailbox, validates patch subjects/order, copies only the six affected source/binding files to a temporary scratch tree, performs sequential `git apply --check` and scratch `git apply`, and writes a review JSON. It **does not** edit kernel source, write PMIC registers, modify voltage constraints or assemble a boot image.

```bash
cd /root/orangepi-zero3w-linux-mainline
git pull --ff-only
python3 scripts/check-axp318w-upstream-backport.py \
 --archive /root/opi3w-m2-work/axp318w-upstream-v8.tar.gz \
 --source /root/opi3w-hybrid-sources-0.1.0/linux \
 --output /root/opi3w-m2-work/axp318w-upstream-check-v1
```

**Required gates after applicability:** independently compare AXP8191 versus AXP318W PMIC silicon ID, CLDO5 voltage and enable registers, DCDC1/outs switch register map and exact `dc1sw2` identity. Verify whether the Zero 3W needs AXP515 for any boot-critical rail. Only then construct a separate upstream PMIC configuration and new board DTS. No live voltage or 1.8V MMC tests until that evidence is complete.

## Operator WSL applicability result, November 17

All five upstream AXP318W v8 patches passed sequential scratch `git apply --check` and application against the pinned clean Linux source. They cover constified MFD cells, corrected I2C instantiation, DT bindings, AXP318W MFD and regulator data. This establishes **source applicability only**, not compile success, device identity or electrical compatibility.

Next script: `scripts/build-axp318w-clean-driver.py` constructs a new Linux source copy and separate build output from the pinned clean config, applies only those five reviewed patches, enables `I2C`, `MFD_AXP20X_I2C`, `REGULATOR_AXP20X`, resolves dependencies with `olddefconfig`, and builds `drivers/mfd/` and `drivers/regulator/` independently. It verifies `axp20x.o`, `axp20x-i2c.o` and `axp20x-regulator.o`; no boot image or PMIC writes. AXP8191 vs AXP318W and DC1SW2 vs SWOUT2 remain explicitly unverified.

```bash
cd /root/orangepi-zero3w-linux-mainline
git pull --ff-only
python3 scripts/build-axp318w-clean-driver.py \
 --source /root/opi3w-hybrid-sources-0.1.0/linux \
 --config /root/opi3w-clean-618-config-v3/.config \
 --review /root/opi3w-m2-work/axp318w-upstream-check-v1 \
 --output /root/opi3w-m2-work/axp318w-clean-compile-v1 \
 --jobs 4
```

## Operator validation: isolated AXP318W MFD/regulator compile PASS

The WSL compilation completed successfully from the five reviewed upstream v8 patches, applied to a separate source copy of clean Linux 6.18. The operator's output showed the three expected objects:

```text
CC drivers/mfd/axp20x.o
CC drivers/mfd/axp20x-i2c.o
CC drivers/regulator/axp20x-regulator.o
AXP318W_MFD_REGULATOR_COMPILE_PASS
NOT_HARDWARE_VALIDATED: do not bind AXP8191 to AXP318W until register identity confirmed
```

Result: **source applicability 5/5, compile PASS**. No full combined kernel link including PMIC, no live regulator programming, no electrical proof, and no AXP8191-compatible alias have been tested.

Next: search the vendor's generic AXP core and regulator definitions, which need not have `8191` in their filenames. Confirm AXP8191 chip identity and CLDO5/SWOUT2 register mapping, then merge PMIC into a new clean source track without modifying the 4,429,832-byte combined CCU+pinctrl baseline.
