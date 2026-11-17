# A733 UART-only preflight: safe firmware and RAM handoff gate

## Current verified artifacts

| Artifact | SHA256 |
| --- | --- |
| Upstream Linux 6.18 A733 CCU/pinctrl/AXP318W + DesignWare UART `Image`, 4,562,952 B | `a2e34a97113b9fff7c64112d46e6f9e131bf2ebe13d9cb1734b4fea49803e311` |
| Upstream A733 v3 + Zero 3W UART-only DTB | `b81ae21342c8748bc65a40d38640a2e5c708cd839457e91265cff4d013a851a2` |

The compiled UART-only DTB passed CPP, dtc and eight static policy checks. **It has no `/memory` node.** The known M2dc stage-two script uses `booti 0x41000000 0x45000000:${filesize} 0x44000000`, loading its original vendor-raw initrd. `fdt addr` and `fdt resize` do not establish a usable memory map. Full RAM fixups at kernel handoff remain unverified. The existing M2dc path **does not automatically fall back** if stage two returns.

## Strict order

1. Preserve the proven M2dc card/media unchanged. Use a separate removable test medium if preparing a copy. Do not overwrite `boot.scr`, `stage2.scr`, an `Image`, or the existing `mainline` directory on the control card.
2. Stage the hash-pinned test artifacts locally using `scripts/stage-a733-uart-preflight.py`. It creates **only** a standalone `uart-preflight` folder, containing `Image`, `sun60i-a733-orangepi-zero3w-uart-only.dtb`, `preflight.cmd`, optional `preflight.scr`, `report.json` and instructions.
3. Copy that folder to `/boot/uart-preflight/` **on a separate test medium**. At an interactive U-Boot prompt, confirm the correct `devtype`, `devnum`, and `prefix`. No autoboot variable changes.
4. Run `load ${devtype} ${devnum} 0x46000000 ${prefix}uart-preflight/preflight.scr`, then `source 0x46000000`. This calls `bdinfo`, prints env and FDT nodes and returns to U-Boot. It **never calls `booti` or `bootm`**, changes PMIC voltages, or writes MMC media.
5. Capture U-Boot's reported DRAM banks, effective FDT `/memory` or `memory@...` status, UART alias, `/chosen`, environment and diagnostics. Missing memory after loading the UART-only DTB is an expected blocker, not an unexpected failure.
6. Only after inspecting this evidence should a *separate* handoff recipe be designed: provide a verified RAM map (or proven U-Boot memory fixup), use upstream 8250 earlycon, preserve initrd bounds and the frozen firmware chain, and execute a reversible `booti` test. Current kernel runtime UART patches may still be required.

### Operator command

```bash
cd /root/orangepi-zero3w-linux-mainline
git pull --ff-only

python3 scripts/stage-a733-uart-preflight.py \
 --image /root/opi3w-m2-work/a733-clean-uart-gate-v1/obj/arch/arm64/boot/Image \
 --dtb /root/opi3w-m2-work/zero3w-uart-only-dtb-check-v1/sun60i-a733-orangepi-zero3w-uart-only.dtb \
 --output /root/opi3w-m2-work/uart-preflight
```

The output must say `PREFLIGHT_STAGED_NO_BOOT`. If `MKIMAGE_SCRIPT: False`, install `u-boot-tools` and generate in a **new** output folder rather than overwriting the first result.

**Safety:** neither the source-only build script nor this preflight proves AXP8191 equals AXP318W, PMIC rail-parent correctness, PF 1.8 V switching, microSD operation, or Linux boot. Do not enable MMC0, R-domain I²C, regulator consumers or the unreviewed voltage-mode patch for this gate.
