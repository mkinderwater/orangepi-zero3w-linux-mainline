# Reproducible Zero 3W builds and permanent engineering evidence

## What is truly proven on Nov 15, 2026

- Official vendor 6.6.98 revision and A733 `.config` pinned; two independent **control** and **identity** builds compile completely, including AIC8800 modules, VE codec and NPU module.
- The `vendor-6.6.98/scripts/` in this Git branch are versioned. Each build uses separate source worktrees and `O=` object directories on WSL ext4. Build manifests go to Windows Downloads.
- Known pre-compile failures from vendor source were repaired in **disposable worktrees only**: malformed `gt9xx_secondary//Kconfig` source path causing infinite `SYNC auto.conf` loop; `cedar-ve/Makefile` relative `$(src)/codec/Makefile` failing under `O=` and corrected to `$(srctree)/$(src)/codec/Makefile`. Earlier grouped-target GNU Make patch was **tried and failed**, then reverted. See [next steps](../vendor-6.6.98/docs/next-steps.md).
- Not yet hardware tested: newly compiled control and identity 6.6.98 binaries. Do not promote them to release.
- Not yet fully reproducible from this Git branch alone: older hybrid 6.18 0.2.7 transformer, exact composed BSP source snapshots, all compiled modules and complete flash assembler. Preserve WSL worktrees and export an audited patch series before claiming complete 6.18 source reproducibility.

## Permanent evidence required per experiment

Store a small redacted text/JSON result under `evidence/experiments/<ID>/` with:

```yaml
experiment: F1
baseline: VBI
kernel: vendor-linux-6.6.98
dtb: hybrid-0.2.7
initramfs: vendor
firmware_sha256: 10fe537251b4262236f54d729c258706ad41419c3411dd2201ffc57e4924a9b0
boot_result: HW_PASS_USERSPACE
hdmi_result: HW_FAIL_DRIVER_BIND
evidence: "uname, /proc/cmdline, running FDT, dmesg, findmnt, SSH"
limitations: "onboard Wi-Fi not shown; 6.18 kernel entry still unknown"
```

For new experiments include exact full raw Image/DTB/initrd/checksums, flashed media image SHA256, build host and cross compiler versions, source `git rev-parse`, `git status`, boot script text, U-Boot state, FDT status and kernel logs. If artifact files cannot be committed for size/license/security, publish SHA256 plus an explicit acquisition path. Mark evidence as hardware, offline, inferred or unknown. Never attribute a vendor result to the 6.18 kernel.

## Flash/image release gate

1. Clean pinned source and deterministic build scripts (or explicit recorded toolchain differences), exact reviewed patches.
2. Generated Image, DTB and matching module directory and initramfs; verify **kernelrelease** is coherent. DTS alone cannot fix 6.18 kernel APIs.
3. Keep known-good Boot0/U-Boot/monitor/SCP bytes and boot scripts; preserve root UUID and layout, FAT/ext4 distinctions.
4. Audit occupied ranges, initramfs relocation/overlap, BL31 reservation, file hashes. Normalize mounted ext4 /boot as in tested reference builder (including zero-filled sectors) before assembly and verify fsck.
5. Ensure at least one independent early kernel diagnostic. No marker read does **not** prove Linux failed if console/SD is unverified.
6. Flash spare card, never overwrite only bootable control; record **which actual file was flashed** and checksum/readback.
7. Test boot, root, network, HDMI, PMIC, SD, USB, RAM variants, reboot and power-off. Distinguish vendor Linux HDMI console from bootloader splash, and PowerVR from HDMI scanout.
8. Release only when independent physical validation passes and full source/build/installer workflow is published.

## Publishing policy

Repository should contain **all owned reproducible code, text patches, tests, build scripts, manifests and sanitized evidence**. Do not commit firmware dumps or proprietary blobs without license rights, disk images >4 GiB, passwords/SSID, machine IDs or unredacted private logs. Public-source links and pinned commits must be kept current. Keep the failed hypotheses and root causes so future maintainers do not repeat the experiment.
