# Clean A733 kernel: replace vendor CCU/pinctrl with upstream patch series

Date: 2026-11-17. **Status:** upstream references and source-reduction decision, not yet applied/compiled.

## Ground truth: actual hybrid source and clean kernel

Operator inspected `/root/opi3w-hybrid-build-0.2.7/linux`. Six vendor files total **6,914 lines**, split:

| File | Lines |
| --- | ---: |
| `bsp/drivers/clk/sunxi-ng/ccu-sun60iw2.c` | 2,908 |
| `bsp/drivers/clk/sunxi-ng/ccu-sun60iw2-r.c` | 397 |
| `bsp/drivers/clk/sunxi-ng/ccu-sun60iw2-cpupll.c` | 351 |
| `bsp/drivers/clk/sunxi-ng/ccu-sun60iw2-rtc.c` | 262 |
| `bsp/drivers/pinctrl/pinctrl-sun60iw2.c` | 2,722 |
| `bsp/drivers/pinctrl/pinctrl-sun60iw2-r.c` | 274 |

Their main source compat strings are vendor `allwinner,sun60iw2-ccu`, `sun60iw2-r-ccu`, `sun60iw2-pinctrl` and `sun60iw2-r-pinctrl`. They rely on imported Allwinner shared BSP infrastructure and `sunxi-sid.h`. Do **not** inherit that infrastructure in the product kernel.

The pinned **clean upstream Linux** source is commit `4aea1dc4cad17cd146072e13b1fd404f32b8b3ef`, with a fresh 6.18 config (573 built-in options, no modules) that enables generic `ARCH_SUNXI`, `SUNXI_CCU`, `MMC_SUNXI`, generic 8250, ext4 and initrd, but lacks explicit A733 CCU/pinctrl/PMIC/MMC support. Kconfig pass does not establish a viable A733 boot.

## New upstream work found, November 2026

1. **A733 CCU and PRCM v7 series, 2026-11-12:** Junhui Liu, `[PATCH v7 0/8] clk: sunxi-ng: Add support for Allwinner A733 CCU and PRCM`. [Series and scope](https://lists.openwall.net/linux-kernel/2026/11/12/989). Main CCU, PRCM, common helpers and binding headers. v7 includes critical MBUS and GIC handling, storage DMA clock gating and PLL parent corrections. This series is explicitly for A733, unlike the 0.2.7 imported generic sun60iw2 BSP. Treat as prime *upstream* CCU donor, subject to pinned-6.18 applicability and needed prerequisites.
2. **A733 pinctrl voltage safety v3, 2026-11-09:** Enzo Adriano, `[PATCH v3] pinctrl: sunxi: use automatic voltage detection on A733`. [Source](https://lists.openwall.net/linux-kernel/2026/11/10/266). A733 has **two-bit** bank voltage-mode fields; upstream one-bit handlers mishandle PF/other banks, and A733 R-PIO differs from A523-R. Proposed fix sets AUTO mode and prevents per-pin incorrect writes. **Not hardware-validated for 1.8 V switching.** Do not confuse this with a proven fix for our independent vendor `sunxi_power_auto_switch_pf()` panic. This patch needs A733 upstream pinctrl base support first.
3. **A733 microSD card-detect pinctrl fix, 2026-11-10:** Vinicius Pedrosa, `pinctrl: sunxi: a733: do not switch the mux to read IRQ lines`. [Source](https://lists.openwall.net/linux-kernel/2026/11/10/2385). Affects PF6 card-detect IRQ behavior; tested on Cubie A7Z with a pending A733 stack. Add as a discrete SD card acceptance test. Do not infer that Zero 3W necessarily uses PF6 without inspecting its actual DTS/wiring.
4. **A733 SoC DTS v3 series, 2026-11-10:** Includes nonvendor A733 UART `"allwinner,sun60i-a733-uart", "snps,dw-apb-uart"`, clock/reset and pinctrl descriptions. [Patch](https://lists.openwall.net/linux-kernel/2026/11/10/787). Start canonical board description from this upstream language, not copied 3,000-line vendor board includes. Board 3W pin assignments/rails still need hardware verification.
5. **A733 PCK600 upstream backport already staged:** `patches/linux-6.18/0002-pmdomain-sunxi-a733-upstream-pck600.patch` and `0003-dt-bindings-a733-pck600-ids.patch`; both passed `git apply --check` against real hybrid 6.18.19, but are not compiled/tested. This is GPU-only, not part of initial PID1 boot.

## Review and integration strategy

**Do not backport Linux 7.4 wholesale.** Prefer the individually identified v7 A733 CCU, A733 pinctrl, necessary DTS, and eventually upstream MMC/PMIC patches with exact prerequisites. Pin sources, commit IDs or Message-IDs and licenses. Audit Kbuild/Kconfig and binding dependencies; apply to an isolated upstream 6.18.19 checkout with an explicit patch sequence and compile checks. If incompatible, port the smallest upstream-supported portion without restoring the BSP.

**Boot-minimal sequence:**
1. Upstream main A733 CCU and R CCU, accurately handle oscillators, PLL and critical GIC/MBUS/SD clocks.
2. Upstream A733 pinctrl + R-pinctrl with A733 two-bit voltage field correction; prohibit speculative PF bank switching.
3. A733 DW APB UART binding + proof of actual UART0 mapping and device serial console.
4. Only then upstream SUNXI MMC0 with verified A733 register/clock/reset/voltage mapping, AXP8191 rail/PMIC and SD root.
5. Canonical Zero 3W DTS containing only verified board hardware, with proper compatible chain. Side projects HDMI, Wi-Fi, GPU and audio later.

**Do not conflate** generic Kconfig enabled with A733-capable hardware drivers, and do not claim these patch series are merged into Linux 6.18 or hardware-proven on our board. Keep the 0.2.7 kernel as a known UART/PID1 handoff reference only.

## Release gate

A build is not releasable merely because it compiles. Require UART PID1, SD/MMC0 enumeration, PF bank voltage stability, ext4/root access and bounded reboot cycling before enabling server or GPU profiles.

Current next action: obtain exact v7 series and pinctrl prerequisites, validate patch application against the pinned 6.18 source, then implement **two independently testable CCU and pinctrl changes** in separate build variants. Preserve their separate failure signals.
