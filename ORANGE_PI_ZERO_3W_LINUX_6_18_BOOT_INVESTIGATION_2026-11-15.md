# Orange Pi Zero 3W: Linux 6.18.19 boot investigation and historical test record

**Last updated:** November 15, 2026  
**Board:** Orange Pi Zero 3W, Allwinner A733 / sun60iw2p1  
**Target:** Linux 6.18.19, A733 platform support, native DRM/HDMI, one image for supported RAM variants  
**Publication status:** Engineering investigation, **not a bootable Linux 6.18 release**

> **Most important result: A2P and A2V both boot on physical hardware. A2 and A2M do not.**
>
> The original vendor boot process works when it is preserved, including when its exact `boot.scr` is executed as a second-stage script. Recreating a seemingly equivalent boot process can produce the same frozen Orange Pi splash even with the original vendor kernel. **We have not proved that Linux 6.18 is the cause of the splash, and we have not yet proved Linux 6.18 executes on this board.**

This document is a chronological, evidence-based account of the attempts made to bring Linux 6.18.19 to the A733-based Orange Pi Zero 3W. It consolidates the existing [mainline repository](https://github.com/mkinderwater/orangepi-zero3w-linux-mainline) records, hardware observations, the vendor-kernel image project, the M2 series, hybrid integration revisions 0.2.0 through 0.2.7, SD-card diagnostics, and the November 15 stock-image controls. It is intended to spare other developers repeated failures while distinguishing confirmed behavior from hypotheses.

**Terminology:** `PASS (hardware)` means an actual positive board observation reported by the operator; `PASS (offline)` means compilation, filesystem, image or checksum validation only; `HANG OBSERVED` means the last HDMI frame remained visible but the CPU's execution point was not measured; `NOT TESTED` means no hardware outcome was supplied. A manual `record --state PASS` operation does **not** measure a physical boot.

---

## 1. Executive summary

The known-good vendor Linux **6.6.98-sun60iw2** boots with HDMI, Wi-Fi and SSH. The separate `opi-3w-wbuild` project also produced a working vendor-kernel image with an extra FAT32 configuration partition after fixing a real ext4 boot-file allocation problem. The experimental Linux **6.18.19** kernel and its matching initramfs and modules **compile**, including hybrid **0.2.7** with built-in A733 display engine, TCON and HDMI driver objects. No test has yet positively identified Linux 6.18 running on the physical Zero 3W.

The later bootloader experiments are more instructive than another kernel rebuild:

| Control | Kernel / data | Layout | Boot path | Actual result |
| --- | --- | --- | --- | --- |
| **A1** | Original vendor 6.6.98, vendor DTB and initramfs | Stock, one ext4 partition | Original vendor `boot.scr` / `bootm` | **Historically boots**, not freshly reflashed during this A-series batch |
| **A2** | Vendor 6.6.98 with experimental raw-Image / initrd handling | Stock, one ext4 | Rewritten `booti` handoff | **HANG OBSERVED**, unchanged splash |
| **A2M** | Original vendor `uImage`, `uInitrd` and DTB | Stock, one ext4 | Rewritten **two-stage `bootm`** procedure | **HANG OBSERVED**, unchanged splash |
| **A2P** | Original vendor files | Stock, copied and boot-normalized ext4 | **Original `boot.scr` retained** | **PASS (hardware)**, confirmed November 15 |
| **A2V** | Original vendor files | Stock, one ext4 | **Minimal first stage invokes byte-identical vendor `boot.scr` as stage two** | **PASS (hardware)**, confirmed November 15 |

**Supported inferences:**

1. A2P demonstrates that copying the stock image and running the proven ext4 `/boot` normalizer does not, by itself, prevent the stock vendor boot.
2. A2V demonstrates that a *two-stage U-Boot script is viable* when the original vendor boot semantics are preserved. It is not necessary to replace U-Boot or TF-A simply because the script has two stages.
3. A2M demonstrates that the frozen splash can occur **with the original vendor 6.6 kernel, vendor DTB, vendor initramfs, stock one-ext4 layout and `bootm`** when our script is rewritten. Therefore the symptom does **not require** Linux 6.18, `booti`, or the extra FAT32 partition.
4. A2M changed multiple details simultaneously, so the evidence does **not** yet identify whether the failing operation is the environment import, FDT handling, load addresses/order, command line, or a less obvious U-Boot interaction.
5. A2/A2M do **not** prove every `booti` or every custom partition layout is bad. They only demonstrate failure in those specific constructions.
6. The successful 0.2.7 **U-Boot FAT checkpoint** proves the script reached its `booti` call site. It does not prove Linux was entered or successfully mounted storage.

**Current priority:** Preserve A2P and A2V as immutable boot controls. Compare the *finished, decoded* A2V and A2M boot scripts and final environments, then change one operation at a time on top of **booting A2V**. Once that divergence is understood, adapt the working vendor script path to the matched 6.18 artifacts without discarding HDMI support.

## 2. Board identity, layouts and pinned source revisions

The target board is **Orange Pi Zero 3W (A733)**. It must not be confused with the H618-based Orange Pi Zero 3, Orange Pi Zero 2W, Orange Pi 4 Pro, or Radxa Cubie A7A/A7S. Those devices can provide SoC subsystem clues, not verified board wiring, DRAM training, or power topology.

### Partition and firmware layout

| Image family | Reserved firmware | FAT32 | Linux ext4 |
| --- | --- | --- | --- |
| Original Orange Pi 1.0.2 vendor Debian Trixie Server | First 32 MiB | None added by our tooling | **Starts 32 MiB**, LBA 65536 |
| `opi-3w-wbuild` 0.7.6 / M2db / hybrid custom layout | First 32 MiB | **Starts 32 MiB**, 64 MiB long, MBR partition 2 | **Starts 96 MiB**, LBA 196608, MBR partition 1 |

The custom image's **partition numbers are not in physical disk order**. That is legal. The stock-vs-custom offline inventory successfully mounted the original ext4 filesystem **read-only** and reported Boot0 and U-Boot package payloads identical between the inspected original donor and custom control. That is evidence about firmware bytes, **not** evidence that different boot scripts or root identifiers are equivalent.

The original stock donor file used for these tests is Orange Pi's `Orangepizero3w_1.0.2_debian_trixie_server_linux6.6.98.img`. Its location on the operator's workstation is intentionally omitted from this public record. No full vendor images or proprietary boot binaries are included here.

### Reproducible source identities

| Input | Pinned revision | Purpose |
| --- | --- | --- |
| Linux 6.18.19 | `4aea1dc4cad17cd146072e13b1fd404f32b8b3ef` | Base hybrid kernel |
| `alexcaoys/allwinner-bsp` | `656a550c826787e7e72fae58ca793df9e0988ac8` | Selected Allwinner clock, pinctrl, UART, TWI, PMIC, DRM and MMC integration |
| `jonas5/Allwinner-A733-kernel` | `fc71840a8b5bb17a73ed42cc00e46838a97c8aa1` | A733 integration reference, **not** Zero 3W hardware proof |
| `orangepi-xunlong/linux-orangepi` | `2ac08e8c7cdc28abbdc5c9a9dd812f887ae9c79f` | Vendor 6.6.98 Zero 3W reference |
| Older M2cn/M2co modified base | `908869c38e30ef03066387543f3ecf0212d15200` | Older A733 worktree, **already modified**, not clean upstream |

Source compilation, driver registration at runtime, and hardware success are three different acceptance gates. In particular, importing the 4 Pro display configuration does not prove it works on the Zero 3W.

## 3. Historical vendor boot-file failure: ext4 allocation

Before the Linux 6.18 investigation, a newly assembled *vendor Linux 6.6* image from the `opi-3w-wbuild` project remained at the bootloader splash despite logical kernel, DTB, initramfs and reserved boot-byte hashes matching working images. The failing 0.7.0 build had **347 sparse 4 KiB blocks in the kernel file** after `mkfs.ext4 -d` populated the filesystem.

The working remediation, retained in [`opi-3w-wbuild/scripts/boot_allocation.py`](https://github.com/mkinderwater/opi-3w-wbuild/blob/main/scripts/boot_allocation.py), is to:

1. Create the actual ext4 filesystem using the expected vendor filesystem profile.
2. Mount it **read-write** after the final boot files have been populated.
3. Snapshot file payload hashes, symlinks, hardlinks, metadata and ownership.
4. Rewrite and physically preallocate all regular `/boot` files, including regions that are logically zero, with no sparse holes.
5. Verify every hash and link/metadata invariant again.
6. Unmount, run fsck and keep an allocation audit of the finished filesystem.

A normalized vendor image physically booted, with HDMI/login and functional Wi-Fi, SSH, root expansion and GPU compute tests. **Do not claim sparse holes alone were proven causal:** mounting the ext4 filesystem also initializes/changes journal state, and the mount-only control did not establish the isolated trigger.

A later **M2cs** audit of a different finished experimental image checked **121 boot files with no sparse holes**. It is therefore incorrect to reuse the earlier sparse-file diagnosis for every later splash. **A2P now gives additional hardware confirmation that an untouched vendor boot script survives the copy-plus-normalization process.**

## 4. Historical M2 implementation and build chronology

The existing repository contains much of this work in [`docs/development-history.md`](https://github.com/mkinderwater/orangepi-zero3w-linux-mainline/blob/main/docs/development-history.md), the [M2cn report](https://github.com/mkinderwater/orangepi-zero3w-linux-mainline/blob/main/docs/m2cn-isolated-build-2026-11-14.md), and the [boot handoff investigation](https://github.com/mkinderwater/orangepi-zero3w-linux-mainline/blob/main/docs/boot-handoff-and-failures.md). The entries below preserve the difference between compilation and execution.

| Stage | What was done | Recorded result and limitation |
| --- | --- | --- |
| **M2o** | Initial Zero 3W board DTS; MMC not ready | DTB compile, not boot-ready |
| **M2r** | Experimental AXP8191 minimal provider for DCDC1, CLDO5 and DC1SW2 | Source/build evidence; no safe-voltage hardware proof |
| **M2bp–M2bx** | Board pin mapping, MMC and PMIC supply relationships from vendor DTS | Static evidence only |
| **M2by** | Early PMIC integration | Incorrect `r_i2c0_pins` label broke the build |
| **M2bz / M2ca** | Corrected R-I2C pinctrl to `&r_i2c0_pl_pins`; configured MMC | Kernel and DTB compiled, not proof of boot |
| **M2cb** | Restricted PMIC regmap writes to verified low registers `0x10`, `0x11`, `0x12`, `0x21`, `0x33` | Compile and consistency checks; **not a read-only PMIC**, no runtime rail-state proof |
| **M2cf** | Reviewed 0.7.6 vendor boot script, memory addresses, root UUID and partition layout | Offline boot-chain investigation |
| **M2cg** | Built legacy kernel header / boot package experiments | Fixed missing `mkimage`, `find | head` under `pipefail` (exit 141), and WSL partition-offset handling |
| **M2ch** | Staged **1,426** matching ARM64 kernel modules | Installation success; `INSTALL_MOD_STRIP=0` incorrectly selects stripping, corrected by using an empty argument |
| **M2ci** | Direct-root and separate initramfs candidates | Offline preparation only |
| **M2ck** | Verified I2C fallback; corrected device-tree build target to `m2by` | Compile success |
| **M2cl** | Dual-path image with original vendor recovery branch, dense-file normalization | Offline image verified; experimental Linux not executed |
| **M2cm UNARMED** | Vendor boot branch active, experimental Linux files present but not selected | **Physical PASS:** HDMI Debian login, Wi-Fi, SSH; `uname -r` = `6.6.98-sun60iw2` |
| **M2cn** | Isolated source reconstruction and cross-compile | Kernel and DTB compiled; **841 untracked candidates** copied and **16 held for review** |
| **M2co** | Rebuilt against modified base and compared outputs | Matching DTB checksum; not a standalone reproduction from unmodified upstream |

The M2cn source base already contained substantial A733 changes, so its apparent clean reconstruction does not mean the published patch set is sufficient to build directly against unmodified Linux 6.18.19.

## 5. Historical M2 hardware boot experiments

| Test | Configuration | Actual observation | Correct conclusion |
| --- | --- | --- | --- |
| **M2cp** | Linux 6.18 raw ARM64 `Image` via `booti`, no initramfs | Bootloader splash remained | No confirmed kernel entry |
| **M2cr** | Linux 6.18 with static ARM64 BusyBox diagnostic initramfs | Same splash; no persistent root log | Failure stage unknown |
| **M2cs** | Offline inspection of M2cr ext4 boot allocation | All 121 boot files dense | Historical sparse-hole defect not evident in that image |
| **M2ct LEGACY / RAW** | Different ramdisk and handoff formats | Logo/splash remained | Neither demonstrated Linux entry |
| **M2cv CONTROL** | Vendor 6.6.98 `bootm` branch | **Debian HDMI login** | Vendor control physically works |
| **M2cv DIAG** | Linux 6.18 `booti` with matching diagnostic initramfs | Splash remained | Kernel entry unconfirmed |
| **M2cv DIRECT** | Linux 6.18 `booti` without initramfs | Splash remained | Original failure does not require the initramfs |
| **M2cx DIRECT** | Added 24 MHz clock and tentative PB9/PB10 UART mapping | Same splash | DT edits insufficient; physical Linux UART routing not proven |
| **M2cy** | Decoded finished scripts / `root=` construction | Root command-line construction present | Earlier missing-`root=` hypothesis unsupported |
| **M2da RAW-INITRD** | Vendor 6.6.98 kernel, experimental `booti`, possible `bootm` fallback | **Photographed Linux VFS panic at about 3.8 seconds** | Vendor Linux executed; whether entry was through `booti` remains ambiguous |
| **M2db v4** | Two-stage no-fallback vendor raw `booti` candidate | Completed offline packaging and script checks | Not independent proof of 6.18 execution |
| **M2dc** | Static boot/script, Linux 6.18 component, and kernel target selection audits | Analyzed staged artifacts / configurations | Inspect and compile evidence, not verified hardware boot |

### The observed M2da panic

The photographed console showed the vendor kernel `6.6.98-sun60iw2` stopping at:

```text
[    3.792147] Kernel panic - not syncing: VFS: Unable to mount root fs on unknown-block(0,0)
```

This proves an actual **vendor 6.6.98 kernel entered and reached the root-mount path** in that test. It does **not** demonstrate a Linux 6.18 boot. Because the script may have retained a fallback `bootm` after `booti` returned, the photograph alone **cannot identify which handoff mechanism executed**. `unknown-block(0,0)` is not enough to choose among wrong root identifier, unavailable block device, MMC power, absent/malformed initramfs, or other storage faults.

### A confirmed U-Boot script memory overlap

The vendor bootloader's default script address was **`0x43100000`**. One earlier Linux 6.18 raw Image was loaded at **`0x41000000`**, extended past **`0x43729A00`** by actual file bytes and declared a footprint to roughly **`0x437F0000`**. This overlaps the script still resident/executing at `0x43100000`.

The M2cv family introduced a tiny first-stage script and relocated stage two to **`0x46000000`**, with DTB staging around **`0x44000000`** and initramfs staging around **`0x45000000`**. This removes the obvious script-overwrite problem. It does **not** establish that the vendor `booti` path, ATF/BL31 region, initrd relocation, and CPU entry obey all other firmware constraints.

### A separate confirmed M2cr BusyBox bug

The ARM64 BusyBox binary installed in an early diagnostic initramfs offered `findfs`, `mount` and `switch_root`, but **not `blkid`**. Its `/init` called `busybox blkid` to find the ext4 root UUID and would never match even if Linux reached it. The source was corrected to use `busybox findfs UUID=...`. This was a deterministic userspace bug; it cannot explain M2cp, which had no initramfs.

## 6. Hybrid Linux 6.18.19 integration, revisions 0.2.0 through 0.2.7

The later hybrid used frozen Linux 6.18.19, selected Allwinner BSP components, the Zero 3W vendor-derived DTB, a matching static C initramfs, and fail-closed source transformation tests. Initial packages built *boot sets*, not complete flashable images.

| Version | First observed failure / change | Result or correction |
| --- | --- | --- |
| **0.2.0** | `sunxi_uart_startup: expected one function definition` before compile | Naive C string masking swallowed functions due to backslash-continued string literals; lexer repaired |
| **0.2.1** | `sunxi_uart_set_termios: expected one function definition` | Conditional preprocessor directives inside function parameters needed parsing support |
| **0.2.2** | Boot-critical Kconfig check rejected disabled `SERIAL_EARLYCON`, `TMPFS`, `AW_SERIAL_EARLYCON`, `AW_TWI`, AXP2101 MFD/I2C/regulator options | Added correct `SHMEM`, `AW_DMA`, I2C/PMIC and serial dependency chain |
| **0.2.3** | Compiler error: `struct uart_port` has no member `rs485conf` in `sunxi-uart-ng-core.c` | RS485 configuration belongs to containing Allwinner `sunxi_uart_port`; mocked type had hidden the bug; added GCC negative regression test |
| **0.2.4** | RS485 field owner and mock corrected | Native/host tests passed; no separate successful full host compile recorded |
| **0.2.5** | Removed a hardcoded 1 GiB DTS memory override and audited firmware-derived RAM sizing | **First successful complete WSL build:** Linux Image, module install/`depmod`, static matching AArch64 `/init` |
| **0.2.5 FLASH-TEST** | Custom FAT32+ext4 image flashed | Static Orange Pi splash; solid red light, unverified as software status LED; `/boot/mainline/hybrid-0.2.5/` and matching module tree existed, but no `/var/log/opi3w-hybrid/` |
| **0.2.5 TRACE** | Separate pre-kernel U-Boot checkpoint image assembled | Offline assembly succeeded; no distinct hardware result supplied for this particular image |
| **0.2.6** | Selected A733 DE/TCON/HDMI DRM integration; Kconfig rejected `DRM_CLIENT_SELECTION`, `DRM_FBDEV_EMULATION`, `DRM_CLIENT_DEFAULT_FBDEV`, `FB_CORE`, `FRAMEBUFFER_CONSOLE` | Allwinner driver selected `DRM_CLIENT` but missed hidden Linux 6.18 `DRM_CLIENT_SELECTION` dependency |
| **0.2.7** | Added DRM client dependency; preserved pre-kernel FAT trace and Linux FAT checkpoints | **Full kernel/modules/initramfs cross-build succeeded with HDMI driver code compiled**; hardware flash still remained at splash, with no Linux persistent logs |

The **0.2.7 HDMI objective remains open**. Selecting DE352, TCON, HDMI 2.0, DRM fbdev emulation, and `console=tty0` in a compiled kernel is not proof that the display PHY powers up, EDID/HPD works, a connector/CRTC registers, or a visible console appears. HDMI is not proof of kernel entry if its initialization fails.

A different historical assembly error accidentally carried a **6.6.98 vendor initramfs with a 6.18 kernel**. Do **not** conflate that older problem with 0.2.5/0.2.7, whose static ARM64 initramfs builds used the expected kernel release. Verify the final flashed image payloads by hash before inferring a mismatch.

## 7. 0.2.7 FAT diagnostic archive: what the files actually say

The operator supplied `E.zip`, containing **22 files** from the FAT32 diagnostic partition of a 0.2.7 hardware test. The log entries identify release **`6.18.19-opi3w-hybrid-0.2.7`**, build ID:

```text
e07cb06059c8ffbf604a5e0b0a2ab95d1378055034361836c44f1fa721e9a9dc
```

Direct inspection of the uploaded archive confirmed:

| File | Actual recorded status | Meaning |
| --- | --- | --- |
| `S2ENT.LOG` | `REACHED` | U-Boot stage two entered |
| `KLOAD.LOG` | `REACHED` | Kernel load command reported success |
| `DLOAD.LOG` | `REACHED` | DTB load reported success |
| `RLOAD.LOG` | `REACHED` | Ramdisk load reported success |
| `PREBOOT.LOG` | `REACHED` | U-Boot reached the command immediately before `booti` |
| `RETURN.LOG` | `NOT_REACHED` | No return checkpoint; not proof Linux ran |
| `KFAIL.LOG`, `DFAIL.LOG`, `RFAIL.LOG` | `NOT_REACHED` | Corresponding load-failure paths were not recorded |
| `OPI3W.LOG` | **Zero bytes** | No Linux `/init` FAT checkpoint |
| `BOOT-STATUS.TXT` | `BUILD-ONLY` | No Linux/systemd boot service marker |
| ext4 `/var/log/opi3w-hybrid/` | **Absent** | No persistent root-mounted Linux logs |

**Do not mistake the `.MRK` files for execution evidence.** They are prebuilt marker *templates* containing `REACHED`; the `.LOG` files reflect on-card updates. The Linux FAT logger runs only once PID1 and the Linux SD/FAT stack are usable, so an empty `OPI3W.LOG` cannot separate a failed U-Boot handoff from a kernel, MMC, PMIC, or FAT mount failure.

The same experimental image had a compiled HDMI driver, but the unchanged splash is still an inconclusive Linux-entry marker. The red LED being solid is also inconclusive unless its physical identity and trigger are confirmed.

## 8. November 15 stock image isolation, what changed and what didn't

The original single-ext4 vendor image was mounted and audited read-only:

```text
AUDITED_NOT_FLASHABLE
A2: CANDIDATE_NEEDS_TEST
B1/B2 bootloader payload identical: True
```

Those lines are **offline inventory results**, not proof of a hardware boot. A subsequent script invocation with `record --test A1 --state PASS` created a manually declared status; the operator clarified that A1's evidence was **prior historical boot experience**, not a fresh card test. This distinction is retained in the test table.

### Why A2M was a weak control

Source audit of A2M against the published vendor [`boot-sun60iw2.cmd`](https://github.com/orangepi-xunlong/orangepi-build/blob/next/external/config/bootscripts/boot-sun60iw2.cmd) found several simultaneous departures:

| Boot operation | Original vendor boot | Failing A2M |
| --- | --- | --- |
| Kernel and initramfs | Stock `uImage` and `uInitrd` | Same originals |
| Kernel handoff | `bootm` | `bootm` |
| Boot script | Single stock `boot.scr` | Rewritten two-stage script |
| Boot environment | Imports `orangepiEnv.txt` when present | Import skipped |
| Kernel/DTB/ramdisk addresses | Established vendor environment | Forced addresses around `0x41000000`, `0x44000000`, `0x45000000` |
| Load order | Initrd, kernel, DTB | Kernel, DTB, initrd |
| FDT processing | `fdt addr`, `fdt resize`, optional overlays | FDT commands and overlays omitted |
| Kernel command line | Vendor-generated arguments, root selection and board flags | Smaller hardcoded subset |

**A2M's hang proves none of these individual changes is the cause.** It demonstrates only that the combination did not reproduce the stock boot behavior.

### Why A2P and A2V are much stronger controls

The later `vendor_controls.py` implements two matched alternatives against the *same* original stock image:

- **A2P:** Copy the stock image without replacing `boot.scr`, kernel, DTB, initramfs or firmware. Run mounted-ext4 boot-file normalization and check hashes. **The operator confirmed this image boots.** This rejects the claim that copying plus normalization necessarily breaks the stock image.
- **A2V:** Store the original compiled vendor `boot.scr` byte-for-byte at `/boot/mainline/stock-vendor-stage2.scr`. Replace only `/boot/boot.scr` with a tiny first-stage script that loads the stored original at `0x46000000` and invokes `source 0x46000000`. Vendor environment, FDT handling, overlays, load order and `bootm` remain in the unchanged vendor second stage. **The operator confirmed this image boots.** This rejects the claim that two-stage sourcing is inherently incompatible with the vendor bootloader.

A2V's first-stage logic, excerpted for reproducibility:

```bash
if ext4load mmc 0:1 0x46000000 /boot/mainline/stock-vendor-stage2.scr; then
    source 0x46000000
fi
# If the stage returns, stop. There is no experimental fallback.
```

**Most important next inference:** A2M and A2V differ in the *substance* of the second-stage script. The original vendor script now serves as the first reliable template for our next boot experiments. Preserve the A2P and A2V image files and their audit JSONs, along with the original vendor `.img`. Do not replace them in place.

## 9. Additional official boot-package research, verified November 15

The official [`orangepi-xunlong/orangepi-build` sun60iw2 boot-package directory](https://github.com/orangepi-xunlong/orangepi-build/tree/next/external/packages/pack-uboot/sun60iw2) provides further context and important warnings.

### Official package contents

Its `bin/` directory contains distinct images:

- `boot0_sdcard.fex`
- `boot0_sdcard_a733.fex`
- `boot0_sdcard_orangepizero3w.fex`
- `boot0_sdcard_orangepizero3w_1800M.fex`
- `boot0_spinor_a733.fex`
- `boot0_ufs_a733.fex` and `boot0_ufs_orangepizero3w.fex`
- `monitor.fex`, `scp.fex`, `boot_package.cfg`, `sys_config/sys_config.fex` and `dts/u-boot-current.dts`

This is **concrete evidence that board-specific Boot0 / DRAM training variants are published**. It does **not** mean we can safely interchange them on an arbitrary RAM SKU. The inspected official package recipe is:

```ini
[package]
item=u-boot, u-boot.fex
item=monitor, monitor.fex
item=scp, scp.fex
;item=optee, optee.fex
```

That confirms a package with distinct U-Boot, monitor and SCP components. A working kernel depends on more than an ext4 image and a `boot.scr`; Boot0 memory training, U-Boot, trusted monitor firmware, supplied FDT and memory reservations can all matter. **Do not overwrite the proven Boot0 or boot package just to test the Linux kernel.**

### The bootloader UART pin evidence and its limit

The published `sys_config.fex` defines:

```ini
[uart_para]
uart_debug_port = 0
uart_debug_tx   = port:PB09<2><1><default><default>
uart_debug_rx   = port:PB10<2><1><default><default>
```

This is evidence of a **boot firmware debug-UART configuration**, not proof that our Linux 6.18 UART device-tree node has the correct pinctrl or that the pins are exposed on the board's accessible connector. The **pinned vendor Zero 3W Linux DTS** previously inspected has empty UART0 pinctrl pin strings, and PB9/PB10 also appear in a vendor TWI8 definition. These observations concern different configuration layers and are **not sufficient to assign a physical Linux UART connection** without a hardware pinout and measured serial output.

The same official directory's `dts/u-boot-current.dts` identifies a generic **T736 / T736-DEMO-AIOT** board. **Do not deploy that U-Boot DTS as the Zero 3W board DTB.** Its AXP8191, HDMI and MMC nodes are useful reference material, not proof of Zero 3W electrical routing.

### Relation to dlan17's newer A733 boot chain

The independent [`dlan17/a733/boot-sdcard.md`](https://github.com/dlan17/a733/blob/main/boot-sdcard.md) documents keeping vendor Boot0 for DDR training while packaging a newer A733 U-Boot and TF-A. That guide calls out an explicit SPL/U-Boot **load-address overlap** and moves an SPL load address from `0x4a000000` to `0x48000000`. The example writes Boot0 at **128 KiB** while the audited Zero 3W stock image's Boot0 header starts at **8 KiB**. Its packaged boot-stage placement corresponds to **16,793,600 bytes**, matching our vendor boot-package area, but image contents and protocols are not necessarily compatible.

**Do not run the guide's `dd` offsets against the stock Zero 3W image without a complete firmware compatibility audit.** A2P and A2V now prove the currently retained bootloader can boot stock Linux, so replacing it should not be the default next experiment.

### Android Boot0 and 12 GB RAM

The related [Incipiens Android 12 GB Boot0 investigation](https://github.com/Incipiens/orange-pi-zero-3w-12gb-android-fix) reports that different DRAM training profiles in the stock Android Boot0 prevented its 12 GB board from booting; transplanting **verified parameters** from an official Linux Boot0 repaired that *Android* image. It does **not** establish a Linux 6.18 failure cause for our current board, but reinforces the requirement to qualify each memory variant and avoid a hardcoded 1 GiB `/memory` node. The hybrid removed that override in 0.2.5. A published U-Boot source also contains a 2048 MiB memory-size clamp; whether that is present in the **exact retained donor firmware** is unverified.

## 10. Outstanding technical risks, ranked by evidence

| Risk / hypothesis | What supports investigating it | What would establish or reject it |
| --- | --- | --- |
| **Rewritten vendor script semantics** | A2V boots; A2M fails on same kernel/layout/handoff family | Reproduce a failure by changing **one vendor-script operation** at a time and verify final executed commands |
| **Firmware handoff to raw ARM64 Linux** | Many experimental `booti` trials remain at splash; earlier script-address overlap confirmed | Vendor no-fallback `booti` control with positively identified vendor kernel entry or return code; audit BL31 and initrd relocation |
| **Kernel/device-tree initialization** | 6.18 hybrid platform is a selective BSP port | Independent early kernel/PID1 signal on board, before MMC root mounting |
| **PMIC/I2C/MMC probe and voltage handling** | AXP8191 and SD rail dependencies; separate Zero 3W project reports failures here | Linux log shows regulator and MMC device registration, card voltage negotiation, then block device enumeration |
| **Initramfs and root selection** | Linux FAT and root logs absent; earlier BusyBox and mixed-ABI packaging errors occurred | Linux-independent init signal and staged root discovery logs; exact payload hashes and `root=` value |
| **HDMI/KMS** | 0.2.7 compiles selected A733 DRM drivers but never takes over HDMI visibly | Real connector/CRTC and EDID, mode set, display pipeline, power rails and fbcon proof |
| **Filesystem layout** | Custom FAT+ext4 differs from stock | Matched B1/B2 images differing **only** in partition geometry/root ID after script path is proven |
| **RAM-size reporting / Boot0 variants** | Multiple capacity SKUs and published Boot0 profiles | Boot0 training and U-Boot FDT `/memory` banks plus Linux `MemTotal` tested across capacities |

The leading hypothesis has changed following A2P/A2V. **Investigate boot-script equivalence before rebuilding the 6.18 kernel or changing PMIC/HDMI drivers.** Once the script is proven, kernel/platform diagnostics become meaningful.

## 11. Next controlled experiments: do this before another speculative build

### Batch S: binary-search the boot script against the proven A2V control

Start with the **working A2V** image, which sources the **original compiled vendor `boot.scr`**. Extract the actual executed script bytes from the **finished images**, not the assembler's string templates. Decode both A2V and A2M with a compatible U-Boot script tool (`dumpimage -T script`, or an independently verified legacy script header parser).

1. **Capture and preserve evidence:** Full SD-card image SHA256, original vendor script SHA256, A2V first-stage and second-stage script SHA256, exact bootloader/firmware hashes and root partition UUID. Record the A2V physical boot observation.
2. **Diff the actual boot scripts:** Compare `orangepiEnv.txt` parsing, all `setenv`, `part uuid`, `${devtype}`, `${devnum}`, `${prefix}`, `${filesize}`, `load`, `fdt addr`, `fdt resize`, overlays, `bootm` and bootargs; do not compare generated script source alone.
3. **Test hypothesis S1:** Change **only** environment import behavior on an A2V-derived image while retaining addresses, FDT commands and boot order. Compare against untouched A2V.
4. **Test hypothesis S2:** Starting again from untouched A2V, change **only** FDT setup (one operation, such as `fdt addr` or `fdt resize`) while retaining environment import, addresses and boot order. Do not combine S1 and S2 modifications in one image.
5. If neither change reproduces failure, test load addresses, load order, overlays and the exact bootargs one at a time, always starting from the verified A2V base. Keep a separate physical result and full image hashes for each branch.

For both competing hypotheses in a test batch, preserve a known-good control card. A test that simply leaves the splash intact must be reported as **observed no-login/no-display progress**, not as an identified kernel crash.

### Batch K: integrate the **unchanged** 0.2.7 kernel with the proven script semantics

Only after understanding script differences, build a stock-layout experimental image that preserves the vendor initialization flow while substituting the **matched 6.18.19 `Image`, exact Zero 3W DTB, and matching 6.18 initramfs**. A successful vendor `bootm` script cannot be reused *literally* with a raw ARM64 `Image`; any necessary `booti` change must be separately justified and verified. Confirm:

- ARM64 Image header magic, declared memory footprint, entry/load semantics and alignment.
- No overlap among the boot script (especially `0x43100000` and `0x46000000`), kernel, DTB, initramfs, BL31/secure region or reserved DRAM.
- Correct DTB source and **source plus compiled and loaded DTB hashes**, not just a file named Zero 3W.
- Exact initramfs format and release. Do not accidentally reuse vendor 6.6.98 initramfs with Linux 6.18.19.
- Final **expanded** `bootargs` after all U-Boot environment imports, including root identification and `console=tty0` when HDMI is expected.
- `booti` return handling: no silent vendor `bootm` fallback that could masquerade as a hybrid success.

If that still gives no positive Linux entry evidence, use a **storage-independent `/init` checkpoint** with a proven GPIO or UART. The 6.18 HDMI driver is retained, but its silence cannot establish early CPU execution failure.

### Batch F: filesystem layout as one independent variable

Only once a known working hybrid boot path is available, compare stock single-ext4 B1 with custom FAT32+ext4 B2. Require **SHA256-identical** kernel, DTB, initramfs and known U-Boot components. Kernel arguments and scripts must be functionally equivalent, differing only in root partition identification or location. A previous image assembler's offline success is not a substitute for this paired hardware experiment.

### Finish product acceptance

Require: Linux `uname -r` proving 6.18.19, reliable MMC/ext4 mount and userspace, functional HDMI **mode setting/console**, networking as required, and correct RAM recognition on each supported capacity. Only then consider publishing a bootable binary release. The current repository should remain labeled experimental.

## 12. Known hashes and evidence locations

| Artifact | Value / result | Caution |
| --- | --- | --- |
| Historical M2 compiled DTB | `577f128db2e67a7208451413bdd36b5280253e2e98d23382aa4a3bc8568243e2` | Different from hybrid 0.2.x DTB |
| M2cn isolated reconstructed `Image` | `59877d59304bad5dc46f61e7f881eea5f4c8433248be4de1f4ce0dd1e2f5faf5` | Different earlier modified source branch |
| 0.2.5 FLASH-TEST image | `23376f0b8e477f8708a0f7ea16cdb887efd98dd398f386d2454467821f489e62` | Assembled image, not a kernel boot success |
| 0.2.5 U-Boot trace assembled image | `ede6ce4a8abbda0f94a54e41957f25a046368127ff908f902eebb2c415533a0c` | Offline assembled, no independent hardware result recorded |
| 0.2.7 diagnostic **build ID** | `e07cb06059c8ffbf604a5e0b0a2ab95d1378055034361836c44f1fa721e9a9dc` | **Not** the SD image SHA256 |
| A2P image SHA256 | **Not supplied in this record** | Do not infer from name |
| A2V image SHA256 | **Not supplied in this record** | Do not infer from name |
| A2M image SHA256 | **Not supplied in this record** | Do not infer from name |

The A2P/A2V image builders retain `.audit.json` and `.sha256` sidecars locally in the operator's WSL environment. Those should be added as sanitized **text-only provenance evidence** once available, not replaced by guessed hashes. The existing repository contains M2ca/M2cb, M2cn/M2co, M2cr, M2da, ext4, PMIC and HDMI source audits.

## 13. Per-test acceptance manifest (copy for every new image)

```yaml
test_id: A2V
result: HARDWARE_PASS_OPERATOR_REPORTED
date: 2026-11-15
board: Orange Pi Zero 3W (A733)
ram_variant: UNKNOWN
image_sha256: UNKNOWN
image_size_bytes: UNKNOWN
donor_sha256: UNKNOWN
boot0_sha256: UNKNOWN
boot_package_sha256: UNKNOWN
first_stage_boot_scr_sha256: UNKNOWN
second_stage_boot_scr_sha256: UNKNOWN
kernel_image_sha256: UNKNOWN
initramfs_sha256: UNKNOWN
dtb_loaded_path_sha256: UNKNOWN
dtb_in_memory_sha256: UNVERIFIED
source_dts_sha256: UNKNOWN
included_dtsi_sha256: {}
dtc_command: UNKNOWN
expanded_bootargs: UNVERIFIED
kernel_staging_address: UNKNOWN
fdt_staging_address: UNKNOWN
ramdisk_staging_address: UNKNOWN
firmware_monitor_reserved_regions: UNKNOWN
boot_method: stock_vendor_bootm_via_preserved_stage2
observed_result: BOOTED
recorded_by: operator
runtime_kernel_version: NOT_CAPTURED_FOR_THIS_RUN
notes: Two-stage U-Boot sources the original vendor boot.scr unchanged.
```

`UNKNOWN` is an acceptable honest value until evidence becomes available. A reported **hardware PASS** and a **provenance-complete** test are different states. No script-generated `PASS` record is accepted as physical observation without the test operator's confirmation.

## 14. References

### Primary project records

- [Project: orangepi-zero3w-linux-mainline](https://github.com/mkinderwater/orangepi-zero3w-linux-mainline)
- [Historical M2 development record](https://github.com/mkinderwater/orangepi-zero3w-linux-mainline/blob/main/docs/development-history.md)
- [Boot script, addresses and M2-series hardware failures](https://github.com/mkinderwater/orangepi-zero3w-linux-mainline/blob/main/docs/boot-handoff-and-failures.md)
- [M2da photographed vendor VFS panic](https://github.com/mkinderwater/orangepi-zero3w-linux-mainline/blob/main/docs/orange-pi-zero-3w-uboot-booti-kernel-panic-m2da.md)
- [M2cr BusyBox `blkid` bug](https://github.com/mkinderwater/orangepi-zero3w-linux-mainline/blob/main/docs/m2cr-initramfs-root-discovery.md)
- [M2cn reconstruction limits](https://github.com/mkinderwater/orangepi-zero3w-linux-mainline/blob/main/docs/m2cn-isolated-build-2026-11-14.md)
- [AXP8191 and MMC dependencies](https://github.com/mkinderwater/orangepi-zero3w-linux-mainline/blob/main/docs/pmic-mmc-and-i2c.md)
- [Working vendor HDMI reference](https://github.com/mkinderwater/orangepi-zero3w-linux-mainline/blob/main/docs/vendor-hdmi-baseline.md)
- [Working image builder and ext4 boot allocation](https://github.com/mkinderwater/opi-3w-wbuild)

### External hardware and firmware research

- [Official Orange Pi sun60iw2 boot script](https://github.com/orangepi-xunlong/orangepi-build/blob/next/external/config/bootscripts/boot-sun60iw2.cmd)
- [Official Orange Pi sun60iw2 Boot0 and package files](https://github.com/orangepi-xunlong/orangepi-build/tree/next/external/packages/pack-uboot/sun60iw2)
- [Zero 3W's public A733 vendor and PMIC/boot research by nickyg666](https://github.com/nickyg666/orangepi-zero3w-mainline)
- [A733 display subsystem integration reference from jonas5](https://github.com/jonas5/Allwinner-A733-kernel)
- [dlan17: A733 boot-from-SD and alternate U-Boot/TF-A chain](https://github.com/dlan17/a733/blob/main/boot-sdcard.md)
- [Incipiens: official Android 12 GB Boot0 DRAM parameter correction](https://github.com/Incipiens/orange-pi-zero-3w-12gb-android-fix)
- [XDA article about the Zero 3W and Android TV usage, supplied as context](https://www.xda-developers.com/orange-pi-zero-3w-android-boot-using-as-tv/) (not used for direct technical assertions; article contents were not independently verified)

## 15. Publication safety and known limitations

This report contains code-level observations and sanitized test outcomes. It **does not redistribute** whole stock SD images, TOC1/U-Boot packages, proprietary vendor firmware, unreviewed Allwinner or PowerVR source, device serial numbers, credentials, private networks or individual users' home directories. The A733 source merges and DRM port require license and attribution review before publishing complete patches. Statements about other developers' reported hardware results are attributed to their projects and are not our own hardware confirmations.

**Status at publication:** **A2P PASS, A2V PASS, A2/A2M HANG, hybrid Linux 6.18.19 build PASS, hybrid Linux 6.18.19 hardware boot UNVERIFIED.** Next practical work is a one-difference-at-a-time A2V-vs-A2M boot script investigation, **not** another uncontrolled rebuild. HDMI remains a mandatory acceptance target once kernel entry and root boot are established.
