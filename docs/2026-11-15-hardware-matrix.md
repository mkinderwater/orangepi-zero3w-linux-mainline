# Physical Zero 3W results and test matrix
Evidence cutoff: 2026-11-15; statuses below describe operator hardware reports, not guessed boot stages.

| ID | Kernel / DTB / initramfs | Outcome | Evidence and limits |
| --- | --- | --- | --- |
| Stock vendor 1.0.2 | 6.6.98 / stock / stock | **HW PASS** | Debian login, native HDMI, Wi-Fi, SSH |
| mk vendor reference 0.7.6 | vendor 6.6.98 / vendor / vendor | **HW PASS** | Rebuilt reference image with normalized ext4 /boot; HDMI, SSH, Wi-Fi |
| A2P | stock untouched vendor script and stock partition layout | **HW PASS** | Preserved vendor flow; ext4 /boot normalized |
| A2V | original vendor script as second stage | **HW PASS** | Full vendor boot; second stage at 0x46000000 |
| S1 | A2V without `fdt addr` and `fdt resize` | **HW FAIL** | No confirmed Linux boot; FDT commands must be preserved in tested path |
| S2 | A2V without environment import | **HW FAIL** | No confirmed Linux boot; preserve `orangepiEnv.txt` |
| VBN | vendor raw Image, vendor DTB, **no** initrd, `booti` | **HW PASS (kernel entry only)** | Photographed VFS panic `unknown-block(0,0)`; vendor Linux executes |
| VBI | vendor raw Image + vendor gzip initrd + vendor DTB, `booti` | **HW PASS** | Debian login; vendor raw `booti` handoff proven |
| HBI-027 | hybrid 6.18.19 0.2.7 + hybrid DTB + hybrid initrd | **HW FAIL/OBSERVED** | Splash, red LED solid, no confirmed 6.18 log |
| K2 | same hybrid Image/DTB, no initrd | **HW FAIL/OBSERVED** | Does not boot; removing initrd alone did not restore operation |
| F2 | hybrid 6.18.19 + vendor DTB, no initrd | **HW FAIL/OBSERVED** | Splash; LED starts solid, blinks once then off |
| F1 | vendor 6.6.98 + hybrid 0.2.7 DTB + vendor initrd | **HW PASS (userspace)** | SSH at USB-C Ethernet, vendor banner, ext4 root mount and resize, RAM fixup; **Linux HDMI FAIL**. LED initially heartbeat then off in one run |
| Vendor 6.6.98 rebuilt control | pinned official source + original DTS | **OFFLINE PASS ONLY** | Image, DTB and modules successfully built, not flashed |
| Vendor 6.6.98 rebuilt identity | same source + correct board ID and preserved SoC fallback | **OFFLINE PASS ONLY** | Image, DTB and modules successfully built, not flashed |

## F1 independent proof

Running `uname -a`: `Linux orangepizero3w 6.6.98-sun60iw2 ... aarch64 GNU/Linux`. SSH succeeded at `192.168.24.121` during the test; this address is ephemeral test context, not an instruction to use that network. USB-C Ethernet adapter established a working IP. `/dev/mmcblk0p1` mounted ext4 read-write. Vendor resize began about 11.93 seconds and completed at about 103.74 seconds (61,886,464 blocks), yielding ~233 GiB root. This proves first-boot userspace execution even though HDMI still showed `initializing boot loader`.

Date in `/var/log` was July 31 due to absent battery-backed RTC and RAM logging; do not use timestamp alone as boot proof.

The onboard Wi-Fi has not been independently shown to work on F1; working USB Ethernet does **not** prove Wi-Fi. HDMI is a documented failure in F1 even though the OS boots. A heartbeat LED does not prove root mounting; a frozen splash does not prove failure.

## Prior experiments

M2cp, M2cr, M2ct, M2cv, M2cx and earlier M2ca/M2cb builds are covered in [the earlier hardware/boot investigation](boot-handoff-and-failures.md). Do not reinterpret an old splash-only trial as confirmed kernel non-entry.

## Next hardware acceptance

1. Source-hash-verified 6.6.98 control image: Wi-Fi, SSH, HDMI Linux console, MMC, USB-C, RAM, journal, reboot, shutdown.
2. Separately flashed 6.6.98 identity DTB-only change: same tests, especially HDMI.
3. Only after passes: 6.18 diagnostic with independent positive kernel-entry marker, then PMIC/MMC/root and finally HDMI.

All image assembly must preserve the stock firmware and require a final SHA256 manifest; use a spare SD card.
