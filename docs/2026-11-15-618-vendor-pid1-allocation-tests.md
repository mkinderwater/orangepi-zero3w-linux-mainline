# Two independent follow-up tests: allocation and vendor PID1 control

Status: tools committed, offline execution and new hardware tests NOT YET PERFORMED.

## Ground truth

The two PID1 images use identical 6.18 kernel/DTB/boot-script/initramfs payload hashes. The unnormalized image showed the status LED remaining on; the normalized image showed the LED switching off after the frozen bootloader splash. Neither observation establishes kernel/PID1 entry. The PID1 probe does not start networking, so absence of NIC link is not a root or PID1 test.

### Test A: compare holes on already flashed 6.18 images

```bash
cd /root/orangepi-zero3w-linux-mainline
python3 diagnostics/compare-boot-allocation.py \
  --original /root/opi3w-m2-work/opi3w-HBI-027-PID1-DIAG.img \
  --normalized /root/opi3w-m2-work/opi3w-HBI-027-PID1-NORMALIZED.img \
  --output /root/opi3w-m2-work/pid1-allocation-compare.json
```

Uses a readonly offset loop and ext4 `ro,noload` mount to inspect SEEK_HOLE results. This is a direct hole-presence measurement, not proof of U-Boot sensitivity. If both are dense, metadata/allocation/physical extent differences remain possible. No source image is changed.

### Test B: vendor-kernel PID1 control

Keep original hardware-booting VBI source unchanged. Replace only `/boot/mainline/verified-vendor-initrd.gz` with our **same** AArch64 static PID1 CPIO gzip, retain the vendor 6.6.98 raw Image, stock DTB, exact A2V-derived first and second stage, and all bootargs and firmware. Normalize with the pinned `opi-3w-wbuild` boot allocator. This is a diagnostic image that intentionally does **not** boot Debian or bring up Ethernet.

```bash
python3 diagnostics/build-vbi-pid1-control.py \
  --source /root/opi3w-vendor-booti-0.1.0/opi3w-VBI-vendor-A2V-booti.img \
  --probe /root/opi3w-m2-work/618-pid1-probe/pid1-probe-initramfs.cpio.gz \
  --wbuild-scripts /root/opi-3w-wbuild/scripts \
  --output /root/opi3w-m2-work/opi3w-VBI-PID1-CONTROL.img
```

Do not flash until SHA256 and independent finished-image audit pass. Use a spare microSD. If a genuine `OPI3W_PID1: START` message appears on HDMI with the vendor kernel, that establishes that PID1 probe executes through the vendor handoff and the output channel works there. It does **not** establish the Linux 6.18 output channel works. Missing output remains inconclusive without validated console. If the vendor PID1 probe does not visibly print, do not use that negative result to condemn 6.18.

## Record before changing kernel

Capture SHA256 sidecars, dense allocation audit, LED before/after splash, visible output, boot behaviour and whether any line explicitly reports a Linux version. Never count a frozen U-Boot splash or an unlit NIC as decisive. Separate the original HBI outcome from our new vendor PID1 control.
