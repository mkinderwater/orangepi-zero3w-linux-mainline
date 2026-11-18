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

## Hardware test: 26 MHz DTB, Linux 6.18 reaches init then panics (capture 2026-11-18)

**Single-variable test succeeded at its clock-model goal.** Original RAM-A kernel and `uart-diagnostic-initrd.gz` were loaded; replacement DTB `ram-b-26mhz-test.dtb` at 0x44000000 had `/osc-clk/clock-frequency = 26000000`. Bootargs kept `keep_bootcon` unchanged.

Observed:

```text
A733UARTDIAG pre-reset: clk=24000000 parent=apb-uart parent_rate=24000000 uartclk=24000000
A733UARTDIAG post-setup: clk=24000000 parent=apb-uart parent_rate=24000000 uartclk=24000000
2500000.serial: ttyS0 at MMIO 0x2500000 (irq = 15, base_baud = 1500000) is a 16550A
A733UARTDIAG pre-register: clk=24000000 parent=apb-uart parent_rate=24000000 uartclk=24000000
clk: Disabling unused clocks
Freeing unused kernel memory: 320K
Run /init as init process
Failed to execute /init (error -8)
Run /sbin/init as init process
Run /etc/init as init process
Run /bin/init as init process
Run /bin/sh as init process
Kernel panic - not syncing: No working init found.
SMP: stopping secondary CPUs
[333]HELLO! BOOT0 is starting!
```

- `-8` is `ENOEXEC` (exec format error). The diagnostic initramfs' `/init` is not executable as presented to the kernel, e.g. invalid/missing shebang, unsupported binary format, or broken interpreter. The **specific cause must be found by inspecting the archive**, not assumed.
- The kernel progressed to userspace handoff; no late serial corruption is visible in this test. Dual console lines persist because `keep_bootcon` remains present. Native UART **TX during this boot** improved materially; RX and a working interactive prompt remain unverified.
- Subsequent Boot0 follows the panic. It does not identify the reset mechanism. No evidence that the 26 MHz fix eliminates independent spontaneous resets; it eliminates the observed software clock-rate discrepancy.
- **Next:** inspect `uart-diagnostic-initrd.gz` offline. Check archive entries, mode bits, `/init` file type, first bytes, ELF machine/interpreter or shebang and executable dependencies. Build a corrected minimal initramfs, retaining original kernel and 26 MHz DTB for a controlled second test. Then remove `keep_bootcon` separately.
- Preserve raw UART capture separately: `Pasted text(20261118-005013).txt`.

## RAM-B script execution rebuild (operator result, November 17)

Diagnostic initramfs `uart-diagnostic-initrd.gz` SHA-256 `1a68a774c6b47081f338bcc8f595b4a154dbd433293cf3ad1b8df31cc7ac919b`; `/init` is executable shebang `#!/bin/busybox sh`. BusyBox is statically linked AArch64 ELF64. Earlier RAM-A kernel `.config` had `CONFIG_BINFMT_ELF=y`, but `CONFIG_BINFMT_SCRIPT` was not enabled, explaining the observed `ENOEXEC` for `/init`.

Isolated build output: `/root/opi3w-m2-work/ram-b-script-fix/obj`. Configuration reported `CONFIG_BINFMT_ELF=y` and `CONFIG_BINFMT_SCRIPT=y` after `olddefconfig`. Operator reports successful `Image` build and copied it to `/home/Image-ram-b-script-fix`, size approximately 4.4 MiB. SHA-256 `67a0a073950bb6c92e2a06e61235e90509ad5d3964703dec70cb4f53e4a339c8`.

**Next:** Boot corrected kernel with same 26 MHz test DTB and original initramfs, unchanged boot arguments. Expect script `/init` to execute, but stable userspace and reboot-free runtime are **not yet demonstrated**. Preserve the original `/mainline/Image` and boot scripts.

## RAM-B first successful /init shell (operator hardware log)

Image `Image-ram-b-script-fix`, SHA-256 `67a0a073950bb6c92e2a06e61235e90509ad5d3964703dec70cb4f53e4a339c8`, with 26 MHz test DTB and original diagnostic initramfs. Newly built kernel config includes `CONFIG_BINFMT_SCRIPT=y` and `CONFIG_BINFMT_ELF=y`.

```text
Freeing unused kernel memory: 320K
Run /init as init process
mount: mounting proc on /proc failed: No such device
BusyBox v1.37.0 (Debian 1:1.37.0-6+b9) built-in shell (ash)
sh: can't access tty; job control turned off
~ #
```

**Observed hardware PASS:** initramfs script now executes, BusyBox ash shell prompt appears, serial output readable into userspace. **Pending:** prove typed UART RX commands work; inspect `CONFIG_PROC_FS` (likely disabled, not verified), controlling tty setup and devpts/console access; quantify uptime and resets. No LKG promotion yet. Do not conflate the missing proc filesystem with a UART defect.

## Interactive UART TX/RX proved (operator hardware test)

At the RAM-B `~ #` BusyBox ash prompt, typed `echo "RAM-B UART RX/TX PASS"` executed and printed exactly `RAM-B UART RX/TX PASS`. Typed `uname -a` executed and returned `Linux (none) 6.18.19+ #1 SMP Tue Nov 17 18:54:09 CST 2026 aarch64 GNU/Linux`. Thus native serial input and output both work at the shell level. `cat /proc/uptime` returned `sh: cat: not found`; do not mistake this for proof about kernel uptime because the `cat` applet is not found and the earlier `/proc` mount failed with `No such device`. Stability time and reset-free endurance remain untested.

## Hardware interactive uptime observation

Operator showed BusyBox ash shell on the actual Orange Pi, typed commands, interrupted a sleep with Ctrl+C, then obtained:

```text
/bin/busybox uptime
00:04:36 up 4 min, 0 users, load average: 0.00, 0.00, 0.00
```

BusyBox 1.37.0 applet list contains `cat`, `uptime`, `sleep`, `cttyhack`, `mount`, `stty`. `cat` is not linked in the shell's PATH, but can be invoked as `/bin/busybox cat`. Output indicates a live shell at 4m36s reported uptime with no reset shown during that observation. The 60-second sleep command was interrupted, **so it is not a completed 60-second test**. The proc mount error and lack of controlling tty remain unresolved; diagnose kernel `CONFIG_PROC_FS` and initramfs setup separately. This is a **working userspace checkpoint**, not yet LKG endurance certification.
