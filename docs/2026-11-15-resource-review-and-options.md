# Zero 3W Linux 6.6.98 / 6.18.19: cross-source review and actionable options

Status: 2026-11-15. Reviewed published repository and pinned external sources. No new hardware tests in this document.

## Reviewed resources, authority and limits

| Source | What it can establish | What it cannot establish |
| --- | --- | --- |
| [Orange Pi build framework](https://github.com/orangepi-xunlong/orangepi-build/tree/7f24222b928eab94780f2af03289ce527e07241e) | Board build family, firmware package names, U-Boot branch, defaults, source config | Hardware behavior of our modified images |
| [Orange Pi Linux 6.6.98](https://github.com/orangepi-xunlong/linux-orangepi/tree/2ac08e8c7cdc28abbdc5c9a9dd812f887ae9c79f) | Board DTS/DTSI, BSP drivers, compiler source reference | Source/compiled image identity with shipped stock without compare |
| [Allwinner BSP](https://github.com/alexcaoys/allwinner-bsp/tree/656a550c826787e7e72fae58ca793df9e0988ac8) | A733 CCU/pinctrl/UART/TWI/MMC/PMIC/DRM matching and behavior | Safe untested transplant into upstream 6.18 |
| [Jonas A733 engineering](https://github.com/jonas5/Allwinner-A733-kernel/tree/fc71840a8b5bb17a73ed42cc00e46838a97c8aa1) | Alternative A733 integration and voltage-step reference | Proof of our board's rails or Linux 6.18 success |
| [Independent Zero 3W 6.18 bring-up](https://github.com/nickyg666/orangepi-zero3w-mainline) | Reported working 6.18.19 and experience with AW_TWI, PMIC and MMC voltage | Our own 6.18 kernel entry proof |
| [Working reference image builder](https://github.com/mkinderwater/opi-3w-wbuild) | ext4 boot normalization and proven vendor 0.7.6 control | Guaranteed viability of hybrid 6.18 BSP |
| [This repository's M2 history](boot-handoff-and-failures.md) | Earlier experiments, negative outcomes, boot script boundaries | Proof of later F1/HBI behavior without newer evidence |
| [Hardware matrix](2026-11-15-hardware-matrix.md) and [boot chain](2026-11-15-boot-chain.md) | Flashed controls, handoff addresses and operator observations | A directly captured hardware 6.18 console trace |
| [F1 running DTB findings](2026-11-15-dts-dtb.md), [PMIC](2026-11-15-pmic-mmc.md), [HDMI](2026-11-15-hdmi.md) | Actual F1 6.6 vendor-kernel success with hybrid DTB, RAM fixup, PMIC and HDMI fail | Every 6.18 DT binding succeeds |

## Options, grouped by component

**These are choices to test, not a shopping list of fixes to apply together.** The priority reflects hardware evidence and impact on reproducibility.

| ID | Area | Option | Reason to consider | Test / reject condition | Priority |
| --- | --- | --- | --- | --- | --- |
| REF-1 | Vendor 6.6.98 | Rebuild unchanged pinned kernel and exact vendor DTB in a stock image | Separates toolchain/repackaging problems from board DTS | Hardware HDMI, root, Wi-Fi, USB, reboot; compare hashes | **First** |
| REF-2 | Vendor 6.6.98 DTS | Board ID `xunlong,orangepi-zero3w` with required `arm,sun60iw2p1` fallback | Fixes known vendor DTS naming error without HDMI root-match regression | One-property compiled DTB diff; hardware HDMI and SSH | **Second** |
| REF-3 | Vendor firmware | Keep exact stock Boot0/U-Boot/monitor/SCP and startup script | Vendor raw `booti` is already proven; generic A733 bootloader adds risk | First 32MiB hash/control pass; do not guess DRAM profile | Mandatory |
| DTS-1 | Cross-kernel root | Match every root-compatible consumer used by installed drivers | Hybrid 0.2.7 dropped `arm,sun60iw2p1`, causing F1 HDMI fail | Static match check + F1 single-property hardware test | High |
| DTS-2 | Board hardware | Diff **compiled** vendor and hybrid DTBs, normalized by node/property | Board description and software bindings can both change | Classify hardware, binding, bootloader-fixup and cosmetic differences | High |
| DTS-3 | UART | Validate true Linux pin mux and early console on board | Vendor UART0 pin list empty; Boot0 PB9/PB10 is not Linux proof | Electrical/pinout evidence + known working UART messages | High |
| PMIC-1 | AXP8191 | Preserve DCDC1/DC1SW2/CLDO5 and use pinned BSP provider | Vendor 6.6 and F1 mount root; hybrid has matched drivers | Keep regulator/phandle + actual probe log; don't remove `vmmc` | Mandatory |
| PMIC-2 | AXP515 | Debug I²C address 0x34 interrupt-mask timeout independently | Real F1 warning despite successful AXP8191 | Bus trace + driver error and board presence; do not change voltages | Medium |
| PMIC-3 | MMC | Retain AW_MMC v5p3x compatible and check actual power sequencing | Hybrid compiled and linked driver; no proven 6.18 MMC enumerate | Confirm clock/reset, VMMC, card-detect; read integrity | High after kernel entry |
| CLK-1 | Clock domains | Read MHz/Hz/kHz reference and capture vendor clock tree | 24 MHz oscillator, 150 MHz SD and 1200 DRAM setting are not interchangeable | Read-only `clk_summary` and source binding | High |
| HDMI-1 | Display | Restore SoC root fallback, test vendor-kernel HDMI first | Known match failure is root-compatible error | Correct root match and Linux DRM bind, not just splash | High after REF-1 |
| HDMI-2 | Display | After root fix, check PHY, DE352, TCON3, DCDC2/CLDO2 separately | Later failures may remain | EDID, HPD, DRM connector/CRTC/plane and physical output | Medium |
| BOOT-1 | Linux 6.18 | Preserve VBI-derived `booti` chain and measure actual runtime environment | VBI proved raw vendor `booti` reaches Debian; static HBI range does not overlap | U-Boot `printenv`, FDT in RAM, positive early marker | Critical before more 6.18 source edits |
| BOOT-2 | Linux 6.18 | Earliest boot instrumentation not relying on HDMI/heartbeat | F1 proves frozen splash is misleading | Validated UART or safe GPIO signal; no console-output absence inference | Critical |
| PORT-1 | Linux 6.18 | Reconstruct exact 0.2.7 transformer and source patch series | Pinned inputs + artifact hashes are not complete build recipe | Clean clone reproduces build, module/initrd and Image/DTB hashes or explained deltas | Critical for Git goal |
| DVFS-1 | CPU/DDR | Observe vendor OPP, cpufreq and DDR before modifying clocks | Clock values in Boot0 and kernel differ in units and stage | Read-only source/runtime comparison; no overclock | Later |
| RTC-1 | HYM8563 | Verify physical device presence before editing DTS | F1 I²C timeout, no reliable battery-backed time | Board schematic or bus probe, then isolated DTS test | Later |

See [clock and frequency reference](2026-11-15-clock-frequency-reference.md) for the **definitions of MHz**, source units and a separate CLK-A through CLK-G experiment matrix.

## Recommended two-test batches

| Batch | Experiment A | Experiment B | Expected new evidence |
| --- | --- | --- | --- |
| R1 | REF-1: untouched 6.6.98 control | REF-2: single DT board-identity correction | Verified reproducible vendor reference; HDMI changes isolated |
| R2 | DTS-1: root matches against vendor drivers | CLK-1: read-only clock topology | Prevent reintroducing root compatibility and unit errors |
| R3 | BOOT-1: U-Boot runtime handoff capture | BOOT-2: independent early Linux signal | Distinguish 6.18 kernel entry from network/HDMI failures |
| R4 | PMIC-2: AXP515 bus trace | HDMI-2: post-root-match PHY and DRM trace | Independently locate nonfatal vendor PMIC and display errors |
| R5 | PORT-1: reproduce 0.2.7 from pinned inputs | DTS-2: normalized compiled FDT diff | Full 6.18 Git reconstruction and exact platform deltas |

Maintain **one altered variable in each independent test**. Two tests per batch should not mean mixing two changes into one image.

## Important unsupported assumptions to avoid

- `1800M` in a Boot0 filename does **not** authorize 1800 MHz DRAM, CPU or video assumptions.
- `dram_clk=1200` is not inherently equivalent to DDR-2400 MT/s without verified Boot0 semantics.
- Static 512 MiB vendor memory node does not imply actual RAM limited to 512 MiB: F1's runtime FDT contains 1 GiB.
- Compiled `CONFIG_AW_TWI=y`, `AW_MMC=y`, regulator phandles, and `sunxi-mmc-v5p3x` prove **build viability**, not a working 6.18 MMC probe.
- F2 LED one-blink-off does not prove Linux entered or stopped before the kernel.
- AXP515 timeout does not prove the PMIC part is absent or that the bus must be slowed.
- A Linux image built successfully does not establish byte identity with the stock image or hardware boot success.
- GPU acceleration and HDMI scanout are separate systems.

## Decision

Prioritize **REF-1 / REF-2**, preserving firmware/boot environment. Then validate UART and clock definitions **read-only** while exporting the actual 0.2.7 hybrid patch/assembler. Delay rail, DDR and PHY tuning until the reference passes and the kernel-entry stage is observable.
