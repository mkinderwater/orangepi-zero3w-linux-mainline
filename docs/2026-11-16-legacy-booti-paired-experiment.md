# Controlled legacy-uInitrd handoff pair: vendor 6.6.98 and hybrid 6.18.19

**Status: assembler source committed, offline image assembly NOT executed, hardware NOT tested.**

## Purpose

Isolate the one remaining vendor U-Boot API difference from nickyg666's reported successful 6.18 Zero 3W boot:

| Parameter | Existing proven vendor VBI handoff | New legacy handoff |
| --- | --- | --- |
| Payload | raw gzip CPIO static AArch64 PID1 | identical raw gzip bytes, wrapped by 64-byte ARM U-Boot legacy RAMDisk header |
| Second-stage `booti` | `booti kernel_addr ramdisk_addr:size fdt_addr` | `booti kernel_addr ramdisk_addr fdt_addr` |
| Kernel | Unchanged in each profile | Unchanged |
| DTB | Unchanged in each profile | Unchanged |
| Boot0/U-Boot monitor/SCP | Unchanged | Unchanged |
| Root filesystem files | All hashes unchanged except **second-stage script and initrd** | Checked via full file inventory |
| /boot allocation | Existing mounted-ext4 normalization | Same pinned normalizer |
| A733 CCU/pinctrl | Unchanged | Unchanged |

The pair isolates the **coherent initramfs interface**, meaning the wrapper and matching operand must change together. This is not a double kernel modification.

## Commands (Debian WSL, run from cloned test branch)

Precondition: `mkimage`, `losetup`, `mount`, `e2fsck`, `cpio`, `gzip`, `sfdisk` and pinned boot normalizer. Existing LED PID1 probe must be the same archive in both tests.

```bash
cd /root/orangepi-zero3w-linux-mainline
git pull --ff-only

# Check script syntax/CLI before assembling any 4 GiB image.
python3 -m py_compile diagnostics/build-legacy-booti-pair.py
python3 diagnostics/build-legacy-booti-pair.py --help

# Known-good vendor-kernel control first.
python3 diagnostics/build-legacy-booti-pair.py \
  --profile vendor \
  --source /root/opi3w-vendor-booti-0.1.0/opi3w-VBI-vendor-A2V-booti.img \
  --probe /root/opi3w-m2-work/618-pid1-led-v1/pid1-probe-initramfs.cpio.gz \
  --wbuild-scripts /root/opi-3w-wbuild/scripts \
  --output /root/opi3w-m2-work/opi3w-VBI-LEGACY-PID1-v1.img

cd /root/opi3w-m2-work
sha256sum -c opi3w-VBI-LEGACY-PID1-v1.img.sha256
cat opi3w-VBI-LEGACY-PID1-v1.img.audit.json
```

**Do not build or flash the hybrid candidate until the vendor control is physically validated.** For the vendor control: three LED startup flashes and later ALIVE flash / HDMI with `UNAME Linux 6.6.98-sun60iw2 aarch64` is hardware PASS for the coherent legacy interface. A board showing the splash alone is not a PASS.

After vendor hardware PASS, produce the hybrid image:

```bash
cd /root/orangepi-zero3w-linux-mainline
python3 diagnostics/build-legacy-booti-pair.py \
  --profile hybrid \
  --source /root/opi3w-HBI-027-vendor-VBI-booti.img \
  --probe /root/opi3w-m2-work/618-pid1-led-v1/pid1-probe-initramfs.cpio.gz \
  --wbuild-scripts /root/opi-3w-wbuild/scripts \
  --output /root/opi3w-m2-work/opi3w-HBI-027-LEGACY-PID1-v1.img

cd /root/opi3w-m2-work
sha256sum -c opi3w-HBI-027-LEGACY-PID1-v1.img.sha256
cat opi3w-HBI-027-LEGACY-PID1-v1.img.audit.json
```

Inspect final images independently (filesystem audit, legacy header via `dumpimage -l`, decoded stage2 and SHA). The assembler verifies donor image SHA, kernel and DTB SHA, preserved first-stage script, exact firmware 32 MiB prefix, full ext4 logical file inventory, only two modified paths, and pinned mounted-ext4 boot normalization. It refuses to overwrite an output.

**Known limits:** donor filenames in examples are historical paths, and may need to be adjusted after independently locating exact pinned donor SHA. The assembled image is not a hardware success claim. Firmware ramdisk relocation and BL31 protections remain unobserved until hardware instrumentation. The legacy format may trigger a different U-Boot parser path; a failed legacy vendor control means stop, not try hybrid.

## Safety and fail-closed gates

- Never change physical SD block devices from this builder.
- Never modify source image or replace kernel/DTB/Boot0.
- Keep vendor environment import, FDT setup and overlay logic.
- Do not introduce vendor `bootm` fallback that could misidentify the running kernel.
- Keep the Linux 6.18 clock investigation separate.
- First-boot LED state difference remains deferred.
