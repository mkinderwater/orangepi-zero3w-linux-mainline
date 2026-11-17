# Try9: non-UART evidence path using Linux 6.18 ramoops

## Goal

Determine whether the A733 Zero 3W reaches kernel late init and PID1 after native serial becomes unreadable. Avoid assuming broken UART means a dead kernel. Preserve the RAM-A control and do not enable MMC0 merely to write forensic records. Try8A initial native-console termios bypass improves readable output through late initcalls, but subsequent serial corruption and a later Boot0 restart remain unexplained.

## Why pstore / ramoops

Upstream Linux 6.18 has built-in `CONFIG_PSTORE=y`, `CONFIG_PSTORE_RAM=y`, `CONFIG_PSTORE_CONSOLE=y`, and `CONFIG_PSTORE_PMSG=y`. Ramoops stores kernel console messages and panic/oops records in reserved physical RAM without writing SD or using the UART. Documentation: https://docs.kernel.org/admin-guide/ramoops.html and https://kernel.googlesource.com/pub/scm/linux/kernel/git/stable/linux.git/+/refs/heads/linux-6.18.y/Documentation/admin-guide/ramoops.rst

**Major limitation:** this only survives a restart if DRAM contents persist. Vendor Boot0 may retrain/clear RAM or U-Boot may overwrite the chosen region. There is no proven persistence on this board. Do not claim that empty memory disproves Linux execution.

## Experimental reservation

Try9 adds a `compatible = "ramoops"` reserved-memory child at **0x7c000000** with **1 MiB** reserved, `no-map`, `record-size = 0x10000`, `console-size = 0x40000`, `pmsg-size = 0x10000`, `ecc-size = 16`. This is inside confirmed 1 GiB RAM but outside known BL31 0x48000000..0x48ffffff and the observed initrd at 0x49f07000..0x49fff36b. **This does not prove it is outside every unknown Boot0/SCP memory use**. Verify it against the live firmware memory map before a hardware test. Only use on a disposable test image and SD card.

The kernel still uses try8A's console setup preservation; other source and firmware remain the same. Ramoops becomes active during Linux initialization, so its absence does not tell us about failures *before* the pstore driver probes.

## Build independent SD image

```bash
cd /root/orangepi-zero3w-linux-mainline
git pull --ff-only
python3 scripts/build-a733-try9-ramoops.py \
  --source /root/opi3w-m2-work/a733-uart-try8a/linux \
  --config /root/opi3w-m2-work/a733-uart-try8a/obj/.config \
  --soc-source /root/opi3w-m2-work/a733-dts-v3-source-check-v1/linux \
  --control /root/opi3w-m2-work/a733-ram-ab-v1/a733-clean-uart-ram-a-v1.img \
  --output /root/opi3w-m2-work/a733-try9-ramoops   --jobs 4
```

The script hard-checks resulting Kconfig, RAM-A 1 GiB, BL31, new reserved-memory properties, FAT readback hashes, and writes `report.json`. It does not touch the original RAM-A disk image or physical SD card. Expected output `a733-try9-ramoops/a733-try9-ramoops.img`. **Build not yet run by assistant; errors remain possible.**

```bash
cp /root/opi3w-m2-work/a733-try9-ramoops/a733-try9-ramoops.img /home/a733-try9-ramoops.img
```

Flash this image only to a sacrificial SD card after successful compilation and checks.

Boot manually at U-Boot prompt (vendor U-Boot reads SD FAT MBR partition 2, but autoboot scans partition 1):

```text
setenv devtype mmc
setenv devnum 0:2
setenv prefix /
fatload mmc 0:2 0x46000000 /mainline/stage2.scr
source 0x46000000
```

If the board **warm-reboots on its own**, interrupt U-Boot autoboot immediately and do not boot Linux a second time. Record output of:

```text
help pstore
md.b 0x7c000000 0x100
md.b 0x7c0b0000 0x100
```

The second address is only a preliminary **candidate** near the ramoops console area, not a guaranteed offset. Ramoops layout may include ECC overhead and record areas; never interpret arbitrary ASCII at these offsets as a verified record without checking its headers and ABI. Do not use a gigantic UART dump that overwhelms the serial link.

If U-Boot supports `pstore`, follow its help to configure and display the **same** address 0x7c000000 and size 0x100000, record 0x10000, console 0x40000, pmsg 0x10000, ECC 16. Not all vendor U-Boot 2018.07 builds include that command. Do not guess the exact command syntax if missing. Upstream U-Boot pstore command reference: https://docs.u-boot.org/en/v2023.10/usage/cmd/pstore.html

If Linux remains running and a shell becomes available, mount `pstore` and inspect `/sys/fs/pstore` (if kernel config supports it). The initramfs already emits `M2cr: INITRAMFS ENTERED` to `/dev/kmsg` upon PID1 execution, but it also writes `/dev/console`. Ramoops can capture these messages if the driver is active and the kernel console path is alive. **Do not assume the PID1 marker can appear if /init is never executed.**

## Follow-up milestone: SD persistence

Only after independently validating MMC0 using conservative 3.3V and no untested voltage switching should we add an optional diagnostics-only file write. The currently tested UART-only DTS has MMC0 disabled. U-Boot reading the SD card proves nothing about Linux MMC. A dedicated FAT or ext4 trace partition must be clearly isolated from root and have preflight/limits; do not enable the PMIC or change the SD voltage just to log data.

## Acceptance and failure rules

1. Try9 must boot the same RAM-A kernel through native UART and late init, with no unintentional firmware/PMIC changes.
2. If a reset occurs, check RAM records *before another Linux boot*. Any preserved readable console or oops evidence is new insight.
3. If records vanish after Boot0, report retention as unsupported and move to other nonvolatile observations, not a fabricated successful panic trace.
4. Once we have persistent evidence, instrument subsequent UART `set_termios()` calls with a ring buffer (not recursive printk under console locks), separate from pstore initial-console evidence.
5. Keep the original 1 GiB RAM-A control image immutable.
