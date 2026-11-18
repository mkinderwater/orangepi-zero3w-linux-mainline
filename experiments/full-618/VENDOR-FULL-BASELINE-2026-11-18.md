# New baseline: vendor Linux 6.6.98, full Zero 3W DTB

**Purpose:** Re-establish a known-good, dependency-complete control before integrating Linux 6.18 into an A733 Orange Pi Zero 3W with HDMI connected at power-on.

## Baseline definition

- Source: `/home/opi3w-VBI-vendor-A2V-booti.img` (hardware-tested Debian login over HDMI; vendor kernel 6.6.98).
- Source image SHA256: `7c76d125013df144d238526e396c1c9d5878c2cdf57eaa3ac09f613e32afa63c`.
- One ext4 partition starting at sector 65536. Existing A2V `booti` vendor-image handoff remains untouched.
- Payloads preserved exactly: Boot0, BL31, SCP, vendor U-Boot, vendor 6.6.98 Image and modules, full vendor DTB and initramfs, boot scripts, rootfs.
- **This is a vendor-stock-kernel / vendor-DTB control, not a factory-original byte image.** The source VBI was previously assembled with a tested vendor `booti` chain. No claim its firmware matches the exact July retail image beyond existing evidence.
- **This is NOT Linux 6.18.** It tests the complete vendor dependency chain first; it does not prove the vendor DTB can boot an unmodified 6.18 kernel.

## Build on Debian host

```sh
cd /root/orangepi-zero3w-linux-mainline/orangepi-zero3w-linux-mainline
git pull --ff-only origin work/linux-6.18-full-integration
python3 scripts/build-vendor-full-stock-baseline.py
```

Output: `/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/opi3w-VENDOR-6698-full-stock-baseline.img`

Builder pins entire source SHA, verifies the single-partition layout, checks the vendor kernel/config/initramfs and board DTB including DE/TCON3/HDMI nodes, clones every byte, checks exact image SHA equality and reinspects cloned boot assets. No source image modification, no new environment file and no U-Boot firmware changes. **Builder not yet run on host**.

## Hardware acceptance

On a dedicated spare microSD (not the recovery card), test:
1. HDMI physically connected **before power-on**.
2. UART capture from first firmware message through Linux and Debian login.
3. Confirm video is **Linux output**, not only the static U-Boot splash.
4. Verify `uname -r` reports `6.6.98-sun60iw2`, `/sys/class/drm` lists connector status, and record uptime.
5. Reboot at least twice, with HDMI attached, and verify repeated vendor-OS entry.
6. Compare against the same control with HDMI disconnected and inserted at U-Boot prompt; record differences.

## Only after baseline passes

The next experiment should be **separate** and change one dimension at a time:
- Stage A: vendor 6.6.98 Image + *modified* Linux DTB, keeping vendor firmware/root unchanged to find dependency sensitivity.
- Stage B: 6.18 Image with a **translated vendor-equivalent DTB and matched 6.18 drivers**. Do not use unmodified vendor DTB phandles, clocks, resets or regulator bindings with 6.18.
- Never label a DTB 'full' merely because it contains nodes. Every active `compatible`, supply, interrupt, clock and reset must bind against the selected kernel.
- Preserve the 26 MHz oscillator evidence and correct A733-specific PCK power domains. No speculative clock register writes.

**Decision gate:** if the new byte-identical control fails, inspect media, power and boot reproducibility before changing DTBs. If it passes, vendor display/PMIC/MMC/clock dependencies provide a grounded control; then translate them into a genuine 6.18 baseline.
