# Try7: trace actual Linux 8250 selected baud divisor at console takeover

## Facts and corrected clock interpretation

- RAM-A: 1 GiB DRAM at 0x40000000; BL31 16 MiB no-map; all eight A733 CPUs initialize.
- Early UART at 0x02500000 runs with firmware configuration and emits readable 115200 8N1.
- Native `ttyS0` registration produces corrupted bytes reproducibly after the 8250 driver announces the port.
- Try3 A733 skip-clock-rate and DLF mask, and try4 SCP critical-clock protections, did not fix output.
- Try5b measured `clk=22153846 parent=apb-uart parent_rate=22153846 uartclk=22153846 LCR=03 IER=00 LSR=60 MCR=03 USR=06`.
- Try6 measured `APB_UART_RAW=0x00000000` during Linux UART probe, with unchanged 22,153,846-Hz clock report.
- U-Boot measured `PLL_REF 0x02002000=0xF8675F00` and `APB_UART 0x02002538=0`. The PLL reference rate calculates as `24,000,000 * 96 / 104 = 22,153,846.15 Hz`, consistent with Linux. **Do not label 22.15 MHz a CCU calculation error or assume APB_UART=0 implies a 24 MHz output.**

## Instrument the selected divisor, not hardware latches

`scripts/build-a733-uart-divisor-try7.py` copies the built try5b Linux 6.18 source tree and adds a single A733-filtered log to `serial8250_do_set_termios()`, immediately after `serial8250_get_baud_rate()` and `serial8250_get_divisor()`, before taking the port spinlock. The logged value is the *actual quotient selected by the Linux core*, not just a manually modeled quotient. The log also includes the fractional value returned by the driver hook, requested baud and line control byte. It does **not** write or read hardware divisor latches or toggle DLAB.

```text
A733DIVDIAG requested_baud=... uartclk=... quot=... frac=... lcr_selected=... actual_integer_model_baud=...
```

The diagnostic still relies on `pr_emerg` during console setup. If no line appears, it may be a printk sequencing/reentrancy issue; do not infer the callback never ran. It can affect timing, so use only on test hardware. The reported integer baud ignores fractional-divisor effects and is labeled a *model*; `quot` and `frac` are selected values, **not evidence the peripheral accepted the writes**.

## Build and test

```bash
cd /root/orangepi-zero3w-linux-mainline
git pull --ff-only
python3 scripts/build-a733-uart-divisor-try7.py \
  --source /root/opi3w-m2-work/a733-uart-try5b/linux \
  --config /root/opi3w-m2-work/a733-uart-try5b/obj/.config \
  --output /root/opi3w-m2-work/a733-uart-try7-divisor \
  --jobs 4
```

This is source staging and compilation only. The resulting `obj/arch/arm64/boot/Image` is **not** a bootable SD card image. If it links, clone the original successful RAM-A image and replace only FAT `/mainline/Image` using `mcopy -i image.img@@33554432`. Read back and compare hashes before writing the test SD. Keep memory node, BL31, DTB, initrd, firmware and bootargs identical. Vendor U-Boot requires `devtype=mmc devnum=0:2 prefix=/` then sourcing `/mainline/stage2.scr`.

## Acceptance

Record the `A733DIVDIAG` line before `ttyS0` native takeover. If quotient=12 and frac=0, the integer baud model is about 115,385 at 22,153,846 Hz and further investigation should target how hardware writes LCR/DLAB/DLL/DLH. If selected quotient differs or fractional divisor is nonzero, assess the actual serial core and A733 DLF detection before making changes. The remaining competing theories are (1) divisor/LCR/IER register write failure during native registration and (2) kernel console sequencing/reentrancy with otherwise correct divisor. No fix is claimed from this diagnostic.
