# RAM-B Hardware Baseline H0

Date: 2026-11-17. **Status: Partially observed; read-only inventory in progress.**

## Runtime evidence from Orange Pi Zero 3W

Operator's BusyBox shell output:

```text
Linux (none) 6.18.19+ #1 SMP Tue Nov 17 18:54:09 CST 2026 aarch64 GNU/Linux
00:13:54 up 13 min, 0 users, load average: 0.00, 0.00, 0.00
nproc: 8
free: can't open '/proc/meminfo': No such file or directory
mount: no /proc/mounts
/sys/firmware/devicetree/base: No such file or directory
/sys/bus/platform/devices: No such file or directory
```

### Interpretation

- Eight processors and a running AArch64 kernel are directly observed.
- No unexpected reboot appears during this reported uptime, but a 24-hour no-reset baseline is **not** yet proven.
- The absent proc/sysfs paths **do not** prove missing devices or failed probe. The previous initramfs log reported `mount: mounting proc on /proc failed: No such device`. Verify kernel `CONFIG_PROC_FS`, `CONFIG_SYSFS`, and `CONFIG_DEVTMPFS` using the exact RAM-B build output `.config`; do not assume the result from the shell alone.
- BusyBox uptime may use sysinfo rather than procfs; therefore working `uptime` does not mean procfs is mounted.
- Native UART TX/RX works but terminal input/output can interleave. `keep_bootcon` remains enabled and the shell lacks a controlling TTY; distinguish these from baud error by separate tests.

## Previously confirmed clock/boot facts

- RTC DCXO select register at `0x07090160`: `0x183fb0f7` (26 MHz selection under A733 register mapping).
- PLL_REF at `0x02002000`: `0xf8675f00`, factors N=96, M=104, P=1, giving a nominal 24 MHz from 26 MHz input.
- APB_UART at `0x02002538`: `0x00000000`, sys-24M /1.
- 26 MHz corrected test DTB SHA-256: `1ff786ed912df7d4b4d19e366b3c968a5e0552c39f58d61a8414514eba141d9d`.
- Script-enabled kernel Image SHA-256: `67a0a073950bb6c92e2a06e61235e90509ad5d3964703dec70cb4f53e4a339c8`.

## Collection policy

Keep current RAM-B kernel and device tree untouched while conducting H0. Gather all available compiled configurations and decompiled DT data on the Debian host, and defer extra drivers, live `devmem`, destructive reset tests and bootloader changes. Classify each fact as observed, device-tree-described, inferred or unknown.

## Next read-only collection

On Debian, inspect the exact RAM-B build `.config` for `PROC_FS`, `SYSFS`, `DEVTMPFS`, `TTY`, `UNIX98_PTYS`, and `DEVPTS_FS`. Capture current DTB's nodes, phandle relationships, clocks, interrupts, reserved memory, UART pinctrl and hardware status. Do not declare missing hardware merely because no sysfs/procfs interface is currently available.

## Confirmed kernel configuration: diagnostic interfaces absent

Operator checked `/root/opi3w-m2-work/ram-b-script-fix/obj/.config`:

```text
CONFIG_DEVTMPFS=y
CONFIG_DEVTMPFS_MOUNT=y
CONFIG_TTY=y
CONFIG_UNIX98_PTYS=y
CONFIG_ARM64=y
CONFIG_SMP=y
CONFIG_NR_CPUS=512
CONFIG_OF=y
CONFIG_OF_ADDRESS=y
CONFIG_OF_IRQ=y
CONFIG_PINCTRL=y
CONFIG_GPIOLIB=y
CONFIG_REGULATOR=y
CONFIG_COMMON_CLK=y
CONFIG_PSTORE=y
CONFIG_PSTORE_RAM=y
```

`CONFIG_PROC_FS` and `CONFIG_SYSFS` were absent from the enabled `CONFIG_...=...` grep output and correlate with the observed mount failures. Verify the explicit `# CONFIG_PROC_FS is not set` / `# CONFIG_SYSFS is not set` lines if needed. `CONFIG_NR_CPUS=512` is a compile-time limit, not the observed physical CPU count (8). Next candidate: isolated build with only PROC_FS and SYSFS enabled, still using the same 26 MHz DTB and unmodified diagnostic initramfs. This is NOT hardware-tested.
