# MMC hardware test record (2026-11-17)

## Baseline
Board Orange Pi Zero 3W A733. Linux 6.18.19+ built Tue Nov 17 09:53:33 CST 2026. Machine model `Xunlong Orange Pi Zero 3W (RAM-A + ramoops diagnostic)`. U-Boot vendor storage read works: GE8QT 238.5 GiB, 4-bit 50 MHz.

## First RAM DT test
`/soc/mmc@4020000`: `status=okay`, `bus-width=4`, `max-frequency=25000000`. MMC controller probe eventually succeeds. Kernel emits `vcc-pf not found, using dummy regulator`, `no support for card's volts`, `mmc0: error -22 whilst initialising SD card`. No Linux SD block device proven.

## Second RAM DT test
Same plus `voltage-ranges=<3300 3400>`, `no-1-8-v`. Same voltage error and `-22` result. Early `-517` deferral is resolved later. Native ttyS0 driver and the boot console both register; UART text corrupts near end before Boot0 starts again. Reset cause unknown.

## Next test
Build OCR-A and capture actual card OCR, host OCR and overlap. Do not change hardware voltage handling until observed values and regulator mapping are checked. OCR-B source is provisional and held pending API validation.

## Original captures
Stored in conversation uploads named `Pasted text(20261117-161958).txt` and `Pasted text(20261117-162334).txt`. These raw UART captures are not published here because long logs contain repeated output and unverified serial corruption. Preserve them as separate evidence if needed.

## Source-tree audit (reported 2026-11-17)

- MMC candidate source trees: `/root/opi3w-m2-work/a733-try9-ramoops/linux`, `/root/opi3w-m2-work/a733-try9-ramoops-v2/linux`, `/root/opi3w-m2-work/linux`.
- All report upstream base commit `4aea1dc4c`; the two try9 trees contain numerous uncommitted board modifications, while the shared tree showed untracked `m2j/`.
- In each candidate, `mmc_select_voltage` starts at `drivers/mmc/core/core.c:1120`, `mmc_of_parse(mmc)` occurs at `drivers/mmc/host/sunxi-mmc.c:1441`, and `mmc_add_host(mmc)` at line 1469.
- Proposed first choice: `a733-try9-ramoops-v2/linux`, pending confirmation against the November 17 RAM-A compiled Image and actual source anchors. **No patch applied, no kernel built or tested yet.**
