# Vendor HDMI driver: known-good baseline for A733 display work

**Why this matters:** The working Orange Pi Zero 3W 0.7.6 image running vendor Linux `6.6.98-sun60iw2` was physically observed displaying a Debian login console over HDMI on 2026-11-14. This is our **video output reference**, independent of how a new driver is implemented. A builder may choose to port the vendor DRM pipeline, adapt existing mainline DRM pieces, or write a new A733 KMS driver. Don't confuse a working vendor display with an upstream Linux 6.18 display.

## Known vendor display pipeline

| Component | Grounded location or dependency |
| --- | --- |
| Display engine | A733 DE352 at `0x05000000`, with vendor RCQ register-update design and UI channels |
| Timing controller | TCON3 at `0x05730000`; routing and clock/reset setup required |
| HDMI controller | Hardware at `0x05520000`; Synopsys DesignWare HDMI core plus SoC glue |
| PHY | Synopsys/Allwinner PHY and PHY-top configuration, HDMI pixel clock derived through PHY PLL |
| Power | AXP8191 `DCDC2` and `CLDO2`; vendor Zero 3W `&hdmi0` declares `dcdc2-supply` and `cldo2-supply` |
| Verified output | HDMI login console under *vendor* Linux 6.6.98; not tested on mainline 6.18 |

Relevant paths **in the vendor kernel source checkout** (reference only; source not redistributed here):

```
bsp/drivers/drm/sunxi_drm_drv.c
bsp/drivers/drm/sunxi_drm_crtc.c
bsp/drivers/drm/sunxi_drm_hdmi.c
bsp/drivers/drm/sunxi_drm_gem.c
bsp/drivers/drm/sunxi_device/sunxi_hdmi.c
bsp/drivers/drm/sunxi_device/sunxi_tcon.c
bsp/drivers/drm/sunxi_device/sunxi_tcon_top.c
bsp/drivers/drm/sunxi_device/hardware/lowlevel_hdmi20/
bsp/drivers/drm/sunxi_device/hardware/lowlevel_tcon/
arch/arm64/boot/dts/allwinner/sun60i-a733-orangepi-zero3w.dts
```

These are the **vendor** implementations, not a declaration that `drivers/gpu/drm/sun4i/` in mainline directly supports A733 DE352/TCON3. The vendor's exact channel routing must be read from the running flattened DT and driver, not inferred from conflicting source DTS overrides.

## Different but complementary goals

**Display:** scanout, CRTC/planes, HDMI mode setting, HPD/EDID, PHY, TCON timing and buffer allocation. **GPU:** PowerVR BXM 3D rendering via kernel DRM plus userspace Mesa. A working framebuffer/HDMI login can exist without PowerVR acceleration, and a compiling PowerVR module does not create a functioning display pipeline.

## Experimental 6.18 status

Our native audit modules compiled and called probe paths, and some RCQ descriptor, shadow-buffer, DMA, mode-timing and atomic-check helper code compiled. **There is no demonstrated registered CRTC/plane/connector with successful modesetting, framebuffer scanout, EDID or HPD on 6.18.19.** Generic `mk,opi3w-a733-*-audit` probe drivers are temporary evidence scaffolds, not display drivers. Avoid describing them as operational HDMI.

### Engineering notes worth preserving

- DE352's RCQ block handling must use the *actual* descriptor count for the source pointer: using the aligned count can walk past the descriptor array. A local prototype fixed `vir_addr + block_num_aligned` to `vir_addr + block_num`; bench testing was not hardware proof.
- TCON3 clock/reset sequencing and HDMI PHY power/PLL depend on the SoC-specific integration.
- Exact vendor HDMI rails: DCDC2 voltage selector register `0x13`, enable `0x10 BIT(1)`; CLDO2 selector `0x30`, enable `0x21 BIT(4)`. Their presence in source does not authorize changing rails on the board.

## Useful baseline capture from the running vendor kernel

Run on the physical 6.6.98 image and publish only sanitized output (remove credentials, private network details and serial IDs):

```bash
uname -r
cat /proc/cmdline
ls -la /sys/class/drm
for x in /sys/class/drm/card*-HDMI-A-*/status; do [ -f "$x" ] && { echo "$x"; cat "$x"; }; done
lsmod | grep -Ei 'drm|sunxi|hdmi|pvr' || true
dmesg | grep -Ei 'drm|hdmi|edid|tcon|display|de352' | tail -120
find /proc/device-tree -name '*hdmi*' -o -name '*tcon*'
```

What this adds: vendor device/driver binding evidence, active connector status, boot log, and an HDMI control for other video projects. It does not require uploading or redistributing the vendor binaries.
