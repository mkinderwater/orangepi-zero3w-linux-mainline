# RAM-B Clock Test 01: fixed 24 MHz vs hypothesized 26 MHz

**2026-11-17. Source-controlled and NOT hardware-tested.**

Purpose: verify the leading UART root-clock hypothesis without rebuilding the kernel or changing the working firmware. This is a **pre-rebuild validation experiment**, not the final RAM-B clock implementation.

## Inputs and safeguards

- Exact RAM-A candidate DTB SHA-256: `b63266e8d73611abd2fb693b101f05373134c32ea5784c0899cf969eb00473a1`.
- Original `/osc-clk/clock-frequency` is 24,000,000 Hz.
- Current A733 CCU connects PLL_REF's `hosc` to this fixed node, while the true physical oscillator value is still unconfirmed.
- `/home/ram-b-clock-test` is the output directory. Only a **copy** of the DTB is modified.
- No bootloader files, flash partitions, kernel source, or initramfs are touched.

## Run on Debian

```sh
git fetch origin
git switch work/ram-b-stable-baseline
git pull --ff-only
bash scripts/ram-b-clock-test.sh
```

This emits:

```text
/home/ram-b-clock-test/sun60i-a733-orangepi-zero3w-ram-a-control.dtb
/home/ram-b-clock-test/sun60i-a733-orangepi-zero3w-ram-b-26mhz-test.dtb
/home/ram-b-clock-test/SHA256SUMS
/home/ram-b-clock-test/DTB-CHANGE.diff
/home/ram-b-clock-test/MANIFEST.txt
```

The script aborts if the source DTB SHA is wrong or if more than the one intended clock-frequency property changed.

## Hardware caution and order

**Do not deploy the 26 MHz candidate on the primary working card until checking the board's RTC DCXO selection and PLL_REF hardware register state.** The 24/26 ratio explains `uartclk=22153846` with the right register configuration, but neither the actual crystal nor its firmware divider settings were proven by the DTB alone.

Read-only U-Boot evidence (not a register write):

```text
md.l 0x07090160 1
md.l 0x02002000 1
md.l 0x02002538 1
```

Decode against the **pinned A733 RTC and CCU register definitions** before interpreting. If hardware evidence supports a 26 MHz input, boot the test DTB on a **disposable copy** with the unchanged RAM-A `Image` and initramfs, identical command line, and no reloading of the DTB after its selection. Do not use the automatic stage2 loader without adjusting its DTB path, because it reloads the original file.

## Expected evidence

A proper success requires:
1. Linux `uartclk` consistent with verified physical clock and PLL_REF.
2. Clean output *past* native ttyS0 registration; `keep_bootcon` remains identical to the comparison control for this first test.
3. Functional serial RX/interactive initramfs prompt.
4. No unexpected reset for the observation period.
5. Exact artifact SHA-256 in the test record.

If the clock now reports 24 MHz but UART still corrupts, do not declare the clock hypothesis disproven or proven until the physical divisor and console co-ownership are checked. If rate is unchanged, inspect PLL_REF parent resolution and the actual booted DTB.

This single-variable test is preparatory. The permanent RAM-B patch should model the A733 RTC-detected crystal accurately, verify the unconditional PLL control writes, and rebuild from a clean 6.18.19 worktree.

## Operator generator result (2026-11-17)

- `ram-b-clock-test.sh` completed after correcting Debian `fdtget` integer type from `d` to `u`.
- RAM-A control DTB SHA-256: `b63266e8d73611abd2fb693b101f05373134c32ea5784c0899cf969eb00473a1`.
- 26 MHz candidate DTB SHA-256: `1ff786ed912df7d4b4d19e366b3c968a5e0552c39f58d61a8414514eba141d9d`.
- The generator returned successfully; its single-property diff guard is expected to have passed. Full diff text not independently provided in this result.
- **Hardware oscillator, UART stability and reboot behaviour remain untested for the candidate.** Next gate: U-Boot read-only RTC, PLL_REF and APB-UART register inspection, then controlled boot if consistent.

## U-Boot register evidence: 26 MHz DCXO confirmed by firmware selection

Operator read-only U-Boot observations:

```text
md.l 0x07090160 1 -> 183fb0f7
md.l 0x02002000 1 -> f8675f00
md.l 0x02002538 1 -> 00000000
```

Decoded using the A733 RTC and CCU definitions being audited:

- RTC DCXO bits 15:14 = 2: firmware oscillator selection is **26 MHz**.
- PLL_REF (0x02002000): N field bits 15:8 is 0x5f -> 96; output divider M bits 22:16 is 0x67 -> 104; P bit 1 is 0 -> 1. **26,000,000 x 96 / 104 = 24,000,000 Hz**.
- APB_UART (CCU 0x538): mux bits 26:24 = 0 (sys-24M); divider bits 4:0 = 0 (divide by 1). Expected physical APB UART source **24 MHz**.
- The RAM-A DTB instead provides 24 MHz as the **PLL_REF parent** (fixed `/osc-clk`) and Linux reported `uartclk=22,153,846`. With the above PLL factors, that software rate is exactly `24,000,000 x 96/104`.

**Conclusion:** firmware register state and the RAM-A software clock model are inconsistent. The 26 MHz root-oscillator DTB test is now justified, but stable ttyS0 TX/RX and reboot elimination still require a controlled physical boot. Do not claim the reboot root cause is proven. No register writes were made in this test.

Candidate DTB SHA-256: `1ff786ed912df7d4b4d19e366b3c968a5e0552c39f58d61a8414514eba141d9d`.
