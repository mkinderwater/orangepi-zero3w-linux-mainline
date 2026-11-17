# A733 Linux 6.18 RAM-A versus RAM-B diagnostic image test

## Known previous tests

The clean upstream Linux 6.18.19 kernel **reached the real early UART console on hardware**, reporting `Machine model: Xunlong Orange Pi Zero 3W (UART-only validation)`, then panicked `Failed to allocate page table page` when its board DTB had no `/memory` node. The 8250 early console is therefore known to work. Boot0 and U-Boot report **1 GiB physical DRAM starting at 0x40000000**. The BL31 monitor occupies the `0x48000000..0x48ffffff` 16 MiB range.

Subsequent manual U-Boot FDT edits were corrupted by serial-console paste errors. One test added contiguous RAM and an FDT reservation, then output ended at BL31 handoff, without Linux output; a later split-RAM manual edit failed. **No controlled RAM-A/B result is yet known.** Prepare compiled DTBs, not serial FDT edits.

## Controlled variants

| Item | RAM-A | RAM-B |
| --- | --- | --- |
| Kernel | same 4,562,952-byte clean UART Image | identical |
| Initrd | same raw tiny diagnostic gzip | identical |
| Firmware | existing fresh control image, untouched | identical |
| RAM `reg` | contiguous 1 GiB at `0x40000000` | 128 MiB at `0x40000000` plus 880 MiB at `0x49000000` |
| BL31 | explicit `/reserved-memory/bl31@48000000` with `no-map` | excluded entirely from usable RAM spans |
| MMC0 / PMIC / UHS | disabled | disabled |

Both variants preserve the original UART0 board settings and upstream A733 v3 SoC DTS, and leave runtime bootargs/initrd control to existing proven stage-two script.

`scripts/build-a733-ram-ab-images.py` uses `cpp`, `dtc` and `fdtget` to validate both memory layouts, reserved-memory behavior, and disabled MMC0/R-I2C0. It confirms exact input control-image SHA256 `3bb7d274d5e5110189d240b555fd959481f2a855314f86695abf838b5c252145`, clones that existing 2 GiB image into **two independent new files**, and uses `mtools` to replace only the DTB inside the FAT partition at known offset sector 65536. It reads back the DTB and verifies its SHA256. No loop mount, no kernel rebuild, no original-image mutation, and no physical SD writes.

```bash
cd /root/orangepi-zero3w-linux-mainline
git pull --ff-only
python3 scripts/build-a733-ram-ab-images.py \
  --source /root/opi3w-m2-work/a733-dts-v3-source-check-v1/linux \
  --control /root/opi3w-m2-work/a733-clean-fresh-v1.img \
  --output /root/opi3w-m2-work/a733-ram-ab-v1
```

Expected output files:
- `a733-ram-ab-v1/a733-clean-uart-ram-a-v1.img`
- `a733-ram-ab-v1/a733-clean-uart-ram-b-v1.img`
- `a733-ram-ab-v1/report.json`

**Boot:** the existing vendor U-Boot scans MBR entry 1 while the new FAT partition is entry 2, so autoboot will still not reach stage two. At U-Boot prompt, select `mmc 0:2` and manually source the FAT root `boot.scr`, one line at a time:

```text
setenv devtype mmc
setenv devnum 0:2
setenv prefix /
fatload mmc 0:2 0x47000000 boot.scr
source 0x47000000
```

The same unchanged stage-two script loads the clean kernel and raw diagnostic initrd and calls `booti`. **Only the DTB differs.** Boot one variant at a time on a separate test SD card, record the complete serial output, and do not run `saveenv`. Do not interpret FDT load or BL31 handoff alone as Linux entry. Success criterion: Linux's early console passes the previous page-table panic and can execute PID1. Whether U-Boot adds/chops RAM fixups during handoff remains a separate concern.

Linux HDMI/KMS is not part of these tests. The vendor display's previous success and firmware-held HDMI pixels do not demonstrate a working HDMI console in the new kernel.
