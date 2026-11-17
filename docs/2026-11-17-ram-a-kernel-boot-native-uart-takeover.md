# RAM-A first successful upstream 6.18 boot: native UART takeover isolation

## Hardware evidence (November 16/17 2026)

The first RAM-A DTB boot progressed well past the original `Failed to allocate page table page` panic. Kernel: Linux 6.18.19+, native A733 CCUs probed, 1 GiB reported as `1000292K/1048576K available`, GICv3 initialized, PSCI v1.1, **8 CPUs online**, initramfs unpacked. The DT confirmed reserved BL31 `0x48000000..0x48ffffff` 16 MiB `nomap`. No memory fault observed. The panic was caused by omitted RAM node in earlier UART-only DTB.

The serial capture becomes binary garbage precisely after the native DesignWare/8250 UART driver takes over:

```text
Serial: 8250/16550 driver, 4 ports, IRQ sharing disabled
printk: legacy console [ttyS0] disabled
2500000.serial: ttyS0 at MMIO 0x2500000 (irq = 15, base_baud = 1384615) is a 16550A
<garbage>
```

This suggests, but does not yet prove, clock/divisor change at native serial probe. The `base_baud = 1384615` implies roughly 22.15 MHz input clock if multiplied by 16. Do not assert kernel panic or that PID1 ran; neither is supported by the captured text. User cannot type after corruption. Native UART needs isolated testing.

## New independent earlycon-only image

`dts/sun60i-a733-orangepi-zero3w-ram-a-earlycon-only.dts` preserves RAM-A 1 GiB, BL31 no-map, oscillator, and all other hardware configuration. **Only difference is `&uart0 { status = "disabled"; };`**. Earlycon uses preconfigured UART registers directly; native 8250/DW serial must not probe UART0. UART input and a login shell are **not expected** with the native driver disabled. This is a printk progress diagnostic, not a usability build.

`scripts/build-a733-ram-a-earlycon-only.py` compiles the DTB, validates both memory and BL31 and UART0 status against the *binary* DTB, creates a new image from the successful RAM-A image and patches only the FAT DTB, reads back hash and writes report.json. It never changes the RAM-A input.

```bash
cd /root/orangepi-zero3w-linux-mainline
git pull --ff-only
python3 scripts/build-a733-ram-a-earlycon-only.py \
  --source /root/opi3w-m2-work/a733-dts-v3-source-check-v1/linux \
  --ram-a-image /root/opi3w-m2-work/a733-ram-ab-v1/a733-clean-uart-ram-a-v1.img \
  --output /root/opi3w-m2-work/a733-ram-a-earlycon-only-v1
```

Image output: `a733-clean-ram-a-earlycon-only-v1.img`. Write only this new image to a test SD. The vendor U-Boot still requires manual boot FAT mmc 0:2:

```text
setenv devtype mmc
setenv devnum 0:2
setenv prefix /
fatload mmc 0:2 0x47000000 boot.scr
source 0x47000000
```

Stage-two retains `earlycon=uart8250,mmio32,0x02500000 keep_bootcon`, so the early console should print beyond native UART registration and toward PID1 without a clock reprogram. Acceptance: no garbage at previous switchover, capture complete kernel initialization or error. No UART typing should be expected after Linux starts.

## Next engineering test

If this produces readable end-to-end output, isolate the cause of the native UART takeover: actual serial input clock vs DT-provided clock rate, UART reset state, CLK_UART0 parent and rate, DW baud divider, and native pinctrl. Make one controlled fix per build and retain disabled-UART as a reference. Do not enable MMC/PMIC as part of UART isolation.
