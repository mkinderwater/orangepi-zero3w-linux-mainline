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
