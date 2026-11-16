# Orange Pi Zero 3W engineering knowledge base
Evidence cutoff: 2026-11-15. Maintained alongside the reproducible 6.6.98 work on `work/zero3w-vendor-6.6.98-baseline`.

**Current truth:** Stock vendor Linux 6.6.98 boots with native HDMI, Wi-Fi and SSH. Our separately built 6.6.98 **control** and **identity-corrected** kernel/DTB compile, but have **not** been flashed. F1 (vendor 6.6.98 kernel + hybrid 0.2.7 DTB) reaches Debian userspace, expands root, and supports USB-C Ethernet SSH; its Linux HDMI **fails**. No 6.18.19 kernel hardware execution has been verified. The frozen splash persists even when F1 boots, so splash is **not** a kernel-entry test.

## Start here

| Subject | Record |
| --- | --- |
| Clock units, MHz definitions, actual source settings and experiment options | [clock and frequency reference](2026-11-15-clock-frequency-reference.md) |
| Reviewed Git resources with prioritized alternatives for 6.6/6.18, DTS, PMIC, HDMI and boot | [resource review and options](2026-11-15-resource-review-and-options.md) |
| Current hardware test matrix | [experiments and acceptance](2026-11-15-hardware-matrix.md) |
| Source commits, branches, external work | [sources and resource map](2026-11-15-source-provenance.md) |
| Bootloader, U-Boot, boot scripts and memory addresses | [boot chain and handoff](2026-11-15-boot-chain.md) |
| Compiled/live device tree, board identity, RAM and HDMI | [DTS/DTB findings](2026-11-15-dts-dtb.md) |
| PMIC, power, I2C, MMC and clocks | [PMIC and MMC audit](2026-11-15-pmic-mmc.md) |
| HDMI driver root match, output failure and graphics architecture | [HDMI and display](2026-11-15-hdmi.md) |
| Exact 6.18.19 hybrid versions and unresolved kernel entry | [hybrid 6.18](2026-11-15-hybrid-618.md) |
| Repeatable 6.6.98 vendor builds and build-system bugs | [vendor project](../vendor-6.6.98/README.md) and [next steps](../vendor-6.6.98/docs/next-steps.md) |
| Image validation, safe experiment discipline | [acceptance and release gates](2026-11-15-reproducibility.md) |
| M2x experiments (M2cp through M2dc), original failure and newer cross-checks | [M2x results and options](2026-11-15-m2x-results.md) |
| Original experiments | [M2 history](development-history.md), [original boot investigation](boot-handoff-and-failures.md), [original engineering report](../ORANGE_PI_ZERO_3W_LINUX_6_18_BOOT_INVESTIGATION_2026-11-15.md) |

## Evidence labels

- **HW PASS:** Direct successful board behavior with an identified flashed image.
- **HW FAIL/OBSERVED:** Direct hardware observation, not proof of failure stage.
- **OFFLINE PASS:** Compiler, assembler, static consistency checks, or filesystem audits only.
- **INFERRED:** Hypothesis explaining evidence, not yet isolated.
- **UNKNOWN:** No trustworthy direct evidence.

No uploaded image, vendor binary, SD image, proprietary firmware, private credentials, machine ID, serial number, or full network-bearing logs are reproduced in this repository. Capture hashes and sanitized excerpts instead. Later artifacts may exist only in the WSL build host or ChatGPT conversation and require explicit export before Git can guarantee full reconstruction.

## Primary direction

**First** reproduce and hardware-validate a clean vendor 6.6.98 Zero 3W build (control, then one-property board identity correction). **Then** port independently proven subsystems to 6.18.19, retaining vendor U-Boot and testing kernel entry separately from HDMI. Avoid speculative PMIC changes and do not hardcode RAM size.
