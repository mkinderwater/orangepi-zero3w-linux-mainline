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
