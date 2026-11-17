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

## RAM-A candidate source verification (reported 2026-11-17)

- Preferred tree: `/root/opi3w-m2-work/a733-try9-ramoops-v2/linux`.
- Kernel `make kernelversion`: `6.18.19`; Git base `4aea1dc4c` with local modifications.
- Matching output tree: `/root/opi3w-m2-work/a733-try9-ramoops-v2/obj` (`.config` timestamp 2026-11-17 09:52; `arch/arm64/boot/Image` timestamp 09:53).
- RAM-A boot reported Linux `6.18.19+` built 2026-11-17 09:53:33 CST, strongly consistent with this output. Image hash equivalence not yet verified.
- Exact MMC core: `mmc_select_voltage()` at line 1120; `ocr &= host->ocr_avail` before `if (!ocr)`; host calls `mmc_of_parse(mmc)` at line 1441, then `mmc_add_host(mmc)` at line 1469. Host logs initialized at the end of probe.
- **Next action:** Copy tree and out-of-tree build config before applying diagnostic-only variant A. Verify patch anchors and compiler output; do not overwrite original `Image`.

## MMC-A build artifact reported (2026-11-17)

- User reports `CONFIG_MMC_SUNXI=y` in isolated `/root/opi3w-m2-work/a733-mmc-ocr-A/obj/.config`.
- RAM-A source Image SHA-256: `00c0c75967aa41bd9e31f3db6330502ba220e64ceeecc6b6ba0e015d94a9c23b`.
- MMC-A output Image SHA-256: `65f92c0df0b389fbd5d4a2b3fab1c29a85e67a689b3ae64f4e9ec77c4297f135`.
- Build output exists, hashes differ. Patch installation, `vmlinux` diagnostic-string presence, deployment and hardware results **not yet independently confirmed**.
- Planned on-card filename: `/mainline/Image-mmc-ocr-A`, preserving `/mainline/Image` and stage2 boot script unchanged.
