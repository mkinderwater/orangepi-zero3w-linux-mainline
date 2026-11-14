# AXP8191, MMC0 and R-I2C0: build-tested, runtime unverified

## Linux 6.18 kernel and board DT

- `CONFIG_I2C_MV64XXX=y`; R-I2C0 node at `0x07083000` has `allwinner,sun60i-a733-i2c`, `allwinner,sun8i-v536-i2c`, and `allwinner,sun6i-a31-i2c` fallback strings.
- R-I2C0 pinctrl PL0/PL1 via `&r_i2c0_pl_pins`; AXP8191 at I²C address `0x36`. Driver's OF match `x-powers,axp8191`.
- MMC0 controller `0x04020000`, PF0-PF5 data/clock, PF6 active-low card detect, 4-bit bus. Conservative initial DT config uses 25 MHz and excludes UHS voltage switching.
- Vendor Zero 3W supply connections: `vmmc` <- DC1SW2, DC1SW2 parent DCDC1, and vendor 1.8V switching path CLDO5. Do not remove `vmmc-supply` as a generic workaround for regulator probe deferral.
- `CONFIG_MMC_SUNXI=y`, `CONFIG_EXT4_FS=y`, `CONFIG_MFD_AXP20X=y`, `CONFIG_MFD_AXP20X_I2C=y`, `CONFIG_REGULATOR_AXP20X=y`; checked in M2ch.

## Experimental AXP8191 register whitelist

| Register | Operation |
| --- | --- |
| `0x10` | DCDC1 enable, bit 0 |
| `0x11` | DC1SW2 enable, bit 4 |
| `0x12` | DCDC1 voltage selector |
| `0x21` | CLDO5 enable, bit 7 |
| `0x33` | CLDO5 voltage selector |

The WSL implementation permits these writes; it is **not** a read-only PMIC driver. M2cm checked vendor descriptor identifiers and enable/selector locations, yielding 11/11 source-presence consistency checks. That does not establish every boot-time write or safe regulator voltage transition. The first actual PMIC probe remains untested.

## Lessons from other A733 projects

- [nickyg666/orangepi-zero3w-mainline](https://github.com/nickyg666/orangepi-zero3w-mainline): reports MMC `EPROBE_DEFER` without a working PMIC provider, voltage negotiation failures without `vmmc-supply`, then a successful Linux 6.18.19 boot after fixing I²C/PMIC support and initramfs `switch_root`.
- [jonas5/Allwinner-A733-kernel](https://github.com/jonas5/Allwinner-A733-kernel): publishes A733 regulator descriptions and stepped transitions for CPU rails DCDC2/3/4; relevant to DVFS, **not** proof that our simplified three-rail provider is safe.
- The `AW_TWI` vendor-BSP fix from another project is not automatically relevant to our upstream `i2c-mv64xxx` path. Bind compatibility and actual hardware probe matter.

Our kernel's compiled artifacts: ARM64 `Image` SHA-256 `fbce9a31719eb2c140c240b2800531dfe4ba6e1dc9a69f29f7cdcce9614a5127`; Zero 3W `m2by.dtb` SHA-256 `577f128db2e67a7208451413bdd36b5280253e2e98d23382aa4a3bc8568243e2` (as reported from WSL). Source release `6.18.19-00022-g908869c38e30-dirty`; dirty worktree must be exported and reconstructed into a reviewable patch series.
