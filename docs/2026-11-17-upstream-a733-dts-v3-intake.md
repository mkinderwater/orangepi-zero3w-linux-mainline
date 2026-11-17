# Upstream A733 SoC DTS v3 intake (November 17, 2026)

**State:** public upstream submission found, source-only Linux 6.18 application pending. No board DTB built and no Zero 3W hardware boot proven.

Public [Linux A733/Cubie A7S v3 cover letter](https://lists.openwall.net/linux-kernel/2026/11/10/704) by Enzo Adriano (sent November 9), Message-ID `cover.1794227241.git.enzo.adriano.code@gmail.com`.

Three submitted patches:
1. DT binding for Radxa Cubie A7S.
2. `arch/arm64/boot/dts/allwinner/sun60i-a733.dtsi`, a 601-line upstream SoC description.
3. `sun60i-a733-cubie-a7s.dts` and Makefile entry, a **different board**.

The SoC file describes 6 Cortex-A55 and 2 Cortex-A76 CPUs, PSCI, ARM timer, GICv3, CCUs, R-CCU, PIO, R-PIO, main and R-domain UART/I2C, MMC0-2. This is preferable to crafting our own undocumented SoC DTS. **Do not transplant the Cubie board DTS into the Zero 3W.** Its SD detect polarity and power topology may differ.

The author reports a November 4 Cubie A7S RAM boot with UART0, PMIC and MMC0 reads on an earlier v2 DT, not a Zero 3W test. The v3 cover calls out runtime dependencies not currently proven in our 6.18 backport: new 8250_dw changes (not merely enabling `CONFIG_SERIAL_8250_DW`), firmware clocks, pinctrl IRQ-bank and voltage-mode patches. The latter voltage handling has deliberately been excluded in our clean build for safety. We must not assume DTB compilation is sufficient for electrical use.

Current operator result: separate upstream DesignWare UART-enabled Image full link PASS, 4,562,952 bytes, SHA256 `a2e34a97113b9fff7c64112d46e6f9e131bf2ebe13d9cb1734b4fea49803e311`. `8250_dw.o` exists, but no UART hardware test.

## Next, source-only v3 SoC DTS intake

```bash
cd /root/orangepi-zero3w-linux-mainline
git pull --ff-only
python3 scripts/check-a733-upstream-dts-v3.py \
 --source /root/opi3w-m2-work/a733-clean-uart-gate-v1/linux \
 --output /root/opi3w-m2-work/a733-dts-v3-source-check-v1
```

This fetches the v3 series using `b4`, checks the SoC patch's single expected file path and applies it in a fresh Linux source copy only. It does not apply the Cubie board DTS or alter the working UART Image. Report status `SOC_DTS_SOURCE_APPLIES_NO_DTB_BUILD` is **not** proof of DTB build or schema validation. If the source passes, separately test preprocessor, `dtc`, phandles and bindings against our exact 6.18 CCU/pinctrl/RTC/PMIC headers. Prepare a Zero 3W board-only DTS with proven 3.3 V properties, valid console routing, no speculative memory size or PF bank voltage switching.

**Keep original 4,562,952-byte UART gate and hybrid PID1 control intact.**
