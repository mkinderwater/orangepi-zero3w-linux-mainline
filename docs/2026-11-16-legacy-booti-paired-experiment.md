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

## 2026-11-16 assembler failure: donor second-stage SHA mismatch

Operator attempted the new paired builder. It passed preliminary checks and rejected the donor's **second-stage script SHA**, at `validate_source_script`, before modifying the script or initramfs. No vendor/hybrid hardware pass and no qualified image resulted.

The specific failure:

```text
RuntimeError: Second-stage source hash changed
```

**Known state:** The parent donor hash was checked successfully to reach this location; the kernel, DTB, initramfs, first-stage and environment file checks also passed. The script's expected hash is pinned per profile (`vendor=ec7c2338...`, `hybrid=50a01b89...`), but the **actual observed SHA was not included** in the exception. Do not replace the expected hash by guess, infer which profile the operator ran, or bypass the guard.

Commit `798d691` changes failure diagnostics only: on mismatch, output expected and actual SHA256 plus parsed U-Boot script lines (if header valid). It continues to reject mismatches and deletes the copied partial image.

**Next:** `git pull --ff-only` and rerun the same vendor-profile builder command. Report the `STAGE2_SOURCE_HASH_MISMATCH` block; if only the script's legacy header differs, separately compare the extracted command text, identify provenance and reconcile to a new explicitly pinned full donor. Never weaken the source and retained-file checks.

## U-Boot binary script framing fix (2026-11-16)

On the donor SHA-mismatch diagnostic, the old decoder tried `raw[64:].decode("utf-8")` and encountered `0xb8` in position 3. This is expected for a legacy U-Boot **script** image: after its 64-byte image header, `mkimage -T script` uses an 8-byte multi-image table (`BE32 script_length`, `BE32 0`) followed by the UTF-8 commands and alignment padding. The original parser incorrectly treated the binary length field as command text.

Fix committed `809471f`: parse and validate the script image header (`Linux/ARM/script/none`), the BE32 length table, and zero padding *before* decoding. This parser fix does **not** change the pinned donor SHA, authorize any unknown file, or make a boot claim. A synthetic valid legacy script framing test passed; actual WSL file parsing still needs operator output.

**The SHA mismatch is separate and still unresolved.** After `git pull --ff-only`, rerun the vendor profile command unchanged, and record all lines beginning `STAGE2_SOURCE_HASH_MISMATCH` including `expected:`, `observed:`, and parsed script commands. The tool should continue to fail closed until we reconcile the per-file expected SHA against the exact donor bytes and proven script lineage.

If the original donor copy is already mounted or changed, preserve and audit it rather than relaxing the check or accepting a guessed hash.

## 2026-11-16 verified cause of first vendor-profile stop

The improved parser printed the complete observed VBI donor script SHA256:
`ec7c2338fc654260868af803c60f57ac62148e2fa7cf18d1446efd3ad2b5ad24`.

This **exactly matches** the already pinned, hardware-qualified vendor-stage2 SHA recorded in `diagnostics/build-vbi-pid1-control.py`. The new paired builder accidentally truncated the reference constant by omitting `b5` near the end:
- Incorrect: `ec7c2338fc654260868af803c60f57ac62148e2fa7cf18d1446efd3ad24`
- Correct: `ec7c2338fc654260868af803c60f57ac62148e2fa7cf18d1446efd3ad2b5ad24`

The script text shows initrd `load`, immediate `setenv ... ${filesize}`, kernel load and original `booti kernel ramdisk:size fdt`. There is no verified U-Boot problem in this failure. Commit `badab45` restores **the known-good reference hash**, without bypassing checks or modifying the kernel, donor, image contents or test design.

**Next:** `git pull --ff-only`, re-run the same `--profile vendor` command and follow the existing vendor hardware control gate. As of this note, the new image build and physical legacy boot are still unverified.
