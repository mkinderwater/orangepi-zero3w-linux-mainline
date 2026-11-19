# A733 HDMI clock equivalence: vendor 6.6.98 to Linux 6.18

Evidence: operator run of `scripts/compare-a733-hdmi-ccu-registers.py` against `/root/opi3w-vendor-6698-work/kernel/bsp/drivers/clk/sunxi-ng/ccu-sun60iw2.c` and `/root/opi3w-m2-work/linux-618-hdmi-stage4/linux/drivers/clk/sunxi-ng/ccu-sun60i-a733.c` on 2026-11-18.

The numbers in vendor DTB `clocks` and `resets` properties are **vendor provider specifiers**, not portable identifiers. Map by register, gate bit, mux and name. Below are directly observed source-level equivalents, not yet runtime HDMI proof.

| Vendor CCU binding | Vendor register | Linux 6.18 A733 binding | Linux 6.18 register | Evidence |
|---|---|---|---|---|
| `CLK_HDMI` (253) | `hdmi_clk`, 0x168c bit 0 | `CLK_BUS_HDMI_TV` (251) | `bus_hdmi_tv_clk`, 0x168c bit 0 | same gate register/bit; parent differs |
| `CLK_HDMI_TV` (252) | `hdmi_tv_clk`, 0x1684, M/N/mux/gate | `CLK_HDMI_TV` (250) | `hdmi_tv_clk`, 0x1684, M/N/mux/gate | same base register and bit fields |
| `CLK_HDMI_SFR` (254) | 0x1690 mux bits 24..26, gate31 | `CLK_HDMI_SFR` (252) | 0x1690 mux bits 24..26, gate31 | same register/fields |
| `CLK_DPSS_TOP0` (256) | 0x16c4 bit 0 | `CLK_BUS_DPSS_TOP0` (254) | 0x16c4 bit 0 | same gate register/bit |
| `CLK_DPSS_TOP1` (257) | 0x16cc bit 0 | `CLK_BUS_DPSS_TOP1` (255) | 0x16cc bit 0 | same gate register/bit |
| `CLK_TCONTV0` (247) | 0x1604 bit 0 | `CLK_BUS_TCON_TV0` (244) | 0x1604 bit 0 | same gate register/bit |
| `CLK_TCONTV1` (248) | 0x160c bit 0 | `CLK_BUS_TCON_TV1` (245) | 0x160c bit 0 | same gate register/bit |

**Do not equate names indiscriminately.** The vendor uses a DCXO parent for several gates while the Linux 6.18 driver uses `ahb_hws`. A shared enable bit validates gate identity, not clock propagation/rate semantics.

## HDMI CEC/REF at 0x1680 is not one-to-one

- Vendor `CLK_HDMI_REF` (251) is `hdmi_ref_clk`, mux 24:26, gate31, with `osc32k` and `hdmi-cec-clk32k` parents.
- Linux 6.18 `CLK_HDMI_CEC` (249) uses mux 24:26, gate31; `CLK_HDMI_CEC_32K` (248) uses bit30 with predivider.
- **No one-to-one mapping confirmed for vendor `CLK_HDMI_REF`.** Must verify intended parent and clock assignment against vendor source and HDMI0 clock names.

## Reset IDs require function-based translation

Earlier binding comparison identified different ID numbering even for the same function:
- Vendor HDMI MAIN=108, SUB=107, HDCP=106; Linux 6.18 MAIN=107, SUB=108, HDCP=109.
- Vendor TCONTV0=103, TCONTV1=104; Linux 6.18 BUS_TCON_TV0=104, BUS_TCON_TV1=105.
- Vendor DPSS_TOP0=109, TOP1=110; Linux 6.18 DPSS_TOP0=110, TOP1=111.

Check reset implementation offsets and bit positions before marking these matches hardware-confirmed.

## Distinct remaining blockers

1. PCK-600 A733 power-domain mapping: vendor `allwinner,sun60iw2-pck-600` domains 1, 9, 10; existing 6.18 A523 PCK-600 driver not yet validated for this board.
2. DE v352 IOMMU reference uses `allwinner,iommu-v20` provider and specifiers [8,1]; the stage4 config currently has `CONFIG_IOMMU_SUPPORT=n`.
3. HDMI RTC CCU specifier 12 and the corrected 26MHz oscillator need a compatible source-level mapping.
4. Complete vendor display graph endpoints need conversion, and the small RAM-B DTB has no HDMI nodes.

**Never alter the proven RAM-B DTB or boot binaries in place.** Use a separate DTB candidate after provider mapping.
