# Linux 7.3 assets for our Linux 6.18.19 A733 hybrid

**Decision record, 2026-11-16. Status: PROPOSED, not implemented. No Linux 6.18 hardware PASS.**

This is an engineering adoption plan, **not** permission to merge unreviewed Linux 7.3 code. Preserve working Zero 3W Boot0, vendor monitor/SCP, U-Boot and A2V/VBI handoff controls. Preserve the current Zero 3W PL7 LED, PF6 card detection and exact SD regulator mapping. Do not import the Radxa Cubie A7A DTS or boot firmware.

Source inventory: [Linux 7.x A733 audit](2026-11-16-linux-7x-a733-source-audit.md) and [6.18 cross-project audit](2026-11-16-external-618-deep-audit.md). Upstream core patch collection: [MiniMyth2 linux-7.3/files](https://github.com/warpme/minimyth2/tree/master/script/kernel/linux-7.3/files) with active/disabled selection shown in [Makefile](https://github.com/warpme/minimyth2/blob/master/script/kernel/linux-7.3/Makefile).

## Adoption decision

| Rank | Asset | Reference | Applicability to our 6.18.19 BSP | Classification | Proof / gate |
| --- | --- | --- | --- | --- | --- |
| **P0** | **CCU critical CPUS bus gate** | [6008](https://github.com/warpme/minimyth2/blob/master/script/kernel/linux-7.3/files/6008-clk-sunxi-ng-a733-mark-the-CPUS-bus-gate-as-critical.patch) | Compare 0x5c0 bit 28 `ahb-cpus` ownership with the **actual** vendor `bsp` CCU; avoid late clock disable affecting PSCI | **Adapt concept only**, NOT drop-in upstream patch | Offline map gate register/enable logic, identify whether vendor already retains it. If missing, isolated change and vendor-kernel hardware control |
| **P0** | **MSI-Lite interconnect gates** | [6009](https://github.com/warpme/minimyth2/blob/master/script/kernel/linux-7.3/files/6009-clk-sunxi-ng-a733-keep-the-MSI-Lite-bus-clocks-runni.patch) | Map bus MSI-Lite gates 0x594/0x59c/0x5a4 and AHB/MBUS dependencies against vendor CCU; DMA may be silently inaccessible if gated | Adapt concept only | Independent gate/source review, then narrow test; do not conflate with CPUS fix in same image |
| **P0** | **R-domain/PRCM clocks and reset ownership** | [6002](https://github.com/warpme/minimyth2/blob/master/script/kernel/linux-7.3/files/6002-clk-sunxi-ng-a733-Add-PRCM-CCU.patch), [6003–6007](https://github.com/warpme/minimyth2/blob/master/script/kernel/linux-7.3/Makefile) | Map existing `CONFIG_AW_SUN60IW2_CCU`, `CONFIG_AW_PINCTRL_SUN60IW2_R` and DTB phandles to true consumer/clock providers | **Structural comparison**; do not install parallel clock controller | All clocks used by early GPIO/serial/PMIC have matched, bound providers; compare actual kernel link, not config alone |
| **P1** | **A733 two-bit pin-bank voltage handling** | [6039](https://github.com/warpme/minimyth2/blob/master/script/kernel/linux-7.3/files/6039-pinctrl-sunxi-a733-fix-the-GPIO-withstand-voltage-en.patch) | New upstream pinctrl uses 2-bit per-bank voltage field. Test for equivalent vendor code and valid PL7 supply; premature changes risk GPIO voltage | Adapt only after confirming variant/offsets | PL7 behaviour compared under vendor PID1 LED and 6.18 with other entry evidence; never write blind MMIO or switch rail levels |
| **P1** | **A733 interrupt bank mapping** | [6038](https://github.com/warpme/minimyth2/blob/master/script/kernel/linux-7.3/files/6038-pinctrl-sunxi-fix-EINT-bank-indexing-for-SoCs-with-e.patch) | Fix upstream 7.3 EINT bank indexing when initial bank absent; may not exist in vendor pinctrl | Review for logical equivalent | Audit IRQ parent mappings, avoid changing LED or MMC in same experiment |
| **P1** | **A733 platform DTSI topology** | [6200](https://github.com/warpme/minimyth2/blob/master/script/kernel/linux-7.3/files/6200-arm64-dtsi-allwinner-a733-add-initial-dtsi.patch), [6201](https://github.com/warpme/minimyth2/blob/master/script/kernel/linux-7.3/Makefile) | Cross-check ARM64 CPU nodes/MPIDR, GIC, PSCI method, reserved memory/BL31, timers, root compatibles, CCU clocks and reset phandles | **Read-only DT comparison** first | `dtc` and `fdtget` checks against compiled hybrid/validated vendor DTBs; do not wholesale replace vendor tree |
| **P2** | **MMC controller cleanup, timing, tuning** | [6065](https://github.com/warpme/minimyth2/blob/master/script/kernel/linux-7.3/files/6065-mmc-sunxi-Use-readl_poll_timeout.patch), [6069](https://github.com/warpme/minimyth2/blob/master/script/kernel/linux-7.3/files/6069-mmc-sunxi-Add-A523-clock-phases.patch), [6070](https://github.com/warpme/minimyth2/blob/master/script/kernel/linux-7.3/files/6070-mmc-sunxi-Add-A523-delay-chain-tuning.patch) | 7.3 modifies **upstream `drivers/mmc/host/sunxi-mmc.c`** while our 0.2.7 selected **BSP `CONFIG_AW_MMC=y` and sunxi-mmc-v5p3x**. Nickyg666 reports working `CONFIG_MMC_SUNXI` instead. | **Alternative design**, not a straightforward backport | First establish kernel/PID1 entry, then compare controller DT compatible, `ocr_avail`, AXP8191 supply and timing |
| **P2** | **DMA addressing and IRQ support** | 6045–6048 in [Makefile](https://github.com/warpme/minimyth2/blob/master/script/kernel/linux-7.3/Makefile) | Compare 7.3 `sun6i-dma` to our `AW_DMA` only after execution | Defer | DMA-specific test, independently from MMC |
| **P2** | **Display/HDMI critical gates and graph** | [6022](https://github.com/warpme/minimyth2/blob/master/script/kernel/linux-7.3/files/6022-clk-sunxi-ng-a733-keep-the-display-fabric-clocks-run.patch), [6206](https://github.com/warpme/minimyth2/blob/master/script/kernel/linux-7.3/files/6206-arm64-dtsi-allwinner-a733-Add-HDMI.patch) | F1 boots with a frozen HDMI splash. MiniMyth2 lists 6206 but **comments out that patch** in checked Makefile | Defer HDMI until verified 6.18 kernel entry | Prove headless PID1 first; then display clock and endpoint graph tests |
| **P3** | **USB fabric/SerDes and Ethernet** | [6010](https://github.com/warpme/minimyth2/blob/master/script/kernel/linux-7.3/files/6010-clk-sunxi-ng-a733-keep-the-USB-bus-fabric-clock-runn.patch), 6012–6015, 6085 | The Zero 3W has no onboard Ethernet PHY; our PID1 probe has no USB NIC support. SerDes/PCIe differs by board | Defer | Hardware-matched later USB bringup, not an entry diagnostic |
| **P3** | **GPU/NPU/cpufreq/thermal** | 6016, 6025, 6086–6087, 6209 | Not dependencies of storage-independent PID1 | Defer | Stabilize CPU, memory and peripherals before acceleration |

## P0 action: read-only reconciliation, **no rebuild yet**

**A. Existing hybrid early-platform implementation** (compilation and registration) compared with *7.3 A733 critical clocks and R-domain semantics*.

**B. Vendor U-Boot exact `booti` implementation** compared with *nickyg666 working 6.18's uInitrd legacy handoff* and Armbian vendor `booti` upper-address variant. These are separate hypotheses, not two changes added to one image. The handoff investigation is **not** itself a 7.3 backport; it remains necessary because we have no 6.18 early-entry proof.

On WSL, run without modifying builds:

```bash
K=/root/opi3w-hybrid-build-0.2.7
grep -E '^CONFIG_(AW_SUN60IW2_CCU|AW_PINCTRL_SUN60IW2_R|AW_TWI|AW_DMA|AW_MMC|MMC_SUNXI|CLK_IGNORE_UNUSED|LEDS_GPIO|SERIAL_EARLYCON)=' "$K/build/.config" || true

find "$K/linux/bsp" -type f \( -name '*ccu*.c' -o -name '*pinctrl*.c' -o -name '*clk*.c' \) -print | sort
grep -R -n -E '0x5c0|0x594|0x59c|0x5a4|CLK_IS_CRITICAL|ahb.cpus|msi.lite|cpus.*gate' \
  "$K/linux/bsp/drivers" 2>/dev/null | head -100 || true
```

Compare **actual** clock enable/reset behaviour, not only source names, against 7.3 patches 6008 and 6009. A vendor driver may correctly keep gates open without using `CLK_IS_CRITICAL`. Do not infer a bug from missing symbols.

## P1 action: safely map pinctrl and DTSI

Read 7.3 patches **6038/6039/6200**, compare built hybrid DTB's `/soc` clocks, interrupts, PSCI, reserved-memory and `/leds` phandles against the hardware-proven vendor DTB. Keep the board-specific details from the **vendor Zero 3W**, including LED R_PIO PL7 active-high, SD detect PF6 and true regulators. A donor Cubie A7A/4 Pro DTB is never a direct substitute.

## Two independent hypotheses per future test batch

- **Test H1, U-Boot handoff:** change only the coherent initrd representation and matching `booti` syntax if offline analysis supports that distinction. Exact kernel/DTB/Boot0 preserved. First prove the change with vendor 6.6 control, then 6.18.
- **Test H2, core CCU:** change exactly one proven problematic clock dependency in the kernel **without changing boot script, initrd or DTB**, then try 6.18 and a vendor-behaviour control as appropriate.
- Keep observations and image hashes separately. Never bundle handoff and CCU changes; never infer kernel entry from splash/one LED blink.
- Do not mark 6.18 or 7.3 hardware PASS without positive execution proof.

## Reuse boundaries and source hygiene

- Reuse **facts, algorithms, register maps, documented semantics and tests** immediately.
- Port small, compatible GPL-licensed code only after confirming full license/provenance, prerequisite patches and precise match to Linux 6.18's source/API. Preserve credits and SPDX notices.
- Do not vendor the entire MiniMyth2 patch stack, Linux 7.3 source, board DTB, proprietary firmware, boot0 or an unpinned U-Boot.
- Keep the pinned Linux 6.18.19 source and 0.2.7 baseline immutable; new work uses an explicit experiment branch and full source/config/artifact manifest.
- First-boot LED divergence is recorded separately and **deferred**.

## 2026-11-16 WSL clock-audit output: first actual findings

Operator executed `scripts/audit-618-a733-clocks.py` on `/root/opi3w-hybrid-build-0.2.7`, shared `clock-audit.md`, effective `.config` SHA256 `6a549d0dedfbf28088845fe7262e966a04ad6c72e1e1c1edf209ce7297f3f721`. **OFFLINE REVIEW ONLY**: 230 source files scanned, 446 text hits, no truncation. The report only emits the first 200 excerpts in Markdown and leaves 246 in the local JSON. It primarily matches unrelated Allwinner SoCs; these hits are **not 446 A733 problems**. The actual A733 CCU detailed gate map is not visible in the supplied abbreviated Markdown output.

Compiled config confirms `AW_SUN60IW2_CCU=y`, `AW_PINCTRL_SUN60IW2_R=y`, `AW_TWI=y`, `AW_DMA=y`, `AW_MMC=y`, `AW_MFD_AXP2101=y`, `AW_UART_NG=y`, `LEDS_GPIO=y`, `BLK_DEV_INITRD=y`, `RD_GZIP=y`. `CONFIG_MMC_SUNXI` and `CONFIG_CLK_IGNORE_UNUSED` report **UNKNOWN** because keys are absent from the submitted effective config parsing; UNKNOWN does **not** establish a missing feature. The raw Image SHA and valid ARM64 magic match original 0.2.7; DTB also matches original 0.2.7 and has a status LED.

The imported vendor clock framework contains `#define __SUNXI_ALL_CLK_IGNORE_UNUSED__ 1` and its registration helpers conditionally OR `CLK_IGNORE_UNUSED`. This is an important **alternate clock-retention mechanism** versus Linux 7.3 explicit `CLK_IS_CRITICAL`; however, this macro alone is not proof every relevant A733 gate uses the helper or is registered in our compiled kernel.

**Supplemental direct inspection of pinned donor** `alexcaoys/allwinner-bsp@656a550c826787e7e72fae58ca793df9e0988ac8`, path `drivers/clk/sunxi-ng/ccu-sun60iw2.c` (not yet compared byte-for-byte to our transformed local hybrid):

| Register / bit | Pinned donor gate | Flag |
| --- | --- | --- |
| 0x05C0 / 28 | `cpus-hclk-gate` | `CLK_IGNORE_UNUSED` |
| 0x0594 / 0 | `msi-lite0` | `CLK_IGNORE_UNUSED` |
| 0x059C / 0 | `msi-lite1` | `CLK_IGNORE_UNUSED` |
| **0x05A4 / 0** | **`msi-lite2`** | **`0` (no protection flag)** |
| 0x05C0 / 16 | `msilite0-ahb-gate` | `CLK_IGNORE_UNUSED` |
| 0x05E0 / 29 | `msilite0-mbus-gate` | `CLK_IGNORE_UNUSED` |
| 0x05E0 / 31 | `msilite2-mbus-gate` | `CLK_IGNORE_UNUSED` |
| 0x05C0 / 5 | `de-ahb-gate` | `CLK_IS_CRITICAL` |
| 0x05E0 / 11 | `desys-mbus-gate` | `CLK_IS_CRITICAL` |

The unprotected MSI-Lite2 is a **candidate difference**, not evidence that this clock is used or is disabled in our failed boot. Do not patch it without first checking the hybrid's compiled `ccu-sun60iw2.c`, clock consumers and stage of failure. Also distinguish `CLK_IGNORE_UNUSED` from `CLK_IS_CRITICAL`: they are not identical semantics.

### Focused read-only follow-up on operator WSL

```bash
K=/root/opi3w-hybrid-build-0.2.7
F="$K/linux/bsp/drivers/clk/sunxi-ng/ccu-sun60iw2.c"
test -f "$F" || { echo "Missing exact A733 CCU"; exit 1; }
sha256sum "$F"
sed -n '520,690p' "$F"
grep -n -E 'sun60iw2.*probe|sun60iw2.*init|CLK_IGNORE_UNUSED|CLK_IS_CRITICAL' "$F" | tail -45
```

Review the actual **clock source** before any patch or kernel recompilation. `sed -n 520,690p` should expose specific gates if local source resembles pinned donor; do not assume line numbers if transformed. Then run the independent `audit-618-booti-handoff.py` for the other hypothesis.

**Disposition:** no confirmed Linux 6.18 clock-root cause yet; no source code or hardware change approved.

## 2026-11-16 local hybrid source verification: gate map confirmed

Operator inspected **actual** hybrid build file `/root/opi3w-hybrid-build-0.2.7/linux/bsp/drivers/clk/sunxi-ng/ccu-sun60iw2.c`, SHA256 `6627594bbbfdf3e7883b6f052f78b4e3f8feca91631b44025cb0cb8be57bc199` and showed lines 520–690. The gate definitions agree with the pinned BSP donor previously audited.

| Clock / physical register | Compiled hybrid source | 7.3 patch correspondence |
| --- | --- | --- |
| CPUS HCLK 0x05C0 bit 28 | `CLK_IGNORE_UNUSED` | 6008 retains as critical |
| MSI-Lite0 0x0594 bit 0 | `CLK_IGNORE_UNUSED` | 6009 |
| MSI-Lite1 0x059C bit 0 | `CLK_IGNORE_UNUSED` | 6009 |
| **MSI-Lite2 0x05A4 bit 0** | **`0` unprotected** | 6009 |
| MSI-Lite0 AHB 0x05C0 bit 16 | `CLK_IGNORE_UNUSED` | 6009 |
| MSI-Lite0 MBUS 0x05E0 bit 29 | `CLK_IGNORE_UNUSED` | 6009 |
| MSI-Lite2 MBUS 0x05E0 bit 31 | `CLK_IGNORE_UNUSED` | 6009 |
| USB AHB 0x05C0 bit 9 | `CLK_IGNORE_UNUSED` | 6010 |
| Display AHB 0x05C0 bit 5 | `CLK_IS_CRITICAL` | 6022 |
| Display MBUS 0x05E0 bit 11 | `CLK_IS_CRITICAL` | 6022 |

**Assessment:** Most of the Linux 7.3 gate-retention rationale is already represented in the actual 6.18 vendor BSP. `CLK_IGNORE_UNUSED` prevents disabling unused clocks, while `CLK_IS_CRITICAL` additionally marks clocks as critical; they are not identical. Neither flag proves a gate was enabled, clock registered or runtime PSCI operation succeeded.

MSI-Lite2 is a verified **unprotected source declaration**, but its runtime users, link status and relevance **before PID1** are unverified. Clock cleanup is generally late initialization; do not attribute pre-entry silence to MSI-Lite2 or apply 6009 blindly. The source includes keyed writes to the AHB/MBUS registers (`AHB_MASTER_KEY_VALUE`, `MBUS_MASTER_KEY_VALUE`), so replacing register writes with generic code is unsafe.

**Decision:** defer clock change pending a demonstrated consumer dependency or runtime stage. Continue the separate exact U-Boot `booti`/initrd handoff audit and artifact identity checks. No new kernel, image or SD write. Preserve firstboot LED observation without reopening its deferred investigation.
