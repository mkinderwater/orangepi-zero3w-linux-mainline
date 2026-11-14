# M2cr diagnostic initramfs: missing `blkid` applet and `findfs` correction

**Date:** 2026-11-14  
**Board:** Orange Pi Zero 3W (Allwinner A733)  
**Experimental kernel:** Linux 6.18.19  
**Status:** Corrected scripts pass shell syntax checks. Corrected image rebuild and hardware boot not yet confirmed in this record.

## Scope and evidence

This finding concerns **M2cr's diagnostic initramfs only**. It does not explain the earlier M2cp splash-screen observation.

- **M2cp:** experimental raw ARM64 `Image` with `booti`, **no initramfs**. The board showed “Orange Pi, initializing boot loader.” That screen does not prove where execution stopped; Linux 6.18 HDMI is not functional.
- **M2cr:** a separate diagnostic candidate with a static ARM64 BusyBox initramfs. Its objective is to record whether the kernel enters initramfs, finds MMC root, mounts ext4, and calls `switch_root`.
- **Vendor control:** M2cm unarmed image booted Linux `6.6.98-sun60iw2` with HDMI console, Wi-Fi, and active SSH. This validates only the vendor path.

## Failure discovered before hardware testing

M2cr originally stopped during assembly because no static ARM64 BusyBox was provided:

```text
STOP: no ARM64 static BusyBox found.
M2cr results: ... (exit=4)
```

An ARM64 `busybox-static` Debian package was downloaded and unpacked outside the x86-64 WSL rootfs. Its executable was found at:

```text
/root/opi3w-m2-work/tools/busybox-arm64/extracted/usr/bin/busybox
```

The M2cr builder verified the static AArch64 ELF (1,975,064 bytes) and assembled a diagnostic image, preserving the vendor control and invoking the existing mounted-ext4 `boot_allocation.py` normalization. This **initial image was not flashed**.

The initial assembly printed:

```text
WARN: BusyBox applet blkid not evident in strings; runtime use still unverified
```

The warning was investigated by executing the ARM64 BusyBox applet list via `qemu-aarch64-static` on the x86-64 WSL host:

```sh
B=/root/opi3w-m2-work/tools/busybox-arm64/extracted/usr/bin/busybox
qemu-aarch64-static "$B" --list | grep -E '^(blkid|findfs|mount|switch_root)$'
```

Observed results:

```text
findfs
mount
switch_root
```

`blkid` **was absent**, while `findfs`, `mount`, and `switch_root` were present. The `findfs --help` output explicitly accepts `UUID=uuid` or `LABEL=label`.

## Root cause

The original generated `/init` loop enumerated MMC and SD partitions, then called an unavailable BusyBox applet for each candidate:

```sh
uuid=$(/bin/busybox blkid -s UUID -o value "$dev" 2>/dev/null || :)
if [ "$uuid" = "$UUID" ]; then match=$dev; break; fi
```

Because `blkid` was not in the packaged BusyBox, the command yielded no UUID, the expected root never matched, and the 90-second loop would end at:

```text
FAIL: root UUID not found, no switch_root attempted
```

This failure would occur **if the experimental kernel reached the M2cr initramfs**. It is a deterministic userspace defect in the originally assembled diagnostic image, not evidence that MMC/PMIC hardware failed.

## Correction applied to M2cr source

The script `/root/opi3w-m2cr-618/scripts/init` was updated to use the BusyBox applet that is actually present:

```sh
match=''
i=0
while [ "$i" -lt 90 ]; do
  match=$(/bin/busybox findfs "UUID=$UUID" 2>/dev/null || :)
  [ -n "$match" ] && [ -b "$match" ] && break
  match=''
  i=$((i+1))
  if [ "$((i%10))" -eq 0 ]; then
    audit "Waiting for root MMC and PMIC: ${i}s"
  fi
  /bin/busybox sleep 1
done
```

The build-script advisory check in `/root/opi3w-m2cr-618/scripts/run.sh` was also changed from:

```sh
for cmd in switch_root blkid mount sleep sh; do
```

to:

```sh
for cmd in switch_root findfs mount sleep sh; do
```

Both `sh -n scripts/init` and `bash -n scripts/run.sh` returned successfully. The corrected source has no `blkid` references in either script, based on the reported grep output.

A `busybox: command not found` message in the WSL shell was **not** a target failure: the ARM64 BusyBox binary was not installed as a native x86-64 WSL command and should be invoked under QEMU for host tests, or at `/bin/busybox` in the target initramfs.

## What remains unverified

1. The corrected M2cr diagnostic image has not been shown to pass a new assembly run or boot on hardware.
2. `findfs` is present, but successful UUID resolution on the actual device is not established. The initramfs must mount proc/sys/devtmpfs, wait for MMC to enumerate, and expose block devices.
3. The persistent diagnostics are only written **after** the root filesystem is found and mounted:
   - `/var/log/opi3w-m2cr/early-boot.txt`
   - `/var/log/opi3w-m2cr/dmesg-at-switch-root.txt`
4. Absence of these files cannot distinguish kernel handoff, early kernel, I²C, PMIC, MMC, initramfs, or userspace failure.
5. A persistent `/boot/mainline/armed` file does not guarantee one-shot fallback. Keep the verified vendor recovery image and use spare media.

## Next validation

Rebuild M2cr **after** applying the `findfs` correction, verify the new archive's exit status and inspect the packaged `/init` rather than relying only on the source file. Test on a spare SD card. Record observations and collect the persistent logs if they exist. Do not claim successful Linux 6.18.19 hardware boot until independently verified.

This investigation does **not** establish that the earlier M2cp image, which contained no diagnostic initramfs, was affected by `blkid`. The persistent bootloader splash is still inconclusive.
