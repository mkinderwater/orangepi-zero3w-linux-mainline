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
