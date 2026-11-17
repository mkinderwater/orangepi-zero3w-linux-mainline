# A733 clean 6.18 CCU and pinctrl backport: pinned upstream intake

**Status:** download/intake script committed. Neither CCU nor pinctrl patch series has been applied to or compiled against the pinned 6.18.19 kernel; hardware validation is pending. This does not alter the existing HBI 0.2.7 PID1 image.

## Upstream sources verified 2026-11-17

- CCU v7 **0/8** by Junhui Liu, Message-ID `20261112-a733-clk-v7-0-db7c5451ffa2@pigmoral.tech`, 2026-11-12. Eight patches covering clock/reset bindings, SDM dual patterns, PRCM, PLL, bus/mod clocks, gates and resets. The series is based on 7.4-rc1 and was [applied to sunxi/clk-for-7.5](https://lists.openwall.net/linux-kernel/2026/11/15/635), not backported to 6.18. [v7 cover](https://lists.openwall.net/linux-kernel/2026/11/12/989).
- A733 pinctrl **0/7** by Andre Przywara, Message-ID `20260910133519.459011-1-andre.przywara@arm.com`, 2026-09-10. Seven patches refactor older Sunxi IRQ/MMIO handling, add new A733 register layout, DT binding, R-PIO and main pinctrl driver. Applied for Linux 7.4. [Series](https://lwn.net/Articles/1093640/).
- A733 two-bit voltage-mode follow-up **v3**, Enzo Adriano, Message-ID `20261109-a733-pinctrl-v3@gmail.com`, 2026-11-09. The proposal programs AUTO (01) for all A733 two-bit fields on initialization; it is **not physically verified for 1.8V switching**, and there were earlier conflicting interpretations/alternatives. [Patch](https://lists.openwall.net/linux-kernel/2026/11/10/266). Treat as a *reviewed candidate*, never silently write PF power-mode registers on the Zero 3W.
- A733 PF6 IRQ-mux read correction by Vinicius Pedrosa, Message-ID `20261110130157.112155-1-vinicius.eduardo.pedrosa@gmail.com`, 2026-11-10. Disables `irq_read_needs_mux` because the old helper changes A733 IRQ function 14 to 6; hardware-tested on Cubie A7Z, **not yet on Zero 3W**. [Patch](https://lists.openwall.net/linux-kernel/2026/11/10/2385).

The CCU mainline series includes documented storage MBUS gating and 19.2/24/26 MHz oscillator normalization, both important in the board's earlier failed trials. The pinctrl series has an IRQ bank-offset concern flagged in review; verify before SD card-detect use. Do not assume any of these sources are in the 6.18 baseline.

## Staging, without source modifications

```bash
cd /root/orangepi-zero3w-linux-mainline
git pull --ff-only

command -v b4 || echo "Install b4 from your trusted system environment first"

bash scripts/fetch-a733-upstream-series.sh \
  /root/opi3w-m2-work/a733-upstream-patches-v1
```

The fetch script requires `b4`, `git`, and `sha256sum`; refuses an existing directory, pulls by four exact Message-IDs and records acquired source hashes. If any download or source verification fails, stop, preserve logs and inspect the exact series. **Do not apply downloaded patches to the hybrid source or boot image**.

Then upload `INVENTORY.txt` and the fetched patch mboxes (or a tarball of the intake directory) so we can evaluate actual hunks/dependencies instead of assuming Linux 7.4 patches apply cleanly to 6.18.19.

## Strict backport sequence

1. Confirm CCU v7 eight-patch series and pinctrl seven-patch base plus voltage/IRQ followups were fetched with exact IDs, authors, order and checksums.
2. Compare with **pinned source** `4aea1dc4cad17cd146072e13b1fd404f32b8b3ef`. CCU v7 expects 7.4-rc1 APIs, and pinctrl base expects 7.3-rc1. Treat patch apply or compile failures as missing prerequisites, not excuses to import vendor `bsp/`.
3. Port A733 CCU and A733 pinctrl **independently**, with dedicated Kconfig fragments and DTB-only experimental variants. Do not mix a failed CCU trial with pinctrl.
4. Investigate two-bit PF voltage register handling before enabling pinctrl GPIO supply writes; never force voltage or suppress the older panic.
5. Validate native board UART, SD/MMC0 and PMIC only after clock and pinctrl source dependencies are understood. The clean Kconfig passing does not mean board boot support exists.
6. Keep the legacy verified PID1 image immutable. Build in separate trees and use UART logs as pass/fail evidence.

This intake is a step toward a **clean product kernel**: no historic BSP driver inheritance, separate boot/server/GPU profiles and a canonical verified Zero 3W DTS.
