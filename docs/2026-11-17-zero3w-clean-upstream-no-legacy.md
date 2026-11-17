# Zero 3W Linux 6.18 reset: minimal, no inherited BSP

**Decision:** Stop treating the HBI 0.2.7 hybrid and its copied Allwinner driver tree as the product kernel. Build a **fresh upstream 6.18.19 source + clean Kconfig**, then add only required A733/Zero3W support. Old Allwinner BSP code, old `.config`, vendor compatibility shims, unused device definitions, and earlier speculative patches are **not inherited**.

## The distinction that matters

There are three different kinds of bloat:

- **Kernel source footprint:** the upstream Linux tree includes drivers for many architectures/devices. Most are never compiled. Do not waste time deleting thousands of unrelated upstream source files or create an unmergeable private fork. Use the unmodified pinned upstream tree, with only tiny tracked patches.
- **Compiled kernel/modules:** excessive enabled Kconfig options enlarge the Image, root modules, initrd, attack surface and maintenance scope. This is where a truly lean build matters.
- **DTB hardware baggage:** copied vendor board DTSI enables unrelated devices. Upstream source alone does not provide a complete, validated Zero 3W DTS. We must produce one canonical board DTS with only proven hardware enabled by default.

## Immediate action implemented

`scripts/prepare-zero3w-clean-618.sh` uses the **pinned upstream source** (`/root/opi3w-hybrid-sources-0.1.0/linux`) and `make ARCH=arm64 tinyconfig`. It creates a **new** output directory, refuses existing outputs and never loads the old 0.2.7 `.config`. It requests the core ARM64 + OF + early console + MMC + ext4 + basic USB/NET stack, and disables broad legacy subsystems. It runs `olddefconfig`, records **requested vs effective** symbols and flags hard-gate violations. It does not touch the existing 0.2.7 PID1 source, firmware, image or boot media.

**Important:** A clean config is a *starting inventory*, **not a bootable A733 kernel**. Upstream Linux 6.18 lacks portions of the proven A733 CCU/pinctrl/PMIC/SDIO/SDMMC stack. `MMC_SUNXI=y` alone does not guarantee card access and `SERIAL_8250=y` alone does not guarantee the console. We must add only individually justified upstream-oriented changes, and verify the effective Kconfig dependencies before attempting a hardware image.

## Three product stages, not one bloated config

| Stage | Required | Intentionally excluded |
| --- | --- | --- |
| 0: PID1 boot-minimal | ARM64/OF, CCU, pinctrl, serial console, SD/MMC0, regulators PMIC, initrd/ext4, core clock/reset/interrupt/PSCI | GPU, HDMI/DRM, audio/video capture, NPU, PCIe, touchscreen, cameras, wireless extras, vendor recovery controllers |
| 1: useful server | Stage 0 plus verified USB host/USB Ethernet, Wi-Fi/SDIO, networking, thermal watchdog if confirmed, Debian modules/security | Unused SoC peripherals; unused legacy BSP drivers |
| 2: optional GPU | Stage 1 plus upstream DRM PowerVR and standalone upstream A733 PCK600, validated BXM-4-64 firmware and standard OPP/regulator bindings | Legacy `img,gpu` driver, nested legacy PCK600 provider, direct GPU clock/voltage hacks |

Stage 2 must **not** be silently folded into the boot-minimal baseline. The separate `configs/a733-upstream-gpu-experimental.fragment` and tracked PCK600 backport address that track. Only selected proven functionality moves into a product config.

## Clean slate acceptance, fail closed

1. Generate from the pinned upstream Linux directory, never from `/root/opi3w-hybrid-build-0.2.7/linux` and never from its `.config`.
2. Never run a booting trial from `tinyconfig` alone. Verify the compiled drivers for MMC0/1, AXP8191/AXP515 rails, clock/reset and pinctrl, UART0 pins, USB, board DTB sources and the power-domain provider. A missing upstream binding or probe is a hard blocker, not an invitation to import all of `bsp/`.
3. Prefer **upstream MMC_SUNXI** adapted with justified A733 additions. The legacy `AW_MMC` collision with Linux 6.18 UHS-II is reason enough to remove it from the production build. Nonetheless, upstream MMC0/1 remains a hardware test gate, not a known-good replacement.
4. Use a **clean DTS**, not a renamed old vendor board include. Support board-fitted devices by default. External accessories use explicit overlays if needed. Do not disable power or alter voltages without verified hardware evidence.
5. Preserve only the known-good vendor Boot0/BL31/SCP/U-Boot **as a bounded boot dependency** until replaced by proven upstream firmware. That is not permission to inherit historical kernel code. Freeze those bootloader bytes and keep them outside Git source and routine kernel updates.
6. Build in a new output directory. Audit the produced Image size, module list, `.config`, initrd and DTB; save hashes. Count y/m Kconfig options and compare with 0.2.7, rather than comparing source folder sizes.
7. Keep the old image for recovery and do not overwrite it. Current kernel's verified UART PID1 is a historical acceptance baseline, but its MMC CAP2 collision and PF voltage panic make it **not** a stable operating system.
8. No historical ABI compatibility unless an actual still-shipped hardware or userspace interface requires it. Delete unneeded shims when their last consumer is removed. No in-place legacy migration.

## Operator command

```bash
cd /root/orangepi-zero3w-linux-mainline
git pull --ff-only

bash scripts/prepare-zero3w-clean-618.sh \
 /root/opi3w-hybrid-sources-0.1.0/linux \
 /root/opi3w-clean-618-config-v1

cat /root/opi3w-clean-618-config-v1/config-resolution.tsv
```

The output includes `requested.config` and final `.config`. Some symbols requested by the script may be disabled/absent after Kconfig dependency resolution. Do **not** blindly enable missing options: identify the upstream dependency or record a missing A733 implementation.

**Next real engineering job:** review this fresh config's unresolved symbols and the A733 boot-critical drivers against the stable vendor 6.6.98 kernel and the HBI source, then rebuild *only* those features as small upstream-oriented patches. The product tree will have no `bsp/` driver import.
