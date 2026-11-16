# Orange Pi Zero 3W: what other projects found vs what we proved

Reviewed: **2026-11-15**. This is a direct comparison of source claims and **our own experiments**, not a claim that we independently witnessed any other person's hardware. The word **mainline** needs a qualifier: Linux **6.18.19 plus out-of-tree Allwinner BSP drivers** is a **hybrid kernel**, not A733 support integrated into unmodified upstream Linux.

## How to read this report

- **SOURCE FACT:** Actual code, config, file, commit or text inspected in a repository. This proves what is *published*, not what happens on the device.
- **OTHER PROJECT REPORT:** The counterpart's description of a real test, command output, screenshot or hardware result. Legitimate evidence, **not independently repeated by us**.
- **OUR HARDWARE OBSERVATION:** Output or behavior from our own identified board/image trial, including actual SSH and FDT data.
- **OUR OFFLINE CHECK:** Build, source diff, checksum or image audit. Does not prove boot.
- **INFERENCE / OPEN:** An explanation or plausible cause without an isolated physical test.

Do not convert “build succeeds” into “hardware works,” “someone else reports a boot” into “our image boots,” or “bootloader splash remained” into “the CPU did not enter Linux.”

## At a glance: counterpart vs our project

| Project | What its repository actually says or provides | Their hardware status on **Zero 3W** | What **we** confirmed | What remains open |
| --- | --- | --- | --- | --- |
| [nickyg666/orangepi-zero3w-mainline](https://github.com/nickyg666/orangepi-zero3w-mainline) | Hybrid 6.18.19, BSP UART/TWI/MMC/PMIC, boot script, dated working-session notes | **OTHER PROJECT REPORT:** Ubuntu 26.04 boots via UART (Aug 13); AIC8800 Wi-Fi, PowerVR kernel and Mesa Vulkan/zink reported Aug 14-16 | **OUR HARDWARE:** 6.6.98 vendor boots; **our** 6.18 HBI/K2/F2 not confirmed entering Linux | Reproducing *their exact* image and independently verifying their USB/HDMI/PowerVR results on our board |
| [jonas5/Allwinner-A733-kernel](https://github.com/jonas5/Allwinner-A733-kernel) | A733 patch, boards and boot documentation; 4 Pro/Cubie A7* integrations | **SOURCE FACT:** board matrix labels Zero 3W **Platform Ready**, not **Fully Validated**; validation shown for other A733 boards | **OUR HARDWARE:** Zero 3W stock 6.6.98 HDMI/SSH, F1 hybrid DTB headless boot | Cannot assume Orange Pi 4 Pro bootloader, clocks, pinmux, DRAM or console fixes are safe for Zero 3W |
| [orangepi-xunlong/orangepi-build](https://github.com/orangepi-xunlong/orangepi-build) and [linux-orangepi](https://github.com/orangepi-xunlong/linux-orangepi) | Official A733 board config, Zero 3W DTS, Boot0 package, vendor kernel 6.6.98 | **SOURCE FACT:** vendor 6.6.98 build inputs; official stock image is a hardware control in our investigation | **OUR HARDWARE:** stock vendor 6.6.98 HDMI, Wi-Fi, root, SSH; newly rebuilt control/identity compile only | Source revision not guaranteed byte-identical to distributed official image; freshly built binaries not flashed |
| [alexcaoys/allwinner-bsp](https://github.com/alexcaoys/allwinner-bsp) | BSP source for A733 subsystems and vendor driver matching | **SOURCE FACT:** code reference, **no claim here of our board running this exact imported source** | **OUR OFFLINE:** 6.18 hybrid Image+DTB and MMC/TWI/PMIC objects compiled; F1 vendor kernel uses hybrid DTB | Runtime 6.18 power sequencing, kernel entry, root and HDMI |
| [Incipiens/orange-pi-zero-3w-12gb-android-fix](https://github.com/Incipiens/orange-pi-zero-3w-12gb-android-fix) | Hash-locked Android 13 v1.0 Boot0 hardware-parameter patch, 12 GB LPDDR5 model | **OTHER PROJECT REPORT:** patched 12 GB Android image boots after Linux Boot0 parameter replacement | **OUR HARDWARE:** vendor Linux image boots on our tested 1 GB Zero 3W; original Boot0 bytes retained | Does **not** establish that an Android 12 GB Boot0 repair is needed for our Linux kernel or different RAM variants |

## 1. nickyg666: their reported successful hybrid 6.18, our unverified 6.18

### What is concrete in their repository

Source files inspected on 2026-11-15:
- [README.md](https://github.com/nickyg666/orangepi-zero3w-mainline/blob/master/README.md), blob SHA **e3b0cd91c72acda686d9484f1fb88437dad1d366**.
- [AGENTS.md](https://github.com/nickyg666/orangepi-zero3w-mainline/blob/master/AGENTS.md), blob SHA **0f28f0c71e84430bff78ec1e0d14ad1b0e9e42c7**.
- [mainlining-strategy.md](https://github.com/nickyg666/orangepi-zero3w-mainline/blob/master/mainlining-strategy.md), blob SHA **7fcd57caf1c3e9aa118dcab54b7d35b65ca930f3**.
- [reference/boot.cmd](https://github.com/nickyg666/orangepi-zero3w-mainline/blob/master/reference/boot.cmd), blob SHA **8e1d0005f26ae4a880c2ec2796ce49753e41c565**.

**Read dated notes in sequence.** Their August 11 strategy says the MMC fixes were awaiting an operator power cycle. Their later README **reports a successful Ubuntu 26.04 Linux 6.18.19+ userspace boot on August 13**, and AGENTS.md status **August 16** reports Wi-Fi and GPU progress. The older “pending” document is not evidence that the later tests never occurred. Equally, the later reports are not our physical observations.

### What they report working

| Component | Their reported evidence | What it establishes / does not establish |
| --- | --- | --- |
| Linux 6.18.19 boot | Ubuntu 26.04 login on \`ttyS0\`, systemd 259.5, root \`mmcblk1p1\` | **Their** hybrid reaches userspace; **ours** has no such result |
| Vendor U-Boot \`booti\` | Raw ARM64 Image, legacy \`uInitrd\`, custom placement and relocation | Plausible working strategy. Our VBN/VBI independently establish vendor raw \`booti\` for 6.6.98, **not 6.18** |
| I2C/PMIC | \`AW_TWI\` absent in an earlier build, so AXP8191 regulator provider could not register | **Their** config defect. Our hybrid 0.2.7 already has \`AW_TWI=y\`, so this alone cannot explain our failure |
| MMC | Initially removed \`vmmc-supply\` to avoid deferred probe; then had “no support for card's volts”; restored \`vmmc-supply = <&dc1sw2>\` once PMIC worked | **Final solution includes valid supply**. Do **not** copy the *interim* “remove vmmc” workaround into our DTB |
| Initramfs | \`$B exec /bin/busybox switch_root\` expanded to invalid BusyBox \`exec\` applet; fixed using shell builtin \`exec\` | Their actual userspace fix, separate from our earlier BusyBox \`blkid\`/findfs defect |
| AIC8800 | SDIO enumeration, \`wlan0\`, Wi-Fi association and ping reported on kernel #9 | Their Wi-Fi report is stronger than mere \`.ko\` compilation; ours has not verified AIC8800 under 6.18 |
| PowerVR | \`[drm] Initialized powervr\`, renderD128, Vulkan \`deviceName=PowerVR B-Series BXM-4-64 MC1\`, Mesa 26.0.8 with zink | Reported **actual kernel/user-space GPU** on their setup. Their Mesa build uses custom flags and \`PVR_I_WANT_A_BROKEN_VULKAN_DRIVER=1\`; it is **not** proof of Vulkan conformance or plug-and-play stock Mesa |
| HDMI/display | Reports \`sunxi-drm\` connector \`HDMI-A-1\`, 2560×1440 scanout; **SPI ILI9486** carries fbcon, not HDMI | Having HDMI scanout/DRM registration is **not** the same as a stable HDMI Linux text console. They report \`fbcon=map:1\` wedges boot at ~5.5 s; our stock vendor HDMI Linux console works, F1 hybrid-DTB HDMI does not |

They also report a reproducible boot panic correlated with a separately installed service, later resolved by disabling it. This is not proof that the service alone corrupted a kernel slab; it is a reported correlation/mitigation, not a root-cause isolation relevant to our board.

**Caution about their GPU:** their report distinguishes the **mainline** PowerVR firmware from a similarly named vendor firmware blob, uses a patched kernel driver for absent \`power-domains\`, and explicitly says the Vulkan driver requires a “broken Vulkan driver” opt-in. This is a meaningful result with limitations, not a production-stable GPU validation.

**Caution about their boot script:** a file existing in Git proves the **intended** \`booti\` layout. Verify the actual flashed \`boot.scr\`, U-Boot environment and firmware relocation before assuming every command ran exactly as documented. Their script keeps vendor fallback after \`booti\` returns; a reported 6.18 \`uname\` or login provides stronger identification than splash alone.

### What we ourselves proved

- **OUR HW:** VBN no-fallback vendor raw \`booti\` enters 6.6.98 and panics at VFS; VBI with vendor initrd reaches Debian, so vendor \`booti\` mechanism works.
- **OUR HW:** F1 boots **vendor 6.6.98** using hybrid 0.2.7 DTB: SSH, root MMC and memory size; HDMI driver fails. The splash persists even though Linux runs.
- **OUR SOURCE FINDING:** F1 HDMI fails at root \`of_match_node(hdmi_plat_match, root_node)\`: our hybrid DTB lacks the vendor \`arm,sun60iw2p1\` fallback. This is a concrete source-level explanation with matching logs; correct DTS test still needs hardware.
- **OUR OFFLINE:** hybrid 0.2.7 kernel and DTB compile with \`AW_TWI=y\`, \`AW_MMC=y\`, regulator driver built in and \`sunxi-mmc-v5p3x\` present. HBI-027 has no static script overlap, unlike older M2 experiments.
- **OUR UNKNOWN:** no independently identified 6.18.19 \`uname\`, boot log, root mount or kernel-entry marker on our Orange Pi Zero 3W.

**Comparison:** They report crossing the 6.18 hardware gate. We have crossed the vendor \`booti\`, vendor-kernel + hybrid-DTB, and successful source-build gates. Our next step is **not** to claim their boot happened on our board.

## 2. jonas5: A733 knowledge, not a validated Zero 3W build

Source files inspected: [boards.md](https://github.com/jonas5/Allwinner-A733-kernel/blob/main/boards.md) blob **766bbce37b8693e3a5279230a1a7880ddff3b10d**, [A733_BOOT_FIX.md](https://github.com/jonas5/Allwinner-A733-kernel/blob/main/A733_BOOT_FIX.md) blob **e3f5c289cec9397c3ece4ea80b88e49e417cf318**.

Their **boards.md** marks:
- Orange Pi 4 Pro: **Fully Validated**.
- Radxa Cubie A7A and A7S: **Fully Validated**.
- Orange Pi Zero 3W: **Platform Ready**, not **Fully Validated**.

The A733_BOOT_FIX guide covers 4 Pro/Cubie board bootloader placement, root UUID/timeouts and serial-versus-HDMI console ordering. These are useful **hypotheses/implementation examples**, but do not prove Zero 3W Boot0, LPDDR5, UART pinmux or eMMC wiring is equivalent. **Do not flash a generic 4 Pro Boot0 into the Zero 3W** based on that guide.

Their advice to put \`console=tty1\` last can change where an interactive console attaches. It does **not** repair our F1 HDMI driver failing root platform matching, and it does not establish the 6.18 kernel started.

Our board DTS is officially mislabeled \`xunlong,orangepi-4-pro\`; correct board identity is sensible, but retaining vendor SoC fallback \`arm,sun60iw2p1\` is critical to that BSP HDMI implementation. An A733 family match alone is not a substitute for Zero 3W hardware verification.

## 3. Orange Pi official files: source authority, not automatic reproduction

Pinned:
- [orangepi-build@7f24222](https://github.com/orangepi-xunlong/orangepi-build/tree/7f24222b928eab94780f2af03289ce527e07241e)
- [linux-orangepi@2ac08e8](https://github.com/orangepi-xunlong/linux-orangepi/tree/2ac08e8c7cdc28abbdc5c9a9dd812f887ae9c79f)

**SOURCE FACT:** kernel source Makefile is Linux **6.6.98**; Zero 3W DTS contains the unexpected Orange Pi 4 Pro board compatible along with \`arm,sun60iw2p1\`; source files contain PMIC/MMC/HDMI binding data and vendor startup scripts. Build definitions offer board-specific Boot0 variants and DRAM configuration. No clock-speed filename proves the effective board operating rate.

**OUR HW:** an official 1.0.2 vendor-derived OS image boots with HDMI, Wi-Fi and root. **OUR OFFLINE:** two independent builds using pinned source, original board DTS and corrected one-line board ID both complete Image/DTB/modules. **OPEN:** neither rebuilt Image has been placed in a verified stock-preserving test image or tested physically, and their kernel Image SHA256 values differ. Pinned source does not prove the exact official release binary was rebuilt byte-for-byte.

## 4. Incipiens: a real 12 GB Android Boot0 problem, not ours by default

Their [README](https://github.com/Incipiens/orange-pi-zero-3w-12gb-android-fix/blob/main/README.md), blob **946e35c842ce26c8d737c6c551e1d721b0f68b8d**, reports that official **Android 13 v1.0** fails to boot a **12 GB** Zero 3W and that swapping in verified **Linux Boot0 parameters** repairs it. Their tool checks complete input and Boot0 hashes before patching exact 32-bit words and refuses unknown firmware. This is strong engineering practice, but the board/RAM/OS/Boot0 variant differs from our known-good Linux 6.6.98 donor.

**Our evidence:** physical vendor Linux boot on a **1 GB** Zero 3W; F1 running FDT shows a U-Boot 1 GB RAM fixup from a static 512 MiB source. This does not generalize to 12 GB Android, nor does their Android issue show a Linux 6.18 kernel-entry fault on our board.

**Reuse:** hash gates, restricted changes and preserving firmware. **Do not reuse:** 12 GB Android Boot0 patch on our Linux 1 GB image.

## 5. The important distinction: source, published claims, reality

| Statement | Correct evidence label | What can safely be said |
| --- | --- | --- |
| “Linux 6.18.19 boots on Orange Pi Zero 3W” | OTHER PROJECT REPORT, nickyg666 | Another developer documents successful 6.18.19 **hybrid** boot and login. **Our build remains unverified.** |
| “Linux 6.18 has upstream A733 support” | UNSUPPORTED here | A 6.18 base plus out-of-tree vendor \`bsp/\` is not unmodified mainline A733 support |
| “Wi-Fi and PowerVR work on 6.18” | OTHER PROJECT REPORT, nickyg666 | Reported for their modified kernel, firmware and custom Mesa. Not tested on ours |
| “HDMI works under 6.18” | QUALIFIED OTHER REPORT | They report an HDMI DRM connector/scanout, but warn that fbcon mapping to HDMI wedges boot. We have no 6.18 HDMI proof |
| “The DTB fix is enough to make Linux boot” | UNSUPPORTED | F1 boots **6.6 kernel** with hybrid DTB, not 6.18; source matches don't prove 6.18 execution |
| “Missing AW_TWI explains our boot failure” | DISPROVED AS A CONFIG-MISSING CLAIM | Our compiled hybrid has \`CONFIG_AW_TWI=y\`; runtime I2C behavior under 6.18 still unknown |
| “Remove vmmc-supply to fix MMC” | MISLEADING HISTORICAL WORKAROUND | nickyg666 restored the supply after working PMIC, because removing it caused OCR voltage failure |
| “Frozen HDMI splash means Linux did not start” | CONTRADICTED BY OUR HARDWARE | F1 booted 6.6.98 to SSH while original splash stayed on display |
| “A733 project supports Zero 3W hardware today” | SOURCE MATRIX: PLATFORM READY | jonas5 declares Zero 3W platform ready, **not fully validated** |
| “Our corrected vendor 6.6.98 DTB works” | OFFLINE ONLY | It compiled; we have not tested it on board |
| “12 GB Android Boot0 patch fixes our Linux boot” | NO SUPPORT | Different firmware, memory configuration and symptom |

## 6. What we will actually test next

**Batch A: two independently measured questions, not two edits per image**
1. Vendor 6.6.98 **rebuilt control** with original DTS. Preserve verified Boot0/U-Boot, stock layout/root/initrd and compare complete kernel/module/DTB identities.
2. Vendor 6.6.98 **identity only** after controlling the kernel Image mismatch. Confirm HDMI Linux console, AXP8191, MMC, onboard Wi-Fi, root, USB and detected RAM. No hardware PASS until it actually boots.

**Batch B: compare independent 6.18 entry hypotheses**
1. Bootloader/U-Boot handoff: validate exact relocated initrd, BL31 reservation, DTB and kernel load addresses with physically tested diagnostics.
2. Kernel/early userspace: prove an independent UART or non-destructive early marker before diagnosing MMC/PMIC or HDMI. Do not use the splash as this marker.

**Porting options worth examining, not blindly copying**
- nickyg666's **final**, working \`AW_TWI + AXP8191 + vmmc-supply\` relationship, not their temporary remove-vmmc step.
- Legacy \`uInitrd\` relocation so kernel does not overwrite BL31; compare **actual payload size**, not only staging addresses.
- Shell builtin \`exec switch_root\` distinction, plus our own \`findfs\` vs missing \`blkid\` BusyBox issue.
- Root-compatible HDMI match in our BSP: \`arm,sun60iw2p1\`; note that merely altering \`console=\` will not repair a failed DRM bind.
- Optional GPU work **only after Linux 6.18 userspace** and with correctly matched mainline firmware, kernel driver and Mesa; distinguish render node, Vulkan enumeration, physical output and stability.

## Publication rule

Write **what happened, on whose board, with which image**, then the limit. Avoid generic “proven,” “fixed,” or “mainline supported” without its subject and evidence. Every hardware claim needs date, model/RAM variant, kernel \`uname\`, exact flashed hashes and a positive observation if available. If any are missing, say so. Counterpart statements deserve accurate attribution and respect, not dismissal or promotion into our own results.

**Source provenance:** Current documents inspected directly using GitHub on 2026-11-15. Historical pages can change, so retained blob SHAs above identify the exact reviewed content. Our own records: [hardware matrix](2026-11-15-hardware-matrix.md), [boot chain](2026-11-15-boot-chain.md), [DTS and HDMI](2026-11-15-dts-dtb.md), [M2x](2026-11-15-m2x-results.md), [hybrid 6.18](2026-11-15-hybrid-618.md), [resource hashes](../evidence/2026-11-15-wsl-resource-inventory.md).
