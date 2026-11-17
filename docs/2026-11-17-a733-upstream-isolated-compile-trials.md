# Clean A733 upstream 6.18.19: first independent compile trials

**Status:** CCU 8/8, pinctrl 7/7 and PF6 1/1 passed source-only `git apply --check` and scratch application on pinned Linux 6.18.19. The voltage-mode patch is **excluded**. Neither driver tree has yet compiled or booted in this project.

The following script **creates two new copies** of the pristine upstream Linux source, stages patches only in the new copies, imports a fresh clean 6.18 config and performs **independent driver-subtree builds**. A compile pass is not a hardware pass. No legacy BSP inheritance.

```bash
cd /root/orangepi-zero3w-linux-mainline
git pull --ff-only

# Ensure the normal cross compiler is installed:
command -v aarch64-linux-gnu-gcc

python3 scripts/build-a733-clean-driver-tracks.py \
 --source /root/opi3w-hybrid-sources-0.1.0/linux \
 --config /root/opi3w-clean-618-config-v3/.config \
 --review /root/opi3w-m2-work/a733-upstream-check-v7 \
 --output /root/opi3w-m2-work/a733-clean-driver-build-v1 \
 --jobs 4
```

Separate trees and build folders:

```text
a733-clean-driver-build-v1/
  ccu-linux/        pristine source copy + CCU 8 patches
  ccu-obj/          clean config with SUN60I_A733_CCU and R_CCU enabled
  pinctrl-linux/    pristine source copy + pinctrl 7 patches and PF6 IRQ fix
  pinctrl-obj/      clean config with PINCTRL_SUN60I_A733 enabled
  report.json       compiler progress/effective Kconfig per independent track
```

**Hard stops:** The script refuses existing output directories, a review whose source differs, missing prerequisite review passes, or unresolved A733 Kconfig symbols. Patch applicability is checked and each compilation is independent. If cross build fails, retain the exact compiler error; do not automatically import the BSP or disable the offending object.

**Critical caution:** In the pinctrl track, the two 6.18-only adaptations (rename + preserved variant/full flags) are staged along with patches 2..7 and PF6. No `pinctrl-voltage-v3` is included. The presence of a safe source-only layout backport does not certify actual PF voltage switching.

**Next after compilation:** source and DTB integration for UART/CCU/pinctrl, then upstream MMC0 and AXP regulators, with physical UART logs against the known HBI PID1 control. Do not flash a kernel at this point.

## 2026-11-17: independent driver subtree compilation PASS

Operator executed the revised `scripts/build-a733-clean-driver-tracks.py` with output at `/root/opi3w-m2-work/a733-clean-driver-build-v2`. The script reported:

```text
CC drivers/pinctrl/sunxi/pinctrl-sunxi.o
CC drivers/pinctrl/sunxi/pinctrl-sun60i-a733.o
AR drivers/pinctrl/sunxi/built-in.a
PASS: both isolated driver subtree builds completed; no DTB/hardware testing
```

This is **source compile evidence** for two isolated source trees: one with the eight upstream CCU patches plus the upstream `SUNXI_CCU_M_DATA_WITH_MUX_GATE_FEAT` compatibility macro, one with the seven pinctrl patches and the PF6 correction plus strictly scoped Linux 6.18 compatibility adaptations. The untested GPIO voltage-auto patch was omitted.

It is **not** an all-kernel link, combined integration, DTB schema validation, PMIC/MMC support, PF 1.8V switching proof or hardware boot. Neither the clean upstream baseline nor the existing 0.2.7 PID1 image was flashed.

**Next gate:** merge only those validated upstream source changes into a *third* disposable source copy, enable both A733 Kconfig symbols, and build the entire ARM64 `Image`. Record exact effective config, linker errors and compiler toolchain; do not claim a Zero 3W bootable kernel until upstream-compatible A733 DTS, MMC0 and PMIC support are independently integrated.

## 2026-11-17: combined clean upstream ARM64 Image link PASS

Operator ran `scripts/build-a733-combined-clean-image.py` with the separate successful A733 CCU and pinctrl source trees, the fresh upstream ARM64 configuration and a brand-new combined build output directory.

Observed full-kernel build tail:

```text
LD      vmlinux.unstripped
NM      System.map
SORTTAB vmlinux.unstripped
OBJCOPY vmlinux
GEN     modules.builtin.modinfo
GEN     modules.builtin
OBJCOPY arch/arm64/boot/Image
COMBINED_IMAGE_PASS: /root/opi3w-m2-work/a733-combined-clean-build-v1/obj/arch/arm64/boot/Image
IMAGE_SHA256: 24f58c911c8f382ee48c63952280d504ebe8f1412786fa37fb8af5a38dd8247e
NOT_BOOTABLE: A733 MMC/PMIC/DTS still require integration and hardware validation
```

This proves **one full link** of the upstream A733 CCU/R-CCU and main/R pinctrl driver implementation with the PF6 source fix. The first compiler failure from the missing `SUNXI_CCU_M_DATA_WITH_MUX_GATE_FEAT` macro was resolved by a small upstream macro backport (`0004-clk-sunxi-mux-gate-feat-macro.patch`). The voltage-auto patch remains excluded and the imported BSP is absent.

**Do not claim** kernel hardware boot, regulator voltage stability, SD-card root mounting, Wi-Fi, GPU or a production-ready board definition on this evidence. The output's actual Image byte length and linked-symbol inspection have not yet been supplied.

### Next verification commands (read only)

```bash
OUT=/root/opi3w-m2-work/a733-combined-clean-build-v1
IMAGE="$OUT/obj/arch/arm64/boot/Image"
stat -c 'CLEAN_IMAGE_BYTES=%s' "$IMAGE"
sha256sum "$IMAGE"
grep -E 'CONFIG_(SUN60I_A733_CCU|SUN60I_A733_R_CCU|PINCTRL_SUN60I_A733|MMC_SUNXI)=' "$OUT/obj/.config"
grep -E 'sun60i_a733|sun60i_a733_r' "$OUT/obj/System.map" | head -40
stat -c 'HYBRID_IMAGE_BYTES=%s' /root/opi3w-hybrid-build-0.2.7/stage/boot/Image
```

Next integration focus: upstream SD/MMC0 controller, exact clock/reset/DTB pairing, and verified AXP8191/AXP515 PMIC supply paths. Preserve this clean full-link baseline and the original 0.2.7 UART/PID1 control independently.
