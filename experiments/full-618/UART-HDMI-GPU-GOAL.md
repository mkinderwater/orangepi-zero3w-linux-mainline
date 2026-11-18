# Goal: Vendor-equivalent Linux 6.18, UART plus HDMI GPU

**Priority:** Match the actual Orange Pi Zero 3W vendor Linux 6.6.98 hardware feature set on Linux 6.18. No speculative features, no omissions of relevant vendor hardware, no arbitrary new add-ons.

## Target acceptance
- Keep vendor Boot0, BL31, SCP and U-Boot unchanged.
- Preserve measured 26 MHz DCXO correction feeding the effective 24 MHz PLL reference.
- Native UART0 serial console, readable 115200-baud output and interactive RX.
- Reproduce the **vendor HDMI/display pipeline** on a connected monitor, including mode detection and visible console/framebuffer output.
- Reproduce the **vendor PowerVR GPU support**, establish 6.18 kernel/firmware/userspace compatibility, and verify hardware acceleration on HDMI. Do not confuse GPU rendering with HDMI scanout.
- Preserve supported vendor hardware facilities (SD, Wi-Fi, audio, PMIC, clocks, DMA etc.) as part of parity, but do not make unrelated peripheral bring-up prerequisites for the first UART+HDMI demo when the boot arrangement does not require them.
- Make no board hardware additions or unrelated drivers merely because they are available in Linux 6.18.

## Kernel configuration rule
The vendor 6.6.98 `.config` is the baseline. Compare it against the actual generated 6.18 `.config`. Resolve version-specific Kconfig names, driver dependencies and BSP-to-mainline substitutions by *function*. Document every deviation. A single identical Kconfig symbol does not prove feature parity and absent names may represent renamed options.

Use:

```bash
python3 scripts/audit-vendor-kernel-parity.py \
  /root/opi3w-vendor-6698-work/obj-control/.config \
  /root/opi3w-m2-work/linux-618-full-integration/artifacts/kernel.config
```

Verify both paths exist first. Audit writes `vendor-parity/summary.txt` and full `diff.tsv`; it does not change a kernel configuration or boot files.

## Reference baseline
- Existing live working RAM-B `Image`: SHA-256 `67a0a073950bb6c92e2a06e61235e90509ad5d3964703dec70cb4f53e4a339c8`.
- Corrected 26 MHz RAM-B DTB: SHA-256 `1ff786ed912df7d4b4d19e366b3c968a5e0552c39f58d61a8414514eba141d9d`.
- Existing 6.18 full build: Image SHA-256 `97c98f2cc6135e938c664936674936ece49a3257935395441f4ceacdb8fb406d`; config SHA-256 `aaad20e5df200caae35dc8e58faaf6e843211d3a4b316ccf24bf55ebaf945351`.
- Other Zero 3W projects are useful implementation references, not substitutes for vendor parity or our own hardware testing.

## Do not do
- Do not add generic unrelated Kconfig drivers, extra interfaces or optional dependencies just to make a bigger kernel.
- Do not consider a PowerVR DRM device equivalent to working HDMI output. Both need tested.
- Do not replace vendor firmware as part of this kernel-only parity effort.
- Do not promote builds solely on compilation.

## Initial vendor config comparison

The operator ran the two-version comparison and reported:

- 1,523 vendor-enabled options missing or renamed in Linux 6.18
- 192 Linux 6.18 options enabled but not in the vendor config
- 2,848 other Kconfig value/version differences
- 4,563 total differences

These are symbol differences and cannot be equated to missing driver functions. The next step is the targeted `scripts/report-vendor-hardware-parity.py` report, which groups mismatches by hardware domain and prints UART/display/DRM vendor-enabled gap candidates first. **Do not enable all missing vendor options automatically.** The comparison keeps both `y` and `m` meaningful and records all selected hardware rows for manual mapping; it does not modify configurations or hardware.

```bash
python3 scripts/report-vendor-hardware-parity.py \
 /root/opi3w-vendor-6698-work/obj-control/.config \
 /root/opi3w-m2-work/linux-618-full-integration/artifacts/kernel.config
```

Report: `/root/opi3w-m2-work/linux-618-full-integration/vendor-parity/hardware-focus/summary.txt` and `hardware-differences.tsv`.

## Targeted parity result, first pass

Operator report counted 1,698 hardware-related Kconfig symbol differences: 561 vendor-enabled missing/renamed, 56 newly enabled, 1,081 other. This is **not** proof of 561 missing drivers. Critical confirmed symbols: vendor `CONFIG_DRM=y`, current 6.18 `CONFIG_DRM=n`; vendor A733 BSP modules `CONFIG_AW_DRM=y`, `AW_DRM_DE=y`, `AW_DRM_HDMI20=y`, `AW_DRM_HDMI_TX=y`, `AW_DRM_TCON=y`, `AW_DRM_TCON_TV=y`, `AW_DRM_PHY=y` are not present in the selected 6.18 config. The existing booted 6.18 native UART works despite `AW_UART_NG` being absent, so do not replace it unless hardware behavior requires it.

**Next task:** Inventory *actual* 6.6 vendor source paths and compatible strings for display engine, TCON, HDMI TX, PHY and GPU, then implement this same board's display function on 6.18 (port minimal vendor driver pieces if no equivalent), rather than toggling arbitrary DRM config flags. The candidate 6.18 build cannot be called HDMI-capable until the display engine, HDMI mode setting and PowerVR hardware path have each been proven. Run `bash scripts/inventory-vendor-display-stack.sh` to generate `vendor-display-inventory/summary.txt`. The script is read-only. Maintain the corrected 26 MHz DTB model and known-working ttyS0.

## Vendor display inventory, operator result

Vendor kernel config proves `CONFIG_AW_DRM=y`, `CONFIG_AW_DRM_DE=y`, `CONFIG_AW_DRM_TCON=y`, `CONFIG_AW_DRM_TCON_TV=y`, `CONFIG_AW_DRM_TCON_TOP=y`, `CONFIG_AW_DRM_HDMI_TX=y`, `CONFIG_AW_DRM_HDMI20=y`, `CONFIG_AW_DRM_PHY=y`, plus `CONFIG_AW_FB_CONSOLE=y`, `CONFIG_FRAMEBUFFER_CONSOLE=y` and `CONFIG_DRM=y`. Vendor GPU type is `bxm`. In our 6.18 config, `CONFIG_DRM`, `CONFIG_FB`, `CONFIG_SYNC_FILE` are disabled; `CONFIG_VT=y`, `CONFIG_VT_CONSOLE=y`. Vendor display source confirmed at `/root/opi3w-vendor-6698-work/kernel/bsp/drivers/drm` including `sunxi_device/hardware/lowlevel_de`, `lowlevel_tcon`, `lowlevel_hdmi20` and `phy`. Existing 6.18 contains mainline DRM sun4i and imagination directories, but their presence is **not** proof of A733-compatible display pipeline.

**Immediate implementation work:** map vendor-specific Kconfig dependencies, Makefile-selected sources and A733 board DT nodes to produce a *minimal actual port* of the vendor DE/TCON/HDMI20/PHY. Keep working UART driver and 26 MHz root clock. Use `scripts/map-vendor-hdmi-port.sh` for a read-only extraction into `linux-618-full-integration/hdmi-port-map/`. Only add vendor functions required on the Zero 3W, not every enabled peripheral interface in generic vendor config. Confirm HDMI scanout separately from PowerVR compute/render acceleration.

## Stage 4: First complete vendor HDMI DRM kernel build

Operator reports successful `JOBS=4 bash scripts/port-sunxi-fb-dsi-notifier-618.sh` incremental `Image modules` build. Output kernel `/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/Image-618-vendor-hdmi` SHA-256 `9a4605cea00f1af2596095285162d7c270e35ae33563cc0a8b1b4ee7e1470a98`; build `.config` SHA-256 `a70c49e15c4e7ef684f39965d1e192743e4b2387e283127beefa5788655de290`. DSI old fbdev notifier calls conditionally excluded only with DSI disabled; DSI parity remains unimplemented. Compiling the vendor display engine, TCON, HDMI transmitter and DRM is **not yet** a hardware HDMI result, and the 26 MHz minimal RAM-B DTB lacks known complete display nodes. Next: extract and compare exact original vendor Zero 3W live display graph and dependencies, stage a separately named test DTB, verify boot-time UART and HDMI independently, then GPU rendering. Never overwrite RAM-B LKG.

## Vendor compiled Zero 3W DTB comparison

Operator compared `obj-control` and `obj-identity` compiled vendor 6.6.98 DTBs; DTS diff was 11 lines. Both include enabled `allwinner,sunxi-drm`, DE v352 at `0x05000000`, TCON_TOP0/1 at `0x05500000`/`0x05510000`, TCON3/4 at `0x05730000`/`0x05731000`, and HDMI0 at `0x05520000`. Vendor also describes `img,gpu` at `0x01800000` but the current Linux 6.18 test config has `CONFIG_DRM_POWERVR` disabled.

Vendor HDMI references clock provider phandles `0x12` and `0x2e` and power-domain provider `0x13`; those are **not transferable numeric IDs** into the tiny RAM-B DTB. DE and TCON have related reset and power dependencies. The current RAM-B DTB does not contain the vendor display graph.

Run `python3 scripts/resolve-vendor-hdmi-dependencies.py /root/opi3w-m2-work/linux-618-hdmi-stage4/vendor-dtb-topology/vendor-control.dts /root/opi3w-m2-work/linux-618-hdmi-stage4/vendor-dtb-topology/ram-b.dts --output /root/opi3w-m2-work/linux-618-hdmi-stage4/vendor-dtb-topology/phandle-dependencies.txt` to resolve providers. This is read-only; a boot DTB has **not** been constructed or verified. Retain vendor firmware, proven 26 MHz oscillator and UART.
