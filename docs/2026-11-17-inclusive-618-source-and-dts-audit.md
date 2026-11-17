# Linux 6.18.19 A733 inclusive-kernel integration audit and permanent repair plan

**Target:** Orange Pi Zero 3W (sun60iw2/A733), all board-proven capabilities maintained.  
**Status:** Source/document audit and staged ABI patch; **no new Linux build, SD flash or PF hardware validation**.  
**Evidence:** compiled HBI 0.2.7 Image 8,591,368 B SHA256 `e4b2eff08dfc7e2553cf498def6658515f5f2f1e5e8066d0fcc60a73742069c7`; compiled DTB SHA256 `5c9cd102215183cc56150aab2ce331216bea26d80741cdfc1fb0d95f5818e7b9`; UART 2026-11-17, 6.18 PID1 uname, MMC UHS-II null call, fatal PF voltage-switch panic.  
**Prior full history:** [2026-11-17-full-history-after-uart-mmc-panic.md](2026-11-17-full-history-after-uart-mmc-panic.md).

## Decision

**Keep the existing 6.18.19 kernel as the working engineering base.** UART established its ability to enter Linux, run multicore workqueues, initialize the selected Allwinner BSP platform and execute C PID1. Correct real driver ABI mismatches and preserve board hardware definitions. Do not replace this with an unrelated kernel or hide failures by disabling SD, Wi-Fi, MMC2, voltage switching, MMC core or fatal diagnostics.

**An inclusive kernel is not one that advertises every feature.** It is one that advertises only implemented capabilities while keeping all genuine board devices, safe regulators, functional SDIO, root storage, display, DMA and CPU power management available. Unsupported capabilities are defects, not features.

## 1. Review scope and provenance: what was actually inspected

This audit cross-checked the mainline repository's 2026-11-15 hardware matrix, full boot investigation, M2x summary, hybrid revision notes, BSP import provenance, DTS/DTB and HDMI analyses, PMIC/MMC notes, clock audit, external kernel 7.3 adoption plan, paired legacy-uInitrd tests, new UART log, operator's pasted exact 0.2.7 source lines, and pinned Allwinner BSP, vendor Linux 6.6.98 and Linux 6.18 MMC headers.

**Crucial limit:** The GitHub repository does **not** contain all WSL hybrid source edits, source transformation scripts, exact original kernel build logs, every historical experimental DTS/DTB or binaries. The branch `test/618-hbi-handoff-audit` is 59 commits ahead of `main` at review, primarily new docs/diagnostics. That comparison is **not** a diff of all upstream-to-hybrid changes, nor proof of changes absent from the local 0.2.7 tree. Every untracked change or old patch must be inventoried on WSL before declaring the audit exhaustive.

Run [audit-618-integration-inventory.py](../scripts/audit-618-integration-inventory.py) to collect actual `Kbuild`/`Kconfig`, DTS, patch and vendor MMC definition differences without altering them. Retain the output manifest as a source-of-truth artifact before any patching.

## 2. Patch classification: what stays, what goes, what needs proof

| Item / history | What was changed or proposed | Actual proof | Permanent disposition |
| --- | --- | --- | --- |
| Stock Zero 3W Boot0/BL31/SCP/U-Boot | Keep board DRAM training and original monitor | Original vendor 6.6 and HBI legacy 6.18 serial boots | **KEEP immutable**. Never substitute generic A733 or 4 Pro firmware |
| Mounted-ext4 /boot dense normalization | Preallocate real file data and verify hashes after mkfs | Historic 0.7.0 sparse-hole incident; later reference boot | **KEEP** builder safety and audit; do not mistake it for 6.18 driver fix |
| A2V two-stage U-Boot script | Preserve original env import, FDT addr/resize, overlays | A2V/VBI vendor HW PASS, HBI 6.18 UART PID1 | **KEEP** proven path; no speculative return to fragile handoff experiments |
| Load-address relocation | Earlier 41MiB M2 kernel overwrote executing boot script at 0x43100000; stage2 moved to 0x46000000 | Real older static overlap; HBI 0.2.7 small Image no such static overlap and boots | **KEEP** safe nonoverlap rules, **DO NOT** reapply old 41MiB diagnosis to 0.2.7 |
| Legacy vs raw initramfs | Paired tests with vendor and 6.18 | Vendor legacy boots; 6.18 legacy actually reached PID1 on serial | **SUPPORT both only where proven/needed**; do not identify format as current root cause; prefer one documented tested production handoff |
| Old HDMI and PL7 assumptions | Used splash/LED to infer Linux non-entry | F1 ran Debian under frozen splash; HBI legacy ran PID1 with no observed 3-flash | **REJECT** as negative boot markers; serial uname is proof |
| Hybrid 0.2.0-0.2.4 UART and Kconfig edits | Correct multiline C translation, UART API/RS485, missing DMA, TWI, SHMEM, EARLYCON, PMIC | 0.2.7 build and runtime TWI/UART initialization | **KEEP legitimate API/dependency integration**, but re-audit applied diff; eliminate obsolete translator hacks |
| Hybrid 0.2.6-0.2.7 DE/TCON/HDMI/PHY | Integrated Allwinner display stack and fixed `DRM_CLIENT_SELECTION` build error | Drivers linked, TCON probed in UART; no Linux HDMI display PASS | **KEEP conditional subsystem**, verify source compatibility, binding and physical modeset before declaring HDMI working |
| Early CCU / CPUS / MSI Lite critical gates from Linux7.3 | Proposed added `CLK_IS_CRITICAL` and CCU patches | Original vendor CCU already sets many ignore-unused/critical flags; UART reports `clk: Not disabling unused clocks`; 6.18 starts | **DO NOT import 7.3 patches wholesale**. Keep existing vendor clock model, audit actual `msi_lite2` gap if subsequent evidence arises |
| 24 MHz oscillator and PB9/PB10 UART (M2cx) | Two simultaneous changes | Failed splash-only test; UART now works with 0.2.7 | **DROP as boot fixes**. Retain board-verified UART pinmux; don't change oscillator without measured clocks |
| BL31 reservation, kernel relocation, entry instrumentation | Suspected 6.18 failed before `start_kernel` | UART BL31 -> Linux -> PID1 | **CLOSE as cause of current crash**. Preserve reservation and binary validator, remove planned entry hacks |
| Vendor 6.6 DTS root name `orangepi-4-pro` | Proposed accurate `xunlong,orangepi-zero3w` | Compiles, exact identity change not physically tested | **CORRECT board identity** in clean board DTS while preserving SoC fallback; one isolated hardware test |
| Hybrid DTS root lacks `arm,sun60iw2p1` | Replacement used `allwinner,sun60i-a733` only | F1 vendor HDMI driver explicitly fails root compatible match | **PERMANENT DTS FIX CANDIDATE:** include `arm,sun60iw2p1` fallback with accurate Zero3W identity. Compile/test under 6.18; not an MMC fix |
| Vendor PMIC limited AXP8191 experimental patch | Early three-rail implementation and restricted writes | Build only; superseded by imported full BSP PMIC | **QUARANTINE** `patches/experimental/axp8191-m2cb.patch`; never silently apply to 6.18 production |
| Removing `vmmc-supply` (other developer's interim workaround) | Worked around deferred probe temporarily | Other project later restored regulator; F1 real root/SD depends on regulator | **REJECT**. Maintain DC1SW2/CLDO5 phandles and power sequencing |
| MMC disable / low SD clock DTS in M2o, M2 tests | Disabled MMC0 or capped probe speed | Offline/DTS or inconclusive splash tests | **DO NOT CARRY** into production board DTS. Use validated speed constraints only |
| `sunxi-dis-signal-vol-sw` MMC1 | Vendor DTS property for Wi-Fi SDIO | Present in currently compiled DTB; Wi-Fi 6.18 not yet validated | **PRESERVE pending SDIO validation**, not a generic MMC0 fix |
| Disabled MMC3, enabled MMC2 with legacy erase property | Vendor board DTS status/caps | UART 6.18 kernel exposes runtime crash; dtb read confirms statuses | **KEEP hardware topology pending physical population audit**; fix driver ABI, not disable controllers to conceal bugs |
| Old vendor MMC `HC_ERASE_SZ` `caps2` BIT(9) | Added in `bsp/drivers/mmc/sunxi-mmc.h`, set for legacy `mmc-high-capacity-erase-size` | **Exact ABI collision confirmed** with Linux 6.18 `MMC_CAP2_SD_UHS2` BIT(9). Enabled MMC2 property and null-call observed | **FIX source permanently**: remove obsolete assignment/definition, retain MMC2 and erase support through current core semantics; check remaining legacy flags |
| Old vendor `CACHE_CTRL`, `PACKED_RD/WR/CMD` flags | 6.6-specific backfilled caps with BIT(1), BIT(12), BIT(13) | Existing definitions observed; no upstream 6.18 equivalent established | **AUDIT AND REMOVE/REMAP obsolete semantics** only after inspecting all consumers. Do not invent replacement bits |
| PF auto voltage bank handling type4/type10 | SoC-version-dependent registers and polarity | `sunxi_pconf_set` warning, fatal vendor panic, distinct descriptors | **REAL OPEN BUG**. Independently inspect exact revision, register offset/bit and 1.8V/3.3V feedback; don't suppress panic or force PMIC voltage |
| A733 Linux7.3 two-bit pin-bank voltage patch 6039 | Different upstream pinctrl implementation | No direct compatibility proof for imported vendor BSP | **REFERENCE ONLY** for A733 bank masks; never bulk apply into vendor pinctrl |
| SDIO CMD52, TWI AXP515, RTC, TCON warnings | Runtime subsystem logs | Evidence of individual warnings; not proven cause of SD/MMC0 PF fatal | **TRACK separate issues** after MMC0 stability |
| Grouped-target GNU Make 4.4 patch | Tried as vendor 6.6 source-build workaround | Did not repair Kconfig rerun | **REJECT** failed workaround |
| GT9xx Kconfig path and cedar-ve O= Makefile corrections | Fixed reproducible vendor 6.6 build defects | Both vendor control and identity builds completed offline | **KEEP scoped to 6.6 source builder**; apply to 6.18 only if same defect exists, don't import gratuitously |
| Linux 7.3 A733 DTSI, IRQ/CCU/MMC driver backports | External platform alternatives | Other-board source research, no isolated hardware proof on our 0.2.7 | **REFERENCE ONLY**, selected individual changes need independent evidence |

## 3. Permanent MMC ABI repair, not workaround

Actual compiled files from operator and donor BSP:
- `bsp/drivers/mmc/sunxi-mmc.h`: `#define MMC_CAP2_HC_ERASE_SZ (1 << 9)`.
- `include/linux/mmc/host.h` 6.18: `#define MMC_CAP2_SD_UHS2 (1 << 9)`.
- `bsp/drivers/mmc/sunxi-mmc.c`: `mmc-high-capacity-erase-size` property sets the obsolete bit.
- Compiled DTB: `sdmmc@4020000` SD, `sdmmc@4021000` SDIO, `sdmmc@4022000` eMMC all `status=okay`; MMC2 has obsolete property, MMC3 also has it but `status=disabled`. No MMC0/MMC1 property.
- Actual UART: Oops `pc=0`, `lr=sd_uhs2_power_up+0x58`, in `mmc_attach_sd_uhs2`.

This is a concrete incompatible backfill, not an argument for disabling UHS-II in the Linux core. The **initial triggering controller** is strongly implicated as MMC2; confirm with host-specific log or `caps2` probe. The historic high-capacity erase indication was not proof that the board actually has eMMC fitted.

**Staged patch:** [0001-sunxi-mmc-drop-obsolete-cap2-erase-alias.patch](../patches/linux-6.18/0001-sunxi-mmc-drop-obsolete-cap2-erase-alias.patch). Removes obsolete `caps2` assignment and macro while retaining real card negotiation and SD/MMC host. Not applied to live WSL tree or hardware-tested. Don't treat `git apply --check` as an actual physical pass.

**Completeness gate:** audit *all* vendor `MMC_CAP2_*` definitions against 6.18 and uses, plus `MMC_CAP_*`, `MMC_TIMING_*`, `MMC_PM_*` and modified `struct mmc_host_ops` callbacks. A silent bit alias may remain outside the first grep. Confirm core handles erase geometry and discard without the obsolete host flag. Missing modern equivalents are recorded unsupported, not assigned random free bits.

## 4. PF pinctrl voltage panic: isolated and safe investigation

`bsp/drivers/pinctrl/pinctrl-sunxi.c`:
- `sunxi_pconf_set` handles `PIN_CONFIG_POWER_SOURCE` 1800/3300.
- A733 `auto_power_source_switch=true`.
- `sunxi_power_auto_switch_pf` uses readback status `power_mode_val_reg` and `BIT(bank*2)`; calls `panic` when voltage state disagrees.
- SoC-version selector `sun60iw2_get_soc_ver` chooses `SUNXI_PCTL_HW_TYPE_4` or `TYPE_10`; type10 has a distinct layout and opposite status polarity.
- Current PF warning traced from `sunxi_mmc_signal_voltage_switch`, `pinctrl_select_state`.

**No PF production patch yet:** read-only audit SoC revision, actual descriptor, status/control register map and voltage-switch requests; print observations through serial. A successful kernel staying alive after suppressing the panic **does not establish electrical safety**. Do not change PMIC voltage blindly. Confirm whether failure occurs at 1.8V downshift or 3.3V restore, which controller invoked it, and whether a second controller was concurrently probing.

## 5. DTS and DTB: intended inclusive model

The board DTS should be a faithful hardware description, not a collection of prior escape hatches:

- Root: accurate board `xunlong,orangepi-zero3w` with vendor BSP fallback `arm,sun60iw2p1` where drivers still match it. Include any genuinely required SoC compatibility string only when its bindings are verified.
- RAM: vendor 512MiB source with U-Boot runtime fixup to actual installed RAM. No hardcoded 1GiB or 12GiB.
- Secure firmware: keep BL31 reservation `0x48000000..0x49000000` and known-good firmware prefix.
- PMIC: AXP8191/AXP515 nodes and proven SD regulator phandles; preserve supply relationships. Don't mask bad PMIC behavior by deleting regulators.
- MMC0 SD: PF0-PF6, clock/detection and validated SD and UHS-I modes. Do not disable SD high-speed modes merely to avoid current pinctrl panic without measured root cause.
- MMC1 SDIO: preserve Wi-Fi enable/IRQ/power signals; do not equate CMD52 timeouts with mandatory permanent disabling.
- MMC2 and MMC3: preserve authentic board nodes/status, but verify installed storage hardware and exact per-variant population. A missing physical device is not a reason to write a false UHS-II capability.
- HDMI/DE/TCON: retain actual vendor binding, root compatible and supply dependencies; validate DRM connector, HPD/EDID and modeset independently from boot.
- LED: preserve PL7 mapping, but do not treat startup flashes as a boot-stage oracle if its driver/pinctrl is not verified.
- Overlays and FDT fixup: keep hardware data and original boot script semantics; track the **compiled final DTB**, not only source DTS.

A `dtc` warning is a quality finding but not by itself a kernel execution failure; classify actual `reg` cells, phandles, graph endpoints and required fields separately.

## 6. Controlled build series and acceptance

1. **Freeze audit manifest now**: source hashes for mainline, donor BSP and hybrid 0.2.7, exact `.config`, `Kbuild`, `Kconfig`, all DTS/DTSI sources and built DTB, every applied patch file and `git status`. Compare against historical source and image artifact hashes. Reconcile untracked files before applying any patch.
2. **Kernel U**, from exact 0.2.7: apply **only** the source-correct removed-MMC-cap2-alias patch. Confirm no DTB, pinctrl, PMIC, clock or initrd differences. Boot UART and check the UHS-II Oops independently; PF panic is allowed to remain as an observed failure.
3. **Kernel P**, separately from exact 0.2.7: instrument voltage transition and descriptor selection only. Do not mask errors or write unverified register values. Collect bank, controller, requested voltage, readback, SoC revision, supply status and exact panic point.
4. **Integrate U + verified P fix** after the independent tests show causality. Add source-level regression for host capabilities and a static guard that no vendor obsolete flags collide with Linux 6.18 defined bits. Test all active MMC controllers and accurate root.
5. **Then** board DTS compatibility correction in a separate identified DTB-only experiment, plus external HDMI tests. Rebuild/validate all overlays; no wholesale vendor-to-mainline DTS swap.
6. **Then** regression of PMIC/R-TWI, CPU clocks/PSCI, MMC0 boot root, SDIO Wi-Fi, HDMI/DRM and audio, power/reboot, USB-C, GPIO and thermal, with logs. Keep full-feature aspiration separate from feature validation.
7. Deliver one clean, reproducible patch series plus build/flash tooling; remove source-only one-off experiments from build selections. Maintain historical reports as archived evidence, not instructions applied to production.

**Success gates:** 6.18 correct uname, no null calls, no PF voltage panic, root SD mounted reliably, tested reboot cycles, Wi-Fi association, HDMI actual Linux output, no unsafe PMIC writes, consistent output hashes and full source provenance. Under-test features remain explicitly unvalidated. A passing single PID1 probe is not sufficient for a production image.

## 7. Commands to run on WSL before the next build

```bash
cd /root/orangepi-zero3w-linux-mainline
git pull --ff-only

python3 scripts/audit-618-integration-inventory.py \
  --hybrid /root/opi3w-hybrid-build-0.2.7/linux \
  --mainline /root/opi3w-hybrid-sources-0.1.0/linux \
  --repo /root/orangepi-zero3w-linux-mainline \
  --output /root/opi3w-m2-work/618-whole-integration-audit

cat /root/opi3w-m2-work/618-whole-integration-audit/integration-inventory.md

# Validate patch against actual imported BSP; still does NOT apply it.
cd /root/opi3w-hybrid-build-0.2.7/linux
git apply --check \
  /root/orangepi-zero3w-linux-mainline/patches/linux-6.18/0001-sunxi-mmc-drop-obsolete-cap2-erase-alias.patch
```

If the hybrid source has no `.git` directory, `git apply --check` still parses and checks patch context when Git is installed and run in the source root. Preserve an untouched copy first. Neither `git apply --check` nor this inventory modifies kernel source.

**Do not build or deploy from this audit alone.** The original 0.2.7 kernel is already a proven base; the goal is a maintainable full integration whose real subsystems pass physical tests, not one that simply stops panicking.

## 8. Complete source provenance check after audit tool expansion

The audit tool now supports `--full-core` to hash-compare all hybrid core source files to the exact 6.18.19 reference and `--bsp-reference` to hash-compare the **entire imported BSP tree** against the pinned donor. This is important: a spot diff of `Kbuild`/`Kconfig` alone cannot substantiate an inclusive integration.

```bash
K=/root/opi3w-hybrid-build-0.2.7
R=/root/orangepi-zero3w-linux-mainline
OUT=/root/opi3w-m2-work/618-whole-integration-audit

cd "$R" && git pull --ff-only

# If the pinned BSP checkout is available, set BSPROOT to that actual directory.
# It must contain a drivers/ subdirectory.
BSPROOT=""
args=()
if [ -n "$BSPROOT" ] && [ -d "$BSPROOT/drivers" ]; then
  args+=(--bsp-reference "$BSPROOT")
fi

python3 "$R/scripts/audit-618-integration-inventory.py" \
  --hybrid "$K/linux" \
  --mainline /root/opi3w-hybrid-sources-0.1.0/linux \
  --repo "$R" \
  --full-core \
  "${args[@]}" \
  --output "$OUT"

cat "$OUT/integration-inventory.md"
cd "$K/linux"
git apply --check "$R/patches/linux-6.18/0001-sunxi-mmc-drop-obsolete-cap2-erase-alias.patch"
```

A green `git apply --check` is **patch-context compatibility only**. Do not apply it on the only copy of the working source tree, and do not assume untracked WSL patches have been enumerated until this audit is reviewed. Test with a separately copied worktree, source SHA snapshot, matching `.config`, successful compilation and UART serial log. Compare hashes of resulting Image/DTB with pinned original before flashing.

**Correctness guard:** `MMC_CAP2_HC_ERASE_SZ` was not just a generic experimental definition, it is a collision with an actively meaningful Linux 6.18 flag. Review and remove other obsolete capability flags where no modern API exists. There must be no ad-hoc bit allocation to preserve compatibility.

## 9. Cross-repository MMC architecture comparison and lessons missed

**Checked 2026-11-17.** The exact donor source in `alexcaoys/allwinner-bsp@656a550c826787e7e72fae58ca793df9e0988ac8` contains `#define MMC_CAP2_HC_ERASE_SZ (1 << 9)` in `drivers/mmc/sunxi-mmc.h`. The imported `CONFIG_AW_MMC` driver adds this bit when an active node advertises `mmc-high-capacity-erase-size`. Linux 6.18 reserves the same bit for `MMC_CAP2_SD_UHS2`, but the vendor host ops do not implement `uhs2_control`. UART recorded the matching null-call crash. This collision was inherited during BSP grafting, not fixed by changes to CCU, U-Boot, raw Image headers or initramfs.

Other projects:
- [nickyg666/orangepi-zero3w-mainline AGENTS.md](https://github.com/nickyg666/orangepi-zero3w-mainline/blob/master/AGENTS.md) explicitly documents `CONFIG_MMC_SUNXI` (upstream-style host) and notes that vendor `CONFIG_AW_MMC` is **not set**. Its `sdc0/sdc1/sdc2` DTB nodes were adapted for `allwinner,sun20i-d1-mmc` plus required reset properties. It reports actual Zero 3W userspace and later Wi-Fi tests; it also documents the need to restore `vmmc-supply` after AXP8191/TWI probe was fixed. It did **not** publish a repair to our vendor CAP2 bit collision; selecting another driver avoided its code path.
- [jonas5/Allwinner-A733-kernel](https://github.com/jonas5/Allwinner-A733-kernel) uses the upstream MMC driver in its A733 source/patch plan. Its supported-board notes do not establish a physically validated Zero 3W boot on our exact board/RAM.
- [warpme/minimyth2](https://github.com/warpme/minimyth2) carries A733 additions for upstream MMC/pinctrl, not a demonstrated correction to the vendor `AW_MMC` host. No evidence was found of an upstream fix for this exact imported vendor collision.
- The **absence of a GitHub code-search result is not proof of absence**; the sources' known driver-selection statements are the more important evidence.

**What we missed:** We audited build/link compatibility, hardware phandles, clock registration and loader handoff, but did not reconcile all imported private `MMC_CAP2_*` definitions with current Linux 6.18 ABI. The C compiler sees valid bit arithmetic and cannot reject conflicting meanings. That is an integration-process failure.

**Long-term decision not yet made:** Keep the staged, narrow `AW_MMC` bit-9 repair as **Trial U** for our proven 0.2.7 baseline; at the same time, compare `MMC_SUNXI` as an architectural candidate using identical board support requirements: MMC0 SD boot, MMC1 AIC8800 SDIO with IRQ and safe supplies, MMC2 optional eMMC, UHS-I modes and tuning, CRC/error handling, controller reset, correct DTB bindings, regulator switching, DMA, suspend/resume and stability. Do not disable `AW_MMC` prematurely, remove `vmmc-supply`, or copy another project's DTB wholesale. Choose the permanent host only after measured parity and safe voltage behavior.

**2026-11-17 operator source audit:** The read-only inventory completed with `CAP2_COLLISIONS: 1`, `DTS_CANDIDATES: 0`, `PATCH_FILES: 3`. The zero DTS count describes only the original scanner's path coverage, **not** absence of DTS modifications. A corrected audit must inspect the BSP DTS and built DTB. Review `full_core_comparison` contents from the actual generated JSON before claiming a complete source diff.
