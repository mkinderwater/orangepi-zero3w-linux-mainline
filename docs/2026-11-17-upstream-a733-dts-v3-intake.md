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

## Operator result: upstream A733 v3 SoC DTS source applied

The operator ran `scripts/check-a733-upstream-dts-v3.py` against `/root/opi3w-m2-work/a733-clean-uart-gate-v1/linux`. The script fetched the exact v3 series, validated patch selection, and both `git apply --check` and actual `git apply` succeeded in an isolated source copy:

```text
A733_V3_SOC_DTS_APPLY_PASS: /root/opi3w-m2-work/a733-dts-v3-source-check-v1/linux/arch/arm64/boot/dts/allwinner/sun60i-a733.dtsi
No board DTS, no dtc/schema validation and no hardware boot
```

Next, `scripts/compile-a733-soc-dts-v3.py` preprocesses the actual A733 SoC DTS in place **without altering the kernel tree**, by creating a synthetic non-bootable `/dts-v1/` root in a separate output directory. It uses the original Linux DTS include paths, then runs `dtc` and preserves warnings plus any errors in `report.json`. This checks syntax, include resolution, labels/phandles and basic DT validity. It cannot establish a valid Zero 3W board, runtime driver completeness, schemata or safe PMIC voltages.

```bash
cd /root/orangepi-zero3w-linux-mainline
git pull --ff-only
python3 scripts/compile-a733-soc-dts-v3.py \
 --source /root/opi3w-m2-work/a733-dts-v3-source-check-v1/linux \
 --output /root/opi3w-m2-work/a733-dts-v3-dtc-check-v1
```

Preserve baseline `a2e34a97113b9fff7c64112d46e6f9e131bf2ebe13d9cb1734b4fea49803e311` and do not flash any synthetic DTB.

## 2026-11-17: upstream SoC DTS CPP and DTC PASS; Zero 3W UART-only board DTS staged

Operator ran `scripts/compile-a733-soc-dts-v3.py` on the v3 SoC source; the tool returned `DTC_PASS_SYNTHETIC_ONLY`, with no printed `dtc` warnings. This establishes include/preprocessor/DT compiler success, **not** a Zero 3W DTB or a boot.

Board-specific source added at `dts/sun60i-a733-orangepi-zero3w-uart-only.dts`. It includes the exact v3 upstream A733 SoC DTS and uses only a verified board compatible, console alias for `uart0`, `stdout-path=serial0:115200n8`, a board-level 24 MHz oscillator and `&uart0 { status = "okay"; }`. **No UART pinctrl assignment** is provided because the vendor Zero 3W UART0 pin lists are literally empty and the upstream Cubie PB9/PB10 group is claimed by TWI8 in the vendor Zero 3W configuration. No memory capacity, PMIC node, MMC0 enable, UHS modes, power-source or bootargs override is introduced. The original vendor firmware's memory/initrd fixups remain unverified for this new DTB.

Run `scripts/compile-zero3w-uart-only-dtb.py` against the source tree already containing the upstream A733 SoC DTS:

```bash
cd /root/orangepi-zero3w-linux-mainline
git pull --ff-only
python3 scripts/compile-zero3w-uart-only-dtb.py \
 --source /root/opi3w-m2-work/a733-dts-v3-source-check-v1/linux \
 --board /root/orangepi-zero3w-linux-mainline/dts/sun60i-a733-orangepi-zero3w-uart-only.dts \
 --output /root/opi3w-m2-work/zero3w-uart-only-dtb-check-v1
```

The checker uses `cpp`, `dtc`, decodes the produced DTB, and checks the serial alias, console configuration, disabled MMC0 and disabled PMIC bus. It does not edit original kernel sources or boot media. A pass remains **static only**; do not boot or flash the new DTB without reviewing firmware memory and chosen/initrd overlays plus the exact UART pin function and earlycon UART driver behavior. Note also that upstream v3 UART integration may need a later `8250_dw` runtime patch beyond merely compiling `CONFIG_SERIAL_8250_DW=y`.
