# A733 / Orange Pi Zero 3W clock and frequency reference

Revision: 2026-11-15. **Sources pinned**, no runtime clock measurement in this document. This is a reference of units and potential experiments, **not permission to overclock**.

## What MHz means

- **Hz**: cycles/second. **kHz**: 1,000 Hz. **MHz**: 1,000,000 Hz. **GHz**: 1,000,000,000 Hz.
- In Linux DT `clock-frequency = <N>;` values are ordinarily **Hz**, unless a specific binding explicitly says otherwise.
- CPU frequency settings in Orange Pi build scripts `CPUMIN` and `CPUMAX` use **kHz**; don't read `2002000` as 2,002,000 MHz.
- `max-frequency` in MMC DTB is **Hz** and is a software upper limit, not proof the card ran at that speed.
- **Boot0 DRAM `dram_clk`** is a vendor boot-firmware configuration and must be evaluated against Boot0's parser and selected board profile. It is **not** Linux `clock-frequency` or necessarily the effective DDR transfer rate.
- HDMI pixel/PHY clock, PLL multiplication, TCON output, I²C bus rate, CPU frequency, MMC bus clock and DRAM frequency are separate domains. A change in one cannot be evaluated by comparing a number from another.
- Parent clocks, assigned clocks, clock names, resets and power rails must agree with the **driver's binding**, not just numerical frequency values.

## Values directly found in pinned sources

| Item | Source value | Converted meaning | Scope / evidence |
| --- | --- | --- | --- |
| CPU policy minimum | `CPUMIN=416000` | 416 MHz **if interpreted as kHz** | Orange Pi family build configuration default, not measured CPU speed |
| CPU policy maximum | `CPUMAX=2002000` | 2002 MHz (2.002 GHz) **if interpreted as kHz** | Family default, not verified thermal-safe for every board revision |
| CPU governor default | `ondemand` | Policy, not a MHz number | Family build config |
| Vendor Boot0 DRAM profile | `dram_clk=1200` | Vendor value 1200; often described in MHz, but **exact effective clock and DDR transfer units unverified** | `sys_config.fex`, Boot0 stage before Linux |
| SD/MMC0 max clock | `max-frequency=<150000000>` | 150 MHz cap | Vendor Zero 3W DTS, not measured runtime rate |
| SDIO/MMC1 max clock | `max-frequency=<208000000>` | 208 MHz cap | Vendor Zero 3W DTS, not proof Wi-Fi negotiates 208 MHz |
| Early 6.18 conservative SD probe | 25 MHz | Deliberate diagnostic cap | Historical M2 DTS, NOT the stock vendor requirement |
| R-TWI0 PMIC bus | `clock-frequency=<400000>` | 400 kHz = 0.4 MHz | Vendor Zero 3W DTS, PMIC bus requested speed |
| Some TWI buses | `clock-frequency=<100000>` | 100 kHz = 0.1 MHz | Vendor DTS; don't globally change all buses |
| Audio assigned clock | `assigned-clock-rates=<12288000>` | 12.288 MHz | Vendor audio/codec context, not CPU clock |
| Legacy oscillator experiment | 24 MHz | 24,000,000 Hz | M2cx changed the `&osc` DT node; did **not** produce a verified 6.18 boot |
| Boot0 variant suffix | `boot0_sdcard_orangepizero3w_1800M.fex` | Filename only | Do **not** assume 1800M is CPU clock, DDR data rate or tested board profile without Boot0 evidence |

**Source links:** [vendor board DTS](https://github.com/orangepi-xunlong/linux-orangepi/blob/2ac08e8c7cdc28abbdc5c9a9dd812f887ae9c79f/arch/arm64/boot/dts/allwinner/sun60i-a733-orangepi-zero3w.dts), [family configuration](https://github.com/orangepi-xunlong/orangepi-build/blob/7f24222b928eab94780f2af03289ce527e07241e/external/config/sources/families/sun60iw2.conf), [boot-firmware configuration](https://github.com/orangepi-xunlong/orangepi-build/blob/7f24222b928eab94780f2af03289ce527e07241e/external/packages/pack-uboot/sun60iw2/bin/sys_config/sys_config.fex), [legacy 24MHz experiment](boot-handoff-and-failures.md).

## What to capture on a hardware-booted reference (read-only)

Run from working vendor 6.6.98 Linux as root where needed, and store results outside source checkout:

```bash
uname -a
cat /proc/cmdline
find /sys/devices/system/cpu/cpufreq -maxdepth 2 -type f \
  \( -name 'scaling_cur_freq' -o -name 'scaling_min_freq' -o -name 'scaling_max_freq' \) \
  -print -exec cat {} \;
for f in /sys/kernel/debug/clk/clk_summary /sys/kernel/debug/clk_summary; do
  if [ -r "$f" ]; then cat "$f"; break; fi
done
dmesg | grep -Ei 'clock|pll|ddr|dram|freq|twi|mmc|hdmi' | tail -150
```

The debug clock tree may not be mounted. Do not alter `clk_ignore_unused`, cpufreq limits or PMIC voltage rails just to make this report more complete.

## Distinct safe experiment options

| ID | Option | Controlled variable | Evidence gate |
| --- | --- | --- | --- |
| CLK-A | Establish vendor **runtime** clock tree | None | `clk_summary`, cpufreq, MMC debug and baseline logs |
| CLK-B | Audit 24 MHz oscillator provider | Source/DTB read-only | Root clock frequency and consumers, verify against pinned source; no hardware clock changes |
| CLK-C | Investigate `failed to find dram_clk` | Driver binding source audit first | Confirm exact requested clock name, provider, probe timing; only then change one binding |
| CLK-D | Compare MMC 150 MHz vendor cap with 25 MHz diagnostic | **Test-image DTB cap only**, after vendor pass | SD enumerate, mount, read integrity, UHS signalling and power controls; no automatic frequency increase |
| CLK-E | Validate R-TWI0 bus speed | Read-only hardware logs and source comparison | AXP8191 success, AXP515 error scope, SCL timing if instrumented; do not change bus speed to hide timeouts |
| CLK-F | HDMI PHY/PLL and pixel clock audit | Binding and trace only | First fix root-compatible match, then inspect DRM/HPD/EDID and selected mode; no arbitrary PHY tuning |
| CLK-G | Board Boot0 DRAM variants | Firmware inventory and exact 1:1 hashes only | Correct Boot0 for board/DRAM variant, board-specific memory training; no interchangeable 1800M assumption |

**Priority order:** CLK-A/B/C read-only, independently paired with HDMI source checks. No runtime clock tweaks until the rebuilt 6.6.98 reference physically boots.

## Guardrails

Never hardcode the tested board's RAM capacity: F1 proves U-Boot fixed a static 512 MiB DTB node to the detected 1 GiB. Never infer DRAM transfer rate from `dram_clk` without Boot0 documentation and physical measurement. Never interpret frozen HDMI splash as Linux not executing: F1 boots headless while HDMI DRM fails. Record all attempted experiments, including negative results and exact boot media hashes.
