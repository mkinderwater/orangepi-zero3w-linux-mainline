# Confirmed vendor 0.7.6 boot handoff

Reference: `opi-3w-wbuild-0.7.6.img.gz`, examined read-only from ext4 partition 1. The raw image's FAT partition starts at LBA 65536 (32 MiB); ext4 starts at LBA 196608 (96 MiB). Partition table entry order is not disk order.

The boot script imports `/boot/orangepiEnv.txt`, obtains root by configured UUID (or PARTUUID fallback), and executes:

```text
load ${devtype} ${devnum} ${ramdisk_addr_r} ${prefix}uInitrd
load ${devtype} ${devnum} ${kernel_addr_r} ${prefix}uImage
load ${devtype} ${devnum} ${fdt_addr_r} ${prefix}dtb/${fdtfile}
bootm ${kernel_addr_r} ${ramdisk_addr_r} ${fdt_addr_r}
```

`fdtfile=allwinner/sun60i-a733-orangepi-zero3w.dtb`. `/boot/dtb` is a symlink into `dtb-6.6.98-sun60iw2`; `/boot/uInitrd` is a symlink into its versioned file. The vendor legacy uImage header uses 0x27051956 magic; load and entry address 0x41000000; payload uncompressed. **Copying that header onto an upstream ARM64 Image does not demonstrate boot compatibility.**

A matching Linux 6.18.19 modules tree, initramfs and boot diagnostics must be prepared separately. The working 6.6.98 PowerVR vendor module is not ABI-compatible with 6.18.19.
