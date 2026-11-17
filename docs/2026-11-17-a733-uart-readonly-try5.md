# Try5: read-only A733 UART clock and register diagnostic

## Current proof

Linux 6.18.19+ RAM-A, try3 and try4 all bring up 1 GiB RAM and eight CPUs, unpack the initramfs, and stop producing readable output exactly as `2500000.serial: ttyS0` registers. The user's try4 board subsequently returned to U-Boot; serial capture alone does not establish whether Linux reset or stalled. Try3's UART skip-set-rate / DLF mask and try4's SCP critical gates did not resolve the visible corruption.

`base_baud=1384615` implies `uartclk ≈ 22153840` Hz. This may reflect a valid divider, wrong rate reported by the CCU, or an actual input clock mismatch. It is **not proof** the oscillator is wrong. Linux 6.18 DesignWare driver is known to call `clk_get_rate` and to reconfigure UART during console handoff.

## Try5 output

The script `scripts/build-a733-uart-readonly-diag-618.py` starts from **try4 Linux source**, copies it to a fresh tree and inserts gated, read-only observations for `0x02500000` during the native DesignWare probe:

1. After reading the enabled UART clock, before acquiring/deasserting reset: `pre-reset`
2. After `dw8250_setup_port()`: `post-setup`
3. Immediately before `serial8250_register_8250_port()`: `pre-register`

Each records resolved clock rate, parent name/rate, `uartclk`, IO type, register shift, UART LCR, IER (only when DLAB off), LSR, MCR and USR. The diagnostic does **not** write device registers, toggle DLAB, or access DLL/DLH. It avoids reading IER when DLAB is active and only operates on A733 UART0 with 32-bit shift=2 access.

`pr_emerg` prints before native console registration, so raw captured `A733UARTDIAG` lines can be compared with the downstream corrupted output. Their presence, absence and values give useful checkpoints even without an interactive Linux shell.

### Build

```bash
cd /root/orangepi-zero3w-linux-mainline
git pull --ff-only
python3 scripts/build-a733-uart-readonly-diag-618.py \
  --source /root/opi3w-m2-work/a733-scp-gates-try4/linux \
  --config /root/opi3w-m2-work/a733-scp-gates-try4/obj/.config \
  --output /root/opi3w-m2-work/a733-uart-try5-readonly \
  --jobs 4
```

Output: `a733-uart-try5-readonly/obj/arch/arm64/boot/Image` and `report.json`. Use a fresh clone of the successful RAM-A disk image; replace only `/mainline/Image`, verify SHA256 readback, and flash only a test SD. Preserve the previous RAM-A image and try4 as controls.

### Acceptance

Collect complete boot until after native UART takeover, especially all `A733UARTDIAG` lines. Do not claim the diagnostic itself fixes console output. If the read-only probe shows rate mismatch or unexpected registers, design **two independent competing hypotheses** for the next kernel changes, not an indiscriminate combination of fixes. Confirm whether read-only register snapshots affect output or timing by comparing try4.

### Caveats

Reading UART LSR/USR is used for diagnosis, but even read-only MMIO can have peripheral-specific side effects. This test does not alter mode registers or divisor latches. Be alert for unexpected probe behavior; isolate it from the unmodified kernel.
