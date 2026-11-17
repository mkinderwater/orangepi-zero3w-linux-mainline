# Try8A: skip initial UART0 console termios reconfiguration

**Status: staged source builder; hardware result unknown. Diagnostic only.**

## Source evidence

The exact pinned 6.18.19+ source was inspected:

- `drivers/tty/serial/8250/8250_port.c:3389` `serial8250_console_setup()` parses console arguments and calls `uart_set_options(port, port->cons, baud, parity, bits, flow)`.
- `drivers/tty/serial/serial_core.c:2218` `uart_set_options()` directly calls `port->ops->set_termios(port, &termios, &dummy)` during native console registration.
- `drivers/tty/serial/8250/8250_port.c:2742` `serial8250_do_set_termios()` computes integer/fractional divisors and later writes UART LCR/divisor, IER/FCR, etc. It can be invoked during the console setup path.
- Earlycon prints readable 115200 UART0 output with the firmware-programmed configuration. Native console prints garbage beginning immediately after `2500000.serial: ttyS0`.
- Try5b measured UART `clk=22153846`, `LCR=03`, `IER=00`, `LSR=60`, `MCR=03`, `USR=06` before the switch. Try6 observed raw APB_UART=0. U-Boot PLL_REF `0xF8675F00` accounts for the 22.15 MHz reported rate, so do not call it a Linux clock arithmetic error.

## Independent hypothesis A

Initial native console `uart_set_options()` reconfigures divisor, LCR, interrupt state or related registers incorrectly and disrupts the firmware-working UART. Test by **skipping only** its `port->ops->set_termios` call when (1) a real console `co` is supplied and (2) `port->mapbase == 0x02500000`. No other UART or ordinary post-console termios operation is bypassed.

This test is intentionally **not** a production fix. It can leave software-recorded baud/format divergent from hardware, may affect kernel console internals, and will not prevent other native console setup code from changing registers. Test output may still corrupt. It does not enable MMC/PMIC/HDMI.

## Build

```bash
cd /root/orangepi-zero3w-linux-mainline
git pull --ff-only
python3 scripts/build-a733-uart-console-preserve-try8a.py \
  --source /root/opi3w-m2-work/a733-uart-try5b/linux \
  --config /root/opi3w-m2-work/a733-uart-try5b/obj/.config \
  --output /root/opi3w-m2-work/a733-uart-try8a \
  --jobs 4
```

Builder validates exact source function, writes changes only to new source clone's `serial_core.c`, checks `8250_dw.c` is byte-identical, and compiles to `a733-uart-try8a/obj/arch/arm64/boot/Image`. Do not claim compiled until run on WSL.

When compiled, clone known-good RAM-A 2 GiB image, replace **only** FAT `/mainline/Image` at byte offset 33,554,432, verify readback SHA256 and write only the **test** SD. Keep original RAM-A card and image as control. U-Boot boot script must be started manually from `mmc 0:2`.

## Interpretation

- If output remains readable across native `ttyS0` takeover, that supports (but does not prove) initial `set_termios()` reprogramming as trigger. Then independently instrument the precise divisor and LCR/IER write order to find the real fix.
- If output still corrupts, the initial `set_termios()` path may be innocent or other console registration behavior also alters hardware. Proceed to independent hypothesis B, exact register write order during native console registration, with instrumentation outside console printk locks.
- A silent BL31 handoff cannot be classified as test pass or failure because intermittent silence occurs with known-good RAM-A too.
- A readable shell and input are final goals, **not** guaranteed by preserving firmware UART settings.

## Source files

- [Try8A source builder](../scripts/build-a733-uart-console-preserve-try8a.py)
- [Measured findings](2026-11-17-a733-uart-verified-findings-try5b-try6.md)
- [Try7 divisor investigation](2026-11-17-a733-uart-divisor-try7.md)
