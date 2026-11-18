# Zero 3W DTB integration: existing evidence, no rediscovery

**Date:** 2026-11-18. **Purpose:** Promote existing A733 vendor-to-6.18 research into a tracked integration gate; do not restart the DTB from scratch.

## Confirmed and already investigated

| Workstream | Prior result | Remaining issue |
|---|---|---|
| Vendor 6.6.98 full DTB | Vendor DE352, TCON3/4, HDMI0 and IOMMU v20 identified; stock kernel HDMI verified on board | Not directly portable across kernel clock/reset/binding versions |
| 26 MHz oscillator model | RAM-B Linux 6.18 hardware boots with corrected board oscillator input | Preserve actual 26 MHz model |
| Native UART | Linux 6.18 hardware TX/RX and interactive shell | Silent output after BL31 when HDMI connected *at power-on* |
| PCK600 | Kernel module built-in; DE_SYS, VO, VO1 provider probes return zero; sysfs driver bound on board | Domain power-up by actual display consumer not exercised |
| HDMI/TCON clock correspondence | Seven core gate/register mappings documented in `HDMI-CLOCK-REGISTER-MAP.md`; IDs translated by function, not number | Clock parents/muxes, resets and rate behavior require consumer-level validation |
| HDMI source port | Vendor BSP DRM DE/TCON/HDMI code compiled in 6.18 stage4 | Linux DTB lacks DE/TCON/HDMI graph; no scanout proof |
| IOMMU | Vendor controller `allwinner,iommu-v20` with DE consumers identified | Current stage4 config `CONFIG_IOMMU_SUPPORT=n`; driver not integrated |
| AXP8191 | Existing M2R/M2T kernel patches for selected regulators | No combined hardware proof with current PCK600+HDMI kernel |
| MMC0 | Pinmux, card-detect, OCR/voltage and provider requirements researched | Combined regulator-backed root boot needs validation |
| U-Boot handoff | `drm_debug=1` source guard found; ext4 environment CRC-valid but not imported | No early-boot bypass proven; no causality established |

## Source-of-truth files

- `experiments/full-618/HDMI-CLOCK-REGISTER-MAP.md`: register/bit matches and unresolved parent semantics.
- `experiments/full-618/HDMI-HANDOFF-CROSS-STAGE-AUDIT-2026-11-18.md`: FDT and cold-boot hypotheses.
- `experiments/full-618/UART-HDMI-GPU-GOAL.md`: hardware test progression.
- `docs/vendor-hdmi-baseline.md`: vendor display pipeline and AXP8191 HDMI rails.
- `scripts/resolve-vendor-hdmi-dependencies.py`: phandle/cell-based link resolution.
- `scripts/compare-a733-display-bindings.py` and `compare-a733-hdmi-ccu-registers.py`: vendor/mainline translations.
- `scripts/stage-a733-pck600-probe-dtb.py` and `validate-a733-pck600-probe-dtb.py`: existing hardware-validated power-domain probe DTB lineage.
- `scripts/integrate-axp8191-m2r.sh`: isolated PMIC driver staging.
- `scripts/consolidate-a733-618-dtb-evidence.py`: new inventory of host artifact presence and missing evidence.

## Immediate integration strategy

1. Treat `opi3w-VENDOR-6698-full-stock-baseline.img` (byte-identical to hardware-tested vendor VBI source) as the **stock kernel / full vendor DTB** control. It is **not** a Linux 6.18 image.
2. Treat the hardware-booted `Image-618-vendor-hdmi-pck600-syscon` and `ram-b-26mhz-pck600-probe.dtb` as the known diagnostic Linux 6.18 control. Do not overwrite them.
3. Inventory existing reports and vendor reference DTS using `python3 scripts/consolidate-a733-618-dtb-evidence.py`; make missing reports explicit rather than repeating already completed source exploration.
4. Construct a **separate** 6.18 full-graph candidate by reusing existing clock register equivalence and phandle mapping, with binding translation and exact compatible-driver validation. Resolve AXP8191/PMIC and IOMMU dependencies in the same kernel tree before enabling devices.
5. Only then create a new, separately named flash image; preserve both baselines, firmware prefix and source hashes. Boot with HDMI connected before power-on to check for the original regression. Do not confuse framebuffer success with PowerVR GPU acceleration.

## Promotion gates

- No unresolved phandle, `#*-cells` provider, missing clock/reset regulator or enabled unsupported compatible.
- Exact 6.18 kernel `.config`, image SHA256, DTB SHA256 and module ABI documented.
- Display-side DMA/IOMMU references supported; no speculative removal of supply properties.
- Source-level `CONFIG_AW_DRM=y` is not equivalent to functional HDMI without actual DTB nodes.
- Hardware UART stays usable with HDMI connected at power-on; kernel execution independently observed.
- Full vendor 6.6.98 HDMI hardware revalidation is an independent control, not sufficient evidence of 6.18 parity.

**Status:** Consolidation scripted, host audit pending. **No integrated 6.18 full-graph image is claimed or produced by this step.**
