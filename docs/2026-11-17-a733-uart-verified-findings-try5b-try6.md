# A733 Zero 3W Linux 6.18 UART handoff: measured findings

**Date:** 2026-11-17  
**Hardware:** Orange Pi Zero 3W, Allwinner A733 (sun60iw2), 1 GiB DRAM, vendor Boot0 / SCP / BL31 / U-Boot 2018.07  
**Kernel:** clean upstream-based Linux 6.18.19+, board-specific UART-only DTS and upstream A733 CCU/pinctrl patches  
**Finding status:** kernel memory and CPU startup proven; native UART console corruption reproducible; cause **not proven**.

## Executive finding

The native UART handoff consistently corrupts terminal output immediately after `2500000.serial: ttyS0 at MMIO 0x2500000 (irq = 15, base_baud = 1384615) is a 16550A`. It does not occur during earlycon, when firmware-configured UART0 works at 115200 8N1. Try3's A733 UART skip-rate and DLF mask fixes and try4's SCP clock protections did not restore readable output.

A read-only try5b driver instrument produced reproducible measurements *before* native port registration:

```text
A733UARTDIAG pre-reset: clk=22153846 parent=apb-uart parent_rate=22153846 uartclk=22153846 type=3 shift=2 LCR=03 IER=00 LSR=60 MCR=03 USR=06
A733UARTDIAG post-setup: clk=22153846 parent=apb-uart parent_rate=22153846 uartclk=22153846 type=3 shift=2 LCR=03 IER=00 LSR=60 MCR=03 USR=06
printk: legacy console [ttyS0] disabled
2500000.serial: ttyS0 at MMIO 0x2500000 (irq = 15, base_baud = 1384615) is a 16550A
<unreadable UART bytes>
```

The reported clock is a `clk_get_rate()` framework value, **not a physical frequency measurement**. The exact value is compatible with 288 MHz / 13 = 22,153,846.15 Hz, but this numerical fit is not proof of the source or divider.

The expected `A733UARTDIAG pre-register` line was not present in the captured excerpt. That alone cannot establish whether its code executed. Review console log sequencing and diagnostic placement before making claims based on its absence.

## Demonstrated baseline

| Test | Verified result |
| --- | --- |
| Original UART-only DTS without `/memory` | Linux entered earlycon and panicked `Failed to allocate page table page` |
| RAM-A board DTS | 1 GiB RAM at `0x40000000`, BL31 `0x48000000..0x48ffffff` reserved `no-map`; kernel initialized all eight CPUs and unpacked initramfs |
| UART native probe with RAM-A | Output becomes corrupt at `ttyS0` takeover; PID1 and interactive input unverified |
| RAM-B | Built, no comparable successful hardware run documented |
| UART0 DT status disabled | No visible Linux output after BL31; not evidence of a kernel crash |
| Try3 | SKIP_SET_RATE and contiguous-DLF-mask backport compiled and booted; console still corrupt |
| Try4 | SCP firmware critical gates staged and booted; console still corrupt |
| Try5b | Read-only snapshots before UART takeover confirm 22,153,846 Hz report and stable UART registers; console still corrupt |
| `clk_ignore_unused` | A run remained silent after BL31, so effect on native UART takeover **not evaluated** |
| HDMI disconnected | Same intermittent BL31 silence occurred; HDMI not established as cause |

The intermittent silence immediately after BL31 occurred on both control and patched kernels. Other boots using the same RAM-A configuration reached all eight CPUs; do not conflate silent handoff with the reproducible native-console corruption.

## Measured UART register state

| Field | Value | Interpretation and limit |
| --- | --- | --- |
| `clk_get_rate(baudclk)` | 22153846 Hz | Kernel common-clock-framework report |
| `clk_get_parent()` name | `apb-uart` | Linux clock parent; same reported rate |
| UART `uartclk` | 22153846 Hz | Used by 8250 baud calculations |
| `type` | 3 | `UPIO_MEM32` in this kernel |
| `regshift` | 2 | Word-spaced UART register offsets |
| LCR | `0x03` | 8N1, DLAB clear at snapshot |
| IER | `0x00` | Interrupts disabled before registration |
| LSR | `0x60` | THR and transmitter empty |
| MCR | `0x03` | DTR and RTS set |
| USR | `0x06` | No BUSY bit at snapshot |

These snapshots are read-only and were taken *before* the native console was activated. They cannot show the final DLL/DLH divisor or clock transition during registration.

## U-Boot APB_UART register

At the U-Boot prompt, `md.l 0x02002538 1` returned:

```text
02002538: 00000000
```

The upstream A733 CCU/U-Boot description identifies `0x02002538` as the `APB_UART` mux/divider register. Based on that layout, zero selects the 24 MHz oscillator without division. This is a **pre-Linux** observation, not a simultaneous measurement with try5b's 22,153,846 Hz Linux clock report. Linux may change the clock configuration or derive the parent rate differently. Do **not** claim the silicon runs at 24 MHz during kernel takeover without reading the register then.

If the actual UART input were 24 MHz while Linux computed divisors for 22,153,846 Hz, a nominal divisor of 12 would imply approximately 125000 baud rather than 115200. This is a **testable hypothesis**, not an established finding. No manual custom-baud terminal test was completed, since terminal/adapter support is uncertain and the handoff is too fast.

## Two competing hypotheses for try6

**H1: Clock metadata or clock-programming mismatch.** Hardware mux/divider is configured for 24 MHz, but Linux's clock framework reports 22.153846 MHz. Native console registration uses a divisor based on the reported rate and transmits at an incorrect actual baud. Test by reading raw `APB_UART` `0x02002538` *during the Linux probe*, without changing baud, CCU or UART configuration. Decode actual clock source/divider from the upstream driver.

**H2: Native divisor/control programming bug.** Linux's reported clock and hardware configuration are consistent, but `serial8250_register_8250_port()` or `set_termios()` changes the UART divisor or LCR/IER in a way incompatible with A733. Compare behavior around the takeover only after H1's clock values are known. Avoid changing DLAB in the running console merely to read DLL/DLH.

Upstream A733 serial v2 work describes DLF false-detection at `0xc0` (A733 RS485 control) and skip-set-rate quirks, but try3's targeted 6.18 adaptations did not resolve this board's output. The newer BUSY-safe divisor architecture was **not** backported; do not claim the full upstream patch series is integrated.

## Current next experiment: try6

`scripts/build-a733-uart-raw-clock-try6.py` stages a kernel-only diagnostic from **try5b** that reads physical `0x02002538` during native UART initialization. It reports the raw register and a *modeled* divisor for 115200. It does not change the UART clock or read/write DLL/DLH. Firmware, RAM-A DTB, stage2, and initramfs are unchanged.

```bash
cd /root/orangepi-zero3w-linux-mainline
git pull --ff-only
python3 scripts/build-a733-uart-raw-clock-try6.py \
  --source /root/opi3w-m2-work/a733-uart-try5b/linux \
  --config /root/opi3w-m2-work/a733-uart-try5b/obj/.config \
  --output /root/opi3w-m2-work/a733-uart-try6 \
  --jobs 4
```

**Status:** script committed, not confirmed compiled or run on hardware. Do not treat its expected `APB_UART_RAW` output as observed evidence. Note that the local try5b source was repaired to add `<linux/clk-provider.h>` after a compiler failure; the underlying source tree should contain that correction before building try6.

## Controlled SD test procedure and guards

Build from a copy of the pinned source; copy the working RAM-A image into a new 2 GiB file and replace only FAT `/mainline/Image` (FAT offset 65536 sectors × 512 bytes = 33554432 bytes). Read the kernel back and verify its SHA256. Never overwrite the RAM-A control. The vendor U-Boot still scans partition 1 while the test FAT partition is MBR 2. At prompt, set `devtype=mmc`, `devnum=0:2`, `prefix=/` and source `/mainline/stage2.scr` from `mmc 0:2`. Manual `booti` must include `fdt addr` and `fdt resize 65536` or U-Boot can fail with `FDT_ERR_NOSPACE`.

Do not claim Linux HDMI works based on firmware HDMI logs. Do not infer Linux success from BL31's `Next image address` alone. Do not enable MMC0, PMIC, or voltage switching as part of UART isolation.

## Primary project links

- [RAM-A original DTS](../dts/sun60i-a733-orangepi-zero3w-ram-a.dts)
- [Try3 targeted UART script](../scripts/build-a733-uart-618-targeted.py)
- [Try4 SCP-clock protections script](../scripts/build-a733-scp-clock-gates-618.py)
- [Try5 read-only UART script](../scripts/build-a733-uart-readonly-diag-618.py)
- [Try6 raw CCU read script](../scripts/build-a733-uart-raw-clock-try6.py)
- [Earlier UART research](2026-11-17-a733-uart-upstream-v2-integration.md)
