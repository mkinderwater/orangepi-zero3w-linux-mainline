# A733 CCU v7 and vendor SCP firmware gates: controlled 6.18 test

**Input baseline:** the real successful RAM-A and UART try3 builds. RAM-A has 1 GiB contiguous memory with BL31 `no-map`; Linux 6.18.19+ boots eight CPUs, unpacks initramfs and displays readable printk until native `2500000.serial` console takeover. Try3 adds the A733 SKIP_SET_RATE quirk and DLF mask check; **native console corruption remains**. The unrelated silent BL31 handoffs are not evidence of a kernel crash.

## Upstream source

- Junhui Liu's A733 CCU v7 8/8, Nov 12 2026: https://lists.openwall.net/netdev/2026/11/12/166
- A733 v7 5/8 marks MBUS and GIC clocks critical: https://lists.openwall.net/linux-kernel/2026/11/12/981
- A733 v7 7/8 marks ahb-cpus and mbus-store critical: https://lkml.iu.edu/2611.1/14146.html
- Enzo Adriano's **separate** SCP firmware bus clock protection v2, Nov 12 2026: https://lists.openwall.net/linux-kernel/2026/11/12/3584
- The SCP patch protects **bus-r-msgbox** (PRCM 0x17c bit0) and **bus-r-riscv** (PRCM 0x21c bit0) with `CLK_IS_CRITICAL`. Hardware evidence concerns warm reboot using vendor SCP firmware on Cubie A7S/A7Z. **This is not an established fix for the native UART baud change.**

## Controlled next build

This is **not a full CCU rebase**. Audit all four main CCU critical declarations in the existing try3 tree first; fail closed if anything differs. Create a separate copy of the source, add the two PRCM critical flags if absent, preserve 8250 source byte-for-byte, and compile a fresh ARM64 Image from try3's .config.

```bash
cd /root/orangepi-zero3w-linux-mainline
git pull --ff-only
python3 scripts/build-a733-scp-clock-gates-618.py \
  --source /root/opi3w-m2-work/a733-uart-try3/linux \
  --config /root/opi3w-m2-work/a733-uart-try3/obj/.config \
  --output /root/opi3w-m2-work/a733-scp-gates-try4 \
  --jobs 4
```

Output: `a733-scp-gates-try4/obj/arch/arm64/boot/Image` and `report.json`. Script does **not** write any disk image or hardware storage, and it will fail on an unrecognized CCU declaration. If the report shows all flags already present, do not test a meaningless rebuild.

After build, package to a copy of the *successful RAM-A image*, replacing only the kernel. Read back Image and compare SHA256. Before claiming fix, boot through native UART handoff and verify readable ttyS0 output, `/init` progress and interactive input. Distinguish SCP warm reboot protections from native UART change.

## If native UART still corrupts

Do not keep toggling unrelated clock gates. Inspect pre/post UART clock parent/rate and 8250 divisors (LCR/DLL/DLH), per-port clock data, 32-bit register width and reg-shift; compare with vendor initialization. In the original captured logs, `base_baud=1384615` corresponds to `uartclk=22153840`, which is **not necessarily incorrect**: the UART clock may be divided from a PLL, not sourced directly from the 24 MHz oscillator. More evidence is needed.
