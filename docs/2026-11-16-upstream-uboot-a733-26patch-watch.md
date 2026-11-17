# Upstream U-Boot A733 series watch

**Baseline:** 2026-11-16. **Status:** Submitted for upstream review; not established as merged.

- Subject: `[PATCH 00/26] sunxi: Add Allwinner A733 (sun60i) and Orange Pi 4 Pro support`
- Author: Alastair D'Silva
- Posted: November 13, 2026
- Cover Message-ID: `20261113023236.569054-1-alastair@d-silva.org`
- Original thread: https://lore-kernel.gnuweeb.org/u-boot/20261113023236.569054-1-alastair@d-silva.org/
- Number of patches: 26
- Tested board: **Xunlong Orange Pi 4 Pro**, 6 GiB LPDDR5 at 3600 MT/s; author reports SPL DRAM training, 4-bit MMC0 SD card, and PCIe Gen3 NVMe partition enumeration.
- Original November series also depends on pending TF-A A733 work. See its cover letter for review URLs.

## What to track

| Patch range | Area | Zero 3W implications |
| --- | --- | --- |
| 1-3 | AXP318W PMIC regulators, shutdown, SPL rails | Verify vendor AXP8191 electrical identity and DC1SW2/CLDO5 mapping, never alias blindly |
| 4-11 | DT bindings, GPIO, pinctrl, clock, MMC, UART | Likely useful for independent A733 U-Boot boot and SD; requires Zero 3W pin assignments |
| 12-13 | AArch64 SPL init rodata and FEL return | Important for reproducible nonvendor boot chain |
| 14-21 | ARC PMU LPDDR5 DRAM training, A733 SoC/SPL | **Do not assume applies to Zero 3W LPDDR4**; distinct DRAM training work required |
| 22-24 | Cadence PHY, PCIe, NVMe | Optional; not an SD-root prerequisite |
| 25-26 | A733 SoC DTS and Orange Pi 4 Pro board | Reuse only upstream SoC facts. Create Zero 3W-specific board configuration |

## Status checks

Monitor the original thread for review replies, revisions (`[PATCH v2 ...]` etc.), Patchwork status, accepted series in U-Boot master/next and tagged releases. Verify individual patches, not just the cover title. Distinguish submitted, acked, applied to maintainer tree, merged and released.

**Non-negotiable:** Preserve the known-good Boot0/BL31/SCP/U-Boot 2018.07 as a control until a complete native Zero 3W LPDDR4 build boots SD, passes serial/UART, starts Linux and survives repeated power cycles. This series alone does not replace the control firmware.

No source from this 26-patch submission is currently incorporated into the clean Linux 6.18 image. Linux kernel DTS and U-Boot SPL remain distinct workstreams.
