# RAM-A DTB clock evidence and RAM-B correction gate

Date: 2026-11-17. Status: **source-side wiring confirmed; physical oscillator not yet proven.**

## Exact RAM-A DTB

Path on operator build host: `/root/opi3w-m2-work/a733-try9-ramoops-v2/sun60i-a733-orangepi-zero3w.dtb`

SHA-256: `b63266e8d73611abd2fb693b101f05373134c32ea5784c0899cf969eb00473a1`

Extracted with `dtc -I dtb -O dts`:

```dts
osc-clk {
    compatible = "fixed-clock";
    #clock-cells = <0x00>;
    clock-frequency = <0x16e3600>; // 24,000,000 Hz
    phandle = <0x03>;
};

clock-controller@2002000 {
    compatible = "allwinner,sun60i-a733-ccu";
    reg = <0x2002000 0x2000>;
    clocks = <0x03 0x04 0x00 0x04 0x02 0x04 0x01>;
    clock-names = "hosc", "losc", "iosc", "losc-fanout";
};

rtc@7090000 {
    compatible = "allwinner,sun60i-a733-rtc", "allwinner,sun50i-r329-rtc";
    reg = <0x7090000 0x400>;
    clocks = <0x08 0x17 0x03 0x08 0x00>;
    clock-names = "bus", "hosc", "ahb";
    #clock-cells = <0x01>;
    phandle = <0x04>;
};
```

RAM-A driver `ccu-sun60i-a733.c` uses `CLK_HW_INIT_PARENTS_DATA("pll-ref", hosc, ...)` with `hosc = { .fw_name = "hosc" }`. Therefore PLL_REF takes the DT-supplied **fixed 24 MHz input**, not an RTC-detected DCXO output.

Native Linux UART was observed to report `uartclk=22153846` Hz. Arithmetic `24000000*12/13=22153846.15` Hz exactly matches this *software rate*. If actual board DCXO is 26 MHz and firmware normalizes PLL_REF to 24 MHz, Linux's reported rate would be incorrect, but **that physical premise is still a hypothesis**.

### RTC and board distinction

An RTC node's compatible and clock output cells do **not** prove Linux has registered a working A733 RTC CCU provider or connected its detected crystal rate to PLL_REF. The inspected RAM-A source had no A733 RTC CCU driver file.

### Other historical DTB SHA-256

- `a733-ram-ab-v1/a733-ram-a/sun60i-a733-orangepi-zero3w.dtb`: `b39aa0a21c94b59037230f2b3b42984490b09e7495c06f9627061c9e12faedf3`
- `a733-ram-ab-v1/a733-ram-b/sun60i-a733-orangepi-zero3w.dtb`: `ed8389e81c2025277bbbc89ff899a1a5bddde010bbf1a704fe77a391c7adab6e`

These differ from each other and from the latest RAM-A DTB. **Do not swap among them without a property diff and hardware-tested identity.**

## Next gates

1. Verify physical oscillator selection and PLL_REF divider configuration, preferably from safe read-only bootloader registers; do not alter PLL registers.
2. Build a **single-variable** test DTB using an accurate hardware-proven oscillator source. Keep kernel, bootloader and initramfs identical to RAM-A control for the first test.
3. Compare native `uartclk`, register divisor and clean serial TX/RX after handoff; separately measure reset/uptime.
4. Integrate correctly modeled RTC/DCXO into a minimal and reviewable RAM-B build. Audit fourteen-PLL probe writes independently; never delete/retain them blindly.
5. Promote LKG only after controlled cold/warm boots and 24h stable operation.

No kernel or DTB fix has been built or hardware-tested as part of this note.
