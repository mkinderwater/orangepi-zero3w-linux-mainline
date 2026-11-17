# A733 Zero 3W: full historical trial reconciliation after the UART breakthrough

**Evidence cutoff:** 2026-11-16, serial capture reported 2026-11-17 UTC.  
**Board:** Orange Pi Zero 3W, 1 GiB LPDDR4, vendor Zero 3W Boot0/U-Boot.  
**Status:** **Linux 6.18.19 hybrid 0.2.7 PHYSICALLY REACHED PID1**. Crashed during MMC/card voltage negotiation. **Not a stable boot or root-mount PASS.**

This document supersedes **all earlier interpretations of a frozen Orange Pi splash as Linux 6.18 non-entry**, but does not alter the historical observations. Sources: original November 15 investigation, M2x summary, boot-chain and hardware matrix, hybrid build lineage, PMIC/MMC review, F1 source findings, 6.18 legacy-uInitrd paired experiment, and operator's November 16/17 **UART log**. The full UART text was uploaded in the conversation and is not embedded here; sanitized excerpts below preserve exact evidentiary strings.

## 1. Decisive new physical result

The UART log includes:

```text
290300 bytes read       # legacy uInitrd: 64 header + 290236 compressed data
8591368 bytes read      # exact hybrid 0.2.7 kernel file size
171337 bytes read       # exact hybrid 0.2.7 DTB size
## Loading init Ramdisk from Legacy Image at 43300000 ...
Data Size: 290236 Bytes
Verifying Checksum ... OK
## Flattened Device Tree blob at 43000000
Loading Ramdisk to 49fb9000, end 49fffdbc ... OK
[14.216]Starting kernel ...
NOTICE:  BL3-1: Next image address = 0x41000000
AW BSP version: opi3w-hybrid 0.2.7 / BSP 656a550c8267
CPU: 4 UID: 0 PID: 84 ... 6.18.19-opi3w-hybrid-0.2.7
Hardware name: Orange Pi Zero 3W (opi3w-hybrid 0.2.7) (DT)
...
Freeing unused kernel memory: 320K
Run /init as init process
OPI3W_PID1: START entered PID1 before root/MMC discovery
OPI3W_PID1: UNAME Linux 6.18.19-opi3w-hybrid-0.2.7 aarch64
...
Kernel panic - not syncing: PF voltage switching failed, please be aware!
```

**Consequences of this proof:**
- Valid 6.18 ARM64 entry, MMU, schedulers, clocks sufficient to launch workqueues, pinctrl, SD host and PID1. All "we don't know whether Linux entered" text in earlier notes is **historically accurate only as of that note's date**, **now superseded for THIS legacy HBI test**.
- Bootloader/firmware transferred control successfully; *this test* had no fatal ramdisk/BL31 overlap. Loaded initrd ended at 0x49fffdbc, above the reported BL31 reservation 0x48000000 to 0x49000000. Legacy wrapping worked. Runtime kernel staging at 0x41000000, FDT reported at **0x43000000** and ramdisk staged at **0x43300000**, unlike assumed 0x44000000/0x45000000; actual `bootargs` and environment must be trusted over nominal script comments. Do not assume exact staging addresses carried over to raw/other images.
- **HDMI splash and missing LED three-flash were false negative execution detectors**. Kernel printks appeared on serial; no claim LED hardware driver succeeded. The PF voltage panic and SD workqueue Oops can interrupt the diagnostic and explain absent pulses.
- This log applies directly to the hash-qualified **hybrid legacy PID1** build (image `2f45477b954f669225badb7faf85d81633a58039d1f6b549df76c9b84e7d3819`, Image `e4b2eff08dfc7e2553cf498def6658515f5f2f1e5e8066d0fcc60a73742069c7`, DTB `5c9cd102215183cc56150aab2ce331216bea26d80741cdfc1fb0d95f5818e7b9`). The serial log did not itself include full-image SHA or card readback, so identification rests on payload sizes/versions and the operator's test sequence.
- **Do not retroactively claim raw HBI, M2x, F2 or K2 booted into Linux:** their captures lacked UART evidence.

## 2. Actual kernel defects exposed by UART

### Fault A: UHS-II advertises a capability without a callback, highly probable

```text
Internal error: Oops: 0000000086000005 [#1] SMP
pc : 0x0
lr : sd_uhs2_power_up+0x58/0x68
mmc_attach_sd_uhs2+0x44/0x114
mmc_rescan+0x114/0x264
```

Linux 6.18 `drivers/mmc/core/sd_uhs2.c` checks `host->caps2 & MMC_CAP2_SD_UHS2` before the UHS-II path; `sd_uhs2_power_up` directly calls `host->ops->uhs2_control(host, UHS2_SET_IOS)`. Linux 6.18 `include/linux/mmc/host.h` explicitly requires `uhs2_control` for hosts advertising `MMC_CAP2_SD_UHS2`. `pc=0` and return to `sd_uhs2_power_up` strongly support a null callback caused by **inconsistent host capabilities vs operations**, possibly a BSP 6.6 -> 6.18 bit assignment / cap parsing mismatch. The trace alone cannot prove which specific instruction/struct was null; inspect runtime `caps2`, ops pointer, exact call-site disassembly, DTB advertised caps and vendor host driver initialization to confirm. This Oops occurs inside the MMC workqueue, not necessarily the fatal stopping event by itself.

**Conservative candidate fix:** in the **vendor 6.18 MMC host driver** clear `MMC_CAP2_SD_UHS2` unless a genuine UHS-II implementation exists; do not replace callback by no-op. Guard with positive verification of actual host ops and bit constants. A separate temporary kernel-core assert/trace can expose the invalid capability without changing hardware rails. MMC0 Zero 3W SD should use its supported legacy/UHS-I mode, not UHS-II. Do not globally disable every MMC controller without evidence.

### Fault B: pinctrl PF voltage transition, explicitly fatal

```text
WARNING: CPU: 5 PID: 43 at sunxi_pconf_set+0x55c/0x668
sunxi_pconf_group_set
pinconf_apply_setting
pinctrl_commit_state
pinctrl_select_state
sunxi_mmc_signal_voltage_switch
mmc_set_signal_voltage
mmc_host_set_uhs_voltage
mmc_sd_get_cid
mmc_sd_init_card
...
Kernel panic - not syncing: PF voltage switching failed, please be aware!
```

At least the SD host tries an I/O signalling voltage change and vendor pinctrl refuses or warns. This is **not** proof that 1.8V or 3.3V rail itself is missing. We previously mapped MMC0 PF0-PF5, card detect PF6 and PMIC supplies DC1SW2/CLDO5. The vendor 6.6 DTB boots SD; the *hybrid 6.18* may have a pinctrl driver/voltage-bank state incompatibility or a broken 1.8V switch sequence. Inspect `sunxi_pconf_set` source branch and exact `0x55c` instruction; capture DTB pin states, pinconf arguments and regulator voltage state **before** any voltage or PMIC write. The Linux 7.3 A733 two-bit bank-voltage-control fix (patch 6039) is now a **relevant candidate**, but upstream pinctrl code is not drop-in for the imported vendor BSP. Verify the actual register layout and whether existing BSP already handles PF.

**Do not assume the two faults are independent root causes.** Both arise from asynchronous MMC rescans and may be consequences of one host capability/pinctrl mismatch. We need two isolated theories/tests, not two changes in one kernel.

### Other warnings do not become root cause by proximity

Boot0 initial DRAM training at 1866 MHz failed once, then retrained successfully, reported **1024 MB** and `DRAM simple test OK`. Boot0 GPT errors are compatible with the verified **single-ext4/MBR** image structure, while U-Boot loaded files and Linux executed. Boot0 `fdt returned -9` and SCP/OP-TEE notices were not fatal to this Linux launch. Bootloader HDMI route failure is display-specific. AXP515 probe warning and MMC1 / SDIO CMD52 timeouts deserve later separate review, **after SD/MMC0 stabilizes**. `clk: Not disabling unused clocks` is actually printed; do not resume the unused-clock cleanup hypothesis. The serial trace has simultaneous messages from different CPUs, so text order is not strict causal ordering.

## 3. ALL historical kernel/build families and trials reclassified

The following rows retain the originally reported results. **Only the captured 6.18 legacy PID1 result now has positive 6.18 runtime evidence.**

| Family / trial | Kernel or change | Original observed result | Updated evidentiary meaning |
| --- | --- | --- | --- |
| Vendor stock 1.0.2 | Stock 6.6.98, Boot0, DTB, initrd | HDMI, Debian, Wi-Fi/SSH | **HW PASS** stable control |
| `opi-3w-wbuild` 0.5/0.7.6 | Vendor 6.6.98, FAT+ext4 | Boots with /boot dense allocation | **HW PASS** vendor image, ext4 normalization preserved |
| Stock 0.7.0 defective image | Vendor kernel, sparse ext4 /boot | Splash-only, 347 sparse 4K blocks | Real image assembly issue, NOT 6.18 problem; normalization improved boot |
| M2o | Draft Zero 3W DTS with MMC0 disabled | DTB compiled | **Offline only**, not a valid SD root baseline |
| M2r / M2bp-bx / M2by / M2bz / M2ca-cb | Limited AXP8191, SD rail map, corrected R-TWI PL0/PL1, constrained writes | Build passes after fixes | **Offline only**, limited PMIC source must NOT replace full BSP blindly |
| M2cg / M2ch / M2ck / M2cl | Image tools, modules, DTS target and staged images | Build/package passes | **Offline only**, no kernel entry proof |
| M2cm UNARMED | Conditional vendor 6.6 branch | Vendor boots HDMI/SSH/Wi-Fi | **HW PASS vendor only** |
| M2cp DIRECT | Earlier ~41 MB 6.18 Image, no initrd | Splash | **HW unresolved**, cannot infer non-entry |
| M2cr DIAG / M2cs | BusyBox root discovery, dense-file audit | No runtime log; 121 boot files not sparse | DIAG inconclusive; `blkid` applet missing; dense-file criterion passed |
| M2ct LEGACY & RAW | Alternate ramdisk formats with ~41 MB kernel | Splash | Inconclusive; earlier kernel span **overlapped U-Boot executing script at 0x43100000** |
| M2cv CONTROL | Two-stage U-Boot, vendor 6.6 | HDMI / login / Wi-Fi / SSH | **HW PASS**, second-stage relocation strategy good |
| M2cv DIAG & DIRECT | Two-stage Linux 6.18 | Splash/no logs | Inconclusive: no UART; not evidence of pre-entry stop |
| M2cx DIRECT | Oscillator and PB9/PB10 changes together | Splash | Inconclusive, confounded by two edits |
| M2cy / M2da RAW | Boot script / vendor raw Image | Vendor VFS `unknown-block(0,0)` | **Vendor kernel entry HW PASS** only, root/initrd absent |
| M2db / M2dc | Two-stage and vendor initrd experiments | Offline and splash/no 6.18 proof | Handoff controls; image/kernel/initramfs not always matched |
| A1 | Original vendor image | Vendor OS working | **HW PASS historical** |
| A2, A2M | Rewritten `booti` or `bootm` with vendor artifacts | Splash | These scripts can fail **even with vendor Linux**; confounded semantics |
| A2P, A2V | Stock script preserved, A2V nested stage | HDMI/SSH | **HW PASS**, preserve first-stage env/FDT operations |
| S1, S2 | Delete FDT setup or env import | Splash | **HW FAIL** these two operations must be retained |
| VBN | Vendor raw Image, no initrd, no fallback | VFS panic | **HW PASS kernel entry**, no root |
| VBI | Vendor raw Image, raw gzip initrd | Debian HDMI/login | **HW PASS** raw `booti` interface |
| Hybrid 0.2.0 | UART translator broke multiline literals | Compile failed | Build defect only |
| Hybrid 0.2.1-0.2.3 | UART signature, Kconfig, DMA/I2C dependencies, RS485 field | Compile/preflight failures | Build integration defects fixed subsequently |
| Hybrid 0.2.4 | UART API corrected | Preflight pass | **Offline only** |
| Hybrid 0.2.5 | Full kernel with diagnostics, FAT/ext4 image | Splash; FAT U-Boot traces reached PREBOOT | U-Boot reached handoff; **6.18 runtime unknown** |
| Hybrid 0.2.6 | Added HDMI/DE/TCON/PHY, Kconfig failure | Build failed | Not a runtime result |
| Hybrid 0.2.7 | 8,591,368 B raw Image, vendor BSP graft, original DTB | Complete build | Same kernel **now physically executed**, see new UART proof |
| HBI-027 (raw) | 6.18 0.2.7 + hybrid DTB + raw gzip | Splash, no LED PID1 | **Historical no visible signal**, not proof of non-entry |
| K2 | Hybrid 6.18 without initrd | Splash | No guarantee user-space /init; not entry proof |
| F1 | Vendor 6.6 + hybrid 6.18 DTB | HDMI frozen; SSH root works | **HW PASS vendor/userspace**, **HDMI FAIL** due to root compatible mismatch |
| F2 | Hybrid 6.18 + vendor DTB, no initrd | One LED blink / splash | Inconclusive; cross-version DTB alone cannot isolate early failure |
| VBI PID1 LED | Vendor 6.6 + static C /init | Three startup flashes, ALIVE and HDMI | **HW PASS**, diagnostic validated |
| HBI PID1 LED-v1 (raw) | Hybrid 6.18 + same probe | One flash, splash, no visible PID1 | No UART; **do not infer non-entry** |
| VBI LEGACY PID1 | Vendor 6.6 + legacy `uInitrd` | Boots and HDMI works | **HW PASS** vendor handoff control |
| **HBI-027 LEGACY PID1** | **Hybrid 6.18.19 + exact original Image/DTB, 290236 B probe** | **Serial: U-Boot, Linux, PID1 uname, MMC workqueue Oops, PF voltage panic** | **6.18 KERNEL + PID1 HW PASS; MMC voltage/core FAIL; stable boot FAIL** |
| Vendor rebuilt control/identity 6.6 | Source-pinned vendor kernel and one-line identity DTB | Builds only | **Offline PASS**, no physical proof; original F1 HDMI root compatible finding still applies |
| External nickyg666 6.18.19+ | Different config, mainline MMC_SUNXI | Other developer reports Ubuntu/Wi-Fi/GPU | Published useful counterpart; no need to reproduce exact 26 MB kernel simply to show entry, since our 8.6 MB kernel now enters |
| Jonas5 6.18 and MiniMyth 7.3 | Other A733 boards and framework patches | Different hardware / source | Mine pinctrl/MMC semantics; do NOT import bootloader or entire patch blindly |

**Evidence preservation:** M2x old configurations are not identical to HBI-027; do not treat current MMC bugs as proven in every older kernel. Only the hybrid 0.2.7 legacy-paired serial log identifies this failure by function name and kernel release.

## 4. Earlier conclusions now invalid or downgraded

- **Invalid for the tested legacy HBI-027:** “Linux 6.18 never started”, “early ARM64 entry/missing CCU/BL31 causes current failure”, “the 8.6 MB binary is too small”, “initrd wrapper prevents kernel entry”, “frozen splash indicates U-Boot remained in control”.
- **Actual proved path:** Boot0 -> BL31 -> U-Boot -> ARM64 Image -> `start_kernel` -> MMC/TWI/pinctrl workqueues -> C PID1 -> panic.
- **Still relevant to older builds only:** M2ct 41 MB Image overlapped U-Boot scriptaddr; ext4 sparse-file issue affected a vendor image; HDMI root compatible missing causes vendor F1 display failure.
- **Still open:** exactly which MMC0 capability bits are advertised; whether vendor `AW_MMC` reuses bit positions from older headers, whether card triggers UHS-II incorrectly, PF bank-voltage code path and regulator state, MMC1 SDIO bring-up, HDMI 6.18. The boot log is enough to stop speculative entry hunting.

## 5. Best action sequence: identify, isolate, verify

### Phase A, READ ONLY, no new images

Collect from **actual hybrid 0.2.7**:
1. `grep -Rns -E 'MMC_CAP2_SD_UHS2|uhs2_control|caps2' $K/linux/bsp/drivers/mmc` and `grep -n 'MMC_CAP2_SD_UHS2' $K/linux/include/linux/mmc/host.h`; determine who set the bit, and whether the host provides a handler. Check `SD_UHS2` helper's *exact* linked disassembly and whether the Oops LR corresponds to the callback call.
2. `aarch64-linux-gnu-objdump -d --start-address ...` around `sunxi_pconf_set` to locate source warning at +0x55c; read `bsp/drivers/pinctrl/sunxi/` source, and the DTB's SDC0 voltage pinctrl states. Cross-reference Linux 7.3 patch 6039 **as a hypothesis** only.
3. Preserve the full UART capture and original HBI kernel/DTB/image checksums and source revision. Confirm the tested card or copied image if needed. No PMIC writes.

### Phase B, TWO ISOLATED KERNEL THEORIES

**Trial U (capability-consistency only):** Make only one small change in the **vendor MMC host**: do not advertise UHS-II when `host->ops->uhs2_control` is absent. Prefer a correct capability derivation fix, not core-wide disabling or a fake callback. This may eliminate the `pc=0` Oops, but cannot be assumed to fix PF voltage panic. Keep DTB, script, initrd, PMIC and clocks unchanged.

**Trial P (PF switch only):** Independently, starting again from the exact original 0.2.7 baseline, instrument PF pinctrl voltage transition and report bank, requested voltage, control register and supply state. If the condition proves to be a mismatch in existing vendor PF voltage semantics, make one tightly scoped corrected implementation. Do **not** combine with Trial U until each individual result is captured. A diagnostic-only variant can be executed first, with no rail changes.

**Safety:** If Trial P needs power-rail switching, do not use a guessed register value or replace the PMIC setup. Do not disable fatal warnings blindly. `CONFIG_MMC_SUNXI` from the other project remains a larger alternate implementation for later, after isolated host-capability issues are understood.

### Phase C, controlled acceptance

For each test: compare output Image/DTB hashes, record one changed source unit, run same 290236-byte PID1 probe, boot with UART, capture `uname`, initial UHS-II/PF traces, fatal Oops count, remaining ALIVE lines. Vendor 6.6 reference is the hardware recovery control.

Only once two independent root-cause hypotheses are resolved and **PID1 stays alive without Oops/panic**: enable root mount/MMC0 enumeration, then Wi-Fi/SDIO, HDMI and GPU. A bootloader splash is never a verdict on kernel entry.

## 6. Immediate WSL commands to answer key questions

```bash
K=/root/opi3w-hybrid-build-0.2.7
echo "=== MMC capability definitions and assignment ==="
grep -Rns -E 'MMC_CAP2_SD_UHS2|uhs2_control|caps2[[:space:]]*([|&^]?=)' \
  "$K/linux/bsp/drivers/mmc" "$K/linux/drivers/mmc" "$K/linux/include/linux/mmc" \
  | head -140

echo "=== PF warning / panic source ==="
grep -Rns -E 'PF voltage switching failed|sunxi_pconf_set|sunxi_mmc_signal_voltage_switch' \
  "$K/linux/bsp/drivers/pinctrl" "$K/linux/bsp/drivers/mmc" | head -100

echo "=== Relevant linked locations ==="
grep -E ' (sd_uhs2_power_up|sunxi_pconf_set|sunxi_mmc_signal_voltage_switch|mmc_attach_sd_uhs2)$' "$K/build/System.map"
```

No new kernel is recommended until the specific `caps2` assignment and `sunxi_pconf_set` warning branch are identified.

## 7. Source links and original evidence

- `docs/2026-11-15-hardware-matrix.md`, `docs/2026-11-15-m2x-results.md`, `docs/2026-11-15-hybrid-618.md`, `docs/2026-11-15-pmic-mmc.md`, `docs/2026-11-15-boot-chain.md`.
- `ORANGE_PI_ZERO_3W_LINUX_6_18_BOOT_INVESTIGATION_2026-11-15.md`.
- `docs/2026-11-16-legacy-booti-paired-experiment.md`.
- Linux 6.18 `drivers/mmc/core/sd_uhs2.c` and `include/linux/mmc/host.h`.
- [nickyg666/orangepi-zero3w-mainline](https://github.com/nickyg666/orangepi-zero3w-mainline) for an independent Zero 3W 6.18 implementation, not our kernel's runtime proof.
- [MiniMyth 7.3 A733 patch inventory](2026-11-16-linux-7x-a733-source-audit.md) for candidate bank-voltage semantics.

**Result:** the smallest meaningful next task is **identify the vendor host capability assignment and PF pinctrl warning branch**, not another kernel port or handoff experiment.
