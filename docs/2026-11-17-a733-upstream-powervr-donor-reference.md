# A733 GPU: use upstream PowerVR-compatible Allwinner Linux 6.18 driver reference

**Status:** source-reference decision, not an applied GPU or regulator patch. Date: 2026-11-17.

## Source evidence

Operator inspected two distinct A733 SoC DTSI sources within the built hybrid:

- `/root/opi3w-hybrid-build-0.2.7/linux/bsp/configs/linux-6.18/sun60iw2p1.dtsi` around line 4517, the vendor's **Linux 6.18 upstream-oriented GPU node**.
- `/root/opi3w-hybrid-build-0.2.7/board/sun60iw2p1.dtsi` around line 4600, the **legacy node compiled into hybrid 0.2.7**.
- `/root/opi3w-hybrid-build-0.2.7/linux/drivers/gpu/drm/imagination/pvr_drv.c`, upstream DRM PowerVR match table: `thead,th1520-gpu`, `img,img-rogue`, `img,img-axe`. The generic fallback `img,img-rogue` matches the reference, but not `img,gpu`.
- `/root/opi3w-hybrid-build-0.2.7/linux/bsp/drivers/pm_domain/Kconfig` declares `AW_GPU_PM_DOMAINS` and `AW_PM_DOMAINS`, both **disabled** in tested hybrid .config. Exact PCK600 provider config/driver/IDs not yet examined.

### Preferred donor node from imported 6.18 BSP

```dts
gpu: gpu@1800000 {
    compatible = "img,img-bxm-4-64", "img,img-rogue";
    reg = <0x0 0x01800000 0x0 0x8ffff>;
    interrupts = <GIC_SPI 63 IRQ_TYPE_LEVEL_HIGH>;
    clocks = <&ccu CLK_GPU0>,
             <&ccu CLK_PLL_GPU0>,
             <&ccu CLK_BUS_GPU0>;
    clock-names = "core", "mem", "sys";
    power-domains = <&pck600 PD_GPU_CORE>,
                    <&pck600 PD_GPU_TOP>;
    power-domain-names = "a", "b";
    resets = <&ccu RST_BUS_GPU0>;
    operating-points-v2 = <&gpu_opp_table>;
    #cooling-cells = <2>;
};
```

**This is a verbatim source reference for review, not a ready-to-apply patch.** Provider `pck600` is not known to exist in our hybrid, and its PD identifiers must be matched to a real driver. The reference omits `gpu-supply`; the hybrid presently uses `gpu-supply = <&reg_dcdc4>`, which resolves to AXP8191 DCDC4. The reference's deletion of this regulator linkage must not silently be carried forward.

### Differences to reconcile before any test DTB

| Interface | Hybrid 0.2.7 | Allwinner 6.18 GPU reference |
| --- | --- | --- |
| compatible | `img,gpu` | `img,img-bxm-4-64`, `img,img-rogue` |
| IRQs | GIC 63 + GIC 64, IRQGPU + IRQGPUDVFS | GIC 63 only |
| clock inputs | PLL GPU0, GPU0, bus, 5 peripheral rates | GPU0, PLL GPU0, bus, named `core`/`mem`/`sys` |
| power-domains | `<&pd SUN60IW2_PCK_GPU_TOP>` | `<&pck600 PD_GPU_CORE>, <&pck600 PD_GPU_TOP>` |
| reset | bus GPU0 `reset_bus` | bus GPU0, no named reset |
| supply | `gpu-supply=<&reg_dcdc4>` in final compiled hybrid | not shown in quoted reference node |
| OPP | `gpu_opp_table`, 400/600/800/1008 MHz | `gpu_opp_table` |
| kernel GPU | `CONFIG_DRM_POWERVR=n`; `CONFIG_AW_GPU_PM_DOMAINS=n` | driver matching and PCK600 support to be proven |

The hybrid's 1008 MHz OPP at 960000 µV is present and remains the default requested voltage for that OPP. Do not re-add old `clk_rate=<1008000000>` or force DCDC4 960mV based on a static DTB diff. DVFS/voltage selection is a driver runtime and physical safety concern.

## Gates before creating a separate GPU-enabled test image

1. **PCK600 provider:** locate `pck600:` node, its compatible, `#power-domain-cells`, PD_GPU_CORE / PD_GPU_TOP constants, kernel driver, build Kconfig and provider status. Cross-check against *compiled* DTB. If absent, do not transplant the donor's two-domain reference.
2. **GPU model:** verify A733's exact GPU/BVNC identity and compatibility with upstream PowerVR's supported firmware and hardware revision table, not just the BXM-4-64 family string. The mere `img,img-rogue` fallback permits probing but does not prove support.
3. **Binding validation:** validate against the active Linux `Documentation/devicetree/bindings/gpu/img,powervr-rogue.yaml`; the donor's `operating-points-v2`, vendor OPP compatible string (including space), regulator consumer and additional properties may require adaptation. Confirm clocks are actually provided by the hybrid CCU and appropriate reset/power sequence.
4. **Controlled config:** use an isolated GPU configuration variant with `CONFIG_DRM_POWERVR` and only known dependencies, not an unreviewed wholesale BSP GPU config enable. Confirm effective `.config` after `olddefconfig`.
5. **Hardware order:** first reach stable userspace by fixing the independent MMC legacy CAP2 bit collision and PF voltage-switching panic; preserve current known-good images. Then test GPU probe, clock rates/OPPs, voltage, firmware load, render, suspend/resume and HDMI separately.

### Read-only next investigation on the operator's WSL host

```bash
K=/root/opi3w-hybrid-build-0.2.7
echo '=== PCK600 definitions and domain ID constants ==='
grep -RnsE 'pck600:|PD_GPU_CORE|PD_GPU_TOP|SUN60IW2_PCK_GPU_TOP|#power-domain-cells' \
  "$K/linux/bsp/configs/linux-6.18" "$K/board" "$K/linux/bsp/include" \
  "$K/linux/include/dt-bindings" | head -120

echo '=== Power domain providers and Kconfig ==='
sed -n '1,100p' "$K/linux/bsp/drivers/pm_domain/Kconfig"
grep -RnsE 'pck600|PCK600|PD_GPU_CORE|PD_GPU_TOP' \
  "$K/linux/bsp/drivers/pm_domain" "$K/linux/drivers/pmdomain" 2>/dev/null | head -100

echo '=== Active GPU configuration and compatible ==='
grep -E '(DRM_POWERVR|AW_GPU_PM_DOMAINS|AW_PM_DOMAINS)' "$K/build/.config"
grep -A 32 -B 3 'gpu@1800000' "$K/board/sun60iw2p1.dtsi" | head -40
```

## Decision

**Use the BSP's upstream-targeted Linux 6.18 GPU node as the design reference**, not the legacy hybrid `img,gpu` node. **Do not apply it yet.** Its PCK600 power-provider chain, clock semantics and GPU-supply difference are unverified on our build. Every power and frequency change must be an independent, reversible test.

Related: [GPU clock and DCDC4 evidence](2026-11-17-gpu-clock-dcdc4-dtb-differential.md).

## 2026-11-17: PCK600 provider binding mismatch confirmed

Operator source audit has now located both the donor and legacy provider:

| Field | 6.18 upstream-oriented donor | Legacy hybrid 0.2.7 |
| --- | --- | --- |
| provider node | `pck600: power-controller@7060000` | `pck: pck-600@7060000` with child `pd: power-controller` |
| compatible | `allwinner,sun60i-a733-pck-600` | outer `allwinner,sun60iw2-pck`, `syscon`, `simple-mfd`; child `allwinner,sun60iw2-pck-600` |
| register window | `<0x0 0x07060000 0x0 0xb000>` | same register window on outer node |
| domain cells | 1 | 1 on child |
| clock | `<&r_ccu CLK_R_PPU>` | same, named `pck` in child |
| GPU TOP domain ID | `PD_GPU_TOP` (numeric ID must be confirmed against donor header) | `SUN60IW2_PCK_GPU_TOP=5` |
| GPU CORE domain ID | `PD_GPU_CORE` (numeric ID must be confirmed against donor header) | `SUN60IW2_PCK_GPU_CORE=6`, legacy child definition commented out |
| compatible supported by imported BSP driver | **No direct match shown** | `allwinner,sun60iw2-pck-600` supported |
| config in hybrid build | n/a | `CONFIG_AW_PCK600_DOMAINS=n`, `CONFIG_SUN55I_PCK600=n`, `CONFIG_DRM_POWERVR=n`, `CONFIG_AW_PM_DOMAINS=n`, `CONFIG_AW_GPU_PM_DOMAINS=n` |

Driver `linux/bsp/drivers/pm_domain/pck600_domains.c` contains explicit `sun60iw2_pck600_pm_domains[]` covering GPU TOP and GPU CORE, and matches `allwinner,sun60iw2-pck-600`. The upstream-tree `drivers/pmdomain/sunxi/sun55i-pck600.c` has only A523 coverage in the observed match table; it is **not** currently a proven substitute for sun60iw2.

**Key integration hazard:** The donor's `allwinner,sun60i-a733-pck-600` compatible **does not match** the BSP driver that implements A733-specific domain operations. Do not wholesale swap the donor DTS and enable the driver. The donor and legacy providers also occupy the same physical register window, so both must never bind and drive the PCK600 hardware concurrently.

**Caveat:** Although the legacy DTSI shows the GPU CORE child commented out, the driver has a GPU CORE domain entry; whether the driver requires explicit child definitions is determined by its provider registration/probe code, not the comment alone. Likewise, donor `PD_GPU_CORE` and `PD_GPU_TOP` numeric values must be verified from the donor's included header before asserting they equal legacy 6 and 5.

### Next decision gate: integration is not yet safe

1. Inspect `sunxi_pm_domain_probe()` and its DT child iteration/registration code (roughly `pck600_domains.c:376-485`), especially whether GPU CORE is published only when a `pd_gpu_core` child exists.
2. Inspect donor `PD_GPU_CORE`/`PD_GPU_TOP` definitions, its provider binding and whether any `sun60i-a733-pck-600` driver matches elsewhere in the full kernel.
3. Define one tested provider architecture. If BSP remains transitional, preserve its correct `sun60iw2` compatible while presenting the requisite GPU domain services; don't invent a compatible fallback without driver review.
4. Keep GPU separate from MMC/PF boot fixes; do not adjust clocks or voltage. The 1008 MHz GPU OPP at default 960000 µV remains present in the hybrid's table.
