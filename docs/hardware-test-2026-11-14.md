# M2cm physical board control test, 2026-11-14

**Board:** Orange Pi Zero 3W, Allwinner A733. **Image:** `opi3w-6.18.19-m2cm-UNARMED.img` based on working opi-3w-wbuild 0.7.6. **Executed boot path:** vendor 6.6.98.

## Recorded result

```
$ uname -r
6.6.98-sun60iw2
$ systemctl is-active ssh
active
```

Physical observations: HDMI display attached, local login console working. Wi-Fi `wlan0` obtained a DHCP IPv4 address and SSH login succeeded. This confirms M2cm control assembly, bootloader fallback selection and vendor userspace operate together on the physical board.

**Not tested:** experimental Linux 6.18 kernel entry, board-specific PMIC startup under 6.18, MMC root under 6.18, 6.18 network or HDMI driver, and automatic recovery after an experimental boot failure. In particular, a lit vendor HDMI screen is not evidence that experimental DRM works.

## What was preserved in the image

- Existing U-Boot bootloader area; root ext4 starts at LBA 196608 (96 MiB), FAT partition starts at LBA 65536 (32 MiB).
- Vendor boot path: `boot.scr` -> `/boot/uInitrd`, `/boot/uImage`, `/boot/dtb/allwinner/sun60i-a733-orangepi-zero3w.dtb` -> `bootm`.
- Root filesystem UUID, vendor modules, original boot files; installed experimental `Image`, DTB and matching 6.18 modules in parallel.
- Mounted-ext4 `scripts/boot_allocation.py` normalization and dense `/boot` checks. Historical failing 0.7.0 boot involved 347 unallocated 4KiB blocks despite identical logical kernel bytes. The successful normalization also affects journal initialization; do not assert sparse holes alone are a proven root cause.

## Test gate

The experimental `armed` marker was absent. There is no verified bootloader-managed one-shot rollback; a failed 6.18 boot might require a host to edit the card. Keep a separate vendor recovery card and test media.
