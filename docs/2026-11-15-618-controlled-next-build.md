# Linux 6.18.19: controlled continuation after HBI-027

**Status: tooling committed; no new SD image or kernel compiled; no new hardware outcome claimed.**

## Why this is not another HBI build

Evidence already collected on physical Zero 3W:

- **A2V** boots when the exact vendor second-stage script is sourced.
- **S1** omitting FDT setup and **S2** omitting environment import both fail.
- **VBI** proves raw ARM64 vendor 6.6.98 via no-fallback `booti` boots to Debian.
- **HBI-027** already substitutes matched 6.18.19 `Image`, DTB and C initramfs into the VBI/A2V-derived handoff; it gives no positive 6.18 userspace evidence.
- **F1** proves vendor 6.6.98 kernel + hybrid 0.2.7 DTB boots to SSH, though HDMI fails.
- **F2** uses 6.18 + vendor DTB without initrd; it is **not** a one-variable comparison to HBI.

The 0.2.7 kernel Image SHA256 is `e4b2eff08dfc7e2553cf498def6658515f5f2f1e5e8066d0fcc60a73742069c7`; DTB SHA256 is `5c9cd102215183cc56150aab2ce331216bea26d80741cdfc1fb0d95f5818e7b9`. HBI addresses are already checked for static overlap; real U-Boot relocation has not been observed.

## Phase 1: inspect finished images without altering them

Run on the WSL build host (root, `u-boot-tools`, `e2fsprogs`, util-linux installed):

```bash
cd /root/orangepi-zero3w-linux-mainline
git fetch origin
git switch test/618-hbi-handoff-audit

find /root /home -type f \\( -iname '*VBI*.img' -o -iname '*HBI*.img' -o -iname '*F1*.img' \\) -printf '%p\n' 2>/dev/null

python3 scripts/audit-618-finished-images.py \\
  --vbi /ABSOLUTE/PATH/TO/VBI.img \\
  --hbi /ABSOLUTE/PATH/TO/HBI-027.img \\
  --f1 /ABSOLUTE/PATH/TO/F1.img \\
  --output /root/opi3w-m2-work/618-finished-audit
```

Replace example paths using actual `find` output. If F1 is not available, omit `--f1`. The script opens images read-only with `losetup`, uses `debugfs` to read their ext4 files, computes image/payload hashes, decodes scripts and emits `AUDIT.json`, `VBI-vs-HBI-stage2.diff` and decoded boot scripts. It **does not** build or flash a candidate. Audit cannot by itself establish working in-memory U-Boot relocation.

## Phase 2: prepare exactly two independent 6.18 diagnostic hypotheses

The next image generator must use exact actual paths/hashes from Phase 1, not guess them.

**H1: 6.18 kernel+vendor DTB, with the original 6.18 matched diagnostic initramfs**, retaining every other HBI attribute. This isolates the DTB difference relative to HBI. Note F2 omitted its initramfs, so F2 did not test this condition.

**H2: 6.18 kernel+hybrid DTB, with a independently validated early /init signal**, retaining the same `booti` and all vendor handoff semantics. Confirm the 6.18 initramfs is valid ARM64 and actually receives control. If diagnostic output requires root or unproven UART, the absence of a marker is inconclusive. A serial or safe GPIO method must be hardware-validated independently.

Do not substitute vendor 6.6 modules into 6.18, and do not reuse a vendor initramfs without validating compression, cpio format and the corresponding `booti` length argument. Preserve all PMIC rails, MMC supplies and overlay handling. Avoid changing two variables in one experiment. Never use fallback `bootm` after `booti`.

## Phase 3: actual hardware evidence

Per candidate: record exact finished SD image SHA256; live U-Boot environment and final `bootargs`; pre-handoff memory placement and ramdisk relocation; verified early 6.18 kernel-entry signal; `uname -r` / SSH if userspace starts; MMC/PMIC status and HDMI separately. A static pre-boot checkpoint and a frozen HDMI splash are not proof of Linux entry or its absence.

**Release gate:** 6.18.19 kernel userspace, reliable root and networking, native DRM HDMI modesetting, RAM variants, and reproducible source-to-image build.
