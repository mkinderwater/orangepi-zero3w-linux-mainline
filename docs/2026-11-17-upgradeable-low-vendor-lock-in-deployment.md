# Orange Pi Zero 3W: upgradeable, low-lock-in Linux deployment architecture

**Decision:** Adopt an upstream-first, package-managed Debian ARM64 deployment. Preserve the existing proven A733/Zero 3W boot firmware only as a clearly documented transitional platform dependency. The current hybrid Linux 6.18.19 (0.2.7) is the hardware-entry baseline; it has reached PID1 via serial but is **not** a stable SD/root or product release.

**Status:** Architecture approved for development; no new boot image built and no automatic rollback mechanism proven. This document supersedes the earlier assumption that every kernel upgrade requires rebuilding a complete SD card image.

## 1. Problem and target

The current engineering path imports a large Allwinner BSP into a mainline 6.18 source tree, edits top-level Kbuild/Kconfig, keeps an externally generated board DTB, uses a vendor 2018 U-Boot script and builds a custom complete SD image. That design was useful to prove ARM64 entry and PID1, but it is **expensive to upgrade** and easy to break when upstream MMC, UART, DRM, regulator or pinctrl APIs evolve. A confirmed collision of vendor `MMC_CAP2_HC_ERASE_SZ` with Linux 6.18 `MMC_CAP2_SD_UHS2` is the practical example.

**Target goals:**
- Keep standard Debian stable or equivalent plain ARM64 userspace; system updates through signed APT packages without flashing an OS image.
- Deliver versioned `linux-image`, optional `linux-headers`, board-DTB, firmware and modules as reproducible, signed Debian packages with coherent release identifiers and hashes.
- Maintain one pinned upstream LTS kernel with **small, tracked and auditable** A733 patch series; isolate vendor-only drivers as explicit, temporary compatibility components.
- Have reproducible build scripts and CI, with source pinning, kernel `.config`, compiler versions, patches, module ABI and DTB versions included in a signed release manifest.
- Stage new kernel/DTB/initrd as **new immutable versioned files**, do not overwrite the currently working set until the new one has booted and passed acceptance.
- Treat the 2018 vendor U-Boot, Boot0, monitor, SCP and binary firmware as a *bounded transitional dependency*. Do not call the entire system vendor-free while these remain.
- Avoid using one fixed board RAM size; preserve U-Boot memory fixups for physical variants.
- Be ready to upstream board/DTS and drivers individually, with tracking of accepted upstream replacements and eventual deletion of BSP copies.

## 2. Deployment layers: ownership and upgrade cadence

| Layer | Desired owner | Typical upgrade | Decision |
| --- | --- | --- | --- |
| Boot0/DRAM training/BL31/SCP | Original Zero3W vendor firmware temporarily | Rare and only after exact board revision tests | **Freeze known-good bytes**, preserve hashes and licensing. Independent replacement is a long-term project |
| U-Boot | Vendor 2018 while boot path remains board-sensitive | Rare, separate from OS/kernel updates | Keep current proven script semantics. Evaluate modern mainline U-Boot only in a controlled recovery-capable track |
| Kernel base | Upstream stable/LTS maintained in our own tree | Regular security/stability releases | Pin source commit and maintain one branch for each chosen LTS line, not a drifting permanent fork |
| A733 platform changes | Small owned patch series + upstream accepted patches | Rebase per LTS release | Track feature owner, status, upstream commit/ref and delta; delete carried patches when upstream lands |
| Device tree | Board-level source from verified Zero 3W hardware | Coupled to kernel package when bindings change | One canonical DTS with documented per-revision variants; overlays only for actual optional hardware |
| Kernel modules and firmware | Matched module ABI and redistributable firmware source | Per kernel / firmware release | Package modules under `/lib/modules/<uname -r>`; keep signed firmware with copyright/license inventory |
| Initramfs | Standard Debian initramfs tooling | On kernel install/config changes | Boot-critical device and root dependencies must be available before root mount |
| Root filesystem | Debian stable ARM64 | APT security and application updates | Avoid custom rootfs rebuild for routine updates; preserve system configuration |
| Apps/services | Standard deb packages, service units | Independently | No bundled kernel assumptions or proprietary launch-time scripts |

The target **does not require** committing vendor firmware blobs to public Git or redistributing files without rights.

## 3. MMC driver architecture: make the choice explicitly

**Current:** Linux 6.18 vendor `CONFIG_AW_MMC=y`, vendor `sunxi-mmc-v5p3x` and `mmc-high-capacity-erase-size`; source header defines `MMC_CAP2_HC_ERASE_SZ = BIT(9)`, which is **now Linux 6.18 UHS-II**. Active `sdmmc@4022000` has the legacy erase property. UART reached a null UHS-II callback. A separate PF bank-voltage transition causes a fatal panic.

**Counterpart:** nickyg666's reported Zero 3W Linux 6.18 setup uses upstream-style `CONFIG_MMC_SUNXI` with adapted DTB compatibles/reset bindings and documents sdc0/sdc1 regulator fixes. Jonas and MiniMyth A733 patches also favor upstream MMC work. This suggests a lower-maintenance driver direction; **it is not proof of functional parity on our board**.

**Decision:** Maintain two separate evaluation tracks:
1. `AW_MMC` compatibility repair **only**: remove obsolete CAP2 bit-9 alias and audit all legacy flags. Preserve as the hardware comparison baseline, not the permanent architecture by default.
2. `MMC_SUNXI` integration **only**, using its documented bindings and genuine A733 clock/reset, pinctrl, AXP8191 supply and DMA requirements. Avoid simply changing `compatible` strings unless the actual IP/register model and driver operations match.

Compare both for MMC0 boot/root, MMC1 SDIO Wi-Fi, MMC2 optional eMMC, UHS-I negotiation, voltage handling, SDIO IRQ, tuning, speed, reboots, suspend, error recovery and root filesystem reliability. Adopt upstream `MMC_SUNXI` if it meets parity; otherwise document which board-specific features prevent migration and propose focused upstream patches. No arbitrary global disabling of UHS-II, MMC2, regulator checks or voltage switching.

## 4. Device tree principles

- Canonical Zero 3W DTS with real board identity and vendor SoC fallback `arm,sun60iw2p1` while required for vendor HDMI; never reuse erroneous `orangepi-4-pro` board compatible.
- Keep AXP8191 rails, R-TWI0, MMC0 PF0-PF6 and supplies, MMC1 SDIO/Wi-Fi, and actual enabled hardware; no deleting supplies to work around probe deferral.
- Keep secure-memory reservations and runtime U-Boot RAM-size fixups, not 1 GiB hardcoding.
- Remove historical speculative oscillator changes and no-hardware-evidence hacks; preserve electrical-safe pinctrl switching and correct SoC revision detection.
- DT binding warnings are tracked as validation issues; classify whether they represent real malformed cells vs harmless vendor leftovers.
- DTB is a versioned kernel-coupled artifact; hash and verify each deployed DTB as a pair with `Image` and modules. Don't modify deployed DTBs manually as the normal release process.
- Support board revisions through small source-based DTS variants or overlays with explicit hardware evidence, not by silently shipping universally enabled phantom devices.

## 5. Boot updates: A/B **kernel slots**, not duplicate full OS partitions

Keep one Debian root filesystem and one shared user-data partition (if needed). In the short term retain a boot layout compatible with validated Zero3W vendor U-Boot/ext4 semantics; do **not** repartition a functioning device simply because a newer generic guide says to use FAT.

Example conceptual `/boot/slots`:

```text
/boot/slots/A/
    Image
    initrd.img
    board.dtb
    manifest.sha256
/boot/slots/B/
    Image
    initrd.img
    board.dtb
    manifest.sha256
/boot/boot.scr
/boot/orangepiEnv.txt
```

**Important:** The actual vendor U-Boot does NOT yet have a validated crash-safe bootcount/watchdog rollback. A kernel that panics after `booti` does not automatically return to the script. **Do not claim automatic A/B recovery.**

Safe initial behavior:
1. Install a new, versioned kernel/DTB/initramfs/modules as a complete package set and stage inactive slot.
2. Verify hashes, image header, arm64 architecture, DTB/boot script, reserved-memory ranges, modules and initramfs coherence, mounted-ext4 dense `/boot` allocation, free space and fsck.
3. Only then atomically replace a short, checksummed **boot-selection record** or generated selection script with filesystem sync and postwrite readback. The currently working slot stays intact.
4. Reboot into candidate. Test kernel identity, root mounted RW, storage, SDIO, network and services. Mark known good after successful checks.
5. If it fails, allow *documented manual UART/SD selection* of the retained good slot. Automatic rollback is a **separate** firmware and watchdog project requiring demonstrated persistent bootcount and restart behavior.
6. Once hardware validated, add an explicit boot-attempt mechanism using hardware-safe reset/watchdog + persistent state that is actually read on the next boot; preserve physical recovery media. Never rely on an in-RAM variable surviving power loss.

**Compatibility warning:** Some vendor U-Boot builds reject arbitrary symlinks, fragmented files, unsupported filesystem features or different initrd wrapping. The existing dense-file normalizer, original environment import and FDT preparation remain mandatory gates unless a new bootloader is physically validated.

**Security and data integrity:** An atomic file rename on ext4 does not itself prove power-loss-safe boot selection or successful fsync. Implement and test failure injection at every update stage before advertising crash tolerance.

## 6. Packages and releases

Prefer native Debian tools:
- Package `linux-image-<version>-zero3w` and matching modules, preferably using the standard kernel packaging workflow compatible with `initramfs-tools` and `/etc/kernel/postinst.d` hooks.
- Package board DTBs and **exact-version tied** optional overlays in either the kernel package or a dependency-pinned `zero3w-board-dtb` package. Kernel ABI and DT bindings must match.
- Package firmware only where license permits. Stage artifacts by hash; do not silently overwrite untracked Boot0.
- Include versioned release manifest: upstream SHA, BSP SHA where used, patch manifest, config SHA, toolchain, kernel `uname -r`, built Image, modules, DTB, initrd, test and known failures.
- Publish signed APT repository metadata or signed release packages, check package signatures and hashes before install. Avoid unpublished mutable `latest` image links as release identity.
- Keep normal APT updates separate from firmware and boot-critical upgrades; never permit an automatic background kernel update to destroy only known-good boot path.

A security update for Debian userspace should not require reflashing the SD card.

## 7. Minimal vendor footprint / roadmap

| Stage | Deliverable | Acceptance |
| --- | --- | --- |
| 0. Preserve evidence | 0.2.7 source image/DTB/hashes and all historical test logs | Pin and verify complete reproducible source state |
| 1. Stabilize 6.18 baseline | Permanent MMC CAP2 repair; separately debug PF switching; root SD reliable | UART no Oops/panic; sustained boot and root read/write |
| 2. Standard Debian system | Boot standard Debian 13 ARM64 root, initramfs-tools, network and systemd | Apt update/upgrade without new SD image |
| 3. Versioned kernel packages | Build and install versioned Image/DTB/modules/initrd packages | Two installed kernel versions, matching modules and reversible manual slot selection |
| 4. Mainline MMC migration | Replace vendor MMC with upstream `MMC_SUNXI` when validated | MMC0/1/2 parity, card modes, regulator/SDIO, clean boots |
| 5. Narrow A733 BSP | Upstream/replace pinctrl, CCU, UART, PMIC, power domains, DRM individually | Each patch has upstream reference and board test; vendor components isolated |
| 6. Modern boot firmware | Investigate mainline U-Boot, TF-A, DRAM training and firmware licensing | Real hardware multiboard validation and safe recovery; don't rush Boot0 replacement |
| 7. Maintained release | Periodic LTS updates, CI, package feed, rollback tests | Install/upgrade/rollback on real Zero3W without manual source edits or full reflashing |

## 8. CI and acceptance automation

CI should:
- Checkout pinned Linux LTS commit and deterministic patch series; refuse dirty/nonreproducible source inputs.
- Run old/new MMC CAP2 bit-collision audit and other vendor API definitions before compile.
- Compile all required DTBs and overlays; validate DT bindings against matching kernel tree where schemas exist; ensure root compatible includes actual board.
- Verify kernel Image/DTB/module release matching; modules dependency generation and initramfs with required drivers.
- Inspect firmware/BL31 overlaps and U-Boot script addresses. Normalize /boot files on the final candidate filesystem and audit sparse holes.
- Generate signed manifests and reproducible .deb artifacts.
- Execute host-side tests and automatic static checks, then record real-board UART tests separately. Hardware acceptance is required for hardware claims; emulation cannot establish A733 regulator/SD electrical safety.
- Before release, test interrupted package staging, boot-selection switching, exact rollback path, card-removal and cold-boot behavior on a spare SD.

## 9. Explicitly closed or deferred legacy experiments

**Closed as present 6.18 blocker:** initial ARM64 branch/header, U-Boot entry, 41MiB M2 overlap in **old** image, raw-vs-legacy initrd speculation, broad clock-disable speculation and frozen splash diagnostics. These findings remain archived but must not be reapplied as new fixes.

**Deprecated for production:** temporary limited AXP8191 writes, unjustified PMIC or voltage suppressions, oscillator and PB9/10 combined changes, deleting regulator references, permanent MMC controller disabling, speculative Linux7.3 patch mass imports.

**Open but independent:** PF bank voltage status/polarity, HDMI root compatibility, AIC8800 SDIO, optional eMMC physical population, AXP515/RTC, GPU/DRM and USB features. Do not bundle fixes across these without isolated test results.

## 10. Known limitations and source authority

- There is not yet a verified source-complete reproduction of hybrid 0.2.7 from only the public repository. The actual WSL integration inventory and exact BSP transformer must be captured and reviewed.
- There is no physical confirmation that `MMC_SUNXI` matches the Zero3W bus/voltage/tuning behavior as well as `AW_MMC` on our device.
- No automatic rollback has been implemented, and vendor U-Boot 2018 is a continuing lock-in.
- Only the known 1 GiB Zero3W has been tested by this project; other RAM/board variants require independent validation.
- Current public Zero3W software sources and Armbian coverage continue to use a vendor BSP or hybrid kernel for substantial A733 functionality; fully upstream-only A733 Linux is not yet evidenced here.
- Userspace package management is the *recommended architecture*, not an already deployed feature.

**Cross-references:** [inclusive kernel source/DTS audit](2026-11-17-inclusive-618-source-and-dts-audit.md), [full boot-trial reconciliation](2026-11-17-full-history-after-uart-mmc-panic.md), [source pinning](2026-11-15-source-provenance.md), [MMC driver comparisons](2026-11-16-external-618-deep-audit.md). Debian kernel packaging: [Debian Administrator's Handbook, kernel installation](https://www.debian.org/doc/manuals/debian-handbook/sect.kernel-installation.en.html), [Debian kernel post-installation hooks](https://kernel-team.pages.debian.net/kernel-handbook/ch-update-hooks.html).

## 11. Initial implementation landed: release preflight, no installer

The first deployment artifact is [`scripts/release-kernel-manifest.py`](../scripts/release-kernel-manifest.py). It is intentionally **read-only with respect to all kernel inputs and installed media**. It takes an explicitly specified raw ARM64 Image, DTB, raw-gzip or legacy-uInitrd, matching named kernel module tree and outputs a new JSON manifest containing SHA256 digests, file sizes, Image header fields, DTB header size and module-tree digest. It refuses missing/malformed files and existing output filenames.

This is **not yet** a Debian package builder, a correct `vermagic` checker, DT binding validator, signed manifest or bootloader selector. It does not run `apt`, mount, repartition, modify Boot0, change `boot.scr`, or flash any card. A kernel release label is operator input and **not inferred/verified from the Image**. Legacy-uInitrd magic/type is a minimal preliminary check, not full CRC/header validation. The module-tree check requires at least one module candidate and intentionally cannot validate a modules-all-builtin configuration without extension.

Regression tests [`tests/test_release_kernel_manifest.py`](../tests/test_release_kernel_manifest.py) exercise normal output, overwrite refusal, invalid Image/DTB, missing modules, release mismatch and legacy initrd recognition. These tests are committed but **not executed on the operator's WSL** as part of this Git commit.

On the WSL host:

```bash
cd /root/orangepi-zero3w-linux-mainline
git pull --ff-only
python3 -m unittest discover -s tests -p 'test_release_kernel_manifest.py' -v
python3 scripts/release-kernel-manifest.py --help
```

Before creating a real artifact, identify the exact 0.2.7 matching modules directory and initramfs path. Do not guess a module directory from the source tree. An example invocation after verifying every path:

```bash
python3 scripts/release-kernel-manifest.py \
  --image /root/opi3w-hybrid-build-0.2.7/stage/boot/Image \
  --dtb /root/opi3w-hybrid-build-0.2.7/stage/boot/sun60i-a733-orangepi-zero3w.dtb \
  --initrd /path/to/EXACT-VERIFIED-initrd \
  --modules /path/to/EXACT-VERIFIED-modules/6.18.19-opi3w-hybrid-0.2.7 \
  --kernel-release 6.18.19-opi3w-hybrid-0.2.7 \
  --upstream-sha 4aea1dc4cad17cd146072e13b1fd404f32b8b3ef \
  --bsp-sha 656a550c826787e7e72fae58ca793df9e0988ac8 \
  --output /root/opi3w-m2-work/release-0.2.7-preflight.json
```

The placeholders deliberately prevent accidentally claiming a mismatched module/initrd pairing is valid.

**Companion source audit:** `scripts/audit-618-integration-inventory.py` now discovers A733 DTS under imported BSP and inspects the compiled DTB. Operator's latest run reported `CAP2_COLLISIONS: 1`, `DTS_CANDIDATES: 10`, `PATCH_FILES: 3`. The counts demonstrate coverage improvements, **not** approval of the unreviewed per-file diffs. Review `integration-inventory.md` or the JSON's `full_core_comparison`, `bsp_comparison` and `device_trees` before drafting any cleaned source patch series.

**Next after source diff review and tests:** build a Debian package/staged kernel-slot prototype on throwaway filesystems. Actual boot-selection integration must remain out of scope until UART manual recovery and bootcount/watchdog semantics are proven on this board.
