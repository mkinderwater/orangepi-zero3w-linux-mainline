# A733 Zero 3W minimal device-tree evidence

Date: 2026-11-17. Source inspection only. **No validated board DTB or microSD boot.**

## Confirmed addresses and interrupts

| Block | Physical address | Register size | IRQ | Upstream compatible |
| --- | --- | --- | --- | --- |
| Main CCU | `0x02002000` | `0x2000` | n/a | `allwinner,sun60i-a733-ccu` |
| R-CCU | `0x07010000` | `0x340` | n/a | `allwinner,sun60i-a733-r-ccu` |
| Main PIO | `0x02000000` | `0x600` | SPI 69,71,73,75,77,79,81,83,85,87 | `allwinner,sun60i-a733-pinctrl` |
| R-PIO | `0x07025000` | `0x410` | SPI 198,200 | `allwinner,sun60i-a733-r-pinctrl` |
| UART0 | `0x02500000` | `0x400` | SPI 2 | Validate upstream `snps,dw-apb-uart` |
| MMC0 | `0x04020000` | `0x1000` | SPI 161 | `allwinner,sun60i-a733-mmc`, `allwinner,sun20i-d1-mmc` |
| AXP8191 PMIC | `0x36` on vendor I2C PMU bus | n/a | vendor NMI parent, not yet ported | Upstream AXP318W possible, not yet proven |

The vendor CCU clock inputs are named `hosc`, `losc`, `iosc`. Verify actual upstream CCU driver clock-parent requirements instead of copying the vendor inputs.

## Verified upstream CCU IDs

- `CLK_MMC0=140`, `CLK_BUS_MMC0=141`, `RST_BUS_MMC0=34`.
- `CLK_BUS_UART0=151`, `RST_BUS_UART0=42`. Vendor-specific `CLK_UART0` cannot be copied.
- `CLK_BUS_I2C0=158`, `RST_BUS_I2C0=49`. Main PMIC vendor bus location requires separate inspection; it may be an R-domain I2C controller.
- Binding headers: `include/dt-bindings/{clock,reset}/allwinner,sun60i-a733-ccu.h` and corresponding `-r-ccu.h`.

## MMC0 wiring and safe first-pass configuration

- Vendor PF0, PF1, PF3, PF4 and PF5 grouped as data/control pins, PF2 as separate pin group. Card detection uses PF6, active-low with pull-up, but the exact supported upstream GPIO-cell convention and debounce semantics need checking.
- Vendor node had two pinctrl configurations: 3.3 V and 1.8 V. **Do not copy vendor `power-source=<3300>` or `<1800>` without verifying upstream pinctrl ABI and register behavior.**
- Vendor MMC0 properties `sd-uhs-sdr50`, `sd-uhs-ddr50`, `sd-uhs-sdr104` and maximum 150 MHz must not enter first-pass DTB. Start with **3.3 V, at most 25 MHz** for initial SDR/legacy card enumeration, then raise clock only after verified stable reads. Keep `no-1-8-v` and *no* UHS capabilities.
- Vendor MMC0 supply: `vmmc-supply` from PMIC DC1SW2 (upstream SWOUT2 candidate), 1.8 V CLDO5 references are vendor-specific properties, not supported upstream `vqmmc` selection.
- Vendor DC1SW2 is always on and depends on DCDC1 through `swin-supply`; upstream AXP318W SWOUT2 currently has NULL upstream supply name. Resolve before using this live.
- The upstream A733 pinctrl driver uses table-driven `sunxi_pinctrl_dt_table_init`; lack of literal PF pin names in its source is expected. We must inspect pinmux encoding and upstream A523 example before guessing the numeric function.
- Previously encountered PF bank voltage panic from hybrid BSP is not fixed by a successful source build.

## Remaining information needed for a *minimal and defensible* DTS

1. Vendor board exact UART0 active/sleep pinctrl definitions and their upstream mux function numbers, especially serial-console pins.
2. Vendor board actual PF pin group defaults and card-detect PF6 binding.
3. PMIC parent I2C controller register, IRQ, clock/reset and pinctrl definition. Confirm whether it is R-domain I2C.
4. Linux 6.18 A733 CCU clock inputs, GIC/timer and root oscillator nodes.
5. PMIC silicon identity and regulator parent behavior. **No automatic alias or rail programming.**

Do not generate a boot claim until DTB compile/schema review, real board serial and SD enumeration validation.
